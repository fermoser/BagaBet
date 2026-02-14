import streamlit as st
import pandas as pd
import itertools
from streamlit_gsheets import GSheetsConnection

# 1. CONFIGURAÇÃO
st.set_page_config(page_title="BAGA BET CLOUD", layout="wide")
conn = st.connection("gsheets", type=GSheetsConnection)

# 2. FUNÇÕES DE DADOS
def salvar():
    if 'jogos' in st.session_state and st.session_state.jogos:
        df = pd.DataFrame(st.session_state.jogos).astype(str)
        conn.update(worksheet="Página1", data=df)
        st.toast("Dados salvos! ✅")

def carregar_dados():
    try:
        df = conn.read(worksheet="Página1", ttl=0)
        if not df.empty:
            st.session_state.jogos = df.to_dict('records')
            t_a = df['a'].astype(str).tolist() if 'a' in df else []
            t_b = df['b'].astype(str).tolist() if 'b' in df else []
            st.session_state.times = list(set(t_a + t_b))
    except:
        st.session_state.jogos = []
        st.session_state.times = []

if 'jogos' not in st.session_state:
    carregar_dados()

# 3. FUNÇÕES DE DIÁLOGO (PRECISAM VIR ANTES DO MENU)
@st.dialog("Lançar Placar")
def lancar_placar(idx):
    jogo = st.session_state.jogos[idx]
    st.write(f"Jogo: {jogo['a']} x {jogo['b']}")
    ga = st.number_input("Gols Mandante", value=int(jogo['ga']))
    gb = st.number_input("Gols Visitante", value=int(jogo['gb']))
    if st.button("Confirmar Resultado"):
        st.session_state.jogos[idx]['ga'] = str(ga)
        st.session_state.jogos[idx]['gb'] = str(gb)
        st.session_state.jogos[idx]['finalizado'] = "True"
        salvar()
        st.rerun()

@st.dialog("Fazer Aposta")
def fazer_aposta(idx):
    nome = st.text_input("Seu Nome")
    palpite = st.radio("Quem vence?", ["Mandante", "Empate", "Visitante"])
    if st.button("Registrar Palpite"):
        nova = f"{nome}({palpite})"
        antiga = st.session_state.jogos[idx]['apostas']
        st.session_state.jogos[idx]['apostas'] = f"{antiga} | {nova}" if antiga != "nan" and antiga else nova
        salvar()
        st.rerun()

# 4. MENU E INTERFACE
st.title("⚽ BAGA BET - MODO NUVEM")
menu = st.sidebar.radio("Navegação", ["Jogos", "Tabela", "Novo Torneio"])

if menu == "Novo Torneio":
    qtd = st.number_input("Times", 2, 20, 4)
    nomes = [st.text_input(f"Time {i+1}", key=f"n{i}") for i in range(qtd)]
    if st.button("GERAR NOVO TORNEIO"):
        st.session_state.times = [n for n in nomes if n]
        pares = list(itertools.combinations(st.session_state.times, 2))
        st.session_state.jogos = [{"a": p[0], "b": p[1], "ga": "0", "gb": "0", "finalizado": "False", "apostas": ""} for p in pares]
        salvar()
        st.rerun()

elif menu == "Jogos":
    if not st.session_state.jogos:
        st.info("Crie um torneio!")
    else:
        for i, jogo in enumerate(st.session_state.jogos):
            with st.container(border=True):
                st.write(f"**{jogo['a']} {jogo['ga']} x {jogo['gb']} {jogo['b']}**")
                c1, c2 = st.columns(2)
                if c1.button("Placar", key=f"p{i}"):
                    lancar_placar(i)
                if c2.button("Aposta", key=f"a{i}"):
                    fazer_aposta(i)
                if jogo['apostas'] != "nan" and jogo['apostas']:
                    st.caption(f"Palpites: {jogo['apostas']}")
