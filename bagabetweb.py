import streamlit as st
import pandas as pd
from itertools import combinations
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="BAGA BET PRO", layout="wide", page_icon="⚽")
conn = st.connection("gsheets", type=GSheetsConnection)

# --- FUNÇÕES DE APOIO ---
def para_int(val):
    try:
        if pd.isna(val) or val == "" or str(val).lower() == "nan": return 0
        return int(float(val))
    except: return 0

def ta_finalizado(val):
    v = str(val).upper().strip()
    return v in ["1", "TRUE", "1.0", "VERDADEIRO"]

def carregar_dados():
    try:
        st.cache_data.clear()
        df = conn.read(ttl=0)
        return df if df is not None else pd.DataFrame()
    except: return pd.DataFrame()

def salvar_dados(df_novo):
    df_save = df_novo.loc[:, ~df_novo.columns.str.contains('^Unnamed')]
    conn.update(data=df_save)
    st.cache_data.clear()

# --- CARREGAMENTO INICIAL ---
df_atual = carregar_dados()

# Interface Principal
if 'torneio_ativo' not in st.session_state:
    st.title("⚽ BAGA BET PRO")
    
    # 1. ÁREA DE ABRIR EXISTENTE
    if not df_atual.empty and 'torneio_id' in df_atual.columns:
        # Só tenta listar se houver linhas preenchidas além do cabeçalho
        t_list = df_atual.dropna(subset=['torneio_id'])[['torneio_id', 'formato']].drop_duplicates()
        if not t_list.empty:
            st.subheader("📂 Abrir Torneio")
            cols = st.columns(3)
            for i, row in enumerate(t_list.values):
                label = f"{'🏆' if str(row[1]).upper()=='COPA' else '📈'} {row[0]}"
                if cols[i%3].button(label, key=f"btn_{i}", use_container_width=True):
                    st.session_state.torneio_ativo = row[0]
                    st.session_state.formato = str(row[1]).upper()
                    st.rerun()

    # 2. ÁREA DE CRIAR NOVO (Sempre visível agora)
    st.divider()
    st.subheader("🆕 Criar Novo Torneio")
    c1, c2 = st.columns(2)
    n_id = c1.text_input("Nome do Torneio (ex: liga_2026)")
    n_tp = c2.selectbox("Tipo", ["LIGA", "COPA"])
    
    if st.button("🚀 INICIAR NOVO TORNEIO", use_container_width=True):
        if n_id:
            st.session_state.torneio_ativo = n_id.strip()
            st.session_state.formato = n_tp
            st.rerun()
        else:
            st.error("Por favor, digite um nome para o torneio.")

