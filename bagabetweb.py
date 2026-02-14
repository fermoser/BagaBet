import streamlit as st
import pandas as pd
import itertools
from streamlit_gsheets import GSheetsConnection

# CONFIGURAÇÃO INICIAL
st.set_page_config(page_title="BAGA BET", layout="wide")

# Conexão com a planilha
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error("Erro na conexão GSheets. Verifique seus Secrets.")

# FUNÇÃO PARA SALVAR
def salvar():
    if 'jogos' in st.session_state and st.session_state.jogos:
        df = pd.DataFrame(st.session_state.jogos).astype(str)
        # Mostra na tela para termos certeza que o código chegou aqui
        st.write("Tentando salvar:", df)
        try:
            conn.update(data=df)
            st.success("Dados enviados ao Google!")
        except Exception as e:
            st.error(f"O Google não aceitou os dados: {e}")

# INICIALIZAÇÃO DE VARIÁVEIS
if 'jogos' not in st.session_state:
    st.session_state.jogos = []

# INTERFACE - MENU
st.title("⚽ BAGA BET - NUVEM")
menu = st.sidebar.radio("Escolha uma opção:", ["Ver Jogos", "Novo Torneio"])

if menu == "Novo Torneio":
    st.subheader("Configurar Campeonato")
    time1 = st.text_input("Time 1")
    time2 = st.text_input("Time 2")
    
    if st.button("GERAR TORNEIO"):
        if time1 and time2:
            st.session_state.jogos = [
                {"a": time1, "b": time2, "ga": "0", "gb": "0", "apostas": ""}
            ]
            salvar()
            st.rerun()
        else:
            st.warning("Preencha os nomes dos times!")

elif menu == "Ver Jogos":
    if not st.session_state.jogos:
        st.info("Nenhum jogo criado ainda.")
    else:
        for i, jogo in enumerate(st.session_state.jogos):
            with st.container(border=True):
                st.write(f"**{jogo['a']} {jogo['ga']} x {jogo['gb']} {jogo['b']}**")
                if st.button(f"Gols do {jogo['a']}", key=f"btn{i}"):
                    # Aumenta o gol e salva
                    novo_gol = int(jogo['ga']) + 1
                    st.session_state.jogos[i]['ga'] = str(novo_gol)
                    salvar()
                    st.rerun()
