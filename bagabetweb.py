import streamlit as st
import pandas as pd
from itertools import combinations
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="BAGA BET PRO", layout="wide", page_icon="⚽")
conn = st.connection("gsheets", type=GSheetsConnection)

# --- FUNÇÕES DE SUPORTE ---
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
        if df is None or df.empty:
            return pd.DataFrame(columns=['torneio_id', 'formato', 'fase', 'a', 'b', 'finalizado', 'gols_a', 'gols_b', 'ida_a', 'ida_b', 'volta_a', 'volta_b', 'pen_a', 'pen_b', 'apostas'])
        return df
    except: return pd.DataFrame()

def salvar_db(df):
    df_save = df.loc[:, ~df.columns.str.contains('^Unnamed')]
    conn.update(data=df_save)
    st.cache_data.clear()
    st.toast("Dados sincronizados! ✅")

# --- CARREGAMENTO ---
df_db = carregar_db()

# --- TELA INICIAL ---
if 'torneio_ativo' not in st.session_state:
    st.title("⚽ BAGA BET PRO")
    
    if not df_db.empty and 'torneio_id' in df_db.columns:
        existentes = df_db.dropna(subset=['torneio_id'])
        if not existentes.empty:
            st.subheader("📂 Abrir Torneio")
            t_list = existentes[['torneio_id', 'formato']].drop_duplicates()
            cols = st.columns(3)
            for i, row in enumerate(t_list.values):
                icone = "🏆" if str(row[1]).upper() == "COPA" else "📈"
                if cols[i%3].button(f"{icone} {row[0]}", use_container_width=True):
                    st.session_state.torneio_ativo = row[0]
                    st.session_state.formato = str(row[1]).upper()
                    st.rerun()

    st.divider()
    st.subheader("🆕 Novo Torneio")
    c1, c2 = st.columns(2)
    n_nome = c1.text_input("Nome")
    n_tipo = c2.selectbox("Tipo", ["LIGA", "COPA"])
    if st.button("CRIAR", use_container_width=True):
        if n_nome:
            st.session_state.torneio_ativo = n_nome.strip()
            st.session_state.formato = n_tipo
            st.rerun()

