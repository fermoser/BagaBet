import streamlit as st
import pandas as pd
import random
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="BAGA GESTOR PRO", layout="wide", page_icon="🏆")
conn = st.connection("gsheets", type=GSheetsConnection)

# --- ESTADO ---
if 'teams' not in st.session_state: st.session_state.teams = []
if 'phase' not in st.session_state: st.session_state.phase = 'setup'
if 'rounds' not in st.session_state: st.session_state.rounds = []
if 'playoffs' not in st.session_state: st.session_state.playoffs = []
if 'waiting_next' not in st.session_state: st.session_state.waiting_next = []

# --- FUNÇÕES ---
def get_rankings():
    return sorted(st.session_state.teams, key=lambda x: (x['wins'], -x['losses'], x['goal_diff']), reverse=True)

def build_playoffs():
    """Lógica Robusta de Chaveamento"""
    qualified = [t for t in get_rankings() if t['status'] == 'Classificado']
    n = len(qualified)
    
    if n == 0:
        st.error("Ninguém classificado!")
        return

    matches = []
    waiting = []

    # CASO ÍMPAR (Ex: 3 ou 5 ou 7 times)
    if n in [3, 5, 6, 7]:
        st.session_state.waiting_next = [qualified[0]] # O 1º lugar sempre espera
        to_play = qualified[1:] # O restante joga
        # Se sobraram 2 (total 3), fazem 1 jogo. Se sobraram 4 (total 5), fazem 2 jogos.
        matches = [{'home': to_play[i], 'away': to_play[-(i+1)], 'label': f'Jogo {i+1}'} for i in range(len(to_play)//2)]
        label = "Rodada de Acesso (1º lugar aguarda)"
    
    # CASO PAR PERFEITO (8, 4 ou 2)
    else:
        if n >= 8:
            top8 = qualified[:8]
            matches = [{'home': top8[i], 'away': top8[7-i], 'label': f'Quartas {i+1} ({i+1}ºx{8-i}º)'} for i in range(4)]
            label = "Quartas de Final"
        elif n >= 4:
            top4 = qualified[:4]
            matches = [{'home': top4[i], 'away': top4[3-i], 'label': f'Semi {i+1} ({i+1}ºx{4-i}º)'} for i in range(2)]
            label = "Semifinais"
        else:
            matches = [{'home': qualified[0], 'away': qualified[1], 'label': 'Grande Final'}]
            label = "Grande Final"

    st.session_state.playoffs.append({'label': label, 'matches': matches})
    st.session_state.phase = 'playoff'

# --- SIDEBAR ---
with st.sidebar:
    st.title("📊 Ranking")
    if st.session_state.teams:
        df_rank = pd.DataFrame(get_rankings())
        df_view = df_rank[['name', 'wins', 'losses', 'goal_diff', 'received_bye', 'status']].copy()
        df_view.columns = ['Time', 'V', 'D', 'SG', 'Bye', 'Status']
        df_view['Bye'] = df_view['Bye'].apply(lambda x: "⭐" if x else "")
        
        def style_status(val):
            if val == 'Classificado': return 'background-color: #d4edda; color: black; font-weight: bold'
            if val == 'Eliminado': return 'background-color: #f8d7da; color: black; font-weight: bold'
            return 'background-color: #cce5ff; color: black'
            
        st.dataframe(df_view.style.applymap(style_status, subset=['Status']), hide_index=True)
    
    if st.button("Reset Total"):
        st.session_state.clear()
        st.rerun()

# --- TELAS ---
if st.session_state.phase == 'setup':
    st.title("🏆 Configuração")
    num = st.number_input("Equipes", 2, 32, 8)
    with st.form("st"):
        names = [st.text_input(f"Time {i+1}", f"Equipe {i+1}") for i in range(num)]
        if st.form_submit_button("Gerar"):
            st.session_state.teams = [{'id': i, 'name': n, 'wins': 0, 'losses': 0, 'goals_for': 0, 'goal_diff': 0, 'received_bye': False, 'history': [], 'status': 'Ativo'} for i, n in enumerate(names)]
            st.session_state.phase = 'swiss'
            # 1ª Rodada
            pool = st.session_state.teams.copy(); random.shuffle(pool)
            bye_t = pool.pop() if len(pool)%2 != 0 else None
            m = [{'home': pool[i]['id'], 'away': pool[i+1]['id']} for i in range(0, len(pool), 2)]
            st.session_state.rounds = [{'matches': m, 'bye': bye_t}]
            st.rerun()

elif st.session_state.phase == 'swiss':
    st.title(f"⚽ Rodada {len(st.session_state.rounds)} (Suíço)")
    curr = st.session_state.rounds[-1]
    if curr.get('bye'): st.warning(f"⭐ **FOLGA:** {curr['bye']['name']} (+1 Vitória)")
    
    with st.form("sw"):
        res = []
        for i, m in enumerate(curr['matches']):
            t1 = next(t for t in st.session_state.teams if t['id'] == m['home'])
            t2 = next(t for t in st.session_state.teams if t['id'] == m['away'])
            c1, g1c, g2c, c2 = st.columns([2,1,1,2])
            g1 = g1c.number_input(t1['name'], 0, 50, key=f"g1_{i}")
            g2 = g2c.number_input(t2['name'], 0, 50, key=f"g2_{i}")
            res.append({'h_id': t1['id'], 'a_id': t2['id'], 'g1': g1, 'g2': g2})
        
        if st.form_submit_button("Confirmar Rodada"):
            if curr.get('bye'):
                for t in st.session_state.teams:
                    if t['id'] == curr['bye']['id']: t['wins'] += 1; t['received_bye'] = True
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
                pool = sorted(ativos, key=lambda x: (x['wins'], -x['losses']), reverse=True)
                nb = pool.pop() if len(pool)%2 != 0 else None
                nm = [{'home': pool[i]['id'], 'away': pool[i+1]['id']} for i in range(0, len(pool), 2)]
                st.session_state.rounds.append({'matches': nm, 'bye': nb})
            st.rerun()

elif st.session_state.phase == 'end_swiss':
    st.title("🏁 Suíço Encerrado")
    st.success("Tudo pronto para os Mata-Matas!")
    if st.button("🚀 GERAR MATA-MATA"):
        build_playoffs() # Chama a função que criamos lá em cima
        st.rerun()

elif st.session_state.phase == 'playoff':
    curr_p = st.session_state.playoffs[-1]
    st.title(f"🔥 {curr_p['label']}")
    
    if st.session_state.waiting_next:
        st.info("⏳ **Aguardando na próxima fase:** " + ", ".join([t['name'] for t in st.session_state.waiting_next]))

    with st.form("pl"):
        vencedores = []
        for i, m in enumerate(curr_p['matches']):
            st.subheader(f"{m['label']}")
            c1, g1c, g2c, c2 = st.columns([2,1,1,2])
            g1 = g1c.number_input(m['home']['name'], 0, 50, key=f"p1_{i}")
            g2 = g2c.number_input(m['away']['name'], 0, 50, key=f"p2_{i}")
            vencedores.append(m['home'] if g1 > g2 else m['away'])
        
        if st.form_submit_button("Avançar"):
            # Junta os vencedores com quem estava esperando
            proximos = st.session_state.waiting_next + vencedores
            st.session_state.waiting_next = [] # Limpa a espera
            
            if len(proximos) == 1:
                st.session_state.champion = proximos[0]
                st.session_state.phase = 'champion'
            else:
                # Ordena por campanha para o próximo chaveamento
                proximos = sorted(proximos, key=lambda x: (x['wins'], x['goal_diff']), reverse=True)
                prox_label = "Grande Final" if len(proximos) == 2 else "Semifinais"
                prox_matches = [{'home': proximos[i], 'away': proximos[-(i+1)], 'label': f'Jogo {i+1}'} for i in range(len(proximos)//2)]
                st.session_state.playoffs.append({'label': prox_label, 'matches': prox_matches})
            st.rerun()

elif st.session_state.phase == 'champion':
    st.balloons()
    st.markdown(f"<h1 style='text-align: center;'>🏆 CAMPEÃO: {st.session_state.champion['name']}</h1>", unsafe_allow_html=True)
    if st.button("Novo Torneio"): st.session_state.clear(); st.rerun()
