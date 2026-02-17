import streamlit as st
import pandas as pd
import random
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="BAGA GESTOR - TORNEIO COMPLETO", layout="wide")
conn = st.connection("gsheets", type=GSheetsConnection)

# --- FUNÇÕES DE PERSISTÊNCIA ---

def sync_to_sheets():
    """Salva os times na aba 'Suico', tratando listas para texto"""
    if not st.session_state.teams:
        # Se vazio, cria cabeçalho padrão
        cols = ['id', 'name', 'wins', 'losses', 'goals_for', 'goal_diff', 'received_bye', 'history', 'status']
        df_save = pd.DataFrame(columns=cols)
    else:
        df_save = pd.DataFrame(st.session_state.teams)
        # Converte lista de IDs em string para o Sheets aceitar
        df_save['history'] = df_save['history'].apply(lambda x: str(x))
    
    conn.update(worksheet="Suico", data=df_save)

# --- INICIALIZAÇÃO DO ESTADO ---

if 'teams' not in st.session_state:
    try:
        df_load = conn.read(worksheet="Suico", ttl=0).dropna(how='all')
        if not df_load.empty:
            # Converte string de volta para lista [1, 2, 3]
            df_load['history'] = df_load['history'].apply(lambda x: eval(x) if isinstance(x, str) else [])
            st.session_state.teams = df_load.to_dict('records')
        else:
            st.session_state.teams = []
    except:
        st.session_state.teams = []

# Estados de controle da sessão
states = {
    'rounds': [], 'phase': 'registration', 'playoff_schedule': [], 
    'champion': None, 'swiss_asking_penalties': False, 'playoff_asking_penalties': False
}
for key, val in states.items():
    if key not in st.session_state: st.session_state[key] = val

# --- LÓGICA DE RANKING E ESTATÍSTICAS ---

