import streamlit as st
import pandas as pd
from itertools import combinations
from streamlit_gsheets import GSheetsConnection

# --- 1. CONFIGURAÇÃO E CONEXÃO ---
st.set_page_config(page_title="BAGA BET - MODO LIGA", layout="wide", page_icon="📈")
conn = st.connection("gsheets", type=GSheetsConnection)

# Colunas essenciais para o funcionamento da Liga
COLUNAS_LIGA = [
    'torneio_id', 'formato', 'fase', 'a', 'b', 
    'gols_a', 'gols_b', 'finalizado'
]

# --- 2. FUNÇÕES DE APOIO (BLINDAGEM) ---
def carregar_dados():
    st.cache_data.clear()
    try:
        df = conn.read(ttl=0)
        if df is None or df.empty:
            return pd.DataFrame(columns=COLUNAS_LIGA)
        # Garante que todas as colunas existam para não dar erro de cálculo
        for col in COLUNAS_LIGA:
            if col not in df.columns:
                df[col] = None
        # Converte gols para numérico e preenche vazios com 0
        for g in ['gols_a', 'gols_b']:
            df[g] = pd.to_numeric(df[g], errors='coerce').fillna(0).astype(int)
        return df.loc[:, ~df.columns.str.contains('^Unnamed')]
    except:
        return pd.DataFrame(columns=COLUNAS_LIGA)

def salvar_dados(df):
    # Filtra apenas as colunas que nos interessam para manter a planilha limpa
    df_save = df[COLUNAS_LIGA].copy()
    conn.update(data=df_save)
    st.cache_data.clear()
    st.toast("✅ Sincronizado com Sucesso!")
    st.rerun()

def is_finalizado(val):
    return str(val).upper().strip() in ["1", "SIM", "TRUE", "VERDADEIRO"]

# --- 3. CARREGAMENTO INICIAL ---
df_db = carregar_dados()

# --- 4. TELA DE INÍCIO (GERENCIAMENTO DE TORNEIOS) ---
if 'torneio_ativo' not in st.session_state:
    st.title("⚽ BAGA GESTOR - INÍCIO")
    
    # Seção: Carregar Existentes
    existentes = df_db.dropna(subset=['torneio_id'])
    if not existentes.empty:
        st.subheader("📂 Seus Campeonatos")
        # Mostra apenas torneios únicos
        t_lista = existentes[['torneio_id', 'formato']].drop_duplicates()
        cols = st.columns(3)
        for i, row in enumerate(t_lista.values):
            nome, tipo = row[0], row[1]
            if cols[i%3].button(f"🏟️ {nome} ({tipo})", key=f"abrir_{i}", use_container_width=True):
                st.session_state.torneio_ativo = nome
                st.session_state.formato = tipo
                st.rerun()

    st.divider()

    # Seção: Criar Novo
    st.subheader("🆕 Criar Novo Torneio")
    with st.form("form_novo"):
        col1, col2 = st.columns(2)
        nome_novo = col1.text_input("Nome do Torneio (Ex: LigaTeste)")
        tipo_novo = col2.selectbox("Formato", ["LIGA"]) # Focado em Liga agora
        
        if st.form_submit_button("CRIAR E ENTRAR"):
            if nome_novo:
                st.session_state.torneio_ativo = nome_novo.strip()
                st.session_state.formato = tipo_novo
                st.rerun()
            else:
                st.error("Dê um nome ao torneio!")

