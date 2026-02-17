import streamlit as st
import pandas as pd
import random
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="BAGA GESTOR PRO", layout="wide")

conn = st.connection("gsheets", type=GSheetsConnection)
ABA_JOGOS = "Página1" 
ABA_SUICO = "Suico"
ABA_HISTORICO = "Historico"

def carregar_dados(aba):
    try:
        df = conn.read(worksheet=aba, ttl="0s")
        if df is None or df.empty: return pd.DataFrame()
        df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
        return df.dropna(how='all')
    except: return pd.DataFrame()

def salvar_dados(df, aba):
    if 'torneio_id' in df.columns:
        df = df.dropna(subset=['torneio_id'])
    conn.update(worksheet=aba, data=df)
    st.cache_data.clear()

def calcular_ranking_suico(df_t):
    # Pega todos os times únicos das colunas a e b, ignorando nulos e BYE
    times = set(df_t['a'].dropna().unique()) | set(df_t['b'].dropna().unique())
    if "BYE" in times: times.remove("BYE")
    if not times: return None
    
    stats = {t: {'V':0, 'D':0, 'Jogos': [], 'Buchholz': 0} for t in times}
    jogos_suico = df_t[df_t['fase'] == 'Suico']
    
    for _, r in jogos_suico.iterrows():
        if str(r.get('finalizado')).upper() in ["SIM", "1", "TRUE"]:
            ga, gb = int(r.get('gols_a', 0)), int(r.get('gols_b', 0))
            if ga > gb:
                v, p = r['a'], r['b']
            else:
                v, p = r['b'], r['a']
            if v in stats: stats[v]['V'] += 1; stats[v]['Jogos'].append(p)
            if p in stats: stats[p]['D'] += 1; stats[p]['Jogos'].append(v)
    
    for t in stats:
        stats[t]['Buchholz'] = sum([stats[op]['V'] for op in stats[t]['Jogos'] if op in stats])
        if stats[t]['V'] >= 3: stats[t]['Status'] = "✅ Classificado"
        elif stats[t]['D'] >= 3: stats[t]['Status'] = "❌ Eliminado"
        else: stats[t]['Status'] = "⏳ Ativo"
    return stats

# --- INICIALIZAÇÃO ---
if 'torneio_ativo' not in st.session_state: st.session_state.torneio_ativo = None
if 'tipo_ativo' not in st.session_state: st.session_state.tipo_ativo = None 

df_padrao = carregar_dados(ABA_JOGOS)
df_suico = carregar_dados(ABA_SUICO)
df_hist = carregar_dados(ABA_HISTORICO)

# --- MENU INICIAL ---
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
            if cols[i%3].button(icone + t, key=f"ab_t_{t}", use_container_width=True):
                st.session_state.torneio_ativo = t
                st.session_state.tipo_ativo = "SUICO" if t in ids_s else "PADRAO"
                st.rerun()

    st.divider()
    c1, c2, c3 = st.columns(3)
    with c1:
        n_l = st.text_input("Nova Liga")
        if st.button("CRIAR LIGA"):
            salvar_dados(pd.concat([df_padrao, pd.DataFrame([{'torneio_id':n_l,'formato':'LIGA','fase':'Inscricao'}])]), ABA_JOGOS)
            st.rerun()
    with c3:
        n_s = st.text_input("Novo Suíço")
        if st.button("CRIAR SUÍÇO"):
            salvar_dados(pd.concat([df_suico, pd.DataFrame([{'torneio_id':n_s,'formato':'SUICO','fase':'Inscricao'}])]), ABA_SUICO)
            st.rerun()

else:
    tid = st.session_state.torneio_ativo
    tipo = st.session_state.tipo_ativo
    
    with st.sidebar:
        st.header(f"📍 {tid}")
        menu = st.radio("Menu", ["🏟️ Jogos", "📊 Classificação", "⚙️ Admin"])
        if st.button("🏠 Voltar"): st.session_state.torneio_ativo = None; st.rerun()

    if tipo == "SUICO":
        df_t = df_suico[df_suico['torneio_id'] == tid].copy()
        
        if menu == "🏟️ Jogos":
            jogos = df_t[df_t['fase'] == 'Suico']
            if jogos.empty:
                st.warning("Vá em Admin para sortear os times.")
            else:
                for idx, r in jogos.iterrows():
                    with st.container(border=True):
                        c1, c2, c3 = st.columns([2,1,2])
                        c1.write(f"**{r['a']}**")
                        c2.write(f"{int(r['gols_a'])} x {int(r['gols_b'])}")
                        c3.write(f"**{r['b']}**")
                        with st.expander("Editar"):
                            with st.form(f"f_{idx}"):
                                ga = st.number_input("Gols A", 0, 99, int(r['gols_a']))
                                gb = st.number_input("Gols B", 0, 99, int(r['gols_b']))
                                if st.form_submit_button("Salvar"):
                                    df_suico.loc[idx, ['gols_a', 'gols_b', 'finalizado']] = [ga, gb, "SIM"]
                                    salvar_dados(df_suico, ABA_SUICO); st.rerun()

        elif menu == "📊 Classificação":
            ranking = calcular_ranking_suico(df_t)
            if ranking:
                st.table(pd.DataFrame(ranking).T.sort_values(['V', 'Buchholz'], ascending=False))
            else: st.info("Sem jogos finalizados.")

        elif menu == "⚙️ Admin":
            senha = st.text_input("Senha Admin", type="password")
            if senha == "123":
                # Lógica: Se não houver times na coluna 'a', mostra a caixa de criação
                if df_t['a'].isna().all():
                    st.subheader("🚀 Iniciar Torneio")
                    txt = st.text_area("Times (um por linha)")
                    if st.button("GERAR PARTIDAS"):
                        times = [x.strip() for x in txt.split('\n') if x.strip()]
                        if len(times) >= 6:
                            random.shuffle(times)
                            novos = []
                            for i in range(0, len(times), 2):
                                t1 = times[i]
                                t2 = times[i+1] if i+1 < len(times) else "BYE"
                                novos.append({'torneio_id':tid, 'formato':'SUICO', 'fase':'Suico', 'rodada':1, 'a':t1, 'b':t2, 'gols_a':(1 if t2=='BYE' else 0), 'gols_b':0, 'finalizado':('SIM' if t2=='BYE' else 'NÃO')})
                            # Remove a linha vazia de inscrição e salva os jogos
                            df_suico = df_suico[df_suico['torneio_id'] != tid]
                            salvar_dados(pd.concat([df_suico, pd.DataFrame(novos)], ignore_index=True), ABA_SUICO)
                            st.rerun()
                
                if st.button("🚨 EXCLUIR TORNEIO"):
                    salvar_dados(df_suico[df_suico['torneio_id'] != tid], ABA_SUICO)
                    st.session_state.torneio_ativo = None; st.rerun()
