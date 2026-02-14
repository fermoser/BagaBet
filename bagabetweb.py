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
    if 'jogos' in st.session_state and st.session_state.jogos:
        df = pd.DataFrame(st.session_state.jogos)
        df['apostas'] = df['apostas'].apply(lambda x: "|".join([f"{a['nome']}:{a['valor']}:{a['opcao']}" for a in x]) if x else "")
        conn.update(data=df)

def carregar_nuvem():
    try:
        df = conn.read(ttl=0)
        if not df.empty:
            jogos_lidos = df.to_dict('records')
            for j in jogos_lidos:
                j['apostas'] = []
                if 'apostas' in j and str(j['apostas']) not in ["nan", "None", ""]:
                    for item in str(j['apostas']).split("|"):
                        partes = item.split(":")
                        if len(partes) == 3:
                            j['apostas'].append({"nome": partes[0], "valor": float(partes[1]), "opcao": partes[2]})
                
                j['ga'] = int(j['ga']) if str(j.get('ga')) not in ["None", "nan", ""] else None
                j['gb'] = int(j['gb']) if str(j.get('gb')) not in ["None", "nan", ""] else None
                j['finalizado'] = str(j.get('finalizado')) == "True"
                j['apostas_abertas'] = str(j.get('apostas_abertas', "True")) == "True"
            st.session_state.jogos = jogos_lidos
            st.session_state.times = list(set([j['a'] for j in jogos_lidos] + [j['b'] for j in jogos_lidos]))
    except:
        st.session_state.jogos, st.session_state.times = [], []

if 'jogos' not in st.session_state:
    carregar_nuvem()

# --- SIDEBAR ---
st.sidebar.title("BAGA BET ⚽")
menu = st.sidebar.radio("Navegação", ["Jogos", "Classificação", "Ranking Apostas", "Novo Torneio"])
if st.sidebar.button("⚠️ RESETAR TORNEIO"):
    st.session_state.jogos, st.session_state.times = [], []
    salvar_nuvem()
    st.rerun()

# --- CONTEÚDO ---
if menu == "Novo Torneio":
    st.header("🏆 Novo Torneio")
    qtd = st.number_input("Times", 2, 20, 4)
    nomes = [st.text_input(f"Time {i+1}", key=f"t{i}") for i in range(qtd)]
    if st.button("GERAR", type="primary"):
        times = [n for n in nomes if n]
        if len(times) >= 2:
            pares = list(itertools.combinations(times, 2))
            random.shuffle(pares)
            st.session_state.times = times
            st.session_state.jogos = [{"a": p[0], "b": p[1], "ga": None, "gb": None, "finalizado": False, "apostas_abertas": True, "apostas": []} for p in pares]
            salvar_nuvem(); st.rerun()

