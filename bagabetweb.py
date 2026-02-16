import streamlit as st
import pandas as pd
from itertools import combinations
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="BAGA BET PRO", layout="wide", page_icon="⚽")
conn = st.connection("gsheets", type=GSheetsConnection)

COLUNAS_PADRAO = [
    'torneio_id', 'formato', 'fase', 'a', 'b', 'finalizado', 
    'gols_a', 'gols_b', 'ida_a', 'ida_b', 'volta_a', 'volta_b', 
    'pen_a', 'pen_b', 'apostas'
]

# --- FUNÇÕES DE SEGURANÇA ---
def safe_int(val):
    try:
        if pd.isna(val) or val == "" or str(val).lower() == "nan": return 0
        return int(float(val))
    except: return 0

def is_done(val):
    v = str(val).upper().strip()
    return v in ["1", "TRUE", "1.0", "VERDADEIRO"]

def carregar_db():
    st.cache_data.clear()
    try:
        df = conn.read(ttl=0)
        if df is None or df.empty: return pd.DataFrame(columns=COLUNAS_PADRAO)
        for col in COLUNAS_PADRAO:
            if col not in df.columns: df[col] = None
        return df
    except: return pd.DataFrame(columns=COLUNAS_PADRAO)

def salvar_db(df):
    df_save = df.loc[:, ~df.columns.str.contains('^Unnamed')]
    conn.update(data=df_save)
    st.cache_data.clear()
    st.toast("Dados salvos com sucesso! ✅")

# --- CARREGAMENTO ---
df_db = carregar_db()

# --- TELA INICIAL ---
if 'torneio_ativo' not in st.session_state:
    st.title("⚽ BAGA BET PRO")
    
    existentes = df_db.dropna(subset=['torneio_id'])
    if not existentes.empty:
        st.subheader("📂 Seus Torneios")
        t_list = existentes[['torneio_id', 'formato']].drop_duplicates()
        cols = st.columns(3)
        for i, row in enumerate(t_list.values):
            icone = "🏆" if str(row[1]).upper() == "COPA" else "📈"
            if cols[i%3].button(f"{icone} {row[0]}", key=f"t_{i}", use_container_width=True):
                st.session_state.torneio_ativo = row[0]
                st.session_state.formato = str(row[1]).upper()
                st.rerun()

    st.divider()
    st.subheader("🆕 Criar Novo")
    c1, c2 = st.columns(2)
    n_nome = c1.text_input("Nome do Torneio")
    n_tipo = c2.selectbox("Tipo", ["LIGA", "COPA"])
    if st.button("🚀 CRIAR"):
        if n_nome:
            st.session_state.torneio_ativo, st.session_state.formato = n_nome.strip(), n_tipo
            st.rerun()

