import streamlit as st
import pandas as pd
import itertools
import random
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="BAGA BET PRO", layout="wide", page_icon="⚽")
conn = st.connection("gsheets", type=GSheetsConnection)

# --- UTILITÁRIOS DE FORMATAÇÃO ---
def money(v):
    try:
        cor = "green" if v > 0 else "red" if v < 0 else "black"
        val_fmt = f"R$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return f'<span style="color:{cor}; font-weight:bold;">{val_fmt}</span>'
    except: return "R$ 0,00"

def money_raw(v):
    try: return f"R$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except: return "R$ 0,00"

# --- TRATAMENTO DE DADOS (BLINDAGEM) ---

def to_bool(val):
    """Converte qualquer formato do Sheets em Booleano"""
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
    df = conn.read(ttl=0)
    if df is None or df.empty: return [], [], df
    jogos = []
    times = set()
    for _, row in df.iterrows():
        fina = to_bool(row.get('finalizado'))
        # Se não finalizou, as apostas precisam estar abertas por lógica
        aber = to_bool(row.get('apostas_abertas')) if fina else True
        j = {
            "a": str(row.get('a', '')), "b": str(row.get('b', '')),
            "ga": to_int(row.get('ga')), "gb": to_int(row.get('gb')),
            "finalizado": fina, "apostas_abertas": aber,
            "apostas": parse_bets(row.get('apostas'))
        }
        jogos.append(j); times.add(j['a']); times.add(j['b'])
    return jogos, list(times), df

def salvar_tudo(lista):
    df_save = pd.DataFrame(lista)
    df_save['apostas'] = df_save['apostas'].apply(lambda x: "|".join([f"{a['nome']}:{a['valor']}:{a['opcao']}" for a in x]) if x else "")
    df_save['finalizado'] = df_save['finalizado'].apply(lambda x: "TRUE" if x else "FALSE")
    df_save['apostas_abertas'] = df_save['apostas_abertas'].apply(lambda x: "TRUE" if x else "FALSE")
    conn.update(data=df_save)
    st.cache_data.clear()

# --- INICIALIZAÇÃO ---
if 'jogos' not in st.session_state:
    st.session_state.jogos, st.session_state.times, st.session_state.df_raw = carregar_tudo()

# --- SIDEBAR ---
st.sidebar.title("⚽ BAGA BET PRO")
senha = st.sidebar.text_input("Chave Admin", type="password")
sou_admin = (senha == "1234")

if st.sidebar.button("🔄 SINCRONIZAR NUVEM"):
    st.session_state.jogos, st.session_state.times, st.session_state.df_raw = carregar_tudo()
    st.rerun()

menu = st.sidebar.radio("Navegação", ["Jogos", "Ranking Apostas", "Classificação", "Painel Admin"])

# --- MONITOR ADMIN (O SEU SEGURO) ---
if sou_admin:
    with st.expander("🔍 MONITOR DE DADOS (Diagnóstico)"):
        c_debug1, c_debug2 = st.columns(2)
        c_debug1.write("**Na Planilha:**")
        c_debug1.dataframe(st.session_state.df_raw[['a', 'b', 'finalizado', 'apostas_abertas']])
        c_debug2.write("**No Sistema:**")
        debug_list = [{"Jogo": f"{j['a']}x{j['b']}", "Fim": j['finalizado'], "Aberto": j['apostas_abertas']} for j in st.session_state.jogos]
        c_debug2.table(debug_list)

# --- 1. JOGOS ---
if menu == "Jogos":
    st.header("🏟️ Partidas da Rodada")
    for i, j in enumerate(st.session_state.jogos):
        with st.container(border=True):
            col1, col2, col3 = st.columns([2, 1, 2])
            ga, gb = (j['ga'] if j['ga'] is not None else "-"), (j['gb'] if j['gb'] is not None else "-")
            col1.markdown(f"<h3 style='text-align:right;'>{j['a']}</h3>", unsafe_allow_html=True)
            col2.markdown(f"<h1 style='text-align:center; color:red;'>{ga} x {gb}</h1>", unsafe_allow_html=True)
            col3.markdown(f"<h3 style='text-align:left;'>{j['b']}</h3>", unsafe_allow_html=True)

            if sou_admin:
                adm_col = st.columns(2)
                if not j['finalizado']:
                    with adm_col[0].expander("Lançar Resultado"):
                        vga = st.number_input(f"Gols {j['a']}", 0, 20, key=f"vga{i}")
                        vgb = st.number_input(f"Gols {j['b']}", 0, 20, key=f"vgb{i}")
                        if st.button("FINALIZAR JOGO", key=f"f{i}"):
                            st.session_state.jogos[i].update({'ga': int(vga), 'gb': int(vgb), 'finalizado': True, 'apostas_abertas': False})
                            salvar_tudo(st.session_state.jogos); st.rerun()
                else:
                    if adm_col[0].button("🔄 REABRIR JOGO", key=f"r{i}"):
                        st.session_state.jogos[i].update({'finalizado': False, 'apostas_abertas': True})
                        salvar_tudo(st.session_state.jogos); st.rerun()

            t_ver, t_faz = st.tabs(["📋 Apostas", "💰 Nova Aposta"])
            with t_ver:
                if j['apostas']:
                    df_a = pd.DataFrame(j['apostas'])
                    df_a['Palpite'] = df_a['opcao'].map({"A": j['a'], "B": j['b'], "E": "Empate"})
                    st.table(df_a[['nome', 'Palpite', 'valor']])
                else: st.write("Nenhuma aposta.")
            with t_faz:
                if j['apostas_abertas'] and not j['finalizado'] and sou_admin:
                    n = st.text_input("Apostador", key=f"n{i}")
                    v = st.number_input("Valor R$", 5.0, 1000.0, 10.0, key=f"v{i}")
                    o = st.radio("Palpite", [j['a'], "Empate", j['b']], key=f"o{i}", horizontal=True)
                    if st.button("CONFIRMAR APOSTA", key=f"b{i}"):
                        cod = "A" if o == j['a'] else "B" if o == j['b'] else "E"
                        st.session_state.jogos[i]['apostas'].append({"nome": n, "valor": v, "opcao": cod})
                        salvar_tudo(st.session_state.jogos); st.rerun()
                else: st.info("Apostas encerradas.")

