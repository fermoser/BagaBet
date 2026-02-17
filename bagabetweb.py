import streamlit as st
import pandas as pd
import random
from streamlit_gsheets import GSheetsConnection

# --- 1. CONFIGURAÇÃO E CONEXÃO ---
st.set_page_config(page_title="BAGA GESTOR PRO", layout="wide")
conn = st.connection("gsheets", type=GSheetsConnection)

# --- 2. FUNÇÕES DE DADOS E LÓGICA ---
def carregar_dados():
    try:
        df = conn.read(worksheet="Suico", ttl=0).dropna(how='all')
        if df.empty:
            return pd.DataFrame(columns=['torneio_id', 'rodada', 'a', 'b', 'gols_a', 'gols_b', 'finalizado', 'fase'])
        df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
        cols_num = ['gols_a', 'gols_b', 'rodada']
        for c in cols_num:
            if c in df.columns: df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0).astype(int)
        return df
    except:
        return pd.DataFrame(columns=['torneio_id', 'rodada', 'a', 'b', 'gols_a', 'gols_b', 'finalizado', 'fase'])

def calcular_tabela(df_jogos, tid):
    """Calcula Pontos, Vitórias, Empates, Derrotas e Buchholz."""
    jogos = df_jogos[df_jogos['torneio_id'] == tid].copy()
    stats = {}

    # Inicializa todos os times
    todos = pd.concat([jogos['a'], jogos['b']]).unique()
    for t in todos:
        if t and t != "BYE":
            # Pts = Pontos, V=Vitória, E=Empate, D=Derrota
            stats[t] = {'Pts': 0, 'V': 0, 'E': 0, 'D': 0, 'Buchholz': 0, 'Oponentes': [], 'Status': 'Ativo'}

    # Processa resultados
    suico_games = jogos[(jogos['finalizado'] == 'SIM') & (jogos['fase'] == 'Suíça')]
    
    for _, row in suico_games.iterrows():
        t1, t2 = row['a'], row['b']
        
        # Se for jogo normal
        if t1 in stats and t2 in stats:
            stats[t1]['Oponentes'].append(t2)
            stats[t2]['Oponentes'].append(t1)
            
            if row['gols_a'] > row['gols_b']:   # Vitória A
                stats[t1]['V'] += 1; stats[t1]['Pts'] += 3
                stats[t2]['D'] += 1
            elif row['gols_b'] > row['gols_a']: # Vitória B
                stats[t2]['V'] += 1; stats[t2]['Pts'] += 3
                stats[t1]['D'] += 1
            else:                               # Empate (CORREÇÃO AQUI)
                stats[t1]['E'] += 1; stats[t1]['Pts'] += 1
                stats[t2]['E'] += 1; stats[t2]['Pts'] += 1

        # Se for BYE
        elif t2 == "BYE" and t1 in stats:
            stats[t1]['V'] += 1; stats[t1]['Pts'] += 3

    # Calcula Buchholz e Status
    for t, info in stats.items():
        # Buchholz agora soma os PONTOS dos oponentes (mais justo que vitórias)
        info['Buchholz'] = sum([stats[op]['Pts'] for op in info['Oponentes'] if op in stats])
        
        # Regra de Classificação (3 Vitórias garante vaga, ou podemos usar pontos depois)
        if info['V'] >= 3: info['Status'] = 'Classificado'
        elif info['D'] >= 3: info['Status'] = 'Eliminado'
    
    return stats

def tentar_pareamento(stats, historico_jogos):
    ativos = [t for t, info in stats.items() if info['Status'] == 'Ativo']
    # Ordena por PONTOS, depois Buchholz
    ativos.sort(key=lambda x: (stats[x]['Pts'], stats[x]['Buchholz']), reverse=True)
    
    pares = []
    escolhidos = set()

    # BYE (Ímpar)
    if len(ativos) % 2 != 0:
        for t in reversed(ativos):
            ja_teve_bye = any(((h['a']==t and h['b']=='BYE') or (h['b']==t and h['a']=='BYE')) for h in historico_jogos)
            if not ja_teve_bye:
                pares.append((t, "BYE")); escolhidos.add(t); break
    
    # Pareamento
    for i in range(len(ativos)):
        t1 = ativos[i]
        if t1 in escolhidos: continue
        
        encontrou = False
        for j in range(i + 1, len(ativos)):
            t2 = ativos[j]
            if t2 in escolhidos: continue
            
            ja_jogaram = any(((h['a']==t1 and h['b']==t2) or (h['a']==t2 and h['b']==t1)) for h in historico_jogos)
            if not ja_jogaram:
                pares.append((t1, t2)); escolhidos.add(t1); escolhidos.add(t2); encontrou = True; break
        
        if not encontrou and t1 not in escolhidos: return [] 

    return pares

# --- 3. INTERFACE ---
df_total = carregar_dados()

if 'torneio_ativo' not in st.session_state:
    st.title("🏆 BAGA - GESTOR DE TORNEIOS")
    with st.expander("🆕 Novo Torneio (6 Jogadores)"):
        nome_t = st.text_input("Nome")
        lista = st.text_area("Nomes")
        if st.button("Iniciar"):
            nomes = [x.strip() for x in lista.split('\n') if x.strip()]
            if len(nomes) == 6:
                random.shuffle(nomes)
                novos = []
                for i in range(0, 6, 2):
                    novos.append({'torneio_id': nome_t, 'rodada': 1, 'a': nomes[i], 'b': nomes[i+1], 'gols_a': 0, 'gols_b': 0, 'finalizado': 'NÃO', 'fase': 'Suíça'})
                conn.update(worksheet="Suico", data=pd.concat([df_total, pd.DataFrame(novos)]))
                st.cache_data.clear(); st.rerun()
            else: st.error("Insira 6 nomes.")
    
    st.divider()
    for tid in df_total['torneio_id'].unique():
        if st.button(f"Abrir {tid}", use_container_width=True): st.session_state.torneio_ativo = tid; st.rerun()

