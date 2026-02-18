import streamlit as st
import pandas as pd
import random
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="BAGA GESTOR PRO", layout="wide", page_icon="🏆")
conn = st.connection("gsheets", type=GSheetsConnection)

# --- INICIALIZAÇÃO DE ESTADO ---
if 'teams' not in st.session_state: st.session_state.teams = []
if 'phase' not in st.session_state: st.session_state.phase = 'setup'
if 'rounds' not in st.session_state: st.session_state.rounds = []
if 'playoffs' not in st.session_state: st.session_state.playoffs = []
if 'waiting_next_round' not in st.session_state: st.session_state.waiting_next_round = []
if 'champion' not in st.session_state: st.session_state.champion = None

# --- FUNÇÕES CORE ---

def sync_to_sheets():
    if not st.session_state.teams:
        cols = ['id', 'name', 'wins', 'losses', 'goals_for', 'goal_diff', 'received_bye', 'history', 'status']
        df_save = pd.DataFrame(columns=cols)
    else:
        df_save = pd.DataFrame(st.session_state.teams)
        df_save['history'] = df_save['history'].apply(lambda x: str(x))
    conn.update(worksheet="Suico", data=df_save)

def get_rankings():
    # Critério: Vitórias > Menos Derrotas > Saldo > GP
    return sorted(st.session_state.teams, key=lambda x: (
        x['wins'], -x['losses'], x['goal_diff'], x['goals_for']
    ), reverse=True)

