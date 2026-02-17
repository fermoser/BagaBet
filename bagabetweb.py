import streamlit as st
import pandas as pd
import random
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="BAGA GESTOR - SUIÇO", layout="wide")
conn = st.connection("gsheets", type=GSheetsConnection)

# --- FUNÇÃO DE SINCRONIZAÇÃO E CRIAÇÃO DE COLUNAS ---
def sync_to_sheets():
    """Força a criação das colunas necessárias e salva os dados"""
    df_save = pd.DataFrame(st.session_state.teams)
    
    # Se não houver times, cria um DataFrame vazio com as colunas certas para o DB
    if df_save.empty:
        cols = ['id', 'name', 'wins', 'losses', 'goals_for', 'goal_diff', 'received_bye', 'history', 'status']
        df_save = pd.DataFrame(columns=cols)
    else:
        # Converte lista de histórico em string para o Sheets não dar erro
        df_save['history'] = df_save['history'].apply(lambda x: str(x))
        
    conn.update(worksheet="Suico", data=df_save)

# --- INICIALIZAÇÃO DO STATE ---
if 'teams' not in st.session_state:
    # Tenta carregar dados existentes
    try:
        df_load = conn.read(worksheet="Suico", ttl=0).dropna(how='all')
        if not df_load.empty:
            # Reconverte string de volta para lista no histórico
            df_load['history'] = df_load['history'].apply(lambda x: eval(x) if isinstance(x, str) else [])
            st.session_state.teams = df_load.to_dict('records')
        else:
            st.session_state.teams = []
    except:
        st.session_state.teams = []

# Os demais estados são temporários de sessão (zeram ao fechar o navegador)
if 'rounds' not in st.session_state: st.session_state.rounds = [] 
if 'phase' not in st.session_state: st.session_state.phase = 'registration' 
if 'playoff_schedule' not in st.session_state: st.session_state.playoff_schedule = [] 
if 'champion' not in st.session_state: st.session_state.champion = None
if 'swiss_asking_penalties' not in st.session_state: st.session_state.swiss_asking_penalties = False 
if 'playoff_asking_penalties' not in st.session_state: st.session_state.playoff_asking_penalties = False 

# --- LÓGICA CORE (ORDENAÇÃO FIEL AO SEU MODELO) ---

def get_sorted_rankings(teams, for_pairing=False):
    if for_pairing:
        teams = teams.copy()
        random.shuffle(teams)
    # Vitórias > Menos Derrotas > Não teve Bye > Saldo > GP
    return sorted(teams, key=lambda x: (
        x['wins'], 
        -x['losses'], 
        not x['received_bye'], 
        x['goal_diff'], 
        x['goals_for']
    ), reverse=True)

def update_team_stats(team_id, goals_scored, goals_conceded, is_winner, is_bye=False):
    for team in st.session_state.teams:
        if team['id'] == team_id:
            team['goals_for'] += goals_scored
            team['goal_diff'] += (goals_scored - goals_conceded)
            if is_winner: team['wins'] += 1
            else: team['losses'] += 1
            if is_bye: team['received_bye'] = True
            
            if st.session_state.phase == 'swiss':
                if team['wins'] >= 3: team['status'] = 'Classificado'
                elif team['losses'] >= 3: team['status'] = 'Eliminado'
            break

# --- GERAÇÃO DE RODADAS ---

def generate_swiss_round():
    st.session_state.swiss_asking_penalties = False 
    active_teams = [t for t in st.session_state.teams if t['status'] == 'Ativo']
    
    if not active_teams: return

    # Lógica de Bye
    bye_team = None
    if len(active_teams) % 2 != 0:
        worst_sorted = sorted(active_teams, key=lambda x: (x['wins'], not x['received_bye'], x['goal_diff']))
        bye_team = next((t for t in worst_sorted if not t['received_bye']), worst_sorted[0])
        active_teams.remove(bye_team)

    # Pareamento Inédito
    ranked_pool = get_sorted_rankings(active_teams, for_pairing=True)
    matches = []
    while len(ranked_pool) >= 2:
        home = ranked_pool.pop(0)
        # Tenta achar alguém que ele ainda não jogou
        opponent = next((c for c in ranked_pool if c['id'] not in home['history']), ranked_pool[0])
        ranked_pool.remove(opponent)
        
        matches.append({'home': home['id'], 'away': opponent['id']})
        home['history'].append(opponent['id'])
        opponent['history'].append(home['id'])

    st.session_state.rounds.append({'matches': matches, 'bye': bye_team})
    sync_to_sheets()

