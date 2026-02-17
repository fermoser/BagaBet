import streamlit as st
import pandas as pd
import random
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="BAGA GESTOR - ANTI-TRAVAMENTO", layout="wide")
conn = st.connection("gsheets", type=GSheetsConnection)

def carregar_dados():
    try:
        df = conn.read(worksheet="Suico", ttl=0).dropna(how='all')
        if df.empty:
            return pd.DataFrame(columns=['torneio_id', 'rodada', 'a', 'b', 'gols_a', 'gols_b', 'finalizado', 'fase'])
        df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
        for c in ['gols_a', 'gols_b', 'rodada']:
            if c in df.columns: df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0).astype(int)
        return df
    except:
        return pd.DataFrame(columns=['torneio_id', 'rodada', 'a', 'b', 'gols_a', 'gols_b', 'finalizado', 'fase'])

def calcular_tabela(df_jogos, tid):
    jogos = df_jogos[df_jogos['torneio_id'] == tid].copy()
    stats = {}
    todos = pd.concat([jogos['a'], jogos['b']]).unique()
    for t in todos:
        if t and t != "BYE":
            stats[t] = {'Pts': 0, 'V': 0, 'E': 0, 'D': 0, 'Buchholz': 0, 'Oponentes': [], 'Status': 'Ativo'}

    suico_games = jogos[(jogos['finalizado'] == 'SIM') & (jogos['fase'] == 'Suíça')]
    for _, row in suico_games.iterrows():
        t1, t2 = row['a'], row['b']
        if t1 in stats and t2 in stats:
            stats[t1]['Oponentes'].append(t2); stats[t2]['Oponentes'].append(t1)
            if row['gols_a'] > row['gols_b']:
                stats[t1]['V'] += 1; stats[t1]['Pts'] += 3; stats[t2]['D'] += 1
            elif row['gols_b'] > row['gols_a']:
                stats[t2]['V'] += 1; stats[t2]['Pts'] += 3; stats[t1]['D'] += 1
            else:
                stats[t1]['E'] += 1; stats[t1]['Pts'] += 1; stats[t2]['E'] += 1; stats[t2]['Pts'] += 1
        elif t2 == "BYE" and t1 in stats:
            stats[t1]['V'] += 1; stats[t1]['Pts'] += 3

    for t, info in stats.items():
        info['Buchholz'] = sum([stats[op]['Pts'] for op in info['Oponentes'] if op in stats])
        if info['V'] >= 3: info['Status'] = 'Classificado'
        elif info['D'] >= 3: info['Status'] = 'Eliminado'
    return stats

def tentar_pareamento_flexivel(stats, historico_jogos):
    ativos = [t for t, info in stats.items() if info['Status'] == 'Ativo']
    ativos.sort(key=lambda x: (stats[x]['Pts'], stats[x]['Buchholz']), reverse=True)
    pares, escolhidos = [], set()

    # BYE
    if len(ativos) % 2 != 0:
        for t in reversed(ativos):
            ja_teve_bye = any(((h['a']==t and h['b']=='BYE') or (h['b']==t and h['a']=='BYE')) for h in historico_jogos)
            if not ja_teve_bye:
                pares.append((t, "BYE")); escolhidos.add(t); break

    # Tentativa 1: Inéditos
    for i in range(len(ativos)):
        t1 = ativos[i]
        if t1 in escolhidos: continue
        for j in range(i + 1, len(ativos)):
            t2 = ativos[j]
            if t2 in escolhidos: continue
            ja_jogaram = any(((h['a']==t1 and h['b']==t2) or (h['a']==t2 and h['b']==t1)) for h in historico_jogos)
            if not ja_jogaram:
                pares.append((t1, t2)); escolhidos.add(t1); escolhidos.add(t2); break

    # Tentativa 2: Repetição (Para não travar)
    sobraram = [t for t in ativos if t not in escolhidos]
    for i in range(0, len(sobraram), 2):
        if i + 1 < len(sobraram):
            pares.append((sobraram[i], sobraram[i+1]))
            escolhidos.add(sobraram[i]); escolhidos.add(sobraram[i+1])
        elif sobraram[i] not in escolhidos:
            pares.append((sobraram[i], "BYE"))
    return pares

# --- UI ---
df_total = carregar_dados()
if 'torneio_ativo' not in st.session_state:
    st.title("🏆 BAGA GESTOR PRO")
    with st.expander("🆕 Criar Torneio (6 Jogadores)"):
        nome_t = st.text_input("Nome")
        lista = st.text_area("Nomes")
        if st.button("Iniciar"):
            nomes = [x.strip() for x in lista.split('\n') if x.strip()]
            if len(nomes) == 6:
                random.shuffle(nomes)
                novos = [{'torneio_id': nome_t, 'rodada': 1, 'a': nomes[i], 'b': nomes[i+1], 'gols_a': 0, 'gols_b': 0, 'finalizado': 'NÃO', 'fase': 'Suíça'} for i in range(0, 6, 2)]
                conn.update(worksheet="Suico", data=pd.concat([df_total, pd.DataFrame(novos)]))
                st.cache_data.clear(); st.rerun()
            else: st.error("Mínimo 6 jogadores.")
    st.divider()
    for tid in df_total['torneio_id'].unique():
        if st.button(f"Abrir {tid}", use_container_width=True): st.session_state.torneio_ativo = tid; st.rerun()
