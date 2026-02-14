import streamlit as st
import pandas as pd
import itertools

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="BAGABET PRO", layout="wide", page_icon="⚽")

# --- GERENCIAMENTO DE DADOS (LOCAL) ---
# Como o Tigris está falhando na instalação, vamos usar o estado de sessão.
# Os dados ficarão salvos enquanto o site estiver aberto.
if 'times' not in st.session_state:
    st.session_state.times = []
    st.session_state.jogos = []

def salvar_dados():
    st.toast("Ação registrada com sucesso! ✅")

# --- LÓGICA ESPORTIVA ---
def recalcular_tabela():
    data = {t: {"Time": t, "P": 0, "V": 0, "E": 0, "D": 0, "GP": 0, "GC": 0, "SG": 0} for t in st.session_state.times}
    for j in st.session_state.jogos:
        if j.get("finalizado"):
            ga, gb = j["ga"], j["gb"]
            ta, tb = j["a"], j["b"]
            data[ta]["GP"] += ga; data[ta]["GC"] += gb
            data[tb]["GP"] += gb; data[tb]["GC"] += ga
            if ga > gb:
                data[ta]["P"] += 3; data[ta]["V"] += 1; data[tb]["D"] += 1
            elif gb > ga:
                data[tb]["P"] += 3; data[tb]["V"] += 1; data[ta]["D"] += 1
            else:
                data[ta]["P"] += 1; data[tb]["P"] += 1; data[ta]["E"] += 1; data[tb]["E"] += 1
    
    for t in data: data[t]["SG"] = data[t]["GP"] - data[t]["GC"]
    df = pd.DataFrame(data.values())
    return df.sort_values(by=["P", "V", "SG"], ascending=False).reset_index(drop=True) if not df.empty else df

# --- MODAIS (JANELAS) ---
@st.dialog("📝 Lançar Resultado")
def modal_placar(idx):
    jogo = st.session_state.jogos[idx]
    st.write(f"### {jogo['a']} vs {jogo['b']}")
    col1, col2 = st.columns(2)
    ga = col1.number_input(f"Gols {jogo['a']}", min_value=0, step=1)
    gb = col2.number_input(f"Gols {jogo['b']}", min_value=0, step=1)
    
    if st.button("SALVAR PLACAR"):
        st.session_state.jogos[idx]["ga"] = ga
        st.session_state.jogos[idx]["gb"] = gb
        st.session_state.jogos[idx]["finalizado"] = True
        st.rerun()

@st.dialog("🎲 Nova Aposta")
def modal_aposta(idx):
    jogo = st.session_state.jogos[idx]
    st.write(f"Apostar em: **{jogo['a']} x {jogo['b']}**")
    nome = st.text_input("Seu Nome")
    valor = st.number_input("Valor (R$)", min_value=1.0)
    escolha = st.radio("Palpite", [jogo['a'], "Empate", jogo['b']])
    
    if st.button("CONFIRMAR"):
        if nome:
            st.session_state.jogos[idx]["apostas"].append({
                "Nome": nome, "R$": valor, "Palpite": escolha
            })
            st.rerun()

# --- INTERFACE ---
st.title("BAGA 🟢 BET")

menu = st.sidebar.radio("Navegação", ["⚽ Jogos & Apostas", "📊 Classificação", "🏆 Novo Torneio"])

if menu == "🏆 Novo Torneio":
    st.header("Configurar Campeonato")
    qtd = st.number_input("Qtd de times", 2, 20, 4)
    nomes = [st.text_input(f"Time {i+1}", key=f"nt{i}") for i in range(qtd)]
    if st.button("GERAR"):
        st.session_state.times = [n for n in nomes if n]
        pares = list(itertools.combinations(st.session_state.times, 2))
        st.session_state.jogos = [{"a": p[0], "b": p[1], "ga": 0, "gb": 0, "finalizado": False, "apostas": []} for p in pares]
        st.success("Torneio criado!")

elif menu == "⚽ Jogos & Apostas":
    st.header("Partidas")
    for i, jogo in enumerate(st.session_state.jogos):
        with st.container(border=True):
            c1, c2, c3 = st.columns([3, 1, 1])
            status = "✅" if jogo["finalizado"] else "⏳"
            c1.subheader(f"{status} {jogo['a']} {jogo['ga']} x {jogo['gb']} {jogo['b']}")
            if c2.button("📝 Placar", key=f"p{i}"): modal_placar(i)
            if c3.button("🎲 Apostar", key=f"a{i}"): modal_aposta(i)
            
            if jogo["apostas"]:
                st.table(pd.DataFrame(jogo["apostas"]))

elif menu == "📊 Classificação":
    st.table(recalcular_tabela())
