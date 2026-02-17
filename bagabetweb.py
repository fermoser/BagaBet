import streamlit as st
import pandas as pd
import random
from itertools import combinations
from streamlit_gsheets import GSheetsConnection
from datetime import datetime, timedelta

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="BAGA GESTOR PRO", layout="wide")

# --- ESTILO CSS ---
st.markdown("""
    <style>
    input[type=number] { color: #F4D03F !important; font-weight: bold !important; font-size: 20px !important; }
    .stMarkdown div[style*="background:#eee"] { background-color: #333 !important; color: #F4D03F !important; font-weight: bold; border-radius: 5px; }
    [data-testid="stForm"] .stColumn { display: flex; align-items: center; justify-content: center; }
    </style>
    """, unsafe_allow_html=True)

conn = st.connection("gsheets", type=GSheetsConnection)
ABA_JOGOS = "Página1" 
ABA_SUICO = "Suico"
ABA_HISTORICO = "Historico"

# --- FUNÇÕES DE DADOS ---
def carregar_dados(aba):
    try:
        df = conn.read(worksheet=aba, ttl="0s")
        if df is None or df.empty: return pd.DataFrame()
        df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
        df = df.dropna(how='all')
        return df
    except: return pd.DataFrame()

def salvar_dados(df, aba):
    if 'torneio_id' in df.columns:
        df = df.dropna(subset=['torneio_id'])
    conn.update(worksheet=aba, data=df)
    st.cache_data.clear()

def is_done(val): return str(val).upper().strip() in ["1", "SIM", "TRUE"]

# --- LÓGICA DO MODO SUÍÇO (ISOLADA) ---
def calcular_ranking_suico(df_t):
    times = set(df_t['a'].unique()) | set(df_t['b'].unique())
    if "BYE" in times: times.remove("BYE")
    stats = {t: {'V':0, 'D':0, 'Jogos': [], 'Buchholz': 0} for t in times if pd.notna(t)}
    
    for _, r in df_t[df_t['fase'] == 'Suico'].iterrows():
        if is_done(r['finalizado']):
            ga, gb = int(r.get('gols_a', 0)), int(r.get('gols_b', 0))
            v, p = (r['a'], r['b']) if ga > gb else (r['b'], r['a'])
            if v in stats: stats[v]['V'] += 1; stats[v]['Jogos'].append(p)
            if p in stats: stats[p]['D'] += 1; stats[p]['Jogos'].append(v)
    
    for t in stats:
        stats[t]['Buchholz'] = sum([stats[op]['V'] for op in stats[t]['Jogos'] if op in stats])
        if stats[t]['V'] >= 3: stats[t]['Status'] = "Classificado"
        elif stats[t]['D'] >= 3: stats[t]['Status'] = "Eliminado"
        else: stats[t]['Status'] = "Ativo"
    return stats

# --- INICIALIZAÇÃO ---
if 'torneio_ativo' not in st.session_state: st.session_state.torneio_ativo = None
if 'tipo_ativo' not in st.session_state: st.session_state.tipo_ativo = None 

df_padrao = carregar_dados(ABA_JOGOS)
df_suico = carregar_dados(ABA_SUICO)
df_hist = carregar_dados(ABA_HISTORICO)

