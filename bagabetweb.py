import streamlit as st
import pandas as pd
import random

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Gestor de Torneio Suíço", layout="wide")

# --- ESTRUTURA DE DADOS (MODELO) ---
if 'teams' not in st.session_state:
    st.session_state.teams = [] 
if 'rounds' not in st.session_state:
    st.session_state.rounds = [] 
if 'phase' not in st.session_state:
    st.session_state.phase = 'registration' 
if 'playoff_schedule' not in st.session_state:
    st.session_state.playoff_schedule = [] 
if 'champion' not in st.session_state:
    st.session_state.champion = None

# --- FUNÇÕES AUXILIARES ---

def get_sorted_rankings(teams, for_pairing=False):
    """Ordena times por Vitórias -> Saldo -> Gols Pró"""
    temp_teams = teams.copy()
    if for_pairing:
        random.shuffle(temp_teams) # Shuffle leve para desempatar critérios idênticos
    
    return sorted(temp_teams, key=lambda x: (
        x['wins'], 
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
            
            # Regra Suíça: 3 Vitórias classifica, 3 Derrotas elimina
            if st.session_state.phase == 'swiss':
                if team['wins'] >= 3: team['status'] = 'Classificado'
                elif team['losses'] >= 3: team['status'] = 'Eliminado'
            break

def render_sidebar_stats():
    with st.sidebar:
        st.header("📊 Classificação")
        if st.session_state.teams:
            sorted_teams = get_sorted_rankings(st.session_state.teams)
            display_data = []
            for t in sorted_teams:
                status_icon = "🟢" if t['status'] == 'Classificado' else "🔴" if t['status'] == 'Eliminado' else "⚪"
                display_data.append({
                    'St': status_icon,
                    'Time': t['name'],
                    'V-D': f"{t['wins']}-{t['losses']}",
                    'SG': t['goal_diff']
                })
            st.table(pd.DataFrame(display_data))

# --- LÓGICA DO SUIÇO ---

def generate_swiss_round():
    active_teams = [t for t in st.session_state.teams if t['status'] == 'Ativo']
    if not active_teams: return
    
    random.shuffle(active_teams)
    bye_team = None
    if len(active_teams) % 2 != 0:
        # Pega o pior classificado que ainda não recebeu Bye
        eligible_for_bye = sorted([t for t in active_teams if not t['received_bye']], key=lambda x: (x['wins'], x['goal_diff']))
        bye_team = eligible_for_bye[0] if eligible_for_bye else active_teams[-1]
        active_teams.remove(bye_team)

    ranked_pool = get_sorted_rankings(active_teams, for_pairing=True)
    matches = []
    while len(ranked_pool) >= 2:
        home = ranked_pool.pop(0)
        # Tenta evitar repetir confronto
        opponent = next((c for c in ranked_pool if c['id'] not in home['history']), ranked_pool[0])
        ranked_pool.remove(opponent)
        matches.append({'home': home['id'], 'away': opponent['id']})
        home['history'].append(opponent['id'])
        opponent['history'].append(home['id'])

    st.session_state.rounds.append({'matches': matches, 'bye': bye_team})

# --- LÓGICA DO MATA-MATA (SISTEMA 1º vs ÚLTIMO) ---

def init_playoffs():
    qualified = [t for t in st.session_state.teams if t['status'] == 'Classificado']
    seeds = get_sorted_rankings(qualified) 
    num_q = len(seeds)
    current_matches = []
    waiting_teams = []
    round_name = ""

    # Chaveamento Lógico: 1º vs Último
    if num_q >= 8:
        round_name = "Quartas de Final (1ºx8º)"
        s = seeds[:8]
        current_matches = [
            {'home': s[0], 'away': s[7], 'label': 'Jogo 1'},
            {'home': s[1], 'away': s[6], 'label': 'Jogo 2'},
            {'home': s[2], 'away': s[5], 'label': 'Jogo 3'},
            {'home': s[3], 'away': s[4], 'label': 'Jogo 4'}
        ]
    elif num_q >= 4:
        round_name = "Semifinais (1ºx4º)"
        s = seeds[:4]
        current_matches = [
            {'home': s[0], 'away': s[3], 'label': 'Semi 1'},
            {'home': s[1], 'away': s[2], 'label': 'Semi 2'}
        ]
    elif num_q == 2:
        round_name = "Grande Final"
        current_matches = [{'home': seeds[0], 'away': seeds[1], 'label': 'Final'}]
    
    st.session_state.playoff_schedule.append({'name': round_name, 'matches': current_matches, 'waiting': waiting_teams})
    st.session_state.phase = 'playoff_gameplay'

def advance_playoff_round(winners):
    if len(winners) == 1:
        st.session_state.champion = winners[0]
        st.session_state.phase = 'champion'
    else:
        # Re-seeding para a próxima fase (1º vs Último entre os sobreviventes)
        seeds = get_sorted_rankings(winners)
        next_matches = []
        mid = len(seeds) // 2
        for i in range(mid):
            next_matches.append({'home': seeds[i], 'away': seeds[-(i+1)], 'label': f'Confronto {i+1}'})
        
        name = "Semifinal" if len(winners) == 4 else "Final"
        st.session_state.playoff_schedule.append({'name': name, 'matches': next_matches, 'waiting': []})

# --- INTERFACE ---

if st.session_state.phase == 'registration':
    st.title("🏆 Inscrição do Torneio")
    name = st.text_input("Nome do Time")
    if st.button("Adicionar"):
        if name:
            st.session_state.teams.append({'id': len(st.session_state.teams)+1, 'name': name, 'wins': 0, 'losses': 0, 'goals_for': 0, 'goal_diff': 0, 'received_bye': False, 'history': [], 'status': 'Ativo'})
            st.rerun()
    
    if len(st.session_state.teams) >= 6:
        if st.button("🚀 INICIAR TORNEIO"):
            st.session_state.phase = 'swiss'
            generate_swiss_round()
            st.rerun()

elif st.session_state.phase == 'swiss':
    st.title(f"⚔️ Rodada Suíça {len(st.session_state.rounds)}")
    curr = st.session_state.rounds[-1]
    
    with st.form("results"):
        results = []
        for i, m in enumerate(curr['matches']):
            t1 = next(t for t in st.session_state.teams if t['id'] == m['home'])
            t2 = next(t for t in st.session_state.teams if t['id'] == m['away'])
            c1, c2, c3, c4 = st.columns([2,1,1,2])
            with c1: st.write(f"**{t1['name']}**")
            with c2: s1 = st.number_input("Gols", 0, key=f"s1_{i}")
            with c3: s2 = st.number_input("Gols", 0, key=f"s2_{i}")
            with c4: st.write(f"**{t2['name']}**")
            results.append((t1['id'], t2['id'], s1, s2))
        
        if st.form_submit_button("Confirmar Resultados"):
            if curr['bye']: update_team_stats(curr['bye']['id'], 1, 0, True, True)
            for r in results:
                update_team_stats(r[0], r[2], r[3], r[2] > r[3])
                update_team_stats(r[1], r[3], r[2], r[3] > r[2])
            
            # Checa se ainda existem times "Ativos"
            ativos = [t for t in st.session_state.teams if t['status'] == 'Ativo']
            if len(ativos) <= 1: init_playoffs()
            else: generate_swiss_round()
            st.rerun()

elif st.session_state.phase == 'playoff_gameplay':
    curr_phase = st.session_state.playoff_schedule[-1]
    st.title(f"🔥 {curr_phase['name']}")
    
    with st.form("playoff_results"):
        winners = []
        all_filled = True
        for i, m in enumerate(curr_phase['matches']):
            st.markdown(f"**{m['label']}**")
            c1, c2, c3, c4 = st.columns([2,1,1,2])
            with c1: st.write(m['home']['name'])
            with c2: g1 = st.number_input("Gols", 0, key=f"pg1_{i}")
            with c3: g2 = st.number_input("Gols", 0, key=f"pg2_{i}")
            with c4: st.write(m['away']['name'])
            
            if g1 == g2:
                st.warning("Empate! Informe os pênaltis:")
                cp1, cp2 = st.columns(2)
                p1 = cp1.number_input("Pênaltis", 0, key=f"p1_{i}")
                p2 = cp2.number_input("Pênaltis", 0, key=f"p2_{i}")
                if p1 == p2: all_filled = False
                winners.append(m['home'] if p1 > p2 else m['away'])
            else:
                winners.append(m['home'] if g1 > g2 else m['away'])
        
        if st.form_submit_button("Avançar Fase"):
            if all_filled:
                advance_playoff_round(winners)
                st.rerun()
            else: st.error("Defina um vencedor nos pênaltis!")

elif st.session_state.phase == 'champion':
    st.balloons()
    st.title(f"🏆 CAMPEÃO: {st.session_state.champion['name']}")
    if st.button("Novo Torneio"):
        for k in list(st.session_state.keys()): del st.session_state[k]
        st.rerun()

render_sidebar_stats()
