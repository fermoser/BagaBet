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

# --- FUNÇÃO DE CARREGAMENTO (FORÇA ATUALIZAÇÃO) ---
def carregar_dados():
    try:
        # TTL=0 garante que ele não use "memória antiga" e pegue sempre o que está no Sheets
        df = conn.read(ttl=0)
        if not df.empty:
            jogos_lidos = df.to_dict('records')
            for j in jogos_lidos:
                # Recuperar Apostas
                j['apostas'] = []
                if 'apostas' in j and str(j['apostas']) not in ["nan", "None", ""]:
                    for item in str(j['apostas']).split("|"):
                        partes = item.split(":")
                        if len(partes) == 3:
                            j['apostas'].append({"nome": partes[0], "valor": float(partes[1]), "opcao": partes[2]})
                
                # Garantir que Gols sejam números ou None
                j['ga'] = int(j['ga']) if str(j.get('ga')) not in ["None", "nan", ""] else None
                j['gb'] = int(j['gb']) if str(j.get('gb')) not in ["None", "nan", ""] else None
                j['finalizado'] = str(j.get('finalizado')) == "True"
                j['apostas_abertas'] = str(j.get('apostas_abertas', "True")) == "True"
            
            st.session_state.jogos = jogos_lidos
            st.session_state.times = list(set([j['a'] for j in jogos_lidos] + [j['b'] for j in jogos_lidos]))
        else:
            st.session_state.jogos = []
    except:
        st.session_state.jogos = []

def salvar_nuvem():
    if 'jogos' in st.session_state and st.session_state.jogos:
        df = pd.DataFrame(st.session_state.jogos)
        df['apostas'] = df['apostas'].apply(lambda x: "|".join([f"{a['nome']}:{a['valor']}:{a['opcao']}" for a in x]) if x else "")
        conn.update(data=df)

# Forçar carregamento inicial
if 'jogos' not in st.session_state:
    carregar_dados()

# --- SEGURANÇA E NAVEGAÇÃO ---
st.sidebar.title("BAGA BET ⚽")
admin_key = st.sidebar.text_input("Chave do Admin", type="password")
sou_admin = (admin_key == "1234") 

# Botão de atualizar manual na barra lateral para os usuários
if st.sidebar.button("🔄 ATUALIZAR DADOS"):
    carregar_dados()
    st.rerun()

menu = st.sidebar.radio("Navegação", ["Jogos", "Classificação", "Ranking Apostas", "Novo Torneio"])

# --- CONTEÚDO ---
if menu == "Novo Torneio":
    if not sou_admin:
        st.error("Acesso restrito ao Administrador.")
    else:
        st.header("🏆 Novo Torneio")
        qtd = st.number_input("Qtd Times", 2, 20, 4)
        nomes = [st.text_input(f"Time {i+1}", key=f"t{i}") for i in range(qtd)]
        if st.button("GERAR CAMPEONATO"):
            times = [n for n in nomes if n]
            if len(times) >= 2:
                pares = list(itertools.combinations(times, 2))
                random.shuffle(pares)
                st.session_state.times = times
                st.session_state.jogos = [{"a": p[0], "b": p[1], "ga": None, "gb": None, "finalizado": False, "apostas_abertas": True, "apostas": []} for p in pares]
                salvar_nuvem(); st.rerun()

