import streamlit as st
import pandas as pd
from itertools import combinations
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="BAGA GESTOR PRO", layout="wide")
conn = st.connection("gsheets", type=GSheetsConnection)

COLUNAS = [
    'torneio_id', 'formato', 'fase', 'a', 'b', 'finalizado',
    'gols_a', 'gols_b', 'ida_a', 'ida_b', 'volta_a', 'volta_b', 'pen_a', 'pen_b', 'modo_copa'
]

# --- FUNÇÕES ---
def carregar_dados():
    st.cache_data.clear()
    try:
        df = conn.read(ttl=0)
        if df is None or df.empty: return pd.DataFrame(columns=COLUNAS)
        for c in COLUNAS:
            if c not in df.columns: df[c] = None
        cols_n = ['gols_a', 'gols_b', 'ida_a', 'ida_b', 'volta_a', 'volta_b', 'pen_a', 'pen_b']
        for col in cols_n:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
        return df.loc[:, ~df.columns.str.contains('^Unnamed')]
    except: return pd.DataFrame(columns=COLUNAS)

def salvar_dados(df):
    conn.update(data=df[COLUNAS].copy())
    st.cache_data.clear()
    st.rerun()

def is_done(val):
    return str(val).upper().strip() in ["1", "SIM", "TRUE"]

def obter_vencedor(r):
    if not is_done(r['finalizado']): return "---", ""
    if r['fase'] in ["Final", "3º Lugar"] or r['modo_copa'] == "Só Ida":
        sa, sb = r['gols_a'], r['gols_b']
    else:
        sa, sb = r['ida_a'] + r['volta_a'], r['ida_b'] + r['volta_b']
    if sa > sb: return r['a'], r['b']
    if sb > sa: return r['b'], r['a']
    return (r['a'], r['b']) if int(r['pen_a']) > int(r['pen_b']) else (r['b'], r['a'])

# --- INTERFACE ---
df_db = carregar_dados()

if 'torneio_ativo' not in st.session_state:
    st.title("⚽ BAGA GESTOR")
    ts = df_db.dropna(subset=['torneio_id'])[['torneio_id', 'formato']].drop_duplicates()
    if not ts.empty:
        st.subheader("📂 Abrir Torneio")
        cols = st.columns(3)
        for i, row in enumerate(ts.values):
            if cols[i%3].button(f"{row[0]} ({row[1]})", key=f"t_{i}", use_container_width=True):
                st.session_state.torneio_ativo, st.session_state.formato = row[0], row[1]
                st.rerun()
    st.divider()
    with st.form("novo"):
        c1, c2, c3 = st.columns(3)
        nn, nt, nm = c1.text_input("Nome"), c2.selectbox("Tipo", ["LIGA", "COPA"]), c3.selectbox("Modo", ["Ida e Volta", "Só Ida"])
        if st.form_submit_button("CRIAR"):
            if nn: st.session_state.torneio_ativo, st.session_state.formato, st.session_state.modo = nn.strip(), nt, nm; st.rerun()

