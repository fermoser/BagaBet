import streamlit as st
import pandas as pd
import itertools
import random
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="BAGA BET PRO", layout="wide", page_icon="⚽")
conn = st.connection("gsheets", type=GSheetsConnection)

# --- ESTILO CSS CUSTOMIZADO ---
st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stButton>button { border-radius: 8px; font-weight: 600; }
    .stExpander { border: none !important; box-shadow: 0px 2px 6px rgba(0,0,0,0.05); border-radius: 12px !important; margin-bottom: 10px; }
    div[data-testid="stMetricValue"] { font-size: 1.8rem; color: #1f77b4; }
    h1, h2, h3 { color: #0e1117; font-family: 'Inter', sans-serif; }
    .stTable { border-radius: 10px; overflow: hidden; }
    </style>
    """, unsafe_allow_html=True)

# --- UTILITÁRIOS ---
def money(v):
    try:
        cor = "#28a745" if v > 0 else "#dc3545" if v < 0 else "#212529"
        val_fmt = f"R$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return f'<span style="color:{cor}; font-weight:bold; font-family:monospace;">{val_fmt}</span>'
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

# --- INICIALIZAÇÃO ---
if 'jogos' not in st.session_state:
    st.session_state.jogos, st.session_state.times, st.session_state.df_raw = carregar_tudo()
if 'menu_ativo' not in st.session_state:
    st.session_state.menu_ativo = "Jogos"
if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False

# --- SIDEBAR ---
with st.sidebar:
    st.markdown("<h1 style='text-align: center;'>⚽ BAGA BET</h1>", unsafe_allow_html=True)
    
    if not st.session_state.autenticado:
        senha = st.text_input("🔑 Acesso Admin", type="password")
        if senha == "1234":
            st.session_state.autenticado = True
            st.rerun()
    else:
        st.success("🔓 Admin Autenticado")
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.autenticado = False
            st.rerun()

    st.divider()
    if st.button("🔄 ATUALIZAR NUVEM", type="primary", use_container_width=True):
        st.session_state.jogos, st.session_state.times, st.session_state.df_raw = carregar_tudo()
        st.toast("Dados sincronizados!")

    st.markdown("### Navegação")
    if st.button("🏟️ Jogos da Rodada", use_container_width=True): st.session_state.menu_ativo = "Jogos"; st.rerun()
    if st.button("🤑 Ranking Geral", use_container_width=True): st.session_state.menu_ativo = "Ranking"; st.rerun()
    if st.button("📊 Tabela da Liga", use_container_width=True): st.session_state.menu_ativo = "Classificação"; st.rerun()
    if st.button("⚙️ Configurações", use_container_width=True): st.session_state.menu_ativo = "Admin"; st.rerun()

sou_admin = st.session_state.autenticado

# --- TELAS ---

# 1. JOGOS
if st.session_state.menu_ativo == "Jogos":
    st.title("🏟️ Jogos e Palpites")
    for i, j in enumerate(st.session_state.jogos):
        with st.container(border=True):
            # Header do Jogo
            c1, c2, c3 = st.columns([2, 1, 2])
            ga, gb = (j['ga'] if j['ga'] is not None else "-"), (j['gb'] if j['gb'] is not None else "-")
            c1.markdown(f"<h2 style='text-align:right;'>{j['a']}</h2>", unsafe_allow_html=True)
            c2.markdown(f"<div style='text-align:center; background:#eee; border-radius:10px; padding:10px;'><h1 style='margin:0; color:#e63946;'>{ga} : {gb}</h1></div>", unsafe_allow_html=True)
            c3.markdown(f"<h2 style='text-align:left;'>{j['b']}</h2>", unsafe_allow_html=True)

            # Ações Admin
            if sou_admin:
                if not j['finalizado']:
                    with st.expander("📝 Lançar Resultado"):
                        l1, l2 = st.columns(2)
                        vga = l1.number_input(f"Gols {j['a']}", 0, 20, key=f"vga{i}")
                        vgb = l2.number_input(f"Gols {j['b']}", 0, 20, key=f"vgb{i}")
                        if st.button("FINALIZAR PARTIDA", key=f"f{i}", type="primary"):
                            st.session_state.jogos[i].update({'ga': int(vga), 'gb': int(vgb), 'finalizado': True, 'apostas_abertas': False})
                            salvar_tudo(st.session_state.jogos); st.rerun()
                else:
                    st.button("🔄 Reabrir Jogo", key=f"r{i}", on_click=lambda idx=i: [st.session_state.jogos[idx].update({'finalizado': False, 'apostas_abertas': True}), salvar_tudo(st.session_state.jogos)])

            # Apostas
            tab_ver, tab_add = st.tabs(["📋 Ver Apostas", "➕ Nova Aposta"])
            with tab_ver:
                if j['apostas']:
                    df_a = pd.DataFrame(j['apostas'])
                    df_a['Palpite'] = df_a['opcao'].map({"A": j['a'], "B": j['b'], "E": "Empate"})
                    if j['finalizado']:
                        res = "A" if j['ga'] > j['gb'] else "B" if j['gb'] > j['ga'] else "E"
                        pote = sum(df_a['valor'])
                        venc_v = sum(df_a[df_a['opcao'] == res]['valor'])
                        df_a['Retorno'] = df_a.apply(lambda r: (r['valor']/venc_v * pote) if r['opcao'] == res and venc_v > 0 else 0.0, axis=1)
                        df_a['Lucro'] = df_a['Retorno'] - df_a['valor']
                        df_show = df_a.copy()
                        df_show['Retorno'] = df_show['Retorno'].apply(money_raw)
                        df_show['Lucro'] = df_show['Lucro'].apply(money)
                        st.write(df_show[['nome', 'Palpite', 'valor', 'Retorno', 'Lucro']].to_html(escape=False, index=False), unsafe_allow_html=True)
                    else: st.dataframe(df_a[['nome', 'Palpite', 'valor']], use_container_width=True)
                else: st.info("Nenhuma aposta registrada.")

            with tab_add:
                if sou_admin and j['apostas_abertas'] and not j['finalizado']:
                    with st.form(key=f"f_ap_{i}", clear_on_submit=True):
                        n = st.text_input("Nome do Apostador")
                        v = st.number_input("Valor R$", 1.0, 5000.0, 10.0, step=1.0)
                        o = st.radio("Vencedor", [j['a'], "Empate", j['b']], horizontal=True)
                        if st.form_submit_button("REGISTRAR APOSTA", use_container_width=True):
                            cod = "A" if o == j['a'] else "B" if o == j['b'] else "E"
                            st.session_state.jogos[i]['apostas'].append({"nome": n, "valor": v, "opcao": cod})
                            salvar_tudo(st.session_state.jogos); st.rerun()
                else: st.warning("Apostas fechadas para este jogo.")

# 2. RANKING
elif st.session_state.menu_ativo == "Ranking":
    st.title("🤑 Ranking dos Apostadores")
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
        lista_r = [{"Apostador": k, "Investido": v['pago'], "Retorno": v['ganho'], "Saldo": v['ganho']-v['pago']} for k, v in rank.items()]
        df_r = pd.DataFrame(lista_r).sort_values("Saldo", ascending=False)
        
        # Métricas de destaque
        m1, m2, m3 = st.columns(3)
        m1.metric("Líder de Lucro", df_r.iloc[0]['Apostador'], money_raw(df_r.iloc[0]['Saldo']))
        m2.metric("Total Movimentado", money_raw(df_r['Investido'].sum()))
        m3.metric("Total Apostadores", len(df_r))
        
        st.divider()
        df_r['Investido'] = df_r['Investido'].apply(money_raw)
        df_r['Retorno'] = df_r['Retorno'].apply(money_raw)
        df_r['Saldo'] = df_r['Saldo'].apply(money)
        st.write(df_r.to_html(escape=False, index=False), unsafe_allow_html=True)
    else: st.info("O ranking aparecerá após a finalização dos jogos.")

# 3. CLASSIFICAÇÃO
elif st.session_state.menu_ativo == "Classificação":
    st.title("📊 Classificação do Torneio")
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
    st.dataframe(df_c.style.background_gradient(subset=['P', 'SG'], cmap='Greens'), use_container_width=True)

# 4. ADMIN
elif st.session_state.menu_ativo == "Admin":
    if sou_admin:
        st.title("⚙️ Configurações Admin")
        with st.expander("🔍 Monitor de Dados (Sincronização)"):
            c1, c2 = st.columns(2)
            c1.markdown("**Dados Raw (Sheets)**")
            c1.dataframe(st.session_state.df_raw[['a', 'b', 'finalizado', 'apostas_abertas']], height=200)
            c2.markdown("**Dados App (Processados)**")
            diag = [{"Jogo": f"{j['a']}x{j['b']}", "Fim": j['finalizado'], "Aberto": j['apostas_abertas']} for j in st.session_state.jogos]
            c2.table(diag)

        st.divider()
        st.subheader("🏆 Gerenciar Torneio")
        st.info("Adicione os times na tabela abaixo para gerar os confrontos.")
        df_ed = pd.DataFrame([{"Time": ""} for _ in range(4)])
        edited = st.data_editor(df_ed, num_rows="dynamic", use_container_width=True, key="ed_final")
        
        if st.button("🚀 REINICIAR TUDO E CRIAR JOGOS", type="primary", use_container_width=True):
            ts = [r['Time'].strip() for _, r in edited.iterrows() if r['Time'].strip()]
            if len(ts) >= 2:
                combs = list(itertools.combinations(ts, 2))
                random.shuffle(combs)
                novos = [{"a": c[0], "b": c[1], "ga": None, "gb": None, "finalizado": False, "apostas_abertas": True, "apostas": []} for c in combs]
                salvar_tudo(novos); st.session_state.jogos = novos; st.session_state.times = ts; st.rerun()
    else: st.error("Acesso negado.")
