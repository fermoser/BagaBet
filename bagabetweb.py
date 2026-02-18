import streamlit as st
import pandas as pd
import random
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="BAGA GESTOR PRO", layout="wide", page_icon="🏆")
conn = st.connection("gsheets", type=GSheetsConnection)

# --- INICIALIZAÇÃO ---
if 'teams' not in st.session_state: st.session_state.teams = []
if 'phase' not in st.session_state: st.session_state.phase = 'setup'
if 'rounds' not in st.session_state: st.session_state.rounds = []
if 'playoffs' not in st.session_state: st.session_state.playoffs = []

# --- FUNÇÕES ---

def get_rankings():
    return sorted(st.session_state.teams, key=lambda x: (x['wins'], -x['losses'], x['goal_diff']), reverse=True)

# --- BARRA LATERAL ---
with st.sidebar:
    st.title("📊 Ranking")
    if st.session_state.teams:
        df_rank = pd.DataFrame(get_rankings())
        
        # Criando colunas para visualização
        df_view = df_rank[['name', 'wins', 'losses', 'goal_diff', 'received_bye', 'status']].copy()
        df_view.columns = ['Time', 'V', 'D', 'SG', 'Folga', 'Status']
        
        # GARANTINDO O ÍCONE: Transformamos o booleano em String com Ícone
        df_view['Folga'] = df_view['Folga'].apply(lambda x: "⭐" if x == True else "")

        def style_status(val):
            if val == 'Classificado': return 'background-color: #d4edda; color: black; font-weight: bold'
            if val == 'Eliminado': return 'background-color: #f8d7da; color: black; font-weight: bold'
            return 'background-color: #cce5ff; color: black'

        st.dataframe(df_view.style.applymap(style_status, subset=['Status']), hide_index=True)
    
    if st.button("🗑️ Reiniciar"):
        st.session_state.clear()
        st.rerun()

# --- TELAS ---

if st.session_state.phase == 'setup':
    st.title("🏆 Configuração do Torneio")
    num = st.number_input("Equipes", 2, 32, 8)
    with st.form("setup"):
        names = [st.text_input(f"Time {i+1}", f"Equipe {i+1}", key=f"t{i}") for i in range(num)]
        if st.form_submit_button("GERAR"):
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
    st.title(f"⚽ Rodada {len(st.session_state.rounds)}")
    curr = st.session_state.rounds[-1]
    
    if curr.get('bye'):
        # IMPORTANTE: Pegamos o nome direto do dicionário do Bye
        st.warning(f"⭐ **EM ESPERA (BYE):** {curr['bye']['name']} já garantiu +1 vitória nesta rodada.")

    with st.form("swiss_score"):
        results = []
        for i, m in enumerate(curr['matches']):
            t1 = next(t for t in st.session_state.teams if t['id'] == m['home'])
            t2 = next(t for t in st.session_state.teams if t['id'] == m['away'])
            c1, g1c, g2c, c2 = st.columns([2,1,1,2])
            g1 = g1c.number_input(t1['name'], 0, 50, key=f"g1_{i}")
            g2 = g2c.number_input(t2['name'], 0, 50, key=f"g2_{i}")
            results.append({'h_id': t1['id'], 'a_id': t2['id'], 'g1': g1, 'g2': g2})
        
        if st.form_submit_button("Confirmar Rodada"):
            # 1. PROCESSAR O BYE (CORRIGIDO)
            if curr.get('bye'):
                for t in st.session_state.teams:
                    if t['id'] == curr['bye']['id']:
                        t['wins'] += 1
                        t['received_bye'] = True # Aqui ativa a estrela ⭐

            # 2. PROCESSAR JOGOS
            for r in results:
                t1 = next(t for t in st.session_state.teams if t['id'] == r['h_id'])
                t2 = next(t for t in st.session_state.teams if t['id'] == r['a_id'])
                t1['goals_for'] += r['g1']; t2['goals_for'] += r['g2']
                t1['goal_diff'] += (r['g1'] - r['g2']); t2['goal_diff'] += (r['g2'] - r['g1'])
                if r['g1'] > r['g2']: t1['wins'] += 1; t2['losses'] += 1
                else: t2['wins'] += 1; t1['losses'] += 1
                t1['history'].append(t2['id']); t2['history'].append(t1['id'])
            
            # 3. ATUALIZAR STATUS
            for t in st.session_state.teams:
                if t['wins'] >= 3: t['status'] = 'Classificado'
                elif t['losses'] >= 3: t['status'] = 'Eliminado'
            
            # 4. GERAR PRÓXIMA OU MATA-MATA
            ativos = [t for t in st.session_state.teams if t['status'] == 'Ativo']
            if not ativos:
                st.session_state.phase = 'end_swiss'
            else:
                pool = sorted(ativos, key=lambda x: (x['wins'], -x['losses']), reverse=True)
                new_bye = pool.pop() if len(pool)%2 != 0 else None
                new_m = [{'home': pool[i]['id'], 'away': pool[i+1]['id']} for i in range(0, len(pool), 2)]
                st.session_state.rounds.append({'matches': new_m, 'bye': new_bye})
            st.rerun()

elif st.session_state.phase == 'end_swiss':
    st.title("🏁 Suíço Encerrado")
    st.success("Tudo pronto! Clique para montar o chaveamento.")
    if st.button("🚀 GERAR MATA-MATA"):
        qualified = [t for t in get_rankings() if t['status'] == 'Classificado']
        n = len(qualified)
        
        # Exemplo simples: 1x4, 2x3 se tiver 4 times
        if n >= 4:
            m = [{'home': qualified[0], 'away': qualified[3], 'lbl': 'Semi 1'},
                 {'home': qualified[1], 'away': qualified[2], 'lbl': 'Semi 2'}]
            st.session_state.playoffs.append({'lbl': 'Semifinais', 'matches': m})
        else:
            m = [{'home': qualified[0], 'away': qualified[1], 'lbl': 'Final'}]
            st.session_state.playoffs.append({'lbl': 'Final', 'matches': m})
        
        st.session_state.phase = 'playoff'
        st.rerun()

# (Restante do código de Playoff segue a mesma lógica de atualização...)
