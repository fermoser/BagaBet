import streamlit as st
import pandas as pd
from itertools import combinations
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="GESTOR PRO", layout="wide", page_icon="⚽")
conn = st.connection("gsheets", type=GSheetsConnection)

COLUNAS = [
    'torneio_id', 'formato', 'fase', 'a', 'b', 'finalizado',
    'gols_a', 'gols_b', 'ida_a', 'ida_b', 'volta_a', 'volta_b', 'pen_a', 'pen_b'
]

# --- FUNÇÕES ---
def safe_int(val):
    try:
        if pd.isna(val) or val == "" or str(val).lower() == "nan": return 0
        return int(float(val))
    except: return 0

def is_done(val):
    v = str(val).upper().strip()
    return v in ["1", "TRUE", "SIM", "VERDADEIRO", "1.0"]

def carregar_db():
    st.cache_data.clear()
    try:
        df = conn.read(ttl=0)
        if df is None or df.empty: return pd.DataFrame(columns=COLUNAS)
        for c in COLUNAS:
            if c not in df.columns: df[c] = None
        return df.loc[:, ~df.columns.str.contains('^Unnamed')]
    except: return pd.DataFrame(columns=COLUNAS)

def salvar_db(df):
    df_save = df[COLUNAS].copy()
    conn.update(data=df_save)
    st.cache_data.clear()
    st.toast("✅ Dados Sincronizados!")
    st.rerun() # Força a atualização da tela

# --- INICIALIZAÇÃO ---
df_db = carregar_db()

if 'torneio_ativo' not in st.session_state:
    st.title("⚽ BAGA BET GESTOR")
    
    existentes = df_db.dropna(subset=['torneio_id'])
    if not existentes.empty:
        st.subheader("📂 Abrir Campeonato")
        ts = existentes[['torneio_id', 'formato']].drop_duplicates()
        cols = st.columns(3)
        for i, row in enumerate(ts.values):
            if cols[i%3].button(f"{row[0]} ({row[1]})", key=f"t_{i}", use_container_width=True):
                st.session_state.torneio_ativo = row[0]
                st.session_state.formato = str(row[1]).upper()
                st.rerun()
    
    st.divider()
    st.subheader("🆕 Criar Novo")
    with st.form("novo_t"):
        c1, c2 = st.columns(2)
        nn = c1.text_input("Nome")
        nt = c2.selectbox("Tipo", ["LIGA", "COPA"])
        if st.form_submit_button("CRIAR"):
            if nn:
                st.session_state.torneio_ativo, st.session_state.formato = nn.strip(), nt
                st.rerun()
