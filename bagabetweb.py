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

# --- FUNÇÕES DE SINCRONIZAÇÃO ---
def salvar_nuvem():
    if 'jogos' in st.session_state:
        df = pd.DataFrame(st.session_state.jogos)
        # Transforma a lista de apostas em texto para o Google Sheets
        df['apostas'] = df['apostas'].apply(lambda x: "|".join([f"{a['nome']}:{a['valor']}:{a['opcao']}" for a in x]) if isinstance(x, list) else "")
        conn.update(data=df)

def carregar_nuvem():
    try:
        df = conn.read(ttl=0)
        if df is not None and not df.empty:
            dados = df.to_dict('records')
            for j in dados:
                # Recuperar lista de apostas
                j['apostas'] = []
                txt_ap = str(j.get('apostas', ""))
                if txt_ap and txt_ap not in ["nan", "None", ""]:
                    for item in txt_ap.split("|"):
                        p = item.split(":")
                        if len(p) == 3:
                            j['apostas'].append({"nome": p[0], "valor": float(p[1]), "opcao": p[2]})
                
                # Tratar números e booleanos
                j['ga'] = int(j['ga']) if str(j.get('ga')).isnumeric() else None
                j['gb'] = int(j['gb']) if str(j.get('gb')).isnumeric() else None
                j['finalizado'] = str(j.get('finalizado')) == "True"
                j['apostas_abertas'] = str(j.get('apostas_abertas', "True")) == "True"
            
            st.session_state.jogos = dados
            # Puxa os times únicos da lista de jogos
            st.session_state.times = list(set([j['a'] for j in dados] + [j['b'] for j in dados]))
        else:
            st.session_state.jogos = []
            st.session_state.times = []
    except Exception as e:
        st.session_state.jogos = []

# --- CARREGAMENTO INICIAL ---
if 'jogos' not in st.session_state or not st.session_state.jogos:
    carregar_nuvem()

# --- SEGURANÇA ---
st.sidebar.title("BAGA BET ⚽")
admin_key = st.sidebar.text_input("Chave do Admin", type="password")
sou_admin = (admin_key == "1234") 

if st.sidebar.button("🔄 ATUALIZAR TABELA/JOGOS"):
    carregar_nuvem()
    st.rerun()

menu = st.sidebar.radio("Navegação", ["Jogos", "Classificação", "Ranking Apostas", "Novo Torneio"])

# --- NOVO TORNEIO ---
if menu == "Novo Torneio":
    if not sou_admin:
        st.error("Acesso restrito.")
    else:
        st.header("🏆 Criar Novo Campeonato")
        st.warning("Isso apagará os jogos atuais no Google Sheets!")
        qtd = st.number_input("Qtd Times", 2, 20, 4)
        nomes = [st.text_input(f"Time {i+1}", key=f"t{i}") for i in range(qtd)]
        if st.button("GERAR E SALVAR NA NUVEM"):
            ts = [n for n in nomes if n]
            if len(ts) >= 2:
                ps = list(itertools.combinations(ts, 2))
                random.shuffle(ps)
                st.session_state.times = ts
                st.session_state.jogos = [{"a": p[0], "b": p[1], "ga": None, "gb": None, "finalizado": False, "apostas_abertas": True, "apostas": []} for p in ps]
                salvar_nuvem()
                st.success("Torneio Criado! Vá para a aba 'Jogos'.")
                st.rerun()

