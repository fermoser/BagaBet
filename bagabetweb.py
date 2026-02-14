import streamlit as st
import pandas as pd
import itertools
import random
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="BAGA BET ⚽", layout="wide")
conn = st.connection("gsheets", type=GSheetsConnection)

def money(v):
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# --- FUNÇÕES DE NUVEM ---
def carregar_nuvem():
    try:
        df = conn.read(ttl=0)
        if df is not None and not df.empty:
            # Remove linhas totalmente vazias que bugam a diagonal
            df = df.dropna(subset=['a', 'b'])
            dados = df.to_dict('records')
            jogos_limpos = []
            for j in dados:
                # Recuperar Apostas
                j['apostas'] = []
                txt = str(j.get('apostas', ""))
                if txt and txt not in ["nan", "None", ""]:
                    for item in txt.split("|"):
                        p = item.split(":")
                        if len(p) == 3:
                            j['apostas'].append({"nome": p[0], "valor": float(p[1]), "opcao": p[2]})
                
                # Forçar Gols como Inteiros ou None
                for col in ['ga', 'gb']:
                    val = str(j.get(col, ""))
                    if val.replace('.','',1).strip().isdigit():
                        j[col] = int(float(val))
                    else:
                        j[col] = None

                j['finalizado'] = str(j.get('finalizado')) == "True"
                j['apostas_abertas'] = str(j.get('apostas_abertas', "True")) == "True"
                jogos_limpos.append(j)
            st.session_state.jogos = jogos_limpos
        else:
            st.session_state.jogos = []
    except:
        st.session_state.jogos = []

def salvar_nuvem():
    if 'jogos' in st.session_state and st.session_state.jogos:
        df = pd.DataFrame(st.session_state.jogos)
        df['apostas'] = df['apostas'].apply(lambda x: "|".join([f"{a['nome']}:{a['valor']}:{a['opcao']}" for a in x]) if isinstance(x, list) else "")
        conn.update(data=df)

# --- INICIALIZAÇÃO ---
if 'jogos' not in st.session_state:
    carregar_nuvem()

# --- INTERFACE ---
st.sidebar.title("BAGA BET ⚽")
admin_key = st.sidebar.text_input("Senha Admin", type="password")
sou_admin = (admin_key == "1234")

if st.sidebar.button("🔄 SINCRONIZAR"):
    carregar_nuvem()
    st.rerun()

menu = st.sidebar.radio("Menu", ["Jogos", "Classificação", "Ranking"])

# --- NOVO TORNEIO ---
if sou_admin:
    with st.sidebar.expander("🛠️ CRIAR TORNEIO"):
        qtd = st.number_input("Qtd Times", 2, 10, 4)
        nomes = [st.text_input(f"Time {i+1}", key=f"t{i}") for i in range(int(qtd))]
        if st.button("🚀 GERAR NOVO"):
            ts = [n for n in nomes if n]
            if len(ts) >= 2:
                ps = list(itertools.combinations(ts, 2))
                random.shuffle(ps)
                st.session_state.jogos = [{"a": p[0], "b": p[1], "ga": None, "gb": None, "finalizado": False, "apostas_abertas": True, "apostas": []} for p in ps]
                salvar_nuvem()
                st.rerun()

