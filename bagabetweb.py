import streamlit as st
import pandas as pd
from itertools import combinations
from streamlit_gsheets import GSheetsConnection
from datetime import datetime, timedelta
import random
import io
import json

# --- CONFIGURAÇÃO DA PÁGINA ---
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

# --- CONEXÃO GOOGLE SHEETS ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    SHEET_ENABLED = True
except Exception as e:
    st.error(f"Erro de Conexão com Sheets: {e}")
    SHEET_ENABLED = False

ABA_JOGOS = "Página1" 
ABA_HISTORICO = "Historico"
ABA_SUICO = "suico"
COLUNAS = ['torneio_id', 'formato', 'fase', 'a', 'b', 'finalizado', 'gols_a', 'gols_b', 'ida_a', 'ida_b', 'volta_a', 'volta_b', 'pen_a', 'pen_b', 'modo_copa']

ORDEM_FASES = {"Oitavas": 1, "Quartas": 2, "Semifinal": 3, "3º Lugar": 4, "Final": 5, "Turno Único": 6, "Turno": 7, "Returno": 8, "Liga": 9, "Amistoso": 10}

# --- TEXTO DO REGULAMENTO SUÍÇO ---
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

**4. Partidas**
* **Empate:** Não permitido. Em caso de empate no tempo normal, disputa-se pênaltis.
* **Pontuação:** Vitória (tempo normal ou pênaltis) = 1 ponto.
* **Saldo:** Conta apenas o placar do tempo normal.

