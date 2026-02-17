import streamlit as st
import pandas as pd
import random
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="BAGA GESTOR PRO", layout="wide")

# --- ESTILO CSS ---
st.markdown("""
    <style>
    input[type=number] { color: #F4D03F !important; font-weight: bold !important; font-size: 20px !important; }
    .stMarkdown div[style*="background:#eee"] { background-color: #333 !important; color: #F4D03F !important; font-weight: bold; border-radius: 5px; }
    </style>
    """, unsafe_allow_html=True)

conn = st.connection("gsheets", type=GSheetsConnection)
ABA_JOGOS = "Página1" 
ABA_SUICO = "Suico"
ABA_HISTORICO = "Historico"

# ESTRUTURA COMPLETA DA PLANILHA SUÍÇO
COLUNAS_SUICO = ['torneio_id', 'formato', 'fase', 'rodada', 'a', 'b', 'gols_a', 'gols_b', 'finalizado']

# --- FUNÇÕES DE DADOS ---
def carregar_dados(aba):
    try:
        df = conn.read(worksheet=aba, ttl="0s")
        if df is None or df.empty:
            return pd.DataFrame(columns=COLUNAS_SUICO if aba == ABA_SUICO else [])
        df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
        if aba == ABA_SUICO:
            # Garante que todas as colunas existam no DataFrame carregado
            for col in COLUNAS_SUICO:
                if col not in df.columns: df[col] = None
        return df.dropna(how='all')
    except:
        return pd.DataFrame(columns=COLUNAS_SUICO if aba == ABA_SUICO else [])

def salvar_dados(df, aba):
    # Antes de salvar, se for a aba Suíço, garante que o DataFrame tenha TODAS as colunas
    if aba == ABA_SUICO:
        for col in COLUNAS_SUICO:
            if col not in df.columns: df[col] = None
        df = df[COLUNAS_SUICO] # Reordena para manter o padrão
    
    if 'torneio_id' in df.columns:
        df = df.dropna(subset=['torneio_id'])
    
    conn.update(worksheet=aba, data=df)
    st.cache_data.clear()

def calcular_ranking_suico(df_t):
    times = set(df_t['a'].dropna().unique()) | set(df_t['b'].dropna().unique())
    if "BYE" in times: times.remove("BYE")
    if not times: return None
    
    stats = {t: {'V':0, 'D':0, 'Jogos': [], 'Buchholz': 0} for t in times}
    jogos_finalizados = df_t[df_t['finalizado'].isin(['SIM', '1', True, 'true'])]
    
    for _, r in jogos_finalizados.iterrows():
        ga, gb = int(r.get('gols_a', 0)), int(r.get('gols_b', 0))
        if ga > gb: v, p = r['a'], r['b']
        elif gb > ga: v, p = r['b'], r['a']
        else: continue # Empate não previsto no suíço padrão, mas ignoramos aqui
        
        if v in stats: stats[v]['V'] += 1; stats[v]['Jogos'].append(p)
        if p in stats: stats[p]['D'] += 1; stats[p]['Jogos'].append(v)
    
    for t in stats:
        stats[t]['Buchholz'] = sum([stats[op]['V'] for op in stats[t]['Jogos'] if op in stats])
        v, d = stats[t]['V'], stats[t]['D']
        stats[t]['Status'] = "✅ Classificado" if v >= 3 else ("❌ Eliminado" if d >= 3 else "⏳ Ativo")
    
    return stats

# --- LÓGICA DE NAVEGAÇÃO ---
if 'torneio_ativo' not in st.session_state: st.session_state.torneio_ativo = None
if 'tipo_ativo' not in st.session_state: st.session_state.tipo_ativo = None 

