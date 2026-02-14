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
    else:
        df_vazio = pd.DataFrame(columns=['a', 'b', 'ga', 'gb', 'finalizado', 'apostas', 'apostas_abertas'])
        conn.update(data=df_vazio)

def carregar_nuvem():
    try:
        df = conn.read(ttl=0)
        if not df.empty:
            jogos_lidos = df.to_dict('records')
            for j in jogos_lidos:
                j['apostas'] = []
                if str(j.get('apostas', "")) != "nan" and j.get('apostas', ""):
                    for item in str(j['apostas']).split("|"):
                        partes = item.split(":")
                        if len(partes) == 3:
                            j['apostas'].append({"nome": partes[0], "valor": float(partes[1]), "opcao": partes[2]})
                
                j['ga'] = int(j['ga']) if str(j['ga']) not in ["None", "nan", ""] else None
                j['gb'] = int(j['gb']) if str(j['gb']) not in ["None", "nan", ""] else None
                j['finalizado'] = str(j['finalizado']) == "True"
                j['apostas_abertas'] = str(j.get('apostas_abertas', "True")) == "True"
            
            st.session_state.jogos = jogos_lidos
            st.session_state.times = list(set([j['a'] for j in jogos_lidos] + [j['b'] for j in jogos_lidos]))
        else:
            st.session_state.jogos, st.session_state.times = [], []
    except:
        st.session_state.jogos, st.session_state.times = [], []

if 'jogos' not in st.session_state:
    carregar_nuvem()

# --- LÓGICA DE CLASSIFICAÇÃO ---
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

# --- SIDEBAR ---
st.sidebar.title("BAGA BET ⚽")
menu = st.sidebar.radio("Navegação", ["Jogos", "Classificação", "Ranking Apostas", "Novo Torneio"])
st.sidebar.markdown("---")
if st.sidebar.button("⚠️ RESETAR TORNEIO", use_container_width=True):
    st.session_state.jogos, st.session_state.times = [], []
    salvar_nuvem()
    st.rerun()

# --- CONTEÚDO ---
if menu == "Novo Torneio":
    st.header("🏆 Configurar Novo Torneio")
    qtd = st.number_input("Quantidade de Times", 2, 20, 4)
    nomes = []
    c1, c2 = st.columns(2)
    for i in range(qtd):
        with (c1 if i % 2 == 0 else c2):
            nomes.append(st.text_input(f"Time {i+1}", key=f"t{i}"))
    
    if st.button("GERAR CONFRONTOS", type="primary"):
        times = [n for n in nomes if n]
        if len(times) >= 2:
            pares = list(itertools.combinations(times, 2))
            random.shuffle(pares)
            st.session_state.times = times
            st.session_state.jogos = [{"a": p[0], "b": p[1], "ga": None, "gb": None, "finalizado": False, "apostas_abertas": True, "apostas": []} for p in pares]
            salvar_nuvem()
            st.success("Torneio Criado!")
            st.rerun()

