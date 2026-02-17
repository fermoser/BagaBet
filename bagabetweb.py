import streamlit as st
import pandas as pd
import random
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="BAGA GESTOR PRO", layout="wide")

conn = st.connection("gsheets", type=GSheetsConnection)
ABA_JOGOS = "Página1" 
ABA_SUICO = "Suico"

# Colunas padrão para garantir que a planilha não quebre
COLS_PADRAO = ['torneio_id', 'formato', 'fase', 'a', 'b', 'gols_a', 'gols_b', 'ida_a', 'ida_b', 'volta_a', 'volta_b', 'pen_a', 'pen_b', 'modo_copa', 'finalizado']
COLS_SUICO = ['torneio_id', 'formato', 'fase', 'rodada', 'a', 'b', 'gols_a', 'gols_b', 'finalizado']

# --- FUNÇÕES DE DADOS ---
def carregar_dados(aba):
    try:
        df = conn.read(worksheet=aba, ttl="0s")
        if df is None or df.empty:
            return pd.DataFrame(columns=COLS_SUICO if aba == ABA_SUICO else COLS_PADRAO)
        df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
        cols_alvo = COLS_SUICO if aba == ABA_SUICO else COLS_PADRAO
        for col in cols_alvo:
            if col not in df.columns: df[col] = None
        return df.dropna(how='all')
    except:
        return pd.DataFrame(columns=COLS_SUICO if aba == ABA_SUICO else COLS_PADRAO)

def salvar_dados(df, aba):
    cols_alvo = COLS_SUICO if aba == ABA_SUICO else COLS_PADRAO
    for col in cols_alvo:
        if col not in df.columns: df[col] = None
    df = df[cols_alvo]
    if 'torneio_id' in df.columns:
        df = df.dropna(subset=['torneio_id'])
    conn.update(worksheet=aba, data=df)
    st.cache_data.clear()

# --- NAVEGAÇÃO ---
if 'torneio_ativo' not in st.session_state: st.session_state.torneio_ativo = None
if 'tipo_ativo' not in st.session_state: st.session_state.tipo_ativo = None 

df_padrao = carregar_dados(ABA_JOGOS)
df_suico = carregar_dados(ABA_SUICO)

# --- TELA INICIAL ---
if st.session_state.torneio_ativo is None:
    st.title("⚽ BAGA GESTOR PRO")
    
    ids_p = [str(x) for x in df_padrao['torneio_id'].dropna().unique() if str(x).strip() != ""]
    ids_s = [str(x) for x in df_suico['torneio_id'].dropna().unique() if str(x).strip() != ""]
    all_t = sorted(list(set(ids_p + ids_s)))
    
    if all_t:
        st.subheader("📂 Meus Torneios")
        cols = st.columns(3)
        for i, t in enumerate(all_t):
            icone = "⭐ " if t in ids_s else "🏆 "
            if cols[i%3].button(icone + t, key=f"btn_{t}", use_container_width=True):
                st.session_state.torneio_ativo = t
                st.session_state.tipo_ativo = "SUICO" if t in ids_s else "PADRAO"
                st.rerun()

    st.divider()
    c1, c2 = st.columns(2)
    with c1.container(border=True):
        st.subheader("🏆 Nova Liga/Copa")
        n_p = st.text_input("Nome (Padrão)")
        if st.button("CRIAR PADRÃO"):
            if n_p:
                salvar_dados(pd.concat([df_padrao, pd.DataFrame([{'torneio_id':n_p,'fase':'Inscricao'}])]), ABA_JOGOS); st.rerun()
    with c2.container(border=True):
        st.subheader("⭐ Novo Suíço")
        n_s = st.text_input("Nome (Suíço)")
        if st.button("CRIAR SUÍÇO"):
            if n_s:
                salvar_dados(pd.concat([df_suico, pd.DataFrame([{'torneio_id':n_s,'formato':'SUICO','fase':'Inscricao'}])]), ABA_SUICO); st.rerun()

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
            senha = st.text_input("Senha Admin", type="password")
            if senha == "123":
                st.success("Acesso Liberado")
                with st.expander("📝 Gerar Partidas", expanded=True):
                    txt = st.text_area("Times (um por linha)")
                    if st.button("GERAR 1ª RODADA"):
                        times = [x.strip() for x in txt.split('\n') if x.strip()]
                        if len(times) >= 6:
                            random.shuffle(times)
                            jogos = []
                            for i in range(0, len(times), 2):
                                t1 = times[i]
                                t2 = times[i+1] if i+1 < len(times) else "BYE"
                                jogos.append({'torneio_id':tid, 'formato':'SUICO', 'fase':'Suico', 'rodada':1, 'a':t1, 'b':t2, 'gols_a':(1 if t2=='BYE' else 0), 'gols_b':0, 'finalizado':('SIM' if t2=='BYE' else 'NÃO')})
                            df_limpo = df_suico[df_suico['torneio_id'] != tid]
                            salvar_dados(pd.concat([df_limpo, pd.DataFrame(jogos)]), ABA_SUICO); st.rerun()
                
                if st.button("🚨 EXCLUIR"):
                    salvar_dados(df_suico[df_suico['torneio_id'] != tid], ABA_SUICO)
                    st.session_state.torneio_ativo = None; st.rerun()

        elif menu == "🏟️ Jogos":
            jogos = df_t[df_t['fase'] == 'Suico']
            if jogos.empty: st.warning("Use o Admin para sortear os times.")
            for idx, r in jogos.iterrows():
                with st.container(border=True):
                    c1, c2, c3 = st.columns([2,1,2])
                    c1.write(f"**{r['a']}**")
                    c2.write(f"{int(r['gols_a'])} x {int(r['gols_b'])}")
                    c3.write(f"**{r['b']}**")
                    with st.expander("Placar"):
                        with st.form(f"f_{idx}"):
                            ga = st.number_input("Gols A", 0, 99, int(r['gols_a']))
                            gb = st.number_input("Gols B", 0, 99, int(r['gols_b']))
                            if st.form_submit_button("Salvar"):
                                df_suico.loc[idx, ['gols_a','gols_b','finalizado']] = [ga, gb, "SIM"]
                                salvar_dados(df_suico, ABA_SUICO); st.rerun()

    else:
        # MODO PADRÃO (LIGA/COPA) - Cole seu código de exibição aqui se quiser
        st.info("Modo Liga/Copa Ativo.")