# --- 5. ÁREA DO TORNEIO (MODO LIGA) ---
else:
    t_id = st.session_state.torneio_ativo
    t_fmt = st.session_state.formato
    # Filtra os jogos específicos deste torneio
    jogos_t = df_db[df_db['torneio_id'].astype(str) == str(t_id)].copy()

    with st.sidebar:
        st.header(f"📈 {t_id}")
        menu = st.radio("Navegação", ["🏟️ Jogos", "📊 Classificação", "⚙️ Admin"])
        senha = st.text_input("Senha Admin", type="password")
        acesso = (senha == "1234")
        
        if st.button("🏠 Sair do Torneio"):
            del st.session_state['torneio_ativo']
            st.rerun()

    # --- ABA ADMIN: GERAR JOGOS ---
    if menu == "⚙️ Admin":
        st.subheader("Painel de Controle")
        if acesso:
            with st.expander("Gerar Tabela (Todos contra Todos)", expanded=True):
                txt_times = st.text_area("Lista de Times (um por linha)")
                if st.button("🔥 Gerar Campeonato"):
                    times = [t.strip() for t in txt_times.split('\n') if t.strip()]
                    if len(times) < 2:
                        st.error("Mínimo 2 times!")
                    else:
                        novos = []
                        # Gera todos os jogos possíveis entre os times
                        for a, b in combinations(times, 2):
                            novos.append({
                                'torneio_id': t_id, 'formato': 'LIGA', 'fase': 'Pontos Corridos',
                                'a': a, 'b': b, 'gols_a': 0, 'gols_b': 0, 'finalizado': '0'
                            })
                        # Adiciona ao banco e salva
                        df_updated = pd.concat([df_db, pd.DataFrame(novos)], ignore_index=True)
                        salvar_dados(df_updated)
            
            st.divider()
            if st.button("🚨 EXCLUIR ESTE TORNEIO"):
                df_clean = df_db[df_db['torneio_id'].astype(str) != str(t_id)]
                salvar_dados(df_clean)
        else:
            st.warning("Insira a senha de admin.")

    # --- ABA JOGOS: LANÇAR RESULTADOS ---
    elif menu == "🏟️ Jogos":
        if jogos_t.empty:
            st.info("Nenhum jogo gerado. Vá em Admin.")
        else:
            st.subheader("Confrontos")
            for idx, row in jogos_t.iterrows():
                with st.container(border=True):
                    c1, c2, c3 = st.columns([2, 1, 2])
                    c1.markdown(f"<h4 style='text-align:right'>{row['a']}</h4>", unsafe_allow_html=True)
                    c2.markdown(f"<h3 style='text-align:center; background:#f0f2f6; border-radius:10px;'>{row['gols_a']} x {row['gols_b']}</h3>", unsafe_allow_html=True)
                    c3.markdown(f"<h4 style='text-align:left'>{row['b']}</h4>", unsafe_allow_html=True)
                    
                    if acesso:
                        with st.expander("Lançar Placar"):
                            with st.form(f"f_{idx}"):
                                col_a, col_b = st.columns(2)
                                n_a = col_a.number_input(f"Gols {row['a']}", 0, 99, int(row['gols_a']))
                                n_b = col_b.number_input(f"Gols {row['b']}", 0, 99, int(row['gols_b']))
                                if st.form_submit_button("Confirmar"):
                                    df_db.at[idx, 'gols_a'] = n_a
                                    df_db.at[idx, 'gols_b'] = n_b
                                    df_db.at[idx, 'finalizado'] = "SIM"
                                    salvar_dados(df_db)

    # --- ABA CLASSIFICAÇÃO: O MOTOR DE PONTOS ---
    elif menu == "📊 Classificação":
        st.subheader("Tabela de Pontos Corridos")
        
        times = pd.concat([jogos_t['a'], jogos_t['b']]).dropna().unique()
        # Dicionário com stats zerados
        tabela = {t: {'P':0, 'J':0, 'V':0, 'E':0, 'D':0, 'GP':0, 'GC':0, 'SG':0} for t in times}
        
        for _, r in jogos_t.iterrows():
            if is_finalizado(r['finalizado']):
                tA, tB = r['a'], r['b']
                gA, gB = int(r['gols_a']), int(r['gols_b'])
                
                # Soma gols e jogos
                tabela[tA]['J'] += 1; tabela[tB]['J'] += 1
                tabela[tA]['GP'] += gA; tabela[tA]['GC'] += gB
                tabela[tB]['GP'] += gB; tabela[tB]['GC'] += gA
                tabela[tA]['SG'] = tabela[tA]['GP'] - tabela[tA]['GC']
                tabela[tB]['SG'] = tabela[tB]['GP'] - tabela[tB]['GC']
                
                # Regra de Pontuação
                if gA > gB:
                    tabela[tA]['P'] += 3; tabela[tA]['V'] += 1; tabela[tB]['D'] += 1
                elif gB > gA:
                    tabela[tB]['P'] += 3; tabela[tB]['V'] += 1; tabela[tA]['D'] += 1
                else:
                    tabela[tA]['P'] += 1; tabela[tB]['P'] += 1
                    tabela[tA]['E'] += 1; tabela[tB]['E'] += 1
        
        # Converte para DataFrame para ordenar e exibir
        df_rank = pd.DataFrame.from_dict(tabela, orient='index').reset_index().rename(columns={'index':'Time'})
        if not df_rank.empty:
            # Ordenação oficial: Pontos -> Vitórias -> Saldo de Gols
            df_rank = df_rank.sort_values(by=['P', 'V', 'SG'], ascending=False)
            st.table(df_rank)
