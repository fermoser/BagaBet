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
        # Garante que as colunas de gols sejam números
        for col in ['gols_a', 'gols_b']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col]).fillna(0).astype(int)
            else:
                df[col] = 0
        return df
    except:
        return pd.DataFrame(columns=['torneio_id', 'fase', 'rodada', 'a', 'b', 'gols_a', 'gols_b', 'finalizado'])

df_total = carregar()

if 'torneio_ativo' not in st.session_state:
    st.title("⚽ BAGA GESTOR PRO")
    ids = [str(x) for x in df_total['torneio_id'].dropna().unique() if str(x).strip() != ""]
    if ids:
        st.subheader("Seus Torneios")
        for tid in sorted(ids):
            if st.button(f"🏟️ {tid}", use_container_width=True):
                st.session_state.torneio_ativo = tid
                st.rerun()
else:
    tid = st.session_state.torneio_ativo
    st.header(f"🏆 {tid}")
    if st.button("⬅️ Sair do Torneio"):
        st.session_state.torneio_ativo = None
        st.rerun()

    tab1, tab2, tab3 = st.tabs(["🏟️ Jogos", "📊 Classificação", "⚙️ Admin"])

    with tab3: # ADMIN
        senha = st.text_input("Senha", type="password")
        if senha == "123":
            st.success("Logado")
            with st.expander("Sorteio Inicial"):
                txt = st.text_area("Times (um por linha)")
                if st.button("GERAR 1ª RODADA"):
                    lista = [t.strip() for t in txt.split('\n') if t.strip()]
                    if len(lista) >= 4:
                        random.shuffle(lista)
                        jogos = []
                        for i in range(0, len(lista), 2):
                            t1, t2 = lista[i], (lista[i+1] if i+1 < len(lista) else "BYE")
                            jogos.append({'torneio_id': tid, 'fase': 'Suico', 'rodada': 1, 'a': t1, 'b': t2, 'gols_a': (1 if t2=="BYE" else 0), 'gols_b': 0, 'finalizado': ('SIM' if t2=="BYE" else 'NÃO')})
                        df_save = pd.concat([df_total[df_total['torneio_id'] != tid], pd.DataFrame(jogos)], ignore_index=True)
                        conn.update(worksheet="Suico", data=df_save)
                        st.cache_data.clear()
                        st.rerun()
            
            if st.button("🚨 EXCLUIR TORNEIO"):
                conn.update(worksheet="Suico", data=df_total[df_total['torneio_id'] != tid])
                st.session_state.torneio_ativo = None; st.rerun()

    with tab1: # JOGOS COM PLACAR
        st.subheader("Rodada 1")
        meus_jogos = df_total[(df_total['torneio_id'] == tid) & (df_total['fase'] == 'Suico')]
        for idx, r in meus_jogos.iterrows():
            with st.container(border=True):
                c1, c2, c3 = st.columns([2, 1, 2])
                c1.write(f"**{r['a']}**")
                c2.write(f"{r['gols_a']} x {r['gols_b']}")
                c3.write(f"**{r['b']}**")
                
                if r['b'] != "BYE":
                    with st.expander("Editar Placar"):
                        with st.form(f"form_{idx}"):
                            ga = st.number_input(f"Gols {r['a']}", 0, 20, int(r['gols_a']))
                            gb = st.number_input(f"Gols {r['b']}", 0, 20, int(r['gols_b']))
                            if st.form_submit_button("Salvar"):
                                df_total.at[idx, 'gols_a'] = ga
                                df_total.at[idx, 'gols_b'] = gb
                                df_total.at[idx, 'finalizado'] = 'SIM'
                                conn.update(worksheet="Suico", data=df_total)
                                st.cache_data.clear()
                                st.rerun()

    with tab2: # CLASSIFICAÇÃO REAL
        st.subheader("Tabela")
        jogos_fin = meus_jogos[meus_jogos['finalizado'] == 'SIM']
        stats = {}
        for _, j in jogos_fin.iterrows():
            for t in [j['a'], j['b']]:
                if t not in stats: stats[t] = {'Pts':0, 'PJ':0, 'V':0, 'E':0, 'D':0, 'GP':0, 'GC':0, 'SG':0}
            if j['b'] == "BYE":
                stats[j['a']]['Pts'] += 3; stats[j['a']]['PJ'] += 1; stats[j['a']]['V'] += 1; stats[j['a']]['GP'] += 1
            else:
                stats[j['a']]['PJ'] += 1; stats[j['b']]['PJ'] += 1
                stats[j['a']]['GP'] += j['gols_a']; stats[j['a']]['GC'] += j['gols_b']
                stats[j['b']]['GP'] += j['gols_b']; stats[j['b']]['GC'] += j['gols_a']
                if j['gols_a'] > j['gols_b']: stats[j['a']]['Pts'] += 3; stats[j['a']]['V'] += 1; stats[j['b']]['D'] += 1
                elif j['gols_b'] > j['gols_a']: stats[j['b']]['Pts'] += 3; stats[j['b']]['V'] += 1; stats[j['a']]['D'] += 1
                else: stats[j['a']]['Pts'] += 1; stats[j['b']]['Pts'] += 1; stats[j['a']]['E'] += 1; stats[j['b']]['E'] += 1
        
        for t in stats: stats[t]['SG'] = stats[t]['GP'] - stats[t]['GC']
        tb = pd.DataFrame.from_dict(stats, orient='index').sort_values(by=['Pts', 'V', 'SG', 'GP'], ascending=False)
        if not tb.empty: st.table(tb)
        else: st.info("Nenhum jogo finalizado.")
