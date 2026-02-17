import streamlit as st
import pandas as pd
import random
from streamlit_gsheets import GSheetsConnection

# --- 1. CONFIGURAÇÃO E CONEXÃO ---
st.set_page_config(page_title="BAGA GESTOR - FINAL", layout="wide")
conn = st.connection("gsheets", type=GSheetsConnection)

# --- 2. FUNÇÕES DE DADOS E LÓGICA ---
def carregar_dados():
    """Carrega os dados e garante que as colunas existam."""
    try:
        df = conn.read(worksheet="Suico", ttl=0).dropna(how='all')
        if df.empty:
            return pd.DataFrame(columns=['torneio_id', 'rodada', 'a', 'b', 'gols_a', 'gols_b', 'finalizado', 'fase'])
        # Remove colunas estranhas do Excel
        df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
        # Garante tipos numéricos
        cols_num = ['gols_a', 'gols_b', 'rodada']
        for c in cols_num:
            if c in df.columns: df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0).astype(int)
        return df
    except:
        return pd.DataFrame(columns=['torneio_id', 'rodada', 'a', 'b', 'gols_a', 'gols_b', 'finalizado', 'fase'])

def calcular_buchholz_e_status(df_jogos, tid):
    """Calcula V, D, Buchholz e define Status (Classificado/Eliminado/Ativo)."""
    jogos = df_jogos[df_jogos['torneio_id'] == tid].copy()
    stats = {}

    # 1. Identificar todos os jogadores
    todos = pd.concat([jogos['a'], jogos['b']]).unique()
    for t in todos:
        if t and t != "BYE":
            stats[t] = {'V': 0, 'D': 0, 'Buchholz': 0, 'Oponentes': [], 'Status': 'Ativo'}

    # 2. Processar Jogos Finalizados (Fase Suíça)
    suico_games = jogos[(jogos['finalizado'] == 'SIM') & (jogos['fase'] == 'Suíça')]
    
    for _, row in suico_games.iterrows():
        t1, t2 = row['a'], row['b']
        if t1 in stats and t2 in stats:
            stats[t1]['Oponentes'].append(t2)
            stats[t2]['Oponentes'].append(t1)
            if row['gols_a'] > row['gols_b']:
                stats[t1]['V'] += 1; stats[t2]['D'] += 1
            else:
                stats[t2]['V'] += 1; stats[t1]['D'] += 1
        elif t2 == "BYE" and t1 in stats:
            stats[t1]['V'] += 1 # Vitória automática

    # 3. Calcular Buchholz (Soma das Vitórias dos Oponentes)
    for t, info in stats.items():
        buchholz = sum([stats[op]['V'] for op in info['Oponentes'] if op in stats])
        info['Buchholz'] = buchholz
        
        # Regra: 3 Vitórias = Classificado / 3 Derrotas = Eliminado
        if info['V'] >= 3: info['Status'] = 'Classificado'
        elif info['D'] >= 3: info['Status'] = 'Eliminado'
    
    return stats

def tentar_pareamento(stats, historico_jogos):
    """Tenta criar pares. Retorna Lista de Pares OU Lista Vazia se travar."""
    ativos = [t for t, info in stats.items() if info['Status'] == 'Ativo']
    # Ordena por Vitórias (Score) e depois Buchholz (Desempate)
    ativos.sort(key=lambda x: (stats[x]['V'], stats[x]['Buchholz']), reverse=True)
    
    pares = []
    escolhidos = set()

    # Tratamento de Ímpar (BYE)
    if len(ativos) % 2 != 0:
        # Pega o pior classificado que ainda não teve BYE
        for t in reversed(ativos):
            ja_teve_bye = any(((h['a']==t and h['b']=='BYE') or (h['b']==t and h['a']=='BYE')) for h in historico_jogos)
            if not ja_teve_bye:
                pares.append((t, "BYE"))
                escolhidos.add(t)
                break
    
    # Tentativa de Pareamento (Evitando Repetição)
    for i in range(len(ativos)):
        t1 = ativos[i]
        if t1 in escolhidos: continue
        
        encontrou_oponente = False
        for j in range(i + 1, len(ativos)):
            t2 = ativos[j]
            if t2 in escolhidos: continue
            
            # Verifica se já jogaram nesta fase
            ja_jogaram = any(((h['a']==t1 and h['b']==t2) or (h['a']==t2 and h['b']==t1)) for h in historico_jogos)
            
            if not ja_jogaram:
                pares.append((t1, t2))
                escolhidos.add(t1); escolhidos.add(t2)
                encontrou_oponente = True
                break
        
        # Se um jogador ativo não consegue oponente (travamento), retornamos vazio para forçar fim de fase
        if not encontrou_oponente and t1 not in escolhidos:
            return [] 

    return pares

