import streamlit as st
import pandas as pd
import random
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="BAGA GESTOR PRO", layout="wide", page_icon="🏆")

# --- CONEXÃO GOOGLE SHEETS ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    SHEET_ENABLED = True
except Exception as e:
    st.error(f"Erro de Conexão: {e}")
    SHEET_ENABLED = False

# --- INICIALIZAÇÃO ---
# Adicionado 'bye_history' para rastrear IDs que já folgaram
keys = {'tournament_name': "", 'teams': [], 'phase': 'setup', 'rounds': [], 'playoffs': [], 
        'waiting_next': [], 'champion': None, 'second_place': None, 'third_place': None, 'bye_history': []}

for key, value in keys.items():
    if key not in st.session_state: st.session_state[key] = value

# --- FUNÇÃO DE SALVAMENTO ---
def save_to_sheets():
    if not SHEET_ENABLED or not st.session_state.teams or st.session_state.phase == 'setup': 
        return
    try:
        df_to_save = pd.DataFrame(st.session_state.teams)
        df_to_save['tournament_name'] = st.session_state.tournament_name
        if 'received_bye' in df_to_save.columns:
            df_to_save['received_bye'] = df_to_save['received_bye'].apply(lambda x: "SIM" if str(x).upper() in ["TRUE", "SIM", "1"] else "NÃO")
        df_to_save = df_to_save.astype(str)
        try:
            existing_data = conn.read(worksheet="suico", ttl=0)
            if existing_data is not None and not existing_data.empty:
                other_tournaments = existing_data[existing_data['tournament_name'] != st.session_state.tournament_name]
                df_final = pd.concat([other_tournaments, df_to_save], ignore_index=True)
            else:
                df_final = df_to_save
        except:
            df_final = df_to_save
        conn.update(worksheet="suico", data=df_final)
        st.toast(f"✅ Dados Sincronizados")
    except Exception as e:
        st.error(f"⚠️ Erro ao salvar: {e}")

# --- FUNÇÕES DE LÓGICA ---
def get_rankings():
    return sorted(st.session_state.teams, 
                  key=lambda x: (int(x['wins']), int(x['goal_diff']), int(x['goals_for']), -int(x['goals_against']), -int(x['losses'])), 
                  reverse=True)

# --- SIDEBAR ---
with st.sidebar:
    st.title("📊 Ranking")
    if st.session_state.tournament_name:
        st.subheader(f"🏆 {st.session_state.tournament_name}")
    if st.session_state.teams:
        df_rank = pd.DataFrame(st.session_state.teams)
        for col in ['wins', 'losses', 'goal_diff', 'goals_for', 'goals_against']:
            df_rank[col] = pd.to_numeric(df_rank[col], errors='coerce').fillna(0).astype(int)
        df_rank = df_rank.sort_values(by=['wins', 'goal_diff', 'goals_for', 'goals_against', 'losses'], ascending=[False, False, False, True, True])
        df_view = df_rank[['name', 'wins', 'losses', 'goal_diff', 'goals_for', 'goals_against', 'received_bye', 'status']].copy()
        df_view.columns = ['Time', 'V', 'D', 'SG', 'GP', 'GC', '⭐', 'Status']
        df_view['⭐'] = df_view['⭐'].apply(lambda x: "⭐" if str(x).upper() in ["TRUE", "SIM", "1"] else "")
        def color_status(val):
            if val == 'Classificado': return 'background-color: #d4edda; color: black; font-weight: bold'
            if val == 'Eliminado': return 'background-color: #f8d7da; color: black; font-weight: bold'
            return 'background-color: #cce5ff; color: black; font-weight: bold'
        st.dataframe(df_view.style.applymap(color_status, subset=['Status']), hide_index=True, use_container_width=True)
    if st.button("🗑️ Reset / Novo Torneio"):
        for k in keys: st.session_state[k] = keys[k]
        st.rerun()

# --- TELAS ---
if st.session_state.phase == 'setup':
    st.title("🚀 Novo Torneio Suíço")
    c1, c2 = st.columns([2, 1])
    t_name = c1.text_input("Nome do Torneio")
    num = c2.number_input("Equipes", 2, 64, 8)
    with st.form("f1"):
        names = [st.text_input(f"Time {i+1}", f"Equipe {i+1}", key=f"i{i}") for i in range(num)]
        if st.form_submit_button("Gerar Torneio"):
            if not t_name: st.error("Nome obrigatório!")
            else:
                st.session_state.tournament_name = t_name
                st.session_state.teams = [{'id': i, 'name': n, 'wins': 0, 'losses': 0, 'goal_diff': 0, 'goals_for': 0, 'goals_against': 0, 'received_bye': False, 'status': 'Ativo'} for i, n in enumerate(names)]
                st.session_state.phase = 'swiss'
                
                # SORTEIO INICIAL SEM REPETIÇÃO
                p = st.session_state.teams.copy(); random.shuffle(p)
                b = None
                if len(p) % 2 != 0:
                    b = p.pop()
                    for t in st.session_state.teams:
                        if t['id'] == b['id']: 
                            t['received_bye'] = True
                            st.session_state.bye_history.append(t['id'])
                
                st.session_state.rounds = [{'matches': [{'home': p[i]['id'], 'away': p[i+1]['id']} for i in range(0, len(p), 2)], 'bye': b}]
                save_to_sheets(); st.rerun()