else:
    tid = st.session_state.torneio_ativo
    fmt = st.session_state.formato
    df_t = df_db[df_db['torneio_id'].astype(str) == str(tid)].copy()

    with st.sidebar:
        st.header(f"🏆 {tid}")
        menu = st.radio("Navegação", ["🏟️ Jogos", "📊 Classificação/Ranking", "⚙️ Admin"])
        is_admin = (st.text_input("Senha Admin", type="password") == "1234")
        if st.button("🏠 Sair"):
            st.session_state.clear()
            st.rerun()

    if menu == "⚙️ Admin":
        if is_admin:
            # GERAR INICIAL
            with st.expander("🚀 Iniciar / Adicionar Jogos"):
                times_txt = st.text_area("Times (um por linha)")
                f_nome = st.text_input("Nome da Fase", "Rodada 1")
                if st.button("Gerar Confrontos"):
                    lista = [t.strip() for t in times_txt.split('\n') if t.strip()]
                    novos = []
                    if fmt == "LIGA":
                        for a, b in combinations(lista, 2):
                            novos.append({'torneio_id': tid, 'formato': 'LIGA', 'fase': f_nome, 'a': a, 'b': b, 'finalizado': '0'})
                    else:
                        for i in range(0, len(lista), 2):
                            if i+1 < len(lista):
                                novos.append({'torneio_id': tid, 'formato': 'COPA', 'fase': f_nome, 'a': lista[i], 'b': lista[i+1], 'finalizado': '0'})
                    salvar_db(pd.concat([df_db, pd.DataFrame(novos)], ignore_index=True))

            # AVANÇAR FASE (COPA)
            if fmt == "COPA" and not df_t.empty:
                st.divider()
                st.subheader("⏩ Avançar para Próxima Fase")
                f_origem = st.selectbox("Basear nos vencedores de:", df_t['fase'].unique())
                f_destino = st.text_input("Nome da Nova Fase", "Semifinal")
                
                if st.button("Gerar Chaveamento"):
                    vencs = []
                    jogos_f = df_t[df_t['fase'] == f_origem]
                    for _, r in jogos_f.iterrows():
                        if is_done(r['finalizado']):
                            sa = safe_int(r['ida_a']) + safe_int(r['volta_a'])
                            sb = safe_int(r['ida_b']) + safe_int(r['volta_b'])
                            if sa > sb: vencs.append(r['a'])
                            elif sb > sa: vencs.append(r['b'])
                            else:
                                pa, pb = safe_int(r['pen_a']), safe_int(r['pen_b'])
                                vencs.append(r['a'] if pa > pb else r['b'])
                    
                    if len(vencs) >= 2:
                        proximos = []
                        for i in range(0, len(vencs), 2):
                            if i+1 < len(vencs):
                                proximos.append({'torneio_id': tid, 'formato': 'COPA', 'fase': f_destino, 'a': vencs[i], 'b': vencs[i+1], 'finalizado': '0'})
                        salvar_db(pd.concat([df_db, pd.DataFrame(proximos)], ignore_index=True))
                    else: st.error("Finalize os jogos primeiro!")

            st.divider()
            if st.button("🚨 EXCLUIR CAMPEONATO"):
                salvar_db(df_db[df_db['torneio_id'].astype(str) != str(tid)])
        else: st.warning("Acesse com a senha para gerenciar.")

    elif menu == "🏟️ Jogos":
        if df_t.empty: st.info("Sem jogos.")
        else:
            for fase in df_t['fase'].unique():
                st.markdown(f"#### 📍 {fase}")
                for idx, row in df_t[df_t['fase'] == fase].iterrows():
                    with st.container(border=True):
                        c1, c2, c3 = st.columns([2,1,2])
                        if fmt == "LIGA":
                            pl = f"{safe_int(row['gols_a'])} x {safe_int(row['gols_b'])}"
                        else:
                            sa, sb = safe_int(row['ida_a'])+safe_int(row['volta_a']), safe_int(row['ida_b'])+safe_int(row['volta_b'])
                            pl = f"({safe_int(row['ida_a'])}) {safe_int(row['volta_a'])} x {safe_int(row['volta_b'])} ({safe_int(row['ida_b'])})"
                            if sa == sb and is_done(row['finalizado']):
                                pl += f" P:{safe_int(row['pen_a'])}x{safe_int(row['pen_b'])}"
                        
                        c1.markdown(f"<p style='text-align:right'><b>{row['a']}</b></p>", unsafe_allow_html=True)
                        c2.markdown(f"<div style='text-align:center; background:#eee; border-radius:5px;'>{pl}</div>", unsafe_allow_html=True)
                        c3.markdown(f"<p style='text-align:left'><b>{row['b']}</b></p>", unsafe_allow_html=True)

                        if is_admin:
                            with st.expander("Editar"):
                                with st.form(f"ed_{idx}"):
                                    if fmt == "LIGA":
                                        ga, gb = st.number_input("A", 0, value=safe_int(row['gols_a'])), st.number_input("B", 0, value=safe_int(row['gols_b']))
                                        if st.form_submit_button("Salvar"):
                                            df_db.loc[idx, ['gols_a','gols_b','finalizado']] = [ga, gb, "SIM"]
                                            salvar_db(df_db)
                                    else:
                                        col1, col2 = st.columns(2)
                                        i1 = col1.number_input("Ida A", 0, value=safe_int(row['ida_a']))
                                        i2 = col1.number_input("Ida B", 0, value=safe_int(row['ida_b']))
                                        v1 = col2.number_input("Volta A", 0, value=safe_int(row['volta_a']))
                                        v2 = col2.number_input("Volta B", 0, value=safe_int(row['volta_b']))
                                        p1, p2 = 0, 0
                                        if (i1+v1) == (i2+v2):
                                            st.caption("Empate! Pênaltis:")
                                            p1 = st.number_input("Pên A", 0, value=safe_int(row['pen_a']))
                                            p2 = st.number_input("Pên B", 0, value=safe_int(row['pen_b']))
                                        if st.form_submit_button("Salvar Placar"):
                                            df_db.loc[idx, ['ida_a','ida_b','volta_a','volta_b','pen_a','pen_b','finalizado']] = [i1, i2, v1, v2, p1, p2, "SIM"]
                                            salvar_db(df_db)

    elif menu == "📊 Classificação/Ranking":
        if fmt == "LIGA":
            st.header("Tabela da Liga")
            times = pd.concat([df_t['a'], df_t['b']]).unique()
            stats = {t: {'P':0, 'J':0, 'V':0, 'E':0, 'D':0, 'GP':0, 'GC':0} for t in times if pd.notna(t)}
            for _, r in df_t.iterrows():
                if is_done(r['finalizado']):
                    t1, t2, g1, g2 = r['a'], r['b'], safe_int(r['gols_a']), safe_int(r['gols_b'])
                    stats[t1]['J']+=1; stats[t2]['J']+=1
                    stats[t1]['GP']+=g1; stats[t1]['GC']+=g2
                    stats[t2]['GP']+=g2; stats[t2]['GC']+=g1
                    if g1 > g2: stats[t1]['P']+=3; stats[t1]['V']+=1; stats[t2]['D']+=1
                    elif g2 > g1: stats[t2]['P']+=3; stats[t2]['V']+=1; stats[t1]['D']+=1
                    else: stats[t1]['P']+=1; stats[t2]['P']+=1; stats[t1]['E']+=1; stats[t2]['E']+=1
            df_c = pd.DataFrame.from_dict(stats, orient='index').reset_index().rename(columns={'index':'Time'})
            df_c['SG'] = df_c['GP'] - df_c['GC']
            st.table(df_c.sort_values(by=['P','V','SG'], ascending=False))
        else:
            st.info("No modo COPA, acompanhe os vencedores diretamente na aba JOGOS.")