else:
    # --- ÁREA INTERNA ---
    t_id = st.session_state.torneio_ativo
    formato = st.session_state.formato
    jogos_df = df_db[df_db['torneio_id'].astype(str) == str(t_id)].copy()

    with st.sidebar:
        st.header(t_id)
        st.write(f"Modo: **{formato}**")
        menu = st.radio("Menu", ["🏟️ Jogos", "📊 Classificação", "🤑 Ranking", "⚙️ Admin"])
        is_admin = (st.text_input("Senha", type="password") == "1234")
        if st.button("🏠 Sair"):
            for k in list(st.session_state.keys()): del st.session_state[k]
            st.rerun()

    # --- ABA ADMIN (GERADOR) ---
    if menu == "⚙️ Admin":
        if is_admin:
            st.subheader("Gerador de Confrontos")
            times_txt = st.text_area("Times (um por linha)")
            if st.button("GERAR"):
                lista = [t.strip() for t in times_txt.split("\n") if t.strip()]
                novos = []
                if formato == "LIGA":
                    for a, b in combinations(lista, 2):
                        novos.append({"torneio_id":t_id, "formato":"LIGA", "a":a, "b":b, "finalizado":"0", "apostas":""})
                else:
                    for i in range(0, len(lista), 2):
                        if i+1 < len(lista):
                            novos.append({"torneio_id":t_id, "formato":"COPA", "a":lista[i], "b":lista[i+1], "finalizado":"0", "apostas":""})
                
                df_final = pd.concat([df_db[df_db['torneio_id'].astype(str) != str(t_id)], pd.DataFrame(novos)], ignore_index=True)
                salvar_db(df_final); st.rerun()
        else: st.warning("Acesso restrito.")

    # --- ABA JOGOS ---
    elif menu == "🏟️ Jogos":
        if jogos_df.empty: st.info("Gere os jogos no Admin.")
        else:
            for idx, row in jogos_df.iterrows():
                with st.container(border=True):
                    c1, c2, c3 = st.columns([2, 1, 2])
                    c1.markdown(f"<h3 style='text-align:right'>{row['a']}</h3>", unsafe_allow_html=True)
                    
                    if formato == "LIGA":
                        placar = f"{safe_int(row.get('gols_a'))} x {safe_int(row.get('gols_b'))}"
                    else:
                        ia, ib, va, vb = safe_int(row.get('ida_a')), safe_int(row.get('ida_b')), safe_int(row.get('volta_a')), safe_int(row.get('volta_b'))
                        placar = f"({ia}) {va} x {vb} ({ib})"
                    
                    c2.markdown(f"<h2 style='text-align:center; background:#f0f2f6; border-radius:10px;'>{placar}</h2>", unsafe_allow_html=True)
                    c3.markdown(f"<h3>{row['b']}</h3>", unsafe_allow_html=True)

                    # Lançar Resultados
                    if is_admin:
                        with st.expander("📝 Editar Placar"):
                            if formato == "LIGA":
                                ra, rb = st.number_input(f"A", 0, key=f"ra{idx}"), st.number_input(f"B", 0, key=f"rb{idx}")
                                if st.button("Salvar Liga", key=f"sl{idx}"):
                                    df_db.loc[idx, ['gols_a', 'gols_b', 'finalizado']] = [ra, rb, "TRUE"]
                                    salvar_db(df_db); st.rerun()
                            else:
                                ci, cv = st.columns(2)
                                i1, i2 = ci.number_input("Ida A", 0, key=f"i1{idx}"), ci.number_input("Ida B", 0, key=f"i2{idx}")
                                v1, v2 = cv.number_input("Vol A", 0, key=f"v1{idx}"), cv.number_input("Vol B", 0, key=f"v2{idx}")
                                if st.button("Salvar Copa", key=f"sc{idx}"):
                                    df_db.loc[idx, ['ida_a','ida_b','volta_a','volta_b', 'finalizado']] = [i1, i2, v1, v2, "TRUE"]
                                    salvar_db(df_db); st.rerun()

                    # Sistema de Apostas
                    with st.expander("🤑 Apostas"):
                        # Listar Apostas
                        lista_ap = []
                        raw_ap = str(row.get('apostas', ''))
                        if raw_ap and raw_ap != "nan":
                            for item in raw_ap.split("|"):
                                p = item.split(":")
                                if len(p) == 3: lista_ap.append({"Nome": p[0], "R$": float(p[1]), "Palpite": p[2]})
                        
                        if not is_done(row.get('finalizado')):
                            with st.form(f"ap{idx}"):
                                ca1, ca2, ca3 = st.columns([2,1,2])
                                u_nome = ca1.text_input("Nome")
                                u_valor = ca2.number_input("R$", 1, 100, 10)
                                u_opc = ["A", "B", "Empate"] if formato == "LIGA" else ["A", "B"]
                                u_p = ca3.radio("Vencedor:", u_opc, horizontal=True)
                                if st.form_submit_button("Apostar"):
                                    nova = f"{u_nome}:{u_valor}:{u_p}"
                                    txt_final = f"{raw_ap}|{nova}" if raw_ap and raw_ap != "nan" else nova
                                    df_db.loc[idx, 'apostas'] = txt_final
                                    salvar_db(df_db); st.rerun()
                        
                        if lista_ap: st.table(pd.DataFrame(lista_ap))

    # --- ABA CLASSIFICAÇÃO ---
    elif menu == "📊 Classificação":
        if formato == "LIGA":
            stats = {}
            times = pd.concat([jogos_df['a'], jogos_df['b']]).unique()
            for t in times: stats[t] = {"P":0,"J":0,"V":0,"E":0,"D":0,"GP":0,"GC":0}
            for _, r in jogos_df.iterrows():
                if is_done(r.get('finalizado')):
                    ga, gb = safe_int(r['gols_a']), safe_int(r['gols_b'])
                    stats[r['a']]["J"]+=1; stats[r['b']]["J"]+=1
                    stats[r['a']]["GP"]+=ga; stats[r['a']]["GC"]+=gb
                    stats[r['b']]["GP"]+=gb; stats[r['b']]["GC"]+=ga
                    if ga > gb: stats[r['a']]["P"]+=3; stats[r['a']]["V"]+=1; stats[r['b']]["D"]+=1
                    elif gb > ga: stats[r['b']]["P"]+=3; stats[r['b']]["V"]+=1; stats[r['a']]["D"]+=1
                    else: stats[r['a']]["P"]+=1; stats[r['b']]["P"]+=1; stats[r['a']]["E"]+=1; stats[r['b']]["E"]+=1
            
            df_tab = pd.DataFrame.from_dict(stats, orient='index').reset_index().rename(columns={'index':'Time'})
            df_tab['SG'] = df_tab['GP'] - df_tab['GC']
            st.dataframe(df_tab.sort_values(by=["P", "V", "SG"], ascending=False), hide_index=True)
        else:
            st.info("Modo Copa: Acompanhe os resultados nos Jogos.")

    # --- ABA RANKING (FINANCEIRO) ---
    elif menu == "🤑 Ranking":
        st.subheader("💰 Ranking de Apostadores")
        grana = {}
        for _, r in jogos_df.iterrows():
            raw = str(r.get('apostas', ''))
            if raw and raw != "nan" and is_done(r.get('finalizado')):
                # Determinar vencedor real
                if formato == "LIGA":
                    ga, gb = safe_int(r['gols_a']), safe_int(r['gols_b'])
                    vencedor = "A" if ga > gb else "B" if gb > ga else "Empate"
                else:
                    tot_a = safe_int(r['ida_a']) + safe_int(r['volta_a'])
                    tot_b = safe_int(r['ida_b']) + safe_int(r['volta_b'])
                    vencedor = "A" if tot_a > tot_b else "B" # Simplificado: sem empate na copa
                
                for item in raw.split("|"):
                    p = item.split(":")
                    if len(p) == 3:
                        nome, valor, palpite = p[0], float(p[1]), p[2]
                        if nome not in grana: grana[nome] = 0
                        grana[nome] += valor if palpite == vencedor else -valor
        
        if grana:
            df_r = pd.DataFrame.from_dict(grana, orient='index', columns=['Lucro R$']).reset_index()
            df_r = df_r.rename(columns={'index': 'Apostador'}).sort_values(by='Lucro R$', ascending=False)
            st.table(df_r)
        else: st.info("Nenhuma aposta finalizada ainda.")