# --- TELA INICIAL ---
if st.session_state.torneio_ativo is None:
    st.title("⚽ BAGA GESTOR PRO")
    
    with st.expander("📜 HALL DA FAMA"):
        if not df_hist.empty: st.dataframe(df_hist.sort_index(ascending=False), use_container_width=True)
    
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
            if cols[i%3].button(icone + t, key=f"abrir_{t}", use_container_width=True):
                st.session_state.torneio_ativo = t
                st.session_state.tipo_ativo = "SUICO" if t in ids_s else "PADRAO"
                st.rerun()

    st.divider()
    st.subheader("🆕 Criar Novo")
    c1, c2, c3 = st.columns(3)
    
    with c1.container(border=True):
        st.markdown("### 🏆 LIGA")
        nl = st.text_input("Nome da Liga")
        if st.button("CRIAR LIGA", use_container_width=True):
            if nl:
                novo = pd.DataFrame([{'torneio_id':nl,'formato':'LIGA','fase':'Inscricao','finalizado':'NÃO'}])
                salvar_dados(pd.concat([df_padrao, novo], ignore_index=True), ABA_JOGOS)
                st.session_state.torneio_ativo = nl
                st.session_state.tipo_ativo = "PADRAO"
                st.rerun()
                
    with c2.container(border=True):
        st.markdown("### ⚔️ COPA")
        nc = st.text_input("Nome da Copa")
        mc = st.selectbox("Modo", ["Só Ida", "Ida e Volta"])
        if st.button("CRIAR COPA", use_container_width=True):
            if nc:
                novo = pd.DataFrame([{'torneio_id':nc,'formato':'COPA','modo_copa':mc,'fase':'Inscricao','finalizado':'NÃO'}])
                salvar_dados(pd.concat([df_padrao, novo], ignore_index=True), ABA_JOGOS)
                st.session_state.torneio_ativo = nc
                st.session_state.tipo_ativo = "PADRAO"
                st.rerun()
                
    with c3.container(border=True):
        st.markdown("### ⭐ SUÍÇO (PRO)")
        ns = st.text_input("Nome do Suíço")
        if st.button("CRIAR SUÍÇO", use_container_width=True):
            if ns:
                novo = pd.DataFrame([{'torneio_id':ns, 'formato':'SUICO', 'fase':'Inscricao', 'finalizado':'NÃO'}])
                salvar_dados(pd.concat([df_suico, novo], ignore_index=True), ABA_SUICO)
                st.session_state.torneio_ativo = ns
                st.session_state.tipo_ativo = "SUICO"
                st.rerun()

