import streamlit as st
import pandas as pd
import random
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="BAGA GESTOR PRO", layout="wide")

# --- ESTILO CSS (MANTIDO) ---
st.markdown("""
    <style>
    input[type=number] { color: #F4D03F !important; font-weight: bold !important; font-size: 20px !important; }
    .stMarkdown div[style*="background:#eee"] { background-color: #333 !important; color: #F4D03F !important; font-weight: bold; border-radius: 5px; }
    [data-testid="stForm"] .stColumn { display: flex; align-items: center; justify-content: center; }
    </style>
    """, unsafe_allow_html=True)

conn = st.connection("gsheets", type=GSheetsConnection)
ABA_JOGOS = "Página1" 
ABA_SUICO = "Suico"
ABA_HISTORICO = "Historico"

# Colunas necessárias para o Suíço não travar
COLS_SUICO = ['torneio_id', 'formato', 'fase', 'rodada', 'a', 'b', 'gols_a', 'gols_b', 'finalizado']

# --- FUNÇÕES DE DADOS ---
def carregar_dados(aba):
    try:
        df = conn.read(worksheet=aba, ttl="0s")
        if df is None or df.empty:
            return pd.DataFrame(columns=COLS_SUICO if aba == ABA_SUICO else [])
        df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
        if aba == ABA_SUICO:
            for col in COLS_SUICO:
                if col not in df.columns: df[col] = None
        return df.dropna(how='all')
    except: 
        return pd.DataFrame(columns=COLS_SUICO if aba == ABA_SUICO else [])

def salvar_dados(df, aba):
    if 'torneio_id' in df.columns:
        df = df.dropna(subset=['torneio_id'])
    conn.update(worksheet=aba, data=df)
    st.cache_data.clear()

def calcular_ranking_suico(df_t):
    times = set(df_t['a'].dropna().unique()) | set(df_t['b'].dropna().unique())
    if "BYE" in times: times.remove("BYE")
    if not times: return None
    stats = {t: {'V':0, 'D':0, 'Jogos': [], 'Buchholz': 0} for t in times}
    for _, r in df_t[df_t['fase'] == 'Suico'].iterrows():
        if str(r.get('finalizado')).upper() in ["SIM", "1", "TRUE"]:
            ga, gb = int(r.get('gols_a', 0)), int(r.get('gols_b', 0))
            v, p = (r['a'], r['b']) if ga > gb else (r['b'], r['a'])
            if v in stats: stats[v]['V'] += 1; stats[v]['Jogos'].append(p)
            if p in stats: stats[p]['D'] += 1; stats[p]['Jogos'].append(v)
    for t in stats:
        stats[t]['Buchholz'] = sum([stats[op]['V'] for op in stats[t]['Jogos'] if op in stats])
        vits = stats[t]['V']
        ders = stats[t]['D']
        stats[t]['Status'] = "✅ Classificado" if vits >= 3 else ("❌ Eliminado" if ders >= 3 else "⏳ Ativo")
    return stats

# --- INICIALIZAÇÃO DE ESTADO ---
if 'torneio_ativo' not in st.session_state: st.session_state.torneio_ativo = None
if 'tipo_ativo' not in st.session_state: st.session_state.tipo_ativo = None 

df_padrao = carregar_dados(ABA_JOGOS)
df_suico = carregar_dados(ABA_SUICO)
df_hist = carregar_dados(ABA_HISTORICO)

