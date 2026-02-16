import streamlit as st
import pandas as pd
import random
from itertools import combinations
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="BAGA BET PRO", layout="wide", page_icon="⚽")
conn = st.connection("gsheets", type=GSheetsConnection)

# --- ESTILIZAÇÃO ---
st.markdown("""
    <style>
    .placar-box { background-color: #f1f3f5; border: 2px solid #333; border-radius: 12px; padding: 10px; text-align: center; }
    .fase-header { background: #111; color: #fff; padding: 10px; border-radius: 8px; margin: 15px 0; text-align: center; }
    .time-nome { font-weight: bold; font-size: 1.1rem; }
    </style>
    """, unsafe_allow_html=True)

# --- FUNÇÕES DE DADOS ---
def carregar_tudo():
    try:
        st.cache_data.clear()
        df = conn.read(ttl=0)
        # Limpeza básica: remove linhas onde o torneio_id é nulo
        if df is not None and 'torneio_id' in df.columns:
            return df[df['torneio_id'].notna()]
        return pd.DataFrame()
    except:
        return pd.DataFrame()

def carregar_jogos(nome_torneio):
    df = carregar_tudo()
    if df.empty: return []
    # Filtro flexível (ignora espaços)
    df_f = df[df['torneio_id'].astype(str).str.strip() == str(nome_torneio).strip()]
    
    jogos = []
    for _, r in df_f.iterrows():
        ap = []
        raw_ap = str(r.get('apostas', ''))
        if raw_ap not in ["nan", "", "None"]:
            for item in raw_ap.split("|"):
                p = item.split(":")
                if len(p) == 3: ap.append({"nome": p[0], "valor": float(p[1]), "opcao": p[2]})
        
        jogos.append({
            "a": str(r.get('a', 'A')), "b": str(r.get('b', 'B')),
            "ga": r.get('ga'), "gb": r.get('gb'),
            "ga1": r.get('ga1'), "gb1": r.get('gb1'),
            "ga2": r.get('ga2'), "gb2": r.get('gb2'),
            "pen_a": r.get('pen_a', 0), "pen_b": r.get('pen_b', 0),
            "finalizado": str(r.get('finalizado', '')).upper() == "TRUE",
            "fase": str(r.get('fase', 'Rodada')),
            "formato": str(r.get('formato', 'LIGA')),
            "apostas": ap
        })
    return jogos

def salvar_dados(jogos_atuais, nome_torneio, formato):
    df_full = carregar_tudo()
    nome_torneio = str(nome_torneio).strip()
    df_base = df_full[df_full['torneio_id'].astype(str).str.strip() != nome_torneio] if not df_full.empty else pd.DataFrame()
    
    df_novos = pd.DataFrame(jogos_atuais)
    df_novos['torneio_id'] = nome_torneio
    df_novos['formato'] = formato
    df_novos['finalizado'] = df_novos['finalizado'].apply(lambda x: "TRUE" if x else "FALSE")
    df_novos['apostas'] = df_novos['apostas'].apply(lambda x: "|".join([f"{a['nome']}:{a['valor']}:{a['opcao']}" for a in x]) if x else "")
    
    df_final = pd.concat([df_base, df_novos], ignore_index=True)
    conn.update(data=df_final)
    st.cache_data.clear()

# --- TELA INICIAL ---
if 'torneio_ativo' not in st.session_state:
    st.title("⚽ BAGA BET PRO")
    df_all = carregar_tudo()
    
    if not df_all.empty:
        st.subheader("📂 Torneios Detectados")
        # Pega IDs únicos e tenta adivinhar o formato se estiver nulo
        t_list = df_all[['torneio_id', 'formato']].drop_duplicates()
        
        cols = st.columns(3)
        for i, row in enumerate(t_list.values):
            tid = str(row[0])
            tform = str(row[1]) if pd.notna(row[1]) else "LIGA" # Default caso esteja sumido
            
            if cols[i%3].button(f"{tid} ({tform})", use_container_width=True):
                st.session_state.torneio_ativo = tid
                st.session_state.formato = tform
                st.session_state.jogos = carregar_jogos(tid)
                st.rerun()
    
    st.divider()
    with st.expander("🆕 Criar Novo (ou recuperar sumido)"):
        st.write("Dica: Se o seu torneio sumiu, digite o nome dele exatamente igual abaixo e escolha o tipo.")
        c1, c2 = st.columns(2)
        n_id = c1.text_input("Nome do Torneio")
        n_form = c2.selectbox("Tipo", ["LIGA", "COPA"])
        if st.button("ABRIR / CRIAR"):
            st.session_state.torneio_ativo, st.session_state.formato = n_id, n_form
            st.session_state.jogos = carregar_jogos(n_id)
            st.rerun()

else:
    # --- INTERFACE DO TORNEIO (Mesma estrutura funcional anterior) ---
    with st.sidebar:
        st.title(st.session_state.torneio_ativo)
        menu = st.radio("Menu", ["🏟️ Jogos", "📊 Classificação", "🤑 Ranking", "⚙️ Admin"])
        if st.button("🏠 Início"):
            for k in list(st.session_state.keys()): del st.session_state[k]
            st.rerun()

    if menu == "Admin":
        st.subheader("⚙️ Gerenciamento")
        if st.button("🔄 FORÇAR ATUALIZAÇÃO"):
            st.session_state.jogos = carregar_jogos(st.session_state.torneio_ativo)
            st.rerun()
        
        # Se os jogos voltarem vazios, use esse formulário para gerar
        with st.form("gen"):
            st.write("Se não houver jogos, gere-os abaixo:")
            txt = st.text_area("Times")
            if st.form_submit_button("Gerar"):
                times = [t.strip() for t in txt.split("\n") if t.strip()]
                novos = []
                if st.session_state.formato == "LIGA":
                    for a, b in combinations(times, 2):
                        novos.append({"a":a,"b":b,"ga":None,"gb":None,"finalizado":False,"fase":"Única","apostas":[]})
                else:
                    for i in range(0, len(times), 2):
                        novos.append({"a":times[i],"b":times[i+1],"ga1":None,"gb1":None,"ga2":None,"gb2":None,"finalizado":False,"fase":"Mata-Mata","apostas":[]})
                salvar_dados(novos, st.session_state.torneio_ativo, st.session_state.formato)
                st.session_state.jogos = novos; st.rerun()
    
    # ... O restante do código de Jogos e Apostas permanece igual à versão anterior ...
