import streamlit as st
import pandas as pd
import itertools
import random
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAÇÃO E CONEXÃO ---
st.set_page_config(page_title="BAGA BET CLOUD", layout="wide")
conn = st.connection("gsheets", type=GSheetsConnection)

def money(v):
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# --- FUNÇÕES DE BANCO DE DADOS ---
def salvar_nuvem():
    if 'jogos' in st.session_state:
        df = pd.DataFrame(st.session_state.jogos)
        # Transformamos a lista de apostas em texto para salvar no Sheets
        df['apostas'] = df['apostas'].apply(lambda x: "|".join([f"{a['nome']}:{a['valor']}:{a['opcao']}" for a in x]))
        conn.update(data=df)

def carregar_nuvem():
    try:
        df = conn.read(ttl=0)
        if not df.empty:
            jogos_lidos = df.to_dict('records')
            for j in jogos_lidos:
                # Reconvertemos o texto de apostas em lista de dicionários
                if str(j['apostas']) != "nan" and j['apostas']:
                    lista = []
                    for item in str(j['apostas']).split("|"):
                        partes = item.split(":")
                        if len(partes) == 3:
                            lista.append({"nome": partes[0], "valor": float(partes[1]), "opcao": partes[2]})
                    j['apostas'] = lista
                else:
                    j['apostas'] = []
                # Ajuste de tipos
                j['ga'] = int(j['ga']) if str(j['ga']) != "None" and str(j['ga']) != "nan" else None
                j['gb'] = int(j['gb']) if str(j['gb']) != "None" and str(j['gb']) != "nan" else None
                j['finalizado'] = str(j['finalizado']) == "True"
            st.session_state.jogos = jogos_lidos
            # Extrai times únicos
            st.session_state.times = list(set([j['a'] for j in jogos_lidos] + [j['b'] for j in jogos_lidos]))
    except:
        st.session_state.jogos = []
        st.session_state.times = []

# --- LÓGICA DO TORNEIO ---
if 'jogos' not in st.session_state:
    carregar_nuvem()

def gerar_classificacao():
    cl = {t: {"P":0,"V":0,"E":0,"D":0,"GP":0,"GC":0,"SG":0} for t in st.session_state.times}
    for j in st.session_state.jogos:
        if not j["finalizado"]: continue
        a, b, ga, gb = j["a"], j["b"], j["ga"], j["gb"]
        cl[a]["GP"]+=ga; cl[a]["GC"]+=gb
        cl[b]["GP"]+=gb; cl[b]["GC"]+=ga
        if ga > gb:
            cl[a]["P"]+=3; cl[a]["V"]+=1; cl[b]["D"]+=1
        elif gb > ga:
            cl[b]["P"]+=3; cl[b]["V"]+=1; cl[a]["D"]+=1
        else:
            cl[a]["P"]+=1; cl[b]["P"]+=1; cl[a]["E"]+=1; cl[b]["E"]+=1
    for t in cl: cl[t]["SG"] = cl[t]["GP"] - cl[t]["GC"]
    return pd.DataFrame.from_dict(cl, orient='index').sort_values(by=["P", "V", "SG"], ascending=False)

# --- INTERFACE ---
st.sidebar.title("BAGA BET ⚽")
menu = st.sidebar.radio("Navegação", ["Jogos", "Classificação", "Ranking Apostas", "Novo Torneio"])

if menu == "Novo Torneio":
    st.header("🏆 Configurar Novo Torneio")
    qtd = st.number_input("Quantidade de Times", 2, 20, 4)
    nomes = []
    for i in range(qtd):
        nomes.append(st.text_input(f"Time {i+1}", key=f"t{i}"))
    
    if st.button("GERAR CONFRONTOS (Todos contra Todos)"):
        times = [n for n in nomes if n]
        if len(times) >= 2:
            pares = list(itertools.combinations(times, 2))
            random.shuffle(pares)
            st.session_state.times = times
            st.session_state.jogos = [{"a": p[0], "b": p[1], "ga": None, "gb": None, "finalizado": False, "apostas": []} for p in pares]
            salvar_nuvem()
            st.success("Torneio Criado!")
            st.rerun()