else:
    tid, fmt = st.session_state.torneio_ativo, st.session_state.formato
    df_t = df_db[df_db['torneio_id'].astype(str) == str(tid)].copy()

    with st.sidebar:
        st.header(f"🏆 {tid}")
        menu = st.radio("Menu", ["🏟️ Jogos", "📊 Chaveamento & Pódio", "⚙️ Admin"])
        is_admin = (st.text_input("Senha Admin", type="password") == "1234")
        if st.button("🏠 Sair"): st.session_state.clear(); st.rerun()

    # --- JOGOS ---
    if menu == "🏟️ Jogos":
        if df_t.empty: st.info("Sem jogos.")
        else:
            # Auto-progressão (mesma lógica anterior)
            if fmt == "COPA":
                ultima_fase = df_t['fase'].unique()[-1]
                jogos_fase = df_t[df_t['fase'] == ultima_fase]
                if all(is_done(x) for x in jogos_fase['finalizado']) and ultima_fase not in ["Final", "3º Lugar"]:
                    vencs, perds = [], []
                    for _, r in jogos_fase.iterrows():
                        v, p = obter_vencedor(r)
                        vencs.append(v); perds.append(p)
                    nova = "Final" if len(vencs) == 2 else "Semifinal" if len(vencs) == 4 else "Quartas"
                    proxs = []
                    modo_atual = df_t['modo_copa'].iloc[0]
                    if nova == "Final":
                        proxs.append({'torneio_id': tid, 'formato': 'COPA', 'fase': '3º Lugar', 'a': perds[0], 'b': perds[1], 'finalizado': '0', 'modo_copa': 'Jogo Único'})
                        proxs.append({'torneio_id': tid, 'formato': 'COPA', 'fase': 'Final', 'a': vencs[0], 'b': vencs[1], 'finalizado': '0', 'modo_copa': 'Jogo Único'})
                    else:
                        for i in range(0, len(vencs), 2):
                            proxs.append({'torneio_id': tid, 'formato': 'COPA', 'fase': nova, 'a': vencs[i], 'b': vencs[i+1], 'finalizado': '0', 'modo_copa': modo_atual})
                    salvar_dados(pd.concat([df_db, pd.DataFrame(proxs)], ignore_index=True))

            fases_ordem = sorted(df_t['fase'].unique(), key=lambda x: 1 if x == "Final" else 0)
            for fase in fases_ordem:
                st.subheader(f"📍 {fase}")
                for idx, row in df_t[df_t['fase'] == fase].iterrows():
                    with st.container(border=True):
                        c1, c2, c3 = st.columns([2,1,2])
                        txt_pl = f"{row['gols_a']} x {row['gols_b']}" if (row['modo_copa'] == "Só Ida" or row['fase'] in ["Final", "3º Lugar"]) else f"({row['ida_a']}) {row['volta_a']} x {row['volta_b']} ({row['ida_b']})"
                        if is_done(row['finalizado']) and row['pen_a'] + row['pen_b'] > 0: txt_pl += f" (P: {row['pen_a']}x{row['pen_b']})"
                        c1.markdown(f"<p style='text-align:right'><b>{row['a']}</b></p>", unsafe_allow_html=True)
                        c2.markdown(f"<div style='text-align:center; background:#eee; border-radius:5px;'>{txt_pl}</div>", unsafe_allow_html=True)
                        c3.markdown(f"<p style='text-align:left'><b>{row['b']}</b></p>", unsafe_allow_html=True)

                        if is_admin:
                            # AQUI A MUDANÇA: Gols são livres, Pênaltis e Salvar são um "pacote"
                            if row['modo_copa'] == "Só Ida" or row['fase'] in ["Final", "3º Lugar"]:
                                with st.expander("✎ Lançar Placar"):
                                    ca, cb = st.columns(2)
                                    ga = ca.number_input(f"Gols {row['a']}", 0, 99, int(row['gols_a']), key=f"ga_{idx}")
                                    gb = cb.number_input(f"Gols {row['b']}", 0, 99, int(row['gols_b']), key=f"gb_{idx}")
                                    pa, pb = 0, 0
                                    if ga == gb and fmt == "COPA":
                                        st.warning("Pênaltis (Lançar e Confirmar):")
                                        cpa, cpb = st.columns(2)
                                        pa = cpa.number_input("Pên A", 0, 99, int(row['pen_a']), key=f"pa_{idx}")
                                        pb = cpb.number_input("Pên B", 0, 99, int(row['pen_b']), key=f"pb_{idx}")
                                    if st.button("✅ Confirmar Resultado", key=f"btn_{idx}"):
                                        df_db.loc[idx, ['gols_a','gols_b','pen_a','pen_b','finalizado']] = [ga, gb, pa, pb, "SIM"]
                                        salvar_dados(df_db)
                            else:
                                exp_i = st.expander("🏟️ Jogo de Ida")
                                with exp_i:
                                    ci1, ci2 = st.columns(2)
                                    i1 = ci1.number_input(f"{row['a']} ", 0, 99, int(row['ida_a']), key=f"i1_{idx}")
                                    i2 = ci2.number_input(f"{row['b']} ", 0, 99, int(row['ida_b']), key=f"i2_{idx}")
                                exp_v = st.expander("🏟️ Jogo de Volta")
                                with exp_v:
                                    cv1, cv2 = st.columns(2)
                                    v1 = cv1.number_input(f"{row['a']}  ", 0, 99, int(row['volta_a']), key=f"v1_{idx}")
                                    v2 = cv2.number_input(f"{row['b']}  ", 0, 99, int(row['volta_b']), key=f"v2_{idx}")
                                    pa, pb = 0, 0
                                    if (i1+v1) == (i2+v2):
                                        st.warning("Empate Agregado! Pênaltis:")
                                        cpa, cpb = st.columns(2)
                                        pa = cpa.number_input("Pên A", 0, 99, int(row['pen_a']), key=f"pa_{idx}")
                                        pb = cpb.number_input("Pên B", 0, 99, int(row['pen_b']), key=f"pb_{idx}")
                                if st.button("✅ Salvar Tudo", key=f"btn_{idx}"):
                                    df_db.loc[idx, ['ida_a','ida_b','volta_a','volta_b','pen_a','pen_b','finalizado']] = [i1, i2, v1, v2, pa, pb, "SIM"]
                                    salvar_dados(df_db)

    # --- CHAVEAMENTO GRÁFICO (MODO BALÃO) ---
    elif menu == "📊 Chaveamento & Pódio":
        if fmt == "COPA":
            st.subheader("🗺️ Chaveamento")
            fases_raw = df_t['fase'].unique()
            ordem_map = {"Oitavas":0, "Quartas":1, "Semifinal":2, "3º Lugar":3, "Final":4}
            fases_sorted = sorted(fases_raw, key=lambda x: ordem_map.get(x, 99))
            
            if fases_sorted:
                cols_c = st.columns(len(fases_sorted))
                for i, fase in enumerate(fases_sorted):
                    with cols_c[i]:
                        st.markdown(f"<div style='text-align:center; background:#444; color:white; border-radius:10px; padding:5px; margin-bottom:15px;'>{fase.upper()}</div>", unsafe_allow_html=True)
                        for _, r in df_t[df_t['fase'] == fase].iterrows():
                            done = is_done(r['finalizado'])
                            v, _ = obter_vencedor(r)
                            # Placar do balão
                            if r['modo_copa'] == "Só Ida" or r['fase'] in ["Final", "3º Lugar"]:
                                score = f"{r['gols_a']} x {r['gols_b']}"
                            else:
                                score = f"{r['ida_a']+r['volta_a']} x {r['ida_b']+r['volta_b']}"
                            
                            if done and (r['pen_a'] + r['pen_b'] > 0):
                                score += f" <br><small>(P: {r['pen_a']}x{r['pen_b']})</small>"
                            
                            b_color = "#4CAF50" if done else "#ccc"
                            st.markdown(f"""
                            <div style="border: 2px solid {b_color}; background: #fdfdfd; border-radius: 20px; padding: 10px; margin-bottom: 20px; text-align: center; color: #333; box-shadow: 2px 2px 8px rgba(0,0,0,0.1);">
                                <div style="font-size: 11px; font-weight: bold; color: #777;">{r['a']} x {r['b']}</div>
                                <div style="font-size: 20px; font-weight: 900; margin: 5px 0;">{score}</div>
                                <div style="border-top: 1px solid #eee; padding-top: 5px; font-size: 10px;">Vencedor: <b>{v}</b></div>
                            </div>
                            """, unsafe_allow_html=True)
            
            # Pódio (se finalizada)
            fin = df_t[df_t['fase'] == 'Final']
            if not fin.empty and is_done(fin.iloc[0]['finalizado']):
                st.divider()
                st.balloons()
                c, v = obter_vencedor(fin.iloc[0])
                st.header("🏆 Pódio Final")
                c1, c2, c3 = st.columns(3)
                c1.success(f"🥇 **CAMPEÃO**\n\n{c}")
                c2.info(f"🥈 **VICE**\n\n{v}")
                t3d = df_t[df_t['fase'] == '3º Lugar']
                if not t3d.empty and is_done(t3d.iloc[0]['finalizado']):
                    t3, _ = obter_vencedor(t3d.iloc[0])
                    c3.warning(f"🥉 **3º LUGAR**\n\n{t3}")
        else:
            # Lógica simples de Liga se for formato LIGA
            st.info("Formato Liga: Tabela de pontos disponível.")

    elif menu == "⚙️ Admin":
        if is_admin:
            with st.expander("🚨 EXCLUIR TORNEIO"):
                if st.button("DELETAR PERMANENTEMENTE"):
                    salvar_dados(df_db[df_db['torneio_id'].astype(str) != str(tid)])
