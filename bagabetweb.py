import streamlit as st
import pandas as pd
import itertools
import json

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="BAGABET Web", page_icon="⚽", layout="wide")

# Estilização customizada (CSS) para manter o visual verde
st.markdown("""
    <style>
    .main { background-color: #f5f7fa; }
    .stButton>button { background-color: #1DB954; color: white; border-radius: 8px; border: none; }
    .stButton>button:hover { background-color: #179443; color: white; }
    h1, h2, h3 { color: #1DB954; font-family: 'Segoe UI Black', sans-serif; }
    </style>
    """, unsafe_allow_html=True)

# --- INICIALIZAÇÃO DO ESTADO (BANCO DE DADOS) ---
if 'jogos' not in st.session_state:
    st.session_state.jogos = []
if 'times' not in st.session_state:
    st.session_state.times = []
if 'apostas' not in st.session_state:
    st.session_state.apostas = {} # Dicionário para armazenar apostas por jogo

# --- FUNÇÕES DE LÓGICA ---
def recalcular_tabela():
    data = {t: {"Time": t, "P": 0, "V": 0, "E": 0, "D": 0, "GP": 0, "GC": 0, "SG": 0} for t in st.session_state.times}
    for j in st.session_state.jogos:
        if j["finalizado"]:
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
    if not df.empty:
        df = df.sort_values(by=["P", "V", "SG"], ascending=False).reset_index(drop=True)
    return df

# --- MENU LATERAL ---
with st.sidebar:
    st.title("BAGA 🟢 BET")
    st.write("Gestão de Torneios")
    menu = st.radio("Navegar para:", ["🏠 Início", "🏆 Novo Torneio", "⚽ Jogos & Apostas", "📊 Classificação", "💰 Ranking"])
    
    st.divider()
    if st.button("♻️ Resetar Sistema"):
        st.session_state.clear()
        st.rerun()

# --- TELAS ---
if menu == "🏠 Início":
    st.title("Bem-vindo ao BAGABET ⚽")
    st.write("O seu gerenciador de torneios agora está na web.")
    st.info("Use o menu lateral para configurar um novo torneio ou gerenciar seus jogos.")
    
    if st.session_state.times:
        st.metric("Times Cadastrados", len(st.session_state.times))
        st.metric("Jogos Realizados", len([j for j in st.session_state.jogos if j["finalizado"]]))

elif menu == "🏆 Novo Torneio":
    st.header("Configurar Novo Torneio")
    qtd = st.number_input("Quantos times participarão?", min_value=2, max_value=20, value=4)
    
    with st.form("form_times"):
        cols = st.columns(2)
        nomes_input = []
        for i in range(qtd):
            col_idx = 0 if i < qtd/2 else 1
            nome = cols[col_idx].text_input(f"Time {i+1}", placeholder=f"Ex: Time {i+1}")
            nomes_input.append(nome)
        
        if st.form_submit_button("GERAR TORNEIO 🚀"):
            times_limpos = [n for n in nomes_input if n.strip()]
            if len(times_limpos) < 2:
                st.error("Preencha pelo menos 2 nomes de times.")
            else:
                st.session_state.times = times_limpos
                pares = list(itertools.combinations(times_limpos, 2))
                st.session_state.jogos = [{"id": i, "a": p[0], "b": p[1], "ga": 0, "gb": 0, "finalizado": False} for i, p in enumerate(pares)]
                st.success("Torneio gerado com sucesso!")
                st.rerun()

elif menu == "⚽ Jogos & Apostas":
    st.header("Gerenciamento de Partidas")
    
    if not st.session_state.jogos:
        st.warning("Nenhum torneio ativo. Vá em 'Novo Torneio'.")
    else:
        for i, jogo in enumerate(st.session_state.jogos):
            with st.expander(f"{'✅' if jogo['finalizado'] else '⏳'} {jogo['a']} vs {jogo['b']}"):
                col1, col2, col3 = st.columns([2, 1, 2])
                
                # Placar
                ga = col1.number_input(f"Gols {jogo['a']}", min_value=0, value=jogo['ga'], key=f"ga_{i}")
                gb = col3.number_input(f"Gols {jogo['b']}", min_value=0, value=jogo['gb'], key=f"gb_{i}")
                
                if st.button("Salvar Resultado", key=f"save_{i}"):
                    st.session_state.jogos[i]["ga"] = ga
                    st.session_state.jogos[i]["gb"] = gb
                    st.session_state.jogos[i]["finalizado"] = True
                    st.success("Placar atualizado!")
                    st.rerun()
                
                st.divider()
                st.subheader("Apostas")
                # Sistema de Apostas simples
                nome_ap = st.text_input("Nome do Apostador", key=f"ap_n_{i}")
                valor_ap = st.number_input("Valor R$", min_value=1.0, key=f"ap_v_{i}")
                escolha = st.selectbox("Palpite", [jogo['a'], "Empate", jogo['b']], key=f"ap_e_{i}")
                
                if st.button("Registrar Aposta", key=f"btn_ap_{i}"):
                    if f"jogo_{i}" not in st.session_state.apostas:
                        st.session_state.apostas[f"jogo_{i}"] = []
                    
                    st.session_state.apostas[f"jogo_{i}"].append({
                        "nome": nome_ap, "valor": valor_ap, "palpite": escolha
                    })
                    st.toast(f"Aposta de {nome_ap} registrada!")

elif menu == "📊 Classificação":
    st.header("Tabela de Classificação")
    if not st.session_state.times:
        st.info("Aguardando geração do torneio...")
    else:
        df_ranking = recalcular_tabela()
        st.table(df_ranking)

elif menu == "💰 Ranking":
    st.header("Ranking Financeiro")
    st.write("Em breve: Cálculo automático de rateio de prêmios.")
    # Aqui entraria a mesma lógica de cálculo de lucros que você já tem
