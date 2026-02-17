import streamlit as st
import pandas as pd
import random
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="BAGA GESTOR PRO", layout="wide")

conn = st.connection("gsheets", type=GSheetsConnection)
ABA_JOGOS = "Página1" 
ABA_SUICO = "Suico"

# ESTRUTURA IMUTÁVEL (Para o Google Sheets não apagar colunas)
COLS_SUICO = ['torneio_id', 'formato', 'fase', 'rodada', 'a', 'b', 'gols_a', 'gols_b', 'finalizado']

# --- FUNÇÕES DE DADOS ---
def carregar_dados(aba):
    try:
        df = conn.read(worksheet=aba, ttl="0s")
        if df is None or df.empty:
            return pd.DataFrame(columns=COLS_SUICO)
        df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
        # Garante que todas as colunas existam ao ler
        if aba == ABA_SUICO:
            for col in COLS_SUICO:
                if col not in df.columns: df[col] = "-"
        return df.dropna(how='all')
    except:
        return pd.DataFrame(columns=COLS_SUICO)

def salvar_dados(df, aba):
    if aba == ABA_SUICO:
        # Força o DataFrame a ter exatamente as 9 colunas antes de subir
        for col in COLS_SUICO:
            if col not in df.columns: df[col] = "-"
        df = df[COLS_SUICO] 
    
    if 'torneio_id' in df.columns:
        df = df.dropna(subset=['torneio_id'])
    
    conn.update(worksheet=aba, data=df)
    st.cache_data.clear()

# --- INICIALIZAÇÃO ---
if 'torneio_ativo' not in st.session_state: st.session_state.torneio_ativo = None
if 'tipo_ativo' not in st.session_state: st.session_state.tipo_ativo = None 

df_suico = carregar_dados(ABA_SUICO)
df_padrao = carregar_dados(ABA_JOGOS)

# --- TELA INICIAL ---
if st.session_state.torneio_ativo is None:
    st.title("⚽ BAGA GESTOR PRO")
    
    # Lista unificada de torneios
    ids_s = [str(x) for x in df_suico['torneio_id'].dropna().unique() if str(x) != "-"]
    ids_p = [str(x) for x in df_padrao['torneio_id'].dropna().unique() if str(x) != "-"]
    all_t = sorted(list(set(ids_s + ids_p)))
    
    if all_t:
        st.subheader("📂 Meus Torneios")
        cols = st.columns(3)
        for i, t in enumerate(all_t):
            icone = "⭐ " if t in ids_s else "🏆 "
            if cols[i%3].button(icone + t, key=f"t_{t}", use_container_width=True):
                st.session_state.torneio_ativo = t
                st.session_state.tipo_ativo = "SUICO" if t in ids_s else "PADRAO"
                st.rerun()

    st.divider()
    st.subheader("🆕 Criar Novo Suíço")
    ns = st.text_input("Nome do Torneio")
    if st.button("CRIAR"):
        if ns:
            # Cria a linha inicial preenchendo TODAS as colunas com "-" para não bugar
            nova_linha = pd.DataFrame([[ns, 'SUICO', 'Inscricao', 0, '-', '-', 0, 0, 'NÃO']], columns=COLS_SUICO)
            salvar_dados(pd.concat([df_suico, nova_linha]), ABA_SUICO)
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
            st.subheader("🔐 Painel de Controle")
            senha = st.text_input("Senha", type="password")
            if senha == "123":
                st.success("Acesso Liberado")
                
                # Sorteio (Aparece se não houver jogos reais ou se estiver em 'Inscricao')
                with st.expander("📝 Gerar 1ª Rodada", expanded=True):
                    txt = st.text_area("Times (um por linha)")
                    if st.button("SORTEAR"):
                        times = [x.strip() for x in txt.split('\n') if x.strip()]
                        if len(times) >= 6:
                            random.shuffle(times)
                            novos = []
                            for i in range(0, len(times), 2):
                                t1 = times[i]
                                t2 = times[i+1] if i+1 < len(times) else "BYE"
                                novos.append({'torneio_id':tid, 'formato':'SUICO', 'fase':'Suico', 'rodada':1, 'a':t1, 'b':t2, 'gols_a':(1 if t2=='BYE' else 0), 'gols_b':0, 'finalizado':('SIM' if t2=='BYE' else 'NÃO')})
                            
                            # Limpa o torneio atual e salva a nova rodada
                            df_limpo = df_suico[df_suico['torneio_id'] != tid]
                            salvar_dados(pd.concat([df_limpo, pd.DataFrame(novos)]), ABA_SUICO)
                            st.rerun()
                
                if st.button("🚨 EXCLUIR TUDO"):
                    salvar_dados(df_suico[df_suico['torneio_id'] != tid], ABA_SUICO)
                    st.session_state.torneio_ativo = None; st.rerun()

        elif menu == "🏟️ Jogos":
            jogos = df_t[df_t['fase'] == 'Suico']
            if jogos.empty:
                st.info("Aguardando sorteio no menu Admin.")
            else:
                for idx, r in jogos.iterrows():
                    with st.container(border=True):
                        c1, c2, c3 = st.columns([2,1,2])
                        c1.write(f"**{r['a']}**")
                        c2.write(f"{r['gols_a']} x {r['gols_b']}")
                        c3.write(f"**{r['b']}**")
                        # (Aqui entraria o formulário de placar, mantido simples para teste)

    else:
        st.write("Modo Liga/Copa - Suas funções originais devem ser coladas aqui.")
