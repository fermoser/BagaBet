import streamlit as st
import pandas as pd
from itertools import combinations
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="BAGA BET PRO", layout="wide", page_icon="⚽")
conn = st.connection("gsheets", type=GSheetsConnection)

# --- FUNÇÕES DE CONVERSÃO (Cruciais para ler sua planilha) ---
def para_int(val):
    try:
        if pd.isna(val) or val == "": return 0
        return int(float(val))
    except: return 0

def ta_finalizado(val):
    # Sua planilha tem '1' e 'TRUE'. Essa função entende ambos.
    v = str(val).upper().strip()
    return v in ["1", "TRUE", "1.0"]

def carregar_dados():
    try:
        st.cache_data.clear()
        df = conn.read(ttl=0)
        return df
    except:
        return pd.DataFrame()

def salvar_dados(df_novo):
    conn.update(data=df_novo)
    st.cache_data.clear()

# --- CARREGAMENTO ---
df_atual = carregar_dados()

if 'torneio_ativo' not in st.session_state:
    st.title("⚽ BAGA BET PRO")
    if not df_atual.empty and 'torneio_id' in df_atual.columns:
        st.subheader("📂 Selecione o Torneio")
        # Remove linhas totalmente vazias para não criar botões fantasmas
        t_list = df_atual.dropna(subset=['torneio_id'])[['torneio_id', 'formato']].drop_duplicates()
        cols = st.columns(3)
        for i, row in enumerate(t_list.values):
            if cols[i%3].button(f"{row[0]} ({row[1]})", use_container_width=True):
                st.session_state.torneio_ativo, st.session_state.formato = row[0], row[1]
                st.rerun()
else:
    t_id = st.session_state.torneio_ativo
    formato = st.session_state.formato
    # Filtro exato baseado na sua coluna 'torneio_id'
    jogos_df = df_atual[df_atual['torneio_id'].astype(str) == str(t_id)].copy()

    with st.sidebar:
        st.header(t_id)
        menu = st.radio("Menu", ["🏟️ Jogos", "📊 Classificação", "⚙️ Admin"])
        if st.button("🏠 Sair"):
            for k in list(st.session_state.keys()): del st.session_state[k]
            st.rerun()

    if menu == "🏟️ Jogos":
        for idx, row in jogos_df.iterrows():
            with st.container(border=True):
                c1, c2, c3 = st.columns([2, 1, 2])
                c1.write(f"### {row['a']}")
                
                # Leitura conforme as colunas da sua foto
                if str(row['formato']).upper() == "LIGA":
                    ga, gb = para_int(row.get('gols_a')), para_int(row.get('gols_b'))
                    txt = f"{ga} x {gb}"
                else:
                    ia, ib = para_int(row.get('ida_a')), para_int(row.get('ida_b'))
                    va, vb = para_int(row.get('volta_a')), para_int(row.get('volta_b'))
                    txt = f"({ia}) {va} x {vb} ({ib})"
                
                c2.markdown(f"<h2 style='text-align:center'>{txt}</h2>", unsafe_allow_html=True)
                c3.write(f"### {row['b']}")

    elif menu == "📊 Classificação":
        if str(formato).upper() == "LIGA":
            st.subheader(f"Tabela: {t_id}")
            stats = {}
            # Pega todos os times que aparecem neste torneio
            times = pd.concat([jogos_df['a'], jogos_df['b']]).unique()
            for t in times:
                if pd.notna(t): stats[t] = {"P":0,"J":0,"V":0,"E":0,"D":0,"GP":0,"GC":0}
            
            # Processa apenas jogos marcados como finalizados na sua planilha
            for _, r in jogos_df.iterrows():
                if ta_finalizado(r.get('finalizado')):
                    ga, gb = para_int(r.get('gols_a')), para_int(r.get('gols_b'))
                    t1, t2 = r['a'], r['b']
                    
                    stats[t1]["J"]+=1; stats[t2]["J"]+=1
                    stats[t1]["GP"]+=ga; stats[t1]["GC"]+=gb
                    stats[t2]["GP"]+=gb; stats[t2]["GC"]+=ga
                    
                    if ga > gb:
                        stats[t1]["P"]+=3; stats[t1]["V"]+=1; stats[t2]["D"]+=1
                    elif gb > ga:
                        stats[t2]["P"]+=3; stats[t2]["V"]+=1; stats[t1]["D"]+=1
                    else:
                        stats[t1]["P"]+=1; stats[t2]["P"]+=1; stats[t1]["E"]+=1; stats[t2]["E"]+=1
            
            df_tab = pd.DataFrame.from_dict(stats, orient='index').reset_index().rename(columns={'index':'Time'})
            if not df_tab.empty:
                # Ordena por Pontos, Vitórias e Saldo
                df_tab['SG'] = df_tab['GP'] - df_tab['GC']
                st.dataframe(df_tab.sort_values(by=["P", "V", "SG"], ascending=False), hide_index=True)
        else:
            st.info("O modo Copa não gera tabela de pontos automática.")

    elif menu == "⚙️ Admin":
        st.write("Configurações do Torneio")
        # Espaço para futuras manutenções
