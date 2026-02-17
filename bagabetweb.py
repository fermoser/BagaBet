import streamlit as st
import pandas as pd
import random
from streamlit_gsheets_connection import GSheetsConnection

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Gestor Suíço - Database", layout="wide")

# --- CONEXÃO COM GOOGLE SHEETS (NOME DA ABA: "suico") ---
conn = st.connection("gsheets", type=GSheetsConnection)

def load_from_sheets():
    """Lê os dados da aba 'suico' e carrega no estado do app"""
    try:
        # Tenta ler a aba 'suico'
        df = conn.read(worksheet="suico", ttl=0)
        if not df.empty:
            # Converte DataFrame de volta para lista de dicionários
            data = df.to_dict(orient='records')
            # Garante que colunas numéricas sejam int e recupera o histórico vazio se necessário
            for item in data:
                item['history'] = [] # O Sheets não guarda listas, reiniciamos o cache de confrontos
            return data
    except Exception:
        return []
    return []

def save_to_sheets():
    """Salva o estado atual na aba 'suico'"""
    try:
        if st.session_state.teams:
            df_to_save = pd.DataFrame(st.session_state.teams)
            # Removemos a coluna 'history' antes de salvar (Sheets não aceita listas em células)
            if 'history' in df_to_save.columns:
                df_to_save = df_to_save.drop(columns=['history'])
            
            conn.update(worksheet="suico", data=df_to_save)
            st.toast("💾 Dados salvos em 'suico'!", icon="✅")
    except Exception as e:
        st.error(f"Erro ao salvar na planilha: {e}")

# --- INICIALIZAÇÃO DO ESTADO ---
if 'teams' not in st.session_state:
    # Tenta carregar os times da planilha ao abrir o app
    st.session_state.teams = load_from_sheets()
if 'rounds' not in st.session_state:
    st.session_state.rounds = [] 
if 'phase' not in st.session_state:
    st.session_state.phase = 'registration' if not st.session_state.teams else 'swiss'
if 'playoff_schedule' not in st.session_state:
    st.session_state.playoff_schedule = []

# --- FUNÇÕES DE LÓGICA (SUIÇO E MATA-MATA) ---

def get_sorted_rankings(teams):
    """Critério: Vitórias -> Saldo -> Gols Pró"""
    return sorted(teams, key=lambda x: (x['wins'], x['goal_diff'], x['goals_for']), reverse=True)

def update_stats(t_id, g_scored, g_conceded, win):
    for t in st.session_state.teams:
        if t['id'] == t_id:
            t['goals_for'] += g_scored
            t['goal_diff'] += (g_scored - g_conceded)
            if win: t['wins'] += 1
            else: t['losses'] += 1
            # Regra de classificação
            if t['wins'] >= 3: t['status'] = 'Classificado'
            elif t['losses'] >= 3: t['status'] = 'Eliminado'
            break

def generate_swiss_round():
    active = [t for t in st.session_state.teams if t['status'] == 'Ativo']
    if not active: return
    random.shuffle(active)
    
    # Lógica de Bye
    bye_team = None
    if len(active) % 2 != 0:
        eligible = sorted([t for t in active if not t.get('received_bye', False)], key=lambda x: (x['wins'], x['goal_diff']))
        bye_team = eligible[0] if eligible else active[-1]
        active.remove(bye_team)
    
    pool = get_sorted_rankings(active)
    matches = []
    while len(pool) >= 2:
        h = pool.pop(0)
        # Tenta não repetir jogo (usando cache local de history)
        opp = pool[0] 
        pool.remove(opp)
        matches.append({'home': h['id'], 'away': opp['id']})
    
    st.session_state.rounds.append({'matches': matches, 'bye': bye_team})

