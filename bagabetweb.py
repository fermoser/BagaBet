import streamlit as st
import pandas as pd
import random
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="BAGA BET PRO", layout="wide", page_icon="⚽")
conn = st.connection("gsheets", type=GSheetsConnection)

# --- CSS VISUAL ---
st.markdown("""
    <style>
    .placar-box { background-color: #fff; border: 2px solid #333; border-radius: 12px; padding: 10px; text-align: center; }
    .fase-header { background: #111; color: #fff; padding: 10px; border-radius: 8px; margin: 15px 0; text-align: center; font-weight: bold; }
    .time-chave { color: #000 !important; font-weight: bold; }
    .pódio-container { background: linear-gradient(145deg, #FFD700, #FFA500); padding: 20px; border-radius: 15px; text-align: center; color: #000; margin-bottom: 20px; }
    </style>
    """, unsafe_allow_html=True)

# --- FUNÇÕES DE DADOS ---
def carregar_dados(nome_torneio):
    try:
        df = conn.read(ttl=0)
        if df is None or df.empty: return []
        if 'torneio_id' not in df.columns: return []
        df_f = df[df['torneio_id'] == nome_torneio]
        jogos = []
        for _, r in df_f.iterrows():
            ap = []
            if str(r.get('apostas')) not in ["nan", "", "None"]:
                for item in str(r.get('apostas')).split("|"):
                    p = item.split(":")
                    if len(p) == 3: ap.append({"nome": p[0], "valor": float(p[1]), "opcao": p[2]})
            jogos.append({
                "a": str(r['a']), "b": str(r['b']),
                "ga1": int(r['ga1']) if pd.notna(r['ga1']) else None,
                "gb1": int(r['gb1']) if pd.notna(r['gb1']) else None,
                "ga2": int(r['ga2']) if pd.notna(r['ga2']) else None,
                "gb2": int(r['gb2']) if pd.notna(r['gb2']) else None,
                "pen_a": int(r['pen_a']) if pd.notna(r['pen_a']) else 0,
                "pen_b": int(r['pen_b']) if pd.notna(r['pen_b']) else 0,
                "finalizado": str(r['finalizado']).upper() == "TRUE",
                "fase": str(r['fase']), "tipo": str(r['tipo']), "apostas": ap
            })
        return jogos
    except: return []

def salvar_dados(jogos_atuais, nome_torneio):
    df_base = conn.read(ttl=0)
    if df_base is None: df_base = pd.DataFrame()
    if not df_base.empty and 'torneio_id' in df_base.columns:
        df_base = df_base[df_base['torneio_id'] != nome_torneio]
    df_novos = pd.DataFrame(jogos_atuais)
    df_novos['torneio_id'] = nome_torneio
    df_novos['apostas'] = df_novos['apostas'].apply(lambda x: "|".join([f"{a['nome']}:{a['valor']}:{a['opcao']}" for a in x]) if x else "")
    df_novos['finalizado'] = df_novos['finalizado'].apply(lambda x: "TRUE" if x else "FALSE")
    df_final = pd.concat([df_base, df_novos], ignore_index=True)
    conn.update(data=df_final)
    st.cache_data.clear()

# --- INTERFACE ---
if 'torneio_ativo' not in st.session_state:
    st.markdown("<h1 style='text-align: center;'>⚽ BAGA BET PRO</h1>", unsafe_allow_html=True)
    nome_input = st.text_input("Identificador do Torneio (ex: CopaBaga)")
    if st.button("ENTRAR NO TORNEIO", use_container_width=True):
        if nome_input:
            st.session_state.torneio_ativo = nome_input
            st.session_state.jogos = carregar_dados(nome_input)
            st.rerun()
