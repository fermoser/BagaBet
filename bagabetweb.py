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

# --- FUNÇÕES DE LIMPEZA E CARREGAMENTO ---
def carregar_nuvem():
    try:
        df = conn.read(ttl=0)
        if df is not None and not df.empty:
            dados = df.to_dict('records')
            jogos_processados = []
            todos_os_times = set()
            
            for j in dados:
                # 1. Extrair nomes dos times para garantir que a tabela funcione
                todos_os_times.add(str(j['a']))
                todos_os_times.add(str(j['b']))
                
                # 2. Recuperar apostas
                j['apostas'] = []
                txt_ap = str(j.get('apostas', ""))
                if txt_ap and txt_ap not in ["nan", "None", ""]:
                    for item in txt_ap.split("|"):
                        p = item.split(":")
                        if len(p) == 3:
                            j['apostas'].append({"nome": p[0], "valor": float(p[1]), "opcao": p[2]})
                
                # 3. Forçar conversão de Gols para Inteiro ou None
                try:
                    val_a = str(j.get('ga', ""))
                    j['ga'] = int(float(val_a)) if val_a not in ["None", "nan", ""] else None
                    val_b = str(j.get('gb', ""))
                    j['gb'] = int(float(val_b)) if val_b not in ["None", "nan", ""] else None
                except:
                    j['ga'] = None
                    j['gb'] = None

                j['finalizado'] = str(j.get('finalizado')) == "True"
                j['apostas_abertas'] = str(j.get('apostas_abertas', "True")) == "True"
                jogos_processados.append(j)
            
            st.session_state.jogos = jogos_processados
            st.session_state.times = list(todos_os_times)
        else:
            st.session_state.jogos = []
            st.session_state.times = []
    except Exception as e:
        st.error(f"Erro ao sincronizar: {e}")

def salvar_nuvem():
    if 'jogos' in st.session_state:
        df = pd.DataFrame(st.session_state.jogos)
        df['apostas'] = df['apostas'].apply(lambda x: "|".join([f"{a['nome']}:{a['valor']}:{a['opcao']}" for a in x]) if isinstance(x, list) else "")
        conn.update(data=df)

# --- INICIALIZAÇÃO ---
if 'jogos' not in st.session_state:
    carregar_nuvem()

# --- SIDEBAR ---
st.sidebar.title("BAGA BET ⚽")
admin_key = st.sidebar.text_input("Chave Admin", type="password")
sou_admin = (admin_key == "1234")

if st.sidebar.button("🔄 FORÇAR ATUALIZAÇÃO"):
    carregar_nuvem()
    st.rerun()

menu = st.sidebar.radio("Navegação", ["Jogos", "Classificação", "Ranking Apostas", "Novo Torneio"])

# --- NOVO TORNEIO ---
if menu == "Novo Torneio":
    if not sou_admin:
        st.error("Acesso restrito.")
    else:
        st.header("🏆 Novo Torneio")
        qtd = st.number_input("Qtd Times", 2, 20, 4)
        nomes = [st.text_input(f"Time {i+1}", key=f"t{i}") for i in range(qtd)]
        if st.button("LIMPAR TUDO E CRIAR NOVO"):
            ts = [n for n in nomes if n]
            if len(ts) >= 2:
                ps = list(itertools.combinations(ts, 2))
                random.shuffle(ps)
                st.session_state.jogos = [{"a": p[0], "b": p[1], "ga": None, "gb": None, "finalizado": False, "apostas_abertas": True, "apostas": []} for p in ps]
                st.session_state.times = ts
                salvar_nuvem()
                st.success("Torneio Criado! Aguarde a nuvem...")
                st.rerun()

