import streamlit as st
import pandas as pd
import itertools
import random
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="BAGA BET PRO", layout="wide", page_icon="⚽")
conn = st.connection("gsheets", type=GSheetsConnection)

# --- UTILITÁRIOS ---
def money(v):
    try:
        cor = "green" if v > 0 else "red" if v < 0 else "black"
        val_fmt = f"R$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return f'<span style="color:{cor}; font-weight:bold;">{val_fmt}</span>'
    except: return "R$ 0,00"

def money_raw(v):
    try: return f"R$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except: return "R$ 0,00"

# --- TRATAMENTO DE DADOS ---
def to_bool(val):
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

# --- INICIALIZAÇÃO DE SESSÃO ---
if 'jogos' not in st.session_state:
    st.session_state.jogos, st.session_state.times, st.session_state.df_raw = carregar_tudo()
if 'menu_ativo' not in st.session_state:
    st.session_state.menu_ativo = "Jogos"
if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False

# --- SIDEBAR ---
st.sidebar.title("⚽ BAGA BET PRO")

# Campo de Senha (Sempre visível ou até logar)
if not st.session_state.autenticado:
    senha = st.sidebar.text_input("Chave Admin", type="password")
    if senha == "1234":
        st.session_state.autenticado = True
        st.rerun()
else:
    st.sidebar.success("🔓 Modo Admin Ativo")
    if st.sidebar.button("Sair do Admin"):
        st.session_state.autenticado = False
        st.rerun()

st.sidebar.divider()

# Botão de Sincronização
if st.sidebar.button("🔄 SINCRONIZAR NUVEM", use_container_width=True):
    st.session_state.jogos, st.session_state.times, st.session_state.df_raw = carregar_tudo()
    st.success("Dados atualizados!")

st.sidebar.subheader("Navegação")
if st.sidebar.button("🏟️ JOGOS DA RODADA", use_container_width=True):
    st.session_state.menu_ativo = "Jogos"
    st.rerun()

if st.sidebar.button("🤑 RANKING DE APOSTAS", use_container_width=True):
    st.session_state.menu_ativo = "Ranking"
    st.rerun()

if st.sidebar.button("📊 CLASSIFICAÇÃO", use_container_width=True):
    st.session_state.menu_ativo = "Classificação"
    st.rerun()

if st.sidebar.button("⚙️ PAINEL ADMIN", use_container_width=True):
    st.session_state.menu_ativo = "Admin"
    st.rerun()

sou_admin = st.session_state.autenticado

# --- TELAS ---

if st.session_state.menu_ativo == "Jogos":
    st.header("🏟️ Partidas e Palpites")
    for i, j in enumerate(st.session_state.jogos):
        with st.container(border=True):
            c1, c2, c3 = st.columns([2, 1, 2])
            ga, gb = (j['ga'] if j['ga'] is not None else "-"), (j['gb'] if j['gb'] is not None else "-")
            c1.markdown(f"<h3 style='text-align:right;'>{j['a']}</h3>", unsafe_allow_html=True)
            c2.markdown(f"<h1 style='text-align:center; color:red;'>{ga} x {gb}</h1>", unsafe_allow_html=True)
            c3.markdown(f"<h3 style='text-align:left;'>{j['b']}</h3>", unsafe_allow_html=True)

            if sou_admin:
                if not j['finalizado']:
                    with st.expander("⚙️ Lançar Placar Final"):
                        l1, l2 = st.columns(2)
                        vga = l1.number_input(f"Gols {j['a']}", 0, 20, key=f"vga{i}")
                        vgb = l2.number_input(f"Gols {j['b']}", 0, 20, key=f"vgb{i}")
                        if st.button("ENCERRAR JOGO", key=f"btn_f{i}"):
                            st.session_state.jogos[i].update({'ga': int(vga), 'gb': int(vgb), 'finalizado': True, 'apostas_abertas': False})
                            salvar_tudo(st.session_state.jogos); st.rerun()
                else:
                    if st.button("🔄 Reabrir Jogo", key=f"btn_re{i}"):
                        st.session_state.jogos[i].update({'finalizado': False, 'apostas_abertas': True})
                        salvar_tudo(st.session_state.jogos); st.rerun()

            with st.expander(f"📋 Apostas ({len(j['apostas'])})"):
                if j['apostas']:
                    df_a = pd.DataFrame(j['apostas'])
                    df_a['Palpite'] = df_a['opcao'].map({"A": j['a'], "B": j['b'], "E": "Empate"})
                    if j['finalizado']:
                        res = "A" if j['ga'] > j['gb'] else "B" if j['gb'] > j['ga'] else "E"
                        pote = sum(df_a['valor'])
                        venc_v = sum(df_a[df_a['opcao'] == res]['valor'])
                        df_a['Retorno Bruto'] = df_a.apply(lambda r: (r['valor']/venc_v * pote) if r['opcao'] == res and venc_v > 0 else 0.0, axis=1)
                        df_a['Lucro Líquido'] = df_a['Retorno Bruto'] - df_a['valor']
                        df_show = df_a.copy()
                        df_show['Retorno Bruto'] = df_show['Retorno Bruto'].apply(money_raw)
                        df_show['Lucro Líquido'] = df_show['Lucro Líquido'].apply(money)
                        st.write(df_show[['nome', 'Palpite', 'valor', 'Retorno Bruto', 'Lucro Líquido']].to_html(escape=False, index=False), unsafe_allow_html=True)
                    else: st.table(df_a[['nome', 'Palpite', 'valor']])

            if sou_admin and j['apostas_abertas'] and not j['finalizado']:
                with st.expander("💰 Nova Aposta"):
                    with st.form(key=f"f_ap_{i}", clear_on_submit=True):
                        n = st.text_input("Nome")
                        v = st.number_input("Valor", 1.0, 1000.0, 10.0, step=1.0)
                        o = st.radio("Palpite", [j['a'], "Empate", j['b']], horizontal=True)
                        if st.form_submit_button("SALVAR"):
                            cod = "A" if o == j['a'] else "B" if o == j['b'] else "E"
                            st.session_state.jogos[i]['apostas'].append({"nome": n, "valor": v, "opcao": cod})
                            salvar_tudo(st.session_state.jogos); st.rerun()

