import streamlit as st
import pandas as pd
import itertools
from streamlit_gsheets import GSheetsConnection

st.set_page_config(page_title="BAGA BET CLOUD", layout="wide")
conn = st.connection("gsheets", type=GSheetsConnection)

def carregar_dados():
try:
    df = conn.read(ttl=0)
        if not df.empty:
            st.session_state.jogos = df.to_dict('records')
            t_a = df['a'].astype(str).tolist() if 'a' in df else []
            t_b = df['b'].astype(str).tolist() if 'b' in df else []
            st.session_state.times = list(set(t_a + t_b))
except:
        if 'times' not in st.session_state:
            st.session_state.times = []
            st.session_state.jogos = []

if 'times' not in st.session_state:
carregar_dados()

def salvar():
     if 'jogos' in st.session_state and st.session_state.jogos:
        df = pd.DataFrame(st.session_state.jogos).astype(str)
        conn.update(data=df)
        st.toast("Salvo no Google Sheets!")

st.title("⚽ BAGA BET - MODO NUVEM")
menu = st.sidebar.radio("Menu", ["Jogos", "Tabela", "Novo Torneio"])

if menu == "Novo Torneio":
qtd = st.number_input("Qtd Times", 2, 20, 4)
nomes = [st.text_input(f"Time {i+1}", key=f"n{i}") for i in range(qtd)]
if st.button("GERAR NOVO TORNEIO"):
st.session_state.times = [n for n in nomes if n]
pares = list(itertools.combinations(st.session_state.times, 2))
st.session_state.jogos = []
for p in pares:
st.session_state.jogos.append({"a": str(p[0]), "b": str(p[1]), "ga": "0", "gb": "0", "finalizado": "False", "apostas": ""})
salvar()
st.rerun()

elif menu == "Jogos":
if not st.session_state.jogos:
st.info("Crie um torneio!")
else:
for i, jogo in enumerate(st.session_state.jogos):
with st.container(border=True):
st.write(f"{jogo['a']} {jogo['ga']} x {jogo['gb']} {jogo['b']}")
c1, c2 = st.columns(2)
if c1.button(f"Placar", key=f"p{i}"): lancar_placar(i)
if c2.button(f"Aposta", key=f"ap{i}"): fazer_aposta(i)
if jogo['apostas']: st.caption(f"Palpites: {jogo['apostas']}")

@st.dialog("Placar")
def lancar_placar(idx):
ga = st.number_input("Gols A", value=0)
gb = st.number_input("Gols B", value=0)
if st.button("Confirmar"):
st.session_state.jogos[idx]['ga'] = str(ga)
st.session_state.jogos[idx]['gb'] = str(gb)
st.session_state.jogos[idx]['finalizado'] = "True"
salvar()
st.rerun()

@st.dialog("Aposta")
def fazer_aposta(idx):
nome = st.text_input("Nome")
if st.button("Apostar"):
st.session_state.jogos[idx]['apostas'] += f" | {nome}"
salvar()
st.rerun()

