import streamlit as st
import pandas as pd
import itertools
from streamlit_gsheets import GSheetsConnection

# 1. CONFIGURAÇÃO
st.set_page_config(page_title="BAGA BET CLOUD", layout="wide")
conn = st.connection("gsheets", type=GSheetsConnection)

# 2. FUNÇÕES DE DADOS (COM DEBUG)
def salvar():
    if 'jogos' in st.session_state and st.session_state.jogos:
        df = pd.DataFrame(st.session_state.jogos).astype(str)
        
        # ISSO VAI MOSTRAR OS DADOS NA TELA PARA VOCÊ VER
        st.subheader("DEBUG: Dados sendo enviados:")
        st.write(df) 
        
        try:
            # Tenta salvar sem especificar aba primeiro para ver se vai
            conn.update(data=df)
            st.success("Comando enviado ao Google Sheets! ✅")
        except Exception as e:
            st.error(f"Erro na conexão: {e}")

def carregar_dados():
    try:
        # Tenta ler a planilha
        df = conn.read(ttl=0)
        if not df.empty:
            st.session_state.jogos = df.to_dict('records')
            # Reconstrói a lista de times única
            times_a = df['a'].unique().tolist()
            times_b = df['b'].unique().tolist()
            st.session_state.times = list(set(times_a + times_b))
    except:
        st.session_state.jogos = []
        st.session_state.times = []

# Inicialização
if 'jogos' not in st.session_state:
    carregar_dados()
