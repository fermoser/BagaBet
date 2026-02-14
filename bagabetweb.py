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

# --- FUNÇÃO DE CARREGAMENTO (FORÇA BUSCA NA NUVEM) ---
def carregar_dados_nuvem():
    # TTL=0 é o segredo para os seus amigos verem o dado atualizado na hora
    try:
        df = conn.read(ttl=0) 
        if df is not None and not df.empty:
            jogos_lidos = df.to_dict('records')
            jogos_processados = []
            for j in jogos_lidos:
                # Recuperar Apostas
                j['apostas'] = []
                if 'apostas' in j and str(j['apostas']) not in ["nan", "None", ""]:
                    for item in str(j['apostas']).split("|"):
                        partes = item.split(":")
                        if len(partes) == 3:
                            j['apostas'].append({"nome": partes[0], "valor": float(partes[1]), "opcao": partes[2]})
                
                # Garantir que Gols sejam números
                j['ga'] = int(j['ga']) if str(j.get('ga')) not in ["None", "nan", ""] else None
                j['gb'] = int(j['gb']) if str(j.get('gb')) not in ["None", "nan", ""] else None
                j['finalizado'] = str(j.get('finalizado')) == "True"
                j['apostas_abertas'] = str(j.get('apostas_abertas', "True")) == "True"
                jogos_processados.append(j)
            
            st.session_state.jogos = jogos_processados
            st.session_state.times = list(set([j['a'] for j in jogos_processados] + [j['b'] for j in jogos_processados]))
        else:
            st.session_state.jogos = []
    except:
        st.session_state.jogos = []

def salvar_nuvem():
    if 'jogos' in st.session_state and st.session_state.jogos:
        df = pd.DataFrame(st.session_state.jogos)
        df['apostas'] = df['apostas'].apply(lambda x: "|".join([f"{a['nome']}:{a['valor']}:{a['opcao']}" for a in x]) if x else "")
        conn.update(data=df)

# --- CARREGAMENTO INICIAL OBRIGATÓRIO ---
# Isso garante que ao abrir o link, os dados já venham do Google Sheets
carregar_dados_nuvem()

# --- SEGURANÇA ---
st.sidebar.title("BAGA BET ⚽")
admin_key = st.sidebar.text_input("Chave do Admin", type="password")
sou_admin = (admin_key == "1234") 

if st.sidebar.button("🔄 ATUALIZAR TUDO"):
    st.cache_data.clear() # Limpa o cache do navegador
    carregar_dados_nuvem()
    st.rerun()

menu = st.sidebar.radio("Navegação", ["Jogos", "Classificação", "Ranking Apostas", "Novo Torneio"])

if sou_admin and st.sidebar.button("⚠️ RESETAR TORNEIO"):
    st.session_state.jogos, st.session_state.times = [], []
    salvar_nuvem(); st.rerun()

# --- CONTEÚDO ---
if menu == "Novo Torneio":
    if not sou_admin:
        st.error("Acesso apenas para Administrador.")
    else:
        st.header("🏆 Novo Torneio")
        qtd = st.number_input("Qtd Times", 2, 20, 4)
        nomes = [st.text_input(f"Time {i+1}", key=f"t{i}") for i in range(qtd)]
        if st.button("GERAR CONFRONTOS"):
            times = [n for n in nomes if n]
            if len(times) >= 2:
                pares = list(itertools.combinations(times, 2))
                random.shuffle(pares)
                st.session_state.jogos = [{"a": p[0], "b": p[1], "ga": None, "gb": None, "finalizado": False, "apostas_abertas": True, "apostas": []} for p in pares]
                salvar_nuvem(); st.rerun()

