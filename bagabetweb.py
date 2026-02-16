import streamlit as st
import pandas as pd
import random
from itertools import combinations
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="BAGA BET PRO", layout="wide", page_icon="⚽")
conn = st.connection("gsheets", type=GSheetsConnection)

# --- ESTILIZAÇÃO ---
st.markdown("""
    <style>
    .placar-box { background: #f8f9fa; border: 2px solid #333; border-radius: 10px; padding: 10px; text-align: center; }
    .fase-header { background: #000; color: #fff; padding: 10px; border-radius: 5px; text-align: center; margin: 15px 0; }
    .equipe-nome { font-size: 1.2rem; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# --- FUNÇÕES DE DADOS ---
def carregar_db():
    try:
        st.cache_data.clear()
        df = conn.read(ttl=0)
        if df is None: return pd.DataFrame()
        return df.dropna(how='all')
    except: return pd.DataFrame()

def salvar_db(df_novo):
    conn.update(data=df_novo)
    st.cache_data.clear()

def money(v):
    cor = "#28a745" if v > 0 else "#dc3545" if v < 0 else "#212529"
    val = f"R$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f'<span style="color:{cor}; font-weight:bold;">{val}</span>'

# --- TELA INICIAL ---
df_atual = carregar_db()

if 'torneio_ativo' not in st.session_state:
    st.title("⚽ BAGA BET PRO")
    
    if not df_atual.empty and 'torneio_id' in df_atual.columns:
        st.subheader("📂 Abrir Torneio")
        torneios = df_atual[['torneio_id', 'formato']].dropna().drop_duplicates()
        cols = st.columns(3)
        for i, row in enumerate(torneios.values):
            if cols[i%3].button(f"{'🏆' if row[1]=='COPA' else '📈'} {row[0]}", use_container_width=True):
                st.session_state.torneio_ativo = row[0]
                st.session_state.formato = row[1]
                st.rerun()

    st.divider()
    with st.expander("🆕 Criar Novo Torneio"):
        c1, c2 = st.columns(2)
        n_id = c1.text_input("Nome do Torneio")
        n_tp = c2.selectbox("Tipo", ["LIGA", "COPA"])
        if st.button("GERAR NOVO"):
            st.session_state.torneio_ativo, st.session_state.formato = n_id, n_tp
            st.rerun()

else:
    # --- VARIÁVEIS DO TORNEIO ATIVO ---
    t_id = st.session_state.torneio_ativo
    formato = st.session_state.formato
    # Filtra os jogos específicos deste torneio
    jogos_df = df_atual[df_atual['torneio_id'] == t_id].copy()

    with st.sidebar:
        st.header(t_id)
        st.write(f"Modo: **{formato}**")
        menu = st.radio("Navegação", ["🏟️ Jogos", "📊 Classificação", "🤑 Ranking", "⚙️ Admin"])
        is_admin = (st.text_input("Chave", type="password") == "1234")
        if st.button("🏠 Sair"):
            for k in list(st.session_state.keys()): del st.session_state[k]
            st.rerun()

    # --- ABA JOGOS (Onde a mágica da inserção acontece) ---
    if menu == "🏟️ Jogos":
        if jogos_df.empty:
            st.info("Nenhum jogo. Vá em Admin para gerar.")
        else:
            for idx, row in jogos_df.iterrows():
                with st.container(border=True):
                    c1, c2, c3 = st.columns([2, 1, 2])
                    c1.markdown(f"<div style='text-align:right' class='equipe-nome'>{row['a']}</div>", unsafe_allow_html=True)
                    
                    # Exibição do Placar conforme o Modo
                    if formato == "LIGA":
                        val_a = int(row['gols_a']) if pd.notna(row.get('gols_a')) else "-"
                        val_b = int(row['gols_b']) if pd.notna(row.get('gols_b')) else "-"
                        txt_placar = f"{val_a} x {val_b}"
                    else:
                        ia, ib = (int(row['ida_a']) if pd.notna(row.get('ida_a')) else 0), (int(row['ida_b']) if pd.notna(row.get('ida_b')) else 0)
                        va, vb = (int(row['volta_a']) if pd.notna(row.get('volta_a')) else 0), (int(row['volta_b']) if pd.notna(row.get('volta_b')) else 0)
                        txt_placar = f"({ia}) {va} x {vb} ({ib})"
                    
                    c2.markdown(f"<div class='placar-box'>{txt_placar}</div>", unsafe_allow_html=True)
                    c3.markdown(f"<div class='equipe-nome'>{row['b']}</div>", unsafe_allow_html=True)

                    if is_admin:
                        with st.expander("📝 Editar Placar"):
                            if formato == "LIGA":
                                res_a = st.number_input(f"Gols {row['a']}", 0, 20, key=f"la{idx}")
                                res_b = st.number_input(f"Gols {row['b']}", 0, 20, key=f"lb{idx}")
                                if st.button("Salvar Liga", key=f"bsl{idx}"):
                                    df_atual.loc[idx, ['gols_a', 'gols_b', 'finalizado']] = [res_a, res_b, "TRUE"]
                                    salvar_db(df_atual); st.rerun()
                            else:
                                col_i, col_v = st.columns(2)
                                i_a = col_i.number_input("Ida A", 0, key=f"ia{idx}")
                                i_b = col_i.number_input("Ida B", 0, key=f"ib{idx}")
                                v_a = col_v.number_input("Volta A", 0, key=f"va{idx}")
                                v_b = col_v.number_input("Volta B", 0, key=f"vb{idx}")
                                p_a, p_b = 0, 0
                                if (i_a + v_a) == (i_b + v_b):
                                    p_a = st.number_input("Pen A", 0, key=f"pa{idx}")
                                    p_b = st.number_input("Pen B", 0, key=f"pb{idx}")
                                if st.button("Salvar Copa", key=f"bsc{idx}"):
                                    df_atual.loc[idx, ['ida_a','ida_b','volta_a','volta_b','pen_a','pen_b','finalizado']] = [i_a, i_b, v_a, v_b, p_a, p_b, "TRUE"]
                                    salvar_db(df_atual); st.rerun()

    # --- ABA CLASSIFICAÇÃO (Cálculo em Tempo Real) ---
    elif menu == "📊 Classificação":
        if formato == "LIGA":
            stats = {}
            for _, r in jogos_df.iterrows():
                for t in [r['a'], r['b']]:
                    if t not in stats: stats[t] = {"P":0,"J":0,"V":0,"E":0,"D":0,"GP":0,"GC":0}
                if str(r.get('finalizado')).upper() == "TRUE":
                    ga, gb = int(r['gols_a']), int(r['gols_b'])
                    stats[r['a']]["J"]+=1; stats[r['b']]["J"]+=1
                    stats[r['a']]["GP"]+=ga; stats[r['a']]["GC"]+=gb
                    stats[r['b']]["GP"]+=gb; stats[r['b']]["GC"]+=ga
                    if ga > gb: stats[r['a']]["P"]+=3; stats[r['a']]["V"]+=1; stats[r['b']]["D"]+=1
                    elif gb > ga: stats[r['b']]["P"]+=3; stats[r['b']]["V"]+=1; stats[r['a']]["D"]+=1
                    else: stats[r['a']]["P"]+=1; stats[r['b']]["P"]+=1; stats[r['a']]["E"]+=1; stats[r['b']]["E"]+=1
            
            df_tab = pd.DataFrame.from_dict(stats, orient='index').reset_index().rename(columns={'index':'Time'})
            st.table(df_tab.sort_values(by=["P", "V"], ascending=False))
        else:
            st.info("Modo Copa: Placar Agregado disponível na aba de Jogos.")

    # --- ABA ADMIN (Gerador de Estrutura) ---
    elif menu == "⚙️ Admin" and is_admin:
        st.subheader("⚠️ Zona de Perigo")
        with st.form("gerador"):
            lista_times = st.text_area("Lista de Equipes (um por linha)")
            if st.form_submit_button("🔥 RESETAR E GERAR NOVOS JOGOS"):
                times = [t.strip() for t in lista_times.split("\n") if t.strip()]
                novos_jogos = []
                if formato == "LIGA":
                    for a, b in combinations(times, 2):
                        novos_jogos.append({"torneio_id":t_id, "formato":"LIGA", "a":a, "b":b, "fase":"Única", "finalizado":"FALSE"})
                else:
                    for i in range(0, len(times), 2):
                        novos_jogos.append({"torneio_id":t_id, "formato":"COPA", "a":times[i], "b":times[i+1], "fase":"Mata-Mata", "finalizado":"FALSE"})
                
                df_novos = pd.DataFrame(novos_jogos)
                # Mantém os outros torneios e adiciona os novos jogos deste
                df_final = pd.concat([df_atual[df_atual['torneio_id'] != t_id], df_novos], ignore_index=True)
                salvar_db(df_final)
                st.rerun()
