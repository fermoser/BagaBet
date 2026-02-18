import streamlit as st
import pandas as pd
import random
import io
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Gestor de Torneio Suíço", layout="wide")

# --- CONEXÃO GOOGLE SHEETS ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    SHEET_ENABLED = True
except Exception as e:
    st.error(f"Erro de Conexão com Sheets: {e}")
    SHEET_ENABLED = False

# --- REGULAMENTO ---
REGULAMENTO_TXT = """
### 📜 REGULAMENTO OFICIAL

**1. Formato**
* **Sistema:** Suíço Híbrido.
* **Meta:** 3 Vitórias = Mata-Mata.
* **Eliminação:** 3 Derrotas = Fora.

**2. Critérios de Desempate**
1. Vitórias
2. Menos Derrotas
3. Não ter recebido Bye
4. Saldo de Gols
5. Gols Pró

**3. Mata-Mata (Seed)**
* Times que folgam (Byes) têm prioridade de Seed sobre times que jogaram a fase anterior.
"""

# --- ESTRUTURA DE DADOS ---
if 'teams' not in st.session_state: st.session_state.teams = [] 
if 'rounds' not in st.session_state: st.session_state.rounds = [] 
if 'phase' not in st.session_state: st.session_state.phase = 'registration' 
if 'playoff_schedule' not in st.session_state: st.session_state.playoff_schedule = [] 
if 'champion' not in st.session_state: st.session_state.champion = None
if 'swiss_asking_penalties' not in st.session_state: st.session_state.swiss_asking_penalties = False 
if 'playoff_asking_penalties' not in st.session_state: st.session_state.playoff_asking_penalties = False 
if 'tournament_name' not in st.session_state: st.session_state.tournament_name = ""

# --- FUNÇÕES AUXILIARES ---

def save_to_sheets():
    if not SHEET_ENABLED or not st.session_state.teams: return
    if not st.session_state.tournament_name: return

    try:
        df_current = pd.DataFrame(st.session_state.teams)
        df_current['tournament_name'] = st.session_state.tournament_name
        
        if 'received_bye' in df_current.columns:
            df_current['received_bye'] = df_current['received_bye'].apply(
                lambda x: "SIM" if str(x).upper() in ["TRUE", "SIM", "1"] else "NÃO"
            )
        df_current = df_current.astype(str)

        try:
            existing_data = conn.read(worksheet="suico", ttl=0)
            if existing_data is not None and not existing_data.empty:
                other_tournaments = existing_data[existing_data['tournament_name'] != st.session_state.tournament_name]
                df_final = pd.concat([other_tournaments, df_current], ignore_index=True)
            else:
                df_final = df_current
        except:
            df_final = df_current

        conn.update(worksheet="suico", data=df_final)
    except Exception as e:
        st.error(f"⚠️ Erro ao salvar: {e}")

def get_sorted_rankings(teams, for_pairing=False):
    if for_pairing:
        teams = teams.copy()
        random.shuffle(teams)
     
    return sorted(teams, key=lambda x: (
        x['wins'], 
        -x['losses'], 
        not x['received_bye'], 
        x['goal_diff'], 
        x['goals_for']
    ), reverse=True)

def update_team_stats(team_id, goals_scored, goals_conceded, is_winner, is_bye=False):
    found = False
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
            found = True
            break
    if not found: st.error(f"Erro ID {team_id}")

def convert_df_to_csv(df):
    return df.to_csv(index=False).encode('utf-8')

def generate_export_data():
    if st.session_state.teams:
        sorted_teams = get_sorted_rankings(st.session_state.teams)
        rank_data = [{'Time': t['name'], 'V': t['wins'], 'D': t['losses'], 'SG': t['goal_diff'], 'GP': t['goals_for'], 'St': t['status']} for t in sorted_teams]
        df_rank = pd.DataFrame(rank_data)
    else:
        df_rank = pd.DataFrame()
    return df_rank

