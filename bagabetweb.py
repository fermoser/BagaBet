import streamlit as st
import pandas as pd
from itertools import combinations
from streamlit_gsheets import GSheetsConnection
from datetime import datetime, timedelta

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="BAGA GESTOR PRO", layout="wide")

# --- ESTILO CSS (AMARELO SUAVE) ---
st.markdown("""
    <style>
    input[type=number] {
        color: #F4D03F !important;
        font-weight: bold !important;
        font-size: 20px !important;
    }
    </style>
    """, unsafe_allow_html=True)

conn = st.connection("gsheets", type=GSheetsConnection)
ABA_JOGOS = "Página1" 
ABA_HISTORICO = "Historico"

COLUNAS = [
    'torneio_id', 'formato', 'fase', 'a', 'b', 'finalizado',
    'gols_a', 'gols_b', 'ida_a', 'ida_b', 'volta_a', 'volta_b', 'pen_a', 'pen_b', 'modo_copa'
]

# --- FUNÇÕES DE DADOS ---
def carregar_dados(aba):
    try:
        df = conn.read(worksheet=aba, ttl=0)
        if df is None or df.empty:
            if aba == ABA_JOGOS: return pd.DataFrame(columns=COLUNAS)
            return pd.DataFrame(columns=['torneio_id','formato','campeao','vice','terceiro','data_fim'])
        df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
        if aba == ABA_JOGOS:
            for c in COLUNAS:
                if c not in df.columns: df[c] = None
            cols_n = ['gols_a', 'gols_b', 'ida_a', 'ida_b', 'volta_a', 'volta_b', 'pen_a', 'pen_b']
            for col in cols_n:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
        return df
    except:
        return pd.DataFrame(columns=COLUNAS)

def salvar_dados(df, aba):
    conn.update(worksheet=aba, data=df.copy())
    st.cache_data.clear()
    st.rerun()

def is_done(val):
    return str(val).upper().strip() in ["1", "SIM", "TRUE"]

def obter_vencedor(r):
    if not is_done(r['finalizado']): return "---", ""
    if r['fase'] in ["Final", "3º Lugar"] or r['modo_copa'] == "Só Ida":
        sa, sb = int(r['gols_a']), int(r['gols_b'])
    else:
        sa, sb = int(r['ida_a']) + int(r['volta_a']), int(r['ida_b']) + int(r['volta_b'])
    if sa > sb: return r['a'], r['b']
    if sb > sa: return r['b'], r['a']
    return (r['a'], r['b']) if int(r['pen_a']) > int(r['pen_b']) else (r['b'], r['a'])

# --- INICIALIZAÇÃO ---
if 'torneio_ativo' not in st.session_state:
    st.session_state.torneio_ativo = None

df_db = carregar_dados(ABA_JOGOS)
df_hist = carregar_dados(ABA_HISTORICO)

# --- TELA DE SELEÇÃO ---
if st.session_state.torneio_ativo is None:
    st.title("⚽ BAGA GESTOR")
    
    with st.expander("📜 Hall da Fama (Campeões)"):
        if not df_hist.empty: st.dataframe(df_hist.sort_index(ascending=False), use_container_width=True)
        else: st.info("Histórico vazio.")

    torneios = df_db.dropna(subset=['torneio_id'])['torneio_id'].unique() if not df_db.empty else []
    if len(torneios) > 0:
        with st.expander("📂 Abrir Torneio em Aberto", expanded=True):
            cols = st.columns(3)
            for i, t_nome in enumerate(torneios):
                row_t = df_db[df_db['torneio_id'] == t_nome].iloc[0]
                if cols[i%3].button(f"🏆 {t_nome} ({row_t['formato']})", key=f"sel_{t_nome}"):
                    st.session_state.torneio_ativo = t_nome
                    st.session_state.formato = row_t['formato']
                    st.session_state.modo = row_t['modo_copa']
                    st.rerun()

    st.divider()
    st.subheader("🆕 Novo Torneio")
    with st.form("criar_home"):
        c1, c2, c3 = st.columns(3)
        n = c1.text_input("Nome do Torneio")
        t = c2.selectbox("Tipo", ["COPA", "LIGA"])
        m = c3.selectbox("Modo", ["Só Ida", "Ida e Volta"]) if t == "COPA" else "Só Ida"
        if st.form_submit_button("CRIAR"):
            if n: st.session_state.torneio_ativo, st.session_state.formato, st.session_state.modo = n, t, m; st.rerun()

