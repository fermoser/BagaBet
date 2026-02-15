import streamlit as st
import pandas as pd
import itertools
import random
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="BAGA BET PRO", layout="wide", page_icon="⚽")
conn = st.connection("gsheets", type=GSheetsConnection)

def money(v):
    try: return f"R$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except: return "R$ 0,00"

# --- CONVERSORES DE SEGURANÇA ---

def parse_bool(val, padrao=False):
    """Converte texto do Sheets para Booleano Real"""
    s = str(val).strip().upper()
    if s == "TRUE": return True
    if s == "FALSE": return False
    return padrao

def parse_apostas(txt):
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

# --- NUVEM ---

def carregar_dados_nuvem():
    try:
        df = conn.read(ttl=0)
        if df is not None and not df.empty:
            df = df.dropna(subset=['a', 'b'])
            jogos_lidos = []
            times_lidos = set()
            for row in df.to_dict('records'):
                # LOGICA DE SEGURANÇA:
                # Se 'finalizado' for False, o padrão de 'apostas_abertas' DEVE ser True
                fina = parse_bool(row.get('finalizado'), False)
                aber = parse_bool(row.get('apostas_abertas'), not fina) 
                
                ga = row.get('ga')
                gb = row.get('gb')
                
                j = {
                    "a": str(row.get('a')), "b": str(row.get('b')),
                    "ga": int(float(ga)) if pd.notna(ga) and str(ga).strip() != "" else None,
                    "gb": int(float(gb)) if pd.notna(gb) and str(gb).strip() != "" else None,
                    "finalizado": fina, 
                    "apostas_abertas": aber,
                    "apostas": parse_apostas(row.get('apostas'))
                }
                jogos_lidos.append(j)
                times_lidos.add(j['a']); times_lidos.add(j['b'])
            return jogos_lidos, list(times_lidos)
    except: pass
    return [], []

def salvar_dados_nuvem(lista):
    df_save = pd.DataFrame(lista)
    # Converte tudo para string clara antes de enviar
    df_save['apostas'] = df_save['apostas'].apply(lambda x: "|".join([f"{a['nome']}:{a['valor']}:{a['opcao']}" for a in x]) if x else "")
    df_save['finalizado'] = df_save['finalizado'].apply(lambda x: "TRUE" if x else "FALSE")
    df_save['apostas_abertas'] = df_save['apostas_abertas'].apply(lambda x: "TRUE" if x else "FALSE")
    conn.update(data=df_save)
    st.cache_data.clear()

# --- INICIALIZAÇÃO ---
if 'jogos' not in st.session_state:
    st.session_state.jogos, st.session_state.times = carregar_dados_nuvem()

# --- SIDEBAR ---
st.sidebar.title("BAGA BET ⚽")
senha = st.sidebar.text_input("Chave Admin", type="password")
sou_admin = (senha == "1234")

if st.sidebar.button("🔄 ATUALIZAR TUDO"):
    st.session_state.jogos, st.session_state.times = carregar_dados_nuvem()
    st.rerun()

menu = st.sidebar.radio("Menu", ["Jogos", "Ranking Financeiro", "Classificação", "Resetar Torneio"])