# --- 2. RANKING (COM CORES) ---
elif menu == "Ranking Apostas":
    st.header("🤑 Ranking Financeiro")
    rank = {}
    for j in st.session_state.jogos:
        if j['finalizado'] and j['ga'] is not None:
            res = "A" if j['ga'] > j['gb'] else "B" if j['gb'] > j['ga'] else "E"
            pote = sum(a['valor'] for a in j['apostas'])
            venc_v = sum(a['valor'] for a in j['apostas'] if a['opcao'] == res)
            for a in j['apostas']:
                rank.setdefault(a['nome'], {"ganho": 0.0, "pago": 0.0})
                rank[a['nome']]["pago"] += a['valor']
                if a['opcao'] == res and venc_v > 0:
                    rank[a['nome']]["ganho"] += (a['valor'] / venc_v) * pote
    if rank:
        lista_r = []
        for k, v in rank.items():
            saldo = v['ganho'] - v['pago']
            lista_r.append({"Apostador": k, "Investimento": money_raw(v['pago']), "Retorno": money_raw(v['ganho']), "Saldo": saldo})
        df_r = pd.DataFrame(lista_r).sort_values("Saldo", ascending=False)
        df_r['Saldo'] = df_r['Saldo'].apply(money)
        st.write(df_r.to_html(escape=False, index=False), unsafe_allow_html=True)
    else: st.info("Finalize jogos para ver o ranking.")

# --- 3. CLASSIFICAÇÃO ---
elif menu == "Classificação":
    st.header("📊 Classificação")
    stats = {t: {"P":0,"J":0,"V":0,"E":0,"D":0,"GP":0,"GC":0,"SG":0} for t in st.session_state.times}
    for j in st.session_state.jogos:
        if j['ga'] is not None and j['gb'] is not None:
            a, b, ga, gb = j['a'], j['b'], j['ga'], j['gb']
            stats[a]["J"]+=1; stats[b]["J"]+=1; stats[a]["GP"]+=ga; stats[a]["GC"]+=gb; stats[b]["GP"]+=gb; stats[b]["GC"]+=ga
            if ga > gb: stats[a]["P"]+=3; stats[a]["V"]+=1; stats[b]["D"]+=1
            elif gb > ga: stats[b]["P"]+=3; stats[b]["V"]+=1; stats[a]["D"]+=1
            else: stats[a]["P"]+=1; stats[b]["P"]+=1; stats[a]["E"]+=1; stats[b]["E"]+=1
            stats[a]["SG"] = stats[a]["GP"] - stats[a]["GC"]
            stats[b]["SG"] = stats[b]["GP"] - stats[b]["GC"]
    df_c = pd.DataFrame.from_dict(stats, orient='index').sort_values(["P", "V", "SG"], ascending=False)
    st.table(df_c)

# --- 4. ADMIN ---
elif menu == "Painel Admin":
    if sou_admin:
        st.subheader("Configurar Torneio")
        t_list = st.text_area("Times (um por linha)")
        if st.button("RESETAR E CRIAR"):
            ts = [t.strip() for t in t_list.split("\n") if t.strip()]
            if len(ts) >= 2:
                combs = list(itertools.combinations(ts, 2))
                random.shuffle(combs)
                novos = [{"a": c[0], "b": c[1], "ga": None, "gb": None, "finalizado": False, "apostas_abertas": True, "apostas": []} for c in combs]
                salvar_tudo(novos); st.session_state.jogos = novos; st.session_state.times = ts; st.rerun()
    else: st.error("Restrito")
