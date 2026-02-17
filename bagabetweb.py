import streamlit as st
import pandas as pd
import random
from streamlit_gsheets_connection import GSheetsConnection

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Bagabet - Gestor Suíço", layout="wide")

# --- CONEXÃO COM GOOGLE SHEETS ---
conn = st.connection("gsheets", type=GSheetsConnection)

# --- FUNÇÕES DE BANCO DE DATA (aba "suico") ---

def load_data():
    """Lê os dados diretamente da aba 'suico'"""
    try:
        df = conn.read(worksheet="suico", ttl=0)
        if df.empty:
            return []
        # Converte para lista de dicionários para facilitar a lógica do Python
        data = df.to_dict(orient='records')
        # Garante que campos numéricos não venham como strings
        for item in data:
            item['wins'] = int(item.get('wins', 0))
            item['losses'] = int(item.get('losses', 0))
            item['goals_for'] = int(item.get('goals_for', 0))
            item['goal_diff'] = int(item.get('goal_diff', 0))
            item['history'] = [] # Cache de confrontos da sessão
        return data
    except Exception as e:
        st.error(f"Erro ao ler planilha: {e}")
        return []

def save_data():
    """Salva o estado atual na aba 'suico'"""
    if st.session_state.teams:
        try:
            df_to_save = pd.DataFrame(st.session_state.teams)
            # Removemos colunas que o Sheets não entende (listas)
            if 'history' in df_to_save.columns:
                df_to_save = df_to_save.drop(columns=['history'])
            
            conn.update(worksheet="suico", data=df_to_save)
            st.toast("💾 Sincronizado com a base 'suico'!", icon="✅")
        except Exception as e:
            st.error(f"Erro ao salvar: {e}")

# --- INICIALIZAÇÃO DO ESTADO (SESSION STATE) ---
if 'teams' not in st.session_state:
    st.session_state.teams = load_data()
if 'rounds' not in st.session_state:
    st.session_state.rounds = []
if 'phase' not in st.session_state:
    # Se já tem times, assume que o torneio está em curso
    st.session_state.phase = 'registration' if not st.session_state.teams else 'swiss'
if 'playoff_schedule' not in st.session_state:
    st.session_state.playoff_schedule = []

# --- LÓGICA DO TORNEIO ---

def get_rankings():
    """Ordenação oficial: Vitórias > Saldo > Gols Pró"""
    return sorted(st.session_state.teams, 
                  key=lambda x: (x['wins'], x['goal_diff'], x['goals_for']), 
                  reverse=True)

def update_team(t_id, g_scored, g_conceded, won):
    for t in st.session_state.teams:
        if t['id'] == t_id:
            t['goals_for'] += g_scored
            t['goal_diff'] += (g_scored - g_conceded)
            if won: t['wins'] += 1
            else: t['losses'] += 1
            
            # Regra de Ouro do Suíço: 3-X
            if t['wins'] >= 3: t['status'] = 'Classificado'
            elif t['losses'] >= 3: t['status'] = 'Eliminado'
            break

def generate_swiss():
    active = [t for t in st.session_state.teams if t['status'] == 'Ativo']
    if not active: return
    
    random.shuffle(active)
    # Lógica de Bye (Folga)
    bye_team = None
    if len(active) % 2 != 0:
        eligible_for_bye = sorted([t for t in active if not t.get('received_bye')], 
                                  key=lambda x: (x['wins'], x['goal_diff']))
        bye_team = eligible_for_bye[0] if eligible_for_bye else active[-1]
        active.remove(bye_team)
    
    # Pareamento por Ranking (1º vs 2º, 3º vs 4º...)
    pool = sorted(active, key=lambda x: (x['wins'], x['goal_diff']), reverse=True)
    matches = []
    while len(pool) >= 2:
        h = pool.pop(0)
        a = pool.pop(0)
        matches.append({'home': h['id'], 'away': a['id']})
    
    st.session_state.rounds.append({'matches': matches, 'bye': bye_team})

