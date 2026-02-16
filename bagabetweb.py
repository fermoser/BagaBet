import streamlit as st
import pandas as pd
from itertools import combinations
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="BAGA BET PRO", layout="wide", page_icon="⚽")
conn = st.connection("gsheets", type=GSheetsConnection)

# --- FUNÇÕES DE SEGURANÇA ---
def safe_int(val):
    try:
        if pd.isna(val) or val == "" or str(val).lower() == "nan": return 0
        return int(float(val))
    except: return 0

def is_done(val):
    v = str(val).upper().strip()
    return v in ["1", "TRUE", "1.0", "VERDADEIRO"]

def carregar():
    st.cache_data.clear()
    try:
        df = conn.read(ttl=0)
        if df is None or df.empty:
            return pd.DataFrame(columns=['torneio_id', 'formato', 'fase', 'a', 'b', 'finalizado', 'gols_a', 'gols_b', 'ida_a', 'ida_b', 'volta_a', 'volta_b', 'pen_a', 'pen_b', 'apostas'])
        return df
    except:
        return pd.DataFrame()

def salvar(df):
    # Remove colunas fantasmas e salva
    df_save = df.loc[:, ~df.columns.str.contains('^Unnamed')]
    conn.update(data=df_save)
    st.cache_data.clear()
    st.toast("Dados atualizados na nuvem! ✅")

# --- CARREGAMENTO ---
df_db = carregar()

# --- TELA DE SELEÇÃO / CRIAÇÃO ---
if 'torneio_ativo' not in st.session_state:
    st.title("⚽ BAGA BET PRO")
    
    # Abrir existentes
    if not df_db.empty and 'torneio_id' in df_db.columns:
        existentes = df_db.dropna(subset=['torneio_id'])
        if not existentes.empty:
            st.subheader("📂 Seus Torneios")
            t_list = existentes[['torneio_id', 'formato']].drop_duplicates()
            cols = st.columns(3)
            for i, row in enumerate(t_list.values):
                if cols[i%3].button(f"{row[1]} | {row[0]}", use_container_width=True):
                    st.session_state.torneio_ativo = row[0]
                    st.session_state.formato = str(row[1]).upper()
                    st.rerun()

    st.divider()
    # Criar novo (Sempre disponível)
    st.subheader("🆕 Criar Novo")
    c1, c2 = st.columns(2)
    novo_nome = c1.text_input("Nome do Torneio")
    novo_tipo = c2.selectbox("Tipo", ["LIGA", "COPA"])
    if st.button("🚀 CRIAR AGORA", use_container_width=True):
        if novo_nome:
            st.session_state.torneio_ativo = novo_nome.strip()
            st.session_state.formato = novo_tipo
            st.rerun()