elif menu == "Jogos":
    # --- SEÇÃO DE APOSTAS E FINANCEIRO ---
            exp = st.expander("💰 Painel de Apostas e Resultados")
            
            # Cálculos Financeiros em Tempo Real
            apostas_jogo = j['apostas']
            total_a = sum(a['valor'] for a in apostas_jogo if a['opcao'] == "A")
            total_b = sum(a['valor'] for a in apostas_jogo if a['opcao'] == "B")
            total_e = sum(a['valor'] for a in apostas_jogo if a['opcao'] == "E")
            total_geral = total_a + total_b + total_e

            # 1. LINHA DE MÉTRICAS (Resumo do Dinheiro)
            m1, m2, m3, m4 = exp.columns(4)
            m1.metric(f"No {j['a']}", money(total_a))
            m2.metric("No Empate", money(total_e))
            m3.metric(f"No {j['b']}", money(total_b))
            m4.metric("TOTAL NO POTE", money(total_geral), delta_color="normal")

            st.divider()

            c1, c2 = exp.columns([1, 1.5]) # Coluna menor para input, maior para histórico
            
            # 2. COLUNA DA ESQUERDA: REGISTRAR NOVA APOSTA
            with c1:
                st.subheader("Nova Aposta")
                nome_ap = st.text_input("Nome do Apostador", key=f"n_ap{i}")
                valor_ap = st.number_input("Valor R$", 1.0, 5000.0, 10.0, key=f"v_ap{i}")
                opc_ap = st.radio("Palpite", [j['a'], "Empate", j['b']], key=f"o_ap{i}", horizontal=True)
                
                if st.button("Confirmar Aposta", key=f"btn_ap{i}", use_container_width=True):
                    if nome_ap:
                        trad = "A" if opc_ap == j['a'] else "B" if opc_ap == j['b'] else "E"
                        st.session_state.jogos[i]['apostas'].append({
                            "nome": nome_ap, 
                            "valor": valor_ap, 
                            "opcao": trad
                        })
                        salvar_nuvem()
                        st.success("Aposta registrada!")
                        st.rerun()
                    else:
                        st.error("Digite o nome do apostador!")

            # 3. COLUNA DA DIREITA: HISTÓRICO DE APOSTAS
            with c2:
                st.subheader("Histórico de Apostas")
                if apostas_jogo:
                    # Criar DataFrame para mostrar bonitinho
                    df_ap = pd.DataFrame(apostas_jogo)
                    # Traduzir as siglas A, B, E para os nomes dos times para o usuário ver
                    df_ap['Palpite'] = df_ap['opcao'].map({"A": j['a'], "B": j['b'], "E": "Empate"})
                    df_ap['Valor'] = df_ap['valor'].apply(money)
                    st.dataframe(df_ap[['nome', 'Palpite', 'Valor']], use_container_width=True, hide_index=True)
                else:
                    st.info("Nenhuma aposta para este jogo ainda.")

            st.divider()
            
            # 4. LANÇAR PLACAR (Fica no rodapé do expander)
            st.subheader("Finalizar Jogo")
            p1, p2, p3 = st.columns([1, 1, 1])
            ga_input = p1.number_input(f"Gols {j['a']}", 0, 50, int(j['ga'] or 0), key=f"ga_in{i}")
            p2.markdown("<h3 style='text-align: center;'>X</h3>", unsafe_allow_html=True)
            gb_input = p3.number_input(f"Gols {j['b']}", 0, 50, int(j['gb'] or 0), key=f"gb_in{i}")
            
            if st.button("SALVAR PLACAR FINAL", key=f"btn_res{i}", use_container_width=True, type="primary"):
                st.session_state.jogos[i]['ga'] = ga_input
                st.session_state.jogos[i]['gb'] = gb_input
                st.session_state.jogos[i]['finalizado'] = True
                salvar_nuvem()
                st.rerun()
elif menu == "Classificação":
    st.header("📊 Tabela de Classificação")
    if st.session_state.jogos:
        df_cl = gerar_classificacao()
        st.table(df_cl)
    else:
        st.info("Nenhum jogo finalizado.")

elif menu == "Ranking Apostas":
    st.header("💰 Ranking de Apostadores")
    ranking = {}
    for j in st.session_state.jogos:
        if not j["finalizado"]: continue
        pool = sum(a["valor"] for a in j["apostas"])
        res = "A" if j["ga"] > j["gb"] else "B" if j["gb"] > j["ga"] else "E"
        venc_val = sum(a["valor"] for a in j["apostas"] if a["opcao"] == res)
        for a in j["apostas"]:
            ranking.setdefault(a["nome"], {"ap": 0, "ga": 0})
            ranking[a["nome"]]["ap"] += a["valor"]
            if a["opcao"] == res and venc_val > 0:
                ranking[a["nome"]]["ga"] += (a["valor"] / venc_val * pool)
    
    if ranking:
        dados_r = []
        for n, d in ranking.items():
            dados_r.append({"Nome": n, "Apostado": money(d['ap']), "Ganho": money(d['ga']), "Saldo": money(d['ga']-d['ap'])})
        st.table(pd.DataFrame(dados_r))
    else:
        st.info("Aguardando finalização de jogos com apostas.")