else:
    t_id = st.session_state.torneio_ativo
    formato = st.session_state.formato
    jogos_df = df_db[df_db['torneio_id'].astype(str) == str(t_id)].copy()

    with st.sidebar:
        st.header(f"⚽ {t_id}")
        menu = st.radio("Menu", ["🏟️ Jogos", "📊 Classificação", "🤑 Ranking", "⚙️ Admin"])
        is_admin = (st.text_input("Senha Admin", type="password") == "1234")
        if st.button("🏠 Sair"):
            for k in list(st.session_state.keys()): del st.session_state[k]
            st.rerun()

    # --- ABA ADMIN (GERADOR COM FASES) ---
    if menu == "⚙️ Admin":
        if is_admin:
            st.subheader("Gerar Novos Jogos")
            fase_nome = st.text_input("Nome da Fase (Ex: Quartas, Semifinal, Final)", "Rodada 1")
            times_txt = st.text_area("Times (um por linha)")
            
            if st.button("🔥 GERAR E ADICIONAR"):
                lista = [t.strip() for t in times_txt.split("\n") if t.strip()]
                novos = []
                if formato == "LIGA":
                    for a, b in combinations(lista, 2):
                        novos.append({"torneio_id":t_id, "formato":"LIGA", "fase":fase_nome, "a":a, "b":b, "finalizado":"0"})
                else:
                    for i in range(0, len(lista), 2):
                        if i+1 < len(lista):
                            novos.append({"torneio_id":t_id, "formato":"COPA", "fase":fase_nome, "a":lista[i], "b":lista[i+1], "finalizado":"0"})
                
                df_final = pd.concat([df_db, pd.DataFrame(novos)], ignore_index=True)
                salvar_db(df_final); st.rerun()
            
            st.divider()
            if st.button("⚠️ APAGAR ESTE TORNEIO"):
                df_clean = df_db[df_db['torneio_id'].astype(str) != str(t_id)]
                salvar_db(df_clean); st.rerun()
        else: st.warning("Acesso restrito.")

    # --- ABA JOGOS (AGRUPADOS POR FASE) ---
    elif menu == "🏟️ Jogos":
        if jogos_df.empty: st.info("Gere jogos no Admin.")
        else:
            fases = jogos_df['fase'].unique()
            for f in fases:
                st.markdown(f"### 📍 {f}")
                jogos_fase = jogos_df[jogos_df['fase'] == f]
                
                for idx, row in jogos_fase.iterrows():
                    with st.container(border=True):
                        c1, c2, c3 = st.columns([2, 1, 2])
                        c1.markdown(f"<p style='text-align:right; font-size:18px;'><b>{row['a']}</b></p>", unsafe_allow_html=True)
                        
                        if formato == "LIGA":
                            placar = f"{safe_int(row.get('gols_a'))} x {safe_int(row.get('gols_b'))}"
                        else:
                            ia, ib, va, vb = safe_int(row.get('ida_a')), safe_int(row.get('ida_b')), safe_int(row.get('volta_a')), safe_int(row.get('volta_b'))
                            placar = f"({ia}) {va} x {vb} ({ib})"
                        
                        c2.markdown(f"<h3 style='text-align:center; background:#f0f2f6; border-radius:10px;'>{placar}</h3>", unsafe_allow_html=True)
                        c3.markdown(f"<p style='text-align:left; font-size:18px;'><b>{row['b']}</b></p>", unsafe_allow_html=True)

                        if is_admin:
                            with st.expander("Lançar Resultado"):
                                if formato == "LIGA":
                                    ra, rb = st.number_input("A", 0, key=f"ra{idx}"), st.number_input("B", 0, key=f"rb{idx}")
                                    if st.button("Confirmar", key=f"bs{idx}"):
                                        df_db.loc[idx, ['gols_a','gols_b','finalizado']] = [ra, rb, "1"]
                                        salvar_db(df_db); st.rerun()
                                else:
                                    ci, cv = st.columns(2)
                                    i1, i2 = ci.number_input("Ida A", 0, key=f"i1{idx}"), ci.number_input("Ida B", 0, key=f"i2{idx}")
                                    v1, v2 = cv.number_input("Vol A", 0, key=f"v1{idx}"), cv.number_input("Vol B", 0, key=f"v2{idx}")
                                    if st.button("Confirmar Copa", key=f"sc{idx}"):
                                        df_db.loc[idx, ['ida_a','ida_b','volta_a','volta_b','finalizado']] = [i1, i2, v1, v2, "1"]
                                        salvar_db(df_db); st.rerun()

                        with st.expander("🤑 Apostar"):
                            raw_ap = str(row.get('apostas', ''))
                            if not is_done(row.get('finalizado')):
                                with st.form(f"f_ap{idx}"):
                                    ca1, ca2, ca3 = st.columns([2,1,2])
                                    u_nome = ca1.text_input("Nome")
                                    u_valor = ca2.number_input("R$", 1, 500, 10)
                                    opcs = ["A", "B", "Empate"] if formato == "LIGA" else ["A", "B"]
                                    u_palp = ca3.radio("Vence:", opcs, horizontal=True)
                                    if st.form_submit_button("Apostar"):
                                        nova = f"{u_nome}:{u_valor}:{u_palp}"
                                        txt = f"{raw_ap}|{nova}" if raw_ap and raw_ap != "nan" else nova
                                        df_db.loc[idx, 'apostas'] = txt
                                        salvar_db(df_db); st.rerun()
                            # Lista apostas
                            if raw_ap and raw_ap != "nan":
                                laps = [item.split(":") for item in raw_ap.split("|") if ":" in item]
                                st.dataframe(pd.DataFrame(laps, columns=["Nome", "R$", "Palpite"]), hide_index=True)

    # --- ABA CLASSIFICAÇÃO ---
    elif menu == "📊 Classificação":
        if formato == "LIGA":
            stats = {}
            times = pd.concat([jogos_df['a'], jogos_df['b']]).unique()
            for t in times: 
                if pd.notna(t): stats[t] = {"P":0,"J":0,"V":0,"E":0,"D":0,"GP":0,"GC":0}
            for _, r in jogos_df.iterrows():
                if is_done(r.get('finalizado')):
                    ga, gb = safe_int(r['gols_a']), safe_int(r['gols_b'])
                    stats[r['a']]["J"]+=1; stats[r['b']]["J"]+=1
                    stats[r['a']]["GP"]+=ga; stats[r['a']]["GC"]+=gb
                    stats[r['b']]["GP"]+=gb; stats[r['b']]["GC"]+=ga
                    if ga > gb: stats[r['a']]["P"]+=3; stats[r['a']]["V"]+=1; stats[r['b']]["D"]+=1
                    elif gb > ga: stats[r['b']]["P"]+=3; stats[r['b']]["V"]+=1; stats[r['a']]["D"]+=1
                    else: stats[r['a']]["P"]+=1; stats[r['b']]["P"]+=1; stats[r['a']]["E"]+=1; stats[r['b']]["E"]+=1
            df_tab = pd.DataFrame.from_dict(stats, orient='index').reset_index().rename(columns={'index':'Equipe'})
            if not df_tab.empty and 'GP' in df_tab.columns:
                df_tab['SG'] = df_tab['GP'] - df_tab['GC']
                st.table(df_tab.sort_values(by=["P", "V", "SG"], ascending=False))
        else: st.info("Modo Copa: Resultados exibidos por fases na aba Jogos.")

    # --- ABA RANKING ---
    elif menu == "🤑 Ranking":
        st.subheader("💰 Lucros")
        grana = {}
        for _, r in jogos_df.iterrows():
            if is_done(r.get('finalizado')):
                if formato == "LIGA":
                    ga, gb = safe_int(r['gols_a']), safe_int(r['gols_b'])
                    venc = "A" if ga > gb else "B" if gb > ga else "Empate"
                else:
                    ta, tb = safe_int(r['ida_a'])+safe_int(r['volta_a']), safe_int(r['ida_b'])+safe_int(r['volta_b'])
                    venc = "A" if ta > tb else "B"
                
                raw = str(r.get('apostas', ''))
                if raw and raw != "nan":
                    for item in raw.split("|"):
                        p = item.split(":")
                        if len(p) == 3:
                            n, v, palp = p[0], float(p[1]), p[2]
                            if n not in grana: grana[n] = 0
                            grana[n] += v if palp == venc else -v
        if grana:
            res = pd.DataFrame.from_dict(grana, orient='index', columns=['Saldo R$']).reset_index()
            st.table(res.rename(columns={'index':'Nome'}).sort_values(by='Saldo R$', ascending=False))