else:
    # --- DENTRO DO TORNEIO ---
    t_id = st.session_state.torneio_ativo
    formato = st.session_state.formato
    
    # Filtro dos jogos atuais
    if not df_db.empty and 'torneio_id' in df_db.columns:
        jogos_df = df_db[df_db['torneio_id'].astype(str) == str(t_id)].copy()
    else:
        jogos_df = pd.DataFrame()

    with st.sidebar:
        st.header(t_id)
        st.caption(f"Modo: {formato}")
        menu = st.radio("Menu", ["🏟️ Jogos", "📊 Classificação", "🤑 Apostas", "⚙️ Admin"])
        senha = st.text_input("Chave Admin", type="password")
        is_admin = (senha == "1234")
        if st.button("🏠 Sair"):
            for k in list(st.session_state.keys()): del st.session_state[k]
            st.rerun()

    # --- ABA ADMIN (GERAR JOGOS) ---
    if menu == "⚙️ Admin":
        if is_admin:
            st.subheader("Configuração")
            txt_times = st.text_area("Times (um por linha)")
            if st.button("GERAR CONFRONTOS"):
                lista = [t.strip() for t in txt_times.split("\n") if t.strip()]
                novos = []
                if formato == "LIGA":
                    for a, b in combinations(lista, 2):
                        novos.append({"torneio_id":t_id, "formato":"LIGA", "a":a, "b":b, "finalizado":"0"})
                else:
                    for i in range(0, len(lista), 2):
                        if i+1 < len(lista):
                            novos.append({"torneio_id":t_id, "formato":"COPA", "a":lista[i], "b":lista[i+1], "finalizado":"0"})
                
                # Une com o banco global excluindo o torneio atual (se ele já existia) para resetar
                df_final = pd.concat([df_db[df_db['torneio_id'].astype(str) != str(t_id)], pd.DataFrame(novos)], ignore_index=True)
                salvar(df_final)
                st.rerun()
        else:
            st.warning("Acesso restrito.")

    # --- ABA JOGOS ---
    elif menu == "🏟️ Jogos":
        if jogos_df.empty:
            st.info("Aguardando geração de jogos no Admin.")
        else:
            for idx, row in jogos_df.iterrows():
                with st.container(border=True):
                    c1, c2, c3 = st.columns([2, 1, 2])
                    c1.write(f"### {row['a']}")
                    
                    if formato == "LIGA":
                        txt = f"{safe_int(row.get('gols_a'))} x {safe_int(row.get('gols_b'))}"
                    else:
                        ia, ib = safe_int(row.get('ida_a')), safe_int(row.get('ida_b'))
                        va, vb = safe_int(row.get('volta_a')), safe_int(row.get('volta_b'))
                        txt = f"({ia}) {va} x {vb} ({ib})"
                    
                    c2.markdown(f"<h2 style='text-align:center; color:#007bff;'>{txt}</h2>", unsafe_allow_html=True)
                    c3.write(f"### {row['b']}")

                    if is_admin:
                        with st.expander("Lançar Placar"):
                            if formato == "LIGA":
                                ra, rb = st.number_input(f"A", 0, key=f"la{idx}"), st.number_input(f"B", 0, key=f"lb{idx}")
                                if st.button("Salvar", key=f"bs{idx}"):
                                    df_db.loc[idx, ['gols_a', 'gols_b', 'finalizado']] = [ra, rb, "1"]
                                    salvar(df_db); st.rerun()
                            else:
                                ci, cv = st.columns(2)
                                ia, ib = ci.number_input("Ida A", 0, key=f"ia{idx}"), ci.number_input("Ida B", 0, key=f"ib{idx}")
                                va, vb = cv.number_input("Vol A", 0, key=f"va{idx}"), cv.number_input("Vol B", 0, key=f"vb{idx}")
                                if st.button("Salvar Copa", key=f"bc{idx}"):
                                    df_db.loc[idx, ['ida_a','ida_b','volta_a','volta_b','finalizado']] = [ia, ib, va, vb, "1"]
                                    salvar(df_db); st.rerun()

    # --- ABA CLASSIFICAÇÃO ---
    elif menu == "📊 Classificação":
        if formato == "LIGA":
            st.subheader("Tabela")
            stats = {}
            times = pd.concat([jogos_df['a'], jogos_df['b']]).unique()
            for t in times: stats[t] = {"P":0,"J":0,"V":0,"E":0,"D":0,"GP":0,"GC":0}
            
            for _, r in jogos_df.iterrows():
                if is_done(r.get('finalizado')):
                    ga, gb = safe_int(r['gols_a']), safe_int(r['gols_b'])
                    stats[r['a']]["J"]+=1; stats[r['b']]["J"]+=1
                    stats[r['a']]["GP"]+=ga; stats[r['a']]["GC"]+=gb
                    stats[r['b']]["GP"]+=gb; stats[r['b']]["GC"]+=ga
                    if ga > gb: stats[r['a']]["P"]+=3; stats[r['a']]["V"]+=1; stats[r['b']]["D"]+=1
                    elif gb > ga: stats[r['b']]["P"]+=3; stats[r['b']]["V"]+=1; stats[r['a']]["D"]+=1
                    else: stats[r['a']]["P"]+=1; stats[r['b']]["P"]+=1; stats[r['a']]["E"]+=1; stats[r['b']]["E"]+=1
            
            df_tab = pd.DataFrame.from_dict(stats, orient='index').reset_index().rename(columns={'index':'Equipe'})
            df_tab['SG'] = df_tab['GP'] - df_tab['GC']
            st.table(df_tab.sort_values(by=["P", "V", "SG"], ascending=False))
        else:
            st.info("Copa: Resultados visualizados na aba Jogos.")

    # --- ABA APOSTAS ---
    elif menu == "🤑 Apostas":
        st.subheader("Palpites")
        st.write("Selecione um jogo na aba **🏟️ Jogos** para ver as apostas individuais ou lançar novas.")