elif menu == "Jogos":
    st.header("⚽ Partidas")
    carregar_dados() # Atualiza ao entrar na aba
    if not st.session_state.jogos:
        st.info("Nenhum jogo ativo.")
    else:
        for i, j in enumerate(st.session_state.jogos):
            with st.container(border=True):
                # EXIBIÇÃO DO PLACAR
                c1, c2, c3 = st.columns([2, 1, 2])
                res_a = j['ga'] if j['ga'] is not None else "-"
                res_b = j['gb'] if j['gb'] is not None else "-"
                c1.markdown(f"<h2 style='text-align:right;'>{j['a']}</h2>", unsafe_allow_html=True)
                c2.markdown(f"<h1 style='text-align:center; color:#FF4B4B;'>{res_a} x {res_b}</h1>", unsafe_allow_html=True)
                c3.markdown(f"<h2 style='text-align:left;'>{j['b']}</h2>", unsafe_allow_html=True)

                # PAINEL DO ADMIN (GOLS GRANDES)
                if sou_admin and not j['finalizado']:
                    with st.expander("⚙️ LANÇAR RESULTADO (ADMIN)", expanded=False):
                        st.write("---")
                        l1, l2, l3 = st.columns([2, 2, 2])
                        l1.markdown(f"<h3 style='margin-bottom:-20px;'>GOLS {j['a'].upper()}</h3>", unsafe_allow_html=True)
                        ga_in = l1.number_input("", 0, 99, key=f"ga_in_{i}", step=1)
                        l2.markdown(f"<h3 style='margin-bottom:-20px;'>GOLS {j['b'].upper()}</h3>", unsafe_allow_html=True)
                        gb_in = l2.number_input("", 0, 99, key=f"gb_in_{i}", step=1)
                        if l3.button("🏆 FINALIZAR", key=f"btn_f_{i}", type="primary", use_container_width=True):
                            st.session_state.jogos[i]['ga'] = ga_in
                            st.session_state.jogos[i]['gb'] = gb_in
                            st.session_state.jogos[i]['finalizado'] = True
                            st.session_state.jogos[i]['apostas_abertas'] = False
                            salvar_nuvem(); st.rerun()

                # FINANCEIRO
                ap = j['apostas']
                t_a = sum(x['valor'] for x in ap if x['opcao'] == "A")
                t_e = sum(x['valor'] for x in ap if x['opcao'] == "E")
                t_b = sum(x['valor'] for x in ap if x['opcao'] == "B")
                m1, m2, m3, m4 = st.columns(4)
                m1.metric(j['a'], money(t_a))
                m2.metric("Empate", money(t_e))
                m3.metric(j['b'], money(t_b))
                m4.metric("POTE TOTAL", money(t_a+t_e+t_b))

                # APOSTAS
                with st.expander("💰 APOSTAS"):
                    cx, cy = st.columns([1, 2])
                    with cx:
                        if j['apostas_abertas'] and not j['finalizado']:
                            n_ap = st.text_input("Nome", key=f"n_{i}")
                            v_ap = st.number_input("Valor R$", 1.0, 5000.0, 10.0, step=1.0, key=f"v_{i}")
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
                                df['Aposta'], df['Bruto'], df['Líquido'] = df['valor'].apply(money), df['Bruto'].apply(money), df['Líquido'].apply(money)
                                st.dataframe(df[['nome', 'Palpite', 'Aposta', 'Bruto', 'Líquido']], hide_index=True)
                            else:
                                df['Aposta'] = df['valor'].apply(money)
                                st.dataframe(df[['nome', 'Palpite', 'Aposta']], hide_index=True)

elif menu == "Classificação":
    st.header("📊 Tabela do Campeonato")
    carregar_dados() # Puxa dados novos da nuvem antes de calcular
    if not st.session_state.jogos:
        st.info("Nenhum dado disponível.")
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
    st.header("💰 Ranking Geral de Lucro")
    carregar_dados() # Puxa dados novos da nuvem
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
        dr = [{"Nome": n, "Investido": money(d['ap']), "Retorno": money(d['ga']), "Saldo": money(d['ga']-d['ap']), "lucro_num": d['ga']-d['ap']} for n, d in ranking.items()]
        st.dataframe(pd.DataFrame(dr).sort_values("lucro_num", ascending=False).drop(columns=["lucro_num"]), use_container_width=True, hide_index=True)
    else:
        st.info("O ranking será gerado após o encerramento dos jogos.")
