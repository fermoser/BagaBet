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
        
        # COLUNAS QUE O APP PRECISA TER
        colunas_obrigatorias = [
            'torneio_id', 'formato', 'fase', 'a', 'b', 'finalizado', 
            'gols_a', 'gols_b', 'ida_a', 'ida_b', 'volta_a', 'volta_b', 'pen_a', 'pen_b', 'apostas'
        ]
        
        # Se estiver vazio ou sem a coluna principal, reconstrói
        if df is None or df.empty or 'torneio_id' not in df.columns:
            df_vazio = pd.DataFrame(columns=colunas_obrigatorias)
            return df_vazio
        
        return df
    except:
        return pd.DataFrame()

def salvar_dados(df_novo):
    # Limpa colunas fantasmas antes de salvar
    df_save = df_novo.loc[:, ~df_novo.columns.str.contains('^Unnamed')]
    conn.update(data=df_save)
    st.cache_data.clear()

# --- CARREGAMENTO INICIAL ---
df_atual = carregar_dados()

# Se por um milagre a coluna ainda não existir no df_atual (mesmo após o check), criamos aqui
if 'torneio_id' not in df_atual.columns:
    for col in ['torneio_id', 'formato', 'fase', 'a', 'b', 'finalizado', 'gols_a', 'gols_b', 'ida_a', 'ida_b', 'volta_a', 'volta_b', 'pen_a', 'pen_b', 'apostas']:
        if col not in df_atual.columns:
            df_atual[col] = None

# --- NAVEGAÇÃO ---
if 'torneio_ativo' not in st.session_state:
    st.title("⚽ BAGA BET PRO")
    
    # Mostrar Torneios Existentes
    if not df_atual.empty:
        # Filtra apenas linhas que realmente tem um ID de torneio
        t_existentes = df_atual.dropna(subset=['torneio_id'])
        if not t_existentes.empty:
            st.subheader("📂 Abrir Torneio")
            torneios = t_existentes[['torneio_id', 'formato']].drop_duplicates()
            cols = st.columns(3)
            for i, row in enumerate(torneios.values):
                if cols[i%3].button(f"{'🏆' if row[1]=='COPA' else '📈'} {row[0]}", use_container_width=True):
                    st.session_state.torneio_ativo = row[0]
                    st.session_state.formato = row[1]
                    st.rerun()

    st.divider()
    with st.expander("🆕 Criar Novo Torneio"):
        c1, c2 = st.columns(2)
        n_id = c1.text_input("Nome (Ex: liga_amigos)")
        n_tp = c2.selectbox("Tipo", ["LIGA", "COPA"])
        if st.button("GERAR NOVO"):
            if n_id:
                st.session_state.torneio_ativo = n_id.strip()
                st.session_state.formato = n_tp
                st.rerun()

else:
    t_id = st.session_state.torneio_ativo
    formato = st.session_state.formato
    
    # Filtro de Jogos (Agora blindado contra KeyError)
    jogos_df = df_atual[df_atual['torneio_id'] == t_id].copy()

    with st.sidebar:
        st.header(t_id)
        menu = st.radio("Menu", ["🏟️ Jogos", "📊 Classificação", "⚙️ Admin"])
        is_admin = (st.text_input("Chave", type="password") == "1234")
        if st.button("🏠 Sair"):
            for k in list(st.session_state.keys()): del st.session_state[k]
            st.rerun()

    # --- JOGOS ---
    if menu == "🏟️ Jogos":
        if jogos_df.empty:
            st.info("Vá em Admin para gerar os confrontos.")
        else:
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
                                ra = st.number_input(f"Gols {row['a']}", 0, key=f"la{idx}")
                                rb = st.number_input(f"Gols {row['b']}", 0, key=f"lb{idx}")
                                if st.button("Salvar", key=f"sl{idx}"):
                                    df_atual.loc[idx, ['gols_a', 'gols_b', 'finalizado']] = [ra, rb, "TRUE"]
                                    salvar_dados(df_atual); st.rerun()
                            else:
                                i_a = st.number_input("Ida A", 0, key=f"ia{idx}")
                                i_b = st.number_input("Ida B", 0, key=f"ib{idx}")
                                v_a = st.number_input("Volta A", 0, key=f"va{idx}")
                                v_b = st.number_input("Volta B", 0, key=f"vb{idx}")
                                if st.button("Salvar Copa", key=f"sc{idx}"):
                                    df_atual.loc[idx, ['ida_a','ida_b','volta_a','volta_b','finalizado']] = [i_a, i_b, v_a, v_b, "TRUE"]
                                    salvar_dados(df_atual); st.rerun()

    # --- CLASSIFICAÇÃO ---
    elif menu == "📊 Classificação":
        if formato == "LIGA":
            stats = {}
            for _, r in jogos_df.iterrows():
                for t in [r['a'], r['b']]:
                    if t not in stats: stats[t] = {"P":0,"J":0,"V":0,"E":0,"D":0,"GP":0,"GC":0}
                if str(r.get('finalizado')).upper() == "TRUE":
                    ga, gb = converter_num(r['gols_a']), converter_num(r['gols_b'])
                    stats[r['a']]["J"]+=1; stats[r['b']]["J"]+=1
                    stats[r['a']]["GP"]+=ga; stats[r['a']]["GC"]+=gb
                    stats[r['b']]["GP"]+=gb; stats[r['b']]["GC"]+=ga
                    if ga > gb: stats[r['a']]["P"]+=3; stats[r['a']]["V"]+=1; stats[r['b']]["D"]+=1
                    elif gb > ga: stats[r['b']]["P"]+=3; stats[r['b']]["V"]+=1; stats[r['a']]["D"]+=1
                    else: stats[r['a']]["P"]+=1; stats[r['b']]["P"]+=1; stats[r['a']]["E"]+=1; stats[r['b']]["E"]+=1
            
            st.table(pd.DataFrame.from_dict(stats, orient='index').sort_values(by="P", ascending=False))
        else:
            st.info("Modo Copa: Placar agregado nos Jogos.")

    # --- ADMIN ---
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
                    novos.append({"torneio_id":t_id, "formato":"COPA", "a":lista[i], "b":lista[i+1], "finalizado":"FALSE"})
            
            df_final = pd.concat([df_atual[df_atual['torneio_id'] != t_id], pd.DataFrame(novos)], ignore_index=True)
            salvar_dados(df_final)
            st.rerun()
