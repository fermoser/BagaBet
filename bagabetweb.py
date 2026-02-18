import streamlit as st
import pandas as pd
import random

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="BAGA GESTOR PRO", layout="wide", page_icon="🏆")

# --- INICIALIZAÇÃO SEGURA DO ESTADO ---
keys = {
    'teams': [],
    'phase': 'setup',
    'rounds': [],
    'playoffs': [],
    'waiting_next': [],
    'champion': None,
    'second_place': None,
    'third_place': None
}

for key, value in keys.items():
    if key not in st.session_state:
        st.session_state[key] = value

# --- FUNÇÕES AUXILIARES ---
def get_rankings():
    return sorted(st.session_state.teams, key=lambda x: (x['wins'], -x['losses'], x['goal_diff']), reverse=True)

def build_playoffs():
    qualified = [t for t in get_rankings() if t['status'] == 'Classificado']
    n = len(qualified)
    if n == 0:
        st.error("Ninguém classificado!")
        return
    
    st.session_state.waiting_next = []
    # Reseta estrelas para o mata-mata
    for t in st.session_state.teams: t['received_bye'] = False

    # Lógica de chaveamento para números não-potência de 2
    if n == 6:
        st.session_state.waiting_next = qualified[:2]
        to_play = qualified[2:]
    elif n == 3:
        st.session_state.waiting_next = [qualified[0]]
        to_play = qualified[1:]
    elif n == 5:
        st.session_state.waiting_next = qualified[:3]
        to_play = qualified[3:]
    else:
        to_play = qualified
        
    for t in st.session_state.teams:
        if t['id'] in [w['id'] for w in st.session_state.waiting_next]: t['received_bye'] = True

    matches = [{'home': to_play[i], 'away': to_play[-(i+1)], 'label': f'Jogo {i+1}'} for i in range(len(to_play)//2)]
    st.session_state.playoffs = [{'label': "Mata-Mata", 'matches': matches}]
    st.session_state.phase = 'playoff'

# --- BARRA LATERAL (RANKING) ---
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
    
    if st.button("🗑️ Reset Total"):
        for key in keys: st.session_state[key] = keys[key]
        st.rerun()

# --- FLUXO DE TELAS ---

# 1. TELA DE CONFIGURAÇÃO
if st.session_state.phase == 'setup':
    st.title("🏆 Configuração do Torneio")
    num = st.number_input("Número de equipes", 2, 32, 8)
    with st.form("setup_form"):
        names = [st.text_input(f"Equipe {i+1}", f"Time {i+1}", key=f"inp_{i}") for i in range(num)]
        if st.form_submit_button("INICIAR TORNEIO"):
            st.session_state.teams = [{'id': i, 'name': n, 'wins': 0, 'losses': 0, 'goal_diff': 0, 'received_bye': False, 'status': 'Ativo'} for i, n in enumerate(names)]
            st.session_state.phase = 'swiss'
            pool = st.session_state.teams.copy()
            random.shuffle(pool)
            bye_t = pool.pop() if len(pool)%2 != 0 else None
            st.session_state.rounds = [{'matches': [{'home': pool[i]['id'], 'away': pool[i+1]['id']} for i in range(0, len(pool), 2)], 'bye': bye_t}]
            st.rerun()

# 2. FASE SUÍÇA
elif st.session_state.phase == 'swiss':
    st.title(f"⚽ Fase Suíça - Rodada {len(st.session_state.rounds)}")
    curr = st.session_state.rounds[-1]
    if curr.get('bye'): st.warning(f"⭐ **FOLGA (BYE):** {curr['bye']['name']}")
    
    with st.form("swiss_form"):
        res = []
        for i, m in enumerate(curr['matches']):
            t1 = next(t for t in st.session_state.teams if t['id'] == m['home'])
            t2 = next(t for t in st.session_state.teams if t['id'] == m['away'])
            c1, g1c, g2c, c2 = st.columns([2,1,1,2])
            g1 = g1c.number_input(t1['name'], 0, 50, key=f"s1_{i}")
            g2 = g2c.number_input(t2['name'], 0, 50, key=f"s2_{i}")
            res.append({'h_id': t1['id'], 'a_id': t2['id'], 'g1': g1, 'g2': g2})
        
        if st.form_submit_button("Confirmar Resultados"):
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
            if not ativos:
                st.session_state.phase = 'end_swiss'
            else:
                pool = sorted(ativos, key=lambda x: (x['wins'], -x['losses']), reverse=True)
                for t in st.session_state.teams: t['received_bye'] = False
                nb = pool.pop() if len(pool)%2 != 0 else None
                st.session_state.rounds.append({'matches': [{'home': pool[i]['id'], 'away': pool[i+1]['id']} for i in range(0, len(pool), 2)], 'bye': nb})
            st.rerun()

# 3. FIM DO SUÍÇO
elif st.session_state.phase == 'end_swiss':
    st.title("🏁 Suíço Encerrado")
    if st.button("🚀 GERAR MATA-MATA"):
        build_playoffs()
        st.rerun()

# 4. MATA-MATA (CHAVEAMENTO)
elif st.session_state.phase == 'playoff':
    st.title("🔥 Fase Eliminatória")
    venc, derr, ready = [], [], True
    
    for idx, p_round in enumerate(st.session_state.playoffs):
        st.subheader(f"📍 {p_round['label']}")
        for i, m in enumerate(p_round['matches']):
            c1, g1c, g2c, c2 = st.columns([2,1,1,2])
            g1 = g1c.number_input(f"{m['home']['name']}", 0, 50, key=f"pg1_{idx}_{i}")
            g2 = g2c.number_input(f"{m['away']['name']}", 0, 50, key=f"pg2_{idx}_{i}")
            p1, p2 = 0, 0
            if g1 == g2:
                pc1, pc2 = st.columns(2)
                p1 = pc1.number_input(f"Pên {m['home']['name']}", 0, 50, key=f"pp1_{idx}_{i}")
                p2 = pc2.number_input(f"Pên {m['away']['name']}", 0, 50, key=f"pp2_{idx}_{i}")
                if p1 == p2: ready = False
            
            if g1 > g2 or (g1 == g2 and p1 > p2):
                venc.append(m['home']); derr.append(m['away'])
            else:
                venc.append(m['away']); derr.append(m['home'])

    if st.button("Confirmar Rodada Eliminatória"):
        if not ready:
            st.error("Pênaltis não podem empatar!")
        else:
            current_label = st.session_state.playoffs[-1]['label']
            
            if current_label == "Grande Final":
                st.session_state.champion = venc[-1] # Vendedor da Final
                st.session_state.second_place = derr[-1] # Perdedor da Final
                st.session_state.phase = 'champion'
            elif current_label == "Disputa de 3º Lugar":
                st.session_state.third_place = venc[-1]
            else:
                proximos = st.session_state.waiting_next + venc
                st.session_state.waiting_next = []
                for t in st.session_state.teams: t['received_bye'] = False
                
                if len(proximos) == 2:
                    # Gera Final e 3º lugar simultaneamente
                    st.session_state.playoffs = [
                        {'label': "Grande Final", 'matches': [{'home': proximos[0], 'away': proximos[1], 'label': 'FINAL'}]},
                        {'label': "Disputa de 3º Lugar", 'matches': [{'home': derr[0], 'away': derr[1], 'label': '3º LUGAR'}]}
                    ]
                else:
                    proximos = sorted(proximos, key=lambda x: (x['wins'], x['goal_diff']), reverse=True)
                    st.session_state.playoffs = [{'label': "Próxima Fase", 'matches': [{'home': proximos[i], 'away': proximos[-(i+1)], 'label': f'Jogo {i+1}'} for i in range(len(proximos)//2)]}]
            st.rerun()

# 5. PODIUM FINAL
elif st.session_state.phase == 'champion':
    st.balloons()
    st.markdown("<h1 style='text-align: center;'>🏆 RESULTADO FINAL</h1>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    if st.session_state.champion:
        c2.metric("🥇 1º LUGAR (CAMPEÃO)", st.session_state.champion['name'])
    if st.session_state.second_place:
        c1.metric("🥈 2º LUGAR", st.session_state.second_place['name'])
    if st.session_state.third_place:
        c3.metric("🥉 3º LUGAR", st.session_state.third_place['name'])
    
    st.divider()
    if st.button("🔄 Novo Torneio"):
        for key in keys: st.session_state[key] = keys[key]
        st.rerun()
