import streamlit as st
import pandas as pd
import random
from streamlit_gsheets import GSheetsConnection

# --- 1. CONFIGURAÇÃO E CONEXÃO ---
st.set_page_config(page_title="BAGA GESTOR - FINAL", layout="wide")
conn = st.connection("gsheets", type=GSheetsConnection)

# --- 2. INICIALIZAÇÃO DO STATE (FIX PARA O ERRO DE ATRIBUTO) ---
# Precisamos garantir que as variáveis existam antes de qualquer outra função rodar
if 'teams' not in st.session_state:
    try:
        df_load = conn.read(worksheet="Suico", ttl=0).dropna(how='all')
        if not df_load.empty:
            # Converte string '[1, 2]' de volta para lista real
            df_load['history'] = df_load['history'].apply(lambda x: eval(x) if isinstance(x, str) else [])
            st.session_state.teams = df_load.to_dict('records')
        else:
            st.session_state.teams = []
    except:
        st.session_state.teams = []

# Inicializa outros estados se não existirem
for key, val in {
    'rounds': [], 'phase': 'registration', 'playoff_schedule': [], 
    'champion': None, 'swiss_asking_penalties': False, 'playoff_asking_penalties': False
}.items():
    if key not in st.session_state:
        st.session_state[key] = val

# --- 3. FUNÇÕES DE APOIO ---

def sync_to_sheets():
    """Salva no Google Sheets garantindo as colunas"""
    if not st.session_state.get('teams'):
        cols = ['id', 'name', 'wins', 'losses', 'goals_for', 'goal_diff', 'received_bye', 'history', 'status']
        df_save = pd.DataFrame(columns=cols)
    else:
        df_save = pd.DataFrame(st.session_state.teams)
        df_save['history'] = df_save['history'].apply(lambda x: str(x))
    
    conn.update(worksheet="Suico", data=df_save)

def get_sorted_rankings(teams):
    """Critério: Vitórias > Menos Derrotas > Sem Bye > Saldo > GP"""
    return sorted(teams, key=lambda x: (
        x['wins'], 
        -x['losses'], 
        not x['received_bye'], 
        x['goal_diff'], 
        x['goals_for']
    ), reverse=True)

# --- 4. LÓGICA DE PAREAMENTO ---

def generate_swiss_round():
    st.session_state.swiss_asking_penalties = False 
    active = [t for t in st.session_state.teams if t['status'] == 'Ativo']
    if not active: return

    bye_team = None
    if len(active) % 2 != 0:
        # Pega o pior classificado que ainda não teve Bye
        worst_sorted = sorted(active, key=lambda x: (x['wins'], not x['received_bye'], x['goal_diff']))
        bye_team = next((t for t in worst_sorted if not t['received_bye']), worst_sorted[0])
        active.remove(bye_team)

    # Embaralha para evitar repetição de jogos em seeds iguais
    pool = active.copy()
    random.shuffle(pool)
    # Ordena para parear por performance (Suíço Real)
    ranked = get_sorted_rankings(pool)
    
    matches = []
    while len(ranked) >= 2:
        home = ranked.pop(0)
        # Tenta achar oponente inédito
        idx_opp = 0
        for i, potential in enumerate(ranked):
            if potential['id'] not in home['history']:
                idx_opp = i
                break
        opp = ranked.pop(idx_opp)
        matches.append({'home': home['id'], 'away': opp['id']})
        home['history'].append(opp['id'])
        opp['history'].append(home['id'])

    st.session_state.rounds.append({'matches': matches, 'bye': bye_team})
    sync_to_sheets()

def init_playoffs():
    """Chaveamento Clássico: 1vs8, 2vs7, 3vs6, 4vs5"""
    qualified = [t for t in st.session_state.teams if t['status'] == 'Classificado']
    seeds = get_sorted_rankings(qualified)
    n = len(seeds)
    
    matches = []
    waiting = []
    
    if n >= 8:
        top_8 = seeds[:8]
        name = "Quartas de Final"
        matches = [{'id':f'Q{i}','home':top_8[i],'away':top_8[7-i],'label':f'Jogo {i+1}'} for i in range(4)]
    elif n >= 4:
        top_4 = seeds[:4]
        name = "Semifinais"
        matches = [{'id':f'S{i}','home':top_4[i],'away':top_4[3-i],'label':f'Semi {i+1}'} for i in range(2)]
    elif n == 3:
        name = "Semifinal Única"
        waiting = [seeds[0]] # 1º espera na final
        matches = [{'id':'S1','home':seeds[1],'away':seeds[2],'label':'Semifinal'}]
    else:
        name = "Final Direta"
        matches = [{'id':'F','home':seeds[0],'away':seeds[1],'label':'Final'}]

    st.session_state.playoff_schedule = [{'name': name, 'matches': matches, 'waiting': waiting, 'completed': False}]
    st.session_state.phase = 'playoff_gameplay'
    sync_to_sheets()

# --- 5. INTERFACE (SIDEBAR) ---

