import streamlit as st
import pandas as pd
import random
from itertools import combinations
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="BAGA BET PRO", layout="wide", page_icon="⚽")
conn = st.connection("gsheets", type=GSheetsConnection)

# --- FUNÇÕES DE SEGURANÇA ---
def converter_num(val):
    try:
        if pd.isna(val) or val == "" or val == "nan": return 0
        return int(float(val))
    except: return 0

def carregar_dados():
    try:
        st.cache_data.clear()
        df = conn.read(ttl=0)
        colunas_obrigatorias = [
            'torneio_id', 'formato', 'fase', 'a', 'b', 'finalizado', 
            'gols_a', 'gols_b', 'ida_a', 'ida_b', 'volta_a', 'volta_b', 'pen_a', 'pen_b', 'apostas'
        ]
        if df is None or df.empty or 'torneio_id' not in df.columns:
            return pd.DataFrame(columns=colunas_obrigatorias)
        return df
    except:
        return pd.DataFrame()

def salvar_dados(df_novo):
    df_save = df_novo.loc[:, ~df_novo.columns.str.contains('^Unnamed')]
    conn.update(data=df_save)
    st.cache_data.clear()

# --- CARREGAMENTO ---
df_atual = carregar_dados()

if 'torneio_ativo' not in st.session_state:
    st.title("⚽ BAGA BET PRO")
    if not df_atual.empty:
        t_existentes = df_atual.dropna(subset=['torneio_id'])
        if not t_existentes.empty:
            st.subheader("📂 Abrir Torneio")
            torneios = t_existentes[['torneio_id', 'formato']].drop_duplicates()
            cols = st.columns(3)
            for i, row in enumerate(torneios.values):
                if cols[i%3].button(f"{'🏆' if row[1]=='COPA' else '📈'} {row[0]}", use_container_width=True):
                    st.session_state.torneio_ativo, st.session_state.formato = row[0], row[1]
                    st.rerun()
    st.divider()
    with st.expander("🆕 Criar Novo"):
        c1, c2 = st.columns(2)
        n_id = c1.text_input("Nome")
        n_tp = c2.selectbox("Tipo", ["LIGA", "COPA"])
        if st.button("GERAR"):
            st.session_state.torneio_ativo, st.session_state.formato = n_id.strip(), n_tp
            st.rerun()

else:
    t_id = st.session_state.torneio_ativo
    formato = st.session_state.formato
    jogos_df = df_atual[df_atual['torneio_id'] == t_id].copy()

    with st.sidebar:
        st.header(t_id)
        menu = st.radio("Menu", ["🏟️ Jogos", "📊 Classificação", "🤑 Ranking", "⚙️ Admin"])
        is_admin = (st.text_input("Chave", type="password") == "1234")
        if st.button("🏠 Sair"):
            for k in list(st.session_state.keys()): del st.session_state[k]
            st.rerun()

    if menu == "🏟️ Jogos":
        for idx, row in jogos_df.iterrows():
            with st.container(border=True):
                c1, c2, c3 = st.columns([2, 1, 2])
                c1.write(f"### {row['a']}")
                if formato == "LIGA":
                    txt = f"{converter_num(row.get('gols_a'))} x {converter_num(row.get('gols_b'))}"
                else:
                    ia, ib = converter_num(row.get('ida_a')), converter_num(row.get('ida_b'))
                    va, vb = converter_num(row.get('volta_a')), converter_num(row.get('volta_b'))
                    txt = f"({ia}) {va} x {vb} ({ib})"
                c2.markdown(f"<h2 style='text-align:center'>{txt}</h2>", unsafe_allow_html=True)
                c3.write(f"### {row['b']}")

                if is_admin:
                    with st.expander("Lançar"):
                        if formato == "LIGA":
                            ra, rb = st.number_input(f"A", 0, key=f"a{idx}"), st.number_input(f"B", 0, key=f"b{idx}")
                            if st.button("Salvar", key=f"s{idx}"):
                                df_atual.loc[idx, ['gols_a', 'gols_b', 'finalizado']] = [ra, rb, "TRUE"]
                                salvar_dados(df_atual); st.rerun()
                        else:
                            i1, i2 = st.number_input("Ida A", 0, key=f"i1{idx}"), st.number_input("Ida B", 0, key=f"i2{idx}")
                            v1, v2 = st.number_input("Volta A", 0, key=f"v1{idx}"), st.number_input("Volta B", 0, key=f"v2{idx}")
                            if st.button("Salvar Copa", key=f"sc{idx}"):
                                df_atual.loc[idx, ['ida_a', 'ida_b', 'volta_a', 'volta_b', 'finalizado']] = [i1, i2, v1, v2, "TRUE"]
                                salvar_dados(df_atual); st.rerun()

    elif menu == "📊 Classificação":
        if formato == "LIGA":
            stats = {}
            # Inicializa todos os times com 0
            times_unicos = pd.concat([jogos_df['a'], jogos_df['b']]).unique()
            for t in times_unicos: stats[t] = {"P":0,"J":0,"V":0,"E":0,"D":0,"GP":0,"GC":0}
            
            for _, r in jogos_df[jogos_df['finalizado'] == "TRUE"].iterrows():
                ga, gb = converter_num(r['gols_a']), converter_num(r['gols_b'])
                stats[r['a']]["J"]+=1; stats[r['b']]["J"]+=1
                stats[r['a']]["GP"]+=ga; stats[r['a']]["GC"]+=gb
                stats[r['b']]["GP"]+=gb; stats[r['b']]["GC"]+=ga
                if ga > gb: stats[r['a']]["P"]+=3; stats[r['a']]["V"]+=1; stats[r['b']]["D"]+=1
                elif gb > ga: stats[r['b']]["P"]+=3; stats[r['b']]["V"]+=1; stats[r['a']]["D"]+=1
                else: stats[r['a']]["P"]+=1; stats[r['b']]["P"]+=1; stats[r['a']]["E"]+=1; stats[r['b']]["E"]+=1
            
            df_tab = pd.DataFrame.from_dict(stats, orient='index').reset_index().rename(columns={'index':'Equipe'})
            if not df_tab.empty:
                st.table(df_tab.sort_values(by=["P", "V", "GP"], ascending=False))
        else:
            st.info("Modo Copa: Placar agregado disponível nos Jogos.")

    elif menu == "🤑 Ranking":
        st.subheader("💰 Lucros de Apostas")
        st.info("Apostas serão implementadas na próxima rodada após validação dos placares.")

    elif menu == "⚙️ Admin" and is_admin:
        t_lista = st.text_area("Times")
        if st.button("GERAR"):
            lista = [t.strip() for t in t_lista.split("\n") if t.strip()]
            novos = []
            if formato == "LIGA":
                for a, b in combinations(lista, 2):
                    novos.append({"torneio_id":t_id, "formato":"LIGA", "a":a, "b":b, "finalizado":"FALSE"})
            else:
                for i in range(0, len(lista), 2):
                    if i+1 < len(lista):
                        novos.append({"torneio_id":t_id, "formato":"COPA", "a":lista[i], "b":lista[i+1], "finalizado":"FALSE"})
            df_final = pd.concat([df_atual[df_atual['torneio_id'] != t_id], pd.DataFrame(novos)], ignore_index=True)
            salvar_dados(df_final); st.rerun()
