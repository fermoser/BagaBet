import streamlit as st
import pandas as pd
import itertools
from st_tigris import get_tigris_client

# --- CONFIGURAÇÃO TIGRIS ---
try:
    client = get_tigris_client()
    db = client.get_database("bagabet_db")
    collection = db.get_collection("torneios")
except:
    st.error("Erro ao conectar ao Tigris. Verifique se conectou o Data Source no Streamlit Cloud.")

# --- INICIALIZAÇÃO E PERSISTÊNCIA ---
if 'times' not in st.session_state:
    # Tenta carregar dados existentes do Tigris ao abrir o site
    try:
        doc = collection.find_one({"id": "principal"})
        if doc:
            st.session_state.times = doc["times"]
            st.session_state.jogos = doc["jogos"]
        else:
            st.session_state.times = []
            st.session_state.jogos = []
    except:
        st.session_state.times = []
        st.session_state.jogos = []

def salvar_dados():
    doc = {
        "id": "principal",
        "times": st.session_state.times,
        "jogos": st.session_state.jogos
    }
    collection.insert_or_replace([doc])

# --- INTERFACE ---
st.title("BAGA 🟢 BET - LIVE")

menu = st.sidebar.radio("Navegação", ["🏠 Início", "🏆 Novo Torneio", "⚽ Jogos & Apostas", "📊 Classificação"])

if menu == "🏆 Novo Torneio":
    qtd = st.number_input("Qtd de Times", 2, 20, 4)
    nomes = [st.text_input(f"Time {i+1}", key=f"t{i}") for i in range(qtd)]
    
    if st.button("GERAR TORNEIO"):
        st.session_state.times = [n for n in nomes if n]
        pares = list(itertools.combinations(st.session_state.times, 2))
        st.session_state.jogos = [{"a": p[0], "b": p[1], "ga": 0, "gb": 0, "finalizado": False, "apostas": []} for p in pares]
        salvar_dados()
        st.success("Torneio salvo no Tigris!")
        st.rerun()

elif menu == "⚽ Jogos & Apostas":
    st.header("⚽ Partidas e Palpites")
    
    for i, jogo in enumerate(st.session_state.jogos):
        with st.container(border=True):
            col1, col2 = st.columns([3, 1])
            
            with col1:
                status = "✅" if jogo["finalizado"] else "⏳"
                st.subheader(f"{status} {jogo['a']} {jogo['ga']} x {jogo['gb']} {jogo['b']}")
            
            with col2:
                # Botões de Ação
                if st.button("📝 Placar", key=f"pl{i}"):
                    editar_placar(i)
                if st.button("🎲 Apostar", key=f"ap{i}"):
                    nova_aposta(i)

            # --- AQUI APARECEM AS APOSTAS (COMO NO ORIGINAL) ---
            if jogo["apostas"]:
                df_aps = pd.DataFrame(jogo["apostas"])
                # Melhorando a visualização da tabela de apostas
                st.markdown("**Apostas Registradas:**")
                st.table(df_aps.rename(columns={'nome': 'Apostador', 'valor': 'R$', 'opcao': 'Palpite'}))
            else:
                st.caption("Nenhuma aposta neste jogo ainda.")

# --- MODAIS (DIALOGS) ---

@st.dialog("Lançar Placar")
def editar_placar(idx):
    j = st.session_state.jogos[idx]
    ga = st.number_input(f"Gols {j['a']}", value=j['ga'])
    gb = st.number_input(f"Gols {j['b']}", value=j['gb'])
    if st.button("Salvar e Sincronizar"):
        st.session_state.jogos[idx]["ga"] = ga
        st.session_state.jogos[idx]["gb"] = gb
        st.session_state.jogos[idx]["finalizado"] = True
        salvar_dados() # Manda pro Tigris
        st.rerun()

@st.dialog("Nova Aposta")
def nova_aposta(idx):
    j = st.session_state.jogos[idx]
    nome = st.text_input("Seu Nome")
    valor = st.number_input("Valor R$", 1.0)
    op = st.radio("Palpite", [j['a'], "Empate", j['b']])
    
    if st.button("Confirmar"):
        palpite = "A" if op == j['a'] else "B" if op == j['b'] else "E"
        st.session_state.jogos[idx]["apostas"].append({"nome": nome, "valor": valor, "opcao": palpite})
        salvar_dados() # Manda pro Tigris
        st.success("Aposta registrada na nuvem!")
        st.rerun()