# --- ABA JOGOS ---
elif menu == "Jogos":
    st.header("⚽ Partidas")
    if not st.session_state.get('jogos'):
        st.info("Nenhum jogo na nuvem. Crie um novo torneio.")
    else:
        for i, j in enumerate(st.session_state.jogos):
            with st.container(border=True):
                c1, c2, c3 = st.columns([2, 1, 2])
                ga_v = j['ga'] if j['ga'] is not None else "-"
                gb_v = j['gb'] if j['gb'] is not None else "-"
                c1.markdown(f"<h2 style='text-align:right;'>{j['a']}</h2>", unsafe_allow_html=True)
                c2.markdown(f"<h1 style='text-align:center; color:red;'>{ga_v} x {gb_v}</h1>", unsafe_allow_html=True)
                c3.markdown(f"<h2 style='text-align:left;'>{j['b']}</h2>", unsafe_allow_html=True)

                if sou_admin and not j['finalizado']:
                    with st.expander("⚙️ LANÇAR GOLS (ADMIN)"):
                        l1, l2, l3 = st.columns([2, 2, 2])
                        l1.markdown(f"**Gols {j['a']}**")
                        v_ga = l1.number_input("", 0, 99, key=f"vga{i}", step=1, label_visibility="collapsed")
                        l2.markdown(f"**Gols {j['b']}**")
                        v_gb = l2.number_input("", 0, 99, key=f"vgb{i}", step=1, label_visibility="collapsed")
                        if l3.button("SALVAR PLACAR", key=f"sv{i}", type="primary"):
                            st.session_state.jogos[i].update({'ga': v_ga, 'gb': v_gb, 'finalizado': True, 'apostas_abertas': False})
                            salvar_nuvem(); st.rerun()

                aps = j['apostas']
                va = sum(x['valor'] for x in aps if x['opcao'] == "A")
                ve = sum(x['valor'] for x in aps if x['opcao'] == "E")
                vb = sum(x['valor'] for x in aps if x['opcao'] == "B")
                m1, m2, m3, m4 = st.columns(4)
                m1.metric(j['a'], money(va)); m2.metric("Empate", money(ve)); m3.metric(j['b'], money(vb)); m4.metric("POTE", money(va+ve+vb))

                with st.expander("💰 APOSTAR"):
                    cx, cy = st.columns([1, 2])
                    with cx:
                        if j['apostas_abertas'] and not j['finalizado']:
                            n_ap = st.text_input("Nome", key=f"n{i}")
                            v_ap = st.number_input("R$", 1.0, 5000.0, 10.0, step=1.0, key=f"v{i}")
                            o_ap = st.radio("Vencerá:", [j['a'], "Empate", j['b']], key=f"o{i}", horizontal=True)
                            if st.button("Confirmar", key=f"bt{i}"):
                                t = "A" if o_ap == j['a'] else "B" if o_ap == j['b'] else "E"
                                st.session_state.jogos[i]['apostas'].append({"nome": n_ap, "valor": v_ap, "opcao": t})
                                salvar_nuvem(); st.rerun()
                    with cy:
                        if aps:
                            df_p = pd.DataFrame(aps)
                            df_p['Palpite'] = df_p['opcao'].map({"A": j['a'], "B": j['b'], "E": "Empate"})
                            st.dataframe(df_p[['nome', 'Palpite', 'valor']], hide_index=True)

# --- CLASSIFICAÇÃO ---
elif menu == "Classificação":
    st.header("📊 Tabela de Pontos")
    carregar_nuvem() # Força carregar do Sheets antes de mostrar
    if not st.session_state.get('jogos'):
        st.info("Nenhum jogo finalizado.")
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
        st.table(df_cl)

# --- RANKING ---
elif menu == "Ranking Apostas":
    st.header("💰 Ranking de Lucro")
    carregar_nuvem()
    rk = {}
    for j in st.session_state.get('jogos', []):
        if not j["finalizado"]: continue
        res = "A" if j["ga"] > j["gb"] else "B" if j["gb"] > j["ga"] else "E"
        pote = sum(a["valor"] for a in j["apostas"])
        venc = sum(a["valor"] for a in j["apostas"] if a["opcao"] == res)
        for a in j["apostas"]:
            rk.setdefault(a["nome"], {"in": 0, "re": 0})
            rk[a["nome"]]["in"] += a["valor"]
            if a["opcao"] == res and venc > 0: rk[a["nome"]]["re"] += (a["valor"]/venc*pote)
    if rk:
        res_rk = [{"Nome": n, "Investido": money(d['in']), "Retorno": money(d['re']), "Saldo": money(d['re']-d['in']), "s": d['re']-d['in']} for n, d in rk.items()]
        st.dataframe(pd.DataFrame(res_rk).sort_values("s", ascending=False).drop(columns="s"), hide_index=True)
