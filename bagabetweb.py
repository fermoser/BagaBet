import streamlit as st
import pandas as pd
import random
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="BAGA GESTOR PRO", layout="wide", page_icon="🏆")

# --- CONEXÃO GOOGLE SHEETS ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    SHEET_ENABLED = True
except Exception as e:
    st.error(f"Erro de Conexão com Sheets: {e}")
    SHEET_ENABLED = False

# --- INICIALIZAÇÃO DE ESTADO ---
# bye_history: Lista de IDs que já receberam bye neste torneio
keys = {
    'tournament_name': "", 
    'teams': [], 
    'phase': 'setup', 
    'rounds': [], 
    'playoffs': [], 
    'waiting_next': [], 
    'champion': None, 
    'second_place': None, 
    'third_place': None, 
    'bye_history': [] 
}

for key, value in keys.items():
    if key not in st.session_state: st.session_state[key] = value

# --- FUNÇÕES AUXILIARES ---

def get_rankings():
    """
    Ordena os times para classificação e pareamento.
    Critérios: Vitórias > Saldo > Gols Pró > Menos Gols Contra > Menos Derrotas
    """
    return sorted(st.session_state.teams, 
                  key=lambda x: (int(x['wins']), int(x['goal_diff']), int(x['goals_for']), -int(x['goals_against']), -int(x['losses'])), 
                  reverse=True)

def select_bye_team(candidates):
    """
    Seleciona um time para o BYE garantindo que ele não tenha recebido antes.
    """
    # Filtra quem NUNCA teve bye
    never_had_bye = [t for t in candidates if t['id'] not in st.session_state.bye_history]
    
    # Se todos já tiveram (caso raro), reseta a restrição para este sorteio
    if not never_had_bye:
        pool = candidates
    else:
        pool = never_had_bye
        
    if not pool: return None
    
    # Sorteia um da lista filtrada
    selected = random.choice(pool)
    return selected

def save_to_sheets():
    """
    Salva no Google Sheets de forma acumulativa (não apaga torneios anteriores).
    """
    if not SHEET_ENABLED or not st.session_state.teams or st.session_state.phase == 'setup': 
        return
    
    try:
        df_current = pd.DataFrame(st.session_state.teams)
        df_current['tournament_name'] = st.session_state.tournament_name
        
        # Padroniza visualmente o BYE e converte tudo para texto
        if 'received_bye' in df_current.columns:
            df_current['received_bye'] = df_current['received_bye'].apply(
                lambda x: "SIM" if str(x).upper() in ["TRUE", "SIM", "1"] else "NÃO"
            )
        df_current = df_current.astype(str)

        try:
            # Tenta ler o histórico
            existing_data = conn.read(worksheet="suico", ttl=0)
            
            if existing_data is not None and not existing_data.empty:
                # Remove apenas os dados antigos DESTE torneio específico para atualizar
                # Mantém os dados de outros torneios (histórico)
                other_tournaments = existing_data[existing_data['tournament_name'] != st.session_state.tournament_name]
                df_final = pd.concat([other_tournaments, df_current], ignore_index=True)
            else:
                df_final = df_current
        except:
            df_final = df_current

        conn.update(worksheet="suico", data=df_final)
        st.toast(f"💾 Salvo: {st.session_state.tournament_name}")
        
    except Exception as e:
        st.error(f"⚠️ Erro ao salvar: {e}")

