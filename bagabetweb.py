import streamlit as st
import pandas as pd
import random
from itertools import combinations
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="BAGA BET PRO", layout="wide", page_icon="⚽")
conn = st.connection("gsheets", type=GSheetsConnection)

# --- CSS VISUAL ---
st.markdown("""
    <style>
    .placar-box { background-color: #fff; border: 2px solid #333; border-radius: 12px; padding: 10px; text-align: center; }
    .fase-header { background: #111; color: #fff; padding: 8px; border-radius: 8px; margin: 10px 0; text-align: center; font-weight: bold; }
    .time-nome { font-weight: bold; font-size: 1.1rem; }
    .gols-res { color: #1b5e20; font-weight: 900; font-size: 1.8rem; }
    </style>
    """, unsafe_allow_html=True)

# --- FUNÇÕES DE DADOS ---
def money(v):
    cor = "#28a745" if v > 0 else "#dc3545" if v < 0 else "#212529"
    val_fmt = f"R$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f'<span style="color:{cor}; font-weight:bold;">{val_fmt}</span>'

def carregar_tudo():
    try: 
        # Forçamos ttl=0 e limpamos cache para garantir que venha da nuvem
        st.cache_data.clear()
        df = conn.read(ttl=0)
        if df is not None:
            df = df.dropna(subset=['torneio_id']) # Remove linhas fantasmas
            df['torneio_id'] = df['torneio_id'].astype(str).str.strip()
        return df if df is not None else pd.DataFrame()
    except: return pd.DataFrame()

def carregar_dados_torneio(nome_torneio):
    df = carregar_tudo()
    if df.empty or 'torneio_id' not in df.columns: return []
    
    # Filtro rigoroso pelo ID do torneio
    df_f = df[df['torneio_id'] == str(nome_torneio).strip()]
    
    jogos = []
    for _, r in df_f.iterrows():
        ap = []
        if str(r.get('apostas')) not in ["nan", "", "None"]:
            for item in str(r.get('apostas')).split("|"):
                p = item.split(":")
                if len(p) == 3: ap.append({"nome": p[0], "valor": float(p[1]), "opcao": p[2]})
        
        jogos.append({
            "a": str(r['a']), "b": str(r['b']),
            "ga": int(r['ga']) if pd.notna(r['ga']) else None,
            "gb": int(r['gb']) if pd.notna(r['gb']) else None,
            "pen_a": int(r['pen_a']) if pd.notna(r['pen_a']) else 0,
            "pen_b": int(r['pen_b']) if pd.notna(r['pen_b']) else 0,
            "finalizado": str(r['finalizado']).upper() == "TRUE",
            "fase": str(r['fase']), 
            "formato": str(r.get('formato', 'COPA')),
            "apostas": ap
        })
    return jogos

def salvar_dados(jogos_atuais, nome_torneio, formato):
    df_base = carregar_tudo()
    nome_torneio = str(nome_torneio).strip()
    
    if not df_base.empty and 'torneio_id' in df_base.columns:
        df_base = df_base[df_base['torneio_id'] != nome_torneio]
    
    df_novos = pd.DataFrame(jogos_atuais)
    df_novos['torneio_id'] = nome_torneio
    df_novos['formato'] = formato
    df_novos['apostas'] = df_novos['apostas'].apply(lambda x: "|".join([f"{a['nome']}:{a['valor']}:{a['opcao']}" for a in x]) if x else "")
    df_novos['finalizado'] = df_novos['finalizado'].apply(lambda x: "TRUE" if x else "FALSE")
    
    df_final = pd.concat([df_base, df_novos], ignore_index=True)
    conn.update(data=df_final)
    st.cache_data.clear()

# --- TELA INICIAL ---
if 'torneio_ativo' not in st.session_state:
    st.markdown("<h1 style='text-align: center;'>⚽ BAGA BET PRO</h1>", unsafe_allow_html=True)
    df_all = carregar_tudo()
    
    if not df_all.empty and 'torneio_id' in df_all.columns:
        st.subheader("📂 Torneios Detectados na Nuvem")
        # Identifica torneios e formatos únicos
        t_unicos = df_all[['torneio_id', 'formato']].drop_duplicates()
        
        cols = st.columns(3)
        for i, row in enumerate(t_unicos.values):
            tid, form = row[0], row[1]
            if cols[i%3].button(f"{'🏆' if form=='COPA' else '📈'} {tid}", use_container_width=True):
                st.session_state.jogos = carregar_dados_torneio(tid)
                st.session_state.torneio_ativo = tid
                st.session_state.formato = form
                st.rerun()
                
    st.divider()
    st.subheader("🆕 Criar Novo")
    c1, c2 = st.columns(2)
    n_id = c1.text_input("Nome do Torneio")
    n_form = c2.selectbox("Tipo", ["COPA", "LIGA"])
    if st.button("INICIAR", use_container_width=True):
        if n_id:
            st.session_state.torneio_ativo = n_id.strip()
            st.session_state.formato = n_form
            st.session_state.jogos = []
            st.rerun()

