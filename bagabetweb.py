import streamlit as st
import pandas as pd
import itertools
import random
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="BAGA BET DEBUG", layout="wide", page_icon="⚽")
conn = st.connection("gsheets", type=GSheetsConnection)

def money(v):
    try: return f"R$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except: return "R$ 0,00"

# --- TRATAMENTO DE DADOS (CONVERSORES "TANQUE DE GUERRA") ---

def to_bool(val):
    """Converte qualquer lixo do Sheets em Booleano Real"""
    s = str(val).strip().upper()
    return s in ["TRUE", "1", "VERDADEIRO", "T", "1.0"]

def to_int(val):
    try:
        if pd.isna(val) or str(val).strip() == "": return None
        return int(float(str(val).replace(",", ".")))
    except: return None

def parse_bets(txt):
    lista = []
    txt = str(txt).strip()
    if txt in ["nan", "None", ""]: return lista
    try:
        for item in txt.split("|"):
            p = item.split(":")
            if len(p) == 3:
                lista.append({"nome": p[0], "valor": float(p[1]), "opcao": p[2].upper()})
    except: pass
    return lista

def carregar_tudo():
    # ttl=0 garante que ele ignore o cache e leia do Google agora!
    df = conn.read(ttl=0)
    if df is None or df.empty: return [], [], df
    
    jogos = []
    times = set()
    for _, row in df.iterrows():
        fina = to_bool(row.get('finalizado'))
        # Se não está finalizado, abre por padrão
        aber = to_bool(row.get('apostas_abertas')) if fina else True
        
        j = {
            "a": str(row.get('a', '')),
            "b": str(row.get('b', '')),
            "ga": to_int(row.get('ga')),
            "gb": to_int(row.get('gb')),
            "finalizado": fina,
            "apostas_abertas": aber,
            "apostas": parse_bets(row.get('apostas'))
        }
        jogos.append(j)
        times.add(j['a']); times.add(j['b'])
    return jogos, list(times), df

def salvar_tudo(lista):
    df_save = pd.DataFrame(lista)
    # Salvamos como texto puro para o Sheets não estragar
    df_save['apostas'] = df_save['apostas'].apply(lambda x: "|".join([f"{a['nome']}:{a['valor']}:{a['opcao']}" for a in x]) if x else "")
    df_save['finalizado'] = df_save['finalizado'].apply(lambda x: "TRUE" if x else "FALSE")
    df_save['apostas_abertas'] = df_save['apostas_abertas'].apply(lambda x: "TRUE" if x else "FALSE")
    conn.update(data=df_save)
    st.cache_data.clear()

# --- INICIALIZAÇÃO ---
if 'jogos' not in st.session_state:
    st.session_state.jogos, st.session_state.times, st.session_state.df_raw = carregar_tudo()

# --- SIDEBAR ---
st.sidebar.title("⚽ BAGA BET")
senha = st.sidebar.text_input("Senha Admin", type="password")
sou_admin = (senha == "1234")

if st.sidebar.button("🔄 FORÇAR ATUALIZAÇÃO (F5)"):
    st.session_state.jogos, st.session_state.times, st.session_state.df_raw = carregar_tudo()
    st.rerun()

menu = st.sidebar.radio("Navegação", ["Jogos", "Ranking Financeiro", "Classificação", "Painel Admin"])

# --- 🔍 MONITOR DE DIAGNÓSTICO (SÓ APARECE PARA ADMIN) ---
if sou_admin:
    with st.expander("🔍 MONITOR DE DADOS (ADMIN) - Veja o que o sistema leu"):
        st.write("Dados Brutos vindos da Planilha:")
        st.dataframe(st.session_state.df_raw)
        
        st.write("Dados Processados pelo Código:")
        debug_data = []
        for j in st.session_state.jogos:
            debug_data.append({
                "Jogo": f"{j['a']} x {j['b']}",
                "Finalizado?": j['finalizado'],
                "Apostas Abertas?": j['apostas_abertas'],
                "Qtd Apostas": len(j['apostas'])
            })
        st.table(debug_data)

