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
    # Ordenação: Vitórias > Menos Derrotas > Saldo > GP
    return sorted(st.session_state.teams, key=lambda x: (
        x['wins'], -x['losses'], x['goal_diff'], x['goals_for']
    ), reverse=True)

def generate_swiss_pairing():
    active = [t for t in st.session_state.teams if t['status'] == 'Ativo']
    if not active: return None # Retorna None se não houver mais ninguém ativo
    
    random.shuffle(active)
    ranked = sorted(active, key=lambda x: (x['wins'], -x['losses']), reverse=True)
    
    bye_t = None
    if len(ranked) % 2 != 0:
        eligible_for_bye = [t for t in sorted(ranked, key=lambda x: x['wins']) if not t['received_bye']]
        bye_t = eligible_for_bye[0] if eligible_for_bye else ranked[-1]
        ranked.remove(bye_t)

    matches = []
    while len(ranked) >= 2:
        home = ranked.pop(0)
        idx_opp = 0
        for i, potential in enumerate(ranked):
            if potential['id'] not in home['history']:
                idx_opp = i
                break
        opp = ranked.pop(idx_opp)
        matches.append({'home': home['id'], 'away': opp['id']})
    
    return {'matches': matches, 'bye': bye_t}

def setup_playoffs():
    qualified = [t for t in st.session_state.teams if t['status'] == 'Classificado']
    # Re-ordena apenas os classificados para o chaveamento
    seeds = [t for t in get_rankings() if t['status'] == 'Classificado']
    
    n = len(seeds)
    if n >= 8:
        current_seeds = seeds[:8]
        label = "Quartas de Final"
        m = [{'home': current_seeds[0], 'away': current_seeds[7], 'label': 'Jogo 1 (1º x 8º)'},
             {'home': current_seeds[1], 'away': current_seeds[6], 'label': 'Jogo 2 (2º x 7º)'},
             {'home': current_seeds[2], 'away': current_seeds[5], 'label': 'Jogo 3 (3º x 6º)'},
             {'home': current_seeds[3], 'away': current_seeds[4], 'label': 'Jogo 4 (4º x 5º)'}]
    elif n >= 4:
        current_seeds = seeds[:4]
        label = "Semifinais"
        m = [{'home': current_seeds[0], 'away': current_seeds[3], 'label': 'Semi 1 (1º x 4º)'},
             {'home': current_seeds[1], 'away': current_seeds[2], 'label': 'Semi 2 (2º x 3º)'}]
    elif n >= 2:
        label = "Grande Final"
        m = [{'home': seeds[0], 'away': seeds[1], 'label': 'Final'}]
    else:
        st.error("Classificados insuficientes para gerar mata-mata!")
        return
    
    st.session_state.playoffs.append({'label': label, 'matches': m})
    st.session_state.phase = 'playoff'

# --- BARRA LATERAL (FIXA) ---
with st.sidebar:
    st.title("📊 Ranking")
    if st.session_state.teams:
        df_rank = pd.DataFrame(get_rankings())
        df_view = df_rank[['name', 'wins', 'losses', 'goal_diff', 'received_bye', 'status']].copy()
        df_view.columns = ['Time', 'V', 'D', 'SG', 'Bye', 'Status']
        df_view['Bye'] = df_view['Bye'].map({True: '✅', False: '❌'})
        st.dataframe(df_view, hide_index=True)
    
    st.divider()
    if st.button("🗑️ Reset Total"):
        st.session_state.clear()
        st.rerun()

# --- TELAS ---

if st.session_state.phase == 'setup':
    st.title("🏆 Configuração do Torneio")
    num = st.number_input("Número de equipes", 2, 32, 8)
    with st.form("setup_teams"):
        cols = st.columns(2)
        names = []
        for i in range(num):
            names.append(cols[i%2].text_input(f"Equipe {i+1}", f"Time {i+1}", key=f"in_{i}"))
        
        if st.form_submit_button("GERAR TORNEIO"):
            st.session_state.teams = [{'id': i, 'name': n, 'wins': 0, 'losses': 0, 'goals_for': 0, 'goal_diff': 0, 'received_bye': False, 'history': [], 'status': 'Ativo'} for i, n in enumerate(names)]
            first_round = generate_swiss_pairing()
            if first_round:
                st.session_state.rounds.append(first_round)
                st.session_state.phase = 'swiss'
                sync_to_sheets()
                st.rerun()