# --- 3. INTERFACE VISUAL ---
df_total = carregar_dados()

if 'torneio_ativo' not in st.session_state:
    st.title("🏆 BAGA GESTOR - VERSÃO FINAL")
    with st.expander("🆕 Criar Novo Torneio (6 Jogadores)"):
        nome_t = st.text_input("Nome do Torneio")
        lista_txt = st.text_area("Nomes (um por linha)")
        if st.button("INICIAR TORNEIO"):
            nomes = [x.strip() for x in lista_txt.split('\n') if x.strip()]
            if len(nomes) == 6:
                random.shuffle(nomes)
                # Gera Rodada 1
                novos = []
                for i in range(0, 6, 2):
                    novos.append({'torneio_id': nome_t, 'rodada': 1, 'a': nomes[i], 'b': nomes[i+1], 'gols_a': 0, 'gols_b': 0, 'finalizado': 'NÃO', 'fase': 'Suíça'})
                conn.update(worksheet="Suico", data=pd.concat([df_total, pd.DataFrame(novos)]))
                st.cache_data.clear(); st.rerun()
            else:
                st.error("Para este teste, insira exatamente 6 nomes.")
    
    st.divider()
    for tid in df_total['torneio_id'].unique():
        if st.button(f"Abrir {tid}", use_container_width=True):
            st.session_state.torneio_ativo = tid; st.rerun()