elif menu == "Jogos":
    st.header("⚽ Calendário de Jogos")
    if not st.session_state.jogos:
        st.info("Nenhum torneio ativo.")
    else:
        for i, j in enumerate(st.session_state.jogos):
            with st.container(border=True):
                col1, col2, col3 = st.columns([2, 1, 2])
                res_a = j['ga'] if j['ga'] is not None else "-"
                res_b = j['gb'] if j['gb'] is not None else "-"
                col1.markdown(f"<h2 style='text-align: right;'>{j['a']}</h2>", unsafe_allow_html=True)
                col2.markdown(f"<h1 style='text-align: center;'>{res_a} x {res_b}</h1>", unsafe_allow_html=True)
                col3.markdown(f"<h2 style='text-align: left;'>{j['b']}</h2>", unsafe_allow_html=True)
                
                exp = st.expander("💰 Painel de Controle e Apostas")
                ap = j['apostas']
                t_a = sum(x['valor'] for x in ap if x['opcao'] == "A")
                t_b = sum(x['valor'] for x in ap if x['opcao'] == "B")
                t_e = sum(x['valor'] for x in ap if x['opcao'] == "E")
                total_pote = t_a + t_b + t_e

                m1, m2, m3, m4 = exp.columns(4)
                m1.metric(j['a'], money(t_a))
                m2.metric("Empate", money(t_e))
                m3.metric(j['b'], money(t_b))
                m4.metric("POTE", money(total_pote))

                st.divider()
                ca, cb = exp.columns([1, 1.5])

                with ca:
                    if not j['finalizado'] and j['apostas_abertas']:
                        st.subheader("Registrar Aposta")
                        n_ap = st.text_input("Nome", key=f"n{i}")
                        v_ap = st.number_input("Valor R$", 1.0, 5000.0, 10.0, key=f"v{i}")
                        o_ap = st.radio("Palpite", [j['a'], "Empate", j['b']], key=f"o{i}", horizontal=True)
                        if st.button("Confirmar Aposta", key=f"ba{i}", use_container_width=True):
                            if n_ap:
                                trad = "A" if o_ap == j['a'] else "B" if o_ap == j['b'] else "E"
                                st.session_state.jogos[i]['apostas'].append({"nome": n_ap, "valor": v_ap, "opcao": trad})
                                salvar_nuvem(); st.rerun()
                        if st.button("🚫 Encerrar Apostas", key=f"lock_ap{i}", type="secondary"):
                            st.session_state.jogos[i]['apostas_abertas'] = False
                            salvar_nuvem(); st.rerun()
                    elif not j['finalizado'] and not j['apostas_abertas']:
                        st.warning("⚠️ Apostas Encerradas para este jogo.")
                        if st.button("🔓 Reabrir Apostas", key=f"unlock_ap{i}"):
                            st.session_state.jogos[i]['apostas_abertas'] = True
                            salvar_nuvem(); st.rerun()
                    else:
                        st.success("✅ Jogo e Apostas Finalizados.")

                with cb:
                    st.subheader("Histórico e Detalhes")
                    if ap:
                        df_ap = pd.DataFrame(ap)
                        df_ap['Palpite'] = df_ap['opcao'].map({"A": j['a'], "B": j['b'], "E": "Empate"})
                        if j['finalizado']:
                            res_real = "A" if j['ga'] > j['gb'] else "B" if j['gb'] > j['ga'] else "E"
                            venc_val = sum(x['valor'] for x in ap if x['opcao'] == res_real)
                            df_ap['Bruto'] = df_ap.apply(lambda r: (r['valor']/venc_val*total_pote) if r['opcao']==res_real and venc_val>0 else 0.0, axis=1)
                            df_ap['Líquido'] = df_ap['Bruto'] - df_ap['valor']
                            df_ex = df_ap.copy()
                            df_ex['Aposta'] = df_ex['valor'].apply(money)
                            df_ex['Bruto'] = df_ex['Bruto'].apply(money)
                            df_ex['Líquido'] = df_ex['Líquido'].apply(money)
                            st.dataframe(df_ex[['nome', 'Palpite', 'Aposta', 'Bruto', 'Líquido']], use_container_width=True, hide_index=True)
                        else:
                            df_ap['Aposta'] = df_ap['valor'].apply(money)
                            st.dataframe(df_ap[['nome', 'Palpite', 'Aposta']], use_container_width=True, hide_index=True)
                    else: st.info("Sem apostas.")

                st.divider()
                if not j['finalizado']:
                    st.subheader("Encerrar Partida")
                    p1, p2, p3 = st.columns([2,1,2])
                    ga_in = p1.number_input(f"Gols {j['a']}", 0, 50, key=f"ga{i}")
                    gb_in = p3.number_input(f"Gols {j['b']}", 0, 50, key=f"gb{i}")
                    if st.button("🏆 FINALIZAR JOGO (Bloquear)", key=f"fin{i}", type="primary", use_container_width=True):
                        st.session_state.jogos[i]['ga'] = ga_in
                        st.session_state.jogos[i]['gb'] = gb_in
                        st.session_state.jogos[i]['finalizado'] = True
                        st.session_state.jogos[i]['apostas_abertas'] = False
                        salvar_nuvem(); st.rerun()
                else:
                    st.info(f"Resultado Final: {j['ga']} x {j['gb']}")

elif menu == "Classificação":
    st.header("📊 Tabela de Classificação")
    if st.session_state.jogos: st.table(gerar_classificacao())
    else: st.info("Aguardando jogos.")

elif menu == "Ranking Apostas":
    st.header("💰 Ranking Geral")
    ranking = {}
    for j in st.session_state.jogos:
        if not j["finalizado"]: continue
        pool = sum(a["valor"] for a in j["apostas"])
        res = "A" if j["ga"] > j["gb"] else "B" if j["gb"] > j["ga"] else "E"
        venc_val = sum(a["valor"] for a in j["apostas"] if a["opcao"] == res)
        for a in j["apostas"]:
            ranking.setdefault(a["nome"], {"ap": 0, "ga": 0})
            ranking[a["nome"]]["ap"] += a["valor"]; ranking[a["nome"]]["ga"] += (a["valor"]/venc_val*pool) if a["opcao"]==res and venc_val>0 else 0
    if ranking:
        dr = [{"Nome": n, "Apostado": money(d['ap']), "Ganho": money(d['ga']), "Saldo": money(d['ga']-d['ap'])} for n, d in ranking.items()]
        st.table(pd.DataFrame(dr))
