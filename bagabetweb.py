import streamlit as st
import pandas as pd
import random
from streamlit_gsheets import GSheetsConnection

# 1. Configuração e Conexão
st.set_page_config(page_title="BAGA FIX FINAL", layout="wide")
conn = st.connection("gsheets", type=GSheetsConnection)

# 2. Função de Leitura (ttl=0 para ler na hora o que está no Sheets)
def carregar():
    try:
        df = conn.read(worksheet="Suico", ttl=0)
        return df.loc[:, ~df.columns.str.contains('^Unnamed')]
    except:
        return pd.DataFrame(columns=['torneio_id', 'fase', 'a', 'b', 'finalizado'])

df_total = carregar()

# 3. Navegação Simples
if 'torneio_ativo' not in st.session_state:
    st.title("⚽ GESTOR BAGA")
    
    # Criar Novo
    with st.expander("➕ CRIAR NOVO SUÍÇO"):
        nome = st.text_input("Nome do Torneio")
        if st.button("Criar"):
            if nome:
                nova_linha = pd.DataFrame([{'torneio_id': nome, 'fase': 'Inscricao', 'finalizado': 'NÃO'}])
                df_atualizado = pd.concat([df_total, nova_linha], ignore_index=True)
                conn.update(worksheet="Suico", data=df_atualizado)
                st.cache_data.clear()
                st.rerun()

    # Lista de Torneios
    if not df_total.empty:
        ids = [str(x) for x in df_total['torneio_id'].dropna().unique() if str(x).strip() != ""]
        for tid in sorted(ids):
            if st.button(f"Entrar: {tid}"):
                st.session_state.torneio_ativo = tid
                st.rerun()

else:
    # --- ÁREA DO TORNEIO (Onde você está na foto nnnn.png) ---
    tid = st.session_state.torneio_ativo
    st.header(f"🏆 {tid}")
    
    if st.button("⬅️ Voltar"):
        st.session_state.torneio_ativo = None
        st.rerun()

    aba1, aba2 = st.tabs(["🏟️ Jogos", "⚙️ Admin"])

    with aba2: # ABA ADMIN
        st.subheader("Painel de Controle")
        
        # IMPORTANTE: A senha agora é validada e o conteúdo só aparece se estiver correta
        senha = st.text_input("Digite a Senha para liberar", type="password", key="senha_admin")
        
        if senha == "123":
            st.success("Acesso Liberado! O campo abaixo apareceu:")
            st.markdown("---")
            
            # ESTE É O CAMPO QUE VOCÊ PRECISA
            texto_times = st.text_area("COLE OS TIMES AQUI (UM POR LINHA)", height=300, placeholder="Time A\nTime B\nTime C...")
            
            if st.button("🚀 GERAR JOGOS DA 1ª RODADA"):
                lista = [t.strip() for t in texto_times.split('\n') if t.strip()]
                if len(lista) >= 4:
                    random.shuffle(lista)
                    jogos_novos = []
                    for i in range(0, len(lista), 2):
                        t1 = lista[i]
                        t2 = lista[i+1] if i+1 < len(lista) else "BYE"
                        jogos_novos.append({'torneio_id': tid, 'fase': 'Suico', 'a': t1, 'b': t2, 'finalizado': 'NÃO'})
                    
                    # Remove o registro de 'Inscricao' e salva as partidas
                    df_outros = df_total[df_total['torneio_id'] != tid]
                    df_salvar = pd.concat([df_outros, pd.DataFrame(jogos_novos)], ignore_index=True)
                    conn.update(worksheet="Suico", data=df_salvar)
                    st.cache_data.clear()
                    st.success("Sucesso! Os jogos foram criados.")
                    st.rerun()
                else:
                    st.error("Insira pelo menos 4 times.")

    with aba1: # ABA JOGOS
        st.subheader("Partidas")
        meus_jogos = df_total[(df_total['torneio_id'] == tid) & (df_total['fase'] == 'Suico')]
        if meus_jogos.empty:
            st.info("Aguardando sorteio no Admin.")
        else:
            for _, r in meus_jogos.iterrows():
                st.write(f"⚽ **{r['a']}** vs **{r['b']}**")
