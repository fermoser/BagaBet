import streamlit as st
import pandas as pd
import random
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="BAGA GESTOR PRO", layout="wide", page_icon="🏆")
conn = st.connection("gsheets", type=GSheetsConnection)

# --- FUNÇÕES DE BANCO DE DADOS (CORE) ---
def carregar_dados():
    try:
        df = conn.read(worksheet="Suico", ttl=0).dropna(how='all')
        if df.empty:
            return pd.DataFrame(columns=['torneio_id', 'rodada', 'a', 'b', 'gols_a', 'gols_b', 'finalizado', 'fase', 'pen_a', 'pen_b'])
        # Garantir colunas
        cols_needed = ['torneio_id', 'rodada', 'a', 'b', 'gols_a', 'gols_b', 'finalizado', 'fase', 'pen_a', 'pen_b']
        for c in cols_needed:
            if c not in df.columns: df[c] = 0 if 'gols' in c or 'pen' in c else None
        return df
    except:
        return pd.DataFrame(columns=['torneio_id', 'rodada', 'a', 'b', 'gols_a', 'gols_b', 'finalizado', 'fase', 'pen_a', 'pen_b'])

def salvar_dados(df):
    conn.update(worksheet="Suico", data=df)
    st.cache_data.clear()

# --- LÓGICA ESTATÍSTICA ---
def calcular_stats(df, tid):
    jogos = df[df['torneio_id'] == tid]
    times = pd.concat([jogos['a'], jogos['b']]).unique()
    stats = []
    
    for t in times:
        if not t or t == "BYE": continue
        v, d, gp, gc, sg, bye_count = 0, 0, 0, 0, 0, 0
        history = []
        
        # Filtra jogos do time na fase Suíça
        jogos_t = jogos[(jogos['a'] == t) | (jogos['b'] == t)]
        
        for _, row in jogos_t.iterrows():
            if row['finalizado'] == 'SIM':
                # Identifica oponente
                op = row['b'] if row['a'] == t else row['a']
                if row['fase'] == 'Suíça':
                    history.append(op)
                
                # Gols
                g_pro = row['gols_a'] if row['a'] == t else row['gols_b']
                g_con = row['gols_b'] if row['a'] == t else row['gols_a']
                
                # Penaltis (para desempate visual apenas, critério Copa é V/D)
                p_pro = row['pen_a'] if row['a'] == t else row['pen_b']
                p_con = row['pen_b'] if row['a'] == t else row['pen_a']

                # Lógica de Vitória (Copa: sem empate)
                is_bye = op == "BYE"
                if is_bye:
                    bye_count += 1
                    v += 1
                    gp += 1 # Bye conta 1 gol pró
                    sg += 1
                else:
                    gp += g_pro
                    gc += g_con
                    sg += (g_pro - g_con)
                    
                    if g_pro > g_con: v += 1
                    elif g_con > g_pro: d += 1
                    else: # Empate no tempo normal -> decide nos pênaltis
                        if p_pro > p_con: v += 1
                        else: d += 1

        status = 'Ativo'
        if v >= 3: status = 'Classificado'
        elif d >= 3: status = 'Eliminado'
        
        stats.append({
            'name': t, 'wins': v, 'losses': d, 'goals_for': gp, 
            'goal_diff': sg, 'received_bye': bye_count > 0, 
            'history': history, 'status': status, 'buchholz': 0 
        })
    
    # Calcular Buchholz (Soma das vitórias dos oponentes)
    stats_dict = {t['name']: t for t in stats}
    for t in stats:
        bh = 0
        for op_name in t['history']:
            if op_name in stats_dict and op_name != "BYE":
                bh += stats_dict[op_name]['wins']
        t['buchholz'] = bh
        
    return stats

def get_sorted_rankings(stats_list):
    # Ordena: Vitórias > Buchholz > Não teve Bye > Saldo > Gols Pró
    return sorted(stats_list, key=lambda x: (
        x['wins'], 
        x['buchholz'],
        not x['received_bye'], 
        x['goal_diff'], 
        x['goals_for']
    ), reverse=True)