def render_sidebar_stats():
    with st.sidebar:
        st.header("📊 Classificação")
        if st.session_state.tournament_name: st.caption(f"🏆 {st.session_state.tournament_name}")

        if st.session_state.teams:
            sorted_teams = get_sorted_rankings(st.session_state.teams)
            current_bye_id = None
            if st.session_state.phase == 'swiss' and st.session_state.rounds:
                curr = st.session_state.rounds[-1]
                if curr.get('bye') and not curr.get('completed'): current_bye_id = curr['bye']['id']

            st.markdown("""<style>.compact-table {width:100%; font-size:12px;} th{text-align:left;}</style>""", unsafe_allow_html=True)
            html_rows = ""
            for t in sorted_teams:
                status_icon = "🟢" if t['status'] == 'Classificado' else ("🔴" if t['status'] == 'Eliminado' else "⚪")
                name_display = f"<b>{t['name']} (F)</b>" if (current_bye_id and t['id'] == current_bye_id) else t['name']
                bye_disp = 'Sim' if (t['received_bye'] or (current_bye_id and t['id'] == current_bye_id)) else '-'
                html_rows += f"<tr><td>{status_icon}</td><td>{name_display}</td><td>{t['wins']}-{t['losses']}</td><td>{t['goal_diff']}</td></tr>"

            st.markdown(f"""<table class="compact-table"><thead><tr><th>St</th><th>Time</th><th>V-D</th><th>SG</th></tr></thead><tbody>{html_rows}</tbody></table>""", unsafe_allow_html=True)
        
        st.divider()
        if st.button("📥 Baixar CSV"):
            df = generate_export_data()
            st.download_button("Download", convert_df_to_csv(df), "dados.csv", "text/csv")

# --- LÓGICA SUÍÇO ---
def generate_swiss_round():
    st.session_state.swiss_asking_penalties = False 
    active_teams = [t for t in st.session_state.teams if t['status'] == 'Ativo' and t['losses'] < 3]
    bye_team = None
    
    if len(active_teams) % 2 != 0:
        eligible = [t for t in active_teams if not t['received_bye']]
        candidates = eligible if eligible else active_teams
        
        if st.session_state.rounds:
            last_round = st.session_state.rounds[-1]
            loser_ids = []
            for m in last_round['matches']:
                wid = m.get('winner_id')
                if wid: loser_ids.append(m['away'] if wid == m['home'] else m['home'])
            loser_candidates = [t for t in candidates if t['id'] in loser_ids]
            if loser_candidates: candidates = loser_candidates
            
        if candidates:
            bye_team = random.choice(candidates)
            active_teams.remove(bye_team)
    
    ranked_pool = get_sorted_rankings(active_teams, for_pairing=True)
    matches = []
    while len(ranked_pool) >= 2:
        home = ranked_pool.pop(0)
        opponent = next((ranked_pool.pop(i) for i, c in enumerate(ranked_pool) if c['id'] not in home['history']), ranked_pool.pop(0))
        matches.append({'home': home['id'], 'away': opponent['id'], 'home_score': 0, 'away_score': 0})
        home['history'].append(opponent['id']); opponent['history'].append(home['id'])

    st.session_state.rounds.append({'matches': matches, 'bye': bye_team, 'completed': False})

# --- LÓGICA MATA-MATA (REVISADA E UNIVERSAL) ---
def init_playoffs():
    qualified = [t for t in st.session_state.teams if t['status'] == 'Classificado']
    seeds = get_sorted_rankings(qualified) 
    
    if len(seeds) > 8: seeds = seeds[:8]
    num_q = len(seeds)
    
    matches, waiting = [], []
    r_name = ""

    if num_q == 3:
        r_name = "Semifinal Única"
        waiting = [seeds[0]]
        matches = [{'id': 'S1', 'home': seeds[1], 'away': seeds[2], 'label': 'Semifinal'}]
    elif num_q == 4:
        r_name = "Semifinais"
        matches = [{'id': 'S1', 'home': seeds[0], 'away': seeds[3], 'label': 'Semi 1'}, {'id': 'S2', 'home': seeds[1], 'away': seeds[2], 'label': 'Semi 2'}]
    elif num_q == 5:
        r_name = "Wildcard (Repescagem)"
        waiting = [seeds[0], seeds[1], seeds[2]] 
        matches = [{'id': 'WC', 'home': seeds[3], 'away': seeds[4], 'label': 'Repescagem'}]
    elif num_q == 6:
        r_name = "Quartas de Final"
        waiting = [seeds[0], seeds[1]]
        matches = [{'id': 'QFA', 'home': seeds[3], 'away': seeds[4], 'label': 'QF A'}, {'id': 'QFB', 'home': seeds[2], 'away': seeds[5], 'label': 'QF B'}]
    elif num_q == 7:
        r_name = "Quartas de Final"
        waiting = [seeds[0]]
        matches = [{'id': 'QFA', 'home': seeds[3], 'away': seeds[4], 'label': 'QF A'}, {'id': 'QFB', 'home': seeds[2], 'away': seeds[5], 'label': 'QF B'}, {'id': 'QFC', 'home': seeds[1], 'away': seeds[6], 'label': 'QF C'}]
    elif num_q == 8:
        r_name = "Quartas de Final"
        matches = [{'id': 'Q1', 'home': seeds[0], 'away': seeds[7], 'label': 'QF 1'}, {'id': 'Q2', 'home': seeds[1], 'away': seeds[6], 'label': 'QF 2'}, {'id': 'Q3', 'home': seeds[2], 'away': seeds[5], 'label': 'QF 3'}, {'id': 'Q4', 'home': seeds[3], 'away': seeds[4], 'label': 'QF 4'}]
    
    if num_q < 3: st.error("Mínimo 3 classificados."); return

    for m in matches:
        m.update({'h_goals': 0, 'a_goals': 0, 'h_pen': 0, 'a_pen': 0})

    st.session_state.playoff_schedule = [{'name': r_name, 'matches': matches, 'waiting': waiting, 'completed': False}]
    st.session_state.phase = 'playoff_gameplay'
    save_to_sheets()