# --- SIDEBAR (RANKING) ---
with st.sidebar:
    st.title("📊 Classificação")
    if st.session_state.tournament_name:
        st.caption(f"🏆 {st.session_state.tournament_name}")
    
    if st.session_state.teams:
        # Prepara dados para exibição (converte para int para ordenar certo)
        df_rank = pd.DataFrame(st.session_state.teams)
        cols_num = ['wins', 'losses', 'goal_diff', 'goals_for', 'goals_against']
        for col in cols_num:
            df_rank[col] = pd.to_numeric(df_rank[col], errors='coerce').fillna(0).astype(int)
            
        df_rank = df_rank.sort_values(by=['wins', 'goal_diff', 'goals_for', 'goals_against', 'losses'], 
                                     ascending=[False, False, False, True, True])
        
        df_view = df_rank[['name', 'wins', 'losses', 'goal_diff', 'goals_for', 'goals_against', 'received_bye', 'status']].copy()
        df_view.columns = ['Time', 'V', 'D', 'SG', 'GP', 'GC', '⭐', 'Status']
        
        # Estrela visual para quem tem Bye ATIVO
        df_view['⭐'] = df_view['⭐'].apply(lambda x: "⭐" if str(x).upper() in ["TRUE", "SIM", "1"] else "")

        def color_status(val):
            if val == 'Classificado': return 'background-color: #d4edda; color: black; font-weight: bold'
            if val == 'Eliminado': return 'background-color: #f8d7da; color: black; font-weight: bold'
            return 'background-color: #cce5ff; color: black; font-weight: bold'

        st.dataframe(df_view.style.applymap(color_status, subset=['Status']), 
                     hide_index=True, use_container_width=True)
    
    st.divider()
    if st.button("🗑️ NOVO TORNEIO / RESET"):
        for k in keys: st.session_state[k] = keys[k]
        st.rerun()

# --- TELAS PRINCIPAIS ---

# 1. SETUP DO TORNEIO
if st.session_state.phase == 'setup':
    st.title("🏆 Configuração do Torneio")
    c1, c2 = st.columns([2, 1])
    t_name = c1.text_input("Nome do Torneio (Obrigatório para Histórico)")
    num = c2.number_input("Quantidade de Equipes", 2, 64, 8)
    
    with st.form("setup_form"):
        names = [st.text_input(f"Time {i+1}", f"Equipe {i+1}", key=f"inp_{i}") for i in range(num)]
        
        if st.form_submit_button("🏁 INICIAR COMPETIÇÃO"):
            if not t_name:
                st.error("⚠️ Por favor, digite um nome para o torneio!")
            else:
                st.session_state.tournament_name = t_name
                # Criação dos times
                st.session_state.teams = [{
                    'id': i, 'name': n, 
                    'wins': 0, 'losses': 0, 'goal_diff': 0, 
                    'goals_for': 0, 'goals_against': 0, 
                    'received_bye': False, 'status': 'Ativo'
                } for i, n in enumerate(names)]
                
                st.session_state.phase = 'swiss'
                
                # Sorteio da 1ª Rodada (Aleatório)
                pool = st.session_state.teams.copy()
                random.shuffle(pool)
                
                bye_team = None
                if len(pool) % 2 != 0:
                    bye_team = select_bye_team(pool) # Usa a função inteligente
                    if bye_team:
                        # Marca no histórico e no status atual
                        st.session_state.bye_history.append(bye_team['id'])
                        for t in st.session_state.teams:
                            if t['id'] == bye_team['id']: t['received_bye'] = True
                        pool = [t for t in pool if t['id'] != bye_team['id']]
                
                matches = [{'home': pool[i]['id'], 'away': pool[i+1]['id']} for i in range(0, len(pool), 2)]
                st.session_state.rounds = [{'matches': matches, 'bye': bye_team}]
                
                save_to_sheets()
                st.rerun()

