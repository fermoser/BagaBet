import streamlit as st
import pandas as pd
import itertools
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="BAGABET PRO", layout="wide", page_icon="⚽")

# --- CONEXÃO COM GOOGLE SHEETS ---
conn = st.connection("gsheets", type=GSheetsConnection)

def carregar_dados_nuvem():
    try:
        # Tenta ler a planilha (aba principal)
        df = conn.read(ttl=0) # ttl=0 força a ler dados novos, sem cache
        if not df.empty:
            # Aqui convertemos a tabela de volta para o formato de lista do Python
            # Isso é um pouco técnico, mas garante que o app entenda os dados
            st.session_state.jogos = df.to_dict('records')
            # Extrai os nomes dos times únicos das colunas 'a' e 'b'
            times_a = df['a'].unique().tolist()
            times_b = df['b'].unique().tolist()
            st.session_state.times = list(set(times_a + times_b))
    except:
        if 'times' not in st.session_state:
            st.session_state.times = []
            st.session_state.jogos = []

def salvar_dados_nuvem():
    if 'jogos' in st.session_state and st.session_state.jogos:
        df_para_salvar = pd.DataFrame(st.session_state.jogos)
        # Limpa colunas de objetos complexos (como listas de apostas) para o Sheets não dar erro
        # No Sheets, as apostas serão salvas como texto formatado
        conn.update(data=df_para_salvar)
        st.toast("Sincronizado com Google Sheets! 📈")

# Inicializa dados
if 'times' not in st.session_state:
    carregar_dados_nuvem()

# --- LÓGICA ESPORTIVA ---
def recalcular_tabela():
    data = {t: {"Time": t, "P": 0, "V": 0, "E": 0, "D": 0, "GP": 0, "GC": 0, "SG": 0} for t in st.session_state.times}
    for j in st.session_state.jogos:
        if j.get("finalizado"):
            ga, gb = int(j["ga"]), int(j["gb"])
            ta, tb = j["a"], j["b"]
            data[ta]["GP"] += ga; data[ta]["GC"] += gb
            data[tb]["GP"] += gb; data[tb]["GC"] += ga
            if ga > gb:
                data[ta]["P"] += 3; data[ta]["V"] += 1; data[tb]["D"] += 1
            elif gb > ga:
                data[tb]["P"] += 3; data[tb]["V"] += 1; data[ta]["D"] += 1
            else:
                data[ta]["P"] += 1; data[tb]["P"] += 1; data[ta]["E"] += 1; data[tb]["E"] += 1
    
    df = pd.DataFrame(data.values())
    return df.sort_values(by=["P", "V"], ascending=False).reset_index(drop=True) if not df.empty else df

# --- MODAIS ---
@st.dialog("📝 Lançar Resultado")
def modal_placar(idx):
    jogo = st.session_state.jogos[idx]
    ga = st.number_input(f"Gols {jogo['a']}", min_value=0, value=int(jogo['ga']))
    gb = st.number_input(f"Gols {jogo['b']}", min_value=0, value=int(jogo['gb']))
    if st.button("SALVAR"):
        st.session_state.jogos[idx]["ga"] = ga
        st.session_state.jogos[idx]["gb"] = gb
        st.session_state.jogos[idx]["finalizado"] = True
        salvar_dados_nuvem()
        st.rerun()

@st.dialog("🎲 Nova Aposta")
def modal_aposta(idx):
    jogo = st.session_state.jogos[idx]
    nome = st.text_input("Seu Nome")
    valor = st.number_input("Valor (R$)", min_value=1.0)
    escolha = st.radio("Palpite", [jogo['a'], "Empate", jogo['b']])
    if st.button("CONFIRMAR"):
        if "apostas" not in st.session_state.jogos[idx] or isinstance(st.session_state.jogos[idx]["apostas"], float):
             st.session_state.jogos[idx]["apostas"] = []
        
        # Guardamos a aposta como uma string simples para o Sheets aceitar fácil
        nova_aposta = f"{nome}: {escolha} (R${valor})"
        if isinstance(st.session_state.jogos[idx]["apostas"], str):
            st.session_state.jogos[idx]["apostas"] += f" | {nova_aposta}"
        else:
            st.session_state.jogos[idx]["apostas"] = nova_aposta
            
        salvar_dados_nuvem()
        st.rerun()

# --- INTERFACE ---
st.title("BAGA 🟢 BET - CLOUD")

menu = st.sidebar.radio("Navegação", ["⚽ Jogos", "📊 Tabela", "🏆 Novo Torneio"])

if menu == "🏆 Novo Torneio":
    qtd = st.number_input("Times", 2, 20, 4)
    nomes = [st.text_input(f"Time {i+1}", key=f"n{i}") for i in range(qtd)]
    if st.button("GERAR TORNEIO"):
        st.session_state.times = [n for n in nomes if n]
        pares = list(itertools.combinations(st.session_state.times, 2))
        st.session_state.jogos = [{"a": p[0], "b": p[1], "ga": 0, "gb": 0, "finalizado": False, "apostas": ""} for p in pares]
        salvar_dados_nuvem()
        st.success("Torneio Criado!")

elif menu == "⚽ Jogos":
    for i, jogo in enumerate(st.session_state.jogos):
        with st.container(border=True):
            col1, col2, col3 = st.columns([3, 1, 1])
            col1.write(f"**{jogo['a']} {jogo['ga']} x {jogo['gb']} {jogo['b']}**")
            if col2.button("Placar", key=f"p{i}"): modal_placar(i)
            if col3.button("Apostar", key=f"a{i}"): modal_aposta(i)
            if jogo.get("apostas"):
                st.caption(f"Apostas: {jogo['apostas']}")

elif menu == "📊 Tabela":
    st.table(recalcular_tabela())
