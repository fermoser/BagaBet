import streamlit as st
import pandas as pd
import random
from itertools import combinations
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="BAGA BET PRO", layout="wide", page_icon="⚽")
conn = st.connection("gsheets", type=GSheetsConnection)

# --- TRATAMENTO DE DADOS ---
def para_int(val):
    try:
        if pd.isna(val) or val == "" or str(val).lower() == "nan": return 0
        return int(float(val))
    except: return 0

def ta_finalizado(val):
    v = str(val).upper().strip()
    return v in ["1", "TRUE", "1.0", "VERDADEIRO"]

def carregar_dados():
    try:
        st.cache_data.clear()
        df = conn.read(ttl=0)
        return df if df is not None else pd.DataFrame()
    except: return pd.DataFrame()

def salvar_dados(df_novo):
    # Garante que não salvamos colunas fantasmas
    df_save = df_novo.loc[:, ~df_novo.columns.str.contains('^Unnamed')]
    conn.update(data=df_save)
    st.cache_data.clear()

# --- INTERFACE INICIAL ---
df_atual = carregar_dados()

if 'torneio_ativo' not in st.session_state:
    st.title("⚽ BAGA BET PRO")
    
    if not df_atual.empty and 'torneio_id' in df_atual.columns:
        t_list = df_atual.dropna(subset=['torneio_id'])[['torneio_id', 'formato']].drop_duplicates()
        if not t_list.empty:
            st.subheader("📂 Abrir Torneio")
            cols = st.columns(3)
            for i, row in enumerate(t_list.values):
                label = f"{'🏆' if str(row[1]).upper()=='COPA' else '📈'} {row[0]}"
                if cols[i%3].button(label, use_container_width=True):
                    st.session_state.torneio_ativo = row[0]
                    st.session_state.formato = str(row[1]).upper()
                    st.rerun()

    st.divider()
    with st.expander("🆕 Criar Novo Torneio"):
        c1, c2 = st.columns(2)
        n_id = c1.text_input("Nome do Torneio")
        n_tp = c2.selectbox("Tipo", ["LIGA", "COPA"])
        if st.button("CRIAR"):
            if n_id:
                st.session_state.torneio_ativo, st.session_state.formato = n_id.strip(), n_tp
                st.rerun()

