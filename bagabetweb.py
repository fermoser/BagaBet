import streamlit as st
import pandas as pd
from itertools import combinations
from streamlit_gsheets import GSheetsConnection
from datetime import datetime, timedelta
import random
import io

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="BAGA GESTOR PRO", layout="wide")

# --- ESTILO CSS ---
st.markdown("""
    <style>
    input[type=number] { color: #F4D03F !important; font-weight: bold !important; font-size: 20px !important; }
    .stMarkdown div[style*="background:#eee"] { background-color: #333 !important; color: #F4D03F !important; font-weight: bold; border-radius: 5px; }
    .compact-table { width: 100%; font-size: 12px; border-collapse: collapse; }
    .compact-table th, .compact-table td { padding: 4px; text-align: center; border-bottom: 1px solid #444; }
    .compact-table th { background-color: #262730; color: white; }
    .text-left { text-align: left !important; }
    </style>
    """, unsafe_allow_html=True)

conn = st.connection("gsheets", type=GSheetsConnection)
ABA_JOGOS = "Página1" 
ABA_HISTORICO = "Historico"
ABA_SUICO = "suico"
COLUNAS = ['torneio_id', 'formato', 'fase', 'a', 'b', 'finalizado', 'gols_a', 'gols_b', 'ida_a', 'ida_b', 'volta_a', 'volta_b', 'pen_a', 'pen_b', 'modo_copa']

ORDEM_FASES = {"Oitavas": 1, "Quartas": 2, "Semifinal": 3, "3º Lugar": 4, "Final": 5, "Liga": 6, "Turno Único": 6}

# --- REGULAMENTO SUÍÇO ---
REGULAMENTO_TXT = """
### 📜 REGULAMENTO OFICIAL – TORNEIO SUÍÇO (TRIPLE ELIMINATION)
**1. Formato**
* **Sistema:** Suíço Híbrido (Classificatória + Mata-Mata).
* **Meta:** 3 Vitórias garantem vaga no Mata-Mata.
* **Eliminação:** 3 Derrotas eliminam a equipe.

**2. Fase de Classificação**
* Jogos definidos por campanhas iguais (Vencedores x Vencedores).
* **Bye (Folga):** Em rodadas com número ímpar, um time folga.
* **Critério do Bye:** Sorteio aleatório entre os times que perderam na rodada anterior e ainda não tiveram Bye.

**3. Critérios de Desempate**
1. Vitórias
2. Menos Derrotas
3. Não ter recebido Bye
4. Saldo de Gols
5. Gols Pró

**4. Fase Final (Mata-Mata)**
* Os 8 melhores classificados avançam.
* Vencedores de repescagem sempre entram como últimos Seeds na rodada seguinte.
"""

# --- GESTÃO DE ESTADO (SUPER APP) ---
if 'torneio_ativo' not in st.session_state: st.session_state.torneio_ativo = None
if 'temp_fmt' not in st.session_state: st.session_state.temp_fmt = "COPA"

# --- GESTÃO DE ESTADO (SUÍÇO) ---
keys_suico = {
    'teams': [], 'rounds': [], 'phase': 'registration', 'playoff_schedule': [], 
    'champion': None, 'vice': None, 'third': None, 
    'swiss_asking_penalties': False, 'playoff_asking_penalties': False, 'bye_history': []
}
for k, v in keys_suico.items():
    if k not in st.session_state: st.session_state[k] = v

# --- FUNÇÕES DE DADOS (SUPER APP) ---
def carregar_dados(aba):
    try:
        df = conn.read(worksheet=aba, ttl="0s")
        if df is None or df.empty:
            return pd.DataFrame(columns=COLUNAS) if aba == ABA_JOGOS else pd.DataFrame(columns=['torneio_id','formato','campeao','vice','terceiro','data_fim'])
        df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
        if aba == ABA_JOGOS:
            for c in COLUNAS:
                if c not in df.columns: df[c] = None
            cols_n = ['gols_a', 'gols_b', 'ida_a', 'ida_b', 'volta_a', 'volta_b', 'pen_a', 'pen_b']
            for col in cols_n:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
        return df
    except: return pd.DataFrame(columns=COLUNAS)

def salvar_dados(df, aba):
    df = df.dropna(subset=['torneio_id'])
    conn.update(worksheet=aba, data=df)
    st.cache_data.clear()

def is_done(val): return str(val).upper().strip() in ["1", "SIM", "TRUE"]

def obter_vencedor_perdedor(r):
    if not is_done(r['finalizado']): return None, None
    if r['fase'] in ["Final", "3º Lugar", "Liga", "Turno Único"] or r['modo_copa'] == "Só Ida":
        sa, sb = int(r['gols_a']), int(r['gols_b'])
    else:
        sa, sb = int(r['ida_a']) + int(r['volta_a']), int(r['ida_b']) + int(r['volta_b'])
    
    if sa > sb: return r['a'], r['b']
    elif sb > sa: return r['b'], r['a']
    else:
        pa, pb = int(r.get('pen_a', 0)), int(r.get('pen_b', 0))
        if pa > pb: return r['a'], r['b']
        if pb > pa: return r['b'], r['a']
        return None, None