# --- PAREAMENTO ANTI-TRAVAMENTO ---
def gerar_pareamento_suico(stats_list):
    ativos = [t for t in stats_list if t['status'] == 'Ativo']
    # Ordena para pareamento
    ativos.sort(key=lambda x: (x['wins'], x['buchholz']), reverse=True)
    
    pares = []
    escolhidos = set()
    
    # 1. BYE
    if len(ativos) % 2 != 0:
        # Pega o pior classificado que ainda não teve bye
        candidatos_bye = sorted(ativos, key=lambda x: (x['wins'], not x['received_bye'], x['goal_diff']))
        bye_team = None
        for cand in candidatos_bye:
            if not cand['received_bye']:
                bye_team = cand
                break
        if not bye_team: bye_team = candidatos_bye[0] # Fallback
        
        pares.append((bye_team['name'], "BYE"))
        escolhidos.add(bye_team['name'])
    
    # 2. Pareamento Preferencial (Inédito)
    for i in range(len(ativos)):
        t1 = ativos[i]
        if t1['name'] in escolhidos: continue
        
        for j in range(i + 1, len(ativos)):
            t2 = ativos[j]
            if t2['name'] in escolhidos: continue
            
            if t2['name'] not in t1['history']:
                pares.append((t1['name'], t2['name']))
                escolhidos.add(t1['name']); escolhidos.add(t2['name'])
                break
    
    # 3. Pareamento de Resgate (Repete jogo se necessário)
    sobraram = [t for t in ativos if t['name'] not in escolhidos]
    for i in range(0, len(sobraram), 2):
        if i+1 < len(sobraram):
            pares.append((sobraram[i]['name'], sobraram[i+1]['name']))
        elif sobraram[i]['name'] not in escolhidos: # Caso raríssimo de sobra pós-bye
             pares.append((sobraram[i]['name'], "BYE"))
             
    return pares

# --- UI COMPONENTS ---
def render_sidebar(stats):
    with st.sidebar:
        st.header("📊 Classificação Ao Vivo")
        if stats:
            ranked = get_sorted_rankings(stats)
            display_data = []
            for t in ranked:
                icon = "🟢" if t['status']=='Classificado' else "🔴" if t['status']=='Eliminado' else "⚪"
                display_data.append({
                    'St': icon, 'Time': t['name'], 'V-D': f"{t['wins']}-{t['losses']}",
                    'BH': t['buchholz'], 'SG': t['goal_diff']
                })
            st.dataframe(pd.DataFrame(display_data), hide_index=True, use_container_width=True)
            st.caption("BH: Buchholz (Força dos oponentes)")
        else:
            st.info("Aguardando início.")

# --- APP PRINCIPAL ---
df_total = carregar_dados()

if 'torneio_ativo' not in st.session_state or not st.session_state.torneio_ativo:
    st.title("🏆 BAGA GESTOR PRO")
    with st.expander("🆕 Criar Novo Torneio", expanded=True):
        nome_t = st.text_input("Nome do Torneio")
        lista = st.text_area("Jogadores (um por linha)")
        if st.button("🚀 Iniciar Torneio"):
            nomes = [x.strip() for x in lista.split('\n') if x.strip()]
            if 6 <= len(nomes) <= 20:
                random.shuffle(nomes)
                # Gera Rodada 1
                pares = []
                for i in range(0, len(nomes), 2):
                    pares.append({'torneio_id': nome_t, 'rodada': 1, 'a': nomes[i], 'b': nomes[i+1], 'fase': 'Suíça', 'finalizado': 'NÃO'})
                
                df_novo = pd.concat([df_total, pd.DataFrame(pares)])
                salvar_dados(df_novo)
                st.session_state.torneio_ativo = nome_t
                st.rerun()
            else:
                st.error("Mínimo 6 jogadores.")
    
    st.divider()
    tids = df_total['torneio_id'].unique()
    if len(tids) > 0:
        st.subheader("Carregar Torneio Existente")
        cols = st.columns(4)
        for i, tid in enumerate(tids):
            if cols[i%4].button(f"📂 {tid}", key=tid):
                st.session_state.torneio_ativo = tid
                st.rerun()