# --- TELAS ---
if menu == "Jogos":
    st.header("⚽ Partidas")
    if not st.session_state.get('jogos'):
        st.info("Nenhum jogo. Crie o torneio na lateral.")
    else:
        for i, j in enumerate(st.session_state.jogos):
            with st.container(border=True):
                c1, c2, c3 = st.columns([2, 1, 2])
                ga_ex = j['ga'] if j['ga'] is not None else "-"
                gb_ex = j['gb'] if j['gb'] is not None else "-"
                c1.markdown(f"<h3 style='text-align:right;'>{j['a']}</h3>", unsafe_allow_html=True)
                c2.markdown(f"<h1 style='text-align:center; color:red;'>{ga_ex} x {gb_ex}</h1>", unsafe_allow_html=True)
                c3.markdown(f"<h3 style='text-align:left;'>{j['b']}</h3>", unsafe_allow_html=True)

                if sou_admin and not j['finalizado']:
                    with st.expander("📝 LANÇAR PLACAR"):
                        l1, l2, l3 = st.columns(3)
                        v_ga = l1.number_input(f"Gols {j['a']}", 0, 20, key=f"ga{i}")
                        v_gb = l2.number_input(f"Gols {j['b']}", 0, 20, key=f"gb{i}")
                        if l3.button("SALVAR", key=f"sv{i}", use_container_width=True):
                            st.session_state.jogos[i].update({'ga': int(v_ga), 'gb': int(v_gb), 'finalizado': True, 'apostas_abertas': False})
                            salvar_nuvem(); st.rerun()

                # APOSTAS
                with st.expander("💰 APOSTAR"):
                    col_f, col_h = st.columns([1, 2])
                    with col_f:
                        if j['apostas_abertas'] and not j['finalizado']:
                            n_ap = st.text_input("Nome", key=f"n{i}")
                            v_ap = st.number_input("R$", 1.0, 1000.0, 10.0, step=1.0, key=f"v{i}")
                            o_ap = st.radio("Vence:", [j['a'], "Empate", j['b']], key=f"o{i}")
                            if st.button("Apostar", key=f"bt{i}"):
                                t = "A" if o_ap == j['a'] else "B" if o_ap == j['b'] else "E"
                                st.session_state.jogos[i]['apostas'].append({"nome": n_ap, "valor": v_ap, "opcao": t})
                                salvar_nuvem(); st.rerun()
                    with col_h:
                        if j['apostas']: st.dataframe(pd.DataFrame(j['apostas']), hide_index=True)

elif menu == "Classificação":
    st.header("📊 Tabela de Pontos")
    carregar_nuvem() # Garante que está lendo do Sheets
    if st.session_state.get('jogos'):
        # Extrai os times de forma dinâmica
        times_lista = sorted(list(set([j['a'] for j in st.session_state.jogos] + [j['b'] for j in st.session_state.jogos])))
        # Cria o dicionário da tabela
        cl = {t: {"P":0,"V":0,"E":0,"D":0,"GP":0,"GC":0,"SG":0} for t in times_lista}
        
        for j in st.session_state.jogos:
            if j.get("finalizado") == True and j.get("ga") is not None:
                a, b, ga, gb = j["a"], j["b"], int(j["ga"]), int(j["gb"])
                cl[a]["GP"] += ga; cl[a]["GC"] += gb
                cl[b]["GP"] += gb; cl[b]["GC"] += ga
                if ga > gb: 
                    cl[a]["P"] += 3; cl[a]["V"] += 1; cl[b]["D"] += 1
                elif gb > ga: 
                    cl[b]["P"] += 3; cl[b]["V"] += 1; cl[a]["D"] += 1
                else: 
                    cl[a]["P"] += 1; cl[b]["P"] += 1; cl[a]["E"] += 1; cl[b]["E"] += 1
        
        for t in cl: cl[t]["SG"] = cl[t]["GP"] - cl[t]["GC"]
        
        # Converte para DataFrame e exibe
        df_final = pd.DataFrame.from_dict(cl, orient='index').sort_values(by=["P", "V", "SG"], ascending=False)
        st.table(df_final)

elif menu == "Ranking":
    st.header("💰 Ranking de Apostas")
    carregar_nuvem()
    rk = {}
    for j in st.session_state.jogos:
        if j["finalizado"] and j["ga"] is not None:
            res = "A" if j["ga"] > j["gb"] else "B" if j["ga"] < j["gb"] else "E"
            pote = sum(a["valor"] for a in j["apostas"])
            venc = sum(a["valor"] for a in j["apostas"] if a["opcao"] == res)
            for a in j["apostas"]:
                rk.setdefault(a["nome"], {"gasto": 0, "ganho": 0})
                rk[a["nome"]]["gasto"] += a["valor"]
                if a["opcao"] == res and venc > 0:
                    rk[a["nome"]]["ganho"] += (a["valor"]/venc*pote)
    if rk:
        df_rk = pd.DataFrame([{"Nome": k, "Lucro": money(v["ganho"]-v["gasto"]), "s": v["ganho"]-v["gasto"]} for k, v in rk.items()])
        st.dataframe(df_rk.sort_values("s", ascending=False).drop(columns="s"), hide_index=True)