# --- FUNÇÕES DE DADOS (SUÍÇO) ---
def save_to_sheets_suico():
    if not st.session_state.torneio_ativo or not st.session_state.teams: return
    try:
        df_current = pd.DataFrame(st.session_state.teams)
        df_current['tournament_name'] = st.session_state.torneio_ativo
        if 'received_bye' in df_current.columns:
            df_current['received_bye'] = df_current['received_bye'].apply(lambda x: "SIM" if str(x).upper() in ["TRUE", "SIM", "1"] else "NÃO")
        df_current = df_current.astype(str)
        try:
            existing_data = conn.read(worksheet=ABA_SUICO, ttl=0)
            if existing_data is not None and not existing_data.empty:
                other_tournaments = existing_data[existing_data['tournament_name'] != st.session_state.torneio_ativo]
                df_final = pd.concat([other_tournaments, df_current], ignore_index=True)
            else: df_final = df_current
        except: df_final = df_current
        conn.update(worksheet=ABA_SUICO, data=df_final)
    except Exception as e: st.error(f"Erro ao salvar Suíço: {e}")

def get_sorted_rankings(teams, for_pairing=False):
    if for_pairing:
        teams = teams.copy()
        random.shuffle(teams)
    return sorted(teams, key=lambda x: (x['wins'], -x['losses'], not x['received_bye'], x['goal_diff'], x['goals_for']), reverse=True)

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

def render_sidebar_stats_suico():
    if st.session_state.teams:
        sorted_teams = get_sorted_rankings(st.session_state.teams, for_pairing=False)
        current_bye_id = None
        if st.session_state.phase == 'swiss' and st.session_state.rounds:
            curr = st.session_state.rounds[-1]
            if curr.get('bye') and not curr.get('completed'): current_bye_id = curr['bye']['id']

        html_rows = ""
        for t in sorted_teams:
            status_icon = "🟢" if t['status'] == 'Classificado' else ("🔴" if t['status'] == 'Eliminado' else "⚪")
            is_current_bye = (current_bye_id and t['id'] == current_bye_id)
            name_display = f"<b>{t['name']} (F)</b>" if is_current_bye else t['name']
            bye_disp = 'Sim' if (t['received_bye'] or is_current_bye) else '-'
            goals_against = t['goals_for'] - t['goal_diff']
            rec = f"{t['wins']}-{t['losses']}"
            html_rows += f"<tr><td>{status_icon}</td><td class='text-left'>{name_display}</td><td>{rec}</td><td>{bye_disp}</td><td>{t['goals_for']}</td><td>{goals_against}</td><td>{t['goal_diff']}</td></tr>"

        table_html = f"""
        <table class="compact-table"><thead><tr><th title="Status">St</th><th class="text-left">Time</th><th>V-D</th><th>Bye</th><th title="Gols Pró">GP</th><th title="Gols Contra">GC</th><th title="Saldo de Gols">SG</th></tr></thead><tbody>{html_rows}</tbody></table>
        """
        st.markdown(table_html, unsafe_allow_html=True)
        st.caption("GP: Pró | GC: Contra | SG: Saldo | (F): Folga na rodada")

def generate_swiss_round():
    st.session_state.swiss_asking_penalties = False 
    active_teams = [t for t in st.session_state.teams if t['status'] == 'Ativo' and t['losses'] < 3]
    bye_team = None
    
    if len(active_teams) % 2 != 0:
        eligible_for_bye = [t for t in active_teams if not t['received_bye']]
        candidates = []
        if not st.session_state.rounds: candidates = eligible_for_bye
        else:
            last_round = st.session_state.rounds[-1]
            loser_ids = []
            for m in last_round['matches']:
                winner_id = m.get('winner_id')
                if winner_id:
                    loser = m['away'] if winner_id == m['home'] else m['home']
                    loser_ids.append(loser)
            loser_candidates = [t for t in eligible_for_bye if t['id'] in loser_ids]
            candidates = loser_candidates if loser_candidates else eligible_for_bye
        
        if candidates:
            bye_team = random.choice(candidates)
            active_teams.remove(bye_team)
    
    ranked_pool = get_sorted_rankings(active_teams, for_pairing=True)
    matches = []
    
    while len(ranked_pool) >= 2:
        home = ranked_pool.pop(0)
        opponent = None
        for i, candidate in enumerate(ranked_pool):
            if candidate['id'] not in home['history']:
                opponent = ranked_pool.pop(i)
                break
        if not opponent: opponent = ranked_pool.pop(0)
            
        matches.append({'home': home['id'], 'away': opponent['id'], 'home_score': 0, 'away_score': 0})
        home['history'].append(opponent['id']); opponent['history'].append(home['id'])

    st.session_state.rounds.append({'matches': matches, 'bye': bye_team, 'completed': False})

