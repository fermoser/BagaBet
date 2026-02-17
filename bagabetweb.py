import streamlit as st
import pandas as pd
import random
from streamlit_gsheets import GSheetsConnection

st.set_page_config(page_title="BAGA GESTOR PRO", layout="wide")
conn = st.connection("gsheets", type=GSheetsConnection)

def carregar():
    try:
        df = conn.read(worksheet="Suico", ttl=0)
        df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
        for col in ['gols_a', 'gols_b', 'rodada']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col]).fillna(0).astype(int)
        return df
    except:
        return pd.DataFrame(columns=['torneio_id', 'fase', 'rodada', 'a', 'b', 'gols_a', 'gols_b', 'finalizado'])

df_total = carregar()

if 'torneio_ativo' not in st.session_state:
    st.title("⚽ BAGA GESTOR PRO")
    ids = [str(x) for x in df_total['torneio_id'].dropna().unique() if str(x).strip() != ""]
    if ids:
        for tid in sorted(ids):
            if st.button(f"🏟️ {tid}", use_container_width=True):
                st.session_state.torneio_ativo = tid
                st.rerun()
else:
    tid = st.session_state.torneio_ativo
    st.header(f"🏆 {tid}")
    if st.button("⬅️ Sair"):
        st.session_state.torneio_ativo = None
        st.rerun()

    tab1, tab2, tab3 = st.tabs(["🏟️ Jogos", "📊 Classificação", "⚙️ Admin"])

    with tab2: # CLASSIFICAÇÃO (Necessária para o sorteio da próxima rodada)
        jogos_tid = df_total[df_total['torneio_id'] == tid]
        jogos_fin = jogos_tid[jogos_tid['finalizado'] == 'SIM']
        stats = {}
        for _, j in jogos_fin.iterrows():
            for t in [j['a'], j['b']]:
                if t == "BYE" or t == "-": continue
                if t not in stats: stats[t] = {'Pts':0, 'V':0, 'SG':0}
            
            if j['b'] == "BYE":
                stats[j['a']]['Pts'] += 3; stats[j['a']]['V'] += 1
            else:
                if j['gols_a'] > j['gols_b']: stats[j['a']]['Pts'] += 3; stats[j['a']]['V'] += 1
                elif j['gols_b'] > j['gols_a']: stats[j['b']]['Pts'] += 3; stats[j['b']]['V'] += 1
                else: stats[j['a']]['Pts'] += 1; stats[j['b']]['Pts'] += 1
        
        ranking = pd.DataFrame.from_dict(stats, orient='index').sort_values(by=['Pts', 'V'], ascending=False)
        st.table(ranking)

    with tab3: # ADMIN COM PRÓXIMA RODADA
        senha = st.text_input("Senha", type="password")
        if senha == "123":
            if st.button("🚀 GERAR PRÓXIMA RODADA (SUÍÇO)"):
                if not ranking.empty:
                    lista_times = ranking.index.tolist()
                    random.shuffle(lista_times) # Shuffle para desempatar quem tem mesmos pontos
                    # Ordena por pontos para o pareamento suíço
                    lista_ordenada = ranking.loc[lista_times].sort_values('Pts', ascending=False).index.tolist()
                    
                    rodada_atual = jogos_tid['rodada'].max()
                    novos_jogos = []
                    for i in range(0, len(lista_ordenada), 2):
                        t1 = lista_ordenada[i]
                        t2 = lista_ordenada[i+1] if i+1 < len(lista_ordenada) else "BYE"
                        novos_jogos.append({'torneio_id': tid, 'fase': 'Suico', 'rodada': rodada_atual + 1, 'a': t1, 'b': t2, 'gols_a': (1 if t2=="BYE" else 0), 'gols_b': 0, 'finalizado': ('SIM' if t2=="BYE" else 'NÃO')})
                    
                    df_save = pd.concat([df_total, pd.DataFrame(novos_jogos)], ignore_index=True)
                    conn.update(worksheet="Suico", data=df_save)
                    st.cache_data.clear()
                    st.success(f"Rodada {rodada_atual + 1} Gerada!")
                    st.rerun()

    with tab1: # JOGOS POR RODADA
        rodadas = sorted(jogos_tid['rodada'].unique(), reverse=True)
        for r in rodadas:
            st.subheader(f"Rodada {r}")
            jogos_r = jogos_tid[jogos_tid['rodada'] == r]
            for idx, row in jogos_r.iterrows():
                with st.container(border=True):
                    col1, col2, col3 = st.columns([2,1,2])
                    col1.write(row['a'])
                    col2.write(f"{row['gols_a']} x {row['gols_b']}")
                    col3.write(row['b'])
                    if row['b'] != "BYE" and row['finalizado'] != 'SIM':
                        with st.expander("Lançar"):
                            with st.form(f"f_{idx}"):
                                ga = st.number_input("Gols A", 0, 20, key=f"ga_{idx}")
                                gb = st.number_input("Gols B", 0, 20, key=f"gb_{idx}")
                                if st.form_submit_button("Confirmar"):
                                    df_total.at[idx, 'gols_a'] = ga
                                    df_total.at[idx, 'gols_b'] = gb
                                    df_total.at[idx, 'finalizado'] = 'SIM'
                                    conn.update(worksheet="Suico", data=df_total)
                                    st.cache_data.clear()
                                    st.rerun()