else:
    # --- DENTRO DO TORNEIO ---
    t_id = st.session_state.torneio_ativo
    formato = st.session_state.formato
    
    # Filtro robusto
    if not df_atual.empty and 'torneio_id' in df_atual.columns:
        jogos_df = df_atual[df_atual['torneio_id'].astype(str) == str(t_id)].copy()
    else:
        jogos_df = pd.DataFrame()

    with st.sidebar:
        st.header(f"⚽ {t_id}")
        st.info(f"Modo: {formato}")
        menu = st.radio("Navegação", ["🏟️ Jogos", "📊 Classificação", "⚙️ Admin"])
        is_admin = (st.text_input("Senha Admin", type="password") == "1234")
        if st.button("🏠 Sair do Torneio"):
            for k in list(st.session_state.keys()): del st.session_state[k]
            st.rerun()

    # --- ABA ADMIN: Onde você vai gerar os jogos pela primeira vez ---
    if menu == "⚙️ Admin":
        if is_admin:
            st.subheader("Gerar Confrontos")
            times_input = st.text_area("Lista de Equipes (um por linha)", placeholder="Time A\nTime B\nTime C...")
            if st.button("🔥 GERAR E SALVAR NA PLANILHA"):
                lista_t = [t.strip() for t in times_input.split("\n") if t.strip()]
                if len(lista_t) < 2:
                    st.warning("Insira pelo menos 2 times.")
                else:
                    novos = []
                    if formato == "LIGA":
                        for a, b in combinations(lista_t, 2):
                            novos.append({"torneio_id":t_id, "formato":"LIGA", "a":a, "b":b, "finalizado":"0"})
                    else:
                        for i in range(0, len(lista_t), 2):
                            if i+1 < len(lista_t):
                                novos.append({"torneio_id":t_id, "formato":"COPA", "a":lista_t[i], "b":lista_t[i+1], "finalizado":"0"})
                    
                    df_novos = pd.DataFrame(novos)
                    # Adiciona ao que já existe na planilha (preservando outros torneios)
                    if not df_atual.empty:
                        df_final = pd.concat([df_atual[df_atual['torneio_id'].astype(str) != str(t_id)], df_novos], ignore_index=True)
                    else:
                        df_final = df_novos
                    
                    salvar_dados(df_final)
                    st.success("Jogos gerados com sucesso!")
                    st.rerun()
        else:
            st.warning("Acesse com a senha para gerar jogos.")

    # --- ABA JOGOS ---
    elif menu == "🏟️ Jogos":
        if jogos_df.empty:
            st.info("Vá em **Admin** e gere os jogos deste torneio.")
        else:
            for idx, row in jogos_df.iterrows():
                with st.container(border=True):
                    c1, c2, c3 = st.columns([2, 1, 2])
                    c1.markdown(f"<p style='text-align:right; font-size:20px;'><b>{row['a']}</b></p>", unsafe_allow_html=True)
                    
                    if formato == "LIGA":
                        ga, gb = para_int(row.get('gols_a')), para_int(row.get('gols_b'))
                        txt = f"{ga} x {gb}"
                    else:
                        ia, ib = para_int(row.get('ida_a')), para_int(row.get('ida_b'))
                        va, vb = para_int(row.get('volta_a')), para_int(row.get('volta_b'))
                        txt = f"({ia}) {va} x {vb} ({ib})"
                    
                    c2.markdown(f"<h3 style='text-align:center; background:#f0f2f6; border-radius:10px;'>{txt}</h3>", unsafe_allow_html=True)
                    c3.markdown(f"<p style='text-align:left; font-size:20px;'><b>{row['b']}</b></p>", unsafe_allow_html=True)

                    if is_admin:
                        with st.expander("Lançar Resultado"):
                            if formato == "LIGA":
                                ra = st.number_input(f"Gols {row['a']}", 0, key=f"ra_{idx}")
                                rb = st.number_input(f"Gols {row['b']}", 0, key=f"rb_{idx}")
                                if st.button("Confirmar", key=f"btn_s_{idx}"):
                                    df_atual.loc[idx, ['gols_a', 'gols_b', 'finalizado']] = [ra, rb, "1"]
                                    salvar_dados(df_atual); st.rerun()
                            else:
                                c_i, c_v = st.columns(2)
                                i_a = c_i.number_input("Ida A", 0, key=f"ia_{idx}")
                                i_b = c_i.number_input("Ida B", 0, key=f"ib_{idx}")
                                v_a = c_v.number_input("Volta A", 0, key=f"va_{idx}")
                                v_b = c_v.number_input("Volta B", 0, key=f"vb_{idx}")
                                if st.button("Confirmar Copa", key=f"btn_sc_{idx}"):
                                    df_atual.loc[idx, ['ida_a','ida_b','volta_a','volta_b','finalizado']] = [i_a, i_b, v_a, v_b, "1"]
                                    salvar_dados(df_atual); st.rerun()

    # --- ABA CLASSIFICAÇÃO ---
    elif menu == "📊 Classificação":
        if formato == "LIGA":
            stats = {}
            if not jogos_df.empty:
                times = pd.concat([jogos_df['a'], jogos_df['b']]).unique()
                for t in times:
                    if pd.notna(t): stats[t] = {"P":0,"J":0,"V":0,"E":0,"D":0,"GP":0,"GC":0}
                
                for _, r in jogos_df.iterrows():
                    if ta_finalizado(r.get('finalizado')):
                        ga, gb = para_int(r['gols_a']), para_int(r['gols_b'])
                        t1, t2 = r['a'], r['b']
                        stats[t1]["J"]+=1; stats[t2]["J"]+=1
                        stats[t1]["GP"]+=ga; stats[t1]["GC"]+=gb
                        stats[t2]["GP"]+=gb; stats[t2]["GC"]+=ga
                        if ga > gb: stats[t1]["P"]+=3; stats[t1]["V"]+=1; stats[t2]["D"]+=1
                        elif gb > ga: stats[t2]["P"]+=3; stats[t2]["V"]+=1; stats[t1]["D"]+=1
                        else: stats[t1]["P"]+=1; stats[t2]["P"]+=1; stats[t1]["E"]+=1; stats[t2]["E"]+=1
                
                df_tab = pd.DataFrame.from_dict(stats, orient='index').reset_index().rename(columns={'index':'Equipe'})
                if not df_tab.empty:
                    df_tab['SG'] = df_tab['GP'] - df_tab['GC']
                    st.table(df_tab.sort_values(by=["P", "V", "SG"], ascending=False))
        else:
            st.info("Modo Copa não possui tabela de pontos.")