def setup_playoffs():
    qualified = [t for t in get_rankings() if t['status'] == 'Classificado']
    n = len(qualified)
    
    if n == 0:
        st.error("Ninguém classificado!")
        return

    matches = []
    waiting = []

    # Lógica de BYE por mérito (pular fase)
    if n == 3:
        label = "Semifinal"
        waiting = [qualified[0]] # 1º lugar espera
        matches = [{'home': qualified[1], 'away': qualified[2], 'label': 'Semi (Vencedor encara o 1º)'}]
    elif 4 < n < 8:
        label = "Rodada Preliminar"
        num_to_play = (n - 4) * 2
        to_play = qualified[-num_to_play:]
        waiting = qualified[:n-num_to_play] # Melhores esperam
        matches = [{'home': to_play[i], 'away': to_play[-(i+1)], 'label': f'Jogo Preliminar {i+1}'} for i in range(len(to_play)//2)]
    else:
        if n >= 8:
            label, top = "Quartas de Final", qualified[:8]
            matches = [{'home': top[i], 'away': top[7-i], 'label': f'Quartas {i+1}'} for i in range(4)]
        elif n >= 4:
            label, top = "Semifinais", qualified[:4]
            matches = [{'home': top[i], 'away': top[3-i], 'label': f'Semi {i+1}'} for i in range(2)]
        else:
            label, top = "Grande Final", qualified[:2]
            matches = [{'home': top[0], 'away': top[1], 'label': 'Final'}]

    st.session_state.playoffs.append({'label': label, 'matches': matches})
    st.session_state.waiting_next_round = waiting
    st.session_state.phase = 'playoff'

# --- BARRA LATERAL (RANKING COM CORES E BYE) ---
with st.sidebar:
    st.title("📊 Ranking")
    if st.session_state.teams:
        df_rank = pd.DataFrame(get_rankings())
        
        # Criamos colunas limpas para a exibição
        df_view = df_rank[['name', 'wins', 'losses', 'goal_diff', 'received_bye', 'status']].copy()
        df_view.columns = ['Time', 'V', 'D', 'SG', 'Bye', 'Status']
        
        # O ÍCONE DO BYE (Aparece se recebeu folga no suíço)
        df_view['Bye'] = df_view['Bye'].apply(lambda x: "⭐" if x else "")

        # Função de Cores
        def style_rows(row):
            if row['Status'] == 'Classificado':
                return ['background-color: #c8e6c9'] * len(row) # Verde claro
            elif row['Status'] == 'Eliminado':
                return ['background-color: #ffcdd2'] * len(row) # Vermelho claro
            return [''] * len(row)

        st.dataframe(df_view.style.apply(style_rows, axis=1), hide_index=True, use_container_width=True)
    
    st.divider()
    if st.button("Reset Total"):
        st.session_state.clear()
        st.rerun()

# --- TELAS ---

if st.session_state.phase == 'setup':
    st.title("🏆 Configuração")
    num = st.number_input("Equipes", 2, 32, 8)
    with st.form("setup"):
        names = [st.text_input(f"Time {i+1}", f"Equipe {i+1}") for i in range(num)]
        if st.form_submit_button("Gerar Torneio"):
            st.session_state.teams = [{'id': i, 'name': n, 'wins': 0, 'losses': 0, 'goals_for': 0, 'goal_diff': 0, 'received_bye': False, 'history': [], 'status': 'Ativo'} for i, n in enumerate(names)]
            st.session_state.phase = 'swiss'
            # Primeira Rodada
            pool = st.session_state.teams.copy()
            random.shuffle(pool)
            bye_t = pool.pop() if len(pool)%2 != 0 else None
            m = [{'home': pool[i]['id'], 'away': pool[i+1]['id']} for i in range(0, len(pool), 2)]
            st.session_state.rounds = [{'matches': m, 'bye': bye_t}]
            st.rerun()

elif st.session_state.phase == 'swiss':
    st.title(f"⚽ Rodada {len(st.session_state.rounds)} (Suíço)")
    curr = st.session_state.rounds[-1]
    
    if curr.get('bye'):
        st.warning(f"⭐ **FOLGA (BYE):** {curr['bye']['name']} ganhou +1 vitória.")

    with st.form("results"):
        res = []
        for i, m in enumerate(curr['matches']):
            t1 = next(t for t in st.session_state.teams if t['id'] == m['home'])
            t2 = next(t for t in st.session_state.teams if t['id'] == m['away'])
            c1, g1c, g2c, c2 = st.columns([2,1,1,2])
            g1 = g1c.number_input(t1['name'], 0, 50, key=f"g1_{i}")
            g2 = g2c.number_input(t2['name'], 0, 50, key=f"g2_{i}")
            res.append({'h': t1, 'a': t2, 'g1': g1, 'g2': g2})
        
        if st.form_submit_button("Salvar Resultados"):
            if curr.get('bye'):
                curr['bye']['wins'] += 1; curr['bye']['received_bye'] = True
            for r in res:
                r['h']['goals_for'] += r['g1']; r['a']['goals_for'] += r['g2']
                r['h']['goal_diff'] += (r['g1']-r['g2']); r['a']['goal_diff'] += (r['g2']-r['g1'])
                if r['g1'] > r['g2']: r['h']['wins'] += 1; r['a']['losses'] += 1
                else: r['a']['wins'] += 1; r['h']['losses'] += 1
                r['h']['history'].append(r['a']['id']); r['a']['history'].append(r['h']['id'])
            
            for t in st.session_state.teams:
                if t['wins'] >= 3: t['status'] = 'Classificado'
                elif t['losses'] >= 3: t['status'] = 'Eliminado'
            
            sync_to_sheets()
            ativos = [t for t in st.session_state.teams if t['status'] == 'Ativo']
            if not ativos: 
                st.session_state.phase = 'end_swiss'
            else:
                # Gera próxima rodada
                pool = sorted(ativos, key=lambda x: (x['wins'], -x['losses']), reverse=True)
                bye_t = pool.pop() if len(pool)%2 != 0 else None
                new_m = [{'home': pool[i]['id'], 'away': pool[i+1]['id']} for i in range(0, len(pool), 2)]
                st.session_state.rounds.append({'matches': new_m, 'bye': bye_t})
            st.rerun()

elif st.session_state.phase == 'end_swiss':
    st.title("🏁 Fim da Fase Suíça")
    st.success("Tabela finalizada! Clique abaixo para iniciar o Mata-Mata.")
    if st.button("🚀 IR PARA O MATA-MATA (CHAVEAMENTO 1x8, 2x7...)"):
        setup_playoffs()
        st.rerun()

elif st.session_state.phase == 'playoff':
    curr_p = st.session_state.playoffs[-1]
    st.title(f"🔥 {curr_p['label']}")
    
    if st.session_state.waiting_next_round:
        st.info("🛡️ **Aguardando na próxima fase (Bye por mérito):** " + ", ".join([t['name'] for t in st.session_state.waiting_next_round]))

    with st.form("playoffs"):
        winners = []
        for i, m in enumerate(curr_p['matches']):
            st.subheader(m['label'])
            c1, g1c, g2c, c2 = st.columns([2,1,1,2])
            g1 = g1c.number_input(m['home']['name'], 0, 50, key=f"pg1_{i}")
            g2 = g2c.number_input(m['away']['name'], 0, 50, key=f"pg2_{i}")
            p1, p2 = 0, 0
            if g1 == g2:
                pc1, pc2 = st.columns(2)
                p1, p2 = pc1.number_input("Pên. H", 0), pc2.number_input("Pên. A", 0)
            winners.append(m['home'] if (g1 > g2 or (g1 == g2 and p1 > p2)) else m['away'])
        
        if st.form_submit_button("Confirmar Ganhadores"):
            all_next = st.session_state.waiting_next_round + winners
            st.session_state.waiting_next_round = []
            
            if len(all_next) == 1:
                st.session_state.champion = all_next[0]; st.session_state.phase = 'champion'
            else:
                # Próxima fase
                all_next = sorted(all_next, key=lambda x: (x['wins'], x['goal_diff']), reverse=True)
                lbl = "Final" if len(all_next) == 2 else "Semifinais"
                new_m = [{'home': all_next[i], 'away': all_next[-(i+1)], 'label': f'Jogo {i+1}'} for i in range(len(all_next)//2)]
                st.session_state.playoffs.append({'label': lbl, 'matches': new_m})
            st.rerun()

elif st.session_state.phase == 'champion':
    st.balloons()
    st.header(f"🏆 CAMPEÃO: {st.session_state.champion['name']}")
    if st.button("Reiniciar"): st.session_state.clear(); st.rerun()