else:
    tid = st.session_state.torneio_ativo
    tipo = st.session_state.tipo_ativo
    
    with st.sidebar:
        st.header(f"📍 {tid}")
        menu = st.radio("Menu", ["🏟️ Jogos", "📊 Classificação", "⚙️ Admin"])
        if st.button("🏠 Voltar ao Início"): 
            st.session_state.torneio_ativo = None
            st.rerun()

    # ================= MODO SUÍÇO (NOVO) =================
    if tipo == "SUICO":
        df_t = df_suico[df_suico['torneio_id'] == tid].copy()
        
        if menu == "🏟️ Jogos":
            st.subheader("🏟️ Partidas do Torneio Suíço")
            if df_t[df_t['fase'] == 'Suico'].empty:
                st.info("Aguardando sorteio das partidas no Admin.")
            else:
                for idx, r in df_t[df_t['fase'] == 'Suico'].iterrows():
                    with st.container(border=True):
                        c1, c2, c3 = st.columns([2,1,2])
                        c1.markdown(f"**{r['a']}**")
                        c2.markdown(f"<div style='text-align:center'>{r['gols_a']} x {r['gols_b']}</div>", unsafe_allow_html=True)
                        c3.markdown(f"**{r['b']}**")
                        with st.expander("Lançar Placar"):
                            with st.form(f"form_{idx}"):
                                ga, gb = st.columns(2)[0].number_input("A",0,99,int(r['gols_a'])), st.columns(2)[1].number_input("B",0,99,int(r['gols_b']))
                                if st.form_submit_button("Confirmar"):
                                    df_suico.loc[idx, ['gols_a','gols_b','finalizado']] = [ga, gb, "SIM"]
                                    salvar_dados(df_suico, ABA_SUICO); st.rerun()

        elif menu == "📊 Classificação":
            st.subheader("📊 Ranking Suíço (3 Vitórias Classifica)")
            stats = calcular_ranking_suico(df_t)
            if stats:
                df_r = pd.DataFrame(stats).T.sort_values(by=['V', 'Buchholz'], ascending=False)
                st.table(df_r[['V', 'D', 'Buchholz', 'Status']])
            else: st.info("Sem dados.")

        elif menu == "⚙️ Admin":
            st.header("⚙️ Painel Admin Suíço")
            senha_admin = st.text_input("Senha de Acesso", type="password", key="senha_swiss")
            
            if senha_admin == "123": # Verifique se sua senha é 123
                st.success("Acesso Liberado!")
                
                # SEMPRE MOSTRAR OPÇÃO DE EXCLUIR
                if st.button("🚨 EXCLUIR ESTE TORNEIO (RESET)"):
                    df_suico = df_suico[df_suico['torneio_id'] != tid]
                    salvar_dados(df_suico, ABA_SUICO)
                    st.session_state.torneio_ativo = None
                    st.rerun()
                
                st.divider()

                # VERIFICAÇÃO SE JÁ TEM JOGOS
                # Se não houver a coluna 'a' ou se todas as linhas forem nulas na coluna 'a'
                tem_jogos = False
                if 'a' in df_t.columns:
                    if not df_t['a'].dropna().empty:
                        tem_jogos = True

                if not tem_jogos:
                    st.subheader("📝 Registrar Participantes")
                    st.info("Digite um time por linha. O sistema fará o sorteio automático.")
                    txt_times = st.text_area("Lista de Times:", height=250, placeholder="Time A\nTime B\nTime C...")
                    
                    if st.button("🚀 INICIAR E GERAR 1ª RODADA"):
                        lista_times = [x.strip() for x in txt_times.split('\n') if x.strip()]
                        
                        if len(lista_times) < 6:
                            st.error("Erro: Adicione pelo menos 6 times para o Modo Suíço.")
                        elif len(lista_times) > 16:
                            st.error("Erro: O limite máximo é de 16 times.")
                        else:
                            random.shuffle(lista_times)
                            jogos_novos = []
                            for i in range(0, len(lista_times), 2):
                                t1 = lista_times[i]
                                t2 = lista_times[i+1] if i+1 < len(lista_times) else "BYE"
                                
                                # Regra do BYE: Se enfrentar o BYE, já ganha de 1x0 automaticamente
                                status_b = "SIM" if t2 == "BYE" else "NÃO"
                                g_a = 1 if t2 == "BYE" else 0
                                
                                jogos_novos.append({
                                    'torneio_id': tid, 'formato': 'SUICO', 'fase': 'Suico', 
                                    'rodada': 1, 'a': t1, 'b': t2, 
                                    'gols_a': g_a, 'gols_b': 0, 'finalizado': status_b
                                })
                            
                            # Remove linhas de rascunho (Inscrição) e salva os jogos reais
                            df_suico_novo = df_suico[df_suico['torneio_id'] != tid] 
                            df_final = pd.concat([df_suico_novo, pd.DataFrame(jogos_novos)], ignore_index=True)
                            salvar_dados(df_final, ABA_SUICO)
                            st.success("Rodada 1 gerada com sucesso!")
                            st.rerun()
                else:
                    st.warning("⚠️ Este torneio já possui jogos registrados. Use o menu 'Jogos' para editar placares.")
            
            elif senha_admin != "":
                st.error("Senha Incorreta")

    # ================= MODO PADRÃO (LIGA E COPA - MANTIDO) =================
    else:
        df_t = df_padrao[df_padrao['torneio_id'] == tid].copy()
        
        if menu == "🏟️ Jogos":
            st.subheader("🏟️ Tabela de Jogos")
            # ... (Toda a sua lógica original de exibir jogos de Liga e Copa aqui)
            for f in sorted(df_t['fase'].unique()):
                if f == "Inscricao": continue
                st.markdown(f"### {f}")
                for idx, r in df_t[df_t['fase'] == f].iterrows():
                    with st.container(border=True):
                        # Lógica de exibição de gols ida/volta/penalties que você já tinha
                        st.write(f"{r['a']} vs {r['b']}") 

        elif menu == "⚙️ Admin":
            st.header("⚙️ Admin Liga/Copa")
            senha = st.text_input("Senha", type="password")
            if senha == "123":
                # ... (Toda a sua lógica original de gerar Liga e Copa aqui)
                if st.button("EXCLUIR"):
                    salvar_dados(df_padrao[df_padrao['torneio_id'] != tid], ABA_JOGOS)
                    st.session_state.torneio_ativo = None; st.rerun()

