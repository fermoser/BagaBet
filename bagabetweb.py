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
    if not st.session_state.jogos:
        st.info("Nenhum jogo cadastrado.")
    else:
        for i, j in enumerate(st.session_state.jogos):
            # Container com borda para cada jogo, mais compacto
            with st.container(border=True):
                # Cabeçalho do Jogo mais limpo
                c1, c2, c3 = st.columns([1.5, 1, 1.5])
                res_a = j['ga'] if j['ga'] is not None else "-"
                res_b = j['gb'] if j['gb'] is not None else "-"
                
                c1.markdown(f"<p style='text-align:right; font-size:20px; font-weight:bold; margin:0;'>{j['a']}</p>", unsafe_allow_html=True)
                c2.markdown(f"<h2 style='text-align:center; margin:0;'>{res_a} x {res_b}</h2>", unsafe_allow_html=True)
                c3.markdown(f"<p style='text-align:left; font-size:20px; font-weight:bold; margin:0;'>{j['b']}</p>", unsafe_allow_html=True)

                # Área do Admin (Placar) - Só aparece se não estiver finalizado
                if sou_admin and not j['finalizado']:
                    with st.expander("⚙️ Lançar Placar (Admin)"):
                        col_ga, col_gb, col_btn = st.columns([1, 1, 2])
                        ga_val = col_ga.number_input(f"Gols {j['a']}", 0, 99, key=f"ga{i}", step=1)
                        gb_val = col_gb.number_input(f"Gols {j['b']}", 0, 99, key=f"gb{i}", step=1)
                        if col_btn.button("🏆 FINALIZAR", key=f"f{i}", use_container_width=True, type="primary"):
                            st.session_state.jogos[i].update({'ga': ga_val, 'gb': gb_val, 'finalizado': True, 'apostas_abertas': False})
                            salvar_nuvem(); st.rerun()
                elif j['finalizado']:
                    st.markdown(f"<p style='text-align:center; color:gray;'>Partida Encerrada</p>", unsafe_allow_html=True)

                # Painel de Apostas
                ap = j['apostas']
                t_a = sum(x['valor'] for x in ap if x['opcao'] == "A")
                t_e = sum(x['valor'] for x in ap if x['opcao'] == "E")
                t_b = sum(x['valor'] for x in ap if x['opcao'] == "B")
                total_pote = t_a + t_e + t_b

                # RESOLUÇÃO DO PROBLEMA DA DIAGONAL:
                # Criamos as colunas e inserimos as métricas diretamente nelas
                m1, m2, m3, m4 = st.columns(4)
                m1.metric(j['a'], money(t_a))
                m2.metric("Empate", money(t_e))
                m3.metric(j['b'], money(t_b))
                m4.metric("POTE TOTAL", money(total_pote))

                # Histórico e Nova Aposta em colunas menores
                exp = st.expander("📝 Detalhes das Apostas")
                with exp:
                    cx, cy = st.columns([1, 2])
                    with cx:
                        aberto = j.get('apostas_abertas', True)
                        if aberto and not j['finalizado']:
                            st.markdown("**Nova Aposta**")
                            n_ap = st.text_input("Quem?", key=f"nap{i}", label_visibility="collapsed", placeholder="Nome")
                            v_ap = st.number_input("R$", 1.0, 5000.0, 10.0, key=f"vap{i}")
                            o_ap = st.radio("Palpite", [j['a'], "Empate", j['b']], key=f"oap{i}", horizontal=True)
                            if st.button("Confirmar", key=f"bap{i}", use_container_width=True):
                                if n_ap:
                                    trad = "A" if o_ap == j['a'] else "B" if o_ap == j['b'] else "E"
                                    st.session_state.jogos[i]['apostas'].append({"nome": n_ap, "valor": v_ap, "opcao": trad})
                                    salvar_nuvem(); st.rerun()
                            if sou_admin and st.button("🚫 Trancar", key=f"tr{i}", use_container_width=True):
                                st.session_state.jogos[i]['apostas_abertas'] = False
                                salvar_nuvem(); st.rerun()
                        else:
                            st.write("🔒 Apostas trancadas.")
                            if sou_admin and not j['finalizado']:
                                if st.button("🔓 Reabrir", key=f"re{i}"):
                                    st.session_state.jogos[i]['apostas_abertas'] = True
                                    salvar_nuvem(); st.rerun()

                    with cy:
                        if ap:
                            df = pd.DataFrame(ap)
                            df['Palpite'] = df['opcao'].map({"A": j['a'], "B": j['b'], "E": "Empate"})
                            if j['finalizado']:
                                res = "A" if j['ga'] > j['gb'] else "B" if j['gb'] > j['ga'] else "E"
                                v_val = sum(x['valor'] for x in ap if x['opcao'] == res)
                                df['Bruto'] = df.apply(lambda r: (r['valor']/v_val*total_pote) if r['opcao']==res and v_val>0 else 0.0, axis=1)
                                df['Líquido'] = df['Bruto'] - df['valor']
                                df['Bruto'], df['Líquido'], df['Aposta'] = df['Bruto'].apply(money), df['Líquido'].apply(money), df['valor'].apply(money)
                                st.dataframe(df[['nome', 'Palpite', 'Aposta', 'Bruto', 'Líquido']], use_container_width=True, hide_index=True)
                            else:
                                df['Aposta'] = df['valor'].apply(money)
                                st.dataframe(df[['nome', 'Palpite', 'Aposta']], use_container_width=True, hide_index=True)
                        else:
                            st.info("Nenhuma aposta.")

elif menu == "Classificação":
    st.header("📊 Classificação")
    # Lógica de cálculo aqui (igual a anterior)
    st.info("Acesse para ver a tabela.")

elif menu == "Ranking Apostas":
    st.header("💰 Ranking")
    # Lógica de ranking aqui (igual a anterior)

