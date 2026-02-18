import streamlit as st
import pandas as pd
import random
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="BAGA GESTOR PRO", layout="wide", page_icon="🏆")
conn = st.connection("gsheets", type=GSheetsConnection)

# --- INICIALIZAÇÃO DE ESTADO ---
if 'teams' not in st.session_state: st.session_state.teams = []
if 'phase' not in st.session_state: st.session_state.phase = 'setup'
if 'rounds' not in st.session_state: st.session_state.rounds = []
if 'playoffs' not in st.session_state: st.session_state.playoffs = []
if 'waiting_next_round' not in st.session_state: st.session_state.waiting_next_round = []
if 'champion' not in st.session_state: st.session_state.champion = None

# --- FUNÇÕES CORE ---

def sync_to_sheets():
    if not st.session_state.teams:
        cols = ['id', 'name', 'wins', 'losses', 'goals_for', 'goal_diff', 'received_bye', 'history', 'status']
        df_save = pd.DataFrame(columns=cols)
    else:
        df_save = pd.DataFrame(st.session_state.teams)
        df_save['history'] = df_save['history'].apply(lambda x: str(x))
    conn.update(worksheet="Suico", data=df_save)

def get_rankings():
    return sorted(st.session_state.teams, key=lambda x: (
        x['wins'], -x['losses'], x['goal_diff'], x['goals_for']
    ), reverse=True)

