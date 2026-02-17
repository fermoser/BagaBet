import streamlit as st
import pandas as pd
import random
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAÇÃO INICIAL ---
st.set_page_config(page_title="BAGA GESTOR PRO", layout="wide")
conn = st.connection("gsheets", type=GSheetsConnection)

def carregar_dados():
    try:
        df = conn.read(worksheet="Suico", ttl=0).dropna(how='all')
        if df.empty:
            return pd.DataFrame(columns=['torneio_id', 'rodada', 'a', 'b', 'gols_a', 'gols_b', 'finalizado', 'fase'])
        # Limpeza de colunas fantasmas do Excel
        df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
        return df
    except:
        return pd.DataFrame(columns=['torneio_id', 'rodada', 'a', 'b', 'gols_a', 'gols_b', 'finalizado', 'fase'])

# --- LÓGICA DO SISTEMA SUÍÇO ---
def processar_ranking(df_jogos, tid):
    jogos = df_jogos[df_jogos['torneio_id'] == tid].copy()
    times = {}
    
    # Identificar todos os participantes
    participantes = pd.concat([jogos['a'], jogos['b']]).unique()
    for p in participantes:
        if p and p != "BYE":
            times[p] = {'V': 0, 'D': 0, 'oponentes': [], 'status': 'Ativo', 'Buchholz': 0}

    # Contabilizar Vitórias, Derrotas e Oponentes (Histórico)
    for _, j in jogos[jogos['finalizado'] == 'SIM'].iterrows():
        t1, t2 = j['a'], j['b']
        if t1 in times and t2 in times:
            times[t1]['oponentes'].append(t2)
            times[t2]['oponentes'].append(t1)
            if j['gols_a'] > j['gols_b']:
                times[t1]['V'] += 1; times[t2]['D'] += 1
            else:
                times[t2]['V'] += 1; times[t1]['D'] += 1
        elif t2 == "BYE" and t1 in times:
            times[t1]['V'] += 1  # Vitória automática por Bye

    # Cálculo do Buchholz e Atualização de Status
    for t, info in times.items():
        info['Buchholz'] = sum([times[op]['V'] for op in info['oponentes'] if op in times])
        if info['V'] >= 3: info['status'] = 'Classificado'
        elif info['D'] >= 3: info['status'] = 'Eliminado'
        
    return times

def gerar_rodada_suica(times_info, historico_jogos):
    # Só pareia quem ainda está "Ativo" (nem classificado, nem eliminado)
    ativos = [t for t, info in times_info.items() if info['status'] == 'Ativo']
    # Prioridade 1: Igualdade de Pontuação + Buchholz
    ativos.sort(key=lambda x: (times_info[x]['V'], times_info[x]['Buchholz']), reverse=True)
    
    pareados = []
    escolhidos = set()
    
    # Regra do Bye (Ímpar): Pior campanha que ainda não recebeu Bye
    if len(ativos) % 2 != 0:
        for t in reversed(ativos):
            teve_bye = any(((h['a'] == t and h['b'] == 'BYE') or (h['b'] == t and h['a'] == 'BYE')) for h in historico_jogos)
            if not teve_bye:
                pareados.append((t, "BYE"))
                escolhidos.add(t)
                break

    # Pareamento de Score
    for i in range(len(ativos)):
        t1 = ativos[i]
        if t1 in escolhidos: continue
        
        for j in range(i + 1, len(ativos)):
            t2 = ativos[j]
            if t2 in escolhidos: continue
            
            # Regra de Ineditismo: Proibido enfrentar o mesmo time duas vezes
            ja_jogaram = any(((h['a'] == t1 and h['b'] == t2) or (h['a'] == t2 and h['b'] == t1)) for h in historico_jogos)
            if not ja_jogaram:
                pareados.append((t1, t2))
                escolhidos.add(t1); escolhidos.add(t2)
                break
    return pareados

# --- INTERFACE PRINCIPAL ---
df_total = carregar_dados()

if 'torneio_ativo' not in st.session_state:
    st.title("🏆 BAGA - FORMATO SUÍÇO")
    with st.expander("🆕 Iniciar Novo Torneio (6-16 times)"):
        nome_t = st.text_input("Nome do Evento")
        lista_input = st.text_area("Lista de Jogadores (um por linha)")
        if st.button("Gerar 1ª Rodada"):
            players = [p.strip() for p in lista_input.split('\n') if p.strip()]
            if 6 <= len(players) <= 16:
                random.shuffle(players)
                novos = []
                for i in range(0, len(players), 2):
                    p1 = players[i]; p2 = players[i+1] if i+1 < len(players) else "BYE"
                    novos.append({'torneio_id': nome_t, 'rodada': 1, 'a': p1, 'b': p2, 'gols_a': 1 if p2=="BYE" else 0, 'gols_b': 0, 'finalizado': 'SIM' if p2=="BYE" else 'NÃO', 'fase': 'Suíça'})
                conn.update(worksheet="Suico", data=pd.concat([df_total, pd.DataFrame(novos)]))
                st.cache_data.clear(); st.rerun()
            else: st.error("Mínimo de 6 jogadores.")
    
    st.divider()
    for t_id in df_total['torneio_id'].unique():
        if st.button(f"Abrir: {t_id}", use_container_width=True):
            st.session_state.torneio_ativo = t_id; st.rerun()

