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
    return sorted(st.session_state.teams, key=lambda x: (
        x['wins'], -x['losses'], x['goal_diff'], x['goals_for']
    ), reverse=True)

# --- BARRA LATERAL (ESTILO CORRIGIDO) ---
with st.sidebar:
    st.title("📊 Classificação")
    if st.session_state.teams:
        df_rank = pd.DataFrame(get_rankings())
        
        # Criando a visualização
        df_view = df_rank[['name', 'wins', 'losses', 'goal_diff', 'received_bye', 'status']].copy()
        df_view.columns = ['Time', 'V', 'D', 'SG', 'Bye', 'Status']
        
        # INJEÇÃO DIRETA DO ÍCONE (Garantindo que apareça)
        df_view['Bye'] = df_view['Bye'].apply(lambda x: "⭐" if x == True else "")

        # FUNÇÃO DE ESTILO: APENAS COLUNA STATUS COM TEXTO PRETO
        def style_status_only(val):
            if val == 'Classificado': return 'background-color: #d4edda; color: black; font-weight: bold'
            if val == 'Eliminado': return 'background-color: #f8d7da; color: black; font-weight: bold'
            if val == 'Ativo': return 'background-color: #cce5ff; color: black; font-weight: bold'
            return ''

        st.dataframe(
            df_view.style.applymap(style_status_only, subset=['Status']),
            hide_index=True, 
            use_container_width=True
        )
    
    st.divider()
    if st.button("🗑️ Reset Total"):
        st.session_state.clear()
        st.rerun()

# --- TELAS ---

if st.session_state.phase == 'setup':
    st.title("🏆 Configuração do Torneio")
    num = st.number_input("Número de equipes", 2, 32, 8)
    with st.form("setup_form"):
        names = [st.text_input(f"Equipe {i+1}", f"Time {i+1}") for i in range(num)]
        if st.form_submit_button("INICIAR TORNEIO"):
            st.session_state.teams = [{'id': i, 'name': n, 'wins': 0, 'losses': 0, 'goals_for': 0, 'goal_diff': 0, 'received_bye': False, 'history': [], 'status': 'Ativo'} for i, n in enumerate(names)]
            st.session_state.phase = 'swiss'
            # Gerar 1ª rodada
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
        st.warning(f"⭐ **FOLGA (BYE):** {curr['bye']['name']} recebe +1 vitória.")

    with st.form("swiss_res"):
        res = []
        for i, m in enumerate(curr['matches']):
            t1 = next(t for t in st.session_state.teams if t['id'] == m['home'])
            t2 = next(t for t in st.session_state.teams if t['id'] == m['away'])
            c1, g1c, g2c, c2 = st.columns([2,1,1,2])
            g1 = g1c.number_input(t1['name'], 0, 50, key=f"gs1_{i}")
            g2 = g2c.number_input(t2['name'], 0, 50, key=f"gs2_{i}")
            res.append({'h': t1, 'a': t2, 'g1': g1, 'g2': g2})
        
        if st.form_submit_button("Confirmar Resultados"):
            if curr.get('bye'):
                # Busca o objeto original para atualizar o Bye
                for t in st.session_state.teams:
                    if t['id'] == curr['bye']['id']:
                        t['wins'] += 1
                        t['received_bye'] = True
            
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
                pool = sorted(ativos, key=lambda x: (x['wins'], -x['losses']), reverse=True)
                bye_t = pool.pop() if len(pool)%2 != 0 else None
                new_m = [{'home': pool[i]['id'], 'away': pool[i+1]['id']} for i in range(0, len(pool), 2)]
                st.session_state.rounds.append({'matches': new_m, 'bye': bye_t})
            st.rerun()

elif st.session_state.phase == 'end_swiss':
    st.title("🏁 Suíço Encerrado")
    st.success("Tudo pronto para o Mata-Mata!")
    if st.button("🚀 GERAR MATA-MATA"):
        # Importante: A lógica de setup_playoffs aqui (mesma do código anterior)
        qualified = [t for t in get_rankings() if t['status'] == 'Classificado']
        n = len(qualified)
        
        # (Lógica simplificada de chaveamento 1x8, 2x7...)
        if n >= 8:
            top = qualified[:8]
            m = [{'home': top[i], 'away': top[7-i], 'label': f'Quarta {i+1}'} for i in range(4)]
            st.session_state.playoffs.append({'label': 'Quartas de Final', 'matches': m})
        elif n >= 4:
            top = qualified[:4]
            m = [{'home': top[i], 'away': top[3-i], 'label': f'Semi {i+1}'} for i in range(2)]
            st.session_state.playoffs.append({'label': 'Semifinais', 'matches': m})
        
        st.session_state.phase = 'playoff'
        st.rerun()

elif st.session_state.phase == 'playoff':
    curr_p = st.session_state.playoffs[-1]
    st.title(f"🔥 {curr_p['label']}")
    
    with st.form("p_form"):
        wins = []
        for i, m in enumerate(curr_p['matches']):
            st.subheader(m['label'])
            c1, g1c, g2c, c2 = st.columns([2,1,1,2])
            g1 = g1c.number_input(m['home']['name'], 0, 50, key=f"pg1_{i}")
            g2 = g2c.number_input(m['away']['name'], 0, 50, key=f"pg2_{i}")
            wins.append(m['home'] if g1 > g2 else m['away'])
        
        if st.form_submit_button("Avançar"):
            if len(wins) == 1:
                st.session_state.champion = wins[0]; st.session_state.phase = 'champion'
            else:
                # Gerar Final ou Semis conforme o número de vencedores
                m_next = [{'home': wins[0], 'away': wins[-1], 'label': 'Final'}]
                st.session_state.playoffs.append({'label': 'Final', 'matches': m_next})
            st.rerun()

elif st.session_state.phase == 'champion':
    st.balloons()
    st.header(f"🏆 CAMPEÃO: {st.session_state.champion['name']}")
    if st.button("Novo Torneio"): st.session_state.clear(); st.rerun()
