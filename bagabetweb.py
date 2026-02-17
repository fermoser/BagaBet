import streamlit as st
import pandas as pd
import random
from streamlit_gsheets import GSheetsConnection

st.set_page_config(page_title="BAGA FIX", layout="wide")

# 1. CONEXÃO DIRETA E LIMPEZA
conn = st.connection("gsheets", type=GSheetsConnection)

# Botão de emergência para limpar o cache se o Google Sheets travar
if st.sidebar.button("♻️ FORÇAR ATUALIZAÇÃO"):
    st.cache_data.clear()
    st.rerun()

def carregar_tudo():
    try:
        # Lê a aba Suico sem guardar memória cache (ttl=0)
        df = conn.read(worksheet="Suico", ttl=0)
        if df is None or df.empty:
            return pd.DataFrame(columns=['torneio_id', 'fase', 'a', 'b'])
        # Remove colunas fantasmas do Google
        df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
        return df
    except:
        return pd.DataFrame(columns=['torneio_id', 'fase', 'a', 'b'])

df_total = carregar_tudo()

# --- TELA INICIAL ---
if 'torneio_ativo' not in st.session_state:
    st.title("⚽ GESTOR BAGA")
    
    # Criar Novo
    with st.expander("➕ CRIAR NOVO TORNEIO SUÍÇO"):
        novo_nome = st.text_input("Nome do Torneio")
        if st.button("Confirmar Criação"):
            if novo_nome:
                # Criamos apenas com o ID e Fase, o resto o Google completa
                nova_linha = pd.DataFrame([{'torneio_id': novo_nome, 'fase': 'Inscricao'}])
                df_final = pd.concat([df_total, nova_linha], ignore_index=True)
                conn.update(worksheet="Suico", data=df_final)
                st.cache_data.clear()
                st.success("Criado! Clique em 'FORÇAR ATUALIZAÇÃO'")

    # Listar Torneios (Tratando o erro de IDs mistos que deu antes)
    if not df_total.empty and 'torneio_id' in df_total.columns:
        st.subheader("Seus Torneios:")
        ids = [str(x) for x in df_total['torneio_id'].dropna().unique() if str(x).strip() != ""]
        for tid in sorted(ids):
            if st.button(f"Entrar em: {tid}"):
                st.session_state.torneio_ativo = tid
                st.rerun()

# --- ÁREA DO TORNEIO ---
else:
    tid = st.session_state.torneio_ativo
    st.header(f"🏆 Torneio: {tid}")
    
    if st.button("⬅️ Voltar"):
        st.session_state.torneio_ativo = None
        st.rerun()

    menu = st.tabs(["🎮 Jogos", "⚙️ Admin"])

    with menu[1]: # Aba ADMIN
        st.subheader("Painel de Controle")
        senha = st.text_input("Senha", type="password")
        if senha == "123":
            # A CAIXA QUE VOCÊ PRECISA
            st.markdown("---")
            txt_times = st.text_area("COLE OS TIMES AQUI (UM POR LINHA)", height=250)
            
            if st.button("🚀 SORTEAR E INICIAR AGORA"):
                times = [x.strip() for x in txt_times.split('\n') if x.strip()]
                if len(times) >= 4:
                    random.shuffle(times)
                    jogos = []
                    for i in range(0, len(times), 2):
                        t1 = times[i]
                        t2 = times[i+1] if i+1 < len(times) else "BYE"
                        jogos.append({'torneio_id': tid, 'fase': 'Suico', 'a': t1, 'b': t2, 'finalizado': 'NÃO'})
                    
                    # Remove o rascunho e salva os jogos
                    df_outros = df_total[df_total['torneio_id'] != tid]
                    df_final = pd.concat([df_outros, pd.DataFrame(jogos)], ignore_index=True)
                    conn.update(worksheet="Suico", data=df_final)
                    st.cache_data.clear()
                    st.success("Jogos Gerados! Volte na aba 'Jogos'.")
                else:
                    st.error("Coloque pelo menos 4 times.")

    with menu[0]: # Aba JOGOS
        st.subheader("Partidas Atuais")
        meus_jogos = df_total[(df_total['torneio_id'] == tid) & (df_total['fase'] == 'Suico')]
        
        if meus_jogos.empty:
            st.info("Nenhum jogo gerado. Vá ao Admin.")
        else:
            for _, r in meus_jogos.iterrows():
                st.write(f"🏟️ **{r.get('a', '???')}** vs **{r.get('b', '???')}**")