# 2. FASE SUÍÇA
elif st.session_state.phase == 'swiss':
    st.title(f"⚽ {st.session_state.tournament_name} - Fase Suíça (Rodada {len(st.session_state.rounds)})")
    
    curr = st.session_state.rounds[-1]
    if curr.get('bye'): 
        st.info(f"⭐ **FOLGA (BYE):** {curr['bye']['name']} (Ganha +1 Vitória)")

    with st.form("swiss_matches"):
        results = []
        is_ready = True
        
        # Renderiza jogos
        for i, m in enumerate(curr['matches']):
            t1 = next(t for t in st.session_state.teams if t['id'] == m['home'])
            t2 = next(t for t in st.session_state.teams if t['id'] == m['away'])
            
            st.markdown(f"**{t1['name']} vs {t2['name']}**")
            c1, g1c, g2c, c2 = st.columns([2, 1, 1, 2])
            g1 = g1c.number_input("Gols", 0, 99, key=f"g1_{i}", label_visibility="collapsed")
            g2 = g2c.number_input("Gols", 0, 99, key=f"g2_{i}", label_visibility="collapsed")
            
            p1, p2 = 0, 0
            # Lógica de Pênaltis se houver empate
            if g1 == g2:
                pc1, pc2 = st.columns(2)
                p1 = pc1.number_input(f"Pên {t1['name']}", 0, 50, key=f"p1_{i}")
                p2 = pc2.number_input(f"Pên {t2['name']}", 0, 50, key=f"p2_{i}")
                if p1 == p2: is_ready = False
            
            results.append({'h': t1, 'a': t2, 'g1': g1, 'g2': g2, 'p1': p1, 'p2': p2})
            st.divider()

        if st.form_submit_button("Confirmar Rodada"):
            if not is_ready:
                st.error("⚠️ Jogos empatados precisam de decisão nos pênaltis!")
            else:
                # 1. Processa o Bye (se houver)
                if curr.get('bye'):
                    for t in st.session_state.teams:
                        if t['id'] == curr['bye']['id']: 
                            t['wins'] = int(t['wins']) + 1
                
                # 2. Processa os Resultados
                for r in results:
                    # Gols e Saldo
                    r['h']['goals_for'] = int(r['h']['goals_for']) + r['g1']
                    r['h']['goals_against'] = int(r['h']['goals_against']) + r['g2']
                    r['a']['goals_for'] = int(r['a']['goals_for']) + r['g2']
                    r['a']['goals_against'] = int(r['a']['goals_against']) + r['g1']
                    r['h']['goal_diff'] = r['h']['goals_for'] - r['h']['goals_against']
                    r['a']['goal_diff'] = r['a']['goals_for'] - r['a']['goals_against']
                    
                    # Vitória/Derrota (considerando pênaltis)
                    if r['g1'] > r['g2'] or (r['g1'] == r['g2'] and r['p1'] > r['p2']):
                        r['h']['wins'] = int(r['h']['wins']) + 1
                        r['a']['losses'] = int(r['a']['losses']) + 1
                    else:
                        r['a']['wins'] = int(r['a']['wins']) + 1
                        r['h']['losses'] = int(r['h']['losses']) + 1

                # 3. Atualiza Status (Classificado/Eliminado)
                for t in st.session_state.teams:
                    if int(t['wins']) >= 3: t['status'] = 'Classificado'
                    elif int(t['losses']) >= 3: t['status'] = 'Eliminado'
                
                # 4. Gera Próxima Rodada
                active_teams = [t for t in st.session_state.teams if t['status'] == 'Ativo']
                
                if not active_teams:
                    st.session_state.phase = 'end_swiss'
                else:
                    # Ordena pelo ranking para pareamento equilibrado (Suíço)
                    pool = sorted(active_teams, 
                                  key=lambda x: (int(x['wins']), int(x['goal_diff'])), 
                                  reverse=True)
                    
                    # Reseta estrela visual
                    for t in st.session_state.teams: t['received_bye'] = False
                    
                    bye_team = None
                    if len(pool) % 2 != 0:
                        bye_team = select_bye_team(pool)
                        if bye_team:
                            st.session_state.bye_history.append(bye_team['id'])
                            for t in st.session_state.teams:
                                if t['id'] == bye_team['id']: t['received_bye'] = True
                            pool = [t for t in pool if t['id'] != bye_team['id']]

                    matches = [{'home': pool[i]['id'], 'away': pool[i+1]['id']} for i in range(0, len(pool), 2)]
                    st.session_state.rounds.append({'matches': matches, 'bye': bye_team})
                
                save_to_sheets()
                st.rerun()