def advance_playoff_round(results, waiting_teams, losers=None):
    st.session_state.playoff_asking_penalties = False 
    last_r = st.session_state.playoff_schedule[-1]

    # --- LÓGICA UNIVERSAL DE SEED ---
    # 1. Ordena quem estava esperando (Seeds superiores)
    waiting_sorted = get_sorted_rankings(waiting_teams)
    # 2. Ordena quem veio da rodada anterior (Seeds inferiores)
    results_sorted = get_sorted_rankings(results)
    
    # 3. CONCATENA: Superiores PRIMEIRO, Inferiores DEPOIS.
    # Isso garante que quem jogou repescagem (results) sempre entre DEPOIS de quem folgou (waiting)
    if waiting_teams:
        pool = waiting_sorted + results_sorted
    else:
        # Se ninguém folgou, reordena todo mundo junto por mérito
        pool = get_sorted_rankings(results)

    count = len(pool)
    next_matches, next_name = [], ""
    
    if last_r['name'] == "Finais":
        champ, vice, third = None, None, None
        for m in last_r['matches']:
            w = m['home'] if m['winner_id'] == m['home']['id'] else m['away']
            l = m['away'] if m['winner_id'] == m['home']['id'] else m['home']
            if m['id'] == 'FINAL': champ, vice = w, l
            elif m['id'] == '3RD': third = w
        
        st.session_state.champion = champ
        st.session_state.vice = vice
        st.session_state.third = third
        st.session_state.phase = 'champion'
        save_to_sheets()
        return

    if last_r['name'] == "Semifinais" and losers and len(losers) == 2:
        next_name = "Finais"
        # Grande Final (Mérito total decide mando)
        finalists = get_sorted_rankings(pool)
        next_matches.append({'id': 'FINAL', 'home': finalists[0], 'away': finalists[1], 'label': '🏆 Final'})
        # 3º Lugar
        losers_sorted = get_sorted_rankings(losers)
        next_matches.append({'id': '3RD', 'home': losers_sorted[0], 'away': losers_sorted[1], 'label': '🥉 3º Lugar'})

    elif count == 2:
        next_name = "Grande Final"
        next_matches = [{'id': 'F', 'home': pool[0], 'away': pool[1], 'label': 'Final'}]
    elif count == 4:
        next_name = "Semifinais"
        # Cruzamento Olímpico Fixo (1x4, 2x3) baseado na ordem do pool
        next_matches = [
            {'id': 'S1', 'home': pool[0], 'away': pool[3], 'label': 'Semi 1'},
            {'id': 'S2', 'home': pool[1], 'away': pool[2], 'label': 'Semi 2'}
        ]
    else:
        next_name = "Rodada Eliminatória"
        # Pareamento Melhor x Pior da lista pool
        while len(pool) >= 2:
            h, a = pool.pop(0), pool.pop(-1)
            next_matches.append({'id': 'GEN', 'home': h, 'away': a, 'label': 'Jogo'})
            
    if not next_matches and count == 1:
        st.session_state.champion = pool[0]; st.session_state.phase = 'champion'; save_to_sheets(); return

    for m in next_matches: m.update({'h_goals': 0, 'a_goals': 0, 'h_pen': 0, 'a_pen': 0})

    st.session_state.playoff_schedule.append({'name': next_name, 'matches': next_matches, 'waiting': [], 'completed': False})
    save_to_sheets()