elif menu == "Jogos":
    st.header("⚽ Partidas em Andamento")
    if not st.session_state.get('jogos'):
        st.info("Nenhum jogo ativo. Peça ao admin para criar o torneio.")
    else:
        for i, j in enumerate(st.session_state.jogos):
            with st.container(border=True):
                c1, c2, c3 = st.columns([2, 1, 2])
                res_a = j['ga'] if j['ga'] is not None else "-"
                res_b = j['gb'] if j['gb'] is not None else "-"
                c1.markdown(f"<h2 style='text-align:right;'>{j['a']}</h2>", unsafe_allow_html=True)
                c2.markdown(f"<h1 style='text-align:center; color:red;'>{res_a} x {res_b}</h1>", unsafe_allow_html=True)
                c3.markdown(f"<h2 style='text-align:left;'>{j['b']}</h2>", unsafe_allow_html=True)

                if sou_admin and not j['finalizado']:
                    with st.expander("⚙️ LANÇAR PLACAR (ADMIN)"):
                        st.markdown("---")
                        l1, l2, l3 = st.columns([2, 2, 2])
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

                ap = j['apostas']
                t_a, t_e, t_b = sum(x['valor'] for x in ap if x['opcao'] == "A"), sum(x['valor'] for x in ap if x['opcao'] == "E"), sum(x['valor'] for x in ap if x['opcao'] == "B")
                m1, m2, m3, m4 = st.columns(4)
                m1.metric(j['a'], money(t_a)); m2.metric("Empate", money(t_e)); m3.metric(j['b'], money(t_b)); m4.metric("POTE", money(t_a+t_e+t_b))

                with st.expander("💰 APOSTAS"):
                    cx, cy = st.columns([1, 2])
                    with cx:
                        if j['apostas_abertas'] and not j['finalizado']:
                            n_ap = st.text_input("Nome", key=f"n_{i}")
                            v_ap = st.number_input("Valor R$", 1.0, 5000.0, 10.0, step=1.0, key=f"v_{i}")
                            o_ap = st.radio("Palpite", [j['a'], "Empate", j['b']], key=f"o_{i}", horizontal=True)
                            if st.button("Apostar", key=f"b_{i}", use_container_width=True):
                                if n_ap:
                                    trad = "A" if o_ap == j['a'] else "B" if o_ap == j['b'] else "E"
                                    st.session_state.jogos[i]['apostas'].append({"nome": n_ap, "valor": v_ap, "opcao": trad})
                                    salvar_nuvem(); st.rerun()
                    with cy:
                        if ap:
                            df = pd.DataFrame(ap)
                            df['Palpite'] = df['opcao'].map({"A": j['a'], "B": j['b'], "E": "Empate"})
                            if j['finalizado']:
                                res = "A" if j['ga'] > j['gb'] else "B" if j['gb'] > j['ga'] else "E"
                                pot = t_a + t_e + t_b
                                ven = sum(x['valor'] for x in ap if x['opcao'] == res)
                                df['Bruto'] = df.apply(lambda r: (r['valor']/ven*pot) if r['opcao']==res and ven>0 else 0.0, axis=1)
                                df['Líquido'] = df['Bruto'] - df['valor']
                                df['Bruto'], df['Líquido'], df['Aposta'] = df['Bruto'].apply(money), df['Líquido'].apply(money), df['valor'].apply(money)
                                st.dataframe(df[['nome', 'Palpite', 'Aposta', 'Bruto', 'Líquido']], hide_index=True)
                            else:
                                df['Aposta'] = df['valor'].apply(money)
                                st.dataframe(df[['nome', 'Palpite', 'Aposta']], hide_index=True)

elif menu == "Classificação":
    st.header("📊 Tabela de Classificação Atualizada")
    if not st.session_state.get('jogos'):
        st.info("Aguardando início do torneio.")
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
        df_cl = pd.DataFrame.from_dict(cl, orient='index').sort_values(by=["P", "V", "SG"], ascending=False)
        st.dataframe(df_cl, use_container_width=True)

elif menu == "Ranking Apostas":
    st.header("💰 Ranking de Apostadores")
    ranking = {}
    for j in st.session_state.get('jogos', []):
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
        dr = [{"Nome": n, "Investido": money(d['ap']), "Retorno": money(d['ga']), "Saldo": money(d['ga']-d['ap']), "s": d['ga']-d['ap']} for n, d in ranking.items()]
        st.dataframe(pd.DataFrame(dr).sort_values("s", ascending=False).drop(columns=['s']), use_container_width=True, hide_index=True)
    else:
        st.info("O ranking aparecerá após os jogos serem finalizados.")