**5. Fase Final (Mata-Mata)**
* Os 8 melhores classificados avançam.
* Disputa de Campeão, Vice e 3º Lugar.
"""

# --- GESTÃO DE ESTADO GERAL E SUÍÇO ---
if 'torneio_ativo' not in st.session_state: st.session_state.torneio_ativo = None
if 'temp_fmt' not in st.session_state: st.session_state.temp_fmt = "COPA"

keys_suico = {
    'teams': [], 'rounds': [], 'phase': 'registration', 'playoff_schedule': [], 
    'champion': None, 'vice': None, 'third': None, 
    'swiss_asking_penalties': False, 'playoff_asking_penalties': False
}
for key, value in keys_suico.items():
    if key not in st.session_state: st.session_state[key] = value

# ==========================================
# FUNÇÕES DE BANCO DE DADOS (SUPER APP)
# ==========================================
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
    # 1. Remove linhas realmente vazias
    df = df.dropna(subset=['torneio_id'])
    
    # 2. Transforma qualquer erro de valor nulo em texto vazio (evita o erro do Sheets)
    df = df.fillna("")
    
    # 3. Envia para o Google
    conn.update(worksheet=aba, data=df)
    
    # 4. Limpa o cache para o app ler o dado novo na hora
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

# ==========================================
# FUNÇÕES DO MODO SUÍÇO
# ==========================================
def save_to_sheets_suico():
    if not SHEET_ENABLED or not st.session_state.torneio_ativo: return
    try:
        # Cria o "Cartucho de Memória" (Save State) com todas as variáveis
        pacote_memoria = {
            'teams': st.session_state.teams,
            'rounds': st.session_state.rounds,
            'phase': st.session_state.phase,
            'playoff_schedule': st.session_state.playoff_schedule,
            'champion': st.session_state.champion,
            'vice': st.session_state.vice,
            'third': st.session_state.third
        }
        state_json = json.dumps(pacote_memoria)
        df_current = pd.DataFrame([{'tournament_name': st.session_state.torneio_ativo, 'state_data': state_json}])

        try:
            existing_data = conn.read(worksheet=ABA_SUICO, ttl=0)
            if existing_data is not None and not existing_data.empty and 'tournament_name' in existing_data.columns:
                other_tournaments = existing_data[existing_data['tournament_name'] != st.session_state.torneio_ativo]
                df_final = pd.concat([other_tournaments, df_current], ignore_index=True)
            else:
                df_final = df_current
        except:
            df_final = df_current

        conn.update(worksheet=ABA_SUICO, data=df_final)
    except Exception as e:
        st.error(f"⚠️ Erro ao salvar Suíço: {e}")

def load_from_sheets_suico(t_name):
    if not SHEET_ENABLED: return False
    try:
        existing_data = conn.read(worksheet=ABA_SUICO, ttl=0)
        if existing_data is not None and not existing_data.empty and 'tournament_name' in existing_data.columns:
            t_data = existing_data[existing_data['tournament_name'] == t_name]
            if not t_data.empty:
                # Descompacta o cartucho de memória
                state_json = t_data.iloc[0]['state_data']
                pacote_memoria = json.loads(state_json)
                for k, v in pacote_memoria.items():
                    st.session_state[k] = v
                return True
    except Exception as e:
        pass
    return False
    
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
            
            if is_winner:
                team['wins'] += 1
            else:
                team['losses'] += 1
            
            if is_bye:
                team['received_bye'] = True
            
            if st.session_state.phase == 'swiss':
                if team['wins'] >= 3:
                    team['status'] = 'Classificado'
                elif team['losses'] >= 3:
                    team['status'] = 'Eliminado'
            found = True
            break
    if not found:
        st.error(f"Erro Crítico: ID {team_id} não encontrado.")

def convert_df_to_csv(df):
    return df.to_csv(index=False).encode('utf-8')

def generate_export_data():
    if st.session_state.teams:
        sorted_teams = get_sorted_rankings(st.session_state.teams, for_pairing=False)
        rank_data = []
        for t in sorted_teams:
            rank_data.append({
                'Time': t['name'],
                'Vitorias': t['wins'],
                'Derrotas': t['losses'],
                'Saldo': t['goal_diff'],
                'Gols Pro': t['goals_for'],
                'Status': t['status'],
                'Recebeu Bye': 'Sim' if t['received_bye'] else 'Não'
            })
        df_rank = pd.DataFrame(rank_data)
    else:
        df_rank = pd.DataFrame()

    match_history = []
    
    for i, r in enumerate(st.session_state.rounds):
        if r.get('completed'): 
            if r['bye']:
                match_history.append({
                    'Fase': 'Suíça', 'Rodada': i+1, 
                    'Mandante': r['bye']['name'], 'Placar M': 1, 'Placar V': 0, 'Visitante': 'BYE (Folga)',
                    'Vencedor': r['bye']['name'], 'Notas': 'Vitória automática por Bye'
                })
            
            for m in r['matches']:
                h_name = next((t['name'] for t in st.session_state.teams if t['id'] == m['home']), "Time A")
                a_name = next((t['name'] for t in st.session_state.teams if t['id'] == m['away']), "Time B")
                winner_name = "Empate"
                if 'winner_id' in m:
                    winner_name = h_name if m['winner_id'] == m['home'] else a_name
                note = ""
                if m['home_score'] == m['away_score'] and 'h_pen' in m:
                      note = f"Pênaltis: {m['h_pen']} x {m['a_pen']}"

                match_history.append({
                    'Fase': 'Suíça', 'Rodada': i+1,
                    'Mandante': h_name, 'Placar M': m['home_score'], 
                    'Placar V': m['away_score'], 'Visitante': a_name,
                    'Vencedor': winner_name, 'Notas': note
                })

    for r in st.session_state.playoff_schedule:
        if r['completed']:
            for m in r['matches']:
                h_name = m['home']['name']
                a_name = m['away']['name']
                winner_name = h_name if m.get('winner_id') == m['home']['id'] else a_name
                note = ""
                if m.get('is_penalties'):
                    note = f"Pênaltis: {m['h_pen']} x {m['a_pen']}"
                label_fase = r['name']
                if label_fase == "Finais":
                    if m['id'] == 'FINAL': label_fase = "Grande Final"
                    if m['id'] == '3RD': label_fase = "Disputa 3º Lugar"

                match_history.append({
                    'Fase': 'Mata-Mata', 'Rodada': label_fase,
                    'Mandante': h_name, 'Placar M': m['h_goals'],
                    'Placar V': m['a_goals'], 'Visitante': a_name,
                    'Vencedor': winner_name, 'Notas': note
                })
                
    df_matches = pd.DataFrame(match_history)
    return df_rank, df_matches

def generate_swiss_round():
    st.session_state.swiss_asking_penalties = False 
    
    active_teams = [t for t in st.session_state.teams if t['status'] == 'Ativo' and t['losses'] < 3]
    bye_team = None
    
    if len(active_teams) % 2 != 0:
        eligible_for_bye = [t for t in active_teams if not t['received_bye']]
        candidates = []
        
        if not st.session_state.rounds:
            candidates = eligible_for_bye
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
        if not opponent:
            opponent = ranked_pool.pop(0)
            
        matches.append({
            'home': home['id'], 'away': opponent['id'], 
            'home_score': 0, 'away_score': 0
        })
        home['history'].append(opponent['id'])
        opponent['history'].append(home['id'])

    st.session_state.rounds.append({'matches': matches, 'bye': bye_team, 'completed': False})

def init_playoffs():
    qualified = [t for t in st.session_state.teams if t['status'] == 'Classificado']
    seeds = get_sorted_rankings(qualified, for_pairing=False) 
    
    if len(seeds) > 8:
        st.toast(f"⚠️ Atenção: {len(seeds)} times classificados. Apenas os 8 melhores avançam.")
        seeds = seeds[:8]
    
    num_q = len(seeds)
    current_matches = []
    waiting_teams = [] 
    round_name = ""

    if num_q == 3:
        round_name = "Semifinal Única"
        waiting_teams = [seeds[0]]
        current_matches = [{'id': 'S1', 'home': seeds[1], 'away': seeds[2], 'label': 'Semifinal'}]
    elif num_q == 4:
        round_name = "Semifinais"
        current_matches = [
            {'id': 'S1', 'home': seeds[0], 'away': seeds[3], 'label': 'Semi 1'},
            {'id': 'S2', 'home': seeds[1], 'away': seeds[2], 'label': 'Semi 2'}
        ]
    elif num_q == 5:
        round_name = "Wildcard (Repescagem)"
        waiting_teams = [seeds[0], seeds[1], seeds[2]] 
        current_matches = [{'id': 'WC', 'home': seeds[3], 'away': seeds[4], 'label': 'Repescagem'}]
    elif num_q == 6:
        round_name = "Quartas de Final"
        waiting_teams = [seeds[0], seeds[1]]
        current_matches = [
            {'id': 'QFA', 'home': seeds[3], 'away': seeds[4], 'label': 'Quartas A'},
            {'id': 'QFB', 'home': seeds[2], 'away': seeds[5], 'label': 'Quartas B'}
        ]
    elif num_q == 7:
        round_name = "Quartas de Final"
        waiting_teams = [seeds[0]]
        current_matches = [
            {'id': 'QFA', 'home': seeds[3], 'away': seeds[4], 'label': 'Quartas A'},
            {'id': 'QFB', 'home': seeds[2], 'away': seeds[5], 'label': 'Quartas B'},
            {'id': 'QFC', 'home': seeds[1], 'away': seeds[6], 'label': 'Quartas C'}
        ]
    elif num_q >= 8:
        seeds = seeds[:8]
        round_name = "Quartas de Final"
        current_matches = [
            {'id': 'Q1', 'home': seeds[0], 'away': seeds[7], 'label': 'Quartas 1'},
            {'id': 'Q2', 'home': seeds[1], 'away': seeds[6], 'label': 'Quartas 2'},
            {'id': 'Q3', 'home': seeds[2], 'away': seeds[5], 'label': 'Quartas 3'},
            {'id': 'Q4', 'home': seeds[3], 'away': seeds[4], 'label': 'Quartas 4'}
        ]
    
    if num_q < 3:
         st.error(f"Erro Crítico: Apenas {num_q} classificados. O sistema precisa de no mínimo 3.")
         return

    for m in current_matches:
        m['h_goals'] = 0
        m['a_goals'] = 0
        m['h_pen'] = 0
        m['a_pen'] = 0

    round_data = {
        'name': round_name,
        'matches': current_matches,
        'waiting': waiting_teams,
        'completed': False
    }
    
    st.session_state.playoff_schedule = [round_data]
    st.session_state.phase = 'playoff_gameplay'
    st.session_state.playoff_asking_penalties = False
    save_to_sheets_suico()

def advance_playoff_round(results, waiting_teams, losers=None):
    st.session_state.playoff_asking_penalties = False 
    
    last_round = st.session_state.playoff_schedule[-1]
    last_round_name = last_round['name']

    # Lógica Universal de Seed corrigida
    waiting_sorted = get_sorted_rankings(waiting_teams, for_pairing=False)
    results_sorted = get_sorted_rankings(results, for_pairing=False)
    
    if waiting_teams:
        pool = waiting_sorted + results_sorted
    else:
        pool = get_sorted_rankings(results, for_pairing=False)

    count = len(pool)
    next_matches = []
    next_round_name = ""
    
    if last_round_name == "Finais":
        champion = None
        vice = None
        third = None
        for m in last_round['matches']:
            winner_id = m.get('winner_id')
            winner_obj = m['home'] if winner_id == m['home']['id'] else m['away']
            loser_obj = m['away'] if winner_id == m['home']['id'] else m['home']

            if m['id'] == 'FINAL':
                champion = winner_obj
                vice = loser_obj
            elif m['id'] == '3RD':
                third = winner_obj
                
        if champion:
            st.session_state.champion = champion
            st.session_state.vice = vice 
            st.session_state.third = third 
            st.session_state.phase = 'champion'
            save_to_sheets_suico()
            return

    if last_round_name == "Semifinais" and losers and len(losers) == 2:
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
        next_matches = [
            {'id': 'S1', 'home': pool[0], 'away': pool[3], 'label': 'Semi 1'},
            {'id': 'S2', 'home': pool[1], 'away': pool[2], 'label': 'Semi 2'}
        ]
    else:
        next_round_name = "Rodada Eliminatória"
        while len(pool) >= 2:
            home = pool.pop(0)
            away = pool.pop(-1)
            next_matches.append({'id': 'GEN', 'home': home, 'away': away, 'label': 'Jogo'})
            
    if not next_matches and count == 1:
        st.session_state.champion = pool[0]
        st.session_state.phase = 'champion'
        save_to_sheets_suico()
        return

    for m in next_matches:
        m['h_goals'] = 0
        m['a_goals'] = 0
        m['h_pen'] = 0
        m['a_pen'] = 0

    new_round_data = {
        'name': next_round_name,
        'matches': next_matches,
        'waiting': [],
        'completed': False
    }
    st.session_state.playoff_schedule.append(new_round_data)
    save_to_sheets_suico()

def add_team_callback():
    new_team = st.session_state.team_input
    if new_team and new_team not in [t['name'] for t in st.session_state.teams]:
        existing_ids = [t['id'] for t in st.session_state.teams]
        new_id = (max(existing_ids) + 1) if existing_ids else 1
        t_obj = {'id': new_id, 'name': new_team, 'wins': 0, 'losses': 0, 'goals_for': 0, 'goal_diff': 0, 'received_bye': False, 'history': [], 'status': 'Ativo'}
        st.session_state.teams.append(t_obj)
        st.session_state.team_input = "" 
    elif not new_team:
        st.warning("Digite um nome.")
    else:
        st.error("Time já existe.")

def bulk_import_callback():
    text = st.session_state.bulk_input
    if text:
        names = [n.strip() for n in text.split('\n') if n.strip()]
        count = 0
        for name in names:
            if name not in [t['name'] for t in st.session_state.teams]:
                existing_ids = [t['id'] for t in st.session_state.teams]
                new_id = (max(existing_ids) + 1) if existing_ids else 1
                t_obj = {'id': new_id, 'name': name, 'wins': 0, 'losses': 0, 'goals_for': 0, 'goal_diff': 0, 'received_bye': False, 'history': [], 'status': 'Ativo'}
                st.session_state.teams.append(t_obj)
                count += 1
        st.success(f"{count} times importados!")
        st.session_state.bulk_input = "" 

# ==========================================
# ROTEAMENTO PRINCIPAL
# ==========================================

df_db = carregar_dados(ABA_JOGOS)
df_hist = carregar_dados(ABA_HISTORICO)

if st.session_state.torneio_ativo is None:
    st.title("⚽ BAGA GESTOR PRO")
    
    df_hist = carregar_dados(ABA_HISTORICO)
    
    if not df_hist.empty:
        st.subheader("🏆 Histórico de Competições")
        
        # Criamos abas para não misturar Amistoso com Torneio
        tab_copas, tab_amis = st.tabs(["🏅 Copas e Ligas", "🤝 Amistosos"])
        
        with tab_copas:
            # Filtra tudo que NÃO é amistoso
            df_c = df_hist[df_hist['formato'] != 'AMISTOSO'].copy()
            if not df_c.empty:
                # Mostra colunas padrão de torneio
                exibir_c = df_c[['campeao', 'vice', 'formato', 'data_fim']].sort_index(ascending=False)
                exibir_c.columns = ['🏆 Campeão', '🥈 Vice', 'Formato', '📅 Data/Hora']
                st.dataframe(exibir_c, use_container_width=True, hide_index=True)
            else:
                st.info("Nenhum torneio registrado.")

        with tab_amis:
            # Filtra apenas os AMISTOSOS
            df_a = df_hist[df_hist['formato'] == 'AMISTOSO'].copy()
            if not df_a.empty:
                # Aqui a mágica: Mostra apenas o Resultado (guardado na coluna campeao) e a Data
                exibir_a = df_a[['campeao', 'data_fim']].sort_index(ascending=False)
                exibir_a.columns = ['⚽ Resultado do Amistoso', '📅 Data/Hora']
                st.dataframe(exibir_a, use_container_width=True, hide_index=True)
            else:
                st.info("Nenhum amistoso registrado.")
                
    torneios = df_db['torneio_id'].unique() if not df_db.empty else []
    if len(torneios) > 0:
        st.subheader("📂 Abrir Torneio")
        cols = st.columns(3)
        for i, t in enumerate(torneios):
            formato_salvo = df_db[df_db['torneio_id'] == t]['formato'].iloc[0]
            if cols[i%3].button(f"🏆 {t} ({formato_salvo})", key=f"t_{t}", use_container_width=True):
                st.session_state.torneio_ativo = t
                if formato_salvo == "SUÍÇO":
                    for key in keys_suico: st.session_state[key] = keys_suico[key] # Zera a tela antes de injetar
                    load_from_sheets_suico(t)
                st.rerun()

    st.divider()
    st.subheader("🆕 Criar Novo Torneio")
    
    n = st.text_input("Nome do Torneio", placeholder="Ex: Copa dos Campeões")
    
    st.markdown("##### 🎮 Escolha o Formato:")
    
    # Criamos 4 colunas para os blocos (botões grandes com ícones)
    c1, c2, c3, c4 = st.columns(4)
    
    with c1:
        if st.button("🏆\n\nMODO COPA", use_container_width=True, type="primary" if st.session_state.temp_fmt == "COPA" else "secondary"):
            st.session_state.temp_fmt = "COPA"
            st.rerun()
    with c2:
        if st.button("📊\n\nMODO LIGA", use_container_width=True, type="primary" if st.session_state.temp_fmt == "LIGA" else "secondary"):
            st.session_state.temp_fmt = "LIGA"
            st.rerun()
    with c3:
        if st.button("⚔️\n\nMODO SUÍÇO", use_container_width=True, type="primary" if st.session_state.temp_fmt == "SUÍÇO" else "secondary"):
            st.session_state.temp_fmt = "SUÍÇO"
            st.rerun()
    with c4:
        if st.button("🤝\n\nAMISTOSO", use_container_width=True, type="primary" if st.session_state.temp_fmt == "AMISTOSO" else "secondary"):
            st.session_state.temp_fmt = "AMISTOSO"
            st.rerun()

    # Linha final com o modo de disputa (Ida/Volta) e o Botão de Criar
    st.markdown("<br>", unsafe_allow_html=True)
    c_modo, c_btn = st.columns([1, 2])
    
    opcoes_modo = ["Só Ida", "Ida e Volta"] if st.session_state.temp_fmt in ["COPA", "LIGA", "AMISTOSO"] else ["Só Ida"]
    with c_modo:
        m = st.selectbox("Modo de Disputa", opcoes_modo)
        
    with c_btn:
        st.markdown("<br>", unsafe_allow_html=True) # Espaçamento invisível para alinhar o botão com o selectbox
        if st.button("✅ CONFIRMAR E CRIAR", type="primary", use_container_width=True):
            if n: 
                if st.session_state.temp_fmt == "SUÍÇO":
                    for key in keys_suico: st.session_state[key] = keys_suico[key]
                
                novo_t = pd.DataFrame([{'torneio_id': n, 'formato': st.session_state.temp_fmt, 'fase': 'Setup', 'finalizado': 'NÃO', 'modo_copa': m}])
                salvar_dados(pd.concat([df_db, novo_t], ignore_index=True), ABA_JOGOS)
                
                st.session_state.torneio_ativo = n
                st.rerun()
            else:
                st.warning("⚠️ Por favor, digite um nome para o torneio!")

else:
    tid = st.session_state.torneio_ativo
    df_t = df_db[df_db['torneio_id'] == tid].copy()
    fmt = df_t['formato'].iloc[0] if not df_t.empty else st.session_state.temp_fmt
    modo_atual = df_t['modo_copa'].iloc[0] if not df_t.empty and 'modo_copa' in df_t.columns and pd.notna(df_t['modo_copa'].iloc[0]) else "Só Ida"
    
    with st.sidebar:
        st.header(f"🏆 {tid}")
        
        if fmt == "SUÍÇO":
            if st.button("🏠 Voltar ao Menu Inicial"):
                st.session_state.torneio_ativo = None
                st.rerun()
            
            st.markdown("---")
            st.header("📊 Classificação Geral")
            if st.session_state.teams:
                sorted_teams = get_sorted_rankings(st.session_state.teams, for_pairing=False)
                
                current_bye_id = None
                if st.session_state.phase == 'swiss' and st.session_state.rounds:
                    curr = st.session_state.rounds[-1]
                    if curr.get('bye') and not curr.get('completed'):
                        current_bye_id = curr['bye']['id']

                html_rows = ""
                for t in sorted_teams:
                    if t['status'] == 'Classificado': status_icon = "🟢"
                    elif t['status'] == 'Eliminado': status_icon = "🔴"
                    else: status_icon = "⚪"

                    name_display = t['name']
                    is_current_bye = (current_bye_id and t['id'] == current_bye_id)
                    if is_current_bye:
                        name_display = f"<b>{t['name']} (F)</b>"

                    bye_disp = 'Sim' if (t['received_bye'] or is_current_bye) else '-'
                    goals_against = t['goals_for'] - t['goal_diff']
                    rec = f"{t['wins']}-{t['losses']}"

                    html_rows += f"<tr><td>{status_icon}</td><td class='text-left'>{name_display}</td><td>{rec}</td><td>{bye_disp}</td><td>{t['goals_for']}</td><td>{goals_against}</td><td>{t['goal_diff']}</td></tr>"

                table_html = f"""
                <table class="compact-table">
                    <thead>
                        <tr>
                            <th title="Status">St</th>
                            <th class="text-left">Time</th>
                            <th>V-D</th>
                            <th>Bye</th>
                            <th title="Gols Pró">GP</th>
                            <th title="Gols Contra">GC</th>
                            <th title="Saldo de Gols">SG</th>
                        </tr>
                    </thead>
                    <tbody>
                        {html_rows}
                    </tbody>
                </table>
                """
                st.markdown(table_html, unsafe_allow_html=True)
                st.caption("GP: Pró | GC: Contra | SG: Saldo | (F): Folga na rodada")

            # --- NOVO BLOCO: HISTÓRICO DE TODOS OS JOGOS ---
            st.markdown("---")
            st.header("📜 Histórico de Jogos")
            if st.session_state.rounds or st.session_state.playoff_schedule:
                with st.expander("Ver todas as partidas", expanded=False):
                    # Histórico da Fase Suíça
                    if st.session_state.rounds:
                        st.markdown("#### 📌 Fase Suíça")
                        for i, r_data in enumerate(st.session_state.rounds):
                            if r_data.get('completed'):
                                st.markdown(f"**Rodada {i+1}**")
                                if r_data.get('bye'):
                                    st.write(f"🎉 *Folga: {r_data['bye']['name']}*")
                                for m in r_data['matches']:
                                    h_name = next((t['name'] for t in st.session_state.teams if t['id'] == m['home']), "Time A")
                                    a_name = next((t['name'] for t in st.session_state.teams if t['id'] == m['away']), "Time B")
                                    pen_txt = f" (P: {m['h_pen']}x{m['a_pen']})" if 'h_pen' in m and m['h_pen'] is not None and (m['h_pen'] > 0 or m['a_pen'] > 0) else ""
                                    st.write(f"⚽ {h_name} **{m['home_score']} x {m['away_score']}** {a_name}{pen_txt}")
                                st.divider()
                    
                    # Histórico do Mata-Mata
                    if st.session_state.playoff_schedule:
                        st.markdown("#### 🔥 Fase Final")
                        for r_data in st.session_state.playoff_schedule:
                            if r_data.get('completed'):
                                st.markdown(f"**{r_data['name']}**")
                                for m in r_data['matches']:
                                    h_name = m['home']['name']
                                    a_name = m['away']['name']
                                    pen_txt = f" (P: {m['h_pen']}x{m['a_pen']})" if m.get('is_penalties') else ""
                                    st.write(f"⚽ {h_name} **{m['h_goals']} x {m['a_goals']}** {a_name}{pen_txt}")
                                st.divider()
            else:
                st.info("Nenhum jogo finalizado ainda.")
            
            st.markdown("---")
            st.header("💾 Exportar Dados")
            if st.session_state.teams:
                df_r, df_m = generate_export_data()
                csv_rank = convert_df_to_csv(df_r)
                st.download_button("📥 Baixar Classificação (CSV)", csv_rank, 'classificacao_torneio.csv', 'text/csv')
                if not df_m.empty:
                    csv_matches = convert_df_to_csv(df_m)
                    st.download_button("📥 Baixar Histórico de Jogos (CSV)", csv_matches, 'historico_partidas.csv', 'text/csv')

        else:
            # Cria a variável de controle solta, sem travar no widget
            if 'aba_atual' not in st.session_state: st.session_state.aba_atual = "🏟️ Jogos"
            
            opcoes_menu = ["🏟️ Jogos", "📊 Consulta", "⚙️ Admin"]
            idx_menu = opcoes_menu.index(st.session_state.aba_atual) if st.session_state.aba_atual in opcoes_menu else 0
            
            menu = st.radio("Menu", opcoes_menu, index=idx_menu)
            st.session_state.aba_atual = menu # Atualiza a escolha naturalmente
            
            is_admin = (st.text_input("Senha Admin", type="password") == "1234")
            if st.button("🏠 Voltar ao Menu Inicial"): 
                st.session_state.torneio_ativo = None
                st.rerun()

    # ==========================================
    # FLUXO SUÍÇO
    # ==========================================
    if fmt == "SUÍÇO":
        if st.session_state.phase == 'registration':
            st.title("🏆 Inscrição de Times")
            
            c1, c2 = st.columns([3,1])
            with c1: st.text_input("Nome do Time", key="team_input")
            with c2: st.button("Adicionar", on_click=add_team_callback)

            with st.expander("📝 Importar em Lote"):
                st.text_area("Cole a lista de nomes (um por linha):", key="bulk_input")
                st.button("Importar Lista", on_click=bulk_import_callback)

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
                else:
                    st.error(f"É necessário entre 6 e 16 times. Atual: {qtd}")

        elif st.session_state.phase == 'swiss':
            round_idx = len(st.session_state.rounds)
            st.title(f"⚔️ Fase Suíça - Rodada {round_idx}")
            
            # --- EXIBIR RODADAS ANTERIORES (HISTÓRICO) ---
            if round_idx > 1:
                with st.expander("⏪ Ver Histórico de Rodadas Anteriores", expanded=False):
                    for i in range(round_idx - 1):
                        r_data = st.session_state.rounds[i]
                        st.markdown(f"**📌 Rodada {i+1}**")
                        if r_data.get('bye'):
                            st.write(f"🎉 *BYE (Folga): {r_data['bye']['name']}*")
                        for m in r_data['matches']:
                            h_name = next((t['name'] for t in st.session_state.teams if t['id'] == m['home']), "Time A")
                            a_name = next((t['name'] for t in st.session_state.teams if t['id'] == m['away']), "Time B")
                            winner_name = h_name if m.get('winner_id') == m['home'] else a_name
                            
                            # Verifica se teve pênaltis (evita erro se a chave não existir)
                            tem_penaltis = 'h_pen' in m and m['h_pen'] is not None
                            pen_txt = f" (Pên: {m['h_pen']} x {m['a_pen']})" if tem_penaltis and (m['h_pen'] > 0 or m['a_pen'] > 0) else ""
                            
                            st.write(f"⚽ {h_name} **{m['home_score']} x {m['away_score']}** {a_name}{pen_txt} ➡️ Venceu: **{winner_name}**")
                        st.divider()
            # ----------------------------------------------
            
            st.markdown(f"### ⚡ Rodada Atual: {round_idx}")
            current_round = st.session_state.rounds[-1]
            matches = current_round['matches']
            bye_team = current_round['bye']
            
            if bye_team:
                st.success(f"🎉 **BYE:** O time **{bye_team['name']}** folga nesta rodada e ganha +1 Vitória.")
            tab_jogos, tab_regras = st.tabs(["⚽ Jogos da Rodada", "📜 Regulamento"])

            with tab_regras:
                st.markdown(REGULAMENTO_TXT)

            with tab_jogos:
                with st.form(key=f"swiss_round_form_{round_idx}"):
                    st.subheader("Resultados")
                    
                    matches_data_input = []
                    any_draw = False
                    disabled_score = st.session_state.swiss_asking_penalties

                    for i, match in enumerate(matches):
                        c1, c2, c3, c4 = st.columns([2, 1, 1, 2])
                        home_name = next(t['name'] for t in st.session_state.teams if t['id'] == match['home'])
                        away_name = next(t['name'] for t in st.session_state.teams if t['id'] == match['away'])
                        
                        with c1: st.markdown(f"<h3 style='text-align: right'>{home_name}</h3>", unsafe_allow_html=True)
                        with c2: s1 = st.number_input("Gols", min_value=0, value=0, step=1, key=f"h_{round_idx}_{i}", disabled=disabled_score)
                        with c3: s2 = st.number_input("Gols", min_value=0, value=0, step=1, key=f"a_{round_idx}_{i}", disabled=disabled_score)
                        with c4: st.markdown(f"<h3>{away_name}</h3>", unsafe_allow_html=True)
                        
                        pen_h = 0
                        pen_a = 0
                        
                        if st.session_state.swiss_asking_penalties and s1 is not None and s2 is not None and s1 == s2:
                            st.warning("⚠️ Empate! Decisão por pênaltis:")
                            cp1, cp2 = st.columns(2)
                            with cp1: pen_h = st.number_input(f"Pênaltis {home_name}", min_value=0, value=0, step=1, key=f"swiss_pen_h_{i}")
                            with cp2: pen_a = st.number_input(f"Pênaltis {away_name}", min_value=0, value=0, step=1, key=f"swiss_pen_a_{i}")
                            any_draw = True
                        
                        matches_data_input.append({'match_idx': i, 'home_id': match['home'], 'away_id': match['away'], 'h_g': s1, 'a_g': s2, 'h_p': pen_h, 'a_p': pen_a})
                        
                    btn_label = "Confirmar Classificação" if st.session_state.swiss_asking_penalties else "Conferir Resultados"
                    submitted = st.form_submit_button(btn_label)
                    
                    if submitted:
                        missing_input = False
                        for m in matches_data_input:
                            if m['h_g'] is None or m['a_g'] is None: missing_input = True
                        
                        if missing_input:
                            st.error("Preencha todos os placares.")
                        else:
                            has_new_draw = False
                            if not st.session_state.swiss_asking_penalties:
                                for item in matches_data_input:
                                    if item['h_g'] == item['a_g']: has_new_draw = True
                                
                                if has_new_draw:
                                    st.session_state.swiss_asking_penalties = True
                                    st.rerun()
                                else:
                                    if bye_team: update_team_stats(bye_team['id'], 1, 0, True, True)
                                    for item in matches_data_input:
                                        w_home = item['h_g'] > item['a_g']
                                        w_id = item['home_id'] if w_home else item['away_id']
                                        current_round['matches'][item['match_idx']]['winner_id'] = w_id
                                        current_round['matches'][item['match_idx']]['home_score'] = item['h_g']
                                        current_round['matches'][item['match_idx']]['away_score'] = item['a_g']
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
                                    if item['h_g'] == item['a_g']:
                                        if item['h_p'] is None or item['a_p'] is None: 
                                            st.error("Preencha os pênaltis."); valid = False; break
                                        if item['h_p'] == item['a_p']: 
                                            st.error("Pênaltis não podem empatar."); valid = False; break
                                
                                if valid:
                                    if bye_team: update_team_stats(bye_team['id'], 1, 0, True, True)
                                    for item in matches_data_input:
                                        hg, ag, hp, ap = item['h_g'], item['a_g'], item['h_p'], item['a_p']
                                        w_home = hg > ag if hg != ag else hp > ap
                                        w_id = item['home_id'] if w_home else item['away_id']
                                        current_round['matches'][item['match_idx']]['winner_id'] = w_id
                                        current_round['matches'][item['match_idx']]['home_score'] = hg
                                        current_round['matches'][item['match_idx']]['away_score'] = ag
                                        current_round['matches'][item['match_idx']]['h_pen'] = hp
                                        current_round['matches'][item['match_idx']]['a_pen'] = ap
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
            if current_round['waiting']:
                names_waiting = ", ".join([t['name'] for t in current_round['waiting']])
                st.info(f"🛑 Times aguardando (Byes): **{names_waiting}**")
            
            tab_jogos, tab_regras = st.tabs(["⚽ Jogos da Rodada", "📜 Regulamento"])
            
            with tab_regras: st.markdown(REGULAMENTO_TXT)

            with tab_jogos:
                with st.form(key=f"playoff_form_{round_id}"):
                    matches_data_input = []
                    any_draw = False

                    for i, match in enumerate(current_round['matches']):
                        home = match['home']
                        away = match['away']
                        st.markdown(f"**{match['label']}**")
                        
                        col1, col2, col3, col4, col5 = st.columns([3, 1, 0.5, 1, 3])
                        disabled_score = st.session_state.playoff_asking_penalties
                        
                        with col1: st.markdown(f"<h3 style='text-align: right'>{home['name']}</h3>", unsafe_allow_html=True)
                        with col2: val_h = st.number_input("Gols", min_value=0, value=0, step=1, key=f"pg_h_{round_id}_{i}", disabled=disabled_score)
                        with col3: st.markdown("<h3 style='text-align: center'>X</h3>", unsafe_allow_html=True)
                        with col4: val_a = st.number_input("Gols", min_value=0, value=0, step=1, key=f"pg_a_{round_id}_{i}", disabled=disabled_score)
                        with col5: st.markdown(f"<h3>{away['name']}</h3>", unsafe_allow_html=True)
                        
                        pen_h = 0
                        pen_a = 0
                        
                        if st.session_state.playoff_asking_penalties and val_h is not None and val_a is not None and val_h == val_a:
                            st.warning("⚠️ Empate! Insira os pênaltis:")
                            cp1, cp2 = st.columns(2)
                            with cp1: pen_h = st.number_input(f"Pênaltis {home['name']}", min_value=0, value=None, key=f"pen_h_{round_id}_{i}")
                            with cp2: pen_a = st.number_input(f"Pênaltis {away['name']}", min_value=0, value=None, key=f"pen_a_{round_id}_{i}")
                            any_draw = True
                        
                        matches_data_input.append({'match': match, 'h_g': val_h, 'a_g': val_a, 'h_p': pen_h, 'a_p': pen_a})

                    btn_label = "Confirmar Classificação" if st.session_state.playoff_asking_penalties else "Conferir Resultados"
                    submitted = st.form_submit_button(btn_label)
                    
                    if submitted:
                        missing_input = False
                        for m in matches_data_input:
                            if m['h_g'] is None or m['a_g'] is None: missing_input = True
                        
                        if missing_input:
                            st.error("Preencha todos os placares.")
                        else:
                            has_new_draw = False
                            winners = []
                            losers = []
                            
                            if not st.session_state.playoff_asking_penalties:
                                for item in matches_data_input:
                                    if item['h_g'] == item['a_g']: has_new_draw = True
                                
                                if has_new_draw:
                                    st.session_state.playoff_asking_penalties = True
                                    st.rerun()
                                else:
                                    for item in matches_data_input:
                                        m = item['match']
                                        m['h_goals'] = item['h_g']
                                        m['a_goals'] = item['a_g']
                                        m['is_penalties'] = False
                                        m['h_pen'] = 0
                                        m['a_pen'] = 0
                                        
                                        w = m['home'] if item['h_g'] > item['a_g'] else m['away']
                                        l = m['away'] if item['h_g'] > item['a_g'] else m['home']
                                        m['winner_id'] = w['id']
                                        winners.append(w)
                                        losers.append(l)
                                        
                                        update_team_stats(m['home']['id'], item['h_g'], item['a_g'], w['id'] == m['home']['id'])
                                        update_team_stats(m['away']['id'], item['a_g'], item['h_g'], w['id'] == m['away']['id'])
                                    
                                    current_round['completed'] = True
                                    advance_playoff_round(winners, current_round['waiting'], losers=losers)
                                    st.rerun()
                            else:
                                valid = True
                                winners = []
                                losers = []
                                for item in matches_data_input:
                                    if item['h_g'] == item['a_g']:
                                        if item['h_p'] is None or item['a_p'] is None: st.error("Preencha pênaltis."); valid = False; break
                                        if item['h_p'] == item['a_p']: st.error("Pênaltis sem empate."); valid = False; break
                                
                                if valid:
                                    for item in matches_data_input:
                                        m = item['match']
                                        m['h_goals'] = item['h_g']
                                        m['a_goals'] = item['a_g']
                                        m['h_pen'] = item['h_p']
                                        m['a_pen'] = item['a_p']
                                        
                                        if item['h_g'] != item['a_g']:
                                            m['is_penalties'] = False
                                            w_home = item['h_g'] > item['a_g']
                                        else:
                                            m['is_penalties'] = True
                                            w_home = item['h_p'] > item['a_p']
                                        
                                        w = m['home'] if w_home else m['away']
                                        l = m['away'] if w_home else m['home']
                                        m['winner_id'] = w['id']
                                        winners.append(w)
                                        losers.append(l)
                                        
                                        update_team_stats(m['home']['id'], item['h_g'], item['a_g'], w['id'] == m['home']['id'])
                                        update_team_stats(m['away']['id'], item['a_g'], item['h_g'], w['id'] == m['away']['id'])
                                    
                                    current_round['completed'] = True
                                    advance_playoff_round(winners, current_round['waiting'], losers=losers)
                                    st.rerun()

        elif st.session_state.phase == 'champion':
            st.balloons()
            champ = st.session_state.champion
            vice = st.session_state.get('vice')
            third = st.session_state.get('third')
            
            st.markdown(f"""<div style="text-align: center; padding: 30px;"><h1>🏆 TORNEIO ENCERRADO! 🏆</h1></div>""", unsafe_allow_html=True)
            
            c1, c2, c3 = st.columns(3)
            with c2:
                st.markdown(f"""<div style="text-align: center; background-color: #FFD700; padding: 20px; border-radius: 10px; color: black;"><h2>🥇 CAMPEÃO</h2><h1 style="margin:0;">{champ['name']}</h1></div>""", unsafe_allow_html=True)
            with c1:
                if vice: st.markdown(f"""<div style="text-align: center; background-color: #C0C0C0; padding: 20px; border-radius: 10px; color: black; margin-top: 20px;"><h3>🥈 Vice-Campeão</h3><h2 style="margin:0;">{vice['name']}</h2></div>""", unsafe_allow_html=True)
            with c3:
                if third: st.markdown(f"""<div style="text-align: center; background-color: #CD7F32; padding: 20px; border-radius: 10px; color: black; margin-top: 20px;"><h3>🥉 3º Lugar</h3><h2 style="margin:0;">{third['name']}</h2></div>""", unsafe_allow_html=True)

            st.markdown("---")
            st.markdown("### 📊 Estatísticas do Campeão")
            goals_against = champ['goals_for'] - champ['goal_diff']
            m1, m2, m3, m4 = st.columns(4)
            with m1: m1.metric("Vitórias", champ['wins'])
            with m2: m2.metric("Gols Pró", champ['goals_for'])
            with m3: m3.metric("Gols Sofridos", goals_against)
            with m4: m4.metric("Saldo", champ['goal_diff'])
            
            st.markdown("---")
            if st.button("🏆 ENCERRAR E SALVAR NO HISTÓRICO GERAL", type="primary", use_container_width=True):
                h_br = (datetime.utcnow() - timedelta(hours=3)).strftime("%d/%m/%Y %H:%M")
                nome_vice = vice['name'] if vice else "---"
                nome_terc = third['name'] if third else "---"
                nova_h = pd.DataFrame([{'torneio_id': tid, 'formato': 'SUÍÇO', 'campeao': champ['name'], 'vice': nome_vice, 'terceiro': nome_terc, 'data_fim': h_br}])
                
                salvar_dados(pd.concat([df_hist, nova_h], ignore_index=True), ABA_HISTORICO)
                
                # Exclusão removida! O torneio continua salvo.
                st.success("✅ Torneio encerrado e salvo no Hall da Fama com sucesso!")

    # ==========================================
    # FLUXO COPA / LIGA
    # ==========================================
    else:
        if menu == "🏟️ Jogos":
            if df_t.empty or len(df_t[df_t['fase'] != 'Setup']) == 0: st.info("Gere os jogos no Admin.")
            else:
                for f in sorted(df_t['fase'].unique(), key=lambda x: ORDEM_FASES.get(x, 99)):
                    if f == "Setup": continue
                    with st.expander(f"📍 {f}", expanded=True): # Transforma a fase em um menu sanfona
                        for idx, r in df_t[df_t['fase'] == f].iterrows():
                            with st.container(border=True):
                                c1, c2, c3 = st.columns([2,1,2])
                                p_txt = f"{r['gols_a']} x {r['gols_b']}" if r['modo_copa']=="Só Ida" or fmt=="LIGA" else f"({r['ida_a']}) {r['volta_a']} x {r['volta_b']} ({r['ida_b']})"
                                if is_done(r['finalizado']) and (int(r['pen_a'])+int(r['pen_b'])>0): p_txt += f" (P: {r['pen_a']}x{r['pen_b']})"
                                c1.markdown(f"<p style='text-align:right'><b>{r['a']}</b></p>", unsafe_allow_html=True)
                                c2.markdown(f"<div style='text-align:center; background:#eee; padding:5px; color:black;'>{p_txt}</div>", unsafe_allow_html=True)
                                c3.markdown(f"<p style='text-align:left'><b>{r['b']}</b></p>", unsafe_allow_html=True)
                                
                                if is_admin:
                                    with st.expander("✎ Editar Jogo"):
                                        with st.form(f"f_{idx}"):
                                            # Garante o modo de disputa correto, mas força jogo único para Final e 3º Lugar
                                            is_ida_volta = (fmt in ["COPA", "AMISTOSO"] and modo_atual == "Ida e Volta" and r['fase'] not in ["Final", "3º Lugar"])
                                            
                                            if is_ida_volta:
                                                st.markdown("**⚽ JOGO DE IDA**")
                                                c_ida1, c_ida2 = st.columns(2)
                                                ia = c_ida1.number_input(f"Gols {r['a']}", 0, 99, int(r['ida_a']), key=f"ia_{idx}")
                                                ib = c_ida2.number_input(f"Gols {r['b']}", 0, 99, int(r['ida_b']), key=f"ib_{idx}")
                                                
                                                # A Volta fica escondida numa sanfona abaixo da Ida
                                                with st.expander("🔄 INSERIR JOGO DE VOLTA", expanded=False):
                                                    st.caption(f"Mando de campo invertido: {r['b']} x {r['a']}")
                                                    c_vol1, c_vol2 = st.columns(2)
                                                    vb = c_vol1.number_input(f"Gols {r['b']} (Casa)", 0, 99, int(r['volta_b']), key=f"vb_{idx}")
                                                    va = c_vol2.number_input(f"Gols {r['a']} (Fora)", 0, 99, int(r['volta_a']), key=f"va_{idx}")
                                                    
                                                res, sa, sb = [ia+va, ib+vb, ia, ib, va, vb], (ia+va), (ib+vb)
                                                
                                                st.markdown("---")
                                                encerrar = st.checkbox("✅ Encerrar Confronto (Avançar de Fase)", value=is_done(r['finalizado']), key=f"chk_{idx}")
                                            else:
                                                ca, cb = st.columns(2)
                                                ga = ca.number_input(f"{r['a']}", 0, 99, int(r['gols_a']), key=f"ga_{idx}")
                                                gb = cb.number_input(f"{r['b']}", 0, 99, int(r['gols_b']), key=f"gb_{idx}")
                                                res, sa, sb = [ga, gb, ga, gb, 0, 0], ga, gb
                                                encerrar = True # Jogo único/Liga sempre encerra ao salvar
                                            
                                            pa, pb = 0, 0
                                            if fmt in ["COPA", "AMISTOSO"] and sa == sb and r['a'] != "BYE" and r['b'] != "BYE":
                                                if is_ida_volta:
                                                    st.caption("🏆 Pênaltis (Preencha apenas no jogo de Volta se a soma empatar)")
                                                else:
                                                    st.caption("🏆 Decisão por Pênaltis")
                                                
                                                # Pênaltis agora alinhados perfeitamente abaixo em novas colunas
                                                cp1, cp2 = st.columns(2)
                                                pa = cp1.number_input(f"Pênaltis {r['a']}", 0, 99, int(r['pen_a']), key=f"pa_{idx}")
                                                pb = cp2.number_input(f"Pênaltis {r['b']}", 0, 99, int(r['pen_b']), key=f"pb_{idx}")
                                            
                                            if st.form_submit_button("Salvar"):
                                                status_fim = "SIM" if encerrar else "NÃO"
                                                
                                                # Bloqueio de erro: não deixa encerrar se empatar e não tiver vencedor nos pênaltis
                                                if fmt in ["COPA", "AMISTOSO"] and status_fim == "SIM" and sa == sb and pa == pb and r['a'] != "BYE" and r['b'] != "BYE":
                                                    st.error("⚠️ Empate! Preencha o vencedor dos pênaltis antes de encerrar o confronto.")
                                                else:
                                                    df_db.loc[idx, ['gols_a','gols_b','ida_a','ida_b','volta_a','volta_b','pen_a','pen_b','finalizado']] = res + [pa, pb, status_fim]
                                                    
                                                    if fmt == "COPA" and status_fim == "SIM":
                                                        df_fase = df_db[(df_db['torneio_id'] == tid) & (df_db['fase'] == r['fase'])]
                                                        # Só gera a próxima fase se TODOS os jogos desta fase estiverem com 'encerrar' marcado
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
                                                                for i in range(0, len(v), 2): novos.append({'torneio_id':tid,'formato':'COPA','fase':'Semifinal','a':v[i],'b':v[i+1],'modo_copa':modo_atual,'finalizado':'NÃO'})
                                                            if novos: df_db = pd.concat([df_db, pd.DataFrame(novos)], ignore_index=True)
                                                    
                                                    # Gatilho para pular para a tela Consulta e soltar balões ao finalizar
                                                    df_atualizado = df_db[df_db['torneio_id'] == tid]
                                                    jogos_validos = df_atualizado[df_atualizado['fase'] != 'Setup']
                                                    if not jogos_validos.empty and all(jogos_validos['finalizado'].apply(is_done)):
                                                        st.session_state.aba_atual = "📊 Consulta"
                                                        st.session_state.mostrar_baloes = True
                                                    
                                                    salvar_dados(df_db, ABA_JOGOS); st.rerun()
                if fmt == "AMISTOSO":
                    st.divider()
                    if st.button("🏁 ENCERRAR AMISTOSO E SALVAR NO HISTÓRICO", use_container_width=True, type="primary"):
                        jogo_list = df_t[df_t['fase'] == 'Amistoso']
                        if not jogo_list.empty:
                            jogo = jogo_list.iloc[0]
                            if is_done(jogo['finalizado']):
                                h_br = (datetime.utcnow() - timedelta(hours=3)).strftime("%d/%m/%Y %H:%M")
                                placar_final = f"{jogo['a']} {int(jogo['gols_a'])} x {int(jogo['gols_b'])} {jogo['b']}"
                                if int(jogo['pen_a']) > 0 or int(jogo['pen_b']) > 0:
                                    placar_final += f" (P: {int(jogo['pen_a'])}x{int(jogo['pen_b'])})"
                                nova_h = pd.DataFrame([{
                                    'torneio_id': tid, 'formato': 'AMISTOSO',
                                    'campeao': placar_final, 'vice': '---', 'terceiro': '---', 'data_fim': h_br
                                }])
                                salvar_dados(pd.concat([df_hist, nova_h], ignore_index=True), ABA_HISTORICO)
                                salvar_dados(df_db[df_db['torneio_id'] != tid], ABA_JOGOS)
                                st.success("✅ Amistoso gravado!")
                                st.balloons()
                                st.session_state.torneio_ativo = None
                                st.rerun()
                            else:
                                st.warning("⚠️ Salve o placar primeiro!")
                        
        elif menu == "📊 Consulta":
            st.title("📊 Painel de Consulta")
            
            # --- Lógica do Pódio Automático e Balões ---
            jogos_validos = df_t[df_t['fase'] != 'Setup']
            torneio_encerrado = not jogos_validos.empty and all(jogos_validos['finalizado'].apply(is_done))
            
            if torneio_encerrado:
                if st.session_state.get('mostrar_baloes', False):
                    st.balloons()
                    st.session_state.mostrar_baloes = False # Reseta para não ficar soltando balão toda vez que entrar na tela
                
                c, v, t = "---", "---", "---"
                if fmt == "COPA":
                    fin = df_t[df_t['fase'] == 'Final']
                    t3 = df_t[df_t['fase'] == '3º Lugar']
                    if not fin.empty: c, v = obter_vencedor_perdedor(fin.iloc[0])
                    if not t3.empty: t, _ = obter_vencedor_perdedor(t3.iloc[0])
                elif fmt == "AMISTOSO":
                    ami = df_t[df_t['fase'] == 'Amistoso']
                    if not ami.empty: c, v = obter_vencedor_perdedor(ami.iloc[0])
                else: # LIGA
                    tm = pd.concat([df_t['a'], df_t['b']]).unique()
                    stt = {tmx: {'P':0,'V':0,'SG':0,'GP':0} for tmx in tm if pd.notna(tmx) and tmx != "BYE" and tmx != "Setup"}
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
                
                # Desenhando o Pódio
                st.markdown(f"""<div style="text-align: center; padding: 10px;"><h2>🏆 {'VENCEDOR' if fmt == 'AMISTOSO' else 'PÓDIO FINAL'} 🏆</h2></div>""", unsafe_allow_html=True)
                if fmt == "AMISTOSO":
                    c1, c2 = st.columns(2)
                    with c1: st.markdown(f"""<div style="text-align: center; background-color: #28B463; padding: 15px; border-radius: 10px; color: white; border: 2px solid #1E8449;"><h2>✅ VENCEDOR</h2><h2 style="margin:0;">{c}</h2></div>""", unsafe_allow_html=True)
                    with c2: st.markdown(f"""<div style="text-align: center; background-color: #E74C3C; padding: 15px; border-radius: 10px; color: white; border: 2px solid #B03A2E;"><h3>❌ Derrotado</h3><h3 style="margin:0;">{v}</h3></div>""", unsafe_allow_html=True)
                else:
                    c1, c2, c3 = st.columns(3)
                    with c2: st.markdown(f"""<div style="text-align: center; background-color: #FFD700; padding: 15px; border-radius: 10px; color: black; border: 2px solid #B8860B;"><h2>🥇 CAMPEÃO</h2><h2 style="margin:0;">{c}</h2></div>""", unsafe_allow_html=True)
                    with c1: st.markdown(f"""<div style="text-align: center; background-color: #C0C0C0; padding: 15px; border-radius: 10px; color: black; margin-top: 20px; border: 2px solid #808080;"><h3>🥈 Vice</h3><h3 style="margin:0;">{v}</h3></div>""", unsafe_allow_html=True)
                    with c3: st.markdown(f"""<div style="text-align: center; background-color: #CD7F32; padding: 15px; border-radius: 10px; color: black; margin-top: 20px; border: 2px solid #8B4513;"><h3>🥉 3º Lugar</h3><h3 style="margin:0;">{t}</h3></div>""", unsafe_allow_html=True)
                st.divider()

            # --- Visualização de Jogos e Tabelas ---
            if fmt == "LIGA":
                st.subheader("📈 Tabela de Classificação")
                times = pd.concat([df_t['a'], df_t['b']]).unique()
                stats = {tx: {'Pts':0,'J':0,'V':0,'E':0,'D':0,'GP':0,'GC':0,'SG':0} for tx in times if pd.notna(tx) and tx != "BYE" and tx != "Setup"}
                for _, r in df_t[df_t['finalizado'] == 'SIM'].iterrows():
                    t1, t2, g1, g2 = r['a'], r['b'], int(r['gols_a']), int(r['gols_b'])
                    if t1 in stats and t2 in stats:
                        stats[t1]['J']+=1; stats[t2]['J']+=1; stats[t1]['GP']+=g1; stats[t1]['GC']+=g2; stats[t2]['GP']+=g2; stats[t2]['GC']+=g1
                        if g1 > g2: stats[t1]['Pts']+=3; stats[t1]['V']+=1; stats[t2]['D']+=1
                        elif g2 > g1: stats[t2]['Pts']+=3; stats[t2]['V']+=1; stats[t1]['D']+=1
                        else: stats[t1]['Pts']+=1; stats[t2]['Pts']+=1; stats[t1]['E']+=1; stats[t2]['E']+=1
                        stats[t1]['SG'] = stats[t1]['GP'] - stats[t1]['GC']; stats[t2]['SG'] = stats[t2]['GP'] - stats[t2]['GC']
                
                df_classificacao = pd.DataFrame.from_dict(stats, orient='index').sort_values(by=['Pts','V','SG','GP'], ascending=False)
                st.dataframe(df_classificacao, use_container_width=True)

            st.subheader("⚽ Resultados dos Jogos")
            
            # Listagem de jogos com visual em "Cards" Esportivos
            f_p = ["Turno Único", "Turno", "Returno", "Liga", "Oitavas", "Quartas", "Semifinal", "3º Lugar", "Final", "Amistoso"]
            for fn in f_p:
                jogos_fase = df_t[df_t['fase'] == fn]
                if not jogos_fase.empty:
                    with st.expander(f"📌 {fn.upper()}", expanded=True):
                        for _, r in jogos_fase.iterrows():
                            vw, _ = obter_vencedor_perdedor(r)
                            
                            # Cores de fundo (Dark Mode): Verde bem escuro se finalizado, Cinza escuro se pendente
                            bg_color = "#1E3A2F" if is_done(r['finalizado']) else "#2B2B2B"
                            border_color = "#28B463" if is_done(r['finalizado']) else "#5D6D7E"
                            
                            # Montando o placar visual com fontes maiores
                            if r['modo_copa'] == "Só Ida" or fmt == "LIGA":
                                p_txt = f"<span style='font-size:24px;'>{r['gols_a']}</span> &nbsp;x&nbsp; <span style='font-size:24px;'>{r['gols_b']}</span>"
                            else:
                                soma_a, soma_b = int(r['ida_a']) + int(r['volta_a']), int(r['ida_b']) + int(r['volta_b'])
                                p_txt = f"<div style='font-size:14px; color:#aaa;'>Ida: {r['ida_a']}x{r['ida_b']} | Volta: {r['volta_a']}x{r['volta_b']}</div>"
                                p_txt += f"<span style='font-size:24px;'>{soma_a}</span> &nbsp;x&nbsp; <span style='font-size:24px;'>{soma_b}</span>"
                            
                            # Texto de Pênaltis
                            if is_done(r['finalizado']) and (int(r['pen_a']) + int(r['pen_b']) > 0):
                                p_txt += f"<br><span style='color:#F1C40F; font-size:14px;'>Pênaltis: {r['pen_a']} x {r['pen_b']}</span>"
                                
                            # Quem avança (Só mostra em Mata-Mata finalizado)
                            vencedor_txt = f"<div style='margin-top:5px; color:#F4D03F; font-weight:bold;'>🏆 Avança: {vw}</div>" if vw and fn not in ["Liga", "Turno Único", "Turno", "Returno"] else ""
                            
                            st.markdown(f"""
                            <div style="border: 2px solid {border_color}; background-color: {bg_color}; padding: 10px; border-radius: 8px; margin-bottom: 10px;">
                                <div style="display: flex; justify-content: space-between; align-items: center; text-align: center;">
                                    <div style="flex: 1; font-size: 18px; font-weight: bold; color: white;">{r['a']}</div>
                                    <div style="flex: 1; color: #F4D03F; font-weight: bold;">{p_txt}</div>
                                    <div style="flex: 1; font-size: 18px; font-weight: bold; color: white;">{r['b']}</div>
                                </div>
                                <div style="text-align:center;">{vencedor_txt}</div>
                            </div>
                            """, unsafe_allow_html=True)

        elif menu == "⚙️ Admin" and is_admin:
            # Nova lógica: Se a única fase existente for 'Setup', ele mostra a criação.
            # Se já houver 'Amistoso', 'Oitavas', 'Liga', etc, ele mostra o encerramento.
            fases_reais = [f for f in df_t['fase'].unique() if f != 'Setup']
            
            if not fases_reais:
                st.subheader("🛠️ Configuração de Partidas")
                txt = st.text_area("Times (um por linha)")
                if st.button("GERAR JOGOS", use_container_width=True, type="primary"):
                    times = [x.strip() for x in txt.split('\n') if x.strip()]
                    jogos = []
                    
                    if fmt == "AMISTOSO":
                        if len(times) == 2:
                            jogos.append({'torneio_id': tid, 'formato': 'AMISTOSO', 'fase': 'Amistoso', 'a': times[0], 'b': times[1], 'modo_copa': modo_atual, 'finalizado': 'NÃO'})
                        else:
                            st.error("⚠️ Para um Amistoso, digite exatamente 2 times.")
                    
                    elif fmt == "LIGA":
                        nome_fase = "Turno Único" if modo_atual == "Só Ida" else "Turno"
                        for a, b in combinations(times, 2): 
                            jogos.append({'torneio_id':tid,'formato':'LIGA','fase':nome_fase,'a':a,'b':b,'modo_copa':'Só Ida','finalizado':'NÃO'})
                        if modo_atual == "Ida e Volta":
                            for a, b in combinations(times, 2):
                                jogos.append({'torneio_id':tid,'formato':'LIGA','fase':'Returno','a':b,'b':a,'modo_copa':'Só Ida','finalizado':'NÃO'})
                    
                    else: # COPA
                        f_ini = "Semifinal" if len(times)<=4 else "Quartas"
                        for i in range(0, len(times), 2):
                            t1, t2 = times[i], (times[i+1] if i+1 < len(times) else "BYE")
                            jogos.append({'torneio_id':tid,'formato':'COPA','fase':f_ini,'a':t1,'b':t2,'modo_copa':modo_atual,'finalizado':'NÃO'})
                    
                    if jogos:
                        # Remove a linha de Setup e adiciona os jogos reais
                        df_db = df_db[~((df_db['torneio_id'] == tid) & (df_db['fase'] == 'Setup'))]
                        salvar_dados(pd.concat([df_db, pd.DataFrame(jogos)], ignore_index=True), ABA_JOGOS)
                        st.success("✅ Jogos gerados com sucesso!")
                        st.rerun()
            else:
                st.subheader("🏆 Finalização do Torneio")
                st.info("Certifique-se de que todos os placares foram preenchidos na aba 'Jogos' antes de encerrar.")
                
                if st.button("🏆 ENCERRAR E SALVAR NO HISTÓRICO", use_container_width=True, type="primary"):
                    h_br = (datetime.utcnow() - timedelta(hours=3)).strftime("%d/%m/%Y %H:%M")
                    c, v, t = "---", "---", "---"
                    
                    if fmt == "COPA":
                        fin, t3 = df_t[df_t['fase'] == 'Final'], df_t[df_t['fase'] == '3º Lugar']
                        if not fin.empty: c, v = obter_vencedor_perdedor(fin.iloc[0])
                        if not t3.empty: t, _ = obter_vencedor_perdedor(t3.iloc[0])
                    
                    elif fmt == "AMISTOSO":
                        ami = df_t[df_t['fase'] == 'Amistoso']
                        if not ami.empty:
                            c, v = obter_vencedor_perdedor(ami.iloc[0])
                    
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
                    
                    # Salva no Histórico
                    nova_h = pd.DataFrame([{
                        'torneio_id': tid, 'formato': fmt, 'campeao': c if c else "Empate",
                        'vice': v if v else "Empate", 'terceiro': t, 'data_fim': h_br
                    }])
                    
                    salvar_dados(pd.concat([df_hist, nova_h], ignore_index=True), ABA_HISTORICO)
                    st.success("✅ Gravado no Hall da Fama!")
                    st.session_state.mostrar_baloes = True
                    st.session_state.aba_atual = "📊 Consulta" 
                    st.rerun()

                if st.button("🚨 EXCLUIR TORNEIO (SEM SALVAR)"):
                    salvar_dados(df_db[df_db['torneio_id'] != tid], ABA_JOGOS)
                    st.session_state.torneio_ativo = None
                    st.rerun()
