else:
    # --- INTERFACE DO TORNEIO ATIVO ---
    with st.sidebar:
        st.title(f"{st.session_state.torneio_ativo}")
        menu = st.radio("Menu", ["🏟️ Jogos", "📊 Tabela/Chaves", "🤑 Ranking", "⚙️ Admin"])
        is_admin = (st.text_input("Senha Admin", type="password") == "1234")
        if st.button("🏠 Sair / Trocar Torneio"):
            for k in list(st.session_state.keys()): del st.session_state[k]
            st.rerun()

    # --- ADMIN (RESTAURAR E GERAR) ---
    if menu == "⚙️ Admin":
        st.header("⚙️ Painel de Controle")
        if st.button("🔄 FORÇAR ATUALIZAÇÃO DA NUVEM", use_container_width=True):
            st.session_state.jogos = carregar_dados_torneio(st.session_state.torneio_ativo)
            st.toast("Sincronizado!")
            st.rerun()
            
        if is_admin:
            st.divider()
            with st.form("setup_novo"):
                st.subheader("Reinicializar Torneio")
                qtd = st.number_input("Qtd de Times", 2, 16, 4)
                nomes = [st.text_input(f"Time {i+1}", key=f"nt{i}") for i in range(qtd)]
                if st.form_submit_button("GERAR NOVOS CONFRONTOS"):
                    nomes_f = [n for n in nomes if n]
                    random.shuffle(nomes_f)
                    novos = []
                    if st.session_state.formato == "LIGA":
                        for a, b in combinations(nomes_f, 2):
                            novos.append({"a":a,"b":b,"ga":None,"gb":None,"pen_a":0,"pen_b":0,"finalizado":False,"fase":"Rodada Única","apostas":[]})
                    else:
                        f_i = "FINAL" if qtd==2 else "SEMI" if qtd==4 else "QUARTAS"
                        for i in range(0, len(nomes_f), 2):
                            novos.append({"a":nomes_f[i],"b":nomes_f[i+1],"ga":None,"gb":None,"pen_a":0,"pen_b":0,"finalizado":False,"fase":f_i,"apostas":[]})
                    salvar_dados(novos, st.session_state.torneio_ativo, st.session_state.formato)
                    st.session_state.jogos = novos; st.rerun()

    # --- JOGOS (EXIBIÇÃO) ---
    elif menu == "🏟️ Jogos":
        if not st.session_state.jogos:
            st.info("Nenhum jogo encontrado. Vá em Admin para gerar ou sincronizar.")
        else:
            # Ordena as fases para a Copa
            ordem_fases = ["QUARTAS", "SEMI", "3º LUGAR", "FINAL", "Rodada Única"]
            fases_presentes = sorted(list(set([j['fase'] for j in st.session_state.jogos])), key=lambda x: ordem_fases.index(x) if x in ordem_fases else 99)
            
            for fase in fases_presentes:
                st.markdown(f"<div class='fase-header'>{fase}</div>", unsafe_allow_html=True)
                for idx, j in enumerate(st.session_state.jogos):
                    if j['fase'] == fase:
                        with st.container(border=True):
                            c1, c2, c3 = st.columns([2, 1, 2])
                            c1.markdown(f"<p style='text-align:right;' class='time-nome'>{j['a']}</p>", unsafe_allow_html=True)
                            c2.markdown(f"<div class='placar-box'><span class='gols-res'>{j['ga'] if j['ga'] is not None else '-'} : {j['gb'] if j['gb'] is not None else '-'}</span></div>", unsafe_allow_html=True)
                            c3.markdown(f"<p class='time-nome'>{j['b']}</p>", unsafe_allow_html=True)
                            
                            if is_admin:
                                if not j['finalizado']:
                                    with st.expander("Lançar Placar"):
                                        v1 = st.number_input("Gols A", 0, 20, key=f"v1{idx}{fase}")
                                        v2 = st.number_input("Gols B", 0, 20, key=f"v2{idx}{fase}")
                                        pa, pb = 0, 0
                                        if st.session_state.formato == "COPA" and v1 == v2:
                                            pa = st.number_input("Pên A", 0, 20, key=f"pa{idx}{fase}")
                                            pb = st.number_input("Pên B", 0, 20, key=f"pb{idx}{fase}")
                                        if st.button("Confirmar", key=f"btn{idx}{fase}"):
                                            j.update({"ga":v1,"gb":v2,"pen_a":pa,"pen_b":pb,"finalizado":True})
                                            # Aqui você pode chamar a função de atualizar confrontos de copa se for formato COPA
                                            salvar_dados(st.session_state.jogos, st.session_state.torneio_ativo, st.session_state.formato); st.rerun()
                                else:
                                    if st.button("🔄 Refazer Jogo", key=f"ref{idx}{fase}"):
                                        j['finalizado'] = False; st.rerun()
                            
                            # (O código de apostas e tabelas segue aqui de forma idêntica à anterior...)