def start_playoffs():
    qualified = [t for t in st.session_state.teams if t['status'] == 'Classificado']
    seeds = sorted(qualified, key=lambda x: (x['wins'], x['goal_diff']), reverse=True)
    
    # Chaveamento Clássico (1º vs Último)
    num = len(seeds)
    m = []
    if num >= 8:
        s = seeds[:8]
        m = [{'home': s[0], 'away': s[7], 'label': 'QF 1'}, {'home': s[1], 'away': s[6], 'label': 'QF 2'},
             {'home': s[2], 'away': s[5], 'label': 'QF 3'}, {'home': s[3], 'away': s[4], 'label': 'QF 4'}]
    elif num >= 4:
        s = seeds[:4]
        m = [{'home': s[0], 'away': s[3], 'label': 'Semi 1'}, {'home': s[1], 'away': s[2], 'label': 'Semi 2'}]
    
    st.session_state.playoff_schedule.append({'name': 'Mata-Mata', 'matches': m})
    st.session_state.phase = 'playoffs'

# --- INTERFACE ---

st.sidebar.title("🏆 Bagabet System")
if st.sidebar.button("🔄 Resetar Tudo"):
    st.session_state.teams = []
    st.session_state.phase = 'registration'
    save_data()
    st.rerun()

# Exibe Ranking na lateral
if st.session_state.teams:
    st.sidebar.markdown("---")
    st.sidebar.subheader("📊 Classificação 'suico'")
    df_rank = pd.DataFrame(get_rankings())
    st.sidebar.dataframe(df_rank[['name', 'wins', 'losses', 'status']], hide_index=True)

# --- TELAS ---

if st.session_state.phase == 'registration':
    st.title("Inscrição de Times")
    with st.form("add_team"):
        name = st.text_input("Nome da Equipe")
        if st.form_submit_button("Cadastrar"):
            st.session_state.teams.append({
                'id': len(st.session_state.teams)+1, 'name': name, 'wins': 0, 'losses': 0,
                'goals_for': 0, 'goal_diff': 0, 'status': 'Ativo', 'received_bye': False
            })
            save_data()
            st.rerun()
    
    if len(st.session_state.teams) >= 6:
        if st.button("🚀 Começar Torneio"):
            st.session_state.phase = 'swiss'
            generate_swiss()
            save_data()
            st.rerun()

elif st.session_state.phase == 'swiss':
    st.title(f"⚔️ Rodada Suíça {len(st.session_state.rounds)}")
    curr = st.session_state.rounds[-1]
    
    if curr['bye']:
        st.warning(f"Folga: **{curr['bye']['name']}** (+1 Vitória)")

    with st.form("round_results"):
        res_list = []
        for i, m in enumerate(curr['matches']):
            t1 = next(t for t in st.session_state.teams if t['id'] == m['home'])
            t2 = next(t for t in st.session_state.teams if t['id'] == m['away'])
            c1, c2, c3, c4 = st.columns([2,1,1,2])
            with c1: st.write(t1['name'])
            with c2: g1 = st.number_input("G", 0, key=f"g1_{i}")
            with c3: g2 = st.number_input("G", 0, key=f"g2_{i}")
            with c4: st.write(t2['name'])
            res_list.append((t1['id'], t2['id'], g1, g2))
        
        if st.form_submit_button("Finalizar Rodada"):
            if curr['bye']: update_team(curr['bye']['id'], 1, 0, True)
            for r in res_list:
                update_team(r[0], r[2], r[3], r[2] > r[3])
                update_team(r[1], r[3], r[2], r[3] > r[2])
            
            save_data()
            
            # Verifica se encerra fase suíça
            ativos = [t for t in st.session_state.teams if t['status'] == 'Ativo']
            if len(ativos) <= 1:
                start_playoffs()
            else:
                generate_swiss()
            st.rerun()

elif st.session_state.phase == 'playoffs':
    st.title("🔥 FASE FINAL (Mata-Mata)")
    playoff = st.session_state.playoff_schedule[-1]
    st.subheader(playoff['name'])
    st.info("Critério aplicado: 1º vs Último.")
    # (Interface de resultados do Mata-Mata seguindo a mesma lógica...)
