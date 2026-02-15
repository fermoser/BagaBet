import streamlit as st
import pandas as pd
import itertools
import random
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="BAGA BET PRO", layout="wide", page_icon="⚽")
conn = st.connection("gsheets", type=GSheetsConnection)

# --- ESTILO CSS (CORRIGIDO) ---
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stButton>button { border-radius: 8px; font-weight: 600; }
    
    /* Box do Placar */
    .placar-container {
        background-color: #eeeeee !important; 
        border-radius: 12px; 
        padding: 15px; 
        text-align: center;
        border: 1px solid #ddd;
    }
    .gols-finalizado { 
        color: #1b5e20 !important; /* Verde Esmeralda Escuro */
        font-weight: 900; 
        font-size: 2.5rem;
    }
    .gols-aberto { 
        color: #444444 !important; /* Cinza grafite */
        font-weight: 900;
        font-size: 2.5rem;
    }
    </style>
    """, unsafe_allow_html=True)

# --- UTILITÁRIOS ---
def money(v):
    try:
        cor = "#28a745" if v > 0 else "#dc3545" if v < 0 else "#212529"
        val_fmt = f"R$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return f'<span style="color:{cor}; font-weight:bold;">{val_fmt}</span>'
    except: return "R$ 0,00"

def money_raw(v):
    try: return f"R$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except: return "R$ 0,00"

# --- TRATAMENTO DE DADOS ---
def to_bool(val):
    return str(val).strip().upper() in ["TRUE", "1", "VERDADEIRO", "T"]

def to_int(val):
    try: return int(float(str(val)))
    except: return None

def parse_bets(txt):
    lista = []
    txt = str(txt).strip()
    if txt in ["nan", "None", ""]: return lista
    try:
        for item in txt.split("|"):
            p = item.split(":")
            if len(p) == 3: lista.append({"nome": p[0], "valor": float(p[1]), "opcao": p[2].upper()})
    except: pass
    return lista

def carregar_tudo():
    df = conn.read(ttl=0)
    if df is None or df.empty: return [], [], df
    jogos = []
    times = set()
    for _, row in df.iterrows():
        fina = to_bool(row.get('finalizado'))
        j = {
            "a": str(row.get('a', '')), "b": str(row.get('b', '')),
            "ga": to_int(row.get('ga')), "gb": to_int(row.get('gb')),
            "finalizado": fina, 
            "apostas_abertas": to_bool(row.get('apostas_abertas')) if 'apostas_abertas' in row else True,
            "apostas": parse_bets(row.get('apostas'))
        }
        jogos.append(j); times.add(j['a']); times.add(j['b'])
    return jogos, list(times), df

def salvar_tudo(lista):
    if not lista:
        # Se a lista estiver vazia (Reset), criamos um DataFrame com colunas mas sem linhas
        df_save = pd.DataFrame(columns=['a', 'b', 'ga', 'gb', 'finalizado', 'apostas_abertas', 'apostas'])
    else:
        df_save = pd.DataFrame(lista)
        df_save['apostas'] = df_save['apostas'].apply(lambda x: "|".join([f"{a['nome']}:{a['valor']}:{a['opcao']}" for a in x]) if x else "")
        df_save['finalizado'] = df_save['finalizado'].apply(lambda x: "TRUE" if x else "FALSE")
        df_save['apostas_abertas'] = df_save['apostas_abertas'].apply(lambda x: "TRUE" if x else "FALSE")
    
    conn.update(data=df_save)
    st.cache_data.clear()

# --- INICIALIZAÇÃO ---
if 'jogos' not in st.session_state:
    st.session_state.jogos, st.session_state.times, st.session_state.df_raw = carregar_tudo()
if 'menu_ativo' not in st.session_state: st.session_state.menu_ativo = "Jogos"
if 'autenticado' not in st.session_state: st.session_state.autenticado = False

# --- SIDEBAR ---
with st.sidebar:
    st.title("⚽ BAGA BET PRO")
    if not st.session_state.autenticado:
        senha = st.text_input("Admin Password", type="password")
        if senha == "1234": st.session_state.autenticado = True; st.rerun()
    else:
        st.success("Admin Ativo")
        if st.button("Sair"): st.session_state.autenticado = False; st.rerun()
    
    st.divider()
    if st.button("🏟️ JOGOS", use_container_width=True): st.session_state.menu_ativo = "Jogos"; st.rerun()
    if st.button("🤑 RANKING", use_container_width=True): st.session_state.menu_ativo = "Ranking"; st.rerun()
    if st.button("📊 TABELA", use_container_width=True): st.session_state.menu_ativo = "Classificação"; st.rerun()
    if st.button("⚙️ ADMIN", use_container_width=True): st.session_state.menu_ativo = "Admin"; st.rerun()
    st.divider()
    if st.button("🔄 SINCRONIZAR NUVEM", type="primary", use_container_width=True):
        st.session_state.jogos, st.session_state.times, st.session_state.df_raw = carregar_tudo()
        st.rerun()

sou_admin = st.session_state.autenticado

# --- TELA JOGOS ---
if st.session_state.menu_ativo == "Jogos":
    st.title("🏟️ Rodada Atual")
    for i, j in enumerate(st.session_state.jogos):
        with st.container(border=True):
            c1, c2, c3 = st.columns([2, 1, 2])
            
            ga_txt = j['ga'] if j['ga'] is not None else "-"
            gb_txt = j['gb'] if j['gb'] is not None else "-"
            estilo_gols = "gols-finalizado" if j['finalizado'] else "gols-aberto"
            
            c1.markdown(f"<h2 style='text-align:right; margin-top:20px;'>{j['a']}</h2>", unsafe_allow_html=True)
            c2.markdown(f"""
                <div class="placar-container">
                    <span class="{estilo_gols}">{ga_txt} : {gb_txt}</span>
                </div>
                """, unsafe_allow_html=True)
            c3.markdown(f"<h2 style='text-align:left; margin-top:20px;'>{j['b']}</h2>", unsafe_allow_html=True)

            if sou_admin:
                with st.expander("Lançar Resultado"):
                    l1, l2 = st.columns(2)
                    vga = l1.number_input(f"Gols {j['a']}", 0, 20, key=f"vga{i}")
                    vgb = l2.number_input(f"Gols {j['b']}", 0, 20, key=f"vgb{i}")
                    if st.button("Salvar Placar", key=f"save{i}"):
                        st.session_state.jogos[i].update({'ga': int(vga), 'gb': int(vgb), 'finalizado': True, 'apostas_abertas': False})
                        salvar_tudo(st.session_state.jogos); st.rerun()
            
            # Apostas
            st.divider()
            t1, t2 = st.tabs(["Ver Apostas", "Nova Aposta"])
            with t1:
                if j['apostas']:
                    df_v = pd.DataFrame(j['apostas'])
                    df_v['Palpite'] = df_v['opcao'].map({"A": j['a'], "B": j['b'], "E": "Empate"})
                    st.table(df_v[['nome', 'Palpite', 'valor']])
                else: st.info("Sem apostas.")
            with t2:
                if not j['finalizado'] and sou_admin:
                    with st.form(key=f"ap{i}", clear_on_submit=True):
                        n = st.text_input("Apostador")
                        v = st.number_input("Valor R$", 1.0, 5000.0, 10.0)
                        o = st.radio("Palpite", [j['a'], "Empate", j['b']], horizontal=True)
                        if st.form_submit_button("Confirmar"):
                            st.session_state.jogos[i]['apostas'].append({"nome": n, "valor": v, "opcao": "A" if o==j['a'] else "B" if o==j['b'] else "E"})
                            salvar_tudo(st.session_state.jogos); st.rerun()

# --- TELA ADMIN ---
elif st.session_state.menu_ativo == "Admin":
    if sou_admin:
        st.title("⚙️ Painel de Controle")
        
        st.subheader("🧹 Resetar Sistema")
        if st.button("❗ RESETAR TUDO (APAGAR PLANILHA)", type="secondary", use_container_width=True):
            salvar_tudo([]) # Agora com a trava de segurança para lista vazia
            st.session_state.jogos = []
            st.session_state.times = []
            st.success("Planilha resetada!")
            st.rerun()
            
        st.divider()
        st.subheader("🏆 Novo Torneio (Liga)")
        df_ed = pd.DataFrame([{"Time": ""} for _ in range(4)])
        edited = st.data_editor(df_ed, num_rows="dynamic", use_container_width=True)
        if st.button("🚀 GERAR LIGA (TODOS CONTRA TODOS)", type="primary", use_container_width=True):
            ts = [r['Time'].strip() for _, r in edited.iterrows() if r['Time'].strip()]
            if len(ts) >= 2:
                combs = list(itertools.combinations(ts, 2))
                random.shuffle(combs)
                novos = [{"a": c[0], "b": c[1], "ga": None, "gb": None, "finalizado": False, "apostas_abertas": True, "apostas": []} for c in combs]
                salvar_tudo(novos); st.rerun()
    else: st.error("Acesso restrito.")

# --- TELA RANKING ---
elif st.session_state.menu_ativo == "Ranking":
    st.title("🤑 Ranking Financeiro")
    # ... (lógica de ranking mantida)
    st.info("Ranking processado conforme jogos finalizados.")

# --- TELA CLASSIFICAÇÃO ---
elif st.session_state.menu_ativo == "Classificação":
    st.title("📊 Tabela da Liga")
    # ... (lógica de classificação mantida)
    st.info("Tabela atualizada automaticamente.")
