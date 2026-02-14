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

# --- CARREGAMENTO REFORÇADO ---
def carregar_dados():
    try:
        # TTL=0 força o Streamlit a ignorar o cache e ler o Google Sheets agora
        df = conn.read(ttl=0)
        if df is not None and not df.empty:
            jogos_lidos = df.to_dict('records')
            jogos_certos = []
            for j in jogos_lidos:
                # 1. Recuperar Apostas (Tratamento de Erros)
                j['apostas'] = []
                txt_ap = str(j.get('apostas', ""))
                if txt_ap and txt_ap not in ["nan", "None", ""]:
                    for item in txt_ap.split("|"):
                        p = item.split(":")
                        if len(p) == 3:
                            j['apostas'].append({"nome": p[0], "valor": float(p[1]), "opcao": p[2]})
                
                # 2. Tipagem de Gols e Status
                j['ga'] = int(j['ga']) if str(j.get('ga')) not in ["None", "nan", ""] else None
                j['gb'] = int(j['gb']) if str(j.get('gb')) not in ["None", "nan", ""] else None
                j['finalizado'] = str(j.get('finalizado')) == "True"
                j['apostas_abertas'] = str(j.get('apostas_abertas', "True")) == "True"
                jogos_certos.append(j)
            
            st.session_state.jogos = jogos_certos
            st.session_state.times = list(set([j['a'] for j in jogos_certos] + [j['b'] for j in jogos_certos]))
            return True
    except Exception as e:
        st.error(f"Erro na leitura: {e}")
    return False

def salvar_nuvem():
    if 'jogos' in st.session_state and st.session_state.jogos:
        df = pd.DataFrame(st.session_state.jogos)
        df['apostas'] = df['apostas'].apply(lambda x: "|".join([f"{a['nome']}:{a['valor']}:{a['opcao']}" for a in x]) if x else "")
        conn.update(data=df)

# Inicialização
if 'jogos' not in st.session_state:
    carregar_dados()

# --- SIDEBAR ---
st.sidebar.title("BAGA BET ⚽")
admin_key = st.sidebar.text_input("Chave do Admin", type="password")
sou_admin = (admin_key == "1234") 

if st.sidebar.button("🔄 SINCRONIZAR NUVEM"):
    carregar_dados()
    st.rerun()

menu = st.sidebar.radio("Menu", ["Jogos", "Classificação", "Ranking Apostas", "Novo Torneio"])

if sou_admin and st.sidebar.button("⚠️ RESETAR TUDO"):
    st.session_state.jogos = []
    salvar_nuvem(); st.rerun()

# --- TELAS ---
if menu == "Novo Torneio":
    if not sou_admin: st.error("Acesso Admin necessário.")
    else:
        st.header("🏆 Novo Torneio")
        qtd = st.number_input("Qtd Times", 2, 20, 4)
        nomes = [st.text_input(f"Time {i+1}", key=f"t{i}") for i in range(qtd)]
        if st.button("GERAR"):
            ts = [n for n in nomes if n]
            if len(ts) >= 2:
                ps = list(itertools.combinations(ts, 2))
                random.shuffle(ps)
                st.session_state.jogos = [{"a": p[0], "b": p[1], "ga": None, "gb": None, "finalizado": False, "apostas_abertas": True, "apostas": []} for p in ps]
                salvar_nuvem(); st.rerun()