with st.sidebar:
    st.title("⚙️ Painel")
    if st.session_state.teams:
        st.subheader("Classificação Atual")
        df_rank = pd.DataFrame(get_sorted_rankings(st.session_state.teams))
        # Traduzindo colunas para ficar bonito
        df_show = df_rank[['name', 'wins', 'losses', 'goal_diff', 'received_bye']].copy()
        df_show.columns = ['Time', 'V', 'D', 'Saldo', 'Teve Bye?']
        df_show['Teve Bye?'] = df_show['Teve Bye?'].map({True: '✅ Sim', False: '❌ Não'})
        st.table(df_show)
    
    if st.button("🗑️ RESETAR BANCO DE DADOS"):
        st.session_state.teams = []
        sync_to_sheets()
        st.rerun()

# --- 6. TELAS DO TORNEIO ---

if st.session_state.phase == 'registration':
    st.title("🏁 Cadastro de Times")
    with st.form("add"):
        t_name = st.text_input("Nome do Time")
        if st.form_submit_button("Cadastrar"):
            if t_name:
                new_id = len(st.session_state.teams) + 1
                st.session_state.teams.append({
                    'id': new_id, 'name': t_name, 'wins': 0, 'losses': 0, 
                    'goals_for': 0, 'goal_diff': 0, 'received_bye': False, 
                    'history': [], 'status': 'Ativo'
                })
                sync_to_sheets(); st.rerun()
    
    if len(st.session_state.teams) >= 2:
        if st.button("🚀 Iniciar Torneio"):
            st.session_state.phase = 'swiss'
            generate_swiss_round(); st.rerun()

elif st.session_state.phase == 'swiss':
    round_idx = len(st.session_state.rounds)
    st.title(f"⚽ Rodada {round_idx} (Suíço)")
    curr = st.session_state.rounds[-1]
    
    if curr['bye']:
        st.info(f"✨ **{curr['bye']['name']}** está de folga (Bye) nesta rodada.")

    with st.form(f"f_round_{round_idx}"):
        results = []
        for i, m in enumerate(curr['matches']):
            t1 = next(t for t in st.session_state.teams if t['id'] == m['home'])
            t2 = next(t for t in st.session_state.teams if t['id'] == m['away'])
            c1, c2, c3, c4 = st.columns([2,1,1,2])
            with c1: st.write(f"**{t1['name']}**")
            with c2: g1 = st.number_input("Gols", 0, 99, key=f"g1_{i}", value=None)
            with c3: g2 = st.number_input("Gols", 0, 99, key=f"g2_{i}", value=None)
            with c4: st.write(f"**{t2['name']}**")
            
            p1, p2 = 0, 0
            if st.session_state.swiss_asking_penalties and g1 == g2 and g1 is not None:
                cp1, cp2 = st.columns(2)
                p1 = cp1.number_input("Pên.", 0, key=f"p1_{i}")
                p2 = cp2.number_input("Pên.", 0, key=f"p2_{i}")
            results.append({'h': t1['id'], 'a': t2['id'], 'g1': g1, 'g2': g2, 'p1': p1, 'p2': p2})

        if st.form_submit_button("Salvar Resultados"):
            if any(r['g1'] is None for r in results):
                st.error("Preencha todos os placares.")
            elif not st.session_state.swiss_asking_penalties and any(r['g1'] == r['g2'] for r in results):
                st.session_state.swiss_asking_penalties = True
                st.rerun()
            else:
                # Processa o Bye
                if curr['bye']:
                    for t in st.session_state.teams:
                        if t['id'] == curr['bye']['id']:
                            t['wins'] += 1; t['received_bye'] = True; break
                
                # Processa jogos
                for r in results:
                    # Atualiza os stats usando a lógica do torneio
                    vence_h = r['g1'] > r['g2'] if r['g1'] != r['g2'] else r['p1'] > r['p2']
                    # Função interna de update para simplificar
                    for t in st.session_state.teams:
                        if t['id'] == r['h']:
                            t['goals_for'] += r['g1']; t['goal_diff'] += (r['g1'] - r['g2'])
                            if vence_h: t['wins'] += 1
                            else: t['losses'] += 1
                        if t['id'] == r['a']:
                            t['goals_for'] += r['g2']; t['goal_diff'] += (r['g2'] - r['g1'])
                            if not vence_h: t['wins'] += 1
                            else: t['losses'] += 1
                
                # Atualiza Status (Classificados/Eliminados)
                for t in st.session_state.teams:
                    if t['wins'] >= 3: t['status'] = 'Classificado'
                    elif t['losses'] >= 3: t['status'] = 'Eliminado'
                
                sync_to_sheets()
                active = [t for t in st.session_state.teams if t['status'] == 'Ativo']
                if not active: init_playoffs()
                else: generate_swiss_round()
                st.rerun()

elif st.session_state.phase == 'playoff_gameplay':
    # Lógica de interface idêntica ao que construímos antes, mas ativa agora
    curr_p = st.session_state.playoff_schedule[-1]
    st.title(f"🏆 {curr_p['name']}")
    # ... (Interface do mata-mata segue aqui)
