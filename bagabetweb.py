import streamlit as st
import pandas as pd
import random
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="BAGA GESTOR PRO", layout="wide", page_icon="🏆")

# --- INICIALIZAÇÃO ---
if 'teams' not in st.session_state: st.session_state.teams = []
if 'phase' not in st.session_state: st.session_state.phase = 'setup'
if 'rounds' not in st.session_state: st.session_state.rounds = []
if 'playoffs' not in st.session_state: st.session_state.playoffs = []
if 'waiting_next' not in st.session_state: st.session_state.waiting_next = []
if 'champion' not in st.session_state: st.session_state.champion = None

# --- FUNÇÕES ---

def get_rankings():
    return sorted(st.session_state.teams, key=lambda x: (x['wins'], -x['losses'], x['goal_diff']), reverse=True)

def update_bye_icons():
    """Garante que quem está esperando no Mata-Mata também receba a estrela visual"""
    waiting_ids = [t['id'] for t in st.session_state.waiting_next]
    for t in st.session_state.teams:
        if t['id'] in waiting_ids:
            t['received_bye'] = True
        else:
            # Opcional: manter False se quiser que a estrela suma após jogar
            pass

def build_playoffs():
    qualified = [t for t in get_rankings() if t['status'] == 'Classificado']
    n = len(qualified)
    if n == 0: return
    
    st.session_state.waiting_next = []
    # Resetamos os ícones de bye para o mata-mata para não confundir com o suíço
    for t in st.session_state.teams: t['received_bye'] = False

    if n == 6:
        st.session_state.waiting_next = qualified[:2]
        to_play = qualified[2:]
    elif n == 3:
        st.session_state.waiting_next = [qualified[0]]
        to_play = qualified[1:]
    elif n == 5:
        st.session_state.waiting_next = qualified[:3]
        to_play = qualified[3:]
    elif n == 7:
        st.session_state.waiting_next = [qualified[0]]
        to_play = qualified[1:]
    else:
        to_play = qualified
        
    update_bye_icons() # Marca as estrelas para quem vai esperar
    matches = [{'home': to_play[i], 'away': to_play[-(i+1)], 'label': f'Jogo {i+1}'} for i in range(len(to_play)//2)]
    st.session_state.playoffs.append({'label': "Mata-Mata", 'matches': matches})
    st.session_state.phase = 'playoff'

# --- BARRA LATERAL ---
with st.sidebar:
    st.title("📊 Ranking Geral")
    if st.session_state.teams:
        # Forçamos a criação de um novo DataFrame para garantir o refresh
        df_rank = pd.DataFrame(st.session_state.teams).sort_values(by=['wins', 'goal_diff'], ascending=[False, False])
        
        df_view = df_rank[['name', 'wins', 'losses', 'goal_diff', 'received_bye', 'status']].copy()
        df_view.columns = ['Time', 'V', 'D', 'SG', 'Bye', 'Status']
        
        # Lógica visual da Estrela
        df_view['Bye'] = df_view['Bye'].apply(lambda x: "⭐" if x is True else "")

        def style_status(val):
            if val == 'Classificado': return 'background-color: #d4edda; color: black; font-weight: bold'
            if val == 'Eliminado': return 'background-color: #f8d7da; color: black; font-weight: bold'
            return 'background-color: #cce5ff; color: black'

        st.dataframe(df_view.style.applymap(style_status, subset=['Status']), hide_index=True, use_container_width=True)
    
    if st.button("Reset Total"):
        st.session_state.clear()
        st.rerun()

# --- TELAS ---

if st.session_state.phase == 'setup':
    st.title("🏆 Configuração")
    num = st.number_input("Equipes", 2, 32, 8)
    with st.form("st"):
        names = [st.text_input(f"Time {i+1}", f"Equipe {i+1}", key=f"n{i}") for i in range(num)]
        if st.form_submit_button("Gerar Torneio"):
            st.session_state.teams = [{'id': i, 'name': n, 'wins': 0, 'losses': 0, 'goals_for': 0, 'goal_diff': 0, 'received_bye': False, 'status': 'Ativo'} for i, n in enumerate(names)]
            st.session_state.phase = 'swiss'
            # 1ª Rodada
            pool = st.session_state.teams.copy(); random.shuffle(pool)
            bye_t = pool.pop() if len(pool)%2 != 0 else None
            m = [{'home': pool[i]['id'], 'away': pool[i+1]['id']} for i in range(0, len(pool), 2)]
            st.session_state.rounds = [{'matches': m, 'bye': bye_t}]
            st.rerun()

elif st.session_state.phase == 'swiss':
    st.title(f"⚽ Fase Suíça - Rodada {len(st.session_state.rounds)}")
    curr = st.session_state.rounds[-1]
    
    if curr.get('bye'):
        st.warning(f"💎 **BYE (FOLGA):** {curr['bye']['name']} já recebeu +1 vitória.")

    with st.form("swiss_res"):
        res = []
        for i, m in enumerate(curr['matches']):
            t1 = next(t for t in st.session_state.teams if t['id'] == m['home'])
            t2 = next(t for t in st.session_state.teams if t['id'] == m['away'])
            c1, g1c, g2c, c2 = st.columns([2,1,1,2])
            g1 = g1c.number_input(t1['name'], 0, 50, key=f"g1{i}")
            g2 = g2c.number_input(t2['name'], 0, 50, key=f"g2{i}")
            res.append({'h_id': t1['id'], 'a_id': t2['id'], 'g1': g1, 'g2': g2})
        
        if st.form_submit_button("Confirmar Rodada"):
            # Marca o Bye do Suíço
            if curr.get('bye'):
                for t in st.session_state.teams:
                    if t['id'] == curr['bye']['id']:
                        t['wins'] += 1
                        t['received_bye'] = True 
            
            for r in res:
                t1 = next(t for t in st.session_state.teams if t['id'] == r['h_id'])
                t2 = next(t for t in st.session_state.teams if t['id'] == r['a_id'])
                t1['goal_diff'] += (r['g1']-r['g2']); t2['goal_diff'] += (r['g2']-r['g1'])
                if r['g1'] > r['g2']: t1['wins'] += 1; t2['losses'] += 1
                else: t2['wins'] += 1; t1['losses'] += 1
            
            for t in st.session_state.teams:
                if t['wins'] >= 3: t['status'] = 'Classificado'
                elif t['losses'] >= 3: t['status'] = 'Eliminado'
            
            ativos = [t for t in st.session_state.teams if t['status'] == 'Ativo']
            if not ativos: st.session_state.phase = 'end_swiss'
            else:
                # Gera próxima rodada suíça
                pool = sorted(ativos, key=lambda x: (x['wins'], -x['losses']), reverse=True)
                # Reseta estrelas do suíço para a nova rodada (opcional, mas limpa o visual)
                for t in st.session_state.teams: t['received_bye'] = False 
                nb = pool.pop() if len(pool)%2 != 0 else None
                nm = [{'home': pool[i]['id'], 'away': pool[i+1]['id']} for i in range(0, len(pool), 2)]
                st.session_state.rounds.append({'matches': nm, 'bye': nb})
            st.rerun()

elif st.session_state.phase == 'end_swiss':
    st.title("🏁 Suíço Encerrado")
    if st.button("🚀 GERAR MATA-MATA"):
        build_playoffs()
        st.rerun()

elif st.session_state.phase == 'playoff':
    curr_p = st.session_state.playoffs[-1]
    st.title(f"🔥 {curr_p['label']}")
    
    if st.session_state.waiting_next:
        st.info("🛡️ **Em espera para a próxima fase:** " + ", ".join([t['name'] for t in st.session_state.waiting_next]))

    vencedores = []
    ready = True
    for i, m in enumerate(curr_p['matches']):
        st.subheader(f"{m['label']}")
        c1, g1c, g2c, c2 = st.columns([2,1,1,2])
        g1 = g1c.number_input(f"{m['home']['name']}", 0, 50, key=f"pg1{i}")
        g2 = g2c.number_input(f"{m['away']['name']}", 0, 50, key=f"pg2{i}")
        p1, p2 = 0, 0
        if g1 == g2:
            st.caption("Empate! Defina nos Pênaltis:")
            pc1, pc2 = st.columns(2)
            p1 = pc1.number_input(f"Pên. {m['home']['name']}", 0, 50, key=f"pp1{i}")
            p2 = pc2.number_input(f"Pên. {m['away']['name']}", 0, 50, key=f"pp2{i}")
            if p1 == p2: ready = False
        vencedores.append(m['home'] if (g1 > g2 or (g1 == g2 and p1 > p2)) else m['away'])
    
    if st.button("Confirmar Ganhadores"):
        if ready:
            proximos = st.session_state.waiting_next + vencedores
            st.session_state.waiting_next = [] # Limpa quem estava esperando
            # Limpa estrelas para a próxima fase do mata-mata
            for t in st.session_state.teams: t['received_bye'] = False 
            
            if len(proximos) == 1:
                st.session_state.champion = proximos[0]
                st.session_state.phase = 'champion'
            else:
                proximos = sorted(proximos, key=lambda x: (x['wins'], x['goal_diff']), reverse=True)
                lbl = "Final" if len(proximos) == 2 else "Semifinais"
                # Aqui verificamos se a próxima fase também precisa de Bye (ex: se sobraram 3)
                if len(proximos) == 3:
                    st.session_state.waiting_next = [proximos[0]]
                    update_bye_icons()
                    to_play = proximos[1:]
                    prox_m = [{'home': to_play[0], 'away': to_play[1], 'label': 'Semifinal'}]
                else:
                    prox_m = [{'home': proximos[i], 'away': proximos[-(i+1)], 'label': f'Jogo {i+1}'} for i in range(len(proximos)//2)]
                
                st.session_state.playoffs.append({'label': lbl, 'matches': prox_m})
            st.rerun()