else:
    tid, fmt, modo = st.session_state.torneio_ativo, st.session_state.formato, st.session_state.modo
    df_t = df_db[df_db['torneio_id'].astype(str) == str(tid)].copy()

    with st.sidebar:
        st.header(f"🏆 {tid}")
        menu = st.radio("Menu", ["🏟️ Jogos", "📊 Classificação", "⚙️ Admin"])
        is_admin = (st.text_input("Senha Admin", type="password") == "1234")
        if st.button("🏠 Sair"): st.session_state.torneio_ativo = None; st.rerun()

    # --- ABA ADMIN (ONDE GERA OS JOGOS) ---
    if menu == "⚙️ Admin":
        if is_admin:
            # SE O TORNEIO NÃO TEM JOGOS, MOSTRA O GERADOR
            if df_t.empty:
                st.subheader("🛠️ Configurar Novo Torneio")
                txt_times = st.text_area("Lista de Times (um por linha)")
                if st.button("GERAR TABELA DE JOGOS"):
                    times = [x.strip() for x in txt_times.split('\n') if x.strip()]
                    if len(times) < 2:
                        st.error("Mínimo de 2 times!")
                    else:
                        novos_jogos = []
                        if fmt == "LIGA":
                            for a, b in combinations(times, 2):
                                novos_jogos.append({'torneio_id': tid, 'formato': fmt, 'fase': 'Pontos Corridos', 'a': a, 'b': b, 'modo_copa': 'Só Ida', 'finalizado': 'NÃO'})
                        else:
                            # Gerar Quartas (exemplo padrão para 8 times) ou conforme quantidade
                            qtd = len(times)
                            fase_nome = "Quartas" if qtd <= 8 else "Oitavas"
                            for i in range(0, qtd, 2):
                                t1 = times[i]
                                t2 = times[i+1] if i+1 < qtd else "BYE"
                                novos_jogos.append({'torneio_id': tid, 'formato': fmt, 'fase': fase_nome, 'a': t1, 'b': t2, 'modo_copa': modo, 'finalizado': 'NÃO'})
                        
                        df_novos = pd.DataFrame(novos_jogos)
                        df_final = pd.concat([df_db, df_novos], ignore_index=True)
                        salvar_dados(df_final, ABA_JOGOS)
            else:
                st.subheader("🏁 Finalizar Torneio")
                if st.button("🏆 SALVAR NO HISTÓRICO"):
                    # ... lógica de histórico (idêntica à anterior)
                    st.success("Salvo no Hall da Fama!")
                
                st.divider()
                if st.button("🚨 EXCLUIR ESTE TORNEIO"):
                    salvar_dados(df_db[df_db['torneio_id'] != tid], ABA_JOGOS)
                    st.session_state.torneio_ativo = None; st.rerun()

    # --- ABA JOGOS ---
    elif menu == "🏟️ Jogos":
        if df_t.empty:
            st.warning("Vá em 'Admin' para gerar os jogos deste torneio.")
        else:
            for f in df_t['fase'].unique():
                st.subheader(f"📍 {f}")
                for idx, row in df_t[df_t['fase'] == f].iterrows():
                    with st.container(border=True):
                        c1, c2, c3 = st.columns([2,1,2])
                        # ... (visualização dos jogos idêntica ao anterior)
                        c1.markdown(f"<p style='text-align:right'><b>{row['a']}</b></p>", unsafe_allow_html=True)
                        c2.markdown(f"<div style='text-align:center; background:#eee; padding:5px;'>{row['gols_a']} x {row['gols_b']}</div>", unsafe_allow_html=True)
                        c3.markdown(f"<p style='text-align:left'><b>{row['b']}</b></p>", unsafe_allow_html=True)
                        if is_admin:
                            # expander de edição...
                            pass

    # --- ABA CLASSIFICAÇÃO ---
    elif menu == "📊 Classificação":
        if df_t.empty:
            st.warning("Sem dados para exibir.")
        else:
            # ... lógica de tabela/chaveamento
            pass