# --- APP ---
if st.session_state.phase == 'registration':
    st.title("🏆 Inscrição")
    st.session_state.tournament_name = st.text_input("Nome do Torneio", value=st.session_state.tournament_name)
    c1, c2 = st.columns([3,1])
    with c1: st.text_input("Time", key="team_input")
    with c2: st.button("Add", on_click=add_team_callback)
    
    if st.session_state.teams:
        st.write(f"Inscritos: {len(st.session_state.teams)}")
        if st.button("Iniciar"):
            if not st.session_state.tournament_name: st.error("Nome obrigatório!")
            elif 6 <= len(st.session_state.teams) <= 16:
                st.session_state.phase = 'swiss'
                generate_swiss_round()
                save_to_sheets()
                st.rerun()
            else: st.error("Min 6, Max 16 times.")

elif st.session_state.phase == 'swiss':
    rid = len(st.session_state.rounds)
    st.title(f"⚔️ Suíço - Rodada {rid}")
    cr = st.session_state.rounds[-1]
    if cr['bye']: st.success(f"Bye: {cr['bye']['name']}")
    
    with st.form(f"sw_{rid}"):
        matches_in = []
        any_draw = False
        dis = st.session_state.swiss_asking_penalties
        
        for i, m in enumerate(cr['matches']):
            hn = next(t['name'] for t in st.session_state.teams if t['id'] == m['home'])
            an = next(t['name'] for t in st.session_state.teams if t['id'] == m['away'])
            c1,c2,c3,c4 = st.columns([2,1,1,2])
            with c1: st.write(hn)
            with c2: s1 = st.number_input("G", 0, key=f"h{i}", disabled=dis)
            with c3: s2 = st.number_input("G", 0, key=f"a{i}", disabled=dis)
            with c4: st.write(an)
            ph, pa = 0, 0
            if dis and s1 is not None and s1 == s2:
                kp1, kp2 = st.columns(2)
                ph = kp1.number_input(f"Pen {hn}", 0, key=f"ph{i}")
                pa = kp2.number_input(f"Pen {an}", 0, key=f"pa{i}")
            matches_in.append({'idx': i, 'hid': m['home'], 'aid': m['away'], 'hg': s1, 'ag': s2, 'hp': ph, 'ap': pa})
            
        btn = "Confirmar Classificação" if dis else "Conferir"
        if st.form_submit_button(btn):
            if any(x['hg'] is None for x in matches_in): st.error("Preencha tudo.")
            else:
                if not dis:
                    if any(x['hg'] == x['ag'] for x in matches_in):
                        st.session_state.swiss_asking_penalties = True; st.rerun()
                    else:
                        # Processa Sem Penaltis
                        if cr['bye']: update_team_stats(cr['bye']['id'], 1, 0, True, True)
                        for x in matches_in:
                            wh = x['hg'] > x['ag']
                            wid = x['hid'] if wh else x['aid']
                            cr['matches'][x['idx']].update({'winner_id': wid, 'home_score': x['hg'], 'away_score': x['ag']})
                            update_team_stats(x['hid'], x['hg'], x['ag'], wh)
                            update_team_stats(x['aid'], x['ag'], x['hg'], not wh)
                        cr['completed'] = True; save_to_sheets()
                        if len([t for t in st.session_state.teams if t['status']=='Ativo']) <= 1: init_playoffs()
                        else: generate_swiss_round()
                        st.rerun()
                else:
                    # Processa Com Penaltis
                    valid = True
                    for x in matches_in:
                        if x['hg'] == x['ag'] and (x['hp'] is None or x['hp'] == x['ap']): valid = False
                    if not valid: st.error("Erro nos pênaltis.")
                    else:
                        if cr['bye']: update_team_stats(cr['bye']['id'], 1, 0, True, True)
                        for x in matches_in:
                            wh = x['hg'] > x['ag'] if x['hg'] != x['ag'] else x['hp'] > x['ap']
                            wid = x['hid'] if wh else x['aid']
                            cr['matches'][x['idx']].update({'winner_id': wid, 'home_score': x['hg'], 'away_score': x['ag'], 'h_pen': x['hp'], 'a_pen': x['ap']})
                            update_team_stats(x['hid'], x['hg'], x['ag'], wh)
                            update_team_stats(x['aid'], x['ag'], x['hg'], not wh)
                        cr['completed'] = True; save_to_sheets()
                        if len([t for t in st.session_state.teams if t['status']=='Ativo']) <= 1: init_playoffs()
                        else: generate_swiss_round()
                        st.rerun()

