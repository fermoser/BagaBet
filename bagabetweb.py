import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection

# Configuração simples
st.set_page_config(page_title="BAGA BET NUVEM")

# Tenta conectar com o Google
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except:
    st.error("Erro na conexão. Verifique os Secrets.")

st.title("⚽ BAGA BET - NUVEM")

# Criar um menu simples na lateral
menu = st.sidebar.selectbox("Menu", ["Jogos", "Novo Torneio"])

if menu == "Novo Torneio":
    st.subheader("Criar Novo Jogo")
    t1 = st.text_input("Time da Casa")
    t2 = st.text_input("Time Visitante")
    
    if st.button("Salvar Jogo na Planilha"):
        if t1 and t2:
            # Cria o dado
            novo_jogo = [{"a": t1, "b": t2, "ga": "0", "gb": "0"}]
            df = pd.DataFrame(novo_jogo).astype(str)
            
            # Envia para o Google
            try:
                conn.update(data=df)
                st.success("Jogo salvo com sucesso no Google Sheets!")
            except Exception as e:
                st.error(f"Erro ao enviar para o Google: {e}")
        else:
            st.warning("Preencha os nomes dos times!")

elif menu == "Jogos":
    st.subheader("Jogos Registrados")
    try:
        # Lê o que está na planilha agora
        df_lido = conn.read(ttl=0)
        if not df_lido.empty:
            st.table(df_lido)
        else:
            st.info("A planilha está vazia.")
    except:
        st.info("Nenhum dado encontrado na planilha ainda.")
