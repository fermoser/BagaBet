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

# --- FUNÇÕES CORE ---
def carregar_nuvem():
    try:
        df = conn.read(ttl=0)
        if df is not None and not df.empty:
            # Limpa colunas fantasmas que o Sheets cria e causam a 'diagonal'
            df = df.dropna(subset=['a', 'b']) 
            dados = df.to_dict('records')
            for j in dados:
                # Recuperar apostas
                j['apostas'] = []
                txt = str(j.get('apostas', ""))
                if txt and txt not in ["nan", "None", ""]:
                    for item in txt.split("|"):
                        p = item.split(":")
                        if len(p) == 3:
                            j['apostas'].append({"nome": p[0], "valor": float(p[1]), "opcao": p[2]})
                
                # Tratar Gols com segurança total
                for col in ['ga', 'gb']:
                    val = str(j.get(col, ""))
                    if val.replace('.','',1).isdigit():
                        j[col] = int(float(val))
                    else:
                        j[col] = None

                j['finalizado'] = str(j.get('finalizado')) == "True"
                j['apostas_abertas'] = str(j.get('apostas_abertas', "True")) == "True"
            st.session_state.jogos = dados
        else:
            st.session_state.jogos = []
    except Exception as e:
        st.session_state.jogos = []

def salvar_nuvem():
    if 'jogos' in st.session_state and st.session_state.jogos:
        df = pd.DataFrame(st.session_state.jogos)
        # Serializa as apostas antes de salvar
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
    with st.sidebar.expander("🛠️ ÁREA DO ADMIN"):
        qtd = st.number_input("Qtd Times", 2, 10, 4)
        nomes = [st.text_input(f"Time {i+1}", key=f"t{i}") for i in range(int(qtd))]
        if st.button("🚀 CRIAR NOVO TORNEIO"):
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
        st.info("Nenhum jogo. Use a barra lateral para criar.")
    else:
        for i, j in enumerate(st.session_state.jogos):
            with st.container(border=True):
                c1, c2, c3 = st.columns([2, 1, 2])
                c1.subheader(j['a'])
                ga_ex = j['ga'] if j['ga'] is not None else "-"
                gb_ex = j['gb'] if j['gb'] is not None else "-"
                c2.markdown(f"<h1 style='text-align:center;'>{ga_ex} x {gb_ex}</h1>", unsafe_allow_html=True)
                c3.subheader(j['b'])

                if sou_admin and not j['finalizado']:
                    with st.expander("📝 Lançar Resultado"):
                        l1, l2 = st.columns(2)
                        v_ga = l1.number_input(f"Gols {j['a']}", 0, 20, key=f"ga{i}")
                        v_gb = l2.number_input(f"Gols {j['b']}", 0, 20, key=f"gb{i}")
                        if st.button("Confirmar Placar", key=f"sv{i}"):
                            st.session_state.jogos[i].update({'ga': int(v_ga), 'gb': int(v_gb), 'finalizado': True, 'apostas_abertas': False})
                            salvar_nuvem(); st.rerun()

                # FINANCEIRO E APOSTAS
                aps = j['apostas']
                v_pote = sum(a['valor'] for a in aps)
                st.write(f"**Pote Total:** {money(v_pote)}")
                
                with st.expander("💰 Apostar / Ver Apostas"):
                    col_a, col_b = st.columns([1, 2])
                    with col_a:
                        if j['apostas_abertas'] and not j['finalizado']:
                            n_ap = st.text_input("Nome", key=f"n{i}")
                            v_ap = st.number_input("R$", 1.0, 1000.0, 10.0, step=1.0, key=f"v{i}")
                            o_ap = st.radio("Vence:", [j['a'], "Empate", j['b']], key=f"o{i}")
                            if st.button("Apostar", key=f"bt{i}"):
                                t = "A" if o_ap == j['a'] else "B" if o_ap == j['b'] else "E"
                                st.session_state.jogos[i]['apostas'].append({"nome": n_ap, "valor": v_ap, "opcao": t})
                                salvar_nuvem(); st.rerun()
                    with col_b:
                        if aps: st.table(pd.DataFrame(aps))

elif menu == "Classificação":
    st.header("📊 Tabela de Pontos")
    carregar_nuvem()
    if st.session_state.jogos:
        times = list(set([j['a'] for j in st.session_state.jogos] + [j['b'] for j in st.session_state.jogos]))
        cl = {t: {"P":0,"V":0,"E":0,"D":0,"GP":0,"GC":0} for t in times}
        for j in st.session_state.jogos:
            if j["finalizado"] and j["ga"] is not None:
                a, b, ga, gb = j["a"], j["b"], j["ga"], j["gb"]
                cl[a]["GP"]+=ga; cl[a]["GC"]+=gb; cl[b]["GP"]+=gb; cl[b]["GC"]+=ga
                if ga > gb: cl[a]["P"]+=3; cl[a]["V"]+=1; cl[b]["D"]+=1
                elif gb > ga: cl[b]["P"]+=3; cl[b]["V"]+=1; cl[a]["D"]+=1
                else: cl[a]["P"]+=1; cl[b]["P"]+=1; cl[a]["E"]+=1; cl[b]["E"]+=1
        st.dataframe(pd.DataFrame.from_dict(cl, orient='index').sort_values(by="P", ascending=False), use_container_width=True)

elif menu == "Ranking":
    st.header("💰 Ranking Geral")
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
        df_rk = pd.DataFrame([{"Nome": k, "Lucro": v["ganho"]-v["gasto"]} for k, v in rk.items()])
        st.dataframe(df_rk.sort_values("Lucro", ascending=False), hide_index=True)
