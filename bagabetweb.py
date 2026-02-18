import streamlit as st
import pandas as pd
import random

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="BAGA GESTOR PRO", layout="wide", page_icon="🏆")

# --- INICIALIZAÇÃO ---
for key in ['teams', 'phase', 'rounds', 'playoffs', 'waiting_next', 'champion', 'second_place', 'third_place']:
    if key not in st.session_state:
        st.session_state[key] = [] if key in ['teams', 'rounds', 'playoffs', 'waiting_next'] else None

# --- FUNÇÕES ---
def get_rankings():
    return sorted(st.session_state.teams, key=lambda x: (x['wins'], -x['losses'], x['goal_diff']), reverse=True)

def build_playoffs():
    qualified = [t for t in get_rankings() if t['status'] == 'Classificado']
    n = len(qualified)
    if n == 0: return
    
    st.session_state.waiting_next = []
    for t in st.session_state.teams: t['received_bye'] = False

    if n == 6:
        st.session_state.waiting_next = qualified[:2]
        to_play = qualified[2:]
    elif n == 3:
        st.session_state.waiting_next = [qualified[0]]
        to_play = qualified[1:]
    else:
        to_play = qualified
        
    for t in st.session_state.teams:
        if t['id'] in [w['id'] for w in st.session_state.waiting_next]: t['received_bye'] = True

    matches = [{'home': to_play[i], 'away': to_play[-(i+1)], 'label': f'Jogo {i+1}'} for i in range(len(to_play)//2)]
    st.session_state.playoffs.append({'label': "Mata-Mata", 'matches': matches})
    st.session_state.phase = 'playoff'

# --- SIDEBAR ---
with st.sidebar:
    st.title("📊 Ranking")
    if st.session_state.teams:
        df_rank = pd.DataFrame(st.session_state.teams).sort_values(by=['wins', 'goal_diff'], ascending=[False, False])
        df_view = df_rank[['name', 'wins', 'losses', 'goal_diff', 'received_bye', 'status']].copy()
        df_view.columns = ['Time', 'V', 'D', 'SG', 'Bye', 'Status']
        df_view['Bye'] = df_view['Bye'].apply(lambda x: "⭐" if x is True else "")
        def style_status(val):
            color = '#d4edda' if val == 'Classificado' else '#f8d7da' if val == 'Eliminado' else '#cce5ff'
            return f'background-color: {color}; color: black; font-weight: bold'
        st.dataframe(df_view.style.applymap(style_status, subset=['Status']), hide_index=True)
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
            st.session_state.teams = [{'id': i, 'name': n, 'wins': 0, 'losses': 0, 'goal_diff': 0, 'received_bye': False, 'status': 'Ativo'} for i, n in enumerate(names)]
            st.session_state.phase = 'swiss'
            pool = st.session_state.teams.copy(); random.shuffle(pool)
            bye_t = pool.pop() if len(pool)%2 != 0 else None
            st.session_state.rounds = [{'matches': [{'home': pool[i]['id'], 'away': pool[i+1]['id']} for i in range(0, len(pool), 2)], 'bye': bye_t}]
            st.rerun()

elif st.session_state.phase == 'swiss':
    st.title(f"⚽ Suíço - Rodada {len(st.session_state.rounds)}")
    curr = st.session_state.rounds[-1]
    if curr.get('bye'): st.warning(f"⭐ **FOLGA:** {curr['bye']['name']}")
    with st.form("sw"):
        res = []
        for i, m in enumerate(curr['matches']):
            t1 = next(t for t in st.session_state.teams if t['id'] == m['home'])
            t2 = next(t for t in st.session_state.teams if t['id'] == m['away'])
            c1, g1c, g2c, c2 = st.columns([2,1,1,2])
            g1 = g1c.number_input(t1['name'], 0, 50, key=f"g1{i}")
            g2 = g2c.number_input(t2['name'], 0, 50, key=f"g2{i}")
            res.append({'h_id': t1['id'], 'a_id': t2['id'], 'g1': g1, 'g2': g2})
        if st.form_submit_button("Confirmar Rodada"):
            if curr.get('bye'):
                for t in st.session_state.teams:
                    if t['id'] == curr['bye']['id']: t['wins'] += 1; t['received_bye'] = True
            for r in res:
                t1, t2 = next(t for t in st.session_state.teams if t['id'] == r['h_id']), next(t for t in st.session_state.teams if t['id'] == r['a_id'])
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
                for t in st.session_state.teams: t['received_bye'] = False
                nb = pool.pop() if len(pool)%2 != 0 else None
                st.session_state.rounds.append({'matches': [{'home': pool[i]['id'], 'away': pool[i+1]['id']} for i in range(0, len(pool), 2)], 'bye': nb})
            st.rerun()

elif st.session_state.phase == 'end_swiss':
    st.title("🏁 Suíço Encerrado")
    if st.button("🚀 INICIAR MATA-MATA"): build_playoffs(); st.rerun()

elif st.session_state.phase == 'playoff':
    curr_p = st.session_state.playoffs[-1]
    st.title(f"🔥 {curr_p['label']}")
    
    with st.container():
        venc, derr, ready = [], [], True
        for i, m in enumerate(curr_p['matches']):
            st.subheader(m['label'])
            c1, g1c, g2c, c2 = st.columns([2,1,1,2])
            g1, g2 = g1c.number_input(m['home']['name'], 0, 50, key=f"pg1{i}"), g2c.number_input(m['away']['name'], 0, 50, key=f"pg2{i}")
            p1, p2 = 0, 0
            if g1 == g2:
                pc1, pc2 = st.columns(2); p1, p2 = pc1.number_input(f"Pên {m['home']['name']}", 0, key=f"pp1{i}"), pc2.number_input(f"Pên {m['away']['name']}", 0, key=f"pp2{i}")
                if p1 == p2: ready = False
            if g1 > g2 or (g1 == g2 and p1 > p2): venc.append(m['home']); derr.append(m['away'])
            else: venc.append(m['away']); derr.append(m['home'])

        if st.button("Confirmar e Avançar"):
            if ready:
                if curr_p['label'] == "Grande Final":
                    st.session_state.champion = venc[0]; st.session_state.second_place = derr[0]
                    st.session_state.phase = 'champion'
                elif curr_p['label'] == "Disputa de 3º Lugar":
                    st.session_state.third_place = venc[0]
                else:
                    proximos = st.session_state.waiting_next + venc
                    st.session_state.waiting_next = []
                    for t in st.session_state.teams: t['received_bye'] = False
                    if len(proximos) == 2:
                        st.session_state.playoffs.append({'label': "Grande Final", 'matches': [{'home': proximos[0], 'away': proximos[1], 'label': 'FINAL'}]})
                        # Só gera 3º lugar se veio de uma Semi (venceram 2)
                        if len(derr) >= 2: st.session_state.playoffs.append({'label': "Disputa de 3º Lugar", 'matches': [{'home': derr[0], 'away': derr[1], 'label': '3º LUGAR'}]})
                    else:
                        proximos = sorted(proximos, key=lambda x: (x['wins'], x['goal_diff']), reverse=True)
                        st.session_state.playoffs.append({'label': "Próxima Fase", 'matches': [{'home': proximos[i], 'away': proximos[-(i+1)], 'label': f'Jogo {i+1}'} for i in range(len(proximos)//2)]})
                st.rerun()

elif st.session_state.phase == 'champion':
    st.balloons()
    st.markdown("<h1 style='text-align: center;'>🏆 PÓDIO FINAL</h1>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    if st.session_state.second_place: c1.metric("🥈 2º LUGAR", st.session_state.second_place['name'])
    if st.session_state.champion: c2.metric("🥇 CAMPEÃO", st.session_state.champion['name'])
    if st.session_state.third_place: c3.metric("🥉 3º LUGAR", st.session_state.third_place['name'])
    if st.button("Novo Torneio"): st.session_state.clear(); st.rerun()
