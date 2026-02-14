import streamlit as st
import pandas as pd
import itertools
from streamlit_gsheets import GSheetsConnection

# Configuração da página
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
        # Cria o DataFrame
        df = pd.DataFrame(st.session_state.jogos)
        # CONVERTE TUDO PARA TEXTO (Isso mata o erro UnsupportedOperation)
        df = df.astype(str) 
        # Envia para a planilha
        conn.update(data=df)
        st.toast("Dados salvos na nuvem! ✅")

# --- INTERFACE ---
st.title("⚽ BAGA BET - SISTEMA DE APOSTAS")

menu = st.sidebar.radio("Navegação", ["Jogos & Apostas", "Classificação", "Novo Torneio"])

if menu == "Novo Torneio":
    st.header("🏆 Criar Novo Campeonato")
    qtd = st.number_input("Quantidade de Times", 2, 20, 4)
    nomes = [st.text_input(f"Time {i+1}", key=f"n{i}") for i in range(qtd)]
    
    if st.button("LIMPAR PLANILHA E GERAR TORNEIO"):
        st.session_state.times = [n for n in nomes if n]
        pares = list(itertools.combinations(st.session_state.times, 2))
        st.session_state.jogos = []
        for p in pares:
            st.session_state.jogos.append({
                "a": str(p[0]), 
                "b": str(p[1]), 
                "ga": "0", 
                "gb": "0", 
                "finalizado": "False", 
                "apostas": ""
            })
        salvar()
        st.success("Torneio criado e salvo!")
        st.rerun()

elif menu == "Jogos & Apostas":
    if not st.session_state.get('jogos'):
        st.warning("Nenhum jogo encontrado. Vá em 'Novo Torneio'.")
    else:
        for i, jogo in enumerate(st.session_state.jogos):
            with st.container(border=True):
                col1, col2, col3 = st.columns([3, 1, 1])
                col1.subheader(f"{jogo['a']} {jogo['ga']} x {jogo['gb']} {jogo['b']}")
                
                if col2.button("Placar", key=f"btn_p_{i}"):
                    lancar_placar(i)
                if col3.button("Apostar", key=f"btn_a_{i}"):
                    fazer_aposta(i)
                
                if jogo['apostas']:
                    st.caption(f"Apostas: {jogo['apostas']}")

elif menu == "Classificação":
    st.header("📊 Tabela de Pontos")
    # Lógica simples de pontos
    data = {t: {"Time": t, "P": 0, "V": 0} for t in st.session_state.times}
    for j in st.session_state.jogos:
        if j['finalizado'] == "True":
            ga, gb = int(j['ga']), int(j['gb'])
            if ga > gb: data[j['a']]["P"] += 3; data[j['a']]["V"] += 1
            elif gb > ga: data[j['b']]["P"] += 3; data[j['b']]["V"] += 1
            else: data[j['a']]["P"] += 1; data[j['b']]["P"] += 1
    
    df_rank = pd.DataFrame(data.values()).sort_values(by="P", ascending=False)
    st.table(df_rank)

@st.dialog("Registrar Placar")
def lancar_placar(idx):
    jogo = st.session_state.jogos[idx]
    st.write(f"{jogo['a']} vs {jogo['b']}")
    ga = st.number_input(f"Gols {jogo['a']}", min_value=0, step=1, value=int(jogo['ga']))
    gb = st.number_input(f"Gols {jogo['b']}", min_value=0, step=1, value=int(jogo['gb']))
    if st.button("SALVAR RESULTADO"):
        st.session_state.jogos[idx]['ga'] = str(ga)
        st.session_state.jogos[idx]['gb'] = str(gb)
        st.session_state.jogos[idx]['finalizado'] = "True"
        salvar()
        st.rerun()

@st.dialog("Fazer Aposta")
def fazer_aposta(idx):
    nome = st.text_input("Seu nome")
    palpite = st.radio("Seu palpite", ["Mandante", "Empate", "Visitante"])
    if st.button("CONFIRMAR APOSTA"):
        nova_aposta = f"{nome}({palpite})"
        antiga = st.session_state.jogos[idx]['apostas']
        st.session_state.jogos[idx]['apostas'] = f"{antiga} | {nova_aposta}" if antiga else nova_aposta
        salvar()
        st.rerun()