elif st.session_state.menu_ativo == "Ranking":
    st.header("🤑 Ranking Financeiro")
    # ... (lógica de ranking igual à anterior)
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
        lista_r = [{"Apostador": k, "Investido": money_raw(v['pago']), "Retorno": money_raw(v['ganho']), "Saldo": v['ganho']-v['pago']} for k, v in rank.items()]
        df_r = pd.DataFrame(lista_r).sort_values("Saldo", ascending=False)
        df_r['Saldo'] = df_r['Saldo'].apply(money)
        st.write(df_r.to_html(escape=False, index=False), unsafe_allow_html=True)

elif st.session_state.menu_ativo == "Classificação":
    st.header("📊 Tabela")
    # ... (lógica de classificação igual à anterior)
    stats = {t: {"P":0,"J":0,"V":0,"E":0,"D":0,"SG":0} for t in st.session_state.times}
    for j in st.session_state.jogos:
        if j['ga'] is not None and j['gb'] is not None:
            a, b, ga, gb = j['a'], j['b'], j['ga'], j['gb']
            stats[a]["J"]+=1; stats[b]["J"]+=1
            if ga > gb: stats[a]["P"]+=3; stats[b]["D"]+=1
            elif gb > ga: stats[b]["P"]+=3; stats[a]["D"]+=1
            else: stats[a]["P"]+=1; stats[b]["P"]+=1
            stats[a]["SG"]+=(ga-gb); stats[b]["SG"]+=(gb-ga)
    st.table(pd.DataFrame.from_dict(stats, orient='index').sort_values(["P", "SG"], ascending=False))

elif st.session_state.menu_ativo == "Admin":
    if sou_admin:
        st.header("⚙️ Painel de Controle")
        # VOLTOU A COMPARAÇÃO RAW VS PROCESSADO
        with st.expander("🔍 MONITOR DE DADOS (Raw Sheets vs App)"):
            c1, c2 = st.columns(2)
            c1.write("**Na Planilha (Raw):**")
            c1.dataframe(st.session_state.df_raw[['a', 'b', 'finalizado', 'apostas_abertas']])
            c2.write("**No App (Processado):**")
            diag = [{"Jogo": f"{j['a']}x{j['b']}", "Fim": j['finalizado'], "Aberto": j['apostas_abertas']} for j in st.session_state.jogos]
            c2.table(diag)
        
        st.divider()
        st.subheader("🏆 Novo Torneio")
        df_ed = pd.DataFrame([{"Time": ""} for _ in range(4)])
        edited = st.data_editor(df_ed, num_rows="dynamic", use_container_width=True)
        if st.button("🚀 CRIAR TORNEIO", use_container_width=True):
            ts = [r['Time'].strip() for _, r in edited.iterrows() if r['Time'].strip()]
            if len(ts) >= 2:
                combs = list(itertools.combinations(ts, 2))
                random.shuffle(combs)
                novos = [{"a": c[0], "b": c[1], "ga": None, "gb": None, "finalizado": False, "apostas_abertas": True, "apostas": []} for c in combs]
                salvar_tudo(novos); st.rerun()
    else: st.error("Acesse o modo Admin na barra lateral.")