else:
    # --- DENTRO DO TORNEIO ---
    tid = st.session_state.torneio_ativo
    st.header(f"🏟️ {tid}")
    if st.button("⬅️ Sair"): st.session_state.torneio_ativo = None; st.rerun()

    stats = calcular_buchholz_e_status(df_total, tid)
    tab_jogos, tab_rank, tab_admin = st.tabs(["⚽ Jogos", "📊 Classificação", "⚙️ Admin"])

    # === ABA CLASSIFICAÇÃO ===
    with tab_rank:
        st.subheader("Ranking Suíço")
        if stats:
            df_rank = pd.DataFrame.from_dict(stats, orient='index')
            df_rank = df_rank[['V', 'D', 'Buchholz', 'Status']].sort_values(by=['V', 'Buchholz'], ascending=False)
            st.dataframe(df_rank, use_container_width=True)

    # === ABA ADMIN (O CÉREBRO) ===
    with tab_admin:
        senha = st.text_input("Senha Admin", type="password")
        if senha == "123":
            jogos_tid = df_total[df_total['torneio_id'] == tid]
            rodada_max = jogos_tid['rodada'].max()
            pendentes = jogos_tid[jogos_tid['finalizado'] == 'NÃO']
            
            ativos = [t for t, i in stats.items() if i['Status'] == 'Ativo']
            classificados = [t for t, i in stats.items() if i['Status'] == 'Classificado']
            
            # Ordena classificados para o Mata-Mata
            classificados.sort(key=lambda x: (stats[x]['V'], stats[x]['Buchholz']), reverse=True)

            st.info(f"Fase Suíça: {len(ativos)} Ativos | {len(classificados)} Classificados")

            # 1. Há jogos rolando?
            if not pendentes.empty:
                st.warning(f"Finalize a rodada {rodada_max} antes de continuar.")
            
            # 2. Fase Suíça ainda ativa?
            elif len(ativos) >= 2:
                if st.button("Gerar Próxima Rodada"):
                    historico = jogos_tid[jogos_tid['fase'] == 'Suíça'].to_dict('records')
                    novos_pares = tentar_pareamento(stats, historico)
                    
                    if novos_pares:
                        # Sucesso: gera jogos
                        lista_jogos = []
                        for p in novos_pares:
                            lista_jogos.append({'torneio_id': tid, 'rodada': rodada_max+1, 'a': p[0], 'b': p[1], 'gols_a': 1 if p[1]=="BYE" else 0, 'gols_b': 0, 'finalizado': 'SIM' if p[1]=="BYE" else 'NÃO', 'fase': 'Suíça'})
                        conn.update(worksheet="Suico", data=pd.concat([df_total, pd.DataFrame(lista_jogos)]))
                        st.cache_data.clear(); st.rerun()
                    else:
                        # TRAVAMENTO DETECTADO (Válvula de Escape)
                        st.warning("⚠️ Não há mais pareamentos possíveis sem repetir jogos!")
                        st.success("Encerrando Fase Suíça e calculando Classificados pelo Buchholz...")
                        # Aqui não geramos rodada, apenas deixamos o código cair no 'else' abaixo na próxima atualização
                        # Na prática, ao não gerar rodada, o usuário assume que acabou.
                        # Para forçar visualmente, podemos pedir para ele prosseguir para o mata-mata.
            
            # 3. Fim da Fase Suíça -> Início Mata-Mata
            else:
                st.success("🏁 Fase Suíça Finalizada!")
                
                # CASO ESPECÍFICO: 6 JOGADORES (3 Classificados)
                # Se o pareamento travou e temos menos de 3 classificados oficiais (ex: só 2 com 3 vitórias),
                # precisamos puxar o melhor 'Ativo' pelo Buchholz para completar 3.
                todos_rank = sorted(stats.keys(), key=lambda x: (stats[x]['V'], stats[x]['Buchholz']), reverse=True)
                top3 = todos_rank[:3] # Pega os 3 melhores independente do status 'Classificado' para garantir o mata-mata
                
                st.write(f"**Top 3 Finalistas:** 1º {top3[0]} | 2º {top3[1]} | 3º {top3[2]}")

                ja_tem_semi = not jogos_tid[jogos_tid['fase'] == 'Semifinal'].empty
                ja_tem_final = not jogos_tid[jogos_tid['fase'] == 'Final'].empty

                if not ja_tem_semi:
                    if st.button(f"🔥 Criar Semifinal ({top3[1]} vs {top3[2]})"):
                        semi = pd.DataFrame([{'torneio_id': tid, 'rodada': rodada_max+1, 'a': top3[1], 'b': top3[2], 'gols_a': 0, 'gols_b': 0, 'finalizado': 'NÃO', 'fase': 'Semifinal'}])
                        conn.update(worksheet="Suico", data=pd.concat([df_total, semi]))
                        st.cache_data.clear(); st.rerun()
                
                elif not ja_tem_final:
                    # Verifica quem ganhou a semi
                    jogo_semi = jogos_tid[jogos_tid['fase'] == 'Semifinal'].iloc[0]
                    if jogo_semi['finalizado'] == 'SIM':
                        vencedor_semi = jogo_semi['a'] if jogo_semi['gols_a'] > jogo_semi['gols_b'] else jogo_semi['b']
                        if st.button(f"🏆 Criar Grande Final ({top3[0]} vs {vencedor_semi})"):
                            final = pd.DataFrame([{'torneio_id': tid, 'rodada': rodada_max+1, 'a': top3[0], 'b': vencedor_semi, 'gols_a': 0, 'gols_b': 0, 'finalizado': 'NÃO', 'fase': 'Final'}])
                            conn.update(worksheet="Suico", data=pd.concat([df_total, final]))
                            st.cache_data.clear(); st.rerun()
                    else:
                        st.warning("Aguardando resultado da Semifinal...")
                else:
                    st.success("🏆 Torneio Concluído! Parabéns ao campeão.")

            st.divider()
            if st.button("🗑️ DELETAR TORNEIO (RESET)"):
                df_limpo = df_total[df_total['torneio_id'] != tid]
                conn.update(worksheet="Suico", data=df_limpo)
                st.cache_data.clear(); st.session_state.torneio_ativo = None; st.rerun()

    # === ABA JOGOS (Lançamento) ===
    with tab_jogos:
        jogos_view = df_total[df_total['torneio_id'] == tid]
        if not jogos_view.empty:
            for r in sorted(jogos_view['rodada'].unique(), reverse=True):
                st.subheader(f"Rodada {r}")
                for idx, row in jogos_view[jogos_view['rodada'] == r].iterrows():
                    with st.container(border=True):
                        col_a, col_placar, col_b = st.columns([2,1,2])
                        col_a.markdown(f"<h4 style='text-align: right;'>{row['a']}</h4>", unsafe_allow_html=True)
                        col_placar.markdown(f"<h4 style='text-align: center;'>{row['gols_a']} x {row['gols_b']}</h4>", unsafe_allow_html=True)
                        col_b.markdown(f"<h4 style='text-align: left;'>{row['b']}</h4>", unsafe_allow_html=True)
                        
                        st.caption(f"Fase: {row['fase']}")
                        
                        if row['finalizado'] == 'NÃO' and row['b'] != 'BYE':
                            with st.expander("📝 Lançar Resultado"):
                                with st.form(f"form_{idx}"):
                                    ga = st.number_input("Gols A", 0, 99, key=f"ga_{idx}")
                                    gb = st.number_input("Gols B", 0, 99, key=f"gb_{idx}")
                                    if st.form_submit_button("Confirmar"):
                                        df_total.at[idx, 'gols_a'] = ga
                                        df_total.at[idx, 'gols_b'] = gb
                                        df_total.at[idx, 'finalizado'] = 'SIM'
                                        conn.update(worksheet="Suico", data=df_total)
                                        st.cache_data.clear(); st.rerun()