df_padrao = carregar_dados(ABA_JOGOS)
df_suico = carregar_dados(ABA_SUICO)

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
            if cols[i%3].button(icone + t, key=f"btn_init_{t}", use_container_width=True):
                st.session_state.torneio_ativo = t
                st.session_state.tipo_ativo = "SUICO" if t in ids_s else "PADRAO"
                st.rerun()

    st.divider()
    c1, c2 = st.columns(2)
    with c1.container(border=True):
        st.subheader("🏆 Liga ou Copa")
        n_p = st.text_input("Nome do Torneio (Liga/Copa)")
        if st.button("CRIAR NOVO PADRÃO"):
            if n_p:
                novo = pd.DataFrame([{'torneio_id': n_p, 'fase': 'Inscricao'}])
                salvar_dados(pd.concat([df_padrao, novo]), ABA_JOGOS); st.rerun()
    with c2.container(border=True):
        st.subheader("⭐ Modo Suíço (Novo)")
        n_s = st.text_input("Nome do Torneio Suíço")
        if st.button("CRIAR NOVO SUÍÇO"):
            if n_s:
                # Criamos já com as colunas vazias para não bugar a planilha
                novo = pd.DataFrame([{'torneio_id': n_s, 'formato': 'SUICO', 'fase': 'Inscricao', 'rodada': 0, 'a': None, 'b': None, 'gols_a': 0, 'gols_b': 0, 'finalizado': 'NÃO'}])
                salvar_dados(pd.concat([df_suico, novo]), ABA_SUICO); st.rerun()

else:
    tid = st.session_state.torneio_ativo
    tipo = st.session_state.tipo_ativo
    
    with st.sidebar:
        st.header(f"📍 {tid}")
        menu = st.radio("Menu", ["🏟️ Jogos", "📊 Classificação", "⚙️ Admin"])
        if st.button("🏠 Sair para o Início"):
            st.session_state.torneio_ativo = None
            st.rerun()

    if tipo == "SUICO":
        df_t = df_suico[df_suico['torneio_id'] == tid].copy()
        
        if menu == "⚙️ Admin":
            senha = st.text_input("Senha Admin", type="password")
            if senha == "123":
                # Mostra criação se não houver jogos reais (coluna 'a' vazia)
                if df_t['a'].isna().all() or (df_t['fase'] == 'Inscricao').all():
                    st.subheader("🚀 Iniciar Torneio")
                    txt = st.text_area("Times (um por linha)")
                    if st.button("GERAR 1ª RODADA"):
                        times = [x.strip() for x in txt.split('\n') if x.strip()]
                        if len(times) >= 6:
                            random.shuffle(times)
                            novos_jogos = []
                            for i in range(0, len(times), 2):
                                t1 = times[i]
                                t2 = times[i+1] if i+1 < len(times) else "BYE"
                                novos_jogos.append({'torneio_id':tid, 'formato':'SUICO', 'fase':'Suico', 'rodada':1, 'a':t1, 'b':t2, 'gols_a':(1 if t2=='BYE' else 0), 'gols_b':0, 'finalizado':('SIM' if t2=='BYE' else 'NÃO')})
                            
                            # Limpa o "Inscrição" e salva
                            df_final = pd.concat([df_suico[df_suico['torneio_id'] != tid], pd.DataFrame(novos_jogos)])
                            salvar_dados(df_final, ABA_SUICO); st.rerun()
                
                st.divider()
                if st.button("🚨 EXCLUIR TORNEIO"):
                    salvar_dados(df_suico[df_suico['torneio_id'] != tid], ABA_SUICO)
                    st.session_state.torneio_ativo = None; st.rerun()

        elif menu == "🏟️ Jogos":
            jogos = df_t[df_t['fase'] == 'Suico']
            if jogos.empty: st.warning("Aguardando sorteio no Admin.")
            else:
                for idx, r in jogos.iterrows():
                    with st.container(border=True):
                        col1, col2, col3 = st.columns([2,1,2])
                        col1.write(f"**{r['a']}**")
                        col2.write(f"{int(r['gols_a'])} x {int(r['gols_b'])}")
                        col3.write(f"**{r['b']}**")
                        with st.expander("Lançar Placar"):
                            with st.form(f"form_{idx}"):
                                ga = st.number_input("Gols A", 0, 99, int(r['gols_a']))
                                gb = st.number_input("Gols B", 0, 99, int(r['gols_b']))
                                if st.form_submit_button("Salvar"):
                                    df_suico.loc[idx, ['gols_a', 'gols_b', 'finalizado']] = [ga, gb, "SIM"]
                                    salvar_dados(df_suico, ABA_SUICO); st.rerun()

        elif menu == "📊 Classificação":
            rk = calcular_ranking_suico(df_t)
            if rk:
                df_rk = pd.DataFrame(rk).T.sort_values(['V', 'Buchholz'], ascending=False)
                st.table(df_rk[['V', 'D', 'Buchholz', 'Status']])

    else:
        st.info("Modo Padrão (Liga/Copa) - Lógica original mantida aqui.")