elif st.session_state.phase == 'swiss':
    st.title(f"⚽ Rodada {len(st.session_state.rounds)} (Suíço)")
    
    # Proteção contra erro de rodada inexistente no fim da fase
    if not st.session_state.rounds:
        st.error("Nenhuma rodada encontrada.")
    else:
        curr = st.session_state.rounds[-1]
        
        # Só mostra os jogos se a rodada atual for válida
        if curr:
            if curr.get('bye'): 
                st.warning(f"✨ **Bye desta rodada:** {curr['bye']['name']} (+1 Vitória)")

            with st.form("form_swiss"):
                results = []
                for i, m in enumerate(curr['matches']):
                    t1 = next(t for t in st.session_state.teams if t['id'] == m['home'])
                    t2 = next(t for t in st.session_state.teams if t['id'] == m['away'])
                    c1, g1_c, g2_c, c2 = st.columns([2,1,1,2])
                    g1 = g1_c.number_input(t1['name'], 0, 50, key=f"s1_{i}", step=1)
                    g2 = g2_c.number_input(t2['name'], 0, 50, key=f"s2_{i}", step=1)
                    p1, p2 = 0, 0
                    if g1 == g2:
                        pc1, pc2 = st.columns(2)
                        p1 = pc1.number_input(f"Pên {t1['name']}", 0, 20, key=f"p1_{i}")
                        p2 = pc2.number_input(f"Pên {t2['name']}", 0, 20, key=f"p2_{i}")
                    results.append({'h': t1, 'a': t2, 'g1': g1, 'g2': g2, 'p1': p1, 'p2': p2})
                    st.divider()

                if st.form_submit_button("Confirmar Rodada"):
                    # Processa Bye
                    if curr.get('bye'):
                        curr['bye']['wins'] += 1
                        curr['bye']['received_bye'] = True
                    
                    # Processa Resultados
                    for r in results:
                        vh = r['g1'] > r['g2'] if r['g1'] != r['g2'] else r['p1'] > r['p2']
                        r['h']['goals_for'] += r['g1']; r['h']['goal_diff'] += (r['g1'] - r['g2'])
                        r['a']['goals_for'] += r['g2']; r['a']['goal_diff'] += (r['g2'] - r['g1'])
                        if vh: r['h']['wins'] += 1; r['a']['losses'] += 1
                        else: r['a']['wins'] += 1; r['h']['losses'] += 1
                        r['h']['history'].append(r['a']['id'])
                        r['a']['history'].append(r['h']['id'])

                    # Atualiza Status
                    for t in st.session_state.teams:
                        if t['wins'] >= 3: t['status'] = 'Classificado'
                        elif t['losses'] >= 3: t['status'] = 'Eliminado'
                    
                    sync_to_sheets()
                    
                    # Tenta gerar próxima rodada ou encerra
                    next_r = generate_swiss_pairing()
                    if next_r:
                        st.session_state.rounds.append(next_r)
                    st.rerun()

        # Botão para avançar (aparece quando não há mais ativos)
        ativos = [t for t in st.session_state.teams if t['status'] == 'Ativo']
        if not ativos:
            st.success("🏁 Fase Suíça Concluída!")
            if st.button("🚀 IR PARA O MATA-MATA"):
                setup_playoffs()
                st.rerun()

elif st.session_state.phase == 'playoff':
    curr_pl = st.session_state.playoffs[-1]
    st.title(f"🔥 {curr_pl['label']}")
    
    

    with st.form("form_playoff"):
        winners = []
        for i, m in enumerate(curr_pl['matches']):
            st.subheader(f"{m['label']}")
            c1, g1_c, g2_c, c2 = st.columns([2,1,1,2])
            g1 = g1_c.number_input(m['home']['name'], 0, 50, key=f"pg1_{i}")
            g2 = g2_c.number_input(m['away']['name'], 0, 50, key=f"pg2_{i}")
            p1, p2 = 0, 0
            if g1 == g2:
                pc1, pc2 = st.columns(2)
                p1 = pc1.number_input("Pên.", 0, key=f"pp1_{i}")
                p2 = pc2.number_input("Pên.", 0, key=f"pp2_{i}")
            winners.append(m['home'] if (g1 > g2 or (g1 == g2 and p1 > p2)) else m['away'])
            st.divider()

        if st.form_submit_button("Avançar para Próxima Fase"):
            if len(winners) == 1:
                st.session_state.champion = winners[0]
                st.session_state.phase = 'champion'
            else:
                next_label = "Semifinais" if len(winners) == 4 else "Grande Final"
                m_next = [{'home': winners[i], 'away': winners[len(winners)-1-i], 'label': f'Mata {i+1}'} for i in range(len(winners)//2)]
                st.session_state.playoffs.append({'label': next_label, 'matches': m_next})
            st.rerun()

elif st.session_state.phase == 'champion':
    st.balloons()
    st.markdown(f"<h1 style='text-align: center; color: #FFD700;'>🏆 CAMPEÃO: {st.session_state.champion['name']}</h1>", unsafe_allow_html=True)
    if st.button("RECOMEÇAR TUDO"):
        st.session_state.clear()
        st.rerun()
