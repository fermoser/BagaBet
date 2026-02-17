import streamlit as st
import pandas as pd
import random
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="BAGA GESTOR PRO", layout="wide")

conn = st.connection("gsheets", type=GSheetsConnection)
ABA_JOGOS = "Página1" 
ABA_SUICO = "Suico"

# Colunas que o sistema precisa ter
COLS_SUICO = ['torneio_id', 'formato', 'fase', 'rodada', 'a', 'b', 'gols_a', 'gols_b', 'finalizado']

def carregar_dados(aba):
    try:
        df = conn.read(worksheet=aba, ttl="0s")
        if df is None or df.empty: return pd.DataFrame(columns=COLS_SUICO)
        df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
        for col in COLS_SUICO:
            if col not in df.columns: df[col] = None
        return df.dropna(how='all')
    except: return pd.DataFrame(columns=COLS_SUICO)

def salvar_dados(df, aba):
    if aba == ABA_SUICO:
        for col in COLS_SUICO:
            if col not in df.columns: df[col] = None
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
    
    ids_s = [str(x) for x in df_suico['torneio_id'].dropna().unique() if str(x).strip() != ""]
    ids_p = [str(x) for x in df_padrao['torneio_id'].dropna().unique() if str(x).strip() != ""]
    all_t = sorted(list(set(ids_s + ids_p)))
    
    if all_t:
        st.subheader("📂 Meus Torneios")
        cols = st.columns(3)
        for i, t in enumerate(all_t):
            icone = "⭐ " if t in ids_s else "🏆 "
            if cols[i%3].button(icone + t, key=f"btn_{t}"):
                st.session_state.torneio_ativo = t
                st.session_state.tipo_ativo = "SUICO" if t in ids_s else "PADRAO"
                st.rerun()

    st.divider()
    ns = st.text_input("Nome do Novo Suíço")
    if st.button("CRIAR SUÍÇO"):
        if ns:
            nova_linha = pd.DataFrame([{'torneio_id': ns, 'formato': 'SUICO', 'fase': 'Inscricao'}])
            salvar_dados(pd.concat([df_suico, nova_linha]), ABA_SUICO)
            st.rerun()

else:
    tid = st.session_state.torneio_ativo
    tipo = st.session_state.tipo_ativo
    
    with st.sidebar:
        st.header(f"📍 {tid}")
        menu = st.radio("Menu", ["🏟️ Jogos", "📊 Classificação", "⚙️ Admin"])
        if st.button("🏠 Sair"): st.session_state.torneio_ativo = None; st.rerun()

    if tipo == "SUICO":
        df_t = df_suico[df_suico['torneio_id'] == tid].copy()
        
        if menu == "⚙️ Admin":
            st.subheader("⚙️ Admin Suíço")
            senha = st.text_input("Senha", type="password")
            if senha == "123":
                st.success("Logado!")
                
                # A CAIXA AGORA FICA DENTRO DE UM EXPANDER E SEMPRE EXISTE
                with st.expander("📝 SORTEAR TIMES / RECOMEÇAR", expanded=True):
                    txt = st.text_area("Cole os times (um por linha):", height=200)
                    if st.button("GERAR 1ª RODADA"):
                        times = [x.strip() for x in txt.split('\n') if x.strip()]
                        if len(times) >= 6:
                            random.shuffle(times)
                            jogos = []
                            for i in range(0, len(times), 2):
                                t1 = times[i]
                                t2 = times[i+1] if i+1 < len(times) else "BYE"
                                jogos.append({'torneio_id':tid, 'formato':'SUICO', 'fase':'Suico', 'rodada':1, 'a':t1, 'b':t2, 'gols_a':(1 if t2=='BYE' else 0), 'gols_b':0, 'finalizado':('SIM' if t2=='BYE' else 'NÃO')})
                            
                            # Limpa o que tinha antes e salva os novos
                            df_suico = df_suico[df_suico['torneio_id'] != tid]
                            salvar_dados(pd.concat([df_suico, pd.DataFrame(jogos)]), ABA_SUICO)
                            st.rerun()
                
                if st.button("🚨 EXCLUIR TORNEIO"):
                    salvar_dados(df_suico[df_suico['torneio_id'] != tid], ABA_SUICO)
                    st.session_state.torneio_ativo = None; st.rerun()

        elif menu == "🏟️ Jogos":
            jogos = df_t[df_t['fase'] == 'Suico']
            if jogos.empty: st.info("Vá em Admin e gere a 1ª rodada.")
            else:
                for idx, r in jogos.iterrows():
                    with st.container(border=True):
                        st.write(f"**{r['a']}** {int(r['gols_a'])} x {int(r['gols_b'])} **{r['b']}**")
                        with st.expander("Placar"):
                            with st.form(f"f_{idx}"):
                                ga = st.number_input("A", 0, 99, int(r['gols_a']))
                                gb = st.number_input("B", 0, 99, int(r['gols_b']))
                                if st.form_submit_button("Ok"):
                                    # Usa o índice original para salvar na aba certa
                                    df_suico.loc[idx, ['gols_a', 'gols_b', 'finalizado']] = [ga, gb, "SIM"]
                                    salvar_dados(df_suico, ABA_SUICO); st.rerun()

    else:
        st.write("Aqui você cola o seu código original de LIGA/COPA.")