elif st.session_state.phase == 'playoff_gameplay':
    st.title("🔥 Mata-Mata")
    curr = st.session_state.playoff_schedule[-1]
    rid = len(st.session_state.playoff_schedule)
    st.subheader(curr['name'])
    if curr['waiting']: st.info(f"Aguardando: {', '.join([t['name'] for t in curr['waiting']])}")
    
    with st.form(f"pf_{rid}"):
        minp = []
        dis = st.session_state.playoff_asking_penalties
        for i, m in enumerate(curr['matches']):
            st.write(m['label'])
            c1,c2,c3,c4 = st.columns([2,1,1,2])
            with c1: st.write(m['home']['name'])
            with c2: vh = st.number_input("G", 0, key=f"ph{rid}{i}", disabled=dis)
            with c3: va = st.number_input("G", 0, key=f"pa{rid}{i}", disabled=dis)
            with c4: st.write(m['away']['name'])
            ph, pa = 0, 0
            if dis and vh == va:
                k1, k2 = st.columns(2)
                ph = k1.number_input(f"P {m['home']['name']}", 0, key=f"pph{rid}{i}")
                pa = k2.number_input(f"P {m['away']['name']}", 0, key=f"ppa{rid}{i}")
            minp.append({'m': m, 'vh': vh, 'va': va, 'ph': ph, 'pa': pa})
            
        btn = "Confirmar" if dis else "Conferir"
        if st.form_submit_button(btn):
            if any(x['vh'] is None for x in minp): st.error("Preencha tudo.")
            else:
                if not dis:
                    if any(x['vh'] == x['va'] for x in minp): st.session_state.playoff_asking_penalties = True; st.rerun()
                    else:
                        wins, loss = [], []
                        for x in minp:
                            m = x['m']
                            m.update({'h_goals': x['vh'], 'a_goals': x['va'], 'is_penalties': False})
                            wh = x['vh'] > x['va']
                            w = m['home'] if wh else m['away']
                            l = m['away'] if wh else m['home']
                            m['winner_id'] = w['id']
                            wins.append(w); loss.append(l)
                            update_team_stats(m['home']['id'], x['vh'], x['va'], wh)
                            update_team_stats(m['away']['id'], x['va'], x['vh'], not wh)
                        curr['completed'] = True
                        advance_playoff_round(wins, curr['waiting'], losers=loss)
                        st.rerun()
                else:
                    valid = True
                    for x in minp:
                        if x['vh'] == x['va'] and (x['ph'] is None or x['ph'] == x['pa']): valid = False
                    if not valid: st.error("Erro Pênaltis.")
                    else:
                        wins, loss = [], []
                        for x in minp:
                            m = x['m']
                            m.update({'h_goals': x['vh'], 'a_goals': x['va'], 'h_pen': x['ph'], 'a_pen': x['pa']})
                            wh = x['vh'] > x['va'] if x['vh'] != x['va'] else x['ph'] > x['pa']
                            m['is_penalties'] = (x['vh'] == x['va'])
                            w = m['home'] if wh else m['away']
                            l = m['away'] if wh else m['home']
                            m['winner_id'] = w['id']
                            wins.append(w); loss.append(l)
                            update_team_stats(m['home']['id'], x['vh'], x['va'], wh)
                            update_team_stats(m['away']['id'], x['va'], x['vh'], not wh)
                        curr['completed'] = True
                        advance_playoff_round(wins, curr['waiting'], losers=loss)
                        st.rerun()

elif st.session_state.phase == 'champion':
    st.balloons()
    st.title(f"🏆 {st.session_state.champion['name']} CAMPEÃO!")
    if st.button("Novo Torneio"):
        for k in list(st.session_state.keys()): del st.session_state[k]
        st.rerun()

render_sidebar_stats()