else:
    tid = st.session_state.torneio_ativo
    st.header(f"🏟️ {tid}")
    if st.button("⬅️ Sair"): st.session_state.torneio_ativo = None; st.rerun()
    
    stats = processar_ranking(df_total, tid)
    tab1, tab2, tab3 = st.tabs(["🎮 Jogos", "📊 Ranking", "⚙️ Admin"])

    with tab2:
        st.subheader("Classificação Fase Suíça")
        if stats:
            rdf = pd.DataFrame.from_dict(stats, orient='index').sort_values(by=['V', 'Buchholz'], ascending=False)
            st.dataframe(rdf[['V', 'D', 'Buchholz', 'status']], use_container_width=True)

    with tab3:
        if st.text_input("Senha Admin", type="password") == "123":
            jogos_tid = df_total[df_total['torneio_id'] == tid]
            rodada_max = jogos_tid['rodada'].max()
            pendentes = jogos_tid[jogos_tid['finalizado'] == 'NÃO']
            
            ativos = [t for t, info in stats.items() if info['status'] == 'Ativo']
            classificados = [t for t, info in stats.items() if info['status'] == 'Classificado']
            classificados.sort(key=lambda x: (stats[x]['V'], stats[x]['Buchholz']), reverse=True)

            st.info(f"Fase Suíça: {len(ativos)} Jogando | {len(classificados)} Classificados")

            if not pendentes.empty:
                st.warning(f"Aguardando {len(pendentes)} jogos da rodada {rodada_max}")
            elif len(ativos) >= 2:
                if st.button("Gerar Próxima Rodada Suíça"):
                    novos_pares = gerar_rodada_suica(stats, jogos_tid.to_dict('records'))
                    novos_rows = []
                    for p1, p2 in novos_pares:
                        novos_rows.append({'torneio_id': tid, 'rodada': rodada_max+1, 'a': p1, 'b': p2, 'gols_a': 1 if p2=="BYE" else 0, 'gols_b': 0, 'finalizado': 'SIM' if p2=="BYE" else 'NÃO', 'fase': 'Suíça'})
                    conn.update(worksheet="Suico", data=pd.concat([df_total, pd.DataFrame(novos_rows)]))
                    st.cache_data.clear(); st.rerun()
            else:
                st.success("✅ FASE SUÍÇA CONCLUÍDA")
                # MATA-MATA (CASO 1: 3 CLASSIFICADOS - TORNEIO DE 6)
                if len(classificados) == 3:
                    semi_existe = not jogos_tid[jogos_tid['fase'] == 'Semifinal'].empty
                    final_existe = not jogos_tid[jogos_tid['fase'] == 'Final'].empty
                    
                    if not semi_existe:
                        if st.button(f"Gerar Semifinal ({classificados[1]} x {classificados[2]})"):
                            new_row = pd.DataFrame([{'torneio_id': tid, 'rodada': rodada_max+1, 'a': classificados[1], 'b': classificados[2], 'gols_a': 0, 'gols_b': 0, 'finalizado': 'NÃO', 'fase': 'Semifinal'}])
                            conn.update(worksheet="Suico", data=pd.concat([df_total, new_row]))
                            st.cache_data.clear(); st.rerun()
                    elif not final_existe:
                        semi = jogos_tid[jogos_tid['fase'] == 'Semifinal'].iloc[0]
                        if semi['finalizado'] == 'SIM':
                            vencedor = semi['a'] if semi['gols_a'] > semi['gols_b'] else semi['b']
                            if st.button(f"Gerar Final ({classificados[0]} x {vencedor})"):
                                new_row = pd.DataFrame([{'torneio_id': tid, 'rodada': rodada_max+1, 'a': classificados[0], 'b': vencedor, 'gols_a': 0, 'gols_b': 0, 'finalizado': 'NÃO', 'fase': 'Final'}])
                                conn.update(worksheet="Suico", data=pd.concat([df_total, new_row]))
                                st.cache_data.clear(); st.rerun()

            if st.button("🚨 EXCLUIR TUDO"):
                conn.update(worksheet="Suico", data=df_total[df_total['torneio_id'] != tid])
                st.cache_data.clear(); st.session_state.torneio_ativo = None; st.rerun()

    with tab1:
        v_jogos = df_total[df_total['torneio_id'] == tid]
        for r in sorted(v_jogos['rodada'].unique(), reverse=True):
            st.subheader(f"Rodada {r}")
            for idx, row in v_jogos[v_jogos['rodada'] == r].iterrows():
                with st.container(border=True):
                    c1, c2, c3 = st.columns([2,1,2])
                    c1.markdown(f"**{row['a']}**")
                    c2.markdown(f"### {row['gols_a']} x {row['gols_b']}")
                    c3.markdown(f"**{row['b']}**")
                    st.caption(f"Fase: {row['fase']}")
                    if row['finalizado'] == 'NÃO' and row['b'] != 'BYE':
                        with st.expander("Lançar Resultado"):
                            with st.form(f"form_{idx}"):
                                ga = st.number_input("Gols A", 0, 100, key=f"ga_{idx}")
                                gb = st.number_input("Gols B", 0, 100, key=f"gb_{idx}")
                                if st.form_submit_button("Confirmar"):
                                    df_total.at[idx, 'gols_a'] = ga
                                    df_total.at[idx, 'gols_b'] = gb
                                    df_total.at[idx, 'finalizado'] = 'SIM'
                                    conn.update(worksheet="Suico", data=df_total)
                                    st.cache_data.clear(); st.rerun()