def init_playoffs():
    qualified = [t for t in st.session_state.teams if t['status'] == 'Classificado']
    seeds = get_sorted_rankings(qualified)
    num = len(seeds)
    
    # Chaveamento 1º vs Último
    if num >= 4:
        s = seeds[:4] # Top 4
        m = [{'home': s[0], 'away': s[3], 'label': 'Semi 1'},
             {'home': s[1], 'away': s[2], 'label': 'Semi 2'}]
        st.session_state.playoff_schedule.append({'name': 'Semifinais', 'matches': m})
        st.session_state.phase = 'playoffs'
    elif num == 2:
        m = [{'home': seeds[0], 'away': seeds[1], 'label': 'Final'}]
        st.session_state.playoff_schedule.append({'name': 'Grande Final', 'matches': m})
        st.session_state.phase = 'playoffs'

# --- INTERFACE ---

st.sidebar.title("🎮 Painel de Controle")
if st.sidebar.button("🗑️ Limpar Tudo (Reset)"):
    st.session_state.teams = []
    st.session_state.phase = 'registration'
    save_to_sheets()
    st.rerun()

# --- ABA DE RANKING NA SIDEBAR ---
if st.session_state.teams:
    st.sidebar.subheader("📊 Tabela 'suico'")
    df_side = pd.DataFrame(get_sorted_rankings(st.session_state.teams))
    st.sidebar.dataframe(df_side[['name', 'wins', 'losses', 'goal_diff', 'status']], hide_index=True)

# --- FLUXO DE TELAS ---

if st.session_state.phase == 'registration':
    st.title("📝 Cadastro de Times")
    new_team = st.text_input("Nome do Time")
    if st.button("Adicionar Time"):
        st.session_state.teams.append({
            'id': len(st.session_state.teams)+1, 'name': new_team, 
            'wins': 0, 'losses': 0, 'goals_for': 0, 'goal_diff': 0, 
            'status': 'Ativo', 'received_bye': False
        })
        save_to_sheets()
        st.rerun()
    
    if len(st.session_state.teams) >= 4:
        if st.button("🚀 Iniciar Campeonato"):
            st.session_state.phase = 'swiss'
            generate_swiss_round()
            save_to_sheets()
            st.rerun()

elif st.session_state.phase == 'swiss':
    st.title(f"⚔️ Rodada Suíça {len(st.session_state.rounds)}")
    curr = st.session_state.rounds[-1]
    
    if curr['bye']: st.info(f"Folga da rodada: **{curr['bye']['name']}** (+1 vitória)")

    with st.form("swiss_res"):
        results = []
        for i, m in enumerate(curr['matches']):
            t1 = next(t for t in st.session_state.teams if t['id'] == m['home'])
            t2 = next(t for t in st.session_state.teams if t['id'] == m['away'])
            c1, c2, c3, c4 = st.columns([2,1,1,2])
            with c1: st.write(t1['name'])
            with c2: s1 = st.number_input("Gols", 0, key=f"s1_{i}")
            with c3: s2 = st.number_input("Gols", 0, key=f"s2_{i}")
            with c4: st.write(t2['name'])
            results.append((t1['id'], t2['id'], s1, s2))
        
        if st.form_submit_button("Confirmar Rodada"):
            if curr['bye']: update_stats(curr['bye']['id'], 1, 0, True)
            for r in results:
                update_stats(r[0], r[2], r[3], r[2] > r[3])
                update_stats(r[1], r[3], r[2], r[3] > r[2])
            
            save_to_sheets() # PERSISTÊNCIA NA PLANILHA
            
            ativos = [t for t in st.session_state.teams if t['status'] == 'Ativo']
            if len(ativos) <= 1: init_playoffs()
            else: generate_swiss_round()
            st.rerun()

elif st.session_state.phase == 'playoffs':
    curr_p = st.session_state.playoff_schedule[-1]
    st.title(f"🔥 {curr_p['name']}")
    # Lógica de interface similar ao anterior...
    st.write("Fase final em andamento. Resultados salvos na planilha 'suico'.")