def get_sorted_rankings(teams, for_pairing=False):
    if for_pairing:
        teams = teams.copy()
        random.shuffle(teams)
    # Ranking: Vitórias > Menos Derrotas > Sem Bye > Saldo > GP
    return sorted(teams, key=lambda x: (
        x['wins'], -x['losses'], not x['received_bye'], x['goal_diff'], x['goals_for']
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

# --- MOTORES DO TORNEIO ---

def generate_swiss_round():
    st.session_state.swiss_asking_penalties = False 
    active = [t for t in st.session_state.teams if t['status'] == 'Ativo']
    if not active: return

    bye_team = None
    if len(active) % 2 != 0:
        worst = sorted(active, key=lambda x: (x['wins'], not x['received_bye'], x['goal_diff']))
        bye_team = next((t for t in worst if not t['received_bye']), worst[0])
        active.remove(bye_team)

    ranked = get_sorted_rankings(active, for_pairing=True)
    matches = []
    while len(ranked) >= 2:
        home = ranked.pop(0)
        # Busca oponente que ainda não enfrentou
        idx_op = next((i for i, c in enumerate(ranked) if c['id'] not in home['history']), 0)
        opp = ranked.pop(idx_op)
        matches.append({'home': home['id'], 'away': opp['id']})
        home['history'].append(opp['id'])
        opp['history'].append(home['id'])

    st.session_state.rounds.append({'matches': matches, 'bye': bye_team})
    sync_to_sheets()

def init_playoffs():
    qualified = [t for t in st.session_state.teams if t['status'] == 'Classificado']
    seeds = get_sorted_rankings(qualified)
    n = len(seeds)
    m, w, name = [], [], ""

    if n == 3:
        name, w, m = "Semifinal Única", [seeds[0]], [{'id':'S1','home':seeds[1],'away':seeds[2],'label':'Semi'}]
    elif n == 4:
        name, m = "Semifinais", [{'id':'S1','home':seeds[0],'away':seeds[3],'label':'Semi 1'},{'id':'S2', 'home':seeds[1],'away':seeds[2],'label':'Semi 2'}]
    elif n >= 5: # Lógica simplificada para 5-8: Quartas ou Wildcards
        name = "Quartas de Final"
        num_matches = 4 if n >= 8 else (n // 2)
        m = [{'id': f'Q{i}', 'home': seeds[i], 'away': seeds[-(i+1)], 'label': f'Jogo {i+1}'} for i in range(num_matches)]
        w = seeds[num_matches : n - num_matches]

    st.session_state.playoff_schedule = [{'name': name, 'matches': m, 'waiting': w, 'completed': False}]
    st.session_state.phase = 'playoff_gameplay'
    sync_to_sheets()

def advance_playoff(winners, waiting):
    st.session_state.playoff_asking_penalties = False
    pool = get_sorted_rankings(waiting + winners)
    if len(pool) == 1:
        st.session_state.champion = pool[0]
        st.session_state.phase = 'champion'
    elif len(pool) == 2:
        st.session_state.playoff_schedule.append({'name': 'Grande Final', 'matches': [{'id':'F','home':pool[0],'away':pool[1],'label':'Final'}], 'waiting': [], 'completed': False})
    else:
        # Meio de caminho (ex: de Quartas para Semis)
        st.session_state.playoff_schedule.append({'name': 'Semifinais', 'matches': [{'id':'S1','home':pool[0],'away':pool[-1],'label':'Semi 1'},{'id':'S2','home':pool[1],'away':pool[-2],'label':'Semi 2'}], 'waiting': [], 'completed': False})

# --- INTERFACE ---

with st.sidebar:
    st.header("📊 Ranking")
    if st.session_state.teams:
        st.table(pd.DataFrame(get_sorted_rankings(st.session_state.teams))[['status','name','wins','losses','goal_diff']])
    if st.button("🗑️ RESETAR TORNEIO"):
        st.session_state.teams = []
        sync_to_sheets()
        st.rerun()

# --- TELAS ---

if st.session_state.phase == 'registration':
    st.title("🏆 Inscrição de Times")
    with st.form("cad"):
        name = st.text_input("Nome do Time")
        if st.form_submit_button("Adicionar"):
            if name:
                new_id = max([t['id'] for t in st.session_state.teams], default=0) + 1
                st.session_state.teams.append({'id':new_id, 'name':name, 'wins':0, 'losses':0, 'goals_for':0, 'goal_diff':0, 'received_bye':False, 'history':[], 'status':'Ativo'})
                sync_to_sheets()
                st.rerun()
    if len(st.session_state.teams) >= 6:
        if st.button("🚀 Iniciar Torneio"):
            st.session_state.phase = 'swiss'
            generate_swiss_round()
            st.rerun()

elif st.session_state.phase == 'swiss':
    st.title(f"⚔️ Rodada Suíça {len(st.session_state.rounds)}")
    curr = st.session_state.rounds[-1]
    if curr['bye']: st.warning(f"Folga: {curr['bye']['name']}")

    with st.form("swiss_res"):
        res = []
        for i, m in enumerate(curr['matches']):
            t1 = next(t for t in st.session_state.teams if t['id'] == m['home'])
            t2 = next(t for t in st.session_state.teams if t['id'] == m['away'])
            c1, c2, c3, c4 = st.columns([2,1,1,2])
            with c1: st.write(t1['name'])
            with c2: g1 = st.number_input("G", 0, key=f"g1_{i}", value=None)
            with c3: g2 = st.number_input("G", 0, key=f"g2_{i}", value=None)
            with c4: st.write(t2['name'])
            p1, p2 = 0, 0
            if st.session_state.swiss_asking_penalties and g1 == g2 and g1 is not None:
                cp1, cp2 = st.columns(2); p1 = cp1.number_input("Pên", 0, key=f"p1_{i}"); p2 = cp2.number_input("Pên", 0, key=f"p2_{i}")
            res.append({'h':t1['id'], 'a':t2['id'], 'g1':g1, 'g2':g2, 'p1':p1, 'p2':p2})
        
        if st.form_submit_button("Confirmar Rodada"):
            if any(r['g1'] is None for r in res): st.error("Placares incompletos")
            elif not st.session_state.swiss_asking_penalties and any(r['g1']==r['g2'] for r in res):
                st.session_state.swiss_asking_penalties = True; st.rerun()
            else:
                if curr['bye']: update_team_stats(curr['bye']['id'], 1, 0, True, True)
                for r in res:
                    vh = r['g1'] > r['g2'] if r['g1'] != r['g2'] else r['p1'] > r['p2']
                    update_team_stats(r['h'], r['g1'], r['g2'], vh); update_team_stats(r['a'], r['g2'], r['g1'], not vh)
                sync_to_sheets()
                active = [t for t in st.session_state.teams if t['status'] == 'Ativo']
                if len(active) <= 1: init_playoffs()
                else: generate_swiss_round()
                st.rerun()

elif st.session_state.phase == 'playoff_gameplay':
    curr_r = st.session_state.playoff_schedule[-1]
    st.title(f"🔥 {curr_r['name']}")
    with st.form("playoff_res"):
        res = []
        for i, m in enumerate(curr_r['matches']):
            st.subheader(m['label'])
            c1, c2, c3, c4 = st.columns([2,1,1,2])
            with c1: st.write(m['home']['name'])
            with c2: g1 = st.number_input("G", 0, key=f"pg1_{i}", value=None)
            with c3: g2 = st.number_input("G", 0, key=f"pg2_{i}", value=None)
            with c4: st.write(m['away']['name'])
            p1, p2 = 0, 0
            if st.session_state.playoff_asking_penalties and g1 == g2 and g1 is not None:
                cp1, cp2 = st.columns(2); p1 = cp1.number_input("Pên", 0, key=f"pp1_{i}"); p2 = cp2.number_input("Pên", 0, key=f"pp2_{i}")
            res.append({'m':m, 'g1':g1, 'g2':g2, 'p1':p1, 'p2':p2})
        
        if st.form_submit_button("Avançar"):
            if any(r['g1'] is None for r in res): st.error("Placares incompletos")
            elif not st.session_state.playoff_asking_penalties and any(r['g1']==r['g2'] for r in res):
                st.session_state.playoff_asking_penalties = True; st.rerun()
            else:
                winners = []
                for r in res:
                    vh = r['g1'] > r['g2'] if r['g1'] != r['g2'] else r['p1'] > r['p2']
                    win = r['m']['home'] if vh else r['m']['away']
                    winners.append(win)
                curr_r['completed'] = True
                advance_playoff(winners, curr_r['waiting'])
                st.rerun()

elif st.session_state.phase == 'champion':
    st.balloons()
    st.header(f"🏆 CAMPEÃO: {st.session_state.champion['name']}!")
    if st.button("Novo Torneio"):
        st.session_state.clear()
        st.rerun()