else:
    tid = st.session_state.torneio_ativo
    st.header(f"🏟️ {tid}")
    if st.button("⬅️ Voltar"): st.session_state.torneio_ativo = None; st.rerun()

    stats = calcular_tabela(df_total, tid)
    t1, t2, t3 = st.tabs(["Jogos", "Classificação", "Admin"])

    with t2:
        if stats:
            df_rank = pd.DataFrame.from_dict(stats, orient='index')
            # Mostra Pts, V, E, D, Buchholz
            df_rank = df_rank[['Pts', 'V', 'E', 'D', 'Buchholz', 'Status']].sort_values(by=['Pts', 'Buchholz'], ascending=False)
            st.dataframe(df_rank, use_container_width=True)

    with t3:
        if st.text_input("Senha", type="password") == "123":
            jogos_tid = df_total[df_total['torneio_id'] == tid]
            rodada_max = jogos_tid['rodada'].max()
            pendentes = jogos_tid[jogos_tid['finalizado'] == 'NÃO']
            ativos = [t for t, i in stats.items() if i['Status'] == 'Ativo']
            
            # Pega o Top 3 PELOS PONTOS para o mata-mata
            top_rank = sorted(stats.keys(), key=lambda x: (stats[x]['Pts'], stats[x]['Buchholz']), reverse=True)
            
            st.info(f"Ativos: {len(ativos)} | Líderes: {top_rank[:3]}")

            if not pendentes.empty:
                st.warning(f"Finalize a rodada {rodada_max}")
            elif len(ativos) >= 2:
                if st.button("Próxima Rodada Suíça"):
                    novos = tentar_pareamento(stats, jogos_tid[jogos_tid['fase']=='Suíça'].to_dict('records'))
                    if novos:
                        l = []
                        for p in novos:
                            l.append({'torneio_id': tid, 'rodada': rodada_max+1, 'a': p[0], 'b': p[1], 'gols_a': 0, 'gols_b': 0, 'finalizado': 'NÃO', 'fase': 'Suíça'})
                        conn.update(worksheet="Suico", data=pd.concat([df_total, pd.DataFrame(l)]))
                        st.cache_data.clear(); st.rerun()
                    else:
                        st.error("Travamento de pareamento! Encerre a fase.")
            else:
                st.success("Fim da Fase Suíça!")
                top3 = top_rank[:3]
                
                semi_ok = not jogos_tid[jogos_tid['fase'] == 'Semifinal'].empty
                final_ok = not jogos_tid[jogos_tid['fase'] == 'Final'].empty

                if not semi_ok:
                    if st.button(f"Gerar Semifinal ({top3[1]} vs {top3[2]})"):
                        novo = pd.DataFrame([{'torneio_id': tid, 'rodada': rodada_max+1, 'a': top3[1], 'b': top3[2], 'gols_a': 0, 'gols_b': 0, 'finalizado': 'NÃO', 'fase': 'Semifinal'}])
                        conn.update(worksheet="Suico", data=pd.concat([df_total, novo]))
                        st.cache_data.clear(); st.rerun()
                elif not final_ok:
                    semi = jogos_tid[jogos_tid['fase'] == 'Semifinal'].iloc[0]
                    if semi['finalizado'] == 'SIM':
                        venc = semi['a'] if semi['gols_a'] > semi['gols_b'] else semi['b'] # Aqui sim, semifinal tem que ter vencedor, se empatar lança penal
                        if semi['gols_a'] == semi['gols_b']: st.error("A semifinal não pode terminar empatada! Use pênaltis.")
                        else:
                            if st.button(f"Gerar Final ({top3[0]} vs {venc})"):
                                novo = pd.DataFrame([{'torneio_id': tid, 'rodada': rodada_max+1, 'a': top3[0], 'b': venc, 'gols_a': 0, 'gols_b': 0, 'finalizado': 'NÃO', 'fase': 'Final'}])
                                conn.update(worksheet="Suico", data=pd.concat([df_total, novo]))
                                st.cache_data.clear(); st.rerun()

            if st.button("RESET TOTAL"):
                conn.update(worksheet="Suico", data=df_total[df_total['torneio_id'] != tid])
                st.cache_data.clear(); st.session_state.torneio_ativo = None; st.rerun()

    with t1:
        jogos = df_total[df_total['torneio_id'] == tid]
        for r in sorted(jogos['rodada'].unique(), reverse=True):
            st.subheader(f"Rodada {r}")
            for idx, row in jogos[jogos['rodada'] == r].iterrows():
                with st.container(border=True):
                    c1, c2, c3 = st.columns([2,1,2])
                    c1.write(f"**{row['a']}**"); c2.write(f"{row['gols_a']} x {row['gols_b']}"); c3.write(f"**{row['b']}**")
                    st.caption(row['fase'])
                    if row['finalizado'] == 'NÃO':
                        with st.expander("Lançar"):
                            with st.form(f"f{idx}"):
                                ga = st.number_input("A", 0, 99, key=f"ga{idx}")
                                gb = st.number_input("B", 0, 99, key=f"gb{idx}")
                                if st.form_submit_button("Ok"):
                                    df_total.at[idx, 'gols_a'] = ga; df_total.at[idx, 'gols_b'] = gb; df_total.at[idx, 'finalizado'] = 'SIM'
                                    conn.update(worksheet="Suico", data=df_total); st.cache_data.clear(); st.rerun()