# --- JOGOS ---
elif menu == "Jogos":
    st.header("⚽ Partidas")
    if not st.session_state.get('jogos'):
        st.info("Crie um torneio primeiro.")
    else:
        for i, j in enumerate(st.session_state.jogos):
            with st.container(border=True):
                c1, c2, c3 = st.columns([2, 1, 2])
                ga_v, gb_v = (j['ga'] if j['ga'] is not None else "-"), (j['gb'] if j['gb'] is not None else "-")
                c1.markdown(f"<h2 style='text-align:right;'>{j['a']}</h2>", unsafe_allow_html=True)
                c2.markdown(f"<h1 style='text-align:center; color:red;'>{ga_v} x {gb_v}</h1>", unsafe_allow_html=True)
                c3.markdown(f"<h2 style='text-align:left;'>{j['b']}</h2>", unsafe_allow_html=True)

                if sou_admin and not j['finalizado']:
                    with st.expander("⚙️ LANÇAR GOLS"):
                        l1, l2, l3 = st.columns([2, 2, 2])
                        v_ga = l1.number_input(f"Gols {j['a']}", 0, 99, key=f"vga{i}")
                        v_gb = l2.number_input(f"Gols {j['b']}", 0, 99, key=f"vgb{i}")
                        if l3.button("SALVAR", key=f"sv{i}", type="primary"):
                            st.session_state.jogos[i].update({'ga': int(v_ga), 'gb': int(v_gb), 'finalizado': True, 'apostas_abertas': False})
                            salvar_nuvem()
                            st.rerun()

                # FINANCEIRO
                aps = j['apostas']
                va = sum(x['valor'] for x in aps if x['opcao'] == "A")
                ve = sum(x['valor'] for x in aps if x['opcao'] == "E")
                vb = sum(x['valor'] for x in aps if x['opcao'] == "B")
                st.columns(4)[0].metric(j['a'], money(va))
                st.columns(4)[1].metric("Empate", money(ve))
                st.columns(4)[2].metric(j['b'], money(vb))
                st.columns(4)[3].metric("POTE", money(va+ve+vb))

                with st.expander("💰 APOSTAR"):
                    col_a, col_b = st.columns([1, 2])
                    with col_a:
                        if j['apostas_abertas'] and not j['finalizado']:
                            n_ap = st.text_input("Nome", key=f"n{i}")
                            v_ap = st.number_input("R$", 1.0, 5000.0, 10.0, step=1.0, key=f"v{i}")
                            o_ap = st.radio("Vencerá:", [j['a'], "Empate", j['b']], key=f"o{i}")
                            if st.button("Confirmar", key=f"bt{i}"):
                                t = "A" if o_ap == j['a'] else "B" if o_ap == j['b'] else "E"
                                st.session_state.jogos[i]['apostas'].append({"nome": n_ap, "valor": v_ap, "opcao": t})
                                salvar_nuvem()
                                st.rerun()
                    with col_b:
                        if aps: st.dataframe(pd.DataFrame(aps), hide_index=True)

# --- CLASSIFICAÇÃO ---
elif menu == "Classificação":
    st.header("📊 Tabela")
    carregar_nuvem()
    if not st.session_state.get('jogos') or not st.session_state.get('times'):
        st.info("Nenhum dado encontrado.")
    else:
        cl = {t: {"P":0,"V":0,"E":0,"D":0,"GP":0,"GC":0,"SG":0} for t in st.session_state.times}
        for j in st.session_state.jogos:
            if not j["finalizado"] or j["ga"] is None: continue
            a, b, ga, gb = str(j["a"]), str(j["b"]), int(j["ga"]), int(j["gb"])
            cl[a]["GP"]+=ga; cl[a]["GC"]+=gb; cl[b]["GP"]+=gb; cl[b]["GC"]+=ga
            if ga > gb: cl[a]["P"]+=3; cl[a]["V"]+=1; cl[b]["D"]+=1
            elif gb > ga: cl[b]["P"]+=3; cl[b]["V"]+=1; cl[a]["D"]+=1
            else: cl[a]["P"]+=1; cl[b]["P"]+=1; cl[a]["E"]+=1; cl[b]["E"]+=1
        for t in cl: cl[t]["SG"] = cl[t]["GP"] - cl[t]["GC"]
        st.dataframe(pd.DataFrame.from_dict(cl, orient='index').sort_values(by=["P", "V", "SG"], ascending=False), use_container_width=True)

# --- RANKING ---
elif menu == "Ranking Apostas":
    st.header("💰 Ranking de Lucro")
    carregar_nuvem()
    rk = {}
    for j in st.session_state.get('jogos', []):
        if not j["finalizado"] or j["ga"] is None: continue
        res = "A" if j["ga"] > j["gb"] else "B" if j["gb"] > j["ga"] else "E"
        pote = sum(a["valor"] for a in j["apostas"])
        venc = sum(a["valor"] for a in j["apostas"] if a["opcao"] == res)
        for a in j["apostas"]:
            rk.setdefault(a["nome"], {"in": 0, "re": 0})
            rk[a["nome"]]["in"] += a["valor"]
            if a["opcao"] == res and venc > 0: rk[a["nome"]]["re"] += (a["valor"]/venc*pote)
    if rk:
        res_rk = [{"Nome": n, "Investido": money(d['in']), "Retorno": money(d['re']), "Saldo": money(d['re']-d['in']), "s": d['re']-d['in']} for n, d in rk.items()]
        st.dataframe(pd.DataFrame(res_rk).sort_values("s", ascending=False).drop(columns="s"), use_container_width=True, hide_index=True)
