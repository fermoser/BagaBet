import streamlit as st
import pandas as pd
import random
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="BAGA GESTOR PRO", layout="wide")

conn = st.connection("gsheets", type=GSheetsConnection)
ABA_JOGOS = "Página1" 
ABA_SUICO = "Suico"

# Colunas padrão
COLS_SUICO = ['torneio_id', 'formato', 'fase', 'rodada', 'a', 'b', 'gols_a', 'gols_b', 'finalizado']

def carregar_dados(aba):
    try:
        df = conn.read(worksheet=aba, ttl="0s")
        if df is None or df.empty: return pd.DataFrame(columns=COLS_SUICO)
        df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
        return df
    except: return pd.DataFrame(columns=COLS_SUICO)

def salvar_dados(df, aba):
    if aba == ABA_SUICO:
        for col in COLS_SUICO:
            if col not in df.columns: df[col] = ""
        df = df[COLS_SUICO]
    conn.update(worksheet=aba, data=df)
    st.cache_data.clear()

# --- ESTADO ---
if 'torneio_ativo' not in st.session_state: st.session_state.torneio_ativo = None
if 'tipo_ativo' not in st.session_state: st.session_state.tipo_ativo = None 

df_suico = carregar_dados(ABA_SUICO)
df_padrao = carregar_dados(ABA_JOGOS)

# --- TELA INICIAL ---
if st.session_state.torneio_ativo is None:
    st.title("⚽ BAGA GESTOR PRO")
    
    # --- CORREÇÃO DO ERRO AQUI ---
    # Convertemos todos os IDs para STRING (texto) para o sorted() não travar
    ids_s = [str(x) for x in df_suico['torneio_id'].dropna().unique() if str(x).strip() not in ["", "-", "None"]]
    ids_p = [str(x) for x in df_padrao['torneio_id'].dropna().unique() if str(x).strip() not in ["", "-", "None"]]
    
    lista_final = sorted(list(set(ids_s + ids_p))) # Agora só tem texto, funciona!
    
    st.subheader("📂 Torneios")
    for t in lista_final:
        tipo = "SUICO" if t in ids_s else "PADRAO"
        if st.button(f"{'⭐' if tipo=='SUICO' else '🏆'} {t}", key=f"btn_{t}"):
            st.session_state.torneio_ativo = t
            st.session_state.tipo_ativo = tipo
            st.rerun()

    st.divider()
    ns = st.text_input("Nome do Novo Suíço")
    if st.button("CRIAR SUÍÇO"):
        if ns:
            nova = pd.DataFrame([[str(ns), 'SUICO', 'Inscricao', 0, '', '', 0, 0, 'NÃO']], columns=COLS_SUICO)
            salvar_dados(pd.concat([df_suico, nova]), ABA_SUICO)
            st.rerun()

else:
    tid = st.session_state.torneio_ativo
    tipo = st.session_state.tipo_ativo
    
    with st.sidebar:
        st.header(f"📍 {tid}")
        menu = st.radio("Menu", ["🏟️ Jogos", "📊 Classificação", "⚙️ Admin"])
        if st.button("🏠 Sair"): st.session_state.torneio_ativo = None; st.rerun()

    if tipo == "SUICO":
        if menu == "⚙️ Admin":
            st.subheader("⚙️ Painel Admin")
            senha = st.text_input("Senha", type="password")
            if senha == "123":
                st.success("Acesso Liberado!")
                
                # CAMPO DE TIMES SEMPRE VISÍVEL NO ADMIN
                st.markdown("---")
                st.subheader("📝 Registrar Times / Iniciar Torneio")
                txt = st.text_area("Cole os times aqui (um por linha):", height=200)
                
                if st.button("🚀 GERAR 1ª RODADA"):
                    times = [x.strip() for x in txt.split('\n') if x.strip()]
                    if len(times) >= 6:
                        random.shuffle(times)
                        jogos = []
                        for i in range(0, len(times), 2):
                            t1 = times[i]
                            t2 = times[i+1] if i+1 < len(times) else "BYE"
                            jogos.append({'torneio_id':tid, 'formato':'SUICO', 'fase':'Suico', 'rodada':1, 'a':t1, 'b':t2, 'gols_a':0, 'gols_b':0, 'finalizado':'NÃO'})
                        
                        df_suico = df_suico[df_suico['torneio_id'] != tid]
                        salvar_dados(pd.concat([df_suico, pd.DataFrame(jogos)]), ABA_SUICO)
                        st.rerun()
                    else:
                        st.error("Mínimo de 6 times!")
                
                if st.button("🚨 EXCLUIR ESTE TORNEIO"):
                    salvar_dados(df_suico[df_suico['torneio_id'] != tid], ABA_SUICO)
                    st.session_state.torneio_ativo = None; st.rerun()

        elif menu == "🏟️ Jogos":
            df_t = df_suico[df_suico['torneio_id'] == tid]
            jogos = df_t[df_t['fase'] == 'Suico']
            if jogos.empty:
                st.info("Aguardando sorteio no Admin.")
            else:
                for idx, r in jogos.iterrows():
                    with st.container(border=True):
                        st.write(f"**{r['a']}** vs **{r['b']}**")

    else:
        st.info("Modo Padrão - (Mantenha seu código aqui)")