def init_playoffs():
    qualified = [t for t in st.session_state.teams if t['status'] == 'Classificado']
    seeds = get_sorted_rankings(qualified, for_pairing=False) 
    if len(seeds) > 8: seeds = seeds[:8]
    
    num_q = len(seeds)
    current_matches, waiting_teams, round_name = [], [], ""

    if num_q == 3:
        round_name = "Semifinal Única"; waiting_teams = [seeds[0]]
        current_matches = [{'id': 'S1', 'home': seeds[1], 'away': seeds[2], 'label': 'Semifinal'}]
    elif num_q == 4:
        round_name = "Semifinais"
        current_matches = [{'id': 'S1', 'home': seeds[0], 'away': seeds[3], 'label': 'Semi 1'}, {'id': 'S2', 'home': seeds[1], 'away': seeds[2], 'label': 'Semi 2'}]
    elif num_q == 5:
        round_name = "Wildcard (Repescagem)"; waiting_teams = [seeds[0], seeds[1], seeds[2]] 
        current_matches = [{'id': 'WC', 'home': seeds[3], 'away': seeds[4], 'label': 'Repescagem'}]
    elif num_q == 6:
        round_name = "Quartas de Final"; waiting_teams = [seeds[0], seeds[1]]
        current_matches = [{'id': 'QFA', 'home': seeds[3], 'away': seeds[4], 'label': 'Quartas A'}, {'id': 'QFB', 'home': seeds[2], 'away': seeds[5], 'label': 'Quartas B'}]
    elif num_q == 7:
        round_name = "Quartas de Final"; waiting_teams = [seeds[0]]
        current_matches = [{'id': 'QFA', 'home': seeds[3], 'away': seeds[4], 'label': 'Quartas A'}, {'id': 'QFB', 'home': seeds[2], 'away': seeds[5], 'label': 'Quartas B'}, {'id': 'QFC', 'home': seeds[1], 'away': seeds[6], 'label': 'Quartas C'}]
    elif num_q >= 8:
        seeds = seeds[:8]; round_name = "Quartas de Final"
        current_matches = [{'id': 'Q1', 'home': seeds[0], 'away': seeds[7], 'label': 'Quartas 1'}, {'id': 'Q2', 'home': seeds[1], 'away': seeds[6], 'label': 'Quartas 2'}, {'id': 'Q3', 'home': seeds[2], 'away': seeds[5], 'label': 'Quartas 3'}, {'id': 'Q4', 'home': seeds[3], 'away': seeds[4], 'label': 'Quartas 4'}]
    
    if num_q < 3: st.error("Mínimo 3 classificados."); return

    for m in current_matches: m.update({'h_goals': 0, 'a_goals': 0, 'h_pen': 0, 'a_pen': 0})
    st.session_state.playoff_schedule = [{'name': round_name, 'matches': current_matches, 'waiting': waiting_teams, 'completed': False}]
    st.session_state.phase = 'playoff_gameplay'
    st.session_state.playoff_asking_penalties = False
    save_to_sheets_suico()

def advance_playoff_round(results, waiting_teams, losers=None):
    st.session_state.playoff_asking_penalties = False 
    last_round = st.session_state.playoff_schedule[-1]
    
    # Lógica Universal de Seed para o Suíço (Garante Wildcard no final)
    waiting_sorted = get_sorted_rankings(waiting_teams, for_pairing=False)
    results_sorted = get_sorted_rankings(results, for_pairing=False)
    pool = (waiting_sorted + results_sorted) if waiting_teams else get_sorted_rankings(results, for_pairing=False)

    count = len(pool)
    next_matches, next_round_name = [], ""
    
    if last_round['name'] == "Finais":
        for m in last_round['matches']:
            winner_id = m.get('winner_id')
            w = m['home'] if winner_id == m['home']['id'] else m['away']
            l = m['away'] if winner_id == m['home']['id'] else m['home']
            if m['id'] == 'FINAL': st.session_state.champion, st.session_state.vice = w, l
            elif m['id'] == '3RD': st.session_state.third = w
        st.session_state.phase = 'champion'
        save_to_sheets_suico()
        return

    if last_round['name'] == "Semifinais" and losers and len(losers) == 2:
        next_round_name = "Finais"
        finalists = get_sorted_rankings(pool, for_pairing=False)
        next_matches.append({'id': 'FINAL', 'home': finalists[0], 'away': finalists[1], 'label': '🏆 Grande Final'})
        losers_sorted = get_sorted_rankings(losers, for_pairing=False)
        next_matches.append({'id': '3RD', 'home': losers_sorted[0], 'away': losers_sorted[1], 'label': '🥉 Disputa de 3º Lugar'})
    elif count == 2:
        next_round_name = "Grande Final"
        next_matches = [{'id': 'F', 'home': pool[0], 'away': pool[1], 'label': 'Final'}]
    elif count == 4:
        next_round_name = "Semifinais"
        next_matches = [{'id': 'S1', 'home': pool[0], 'away': pool[3], 'label': 'Semi 1'}, {'id': 'S2', 'home': pool[1], 'away': pool[2], 'label': 'Semi 2'}]
    else:
        next_round_name = "Rodada Eliminatória"
        while len(pool) >= 2: next_matches.append({'id': 'GEN', 'home': pool.pop(0), 'away': pool.pop(-1), 'label': 'Jogo'})
            
    if not next_matches and count == 1:
        st.session_state.champion = pool[0]; st.session_state.phase = 'champion'; save_to_sheets_suico(); return

    for m in next_matches: m.update({'h_goals': 0, 'a_goals': 0, 'h_pen': 0, 'a_pen': 0})
    st.session_state.playoff_schedule.append({'name': next_round_name, 'matches': next_matches, 'waiting': [], 'completed': False})
    save_to_sheets_suico()


# --- BANCO DE DADOS PRINCIPAL ---
df_db = carregar_dados(ABA_JOGOS)
df_hist = carregar_dados(ABA_HISTORICO)

# ==========================================
# --- ROTEADOR PRINCIPAL DA APLICAÇÃO ---
# ==========================================