elif st.session_state.phase == 'swiss':
    st.title(f"⚽ {st.session_state.tournament_name} - Rodada {len(st.session_state.rounds)}")
    curr = st.session_state.rounds[-1]
    if curr.get('bye'): st.info(f"⭐ Folga: {curr['bye']['name']}")
    
    with st.form("fs"):
        res = []
        ready = True
        for i, m in enumerate(curr['matches']):
            t1 = next(t for t in st.session_state.teams if t['id'] == m['home'])
            t2 = next(t for t in st.session_state.teams if t['id'] == m['away'])
            c1, g1c, g2c, c2 = st.columns([2,1,1,2])
            g1 = g1c.number_input(t1['name'], 0, 100, key=f"s1{i}")
            g2 = g2c.number_input(t2['name'], 0, 100, key=f"s2{i}")
            p1, p2 = 0, 0
            if g1 == g2:
                pc1, pc2 = st.columns(2)
                p1 = pc1.number_input(f"Pên {t1['name']}", 0, 100, key=f"ps1{i}")
                p2 = pc2.number_input(f"Pên {t2['name']}", 0, 100, key=f"ps2{i}")
                if p1 == p2: ready = False
            res.append({'h': t1, 'a': t2, 'g1': g1, 'g2': g2, 'p1': p1, 'p2': p2})
            
        if st.form_submit_button("Confirmar Rodada"):
            if not ready: st.error("Decida nos pênaltis!")
            else:
                if curr.get('bye'):
                    for t in st.session_state.teams:
                        if t['id'] == curr['bye']['id']: t['wins'] = int(t['wins']) + 1
                for r in res:
                    r['h']['goals_for'] += r['g1']; r['h']['goals_against'] += r['g2']
                    r['a']['goals_for'] += r['g2']; r['a']['goals_against'] += r['g1']
                    r['h']['goal_diff'] = r['h']['goals_for'] - r['h']['goals_against']
                    r['a']['goal_diff'] = r['a']['goals_for'] - r['a']['goals_against']
                    if r['g1'] > r['g2'] or (r['g1'] == r['g2'] and r['p1'] > r['p2']):
                        r['h']['wins'] += 1; r['a']['losses'] += 1
                    else:
                        r['a']['wins'] += 1; r['h']['losses'] += 1
                
                for t in st.session_state.teams:
                    if int(t['wins']) >= 3: t['status'] = 'Classificado'
                    elif int(t['losses']) >= 3: t['status'] = 'Eliminado'
                
                # --- LÓGICA DA PRÓXIMA RODADA COM BYE BLINDADO ---
                ativos = [t for t in st.session_state.teams if t['status'] == 'Ativo']
                if not ativos: st.session_state.phase = 'end_swiss'
                else:
                    p = [t for t in get_rankings() if t['status'] == 'Ativo']
                    # Limpa o status visual de bye para a nova rodada (mas mantém o histórico bye_history)
                    for t in st.session_state.teams: t['received_bye'] = False
                    
                    b = None
                    if len(p) % 2 != 0:
                        # 1. Tenta pegar quem NUNCA teve bye
                        candidates = [t for t in p if t['id'] not in st.session_state.bye_history]
                        # 2. Se todo mundo já teve bye, reseta a lista e escolhe qualquer um
                        if not candidates: candidates = p
                        
                        b = random.choice(candidates)
                        p = [t for t in p if t['id'] != b['id']]
                        for t in st.session_state.teams:
                            if t['id'] == b['id']: 
                                t['received_bye'] = True
                                st.session_state.bye_history.append(t['id'])
                    
                    st.session_state.rounds.append({'matches': [{'home': p[i]['id'], 'away': p[i+1]['id']} for i in range(0, len(p), 2)], 'bye': b})
                
                save_to_sheets(); st.rerun()

# (Restante do código de playoffs e champion permanece o mesmo)
elif st.session_state.phase == 'end_swiss':
    st.title("🏁 Suíço Encerrado")
    if st.button("🚀 Iniciar Mata-Mata"):
        # Lógica de build_playoffs (vimos no bloco anterior)
        qualified = [t for t in get_rankings() if t['status'] == 'Classificado']
        n = len(qualified)
        if n >= 2:
            st.session_state.waiting_next = []
            for t in st.session_state.teams: t['received_bye'] = False
            # Regra Baga: Folgas automáticas para equilibrar chaves
            if n == 6: st.session_state.waiting_next = qualified[:2]; to_play = qualified[2:]
            elif n == 3: st.session_state.waiting_next = [qualified[0]]; to_play = qualified[1:]
            elif n == 5: st.session_state.waiting_next = qualified[:3]; to_play = qualified[3:]
            else: to_play = qualified
            
            w_ids = [w['id'] for w in st.session_state.waiting_next]
            for t in st.session_state.teams:
                if t['id'] in w_ids: t['received_bye'] = True

            matches = [{'home': to_play[i], 'away': to_play[-(i+1)], 'label': 'Eliminatória'} for i in range(len(to_play)//2)]
            st.session_state.playoffs = [{'label': "Mata-Mata", 'matches': matches}]
            st.session_state.phase = 'playoff'
            save_to_sheets(); st.rerun()

elif st.session_state.phase == 'playoff':
    st.title(f"🔥 Eliminatórias")
    # ... (A lógica de eliminatórias do código anterior já contempla os pênaltis)
    st.info("Fase de Mata-Mata Ativa. Use o Reset na sidebar para novo torneio.")
