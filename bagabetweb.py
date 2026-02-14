import streamlit as st
import pandas as pd
import itertools
import random
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="BAGA BET CLOUD", layout="wide")
conn = st.connection("gsheets", type=GSheetsConnection)

def money(v):
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# --- BANCO DE DADOS (CARREGAMENTO CORRIGIDO) ---
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
                # 1. Recuperar Apostas
                j['apostas'] = []
                if 'apostas' in j and str(j['apostas']) not in ["nan", "None", ""]:
                    for item in str(j['apostas']).split("|"):
                        partes = item.split(":")
                        if len(partes) == 3:
                            j['apostas'].append({"nome": partes[0], "valor": float(partes[1]), "opcao": partes[2]})
                
                # 2. Corrigir Gols (Garantir que sejam números para a classificação)
                j['ga'] = int(j['ga']) if str(j.get('ga')) not in ["None", "nan", ""] else None
                j['gb'] = int(j['gb']) if str(j.get('gb')) not in ["None", "nan", ""] else None
                j['finalizado'] = str(j.get('finalizado')) == "True"
                j['apostas_abertas'] = str(j.get('apostas_abertas', "True")) == "True"
            
            st.session_state.jogos = jogos_lidos
            st.session_state.times = list(set([j['a'] for j in jogos_lidos] + [j['b'] for j in jogos_lidos]))
        else:
            st.session_state.jogos, st.session_state.times = [], []
    except Exception as e:
        st.error(f"Erro ao carregar: {e}")
        st.session_state.jogos = []

if 'jogos' not in st.session_state:
    carregar_nuvem()

# --- SEGURANÇA ---
st.sidebar.title("BAGA BET ⚽")
admin_key = st.sidebar.text_input("Chave do Admin", type="password")
sou_admin = (admin_key == "1234") 

menu = st.sidebar.radio("Navegação", ["Jogos", "Classificação", "Ranking Apostas", "Novo Torneio"])

if sou_admin:
    if st.sidebar.button("⚠️ RESETAR TORNEIO"):
        st.session_state.jogos, st.session_state.times = [], []
        salvar_nuvem(); st.rerun()

# --- CONTEÚDO ---
if menu == "Novo Torneio":
    if not sou_admin:
        st.error("Acesse como Admin.")
    else:
        st.header("🏆 Novo Torneio")
        qtd = st.number_input("Qtd Times", 2, 20, 4)
        nomes = [st.text_input(f"Time {i+1}", key=f"t{i}") for i in range(qtd)]
        if st.button("GERAR CONFRONTOS"):
            times = [n for n in nomes if n]
            if len(times) >= 2:
                pares = list(itertools.combinations(times, 2))
                random.shuffle(pares)
                st.session_state.times = times
                st.session_state.jogos = [{"a": p[0], "b": p[1], "ga": None, "gb": None, "finalizado": False, "apostas_abertas": True, "apostas": []} for p in pares]
                salvar_nuvem(); st.rerun()