if st.session_state.torneio_ativo is None:
    # -----------------------------------
    # TELA INICIAL (MENU GERAL)
    # -----------------------------------
    st.title("⚽ BAGA GESTOR PRO")
    
    with st.expander("📜 HALL DA FAMA"):
        if not df_hist.empty: st.dataframe(df_hist.sort_index(ascending=False), use_container_width=True)

    torneios = df_db['torneio_id'].unique() if not df_db.empty else []
    if len(torneios) > 0:
        st.subheader("📂 Abrir Torneio")
        cols = st.columns(3)
        for i, t in enumerate(torneios):
            fmt_lbl = df_db[df_db['torneio_id']==t]['formato'].iloc[0]
            if cols[i%3].button(f"🏆 {t} ({fmt_lbl})", key=f"t_{t}", use_container_width=True):
                st.session_state.torneio_ativo = t
                st.rerun()

    st.divider()
    with st.form("novo_t"):
        st.subheader("🆕 Criar Novo")
        c1, c2, c3 = st.columns(3)
        n = c1.text_input("Nome")
        st.session_state.temp_fmt = c2.selectbox("Tipo", ["COPA", "LIGA", "SUÍÇO"])
        m = c3.selectbox("Modo", ["Só Ida", "Ida e Volta"]) if st.session_state.temp_fmt == "COPA" else "Só Ida"
        
        if st.form_submit_button("CRIAR TORNEIO"):
            if n: 
                # Se for SUÍÇO, zera as variáveis de sessão para garantir um torneio limpo
                if st.session_state.temp_fmt == "SUÍÇO":
                    for k, v in keys_suico.items(): st.session_state[k] = v
                
                # Registra o torneio no banco principal para ele aparecer no Menu Inicial
                novo_t = pd.DataFrame([{'torneio_id': n, 'formato': st.session_state.temp_fmt, 'fase': 'Setup', 'finalizado':'NÃO'}])
                salvar_dados(pd.concat([df_db, novo_t], ignore_index=True), ABA_JOGOS)
                
                st.session_state.torneio_ativo = n
                st.rerun()

