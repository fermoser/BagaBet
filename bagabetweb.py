import streamlit as st
import pandas as pd
import itertools
import random
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="BAGA BET ⚽", layout="wide")
# Criamos a conexão
conn = st.connection("gsheets", type=GSheetsConnection)

def money(v):
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# --- FUNÇÃO DE CARREGAMENTO (FORÇA A LEITURA REAL) ---
def carregar_nuvem():
    # st.cache_data.clear() <- Isso limpa a memória do navegador
    try:
        # ttl=0 é OBRIGATÓRIO para não ler dado velho
        df = conn.read(ttl=0)
        if df is not None and not df.empty:
            df = df.dropna(subset=['a', 'b'])
            dados = df.to_dict('records')
            jogos_certos = []
            for j in dados:
                # Recuperar Apostas
                j['apostas'] = []
                txt = str(j.get('apostas', ""))
                if txt and txt not in ["nan", "None", ""]:
                    for item in txt.split("|"):
                        p = item.split(":")
                        if len(p) == 3:
                            j['apostas'].append({"nome": p[0], "valor": float(p[1]), "opcao": p[2]})
                
                # Tratar Gols (Forçar número)
                for col in ['ga', 'gb']:
                    val = str(j.get(col, ""))
                    if val.replace('.','',1).strip().isdigit():
                        j[col] = int(float(val))
                    else:
                        j[col] = None

                j['finalizado'] = str(j.get('finalizado')) == "True"
                j['apostas_abertas'] = str(j.get('apostas_abertas', "True")) == "True"
                jogos_certos.append(j)
            
            # Guardamos na memória de sessão
            st.session_state.jogos = jogos_certos
            return jogos_certos
    except:
        return []

def salvar_nuvem():
    if 'jogos' in st.session_state:
        df_save = pd.DataFrame(st.session_state.jogos)
        df_save['apostas'] = df_save['apostas'].apply(lambda x: "|".join([f"{a['nome']}:{a['valor']}:{a['opcao']}" for a in x]) if isinstance(x, list) else "")
        conn.update(data=df_save)
        # Limpamos o cache após salvar para a próxima leitura ser limpa
        st.cache_data.clear()

# --- INTERFACE ---
st.sidebar.title("BAGA BET ⚽")
admin_key = st.sidebar.text_input("Senha Admin", type="password")
sou_admin = (admin_key == "1234")

# Botão de Sincronização que REALMENTE limpa tudo
if st.sidebar.button("🔄 ATUALIZAR AGORA"):
    st.cache_data.clear()
    carregar_nuvem()
    st.rerun()

menu = st.sidebar.radio("Menu", ["Jogos", "Classificação", "Ranking"])

# --- INICIALIZAÇÃO OBRIGATÓRIA ---
# Se mudar de aba, ele recarrega
jogos_atuais = carregar_nuvem()

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
    if not jogos_atuais:
        st.info("Nenhum jogo. Crie o torneio na lateral.")
    else:
        for i, j in enumerate(jogos_atuais):
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
                        if l3.button("SALVAR", key=f"sv{i}"):
                            st.session_state.jogos[i].update({'ga': int(v_ga), 'gb': int(v_gb), 'finalizado': True, 'apostas_abertas': False})
                            salvar_nuvem()
                            st.rerun()

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
                                salvar_nuvem()
                                st.rerun()
                    with col_h:
                        if j['apostas']: st.dataframe(pd.DataFrame(j['apostas']), hide_index=True)

elif menu == "Classificação":
    st.header("📊 Tabela de Pontos")
    if not jogos_atuais:
        st.info("Nenhum dado.")
    else:
        # Extrai os times
        times_lista = sorted(list(set([j['a'] for j in jogos_atuais] + [j['b'] for j in jogos_atuais])))
        cl = {t: {"P":0,"V":0,"E":0,"D":0,"GP":0,"GC":0} for t in times_lista}
        
        for j in jogos_atuais:
            if j.get("finalizado") and j.get("ga") is not None:
                a, b, ga, gb = j["a"], j["b"], int(j["ga"]), int(j["gb"])
                cl[a]["GP"] += ga; cl[a]["GC"] += gb; cl[b]["GP"] += gb; cl[b]["GC"] += ga
                if ga > gb: cl[a]["P"] += 3; cl[a]["V"] += 1; cl[b]["D"] += 1
                elif gb > ga: cl[b]["P"] += 3; cl[b]["V"] += 1; cl[a]["D"] += 1
                else: cl[a]["P"] += 1; cl[b]["P"] += 1; cl[a]["E"] += 1; cl[b]["E"] += 1
        
        df_final = pd.DataFrame.from_dict(cl, orient='index').sort_values(by=["P", "V"], ascending=False)
        st.table(df_final)

elif menu == "Ranking":
    st.header("💰 Ranking de Apostas")
    rk = {}
    for j in jogos_atuais:
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
        df_rk = pd.DataFrame([{"Nome": k, "Saldo": money(v["ganho"]-v["gasto"]), "s": v["ganho"]-v["gasto"]} for k, v in rk.items()])
        st.dataframe(df_rk.sort_values("s", ascending=False).drop(columns="s"), hide_index=True)