else:
    # Sidebar persistente
    with st.sidebar:
        st.title(f"🏆 {st.session_state.torneio_ativo}")
        menu = st.radio("Navegação", ["🏟️ Jogos", "📊 Chaves", "🤑 Ranking", "⚙️ Config"])
        st.divider()
        senha_admin = st.text_input("Senha Admin", type="password")
        is_admin = (senha_admin == "1234")
        if st.button("🏠 Sair do Torneio"):
            for key in list(st.session_state.keys()): del st.session_state[key]
            st.rerun()

    # --- ABA ADMIN (CONFIG) ---
    if menu == "⚙️ Config":
        st.header("⚙️ Configuração do Torneio")
        if not is_admin:
            st.error("Digite a senha correta na barra lateral para liberar esta área.")
        else:
            st.success("Acesso Admin Liberado!")
            tipo_torneio = st.radio("Formato de Confronto", ["UNICO", "VOLTA"], help="VOLTA inclui jogo de ida e volta.")
            qtd_times = st.selectbox("Quantidade de Equipes", [2, 4, 8, 16], index=1)
            
            # Usamos um formulário para os nomes dos times para evitar que a página recarregue a cada letra
            with st.form("form_criacao"):
                st.write("Preencha os nomes dos times:")
                cols_times = st.columns(2)
                nomes_times = []
                for i in range(qtd_times):
                    col_idx = 0 if i < (qtd_times/2) else 1
                    nome_t = cols_times[col_idx].text_input(f"Time {i+1}", key=f"input_t{i}")
                    nomes_times.append(nome_t)
                
                btn_gerar = st.form_submit_button("🚀 CRIAR TORNEIO E GERAR CHAVES")
                
                if btn_gerar:
                    equipes_filtradas = [n.strip() for n in nomes_times if n.strip()]
                    if len(equipes_filtradas) < qtd_times:
                        st.error(f"Por favor, preencha todos os {qtd_times} nomes.")
                    else:
                        random.shuffle(equipes_filtradas)
                        fase_ini = "FINAL" if qtd_times == 2 else "SEMI" if qtd_times == 4 else "QUARTAS"
                        novos_jogos = []
                        for j in range(0, len(equipes_filtradas), 2):
                            novos_jogos.append({
                                "a": equipes_filtradas[j], "b": equipes_filtradas[j+1],
                                "ga1": None, "gb1": None, "ga2": None, "gb2": None,
                                "pen_a": 0, "pen_b": 0, "finalizado": False,
                                "fase": fase_ini, "tipo": tipo_torneio, "apostas": []
                            })
                        salvar_dados(novos_jogos, st.session_state.torneio_ativo)
                        st.session_state.jogos = novos_jogos
                        st.success("Torneio Criado! Vá para a aba Jogos.")

    # --- ABA JOGOS ---
    elif menu == "🏟️ Jogos":
        if not st.session_state.get('jogos'):
            st.warning("Nenhum jogo encontrado. Vá em Config para criar.")
        else:
            # Lógica simples de exibição
            for fase in ["QUARTAS", "SEMI", "3º LUGAR", "FINAL"]:
                jogos_f = [j for j in st.session_state.jogos if j['fase'] == fase]
                if jogos_f:
                    st.markdown(f"<div class='fase-header'>{fase}</div>", unsafe_allow_html=True)
                    for idx_global, jogo in enumerate(st.session_state.jogos):
                        if jogo['fase'] == fase:
                            with st.container(border=True):
                                c1, c2, c3 = st.columns([2, 1, 2])
                                c1.markdown(f"<h3 style='text-align:right;'>{jogo['a']}</h3>", unsafe_allow_html=True)
                                placar_txt = f"{jogo['ga1'] if jogo['ga1'] is not None else '-'} : {jogo['gb1'] if jogo['gb1'] is not None else '-'}"
                                c2.markdown(f"<div class='placar-box'>{placar_txt}</div>", unsafe_allow_html=True)
                                c3.markdown(f"<h3 style='text-align:left;'>{jogo['b']}</h3>", unsafe_allow_html=True)
                                
                                # Aqui você pode adicionar o expander de placar (similar ao anterior) se is_admin for True
