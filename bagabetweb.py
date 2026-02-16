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
    .placar-box { background: #f8f9fa; border: 2px solid #333; border-radius: 10px; padding: 10px; text-align: center; font-size: 1.5rem; font-weight: bold; }
    .fase-header { background: #000; color: #fff; padding: 10px; border-radius: 5px; text-align: center; margin: 15px 0; }
    .vs { font-size: 0.8rem; color: #666; }
    </style>
    """, unsafe_allow_html=True)

# --- FUNÇÕES DE CARREGAMENTO ---
def carregar_dados_direto(nome_torneio):
    try:
        df = conn.read(ttl=0)
        if df is None or df.empty: return []
        
        nome_torneio = str(nome_torneio).strip()
        df_f = df[df['torneio_id'].astype(str).str.strip() == nome_torneio]
        
        jogos = []
        for _, r in df_f.iterrows():
            # Processar Apostas
            ap = []
            if str(r.get('apostas')) not in ["nan", "", "None"]:
                for item in str(r.get('apostas')).split("|"):
                    p = item.split(":")
                    if len(p) == 3: ap.append({"nome": p[0], "valor": float(p[1]), "opcao": p[2]})
            
            # Estrutura flexível para Liga e Copa
            jogos.append({
                "a": str(r['a']), "b": str(r['b']),
                "ga1": int(r['ga1']) if pd.notna(r.get('ga1')) else None,
                "gb1": int(r['gb1']) if pd.notna(r.get('gb1')) else None,
                "ga2": int(r['ga2']) if pd.notna(r.get('ga2')) else None,
                "gb2": int(r['gb2']) if pd.notna(r.get('gb2')) else None,
                "ga": int(r['ga']) if pd.notna(r.get('ga')) else None, # Gols da Liga
                "gb": int(r['gb']) if pd.notna(r.get('gb')) else None,
                "pen_a": int(r['pen_a']) if pd.notna(r.get('pen_a')) else 0,
                "pen_b": int(r['pen_b']) if pd.notna(r.get('pen_b')) else 0,
                "finalizado": str(r.get('finalizado')).upper() == "TRUE",
                "fase": str(r.get('fase')), 
                "formato": str(r.get('formato')),
                "apostas": ap
            })
        return jogos
    except Exception as e:
        st.error(f"Erro ao ler: {e}")
        return []

def salvar_dados(jogos_atuais, nome_torneio, formato):
    df_db = conn.read(ttl=0)
    nome_torneio = str(nome_torneio).strip()
    
    df_limpo = df_db[df_db['torneio_id'].astype(str).str.strip() != nome_torneio] if df_db is not None else pd.DataFrame()
    
    df_novos = pd.DataFrame(jogos_atuais)
    df_novos['torneio_id'] = nome_torneio
    df_novos['formato'] = formato
    df_novos['apostas'] = df_novos['apostas'].apply(lambda x: "|".join([f"{a['nome']}:{a['valor']}:{a['opcao']}" for a in x]) if x else "")
    df_novos['finalizado'] = df_novos['finalizado'].apply(lambda x: "TRUE" if x else "FALSE")
    
    df_final = pd.concat([df_limpo, df_novos], ignore_index=True)
    conn.update(data=df_final)
    st.cache_data.clear()

# --- INTERFACE ---
if 'torneio_ativo' not in st.session_state:
    st.title("⚽ BAGA BET PRO")
    df_db = conn.read(ttl=0)
    if df_db is not None and not df_db.empty:
        st.subheader("📂 Selecione um Torneio Ativo")
        t_unicos = df_db[['torneio_id', 'formato']].dropna().drop_duplicates()
        cols = st.columns(3)
        for i, row in enumerate(t_unicos.values):
            if cols[i%3].button(f"{'🏆' if row[1]=='COPA' else '📈'} {row[0]}", use_container_width=True):
                st.session_state.torneio_ativo = row[0]
                st.session_state.formato = row[1]
                st.session_state.jogos = carregar_dados_direto(row[0])
                st.rerun()
    
    st.divider()
    c1, c2 = st.columns(2)
    n_id = c1.text_input("Novo Torneio")
    n_tp = c2.selectbox("Formato", ["LIGA", "COPA"])
    if st.button("🚀 CRIAR NOVO"):
        st.session_state.torneio_ativo, st.session_state.formato, st.session_state.jogos = n_id, n_tp, []
        st.rerun()

else:
    formato = st.session_state.formato
    with st.sidebar:
        st.title(st.session_state.torneio_ativo)
        menu = st.radio("Menu", ["🏟️ Jogos", "📊 Tabela/Chaves", "🤑 Ranking", "⚙️ Admin"])
        is_admin = (st.text_input("Senha", type="password") == "1234")
        if st.button("🏠 Sair"):
            for k in list(st.session_state.keys()): del st.session_state[k]
            st.rerun()

    # --- ABA JOGOS ---
    if menu == "🏟️ Jogos":
        for fase in sorted(list(set([j['fase'] for j in st.session_state.jogos]))):
            st.markdown(f"<div class='fase-header'>{fase}</div>", unsafe_allow_html=True)
            for idx, j in enumerate(st.session_state.jogos):
                if j['fase'] == fase:
                    with st.container(border=True):
                        c1, c2, c3 = st.columns([2, 1, 2])
                        c1.markdown(f"<p style='text-align:right;'><b>{j['a']}</b></p>", unsafe_allow_html=True)
                        
                        # Exibição do placar baseada no formato
                        if formato == "LIGA":
                            p_txt = f"{j['ga'] if j['ga'] is not None else '-'} : {j['gb'] if j['gb'] is not None else '-'}"
                        else:
                            p_txt = f"({j['ga1'] or 0}) {j['ga2'] or 0} : {j['gb2'] or 0} ({j['gb1'] or 0})"
                        
                        c2.markdown(f"<div class='placar-box'>{p_txt}</div>", unsafe_allow_html=True)
                        c3.markdown(f"<p><b>{j['b']}</b></p>", unsafe_allow_html=True)

                        if is_admin:
                            if not j['finalizado']:
                                with st.expander("Lançar Gols"):
                                    if formato == "LIGA":
                                        v1, v2 = st.number_input("Gols A", 0, key=f"la{idx}"), st.number_input("Gols B", 0, key=f"lb{idx}")
                                        if st.button("Salvar Liga", key=f"bs{idx}"):
                                            j.update({"ga":v1, "gb":v2, "finalizado":True})
                                            salvar_dados(st.session_state.jogos, st.session_state.torneio_ativo, "LIGA"); st.rerun()
                                    else:
                                        colA, colB = st.columns(2)
                                        ga1 = colA.number_input("Ida A", 0, key=f"ga1{idx}")
                                        gb1 = colB.number_input("Ida B", 0, key=f"gb1{idx}")
                                        ga2 = colA.number_input("Volta A", 0, key=f"ga2{idx}")
                                        gb2 = colB.number_input("Volta B", 0, key=f"gb2{idx}")
                                        pa, pb = 0, 0
                                        if (ga1+ga2) == (gb1+gb2):
                                            pa, pb = colA.number_input("Pen A", 0, key=f"pa{idx}"), colB.number_input("Pen B", 0, key=f"pb{idx}")
                                        if st.button("Salvar Copa", key=f"bsc{idx}"):
                                            j.update({"ga1":ga1,"gb1":gb1,"ga2":ga2,"gb2":gb2,"pen_a":pa,"pen_b":pb,"finalizado":True})
                                            salvar_dados(st.session_state.jogos, st.session_state.torneio_ativo, "COPA"); st.rerun()
                            else:
                                if st.button("🔄 Refazer", key=f"rf{idx}"):
                                    j['finalizado'] = False; st.rerun()