else:
    # --- DENTRO DO TORNEIO ---
    tid = st.session_state.torneio_ativo
    df_t = df_total[df_total['torneio_id'] == tid].copy()
    stats = calcular_stats(df_t, tid)
    
    st.markdown(f"## 🏟️ Torneio: **{tid}**")
    if st.button("⬅️ Voltar / Sair"):
        st.session_state.torneio_ativo = None
        st.rerun()
        
    render_sidebar(stats)
    
    # Verifica Fase Atual
    fases_ativas = df_t[df_t['finalizado'] == 'NÃO']['fase'].unique()
    fase_atual = fases_ativas[0] if len(fases_ativas) > 0 else "Intervalo"
    
    # Lógica de Controle
    ativos = [t for t in stats if t['status'] == 'Ativo']
    rodada_max = df_t['rodada'].max()
    jogos_abertos = df_t[(df_t['finalizado'] == 'NÃO') & (df_t['rodada'] == rodada_max)]
    
    # --- ÁREA DE JOGOS ---
    if not jogos_abertos.empty:
        st.subheader(f"⚔️ Jogos em Andamento - {fase_atual}")
        if fase_atual == "Suíça": st.caption(f"Rodada {rodada_max}")
        
        for idx, row in jogos_abertos.iterrows():
            with st.container(border=True):
                c1, c2, c3, c4 = st.columns([2, 1, 1, 2])
                c1.markdown(f"<h3 style='text-align:right'>{row['a']}</h3>", unsafe_allow_html=True)
                
                # Form para lançar resultado
                with st.form(key=f"game_{idx}"):
                    cc1, cc2 = st.columns(2)
                    ga = cc1.number_input("Gols", 0, 99, key=f"ga_{idx}")
                    gb = cc2.number_input("Gols", 0, 99, key=f"gb_{idx}")
                    
                    pa, pb = 0, 0
                    if ga == gb:
                        st.warning("Empate! Insira os pênaltis:")
                        cp1, cp2 = st.columns(2)
                        pa = cp1.number_input(f"Pênaltis {row['a']}", 0, 20, key=f"pa_{idx}")
                        pb = cp2.number_input(f"Pênaltis {row['b']}", 0, 20, key=f"pb_{idx}")
                        
                    if st.form_submit_button("✅ Finalizar Jogo"):
                        if ga == gb and pa == pb:
                            st.error("Pênaltis não podem empatar!")
                        else:
                            # Atualiza no Dataframe Total
                            idx_real = df_total[(df_total['torneio_id'] == tid) & (df_total['a'] == row['a']) & (df_total['b'] == row['b']) & (df_total['rodada'] == row['rodada'])].index[0]
                            df_total.at[idx_real, 'gols_a'] = ga
                            df_total.at[idx_real, 'gols_b'] = gb
                            df_total.at[idx_real, 'pen_a'] = pa
                            df_total.at[idx_real, 'pen_b'] = pb
                            df_total.at[idx_real, 'finalizado'] = 'SIM'
                            salvar_dados(df_total)
                            st.rerun()
                c4.markdown(f"<h3>{row['b']}</h3>", unsafe_allow_html=True)
                
    else:
        # --- INTERVALO / GERAÇÃO DE RODADA ---
        st.success("✅ Rodada Concluída!")
        
        # Se for Suíço e ainda tiver gente ativa
        if len(ativos) >= 2 and fase_atual != "Final":
            c1, c2 = st.columns(2)
            if c1.button("🎲 Gerar Próxima Rodada Suíça"):
                novos_pares = gerar_pareamento_suico(stats)
                novos_dados = []
                for p in novos_pares:
                    is_bye = p[1] == "BYE"
                    novos_dados.append({
                        'torneio_id': tid, 'rodada': rodada_max + 1,
                        'a': p[0], 'b': p[1],
                        'gols_a': 1 if is_bye else 0, 'gols_b': 0,
                        'finalizado': 'SIM' if is_bye else 'NÃO',
                        'fase': 'Suíça'
                    })
                df_novo = pd.concat([df_total, pd.DataFrame(novos_dados)])
                salvar_dados(df_novo)
                st.rerun()
            
            if c2.button("⚠️ Forçar Fim da Fase Suíça (Ir p/ Mata-Mata)"):
                # Cria um registro dummy para marcar transição se necessário, 
                # mas aqui vamos apenas mudar a lógica de exibição baseada no status
                pass # A lógica abaixo cuidará disso
                
        # --- LÓGICA MATA-MATA AUTOMÁTICA ---
        elif len(ativos) <= 1 or fase_atual in ["Semifinal", "Final"]:
            classificados = [t for t in stats if t['status'] == 'Classificado']
            seeds = get_sorted_rankings(classificados)
            
            # Verifica se já tem mata-mata gerado
            tem_semi = not df_t[df_t['fase'] == 'Semifinal'].empty
            tem_final = not df_t[df_t['fase'] == 'Final'].empty
            
            if not tem_semi and not tem_final:
                st.info(f"Classificados: {len(seeds)}")
                if len(seeds) < 2:
                    st.error("Não há classificados suficientes para Mata-Mata.")
                else:
                    if st.button("🔥 Gerar Semifinais / Final"):
                        novos_jogos = []
                        # Exemplo simples: Top 4 vai pra semi, Top 2 direto pra final, ou Top 3 (1 na final, 2 semi)
                        if len(seeds) >= 4:
                            novos_jogos.append({'torneio_id': tid, 'rodada': 90, 'a': seeds[0]['name'], 'b': seeds[3]['name'], 'fase': 'Semifinal', 'finalizado': 'NÃO'})
                            novos_jogos.append({'torneio_id': tid, 'rodada': 90, 'a': seeds[1]['name'], 'b': seeds[2]['name'], 'fase': 'Semifinal', 'finalizado': 'NÃO'})
                        elif len(seeds) == 3:
                            # 1º espera, 2º x 3º
                            novos_jogos.append({'torneio_id': tid, 'rodada': 90, 'a': seeds[1]['name'], 'b': seeds[2]['name'], 'fase': 'Semifinal', 'finalizado': 'NÃO'})
                        elif len(seeds) == 2:
                            novos_jogos.append({'torneio_id': tid, 'rodada': 99, 'a': seeds[0]['name'], 'b': seeds[1]['name'], 'fase': 'Final', 'finalizado': 'NÃO'})
                        
                        salvar_dados(pd.concat([df_total, pd.DataFrame(novos_jogos)]))
                        st.rerun()

            elif tem_semi and not tem_final:
                # Checar se semis acabaram
                semis = df_t[df_t['fase'] == 'Semifinal']
                if semis['finalizado'].all():
                    if st.button("🏆 Gerar Grande Final"):
                        vencedores = []
                        for _, row in semis.iterrows():
                            # Quem ganhou? (Considerando penaltis)
                            if row['gols_a'] > row['gols_b']: vencedores.append(row['a'])
                            elif row['gols_b'] > row['gols_a']: vencedores.append(row['b'])
                            else: vencedores.append(row['a'] if row['pen_a'] > row['pen_b'] else row['b'])
                        
                        # Se tinha 3 jogadores (top 1 esperando)
                        if len(vencedores) == 1: 
                            # Pega o Top 1 do ranking original
                            top_seed = seeds[0]['name']
                            # Verifica se o Top 1 não jogou a semi (se jogou, é bug, mas assumimos logica de 3)
                            salvar_dados(pd.concat([df_total, pd.DataFrame([{'torneio_id': tid, 'rodada': 99, 'a': top_seed, 'b': vencedores[0], 'fase': 'Final', 'finalizado': 'NÃO'}])]))
                        else:
                            salvar_dados(pd.concat([df_total, pd.DataFrame([{'torneio_id': tid, 'rodada': 99, 'a': vencedores[0], 'b': vencedores[1], 'fase': 'Final', 'finalizado': 'NÃO'}])]))
                        st.rerun()
            
            elif tem_final:
                final = df_t[df_t['fase'] == 'Final'].iloc[0]
                if final['finalizado'] == 'SIM':
                    campeao = final['a']
                    if final['gols_b'] > final['gols_a']: campeao = final['b']
                    elif final['gols_a'] == final['gols_b'] and final['pen_b'] > final['pen_a']: campeao = final['b']
                    
                    st.balloons()
                    st.markdown(f"<h1 style='text-align:center; font-size: 80px'>🏆 {campeao} 🏆</h1>", unsafe_allow_html=True)
                    if st.button("Reiniciar / Apagar Torneio"):
                         df_limpo = df_total[df_total['torneio_id'] != tid]
                         salvar_dados(df_limpo)
                         st.session_state.torneio_ativo = None
                         st.rerun()

    # --- HISTÓRICO DE JOGOS ABAIXO ---
    st.divider()
    with st.expander("📜 Histórico de Jogos"):
        st.dataframe(df_t[['fase', 'rodada', 'a', 'gols_a', 'gols_b', 'b', 'pen_a', 'pen_b', 'finalizado']].sort_values(by='rodada', ascending=False), use_container_width=True)