else:
    # -----------------------------------
    # DENTRO DE UM TORNEIO ATIVO
    # -----------------------------------
    tid = st.session_state.torneio_ativo
    df_t = df_db[df_db['torneio_id'] == tid].copy()
    fmt = df_t['formato'].iloc[0] if not df_t.empty else st.session_state.temp_fmt

    # --- SIDEBAR COMPARTILHADA ---
    with st.sidebar:
        st.header(f"🏆 {tid}")
        if fmt == "SUÍÇO":
            if st.button("🏠 Voltar ao Menu Principal"):
                st.session_state.torneio_ativo = None
                st.rerun()
            st.divider()
            st.subheader("📊 Classificação Suíço")
            render_sidebar_stats_suico()
        else:
            menu = st.radio("Menu", ["🏟️ Jogos", "📊 Consulta", "⚙️ Admin"])
            is_admin = (st.text_input("Senha Admin", type="password") == "1234")
            if st.button("🏠 Voltar ao Menu Principal"): 
                st.session_state.torneio_ativo = None; st.rerun()

    # ==========================================
    # FLUXO 1: MODO SUÍÇO
    # ==========================================
    if fmt == "SUÍÇO":
        
        if st.session_state.phase == 'registration':
            st.title("🏆 Inscrição - Modo Suíço")
            
            c1, c2 = st.columns([3,1])
            with c1: st.text_input("Nome do Time", key="team_input")
            with c2: 
                if st.button("Adicionar"):
                    new_team = st.session_state.team_input
                    if new_team and new_team not in [t['name'] for t in st.session_state.teams]:
                        new_id = (max([t['id'] for t in st.session_state.teams]) + 1) if st.session_state.teams else 1
                        st.session_state.teams.append({'id': new_id, 'name': new_team, 'wins': 0, 'losses': 0, 'goals_for': 0, 'goal_diff': 0, 'received_bye': False, 'history': [], 'status': 'Ativo'})
                        st.session_state.team_input = "" 
            
            if st.session_state.teams:
                st.markdown("---")
                st.subheader(f"Times Inscritos ({len(st.session_state.teams)})")
                with st.expander("🗑️ Remover Times"):
                    tn = [t['name'] for t in st.session_state.teams]
                    c_d1, c_d2 = st.columns([3,1])
                    with c_d1: t_rem = st.selectbox("Selecione para excluir:", tn, key="del_ts")
                    with c_d2: 
                        if st.button("Remover"):
                            st.session_state.teams = [t for t in st.session_state.teams if t['name'] != t_rem]
                            st.rerun()

            st.markdown("---")
            if st.button("Iniciar Torneio", type="primary"):
                qtd = len(st.session_state.teams)
                if 6 <= qtd <= 16:
                    st.session_state.phase = 'swiss'
                    generate_swiss_round()
                    save_to_sheets_suico()
                    st.rerun()
                else: st.error(f"É necessário entre 6 e 16 times. Atual: {qtd}")

        elif st.session_state.phase == 'swiss':
            round_idx = len(st.session_state.rounds)
            st.title(f"⚔️ Fase Suíça - Rodada {round_idx}")
            
            current_round = st.session_state.rounds[-1]
            matches = current_round['matches']
            bye_team = current_round['bye']
            
            if bye_team: st.success(f"🎉 **BYE:** O time **{bye_team['name']}** folga nesta rodada e ganha +1 Vitória.")

            tab_jogos, tab_regras = st.tabs(["⚽ Jogos da Rodada", "📜 Regulamento"])
            with tab_regras: st.markdown(REGULAMENTO_TXT)

            with tab_jogos:
                with st.form(key=f"sw_rd_{round_idx}"):
                    matches_data_input = []
                    disabled_score = st.session_state.swiss_asking_penalties

                    for i, match in enumerate(matches):
                        c1, c2, c3, c4 = st.columns([2, 1, 1, 2])
                        home_name = next(t['name'] for t in st.session_state.teams if t['id'] == match['home'])
                        away_name = next(t['name'] for t in st.session_state.teams if t['id'] == match['away'])
                        
                        with c1: st.markdown(f"<h3 style='text-align: right'>{home_name}</h3>", unsafe_allow_html=True)
                        with c2: s1 = st.number_input("Gols", min_value=0, value=None, key=f"h_{round_idx}_{i}", disabled=disabled_score)
                        with c3: s2 = st.number_input("Gols", min_value=0, value=None, key=f"a_{round_idx}_{i}", disabled=disabled_score)
                        with c4: st.markdown(f"<h3>{away_name}</h3>", unsafe_allow_html=True)
                        
                        pen_h, pen_a = 0, 0
                        if st.session_state.swiss_asking_penalties and s1 is not None and s2 is not None and s1 == s2:
                            st.warning("⚠️ Empate! Decisão por pênaltis:")
                            cp1, cp2 = st.columns(2)
                            with cp1: pen_h = st.number_input(f"Pênaltis {home_name}", min_value=0, value=None, key=f"sw_ph_{i}")
                            with cp2: pen_a = st.number_input(f"Pênaltis {away_name}", min_value=0, value=None, key=f"sw_pa_{i}")
                        
                        matches_data_input.append({'match_idx': i, 'home_id': match['home'], 'away_id': match['away'], 'h_g': s1, 'a_g': s2, 'h_p': pen_h, 'a_p': pen_a})
                        
                    btn_label = "Confirmar Classificação" if st.session_state.swiss_asking_penalties else "Conferir Resultados"
                    if st.form_submit_button(btn_label):
                        missing_input = any(m['h_g'] is None or m['a_g'] is None for m in matches_data_input)
                        if missing_input: st.error("Preencha todos os placares.")
                        else:
                            if not st.session_state.swiss_asking_penalties:
                                has_new_draw = any(item['h_g'] == item['a_g'] for item in matches_data_input)
                                if has_new_draw:
                                    st.session_state.swiss_asking_penalties = True
                                    st.rerun()
                                else:
                                    if bye_team: update_team_stats(bye_team['id'], 1, 0, True, True)
                                    for item in matches_data_input:
                                        w_home = item['h_g'] > item['a_g']
                                        w_id = item['home_id'] if w_home else item['away_id']
                                        current_round['matches'][item['match_idx']].update({'winner_id': w_id, 'home_score': item['h_g'], 'away_score': item['a_g']})
                                        update_team_stats(item['home_id'], item['h_g'], item['a_g'], w_home)
                                        update_team_stats(item['away_id'], item['a_g'], item['h_g'], not w_home)
                                    current_round['completed'] = True
                                    save_to_sheets_suico()
                                    if len([t for t in st.session_state.teams if t['status'] == 'Ativo']) <= 1: init_playoffs()
                                    else: generate_swiss_round()
                                    st.rerun()
                            else:
                                valid = True
                                for item in matches_data_input:
                                    if item['h_g'] == item['a_g'] and (item['h_p'] is None or item['a_p'] is None or item['h_p'] == item['a_p']):
                                        st.error("Pênaltis inválidos ou empatados."); valid = False; break
                                if valid:
                                    if bye_team: update_team_stats(bye_team['id'], 1, 0, True, True)
                                    for item in matches_data_input:
                                        hg, ag, hp, ap = item['h_g'], item['a_g'], item['h_p'], item['a_p']
                                        w_home = hg > ag if hg != ag else hp > ap
                                        w_id = item['home_id'] if w_home else item['away_id']
                                        current_round['matches'][item['match_idx']].update({'winner_id': w_id, 'home_score': hg, 'away_score': ag, 'h_pen': hp, 'a_pen': ap})
                                        update_team_stats(item['home_id'], hg, ag, w_home)
                                        update_team_stats(item['away_id'], ag, hg, not w_home)
                                    current_round['completed'] = True
                                    save_to_sheets_suico()
                                    if len([t for t in st.session_state.teams if t['status'] == 'Ativo']) <= 1: init_playoffs()
                                    else: generate_swiss_round()
                                    st.rerun()

        elif st.session_state.phase == 'playoff_gameplay':
            st.title("🔥 Fase Final (Mata-Mata)")
            for idx, r_data in enumerate(st.session_state.playoff_schedule):
                if r_data['completed']:
                    with st.expander(f"✅ {r_data['name']} (Concluído)", expanded=False):
                        for m in r_data['matches']:
                            winner_name = "**" + (m['home']['name'] if m['winner_id'] == m['home']['id'] else m['away']['name']) + "**"
                            pen_txt = f" (Pên: {m['h_pen']} x {m['a_pen']})" if m.get('is_penalties') else ""
                            st.write(f"{m['label']}: {m['home']['name']} {m['h_goals']} x {m['a_goals']} {m['away']['name']}{pen_txt} -> Vencedor: {winner_name}")

            current_round = st.session_state.playoff_schedule[-1]
            round_id = len(st.session_state.playoff_schedule)
            st.markdown(f"### ⚡ Em andamento: {current_round['name']}")
            if current_round['waiting']: st.info(f"🛑 Times aguardando (Byes): **{', '.join([t['name'] for t in current_round['waiting']])}**")
            
            with st.form(key=f"po_form_{round_id}"):
                matches_data_input = []
                disabled_score = st.session_state.playoff_asking_penalties

                for i, match in enumerate(current_round['matches']):
                    st.markdown(f"**{match['label']}**")
                    col1, col2, col3, col4, col5 = st.columns([3, 1, 0.5, 1, 3])
                    with col1: st.markdown(f"<h3 style='text-align: right'>{match['home']['name']}</h3>", unsafe_allow_html=True)
                    with col2: val_h = st.number_input("Gols", min_value=0, value=None, key=f"pg_h_{round_id}_{i}", disabled=disabled_score)
                    with col3: st.markdown("<h3 style='text-align: center'>X</h3>", unsafe_allow_html=True)
                    with col4: val_a = st.number_input("Gols", min_value=0, value=None, key=f"pg_a_{round_id}_{i}", disabled=disabled_score)
                    with col5: st.markdown(f"<h3>{match['away']['name']}</h3>", unsafe_allow_html=True)
                    
                    pen_h, pen_a = 0, 0
                    if st.session_state.playoff_asking_penalties and val_h is not None and val_a is not None and val_h == val_a:
                        st.warning("⚠️ Empate! Insira os pênaltis:")
                        cp1, cp2 = st.columns(2)
                        with cp1: pen_h = st.number_input(f"Pênaltis {match['home']['name']}", min_value=0, value=None, key=f"po_ph_{i}")
                        with cp2: pen_a = st.number_input(f"Pênaltis {match['away']['name']}", min_value=0, value=None, key=f"po_pa_{i}")
                    matches_data_input.append({'match': match, 'h_g': val_h, 'a_g': val_a, 'h_p': pen_h, 'a_p': pen_a})

                btn_label = "Confirmar Classificação" if st.session_state.playoff_asking_penalties else "Conferir Resultados"
                if st.form_submit_button(btn_label):
                    if any(m['h_g'] is None or m['a_g'] is None for m in matches_data_input): st.error("Preencha todos os placares.")
                    else:
                        winners, losers = [], []
                        if not st.session_state.playoff_asking_penalties:
                            has_new_draw = any(item['h_g'] == item['a_g'] for item in matches_data_input)
                            if has_new_draw: st.session_state.playoff_asking_penalties = True; st.rerun()
                            else:
                                for item in matches_data_input:
                                    m = item['match']
                                    m.update({'h_goals': item['h_g'], 'a_goals': item['a_g'], 'is_penalties': False, 'h_pen': 0, 'a_pen': 0})
                                    w = m['home'] if item['h_g'] > item['a_g'] else m['away']
                                    l = m['away'] if item['h_g'] > item['a_g'] else m['home']
                                    m['winner_id'] = w['id']
                                    winners.append(w); losers.append(l)
                                    update_team_stats(m['home']['id'], item['h_g'], item['a_g'], w['id'] == m['home']['id'])
                                    update_team_stats(m['away']['id'], item['a_g'], item['h_g'], w['id'] == m['away']['id'])
                                current_round['completed'] = True
                                advance_playoff_round(winners, current_round['waiting'], losers=losers)
                                st.rerun()
                        else:
                            valid = True
                            for item in matches_data_input:
                                if item['h_g'] == item['a_g'] and (item['h_p'] is None or item['a_p'] is None or item['h_p'] == item['a_p']):
                                    st.error("Pênaltis inválidos."); valid = False; break
                            if valid:
                                for item in matches_data_input:
                                    m = item['match']
                                    m.update({'h_goals': item['h_g'], 'a_goals': item['a_g'], 'h_pen': item['h_p'], 'a_pen': item['a_p']})
                                    m['is_penalties'] = (item['h_g'] == item['a_g'])
                                    w_home = item['h_g'] > item['a_g'] if item['h_g'] != item['a_g'] else item['h_p'] > item['a_p']
                                    w = m['home'] if w_home else m['away']
                                    l = m['away'] if w_home else m['home']
                                    m['winner_id'] = w['id']
                                    winners.append(w); losers.append(l)
                                    update_team_stats(m['home']['id'], item['h_g'], item['a_g'], w['id'] == m['home']['id'])
                                    update_team_stats(m['away']['id'], item['a_g'], item['h_g'], w['id'] == m['away']['id'])
                                current_round['completed'] = True
                                advance_playoff_round(winners, current_round['waiting'], losers=losers)
                                st.rerun()

        elif st.session_state.phase == 'champion':
            st.balloons()
            champ = st.session_state.champion
            vice = st.session_state.vice
            third = st.session_state.third
            
            st.markdown(f"""<div style="text-align: center; padding: 30px;"><h1>🏆 TORNEIO ENCERRADO! 🏆</h1></div>""", unsafe_allow_html=True)
            c1, c2, c3 = st.columns(3)
            with c2: st.markdown(f"""<div style="text-align: center; background-color: #FFD700; padding: 20px; border-radius: 10px; color: black;"><h2>🥇 CAMPEÃO</h2><h1 style="margin:0;">{champ['name']}</h1></div>""", unsafe_allow_html=True)
            with c1: 
                if vice: st.markdown(f"""<div style="text-align: center; background-color: #C0C0C0; padding: 20px; border-radius: 10px; color: black; margin-top: 20px;"><h3>🥈 Vice-Campeão</h3><h2 style="margin:0;">{vice['name']}</h2></div>""", unsafe_allow_html=True)
            with c3: 
                if third: st.markdown(f"""<div style="text-align: center; background-color: #CD7F32; padding: 20px; border-radius: 10px; color: black; margin-top: 20px;"><h3>🥉 3º Lugar</h3><h2 style="margin:0;">{third['name']}</h2></div>""", unsafe_allow_html=True)

            st.divider()
            
            # --- BOTÃO MESTRE: SALVA NO HALL DA FAMA E ENCERRA ---
            if st.button("🏆 ENCERRAR E SALVAR NO HISTÓRICO", type="primary", use_container_width=True):
                h_br = (datetime.utcnow() - timedelta(hours=3)).strftime("%d/%m/%Y %H:%M")
                nome_vice = vice['name'] if vice else "---"
                nome_terc = third['name'] if third else "---"
                nova_h = pd.DataFrame([{'torneio_id': tid, 'formato': 'SUÍÇO', 'campeao': champ['name'], 'vice': nome_vice, 'terceiro': nome_terc, 'data_fim': h_br}])
                
                # Salva no Histórico
                salvar_dados(pd.concat([df_hist, nova_h], ignore_index=True), ABA_HISTORICO)
                
                # Remove o torneio da lista de torneios Ativos na tela inicial
                df_db = df_db[df_db['torneio_id'] != tid]
                salvar_dados(df_db, ABA_JOGOS)
                
                st.session_state.torneio_ativo = None
                st.rerun()

    # ==========================================
    # FLUXO 2: MODO COPA E LIGA (SUPER APP ORIGINAL)
    # ==========================================
    else:
        if menu == "🏟️ Jogos":
            if df_t.empty: st.info("Gere os jogos no Admin.")
            else:
                for f in sorted(df_t['fase'].unique(), key=lambda x: ORDEM_FASES.get(x, 99)):
                    st.subheader(f"📍 {f}")
                    for idx, r in df_t[df_t['fase'] == f].iterrows():
                        if r['fase'] == "Setup": continue # Ignora a linha de registro
                        with st.container(border=True):
                            c1, c2, c3 = st.columns([2,1,2])
                            p_txt = f"{r['gols_a']} x {r['gols_b']}" if r['modo_copa']=="Só Ida" or fmt=="LIGA" else f"({r['ida_a']}) {r['volta_a']} x {r['volta_b']} ({r['ida_b']})"
                            if is_done(r['finalizado']) and (int(r['pen_a'])+int(r['pen_b'])>0): p_txt += f" (P: {r['pen_a']}x{r['pen_b']})"
                            c1.markdown(f"<p style='text-align:right'><b>{r['a']}</b></p>", unsafe_allow_html=True)
                            c2.markdown(f"<div style='text-align:center; background:#eee; padding:5px; color:black;'>{p_txt}</div>", unsafe_allow_html=True)
                            c3.markdown(f"<p style='text-align:left'><b>{r['b']}</b></p>", unsafe_allow_html=True)
                            
                            if is_admin:
                                with st.expander("✎ Editar"):
                                    with st.form(f"f_{idx}"):
                                        ca, cb = st.columns(2)
                                        if fmt=="LIGA" or r['modo_copa']=="Só Ida":
                                            ga, gb = ca.number_input("Gols A",0,99,int(r['gols_a'])), cb.number_input("Gols B",0,99,int(r['gols_b']))
                                            res, sa, sb = [ga, gb, ga, gb, 0, 0], ga, gb
                                        else:
                                            ia, ib = ca.number_input("Ida A",0,99,int(r['ida_a'])), cb.number_input("Ida B",0,99,int(r['ida_b']))
                                            va, vb = ca.number_input("Volta A",0,99,int(r['volta_a'])), cb.number_input("Volta B",0,99,int(r['volta_b']))
                                            res, sa, sb = [ia+va, ib+vb, ia, ib, va, vb], (ia+va), (ib+vb)
                                        pa, pb = 0, 0
                                        if fmt == "COPA" and sa == sb and r['a'] != "BYE" and r['b'] != "BYE":
                                            pa, pb = st.columns(2)[0].number_input("Pen A",0,99,int(r['pen_a'])), st.columns(2)[1].number_input("Pen B",0,99,int(r['pen_b']))
                                        
                                        if st.form_submit_button("Salvar"):
                                            df_db.loc[idx, ['gols_a','gols_b','ida_a','ida_b','volta_a','volta_b','pen_a','pen_b','finalizado']] = res + [pa, pb, "SIM"]
                                            if fmt == "COPA":
                                                df_fase = df_db[(df_db['torneio_id'] == tid) & (df_db['fase'] == r['fase'])]
                                                if all(df_fase['finalizado'].apply(is_done)):
                                                    v, p = [], []
                                                    for _, rf in df_fase.iterrows():
                                                        vw, pl = obter_vencedor_perdedor(rf)
                                                        if vw: v.append(vw); p.append(pl)
                                                    novos = []
                                                    if r['fase'] == "Semifinal" and len(v)>=2:
                                                        novos.append({'torneio_id':tid,'formato':'COPA','fase':'Final','a':v[0],'b':v[1],'modo_copa':'Só Ida','finalizado':'NÃO'})
                                                        novos.append({'torneio_id':tid,'formato':'COPA','fase':'3º Lugar','a':p[0],'b':p[1],'modo_copa':'Só Ida','finalizado':'NÃO'})
                                                    elif r['fase'] == "Quartas" and len(v)>=4:
                                                        for i in range(0, len(v), 2): novos.append({'torneio_id':tid,'formato':'COPA','fase':'Semifinal','a':v[i],'b':v[i+1],'modo_copa':r['modo_copa'],'finalizado':'NÃO'})
                                                    if novos: df_db = pd.concat([df_db, pd.DataFrame(novos)], ignore_index=True)
                                            salvar_dados(df_db, ABA_JOGOS); st.rerun()

        elif menu == "📊 Consulta":
            if fmt == "LIGA":
                times = pd.concat([df_t['a'], df_t['b']]).unique()
                stats = {t: {'P':0,'J':0,'V':0,'E':0,'D':0,'GP':0,'GC':0,'SG':0} for t in times if pd.notna(t) and t != "BYE" and t != "Setup"}
                for _, r in df_t[df_t['finalizado'] == 'SIM'].iterrows():
                    t1, t2, g1, g2 = r['a'], r['b'], int(r['gols_a']), int(r['gols_b'])
                    if t1 in stats and t2 in stats:
                        stats[t1]['J']+=1; stats[t2]['J']+=1; stats[t1]['GP']+=g1; stats[t1]['GC']+=g2; stats[t2]['GP']+=g2; stats[t2]['GC']+=g1
                        if g1 > g2: stats[t1]['P']+=3; stats[t1]['V']+=1; stats[t2]['D']+=1
                        elif g2 > g1: stats[t2]['P']+=3; stats[t2]['V']+=1; stats[t1]['D']+=1
                        else: stats[t1]['P']+=1; stats[t2]['P']+=1; stats[t1]['E']+=1; stats[t2]['E']+=1
                        stats[t1]['SG'] = stats[t1]['GP'] - stats[t1]['GC']; stats[t2]['SG'] = stats[t2]['GP'] - stats[t2]['GC']
                st.table(pd.DataFrame.from_dict(stats, orient='index').sort_values(by=['P','V','SG','GP'], ascending=False))
            else:
                f_p = ["Oitavas", "Quartas", "Semifinal", "3º Lugar", "Final"]
                cols = st.columns(len(f_p))
                for i, fn in enumerate(f_p):
                    with cols[i]:
                        st.markdown(f"**{fn.upper()}**")
                        for _, r in df_t[df_t['fase'] == fn].iterrows():
                            vw, _ = obter_vencedor_perdedor(r)
                            b_c = "#F4D03F" if is_done(r['finalizado']) else "#ccc"
                            st.markdown(f'<div style="border:2px solid {b_c}; padding:5px; border-radius:5px; background:white; color:black; margin-bottom:5px; text-align:center; font-size:11px;">{r["a"]} x {r["b"]}<br><b>V: {vw if vw else "-"}</b></div>', unsafe_allow_html=True)

        elif menu == "⚙️ Admin" and is_admin:
            if len(df_t) <= 1: # Só tem a linha de Setup
                txt = st.text_area("Times (um por linha)")
                if st.button("GERAR"):
                    times = [x.strip() for x in txt.split('\n') if x.strip()]
                    if len(times)>=2:
                        jogos = []
                        if fmt == "LIGA":
                            for a, b in combinations(times, 2): jogos.append({'torneio_id':tid,'formato':'LIGA','fase':'Liga','a':a,'b':b,'modo_copa':'Só Ida','finalizado':'NÃO'})
                        else:
                            f_ini = "Semifinal" if len(times)<=4 else "Quartas"
                            for i in range(0, len(times), 2):
                                t1, t2 = times[i], (times[i+1] if i+1 < len(times) else "BYE")
                                jogos.append({'torneio_id':tid,'formato':'COPA','fase':f_ini,'a':t1,'b':t2,'modo_copa':'Só Ida','finalizado':'NÃO'})
                        
                        # Remove a linha de Setup antes de gerar os jogos
                        df_db = df_db[~((df_db['torneio_id'] == tid) & (df_db['fase'] == 'Setup'))]
                        salvar_dados(pd.concat([df_db, pd.DataFrame(jogos)], ignore_index=True), ABA_JOGOS); st.rerun()
            else:
                if st.button("🏆 ENCERRAR (HALL DA FAMA)"):
                    h_br = (datetime.utcnow() - timedelta(hours=3)).strftime("%d/%m/%Y %H:%M")
                    c, v, t = "---", "---", "---"
                    if fmt == "COPA":
                        fin, t3 = df_t[df_t['fase'] == 'Final'], df_t[df_t['fase'] == '3º Lugar']
                        if not fin.empty: c, v = obter_vencedor_perdedor(fin.iloc[0])
                        if not t3.empty: t, _ = obter_vencedor_perdedor(t3.iloc[0])
                    else: # LIGA
                        tm = pd.concat([df_t['a'], df_t['b']]).unique()
                        stt = {tmx: {'P':0,'V':0,'SG':0,'GP':0} for tmx in tm if pd.notna(tmx) and tmx != "BYE"}
                        for _, r in df_t[df_t['finalizado'] == 'SIM'].iterrows():
                            t1, t2, g1, g2 = r['a'], r['b'], int(r['gols_a']), int(r['gols_b'])
                            if t1 in stt and t2 in stt:
                                stt[t1]['GP']+=g1; stt[t2]['GP']+=g2
                                if g1 > g2: stt[t1]['P']+=3; stt[t1]['V']+=1
                                elif g2 > g1: stt[t2]['P']+=3; stt[t2]['V']+=1
                                else: stt[t1]['P']+=1; stt[t2]['P']+=1
                                stt[t1]['SG'] = stt[t1]['GP'] - g2; stt[t2]['SG'] = stt[t2]['GP'] - g1
                        res_l = pd.DataFrame.from_dict(stt, orient='index').sort_values(by=['P','V','SG','GP'], ascending=False).index.tolist()
                        if len(res_l) >= 1: c = res_l[0]
                        if len(res_l) >= 2: v = res_l[1]
                        if len(res_l) >= 3: t = res_l[2]
                    
                    nova_h = pd.DataFrame([{'torneio_id':tid,'formato':fmt,'campeao':c,'vice':v,'terceiro':t,'data_fim':h_br}])
                    salvar_dados(pd.concat([df_hist, nova_h], ignore_index=True), ABA_HISTORICO)
                    
                    df_db = df_db[df_db['torneio_id'] != tid]
                    salvar_dados(df_db, ABA_JOGOS)
                    st.session_state.torneio_ativo = None
                    st.rerun()
                
                if st.button("🚨 EXCLUIR TORNEIO (SEM SALVAR)"):
                    salvar_dados(df_db[df_db['torneio_id'] != tid], ABA_JOGOS); st.session_state.torneio_ativo = None; st.rerun()
