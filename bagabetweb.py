import streamlit as st
import pandas as pd
import random

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="BAGA GESTOR PRO", layout="wide", page_icon="🏆")

# --- INICIALIZAÇÃO ---
keys = {'teams': [], 'phase': 'setup', 'rounds': [], 'playoffs': [], 'waiting_next': [], 
        'champion': None, 'second_place': None, 'third_place': None}

for key, value in keys.items():
    if key not in st.session_state: st.session_state[key] = value

# --- FUNÇÕES ---
def get_rankings():
    # Lógica de desempate: Vitórias > Saldo > Gols Pró > Menos Gols Contra
    return sorted(st.session_state.teams, 
                  key=lambda x: (x['wins'], x['goal_diff'], x['goals_for'], -x['goals_against']), 
                  reverse=True)

def build_playoffs():
    qualified = [t for t in get_rankings() if t['status'] == 'Classificado']
    n = len(qualified)
    if n < 2: 
        st.error("Número insuficiente de classificados!")
        return
    
    st.session_state.waiting_next = []
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
    else:
        to_play = qualified
        
    waiting_ids = [w['id'] for w in st.session_state.waiting_next]
    for t in st.session_state.teams:
        if t['id'] in waiting_ids: t['received_bye'] = True

    matches = [{'home': to_play[i], 'away': to_play[-(i+1)], 'label': f'Eliminatória {i+1}'} for i in range(len(to_play)//2)]
    st.session_state.playoffs = [{'label': "Mata-Mata", 'matches': matches}]
    st.session_state.phase = 'playoff'

# --- SIDEBAR ---
with st.sidebar:
    st.title("📊 Ranking")
    if st.session_state.teams:
        # Ordenação para exibição
        df = pd.DataFrame(st.session_state.teams).sort_values(
            by=['wins', 'goal_diff', 'goals_for', 'goals_against'], 
            ascending=[False, False, False, True]
        )
        df_view = df[['name', 'wins', 'goal_diff', 'goals_for', 'goals_against', 'received_bye', 'status']].copy()
        df_view.columns = ['Time', 'V', 'SG', 'GP', 'GC', 'Bye', 'Status']
        df_view['Bye'] = df_view['Bye'].apply(lambda x: "⭐" if x else "")

        def color_status(val):
            if val == 'Classificado': color = '#d4edda'
            elif val == 'Eliminado': color = '#f8d7da'
            else: color = '#cce5ff'
            return f'background-color: {color}; color: black; font-weight: bold'

        # height=None faz a tabela crescer conforme o número de linhas
        st.dataframe(df_view.style.applymap(color_status, subset=['Status']), hide_index=True, height=None)
    
    if st.button("🗑️ Reset Total"):
        for k in keys: st.session_state[k] = keys[k]
        st.rerun()

# --- TELAS ---
if st.session_state.phase == 'setup':
    st.title("🏆 Configuração")
    num = st.number_input("Número de Equipes", 2, 64, 8)
    with st.form("f1"):
        names = [st.text_input(f"Time {i+1}", f"Equipe {i+1}", key=f"i{i}") for i in range(num)]
        if st.form_submit_button("Gerar Torneio"):
            st.session_state.teams = [{
                'id': i, 'name': n, 'wins': 0, 'losses': 0, 
                'goal_diff': 0, 'goals_for': 0, 'goals_against': 0,
                'received_bye': False, 'status': 'Ativo'
            } for i, n in enumerate(names)]
            st.session_state.phase = 'swiss'
            p = st.session_state.teams.copy(); random.shuffle(p)
            b = p.pop() if len(p)%2 != 0 else None
            if b:
                for t in st.session_state.teams:
                    if t['id'] == b['id']: t['received_bye'] = True
            st.session_state.rounds = [{'matches': [{'home': p[i]['id'], 'away': p[i+1]['id']} for i in range(0, len(p), 2)], 'bye': b}]
            st.rerun()

elif st.session_state.phase == 'swiss':
    st.title(f"⚽ Fase Suíça - Rodada {len(st.session_state.rounds)}")
    curr = st.session_state.rounds[-1]
    if curr.get('bye'): st.warning(f"⭐ Folga (Ganhou 1 Vitória): {curr['bye']['name']}")
    
    with st.form("fs"):
        res = []
        for i, m in enumerate(curr['matches']):
            t1 = next(t for t in st.session_state.teams if t['id'] == m['home'])
            t2 = next(t for t in st.session_state.teams if t['id'] == m['away'])
            c1, g1c, g2c, c2 = st.columns([2,1,1,2])
            g1 = g1c.number_input(t1['name'], 0, 100, key=f"s1{i}")
            g2 = g2c.number_input(t2['name'], 0, 100, key=f"s2{i}")
            res.append({'h': t1, 'a': t2, 'g1': g1, 'g2': g2})
            
        if st.form_submit_button("Confirmar Rodada"):
            if curr.get('bye'):
                for t in st.session_state.teams:
                    if t['id'] == curr['bye']['id']: t['wins'] += 1
            for r in res:
                # Atualiza Gols Pró, Contra e Saldo
                r['h']['goals_for'] += r['g1']; r['h']['goals_against'] += r['g2']
                r['a']['goals_for'] += r['g2']; r['a']['goals_against'] += r['g1']
                r['h']['goal_diff'] = r['h']['goals_for'] - r['h']['goals_against']
                r['a']['goal_diff'] = r['a']['goals_for'] - r['a']['goals_against']
                
                if r['g1'] > r['g2']: r['h']['wins'] += 1; r['a']['losses'] += 1
                else: r['a']['wins'] += 1; r['h']['losses'] += 1
                
            for t in st.session_state.teams:
                if t['wins'] >= 3: t['status'] = 'Classificado'
                elif t['losses'] >= 3: t['status'] = 'Eliminado'
                
            ativos = [t for t in st.session_state.teams if t['status'] == 'Ativo']
            if not ativos: st.session_state.phase = 'end_swiss'
            else:
                p = sorted(ativos, key=lambda x: (x['wins'], x['goal_diff'], x['goals_for'], -x['goals_against']), reverse=True)
                for t in st.session_state.teams: t['received_bye'] = False
                b = p.pop() if len(p)%2 != 0 else None
                if b:
                    for t in st.session_state.teams:
                        if t['id'] == b['id']: t['received_bye'] = True
                st.session_state.rounds.append({'matches': [{'home': p[i]['id'], 'away': p[i+1]['id']} for i in range(0, len(p), 2)], 'bye': b})
            st.rerun()

elif st.session_state.phase == 'end_swiss':
    st.title("🏁 Fase Suíça Encerrada")
    st.info("Os classificados foram definidos. Prepare-se para o Mata-Mata!")
    if st.button("🚀 Iniciar Mata-Mata"): build_playoffs(); st.rerun()

elif st.session_state.phase == 'playoff':
    st.title("🔥 Eliminatórias")
    venc, derr, ready = [], [], True
    for idx, p_round in enumerate(st.session_state.playoffs):
        st.subheader(p_round['label'])
        for i, m in enumerate(p_round['matches']):
            c1, g1c, g2c, c2 = st.columns([2,1,1,2])
            g1 = g1c.number_input(f"{m['home']['name']}", 0, 100, key=f"g1{idx}{i}")
            g2 = g2c.number_input(f"{m['away']['name']}", 0, 100, key=f"g2{idx}{i}")
            p1, p2 = 0, 0
            if g1 == g2:
                pc1, pc2 = st.columns(2)
                p1 = pc1.number_input(f"Pên {m['home']['name']}", 0, 100, key=f"p1{idx}{i}")
                p2 = pc2.number_input(f"Pên {m['away']['name']}", 0, 100, key=f"p2{idx}{i}")
                if p1 == p2: ready = False
            
            if g1 > g2 or (g1 == g2 and p1 > p2):
                venc.append({'t': m['home'], 'lbl': p_round['label'], 'g': g1, 'gc': g2})
                derr.append({'t': m['away'], 'lbl': p_round['label'], 'g': g2, 'gc': g1})
            else:
                venc.append({'t': m['away'], 'lbl': p_round['label'], 'g': g2, 'gc': g1})
                derr.append({'t': m['home'], 'lbl': p_round['label'], 'g': g1, 'gc': g2})

    if st.button("Confirmar e Avançar"):
        if ready:
            # Atualiza gols do mata-mata para o ranking final
            for item in (venc + derr):
                t_obj = next(t for t in st.session_state.teams if t['id'] == item['t']['id'])
                t_obj['goals_for'] += item['g']; t_obj['goals_against'] += item['gc']
                t_obj['goal_diff'] = t_obj['goals_for'] - t_obj['goals_against']

            final_match = next((v for v in venc if v['lbl'] == "Grande Final"), None)
            if final_match:
                st.session_state.champion = final_match['t']
                st.session_state.second_place = next(d['t'] for d in derr if d['lbl'] == "Grande Final")
                third_match = next((v for v in venc if v['lbl'] == "Disputa de 3º Lugar"), None)
                if third_match: st.session_state.third_place = third_match['t']
                st.session_state.phase = 'champion'
            else:
                proximos = st.session_state.waiting_next + [v['t'] for v in venc]
                st.session_state.waiting_next = []
                for t in st.session_state.teams: t['received_bye'] = False
                
                if len(proximos) == 2:
                    st.session_state.playoffs = [{'label': "Grande Final", 'matches': [{'home': proximos[0], 'away': proximos[1]}]}]
                    if len(derr) >= 2:
                        st.session_state.playoffs.append({'label': "Disputa de 3º Lugar", 'matches': [{'home': derr[0]['t'], 'away': derr[1]['t']}]})
                else:
                    proximos = sorted(proximos, key=lambda x: (x['wins'], x['goal_diff'], x['goals_for'], -x['goals_against']), reverse=True)
                    st.session_state.playoffs = [{'label': "Próxima Fase", 'matches': [{'home': proximos[i], 'away': proximos[-(i+1)]} for i in range(len(proximos)//2)]}]
            st.rerun()

elif st.session_state.phase == 'champion':
    st.balloons()
    st.markdown("<h1 style='text-align: center; color: #FFD700;'>🏆 PÓDIO FINAL 🏆</h1>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    if st.session_state.second_place: c1.info(f"🥈 **2º LUGAR**\n\n{st.session_state.second_place['name']}")
    if st.session_state.champion: c2.success(f"🥇 **CAMPEÃO**\n\n# {st.session_state.champion['name']}")
    if st.session_state.third_place: c3.warning(f"🥉 **3º LUGAR**\n\n{st.session_state.third_place['name']}")
    
    st.divider()
    st.subheader("📊 Classificação Geral Final")
    df_final = pd.DataFrame(st.session_state.teams).sort_values(
        by=['wins', 'goal_diff', 'goals_for', 'goals_against'], 
        ascending=[False, False, False, True]
    )
    df_final_view = df_final[['name', 'wins', 'goal_diff', 'goals_for', 'goals_against']].copy()
    df_final_view.columns = ['Equipe', 'Vitórias', 'Saldo de Gols', 'Gols Pró', 'Gols Contra']
    # Tabela final sem scroll
    st.table(df_final_view)

    if st.button("🔄 Iniciar Novo Torneio"):
        for k in keys: st.session_state[k] = keys[k]
        st.rerun()