# --- INTERFACE ---

st.sidebar.title("📊 Classificação")
if st.session_state.teams:
    sorted_view = get_sorted_rankings(st.session_state.teams)
    df_view = pd.DataFrame(sorted_view)[['status', 'name', 'wins', 'losses', 'goal_diff']]
    st.sidebar.table(df_view)

if st.sidebar.button("🗑️ RESET TOTAL (PLANILHA)"):
    st.session_state.teams = []
    sync_to_sheets()
    st.rerun()

# --- FLUXO DE TELAS ---

if st.session_state.phase == 'registration':
    st.title("🏆 Inscrição - Sistema Suíço")
    with st.form("add_team"):
        new_n = st.text_input("Nome do Time")
        if st.form_submit_button("Adicionar"):
            if new_n:
                new_id = max([t['id'] for t in st.session_state.teams], default=0) + 1
                st.session_state.teams.append({
                    'id': new_id, 'name': new_n, 'wins': 0, 'losses': 0, 
                    'goals_for': 0, 'goal_diff': 0, 'received_bye': False, 
                    'history': [], 'status': 'Ativo'
                })
                sync_to_sheets()
                st.rerun()

    if len(st.session_state.teams) >= 6:
        if st.button("🚀 Iniciar Torneio"):
            st.session_state.phase = 'swiss'
            generate_swiss_round()
            st.rerun()

elif st.session_state.phase == 'swiss':
    round_num = len(st.session_state.rounds)
    st.title(f"⚔️ Rodada {round_num}")
    curr = st.session_state.rounds[-1]
    
    if curr['bye']:
        st.warning(f"Folga da Rodada: {curr['bye']['name']} (+1 Vitória)")

    with st.form(f"results_{round_num}"):
        match_results = []
        for i, m in enumerate(curr['matches']):
            t1 = next(t for t in st.session_state.teams if t['id'] == m['home'])
            t2 = next(t for t in st.session_state.teams if t['id'] == m['away'])
            
            col1, col2, col3, col4 = st.columns([2,1,1,2])
            with col1: st.markdown(f"**{t1['name']}**")
            with col2: g1 = st.number_input("Gols", 0, 50, key=f"g1_{i}", value=None)
            with col3: g2 = st.number_input("Gols", 0, 50, key=f"g2_{i}", value=None)
            with col4: st.markdown(f"**{t2['name']}**")
            
            p1, p2 = 0, 0
            if st.session_state.swiss_asking_penalties and g1 == g2 and g1 is not None:
                c_pen1, c_pen2 = st.columns(2)
                with c_pen1: p1 = st.number_input(f"Pênaltis {t1['name']}", 0, 20, key=f"p1_{i}")
                with c_pen2: p2 = st.number_input(f"Pênaltis {t2['name']}", 0, 20, key=f"p2_{i}")
            
            match_results.append({'h': t1['id'], 'a': t2['id'], 'g1': g1, 'g2': g2, 'p1': p1, 'p2': p2})

        if st.form_submit_button("Confirmar Resultados"):
            if any(r['g1'] is None or r['g2'] is None for r in match_results):
                st.error("Preencha todos os placares.")
            elif not st.session_state.swiss_asking_penalties and any(r['g1'] == r['g2'] for r in match_results):
                st.session_state.swiss_asking_penalties = True
                st.rerun()
            else:
                # Processa Bye
                if curr['bye']: update_team_stats(curr['bye']['id'], 1, 0, True, True)
                # Processa Jogos
                for r in match_results:
                    vence_h = r['g1'] > r['g2'] if r['g1'] != r['g2'] else r['p1'] > r['p2']
                    update_team_stats(r['h'], r['g1'], r['g2'], vence_h)
                    update_team_stats(r['a'], r['g2'], r['g1'], not vence_h)
                
                sync_to_sheets()
                active = [t for t in st.session_state.teams if t['status'] == 'Ativo']
                if len(active) <= 1:
                    st.success("Fase Suíça encerrada! Próximo passo: Mata-Mata.")
                    # Aqui você pode chamar a função init_playoffs() do seu modelo
                else:
                    generate_swiss_round()
                st.rerun()