# 3. TRANSIÇÃO
elif st.session_state.phase == 'end_swiss':
    st.title("🏁 Fim da Fase Suíça")
    st.success("Todos os classificados foram definidos!")
    
    if st.button("🚀 GERAR MATA-MATA (1º vs 8º, 2º vs 7º...)"):
        qualified = [t for t in get_rankings() if t['status'] == 'Classificado']
        n = len(qualified)
        
        if n < 2:
            st.error("Não há times suficientes classificados.")
        else:
            # Reseta Byes visuais
            st.session_state.waiting_next = []
            for t in st.session_state.teams: t['received_bye'] = False
            
            # Lógica de Byes por Ranking no Mata-Mata (Seeding)
            # Se não for potência de 2 (2, 4, 8, 16, 32...), os melhores rankings folgam
            to_play = qualified
            
            if n == 6: # Exemplo: 1º e 2º folgam
                st.session_state.waiting_next = qualified[:2]
                to_play = qualified[2:]
            elif n == 5:
                st.session_state.waiting_next = qualified[:3]
                to_play = qualified[3:]
            elif n == 3:
                st.session_state.waiting_next = [qualified[0]]
                to_play = qualified[1:]
            
            # Aplica estrela de Bye para quem espera a próxima fase
            wait_ids = [w['id'] for w in st.session_state.waiting_next]
            for t in st.session_state.teams:
                if t['id'] in wait_ids: t['received_bye'] = True

            # Cria os jogos: 1º do grupo de jogo vs Último do grupo de jogo
            # Ex: Se sobraram 4 times (3º, 4º, 5º, 6º). 
            # 3º vs 6º e 4º vs 5º.
            matches = []
            num_play = len(to_play)
            for i in range(num_play // 2):
                home = to_play[i]
                away = to_play[-(i+1)] # Pega do final da lista (Melhor x Pior relativo)
                matches.append({'home': home, 'away': away, 'label': 'Eliminatória'})

            st.session_state.playoffs = [{'label': "Mata-Mata", 'matches': matches}]
            st.session_state.phase = 'playoff'
            save_to_sheets()
            st.rerun()

# 4. MATA-MATA (PLAYOFFS)
elif st.session_state.phase == 'playoff':
    st.title(f"🔥 Mata-Mata - {st.session_state.tournament_name}")
    
    venc, derr = [], []
    is_ready = True

    # Renderiza todas as rodadas ativas
    with st.form("playoff_form"):
        for idx, p_round in enumerate(st.session_state.playoffs):
            st.subheader(f"📍 {p_round['label']}")
            
            for i, m in enumerate(p_round['matches']):
                c1, g1c, g2c, c2 = st.columns([2, 1, 1, 2])
                st.markdown(f"**{m['home']['name']} vs {m['away']['name']}**")
                
                g1 = g1c.number_input("Gols", 0, 99, key=f"pg1_{idx}_{i}", label_visibility="collapsed")
                g2 = g2c.number_input("Gols", 0, 99, key=f"pg2_{idx}_{i}", label_visibility="collapsed")
                
                p1, p2 = 0, 0
                if g1 == g2:
                    pc1, pc2 = st.columns(2)
                    p1 = pc1.number_input(f"Pên {m['home']['name']}", 0, 99, key=f"pp1_{idx}_{i}")
                    p2 = pc2.number_input(f"Pên {m['away']['name']}", 0, 99, key=f"pp2_{idx}_{i}")
                    if p1 == p2: is_ready = False
                
                # Identifica vencedor
                winner = m['home'] if (g1 > g2 or (g1==g2 and p1>p2)) else m['away']
                loser = m['away'] if winner['id'] == m['home']['id'] else m['home']
                
                venc.append({'t': winner, 'lbl': p_round['label'], 'g': g1, 'gc': g2})
                derr.append({'t': loser, 'lbl': p_round['label'], 'g': g2, 'gc': g1})
                st.divider()

        btn_text = "Confirmar Resultados"
        if any(r['label'] == "Grande Final" for r in st.session_state.playoffs):
            btn_text = "🏆 FINALIZAR TORNEIO"
            
        if st.form_submit_button(btn_text):
            if not is_ready:
                st.error("⚠️ Resolva os empates nos pênaltis!")
            else:
                # Atualiza stats globais
                for item in (venc + derr):
                    t_obj = next(t for t in st.session_state.teams if t['id'] == item['t']['id'])
                    t_obj['goals_for'] = int(t_obj['goals_for']) + item['g']
                    t_obj['goals_against'] = int(t_obj['goals_against']) + item['gc']
                    t_obj['goal_diff'] = t_obj['goals_for'] - t_obj['goals_against']
                    # Adiciona derrota se estiver na lista de perdedores
                    if any(d['t']['id'] == t_obj['id'] for d in derr): 
                        t_obj['losses'] = int(t_obj['losses']) + 1

                # Lógica de Progressão
                final_match = next((v for v in venc if v['lbl'] == "Grande Final"), None)
                
                if final_match:
                    # FIM DO TORNEIO
                    st.session_state.champion = final_match['t']
                    st.session_state.second_place = next(d['t'] for d in derr if d['lbl'] == "Grande Final")
                    third = next((v for v in venc if v['lbl'] == "Disputa de 3º Lugar"), None)
                    if third: st.session_state.third_place = third['t']
                    st.session_state.phase = 'champion'
                else:
                    # PROXIMA FASE
                    # Pega quem estava esperando (Byes do mata-mata) + Vencedores
                    proximos = st.session_state.waiting_next + [v['t'] for v in venc]
                    st.session_state.waiting_next = [] # Limpa espera
                    for t in st.session_state.teams: t['received_bye'] = False # Limpa estrelas
                    
                    if len(proximos) == 2:
                        # GERA FINAL
                        st.session_state.playoffs = [{'label': "Grande Final", 'matches': [{'home': proximos[0], 'away': proximos[1]}]}]
                        if len(derr) >= 2:
                            st.session_state.playoffs.append({'label': "Disputa de 3º Lugar", 'matches': [{'home': derr[0]['t'], 'away': derr[1]['t']}]})
                    else:
                        # GERA SEMIFINAL ou QUARTAS (Sempre Melhor Rank x Pior Rank)
                        # Re-ordena por ranking para manter a lógica 1x8, 2x7...
                        proximos = sorted(proximos, key=lambda x: (int(x['wins']), int(x['goal_diff'])), reverse=True)
                        new_matches = [{'home': proximos[i], 'away': proximos[-(i+1)]} for i in range(len(proximos)//2)]
                        st.session_state.playoffs = [{'label': "Próxima Fase", 'matches': new_matches}]
                
                save_to_sheets()
                st.rerun()

# 5. PÓDIO
elif st.session_state.phase == 'champion':
    st.balloons()
    save_to_sheets()
    
    st.markdown(f"<h1 style='text-align: center;'>🏆 {st.session_state.tournament_name} 🏆</h1>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    
    if st.session_state.second_place: 
        c1.info(f"🥈 **2º LUGAR**\n\n## {st.session_state.second_place['name']}")
    
    if st.session_state.champion: 
        c2.success(f"🥇 **CAMPEÃO**\n\n# {st.session_state.champion['name']}")
        
    if st.session_state.third_place: 
        c3.warning(f"🥉 **3º LUGAR**\n\n## {st.session_state.third_place['name']}")

    st.divider()
    if st.button("🔄 COMEÇAR NOVO TORNEIO"):
        for k in keys: st.session_state[k] = keys[k]
        st.rerun()
