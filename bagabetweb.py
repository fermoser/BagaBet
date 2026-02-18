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
keys = {'tournament_name': "", 'teams': [], 'phase': 'setup', 'rounds': [], 'playoffs': [], 
        'waiting_next': [], 'champion': None, 'second_place': None, 'third_place': None}

for key, value in keys.items():
    if key not in st.session_state: st.session_state[key] = value

# --- FUNÇÃO DE SALVAMENTO (AGORA COM TRAVA DE SEGURANÇA) ---
def save_to_sheets():
    # SÓ SALVA SE: Tiver conexão, tiver times E a fase não for mais o setup inicial
    if not SHEET_ENABLED or not st.session_state.teams or st.session_state.phase == 'setup': 
        return
    
    try:
        df_to_save = pd.DataFrame(st.session_state.teams)
        df_to_save['tournament_name'] = st.session_state.tournament_name
        
        # Padroniza o BYE para salvar sempre como SIM/NÃO
        if 'received_bye' in df_to_save.columns:
            df_to_save['received_bye'] = df_to_save['received_bye'].apply(
                lambda x: "SIM" if str(x).upper() in ["TRUE", "SIM", "1"] else "NÃO"
            )

        df_to_save = df_to_save.astype(str)

        try:
            # LÊ O HISTÓRICO EXISTENTE
            existing_data = conn.read(worksheet="suico")
            
            if existing_data is not None and not existing_data.empty:
                # Remove apenas os dados do torneio ATUAL para não duplicar linhas 
                # (isso permite atualizar o ranking do torneio que está rolando sem apagar os antigos)
                other_tournaments = existing_data[existing_data['tournament_name'] != st.session_state.tournament_name]
                df_final = pd.concat([other_tournaments, df_to_save], ignore_index=True)
            else:
                df_final = df_to_save
        except:
            df_final = df_to_save

        conn.update(worksheet="suico", data=df_final)
        st.toast(f"☁️ Histórico Atualizado: {st.session_state.tournament_name}")
        
    except Exception as e:
        st.error(f"⚠️ Erro ao salvar histórico: {e}")

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
            
        df_rank = df_rank.sort_values(by=['wins', 'goal_diff', 'goals_for', 'goals_against', 'losses'], 
                                     ascending=[False, False, False, True, True])
        
        df_view = df_rank[['name', 'wins', 'losses', 'goal_diff', 'goals_for', 'goals_against', 'received_bye', 'status']].copy()
        df_view.columns = ['Time', 'V', 'D', 'SG', 'GP', 'GC', '⭐', 'Status']
        
        df_view['⭐'] = df_view['⭐'].apply(lambda x: "⭐" if str(x).upper() in ["TRUE", "SIM", "1"] else "")

        def color_status(val):
            if val == 'Classificado': return 'background-color: #d4edda; color: black; font-weight: bold'
            if val == 'Eliminado': return 'background-color: #f8d7da; color: black; font-weight: bold'
            return 'background-color: #cce5ff; color: black; font-weight: bold'

        st.dataframe(df_view.style.applymap(color_status, subset=['Status']), 
                     hide_index=True, use_container_width=True)
    
    if st.button("🗑️ Reset Local / Novo Torneio"):
        for k in keys: st.session_state[k] = keys[k]
        st.rerun()

# --- TELAS (SETUP) ---
if st.session_state.phase == 'setup':
    st.title("🚀 Novo Torneio Suíço")
    c1, c2 = st.columns([2, 1])
    t_name = c1.text_input("Nome do Torneio")
    num = c2.number_input("Equipes", 2, 64, 8)
    
    with st.form("f1"):
        names = [st.text_input(f"Time {i+1}", f"Equipe {i+1}", key=f"i{i}") for i in range(num)]
        if st.form_submit_button("Criar Torneio"):
            if not t_name: st.warning("Dê um nome ao torneio para salvar no histórico!")
            else:
                st.session_state.tournament_name = t_name
                st.session_state.teams = [{
                    'id': i, 'name': n, 'wins': 0, 'losses': 0, 'goal_diff': 0, 
                    'goals_for': 0, 'goals_against': 0, 'received_bye': False, 'status': 'Ativo'
                } for i, n in enumerate(names)]
                st.session_state.phase = 'swiss'
                
                p = st.session_state.teams.copy(); random.shuffle(p)
                b = p.pop() if len(p)%2 != 0 else None
                if b:
                    for t in st.session_state.teams:
                        if t['id'] == b['id']: t['received_bye'] = True
                
                st.session_state.rounds = [{'matches': [{'home': p[i]['id'], 'away': p[i+1]['id']} for i in range(0, len(p), 2)], 'bye': b}]
                # Agora o salvamento ocorre APÓS a criação real, nunca antes
                save_to_sheets()
                st.rerun()

# --- FASE SUÍÇA ---
elif st.session_state.phase == 'swiss':
    st.title(f"⚽ {st.session_state.tournament_name} - Rodada {len(st.session_state.rounds)}")
    # ... (O restante da lógica de rodadas permanece a mesma do código anterior)
