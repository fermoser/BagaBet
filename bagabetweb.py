import streamlit as st
import pandas as pd
import random
from streamlit_gsheets import GSheetsConnection

st.set_page_config(page_title="BAGA DEBUG", layout="wide")

# 1. CONEXÃO
conn = st.connection("gsheets", type=GSheetsConnection)

# 2. LIMPEZA DE CACHE (Botão para forçar o app a ler o Google Sheets de novo)
if st.sidebar.button("♻️ LIMPAR MEMÓRIA DO APP"):
    st.cache_data.clear()
    st.rerun()

# 3. LEITURA DIRETA
def carregar(aba):
    try:
        # ttl=0 força o app a não guardar memória velha
        return conn.read(worksheet=aba, ttl=0).dropna(how='all')
    except Exception as e:
        st.error(f"Erro ao ler aba {aba}: {e}")
        return pd.DataFrame()

df_suico = carregar("Suico")

st.title("⚽ TESTE DE CONEXÃO")

# MOSTRA O QUE TEM NA PLANILHA AGORA
with st.expander("🔍 Ver o que o Python está lendo no Google Sheets"):
    st.write(df_suico)

# 4. LÓGICA DE EXIBIÇÃO
if df_suico.empty:
    st.warning("A planilha 'Suico' parece vazia para o Python.")
else:
    # Pega os nomes dos torneios
    lista_torneios = df_suico['torneio_id'].unique().tolist()
    
    st.subheader("Torneios Encontrados:")
    for t in lista_torneios:
        if st.button(f"Abrir: {t}"):
            st.session_state.torneio_ativo = t
            st.rerun()

# 5. ADMIN "NA MARRA"
if 'torneio_ativo' in st.session_state:
    st.divider()
    st.header(f"⚙️ Admin: {st.session_state.torneio_ativo}")
    
    senha = st.text_input("Senha", type="password")
    if senha == "123":
        st.success("Logado!")
        
        # A CAIXA DE TEXTO QUE VOCÊ PRECISA
        txt = st.text_area("COLE OS TIMES AQUI (UM POR LINHA)")
        
        if st.button("🚀 GERAR JOGOS AGORA"):
            times = [x.strip() for x in txt.split('\n') if x.strip()]
            if len(times) >= 2:
                # Criando os jogos
                novos = []
                for i in range(0, len(times), 2):
                    t1 = times[i]
                    t2 = times[i+1] if i+1 < len(times) else "BYE"
                    novos.append({'torneio_id': st.session_state.torneio_ativo, 'a': t1, 'b': t2, 'fase': 'Suico'})
                
                # Salvando
                df_final = pd.concat([df_suico, pd.DataFrame(novos)])
                conn.update(worksheet="Suico", data=df_final)
                st.cache_data.clear()
                st.success("Salvou! Clique em 'Limpar Memória' na lateral.")
            else:
                st.error("Coloque pelo menos 2 times para testar.")

st.divider()
if st.button("CRIAR NOVO TESTE"):
    n = "Teste_" + str(random.randint(1,999))
    df_novo = pd.concat([df_suico, pd.DataFrame([{'torneio_id': n, 'fase': 'Inscricao'}])])
    conn.update(worksheet="Suico", data=df_novo)
    st.cache_data.clear()
    st.rerun()