else:
    # --- AMBIENTE DO TORNEIO ---
    t_id = st.session_state.torneio_ativo
    formato = st.session_state.formato
    jogos_df = df_atual[df_atual['torneio_id'].astype(str) == str(t_id)].copy()

    with st.sidebar:
        st.header(f"⚽ {t_id}")
        st.write(f"Modo: **{formato}**")
        menu = st.radio("Menu", ["🏟️ Jogos", "📊 Classificação", "🤑 Ranking", "⚙️ Admin"])
        is_admin = (st.text_input("Senha Admin", type="password") == "1234")
        if st.button("🏠 Sair"):
            for k in list(st.session_state.keys()): del st.session_state[k]
            st.rerun()

    # --- ABA JOGOS ---
    if menu == "🏟️ Jogos":
        if jogos_df.empty:
            st.info("Nenhum jogo gerado. Vá em Admin.")
        else:
            for idx, row in jogos_df.iterrows():
                with st.container(border=True):
                    c1, c2, c3 = st.columns([2, 1, 2])
                    c1.markdown(f"<div style='text-align:right'><b>{row['a']}</b></div>", unsafe_allow_html=True)
                    
                    if formato == "LIGA":
                        txt = f"{para_int(row.get('gols_a'))} x {para_int(row.get('gols_b'))}"
                    else:
                        ia, ib = para_int(row.get('ida_a')), para_int(row.get('ida_b'))
                        va, vb = para_int(row.get('volta_a')), para_int(row.get('volta_b'))
                        txt = f"({ia}) {va} x {vb} ({ib})"
                    
                    c2.markdown(f"<h3 style='text-align:center; background:#eee; border-radius:5px;'>{txt}</h3>", unsafe_allow_html=True)
                    c3.markdown(f"<div><b>{row['b']}</b></div>", unsafe_allow_html=True)

                    if is_admin:
                        with st.expander("📝 Editar Placar"):
                            if formato == "LIGA":
                                ra = st.number_input(f"Gols {row['a']}", 0, key=f"la{idx}")
                                rb = st.number_input(f"Gols {row['b']}", 0, key=f"lb{idx}")
                                if st.button("Salvar Liga", key=f"sl{idx}"):
                                    df_atual.loc[idx, ['gols_a', 'gols_b', 'finalizado']] = [ra, rb, "TRUE"]
                                    salvar_dados(df_atual); st.rerun()
                            else:
                                col_ida, col_volta = st.columns(2)
                                i_a = col_ida.number_input("Ida A", 0, key=f"ia{idx}")
                                i_b = col_ida.number_input("Ida B", 0, key=f"ib{idx}")
                                v_a = col_volta.number_input("Volta A", 0, key=f"va{idx}")
                                v_b = col_volta.number_input("Volta B", 0, key=f"vb{idx}")
                                if st.button("Salvar Copa", key=f"sc{idx}"):
                                    df_atual.loc[idx, ['ida_a','ida_b','volta_a','volta_b','finalizado']] = [i_a, i_b, v_a, v_b, "TRUE"]
                                    salvar_dados(df_atual); st.rerun()

                    # --- SISTEMA DE APOSTAS ---
                    with st.expander("🤑 Apostas"):
                        # Processar apostas atuais
                        aps = []
                        raw_aps = str(row.get('apostas', ''))
                        if raw_aps and raw_aps != "nan":
                            for a_item in raw_aps.split("|"):
                                p = a_item.split(":")
                                if len(p) == 3: aps.append({"Nome": p[0], "R$": float(p[1]), "Palpite": p[2]})
                        
                        if not ta_finalizado(row.get('finalizado')):
                            with st.form(f"form_ap{idx}"):
                                c_n, c_v, c_p = st.columns([2,1,2])
                                u_nome = c_n.text_input("Nome")
                                u_valor = c_v.number_input("R$", 1, 1000, 10)
                                u_opc = ["A", "B", "Empate"] if formato == "LIGA" else ["A", "B"]
                                u_palpite = c_p.radio("Vence:", u_opc, horizontal=True)
                                if st.form_submit_button("Apostar"):
                                    nova_ap = f"{u_nome}:{u_valor}:{u_palpite}"
                                    string_final = f"{raw_aps}|{nova_ap}" if raw_aps and raw_aps != "nan" else nova_ap
                                    df_atual.loc[idx, 'apostas'] = string_final
                                    salvar_dados(df_atual); st.rerun()
                        
                        if aps: st.dataframe(pd.DataFrame(aps), use_container_width=True, hide_index=True)

    # --- ABA CLASSIFICAÇÃO ---
    elif menu == "📊 Classificação":
        if formato == "LIGA":
            st.subheader("Tabela de Pontos")
            stats = {}
            times = pd.concat([jogos_df['a'], jogos_df['b']]).unique()
            for t in times:
                if pd.notna(t): stats[t] = {"P":0,"J":0,"V":0,"E":0,"D":0,"GP":0,"GC":0}
            
            for _, r in jogos_df.iterrows():
                if ta_finalizado(r.get('finalizado')):
                    ga, gb = para_int(r['gols_a']), para_int(r['gols_b'])
                    t1, t2 = r['a'], r['b']
                    stats[t1]["J"]+=1; stats[t2]["J"]+=1
                    stats[t1]["GP"]+=ga; stats[t1]["GC"]+=gb
                    stats[t2]["GP"]+=gb; stats[t2]["GC"]+=ga
                    if ga > gb: stats[t1]["P"]+=3; stats[t1]["V"]+=1; stats[t2]["D"]+=1
                    elif gb > ga: stats[t2]["P"]+=3; stats[t2]["V"]+=1; stats[t1]["D"]+=1
                    else: stats[t1]["P"]+=1; stats[t2]["P"]+=1; stats[t1]["E"]+=1; stats[t2]["E"]+=1
            
            df_tab = pd.DataFrame.from_dict(stats, orient='index').reset_index().rename(columns={'index':'Time'})
            if not df_tab.empty:
                df_tab['SG'] = df_tab['GP'] - df_tab['GC']
                st.dataframe(df_tab.sort_values(by=["P", "V", "SG"], ascending=False), hide_index=True)
        else:
            st.info("Modo Copa: Acompanhe os resultados agregados nos cards de jogos.")

    # --- ABA ADMIN ---
    elif menu == "⚙️ Admin" and is_admin:
        st.subheader("Gerador de Jogos")
        times_input = st.text_area("Lista de Equipes (uma por linha)")
        if st.button("GERAR CONFRONTOS"):
            lista_t = [t.strip() for t in times_input.split("\n") if t.strip()]
            novos = []
            if formato == "LIGA":
                for a, b in combinations(lista_t, 2):
                    novos.append({"torneio_id":t_id, "formato":"LIGA", "a":a, "b":b, "finalizado":"FALSE"})
            else:
                for i in range(0, len(lista_t), 2):
                    if i+1 < len(lista_t):
                        novos.append({"torneio_id":t_id, "formato":"COPA", "a":lista_t[i], "b":lista_t[i+1], "finalizado":"FALSE"})
            
            df_final = pd.concat([df_atual[df_atual['torneio_id'].astype(str) != str(t_id)], pd.DataFrame(novos)], ignore_index=True)
            salvar_dados(df_final); st.rerun()