else:
    tid = st.session_state.torneio_ativo
    st.header(f"🏟️ {tid}")
    if st.button("⬅️ Sair"): st.session_state.torneio_ativo = None; st.rerun()

    stats = calcular_tabela(df_total, tid)
    tab_jogos, tab_rank, tab_admin = st.tabs(["Jogos", "Ranking", "Admin"])

    with tab_rank:
        df_rank = pd.DataFrame.from_dict(stats, orient='index')[['Pts', 'V', 'E', 'D', 'Buchholz', 'Status']].sort_values(by=['Pts', 'Buchholz'], ascending=False)
        st.dataframe(df_rank, use_container_width=True)

    with tab_admin:
        if st.text_input("Senha", type="password") == "123":
            jogos_tid = df_total[df_total['torneio_id'] == tid]
            rodada_max = jogos_tid['rodada'].max()
            pendentes = jogos_tid[jogos_tid['finalizado'] == 'NÃO']
            ativos = [t for t, i in stats.items() if i['Status'] == 'Ativo']
            
            if not pendentes.empty:
                st.warning(f"Finalize a rodada {rodada_max}")
            elif len(ativos) >= 2 and 'fim_forcado' not in st.session_state:
                col1, col2 = st.columns(2)
                if col1.button("Próxima Rodada Suíça"):
                    novos = tentar_pareamento_flexivel(stats, jogos_tid[jogos_tid['fase']=='Suíça'].to_dict('records'))
                    l = []
                    for p in novos:
                        is_bye = p[1] == "BYE"
                        l.append({'torneio_id': tid, 'rodada': rodada_max+1, 'a': p[0], 'b': p[1], 'gols_a': 1 if is_bye else 0, 'gols_b': 0, 'finalizado': 'SIM' if is_bye else 'NÃO', 'fase': 'Suíça'})
                    conn.update(worksheet="Suico", data=pd.concat([df_total, pd.DataFrame(l)]))
                    st.cache_data.clear(); st.rerun()
                if col2.button("Forçar Fim da Fase Suíça"):
                    st.session_state.fim_forcado = True; st.rerun()
            else:
                st.success("🏁 Fase Suíça Concluída")
                top_3 = sorted(stats.keys(), key=lambda x: (stats[x]['Pts'], stats[x]['Buchholz']), reverse=True)[:3]
                semi_ok = not jogos_tid[jogos_tid['fase'] == 'Semifinal'].empty
                final_ok = not jogos_tid[jogos_tid['fase'] == 'Final'].empty
                if not semi_ok:
                    if st.button(f"Gerar Semifinal ({top_3[1]} vs {top_3[2]})"):
                        conn.update(worksheet="Suico", data=pd.concat([df_total, pd.DataFrame([{'torneio_id': tid, 'rodada': rodada_max+1, 'a': top_3[1], 'b': top_3[2], 'gols_a': 0, 'gols_b': 0, 'finalizado': 'NÃO', 'fase': 'Semifinal'}])]))
                        st.cache_data.clear(); st.rerun()
                elif not final_ok:
                    semi = jogos_tid[jogos_tid['fase'] == 'Semifinal'].iloc[0]
                    if semi['finalizado'] == 'SIM':
                        venc = semi['a'] if semi['gols_a'] > semi['gols_b'] else semi['b']
                        if st.button(f"Gerar Final ({top_3[0]} vs {venc})"):
                            conn.update(worksheet="Suico", data=pd.concat([df_total, pd.DataFrame([{'torneio_id': tid, 'rodada': rodada_max+1, 'a': top_3[0], 'b': venc, 'gols_a': 0, 'gols_b': 0, 'finalizado': 'NÃO', 'fase': 'Final'}])]))
                            st.cache_data.clear(); st.rerun()
            st.divider()
            if st.button("🗑️ DELETAR TORNEIO"):
                conn.update(worksheet="Suico", data=df_total[df_total['torneio_id'] != tid])
                if 'fim_forcado' in st.session_state: del st.session_state.fim_forcado
                st.cache_data.clear(); st.session_state.torneio_ativo = None; st.rerun()

    with tab_jogos:
        v_jogos = df_total[df_total['torneio_id'] == tid]
        for r in sorted(v_jogos['rodada'].unique(), reverse=True):
            st.subheader(f"Rodada {r}")
            for idx, row in v_jogos[v_jogos['rodada'] == r].iterrows():
                with st.container(border=True):
                    c1, c2, c3 = st.columns([2,1,2])
                    c1.write(f"**{row['a']}**"); c2.write(f"### {row['gols_a']} x {row['gols_b']}"); c3.write(f"**{row['b']}**")
                    if row['finalizado'] == 'NÃO' and row['b'] != 'BYE':
                        with st.expander("Lançar"):
                            with st.form(f"f{idx}"):
                                ga, gb = st.number_input("A", 0, 99, key=f"a{idx}"), st.number_input("B", 0, 99, key=f"b{idx}")
                                if st.form_submit_button("Confirmar"):
                                    df_total.at[idx, 'gols_a'], df_total.at[idx, 'gols_b'], df_total.at[idx, 'finalizado'] = ga, gb, 'SIM'
                                    conn.update(worksheet="Suico", data=df_total); st.cache_data.clear(); st.rerun()