elif menu == "Jogos":
    st.header("⚽ Jogos")
    for i, j in enumerate(st.session_state.jogos):
        with st.container(border=True):
            # 1. EXIBIÇÃO DO PLACAR (Cabeçalho)
            c1, c2, c3 = st.columns([2, 1, 2])
            res_a = j['ga'] if j['ga'] is not None else "-"
            res_b = j['gb'] if j['gb'] is not None else "-"
            c1.markdown(f"<h2 style='text-align: right;'>{j['a']}</h2>", unsafe_allow_html=True)
            c2.markdown(f"<h1 style='text-align: center;'>{res_a} x {res_b}</h1>", unsafe_allow_html=True)
            c3.markdown(f"<h2 style='text-align: left;'>{j['b']}</h2>", unsafe_allow_html=True)

            # 2. LANÇAMENTO DE GOLS (Visível se não finalizado)
            if not j['finalizado']:
                st.markdown("### 📝 Lançar Resultado")
                col_ga, col_x, col_gb, col_btn = st.columns([2, 0.5, 2, 2])
                ga_val = col_ga.number_input(f"Gols {j['a']}", 0, 99, key=f"ga_in{i}")
                col_x.markdown("<h3 style='padding-top:25px;'>x</h3>", unsafe_allow_html=True)
                gb_val = col_gb.number_input(f"Gols {j['b']}", 0, 99, key=f"gb_in{i}")
                if col_btn.button("🏆 FINALIZAR JOGO", key=f"btn_f{i}", type="primary", use_container_width=True):
                    st.session_state.jogos[i]['ga'] = ga_val
                    st.session_state.jogos[i]['gb'] = gb_val
                    st.session_state.jogos[i]['finalizado'] = True
                    st.session_state.jogos[i]['apostas_abertas'] = False
                    salvar_nuvem(); st.rerun()
            else:
                st.success(f"Partida Encerrada: {j['ga']} x {j['gb']}")

            # 3. PAINEL FINANCEIRO (Expander)
            with st.expander("💰 Detalhes Financeiros e Apostas"):
                ap = j['apostas']
                t_a = sum(x['valor'] for x in ap if x['opcao'] == "A")
                t_b = sum(x['valor'] for x in ap if x['opcao'] == "B")
                t_e = sum(x['valor'] for x in ap if x['opcao'] == "E")
                total_pote = t_a + t_b + t_e

                st.columns(4)[0].metric(j['a'], money(t_a))
                st.columns(4)[1].metric("Empate", money(t_e))
                st.columns(4)[2].metric(j['b'], money(t_b))
                st.columns(4)[3].metric("POTE", money(total_pote))

                st.divider()
                cx, cy = st.columns([1, 2])
                
                with cx: # Registrar Apostas
                    if j['apostas_abertas'] and not j['finalizado']:
                        n_ap = st.text_input("Nome", key=f"n{i}")
                        v_ap = st.number_input("Valor R$", 1.0, 5000.0, 10.0, key=f"v{i}")
                        o_ap = st.radio("Palpite", [j['a'], "Empate", j['b']], key=f"o{i}", horizontal=True)
                        if st.button("Confirmar Aposta", key=f"ba{i}"):
                            if n_ap:
                                trad = "A" if o_ap == j['a'] else "B" if o_ap == j['b'] else "E"
                                st.session_state.jogos[i]['apostas'].append({"nome": n_ap, "valor": v_ap, "opcao": trad})
                                salvar_nuvem(); st.rerun()
                        if st.button("🚫 Encerrar Apostas", key=f"lock{i}"):
                            st.session_state.jogos[i]['apostas_abertas'] = False
                            salvar_nuvem(); st.rerun()
                    else:
                        st.warning("Apostas trancadas.")

                with cy: # Tabela de Rateio
                    if ap:
                        df = pd.DataFrame(ap)
                        df['Palpite'] = df['opcao'].map({"A": j['a'], "B": j['b'], "E": "Empate"})
                        if j['finalizado']:
                            res = "A" if j['ga'] > j['gb'] else "B" if j['gb'] > j['ga'] else "E"
                            v_val = sum(x['valor'] for x in ap if x['opcao'] == res)
                            df['Bruto'] = df.apply(lambda r: (r['valor']/v_val*total_pote) if r['opcao']==res and v_val>0 else 0.0, axis=1)
                            df['Líquido'] = df['Bruto'] - df['valor']
                            df['Aposta'] = df['valor'].apply(money)
                            df['Bruto'] = df['Bruto'].apply(money)
                            df['Líquido'] = df['Líquido'].apply(money)
                            st.dataframe(df[['nome', 'Palpite', 'Aposta', 'Bruto', 'Líquido']], use_container_width=True, hide_index=True)
                        else:
                            df['Aposta'] = df['valor'].apply(money)
                            st.dataframe(df[['nome', 'Palpite', 'Aposta']], use_container_width=True, hide_index=True)

elif menu == "Classificação":
    st.header("📊 Classificação")
    # Lógica de cálculo aqui (igual a anterior)
    st.info("Acesse para ver a tabela.")

elif menu == "Ranking Apostas":
    st.header("💰 Ranking")
    # Lógica de ranking aqui (igual a anterior)