# --- TELA INICIAL ---
if st.session_state.torneio_ativo is None:
    st.title("⚽ BAGA GESTOR PRO")
    
    def extrair_ids(df):
        if df.empty or 'torneio_id' not in df.columns: return []
        return [str(x) for x in df['torneio_id'].dropna().unique() if str(x).strip() != ""]

    ids_p = extrair_ids(df_padrao)
    ids_s = extrair_ids(df_suico)
    all_t = sorted(list(set(ids_p + ids_s)))
    
    if all_t:
        st.subheader("📂 Meus Torneios")
        cols = st.columns(3)
        for i, t in enumerate(all_t):
            icone = "⭐ " if t in ids_s else "🏆 "
            if cols[i%3].button(icone + t, key=f"btn_{t}", use_container_width=True):
                st.session_state.torneio_ativo = t
                st.session_state.tipo_ativo = "SUICO" if t in ids_s else "PADRAO"
                st.rerun()

    st.divider()
    c1, c2, c3 = st.columns(3)
    with c1.container(border=True):
        st.subheader("🏆 Liga/Copa")
        n_p = st.text_input("Nome do Torneio")
        m_p = st.selectbox("Formato", ["LIGA", "COPA"])
        if st.button("CRIAR PADRÃO"):
            if n_p:
                salvar_dados(pd.concat([df_padrao, pd.DataFrame([{'torneio_id':n_p, 'formato':m_p, 'fase':'Inscricao'}])]), ABA_JOGOS)
                st.rerun()
    with c3.container(border=True):
        st.subheader("⭐ Modo Suíço")
        n_s = st.text_input("Nome do Suíço")
        if st.button("CRIAR SUÍÇO"):
            if n_s:
                salvar_dados(pd.concat([df_suico, pd.DataFrame([{'torneio_id':n_s, 'formato':'SUICO', 'fase':'Inscricao'}])]), ABA_SUICO)
                st.rerun()

else:
    tid = st.session_state.torneio_ativo
    tipo = st.session_state.tipo_ativo
    
    with st.sidebar:
        st.header(f"📍 {tid}")
        menu = st.radio("Menu", ["🏟️ Jogos", "📊 Classificação", "⚙️ Admin"])
        if st.button("🏠 Sair"): st.session_state.torneio_ativo = None; st.rerun()

    if tipo == "SUICO":
        df_t = df_suico[df_suico['torneio_id'] == tid].copy()
        if menu == "⚙️ Admin":
            senha = st.text_input("Senha Admin", type="password")
            if senha == "123":
                if df_t['a'].isna().all() or (df_t['fase'] == 'Inscricao').all():
                    txt = st.text_area("Lista de Times (um por linha)")
                    if st.button("GERAR PARTIDAS"):
                        times = [x.strip() for x in txt.split('\n') if x.strip()]
                        if len(times) >= 6:
                            random.shuffle(times)
                            jogos = []
                            for i in range(0, len(times), 2):
                                t1, t2 = times[i], (times[i+1] if i+1 < len(times) else "BYE")
                                jogos.append({'torneio_id':tid, 'formato':'SUICO', 'fase':'Suico', 'rodada':1, 'a':t1, 'b':t2, 'gols_a':(1 if t2=='BYE' else 0), 'gols_b':0, 'finalizado':('SIM' if t2=='BYE' else 'NÃO')})
                            df_suico = df_suico[df_suico['torneio_id'] != tid]
                            salvar_dados(pd.concat([df_suico, pd.DataFrame(jogos)]), ABA_SUICO); st.rerun()
                if st.button("🚨 EXCLUIR"):
                    salvar_dados(df_suico[df_suico['torneio_id'] != tid], ABA_SUICO); st.rerun()

        elif menu == "🏟️ Jogos":
            for idx, r in df_t[df_t['fase'] == 'Suico'].iterrows():
                with st.container(border=True):
                    c1, c2, c3 = st.columns([2,1,2])
                    c1.write(r['a'])
                    c2.write(f"{int(r['gols_a'])} x {int(r['gols_b'])}")
                    c3.write(r['b'])
                    with st.expander("Placar"):
                        with st.form(f"f_{idx}"):
                            ga, gb = st.number_input("A",0,99,int(r['gols_a'])), st.number_input("B",0,99,int(r['gols_b']))
                            if st.form_submit_button("Ok"):
                                df_suico.loc[idx, ['gols_a','gols_b','finalizado']] = [ga, gb, "SIM"]
                                salvar_dados(df_suico, ABA_SUICO); st.rerun()

        elif menu == "📊 Classificação":
            rk = calcular_ranking_suico(df_t)
            if rk: st.table(pd.DataFrame(rk).T.sort_values(['V','Buchholz'], ascending=False))

    else:
        # --- AQUI VOCÊ MANTÉM TODA A SUA LÓGICA DE LIGA/COPA ORIGINAL ---
        st.info("Carregando Modo Padrão (Liga/Copa)...")
        # [Insira aqui o código de exibição de jogos/admin da sua versão anterior]