# --- INTERFACE JOGOS ---
if menu == "Jogos":
    st.header("⚽ Partidas e Apostas")
    for i, j in enumerate(st.session_state.jogos):
        with st.container(border=True):
            c1, c2, c3 = st.columns([2, 1, 2])
            ga, gb = (j['ga'] if j['ga'] is not None else "-"), (j['gb'] if j['gb'] is not None else "-")
            
            # Cabeçalho do jogo
            c1.markdown(f"<h3 style='text-align:right;'>{j['a']}</h3>", unsafe_allow_html=True)
            c2.markdown(f"<h1 style='text-align:center; color:red;'>{ga} x {gb}</h1>", unsafe_allow_html=True)
            c3.markdown(f"<h3 style='text-align:left;'>{j['b']}</h3>", unsafe_allow_html=True)

            # ADMIN: Ações
            if sou_admin:
                cadm = st.columns(2)
                if not j['finalizado']:
                    with cadm[0].expander("Lançar Placar"):
                        l1, l2 = st.columns(2)
                        v_ga = l1.number_input(f"Gols {j['a']}", 0, 20, key=f"ga_{i}")
                        v_gb = l2.number_input(f"Gols {j['b']}", 0, 20, key=f"gb_{i}")
                        if st.button("Encerrar Jogo", key=f"end_{i}"):
                            st.session_state.jogos[i].update({'ga': int(v_ga), 'gb': int(v_gb), 'finalizado': True, 'apostas_abertas': False})
                            salvar_dados_nuvem(st.session_state.jogos)
                            st.rerun()
                else:
                    if cadm[0].button("Reabrir Jogo/Apostas", key=f"re_{i}"):
                        st.session_state.jogos[i].update({'finalizado': False, 'apostas_abertas': True})
                        salvar_dados_nuvem(st.session_state.jogos)
                        st.rerun()

            # SEÇÃO DE APOSTAS
            t_ver, t_faz = st.tabs(["📋 Apostas", "💰 Apostar"])
            with t_ver:
                if j['apostas']:
                    df_ap = pd.DataFrame(j['apostas'])
                    df_ap['Time'] = df_ap['opcao'].map({"A": j['a'], "B": j['b'], "E": "Empate"})
                    st.table(df_ap[['nome', 'Time', 'valor']])
                else: st.write("Nenhuma aposta.")
            
            with t_faz:
                if sou_admin and j['apostas_abertas']:
                    n = st.text_input("Nome", key=f"n_{i}")
                    v = st.number_input("Valor R$", 1.0, 500.0, 10.0, key=f"v_{i}")
                    o = st.radio("Vencedor", [j['a'], "Empate", j['b']], key=f"o_{i}", horizontal=True)
                    if st.button("Confirmar", key=f"b_{i}"):
                        opt = "A" if o == j['a'] else "B" if o == j['b'] else "E"
                        st.session_state.jogos[i]['apostas'].append({"nome": n, "valor": v, "opcao": opt})
                        salvar_dados_nuvem(st.session_state.jogos)
                        st.rerun()
                else: st.info("Apostas encerradas para este jogo.")

# --- RANKING (CÁLCULO AUTOMÁTICO NA ENTRADA) ---
elif menu == "Ranking Financeiro":
    st.header("🤑 Ranking de Lucros")
    ranking = {}
    for j in st.session_state.jogos:
        if j['finalizado'] and j['ga'] is not None:
            res = "A" if j['ga'] > j['gb'] else "B" if j['gb'] > j['ga'] else "E"
            pote = sum(a['valor'] for a in j['apostas'])
            venc = sum(a['valor'] for a in j['apostas'] if a['opcao'] == res)
            for a in j['apostas']:
                ranking.setdefault(a['nome'], {"inv": 0.0, "gan": 0.0})
                ranking[a['nome']]["inv"] += a['valor']
                if a['opcao'] == res and venc > 0:
                    ranking[a['nome']]["gan"] += (a['valor']/venc*pote)
    
    if ranking:
        dados = [{"Apostador": k, "Lucro/Prejuízo": v['gan'] - v['inv']} for k, v in ranking.items()]
        df_r = pd.DataFrame(dados).sort_values("Lucro/Prejuízo", ascending=False)
        st.table(df_r.style.format({"Lucro/Prejuízo": "R$ {:.2f}"}))
    else:
        st.warning("Finalize um jogo para ver o ranking.")

# --- CLASSIFICAÇÃO ---
elif menu == "Classificação":
    st.header("📊 Tabela")
    stats = {t: {"P":0,"J":0,"V":0,"E":0,"D":0,"SG":0} for t in st.session_state.times}
    for j in st.session_state.jogos:
        if j['ga'] is not None and j['gb'] is not None:
            a, b, ga, gb = j['a'], j['b'], j['ga'], j['gb']
            stats[a]["J"]+=1; stats[b]["J"]+=1
            if ga > gb: stats[a]["P"]+=3; stats[a]["V"]+=1; stats[b]["D"]+=1
            elif gb > ga: stats[b]["P"]+=3; stats[b]["V"]+=1; stats[a]["D"]+=1
            else: stats[a]["P"]+=1; stats[b]["P"]+=1; stats[a]["E"]+=1; stats[b]["E"]+=1
            stats[a]["SG"] += (ga - gb); stats[b]["SG"] += (gb - ga)
    df_c = pd.DataFrame.from_dict(stats, orient='index').sort_values(["P", "V", "SG"], ascending=False)
    st.table(df_c)

elif menu == "Resetar Torneio":
    if sou_admin:
        st.subheader("Resetar Tudo")
        txt = st.text_area("Nomes dos times (um por linha)")
        if st.button("CRIAR"):
            ts = [t.strip() for t in txt.split("\n") if t.strip()]
            if len(ts) >= 2:
                pares = list(itertools.combinations(ts, 2))
                novos = [{"a": p[0], "b": p[1], "ga": None, "gb": None, "finalizado": False, "apostas_abertas": True, "apostas": []} for p in pares]
                salvar_dados_nuvem(novos)
                st.session_state.jogos = novos; st.session_state.times = ts
                st.rerun()