def setup_playoffs():
    """Lógica de Bye por Mérito: Melhores esperam se o número for ímpar ou quebrado"""
    qualified = [t for t in get_rankings() if t['status'] == 'Classificado']
    n = len(qualified)
    
    if n == 0:
        st.error("Ninguém classificado para o Mata-Mata!")
        return

    matches = []
    waiting = []

    # Caso 3 times: 1º espera, 2º x 3º jogam semi
    if n == 3:
        label = "Semifinal"
        waiting = [qualified[0]]
        matches = [{'home': qualified[1], 'away': qualified[2], 'label': 'Semi'}]
    
    # Caso 5, 6 ou 7: Melhores esperam para fechar chave de 4 (Semi)
    elif 4 < n < 8:
        label = "Rodada Preliminar"
        num_to_play = (n - 4) * 2
        to_play = qualified[-num_to_play:]
        waiting = qualified[:n-num_to_play]
        # Pareamento invertido para preliminar: melhor dos piores vs pior dos piores
        matches = [{'home': to_play[i], 'away': to_play[-(i+1)], 'label': f'Preliminar {i+1}'} for i in range(len(to_play)//2)]
    
    # Chaves padrão (2, 4, 8)
    else:
        if n >= 8:
            label, top = "Quartas de Final", qualified[:8]
            matches = [{'home': top[i], 'away': top[7-i], 'label': f'Quarta {i+1}'} for i in range(4)]
        elif n >= 4:
            label, top = "Semifinais", qualified[:4]
            matches = [{'home': top[i], 'away': top[3-i], 'label': f'Semi {i+1}'} for i in range(2)]
        else:
            label, top = "Grande Final", qualified[:2]
            matches = [{'home': top[0], 'away': top[1], 'label': 'Final'}]

    st.session_state.playoffs.append({'label': label, 'matches': matches})
    st.session_state.waiting_next_round = waiting
    st.session_state.phase = 'playoff'

# --- BARRA LATERAL ESTILIZADA ---
with st.sidebar:
    st.title("📊 Ranking em Tempo Real")
    if st.session_state.teams:
        df_rank = pd.DataFrame(get_rankings())
        
        # Função para aplicar cores
        def color_status(val):
            if val == 'Classificado': return 'background-color: #d4edda; color: #155724' # Verde
            if val == 'Eliminado': return 'background-color: #f8d7da; color: #721c24'    # Vermelho
            return 'background-color: #cce5ff; color: #004085'                         # Azul
        
        df_view = df_rank[['name', 'wins', 'losses', 'goal_diff', 'received_bye', 'status']].copy()
        df_view.columns = ['Time', 'V', 'D', 'SG', 'Bye', 'Status']
        df_view['Bye'] = df_view['Bye'].map({True: '⭐', False: ''})
        
        st.dataframe(df_view.style.applymap(color_status, subset=['Status']), hide_index=True, use_container_width=True)
    
    st.divider()
    if st.button("🗑️ Reset Total do Torneio"):
        st.session_state.clear()
        st.rerun()

# --- TELAS ---

if st.session_state.phase == 'setup':
    st.title("🏆 Início do Torneio")
    num = st.number_input("Quantos times vão jogar?", 2, 32, 8)
    with st.form("st_form"):
        names = [st.text_input(f"Time {i+1}", f"Equipe {i+1}", key=f"t_{i}") for i in range(num)]
        if st.form_submit_button("GERAR CHAVEAMENTO INICIAL"):
            st.session_state.teams = [{'id': i, 'name': n, 'wins': 0, 'losses': 0, 'goals_for': 0, 'goal_diff': 0, 'received_bye': False, 'history': [], 'status': 'Ativo'} for i, n in enumerate(names)]
            st.session_state.phase = 'swiss'
            # Gerar 1ª rodada aleatória
            pool = st.session_state.teams.copy()
            random.shuffle(pool)
            bye_t = pool.pop() if len(pool)%2 != 0 else None
            m = [{'home': pool[i]['id'], 'away': pool[i+1]['id']} for i in range(0, len(pool), 2)]
            st.session_state.rounds = [{'matches': m, 'bye': bye_t}]
            st.rerun()

elif st.session_state.phase == 'swiss':
    st.title(f"⚔️ Fase Suíça - Rodada {len(st.session_state.rounds)}")
    curr = st.session_state.rounds[-1]
    
    if curr.get('bye'):
        st.success(f"💎 **FOLGA (BYE):** {curr['bye']['name']} recebe +1 Vitória e aguarda.")

    with st.form("swiss_form"):
        res = []
        for i, m in enumerate(curr['matches']):
            t1 = next(t for t in st.session_state.teams if t['id'] == m['home'])
            t2 = next(t for t in st.session_state.teams if t['id'] == m['away'])
            c1, g1c, g2c, c2 = st.columns([3,1,1,3])
            with c1: st.markdown(f"**{t1['name']}**")
            g1 = g1c.number_input("Gols", 0, 50, key=f"s1_{i}", label_visibility="collapsed")
            g2 = g2c.number_input("Gols", 0, 50, key=f"s2_{i}", label_visibility="collapsed")
            with c2: st.markdown(f"**{t2['name']}**")
            res.append({'h': t1, 'a': t2, 'g1': g1, 'g2': g2})
        
        if st.form_submit_button("Salvar Resultados"):
            if curr.get('bye'):
                curr['bye']['wins'] += 1; curr['bye']['received_bye'] = True
            for r in res:
                r['h']['goals_for'] += r['g1']; r['a']['goals_for'] += r['g2']
                r['h']['goal_diff'] += (r['g1']-r['g2']); r['a']['goal_diff'] += (r['g2']-r['g1'])
                if r['g1'] > r['g2']: r['h']['wins'] += 1; r['a']['losses'] += 1
                else: r['a']['wins'] += 1; r['h']['losses'] += 1
                r['h']['history'].append(r['a']['id']); r['a']['history'].append(r['h']['id'])
            
            for t in st.session_state.teams:
                if t['wins'] >= 3: t['status'] = 'Classificado'
                elif t['losses'] >= 3: t['status'] = 'Eliminado'
            
            sync_to_sheets()
            ativos = [t for t in st.session_state.teams if t['status'] == 'Ativo']
            if not ativos: st.session_state.phase = 'end_swiss'
            else:
                # Gerar próxima rodada suíça real
                pool = sorted(ativos, key=lambda x: (x['wins'], -x['losses']), reverse=True)
                bye_t = pool.pop() if len(pool)%2 != 0 else None
                new_m = [{'home': pool[i]['id'], 'away': pool[i+1]['id']} for i in range(0, len(pool), 2)]
                st.session_state.rounds.append({'matches': new_m, 'bye': bye_t})
            st.rerun()

elif st.session_state.phase == 'end_swiss':
    st.title("🏁 Suíço Finalizado")
    st.balloons()
    st.info("Todos os times atingiram 3 vitórias ou 3 derrotas. Verifique o ranking lateral.")
    if st.button("🔥 GERAR MATA-MATA"):
        setup_playoffs()
        st.rerun()

elif st.session_state.phase == 'playoff':
    curr_p = st.session_state.playoffs[-1]
    st.title(f"🔥 {curr_p['label']}")
    
    

    if st.session_state.waiting_next_round:
        st.info("🛡️ **Times em Espera (Avançam Direto):** " + ", ".join([t['name'] for t in st.session_state.waiting_next_round]))

    with st.form("playoff_form"):
        winners = []
        for i, m in enumerate(curr_p['matches']):
            st.subheader(f"{m['label']}")
            c1, g1c, g2c, c2 = st.columns([3,1,1,3])
            g1 = g1c.number_input(m['home']['name'], 0, 50, key=f"pg1_{i}")
            g2 = g2c.number_input(m['away']['name'], 0, 50, key=f"pg2_{i}")
            p1, p2 = 0, 0
            if g1 == g2:
                pc1, pc2 = st.columns(2)
                p1, p2 = pc1.number_input("Pên. Casa", 0, key=f"pp1_{i}"), pc2.number_input("Pên. Fora", 0, key=f"pp2_{i}")
            winners.append(m['home'] if (g1 > g2 or (g1 == g2 and p1 > p2)) else m['away'])
        
        if st.form_submit_button("Confirmar Ganhadores"):
            # Une quem venceu com quem estava esperando
            all_next = st.session_state.waiting_next_round + winners
            st.session_state.waiting_next_round = []
            
            if len(all_next) == 1:
                st.session_state.champion = all_next[0]
                st.session_state.phase = 'champion'
            else:
                # Chaveamento automático dos classificados
                all_next = sorted(all_next, key=lambda x: (x['wins'], x['goal_diff']), reverse=True)
                lbl = "Grande Final" if len(all_next) == 2 else "Semifinais"
                new_m = [{'home': all_next[i], 'away': all_next[-(i+1)], 'label': f'Jogo {i+1}'} for i in range(len(all_next)//2)]
                st.session_state.playoffs.append({'label': lbl, 'matches': new_m})
            st.rerun()

elif st.session_state.phase == 'champion':
    st.balloons()
    st.markdown(f"<h1 style='text-align: center; color: #FFD700;'>🏆 CAMPEÃO: {st.session_state.champion['name']}</h1>", unsafe_allow_html=True)
    if st.button("Reiniciar Sistema"): st.session_state.clear(); st.rerun()