# --- ABA JOGOS ---
if menu == "Jogos":
    st.header("🏟️ Partidas")
    for i, j in enumerate(st.session_state.jogos):
        with st.container(border=True):
            c1, c2, c3 = st.columns([2, 1, 2])
            ga_v = j['ga'] if j['ga'] is not None else "-"
            gb_v = j['gb'] if j['gb'] is not None else "-"
            
            c1.markdown(f"<h3 style='text-align:right;'>{j['a']}</h3>", unsafe_allow_html=True)
            c2.markdown(f"<h1 style='text-align:center; color:red;'>{ga_v} x {gb_v}</h1>", unsafe_allow_html=True)
            c3.markdown(f"<h3 style='text-align:left;'>{j['b']}</h3>", unsafe_allow_html=True)

            if sou_admin:
                col1, col2 = st.columns(2)
                if not j['finalizado']:
                    with col1.expander("Encerrar Jogo"):
                        v_ga = st.number_input(f"Gols {j['a']}", 0, 20, key=f"ga{i}")
                        v_gb = st.number_input(f"Gols {j['b']}", 0, 20, key=f"gb{i}")
                        if st.button("SALVAR RESULTADO", key=f"sv{i}"):
                            st.session_state.jogos[i].update({'ga': int(v_ga), 'gb': int(v_gb), 'finalizado': True, 'apostas_abertas': False})
                            salvar_tudo(st.session_state.jogos)
                            st.rerun()
                else:
                    if col1.button("🔄 REABRIR JOGO", key=f"re{i}"):
                        st.session_state.jogos[i].update({'finalizado': False, 'apostas_abertas': True})
                        salvar_tudo(st.session_state.jogos)
                        st.rerun()

            # Abas de Apostas
            tab1, tab2 = st.tabs(["📋 Apostas", "💰 Apostar"])
            with tab1:
                if j['apostas']:
                    df_ap = pd.DataFrame(j['apostas'])
                    df_ap['Palpite'] = df_ap['opcao'].map({"A": j['a'], "B": j['b'], "E": "Empate"})
                    st.table(df_ap[['nome', 'Palpite', 'valor']])
                else: st.write("Nenhuma aposta.")
            with tab2:
                if j['apostas_abertas'] and not j['finalizado'] and sou_admin:
                    n_ap = st.text_input("Nome", key=f"n{i}")
                    v_ap = st.number_input("Valor", 5.0, 500.0, 10.0, key=f"v{i}")
                    o_ap = st.radio("Palpite", [j['a'], "Empate", j['b']], key=f"o{i}", horizontal=True)
                    if st.button("Confirmar Aposta", key=f"bt{i}"):
                        cod = "A" if o_ap == j['a'] else "B" if o_ap == j['b'] else "E"
                        st.session_state.jogos[i]['apostas'].append({"nome": n_ap, "valor": v_ap, "opcao": cod})
                        salvar_tudo(st.session_state.jogos)
                        st.rerun()
                else:
                    st.info("Apostas bloqueadas (Finalizado ou não é Admin).")

# --- ABA RANKING ---
elif menu == "Ranking Financeiro":
    st.header("💰 Ranking Financeiro")
    ranking = {}
    for j in st.session_state.jogos:
        # CONDIÇÃO CRÍTICA: Se o monitor diz 'True' aqui, o ranking TEM que aparecer
        if j['finalizado'] and j['ga'] is not None:
            res_real = "A" if j['ga'] > j['gb'] else "B" if j['gb'] > j['ga'] else "E"
            pote = sum(a['valor'] for a in j['apostas'])
            venc_v = sum(a['valor'] for a in j['apostas'] if a['opcao'] == res_real)
            
            for a in j['apostas']:
                n = a['nome']
                ranking.setdefault(n, {"ganho": 0.0, "pago": 0.0})
                ranking[n]["pago"] += a['valor']
                if a['opcao'] == res_real and venc_v > 0:
                    ranking[n]["ganho"] += (a['valor'] / venc_v) * pote

    if ranking:
        dados_r = [{"Nome": k, "Saldo": v['ganho'] - v['pago']} for k, v in ranking.items()]
        df_rank = pd.DataFrame(dados_r).sort_values("Saldo", ascending=False)
        st.dataframe(df_rank.style.format({"Saldo": "R$ {:.2f}"}), use_container_width=True)
    else:
        st.warning("Ranking vazio. Certifique-se de que os jogos estão FINALIZADOS no Monitor de Dados.")

# --- ABA CLASSIFICAÇÃO ---
elif menu == "Classificação":
    st.header("📊 Tabela")
    cl = {t: {"P":0,"J":0,"V":0,"E":0,"D":0,"SG":0} for t in st.session_state.times}
    for j in st.session_state.jogos:
        if j['ga'] is not None and j['gb'] is not None:
            a, b, ga, gb = j['a'], j['b'], j['ga'], j['gb']
            cl[a]["J"]+=1; cl[b]["J"]+=1
            if ga > gb: cl[a]["P"]+=3; cl[a]["V"]+=1; cl[b]["D"]+=1
            elif gb > ga: cl[b]["P"]+=3; cl[b]["V"]+=1; cl[a]["D"]+=1
            else: cl[a]["P"]+=1; cl[b]["P"]+=1; cl[a]["E"]+=1; cl[b]["E"]+=1
            cl[a]["SG"] += (ga - gb); cl[b]["SG"] += (gb - ga)
    st.table(pd.DataFrame.from_dict(cl, orient='index').sort_values(["P", "V", "SG"], ascending=False))

# --- ABA ADMIN ---
elif menu == "Painel Admin":
    if sou_admin:
        st.subheader("Novo Torneio")
        txt = st.text_area("Times (um por linha)")
        if st.button("CRIAR"):
            ts = [t.strip() for t in txt.split("\n") if t.strip()]
            if len(ts) >= 2:
                combs = list(itertools.combinations(ts, 2))
                novos = [{"a": c[0], "b": c[1], "ga": None, "gb": None, "finalizado": False, "apostas_abertas": True, "apostas": []} for c in combs]
                salvar_tudo(novos)
                st.session_state.jogos, st.session_state.times = novos, ts
                st.rerun()