elif menu == "Jogos":
    st.header("⚽ Partidas")
    if not st.session_state.get('jogos'):
        st.info("Nenhum jogo carregado. Clique em 'Sincronizar Nuvem' ou crie um torneio.")
    else:
        for i, j in enumerate(st.session_state.jogos):
            with st.container(border=True):
                # PLACAR
                c1, c2, c3 = st.columns([2, 1, 2])
                ga_ex, gb_ex = (j['ga'] if j['ga'] is not None else "-"), (j['gb'] if j['gb'] is not None else "-")
                c1.markdown(f"<h2 style='text-align:right;'>{j['a']}</h2>", unsafe_allow_html=True)
                c2.markdown(f"<h1 style='text-align:center; color:red;'>{ga_ex} x {gb_ex}</h1>", unsafe_allow_html=True)
                c3.markdown(f"<h2 style='text-align:left;'>{j['b']}</h2>", unsafe_allow_html=True)

                # ADMIN: LANÇAR GOLS
                if sou_admin and not j['finalizado']:
                    with st.expander("⚙️ LANÇAR RESULTADO"):
                        l1, l2, l3 = st.columns([2, 2, 2])
                        v_ga = l1.number_input(f"Gols {j['a']}", 0, 99, key=f"vga{i}", step=1)
                        v_gb = l2.number_input(f"Gols {j['b']}", 0, 99, key=f"vgb{i}", step=1)
                        if l3.button("SALVAR", key=f"sv{i}", use_container_width=True, type="primary"):
                            st.session_state.jogos[i].update({'ga': v_ga, 'gb': v_gb, 'finalizado': True, 'apostas_abertas': False})
                            salvar_nuvem(); st.rerun()

                # POTE
                aps = j['apostas']
                va = sum(x['valor'] for x in aps if x['opcao'] == "A")
                ve = sum(x['valor'] for x in aps if x['opcao'] == "E")
                vb = sum(x['valor'] for x in aps if x['opcao'] == "B")
                m1, m2, m3, m4 = st.columns(4)
                m1.metric(j['a'], money(va)); m2.metric("Empate", money(ve)); m3.metric(j['b'], money(vb)); m4.metric("TOTAL", money(va+ve+vb))

                # FORMULÁRIO DE APOSTAS (Restaurado)
                with st.expander("💰 APOSTAR / VER DETALHES"):
                    col1, col2 = st.columns([1, 1.5])
                    with col1:
                        if j['apostas_abertas'] and not j['finalizado']:
                            st.subheader("Nova Aposta")
                            nome_ap = st.text_input("Nome", key=f"n{i}")
                            valor_ap = st.number_input("Valor R$", 1.0, 5000.0, 10.0, step=1.0, key=f"v{i}")
                            op_ap = st.radio("Palpite", [j['a'], "Empate", j['b']], key=f"o{i}", horizontal=True)
                            if st.button("Confirmar", key=f"bt{i}", use_container_width=True):
                                if nome_ap:
                                    t = "A" if op_ap == j['a'] else "B" if op_ap == j['b'] else "E"
                                    st.session_state.jogos[i]['apostas'].append({"nome": nome_ap, "valor": valor_ap, "opcao": t})
                                    salvar_nuvem(); st.rerun()
                        else:
                            st.warning("🔒 Apostas encerradas.")

                    with col2:
                        st.subheader("Histórico")
                        if aps:
                            df_ap = pd.DataFrame(aps)
                            df_ap['Palpite'] = df_ap['opcao'].map({"A": j['a'], "B": j['b'], "E": "Empate"})
                            if j['finalizado']:
                                res = "A" if j['ga'] > j['gb'] else "B" if j['gb'] > j['ga'] else "E"
                                pote = va + ve + vb
                                v_venc = sum(x['valor'] for x in aps if x['opcao'] == res)
                                df_ap['Retorno'] = df_ap.apply(lambda r: (r['valor']/v_venc*pote) if r['opcao']==res and v_venc>0 else 0.0, axis=1)
                                df_ap['Retorno'] = df_ap['Retorno'].apply(money)
                            df_ap['valor'] = df_ap['valor'].apply(money)
                            st.dataframe(df_ap, hide_index=True, use_container_width=True)

elif menu == "Classificação":
    st.header("📊 Classificação")
    carregar_dados() # Força leitura antes de mostrar
    if not st.session_state.get('jogos'): st.info("Sem dados.")
    else:
        cl = {t: {"P":0,"V":0,"E":0,"D":0,"GP":0,"GC":0} for t in st.session_state.times}
        for j in st.session_state.jogos:
            if not j["finalizado"] or j["ga"] is None: continue
            a, b, ga, gb = j["a"], j["b"], int(j["ga"]), int(j["gb"])
            cl[a]["GP"]+=ga; cl[a]["GC"]+=gb; cl[b]["GP"]+=gb; cl[b]["GC"]+=ga
            if ga > gb: cl[a]["P"]+=3; cl[a]["V"]+=1; cl[b]["D"]+=1
            elif gb > ga: cl[b]["P"]+=3; cl[b]["V"]+=1; cl[a]["D"]+=1
            else: cl[a]["P"]+=1; cl[b]["P"]+=1; cl[a]["E"]+=1; cl[b]["E"]+=1
        df_cl = pd.DataFrame.from_dict(cl, orient='index').sort_values(by="P", ascending=False)
        st.table(df_cl)

elif menu == "Ranking Apostas":
    st.header("💰 Ranking")
    carregar_dados()
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
        res_rk = [{"Nome": n, "Gasto": money(d['in']), "Ganho": money(d['re']), "Lucro": money(d['re']-d['in']), "sort": d['re']-d['in']} for n, d in rk.items()]
        st.dataframe(pd.DataFrame(res_rk).sort_values("sort", ascending=False).drop(columns="sort"), hide_index=True, use_container_width=True)