elif menu == "Jogos":
    st.header("⚽ Rodadas")
    if not st.session_state.jogos:
        st.info("Nenhum jogo ativo.")
    else:
        for i, j in enumerate(st.session_state.jogos):
            with st.container(border=True):
                # PLACAR PRINCIPAL
                c1, c2, c3 = st.columns([2, 1, 2])
                res_a, res_b = (j['ga'] if j['ga'] is not None else "-"), (j['gb'] if j['gb'] is not None else "-")
                c1.markdown(f"<h2 style='text-align:right;'>{j['a']}</h2>", unsafe_allow_html=True)
                c2.markdown(f"<h1 style='text-align:center; color:red;'>{res_a} x {res_b}</h1>", unsafe_allow_html=True)
                c3.markdown(f"<h2 style='text-align:left;'>{j['b']}</h2>", unsafe_allow_html=True)

                # LANÇAMENTO DE GOLS (ADMIN) - BEM GRANDE
                if sou_admin and not j['finalizado']:
                    with st.expander("⚙️ LANÇAR RESULTADO (ADMIN)", expanded=False):
                        st.write("---")
                        l1, l2, l3 = st.columns([2, 2, 2])
                        # Texto em HTML para ficar grande
                        l1.markdown(f"### GOLS {j['a'].upper()}")
                        ga_in = l1.number_input("", 0, 99, key=f"ga_in_{i}", step=1, label_visibility="collapsed")
                        l2.markdown(f"### GOLS {j['b'].upper()}")
                        gb_in = l2.number_input("", 0, 99, key=f"gb_in_{i}", step=1, label_visibility="collapsed")
                        if l3.button("🏆 SALVAR FINAL", key=f"btn_f_{i}", type="primary", use_container_width=True):
                            st.session_state.jogos[i]['ga'] = ga_in
                            st.session_state.jogos[i]['gb'] = gb_in
                            st.session_state.jogos[i]['finalizado'] = True
                            st.session_state.jogos[i]['apostas_abertas'] = False
                            salvar_nuvem(); st.rerun()

                # FINANCEIRO
                ap = j['apostas']
                t_a, t_e, t_b = sum(x['valor'] for x in ap if x['opcao'] == "A"), sum(x['valor'] for x in ap if x['opcao'] == "E"), sum(x['valor'] for x in ap if x['opcao'] == "B")
                m1, m2, m3, m4 = st.columns(4)
                m1.metric(j['a'], money(t_a)); m2.metric("Empate", money(t_e)); m3.metric(j['b'], money(t_b)); m4.metric("POTE", money(t_a+t_e+t_b))

                # DETALHES
                with st.expander("💰 DETALHES E APOSTAS"):
                    cx, cy = st.columns([1, 2])
                    with cx:
                        if j['apostas_abertas'] and not j['finalizado']:
                            n_ap = st.text_input("Nome", key=f"n_{i}")
                            v_ap = st.number_input("R$", 1.0, 5000.0, 10.0, step=1.0, key=f"v_{i}")
                            o_ap = st.radio("Palpite", [j['a'], "Empate", j['b']], key=f"o_{i}", horizontal=True)
                            if st.button("Apostar", key=f"b_{i}", use_container_width=True):
                                trad = "A" if o_ap == j['a'] else "B" if o_ap == j['b'] else "E"
                                st.session_state.jogos[i]['apostas'].append({"nome": n_ap, "valor": v_ap, "opcao": trad})
                                salvar_nuvem(); st.rerun()
                    with cy:
                        if ap:
                            df = pd.DataFrame(ap)
                            df['Palpite'] = df['opcao'].map({"A": j['a'], "B": j['b'], "E": "Empate"})
                            if j['finalizado']:
                                res = "A" if j['ga'] > j['gb'] else "B" if j['gb'] > j['ga'] else "E"
                                pote = t_a + t_e + t_b
                                venc = sum(x['valor'] for x in ap if x['opcao'] == res)
                                df['Bruto'] = df.apply(lambda r: (r['valor']/venc*pote) if r['opcao']==res and venc>0 else 0.0, axis=1)
                                df['Líquido'] = df['Bruto'] - df['valor']
                                df['Bruto'], df['Líquido'], df['Aposta'] = df['Bruto'].apply(money), df['Líquido'].apply(money), df['valor'].apply(money)
                                st.dataframe(df[['nome', 'Palpite', 'Aposta', 'Bruto', 'Líquido']], hide_index=True)
                            else:
                                df['Aposta'] = df['valor'].apply(money)
                                st.dataframe(df[['nome', 'Palpite', 'Aposta']], hide_index=True)

elif menu == "Classificação":
    st.header("📊 Tabela de Classificação")
    if not st.session_state.jogos:
        st.info("Sem dados.")
    else:
        cl = {t: {"P":0,"V":0,"E":0,"D":0,"GP":0,"GC":0,"SG":0} for t in st.session_state.times}
        for j in st.session_state.jogos:
            if not j["finalizado"] or j["ga"] is None: continue
            a, b, ga, gb = j["a"], j["b"], int(j["ga"]), int(j["gb"])
            cl[a]["GP"]+=ga; cl[a]["GC"]+=gb; cl[b]["GP"]+=gb; cl[b]["GC"]+=ga
            if ga > gb: cl[a]["P"]+=3; cl[a]["V"]+=1; cl[b]["D"]+=1
            elif gb > ga: cl[b]["P"]+=3; cl[b]["V"]+=1; cl[a]["D"]+=1
            else: cl[a]["P"]+=1; cl[b]["P"]+=1; cl[a]["E"]+=1; cl[b]["E"]+=1
        for t in cl: cl[t]["SG"] = cl[t]["GP"] - cl[t]["GC"]
        st.table(pd.DataFrame.from_dict(cl, orient='index').sort_values(by=["P", "V", "SG"], ascending=False))

elif menu == "Ranking Apostas":
    st.header("💰 Ranking Geral")
    ranking = {}
    for j in st.session_state.jogos:
        if not j["finalizado"] or j["ga"] is None: continue
        res = "A" if j["ga"] > j["gb"] else "B" if j["gb"] > j["ga"] else "E"
        pote = sum(a["valor"] for a in j["apostas"])
        venc = sum(a["valor"] for a in j["apostas"] if a["opcao"] == res)
        for a in j["apostas"]:
            ranking.setdefault(a["nome"], {"ap": 0, "ga": 0})
            ranking[a["nome"]]["ap"] += a["valor"]
            if a["opcao"] == res and venc > 0:
                ranking[a["nome"]]["ga"] += (a["valor"]/venc*pote)
    if ranking:
        dr = [{"Nome": n, "Total Apostado": money(d['ap']), "Total Retorno": money(d['ga']), "Saldo": money(d['ga']-d['ap'])} for n, d in ranking.items()]
        st.dataframe(pd.DataFrame(dr).sort_values("Nome"), use_container_width=True, hide_index=True)
