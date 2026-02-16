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
        for col in ['gols_a', 'gols_b', 'ida_a', 'ida_b', 'volta_a', 'volta_b', 'pen_a', 'pen_b']:
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
    return (r['a'], r['b']) if r['pen_a'] > r['pen_b'] else (r['b'], r['a'])

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

    # --- ADMIN ---
    if menu == "⚙️ Admin":
        if is_admin:
            with st.expander("🚀 Iniciar Torneio"):
                times_txt = st.text_area("Times (um por linha)")
                if st.button("Gerar Jogos"):
                    lista = [t.strip() for t in times_txt.split('\n') if t.strip()]
                    novos = []
                    modo_atual = st.session_state.modo if 'modo' in st.session_state else "Ida e Volta"
                    if fmt == "LIGA":
                        for a, b in combinations(lista, 2):
                            novos.append({'torneio_id': tid, 'formato': 'LIGA', 'fase': 'Pontos Corridos', 'a': a, 'b': b, 'finalizado': '0'})
                    else:
                        fase_nome = "Oitavas" if len(lista) > 8 else "Quartas" if len(lista) > 4 else "Semifinal"
                        for i in range(0, len(lista), 2):
                            if i+1 < len(lista):
                                novos.append({'torneio_id': tid, 'formato': 'COPA', 'fase': fase_nome, 'a': lista[i], 'b': lista[i+1], 'finalizado': '0', 'modo_copa': modo_atual})
                    salvar_dados(pd.concat([df_db, pd.DataFrame(novos)], ignore_index=True))
            if st.button("🚨 EXCLUIR TORNEIO"): salvar_dados(df_db[df_db['torneio_id'].astype(str) != str(tid)])

    # --- JOGOS ---
    elif menu == "🏟️ Jogos":
        if df_t.empty: st.info("Sem jogos.")
        else:
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

            fases_ordem = sorted(df_t['fase'].unique(), key=lambda x: 2 if x == "Final" else 1 if x == "3º Lugar" else 0)
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
                            if fmt == "LIGA" or row['modo_copa'] == "Só Ida" or row['fase'] in ["Final", "3º Lugar"]:
                                with st.expander("✎ Lançar Placar"):
                                    ca, cb = st.columns(2)
                                    ga, gb = ca.number_input(f"Gols {row['a']}", 0, 99, int(row['gols_a']), key=f"ga_{idx}"), cb.number_input(f"Gols {row['b']}", 0, 99, int(row['gols_b']), key=f"gb_{idx}")
                                    pa, pb = 0, 0
                                    if ga == gb and fmt == "COPA":
                                        st.warning("Pênaltis:")
                                        cpa, cpb = st.columns(2)
                                        pa, pb = cpa.number_input("Pên A", 0, 99, int(row['pen_a']), key=f"pa_{idx}"), cpb.number_input("Pên B", 0, 99, int(row['pen_b']), key=f"pb_{idx}")
                                    if st.button("Confirmar", key=f"btn_{idx}"):
                                        df_db.loc[idx, ['gols_a','gols_b','pen_a','pen_b','finalizado']] = [ga, gb, pa, pb, "SIM"]; salvar_dados(df_db)
                            else:
                                with st.expander("🏟️ Jogo de Ida"):
                                    ci1, ci2 = st.columns(2)
                                    i1, i2 = ci1.number_input(f"{row['a']} ", 0, 99, int(row['ida_a']), key=f"i1_{idx}"), ci2.number_input(f"{row['b']} ", 0, 99, int(row['ida_b']), key=f"i2_{idx}")
                                with st.expander("🏟️ Jogo de Volta"):
                                    cv1, cv2 = st.columns(2)
                                    v1, v2 = cv1.number_input(f"{row['a']}  ", 0, 99, int(row['volta_a']), key=f"v1_{idx}"), cv2.number_input(f"{row['b']}  ", 0, 99, int(row['volta_b']), key=f"v2_{idx}")
                                    pa, pb = 0, 0
                                    if (i1+v1) == (i2+v2):
                                        st.warning("Pênaltis:")
                                        cpa, cpb = st.columns(2)
                                        pa, pb = cpa.number_input("Pên A", 0, 99, int(row['pen_a']), key=f"pa_{idx}"), cpb.number_input("Pên B", 0, 99, int(row['pen_b']), key=f"pb_{idx}")
                                if st.button("Salvar Agregado", key=f"btn_{idx}"):
                                    df_db.loc[idx, ['ida_a','ida_b','volta_a','volta_b','pen_a','pen_b','finalizado']] = [i1, i2, v1, v2, pa, pb, "SIM"]; salvar_dados(df_db)

    # --- CHAVEAMENTO GRÁFICO ---
    elif menu == "📊 Chaveamento & Pódio":
        if fmt == "LIGA":
            # Lógica de Liga (Tabela)
            times = pd.concat([df_t['a'], df_t['b']]).unique()
            stats = {t: {'P':0, 'J':0, 'V':0, 'SG':0} for t in times if pd.notna(t)}
            for _, r in df_t[df_t['finalizado'] == 'SIM'].iterrows():
                t1, t2, g1, g2 = r['a'], r['b'], r['gols_a'], r['gols_b']
                stats[t1]['J']+=1; stats[t2]['J']+=1
                if g1 > g2: stats[t1]['P']+=3; stats[t1]['V']+=1
                elif g2 > g1: stats[t2]['P']+=3; stats[t2]['V']+=1
                else: stats[t1]['P']+=1; stats[t2]['P']+=1
                stats[t1]['SG'] += (g1-g2); stats[t2]['SG'] += (g2-g1)
            st.table(pd.DataFrame.from_dict(stats, orient='index').sort_values(by=['P','V','SG'], ascending=False))
        else:
            st.subheader("🗺️ Chaveamento")
            # Ordenar fases: Quartas -> Semi -> 3º Lugar -> Final
            fases_raw = df_t['fase'].unique()
            ordem_map = {"Oitavas":0, "Quartas":1, "Semifinal":2, "3º Lugar":3, "Final":4}
            fases_sorted = sorted(fases_raw, key=lambda x: ordem_map.get(x, 99))
            
            cols = st.columns(len(fases_sorted))
            
            for i, fase in enumerate(fases_sorted):
                with cols[i]:
                    st.markdown(f"<div style='text-align:center; margin-bottom:20px; color:#555;'><b>{fase.upper()}</b></div>", unsafe_allow_html=True)
                    for _, r in df_t[df_t['fase'] == fase].iterrows():
                        done = is_done(r['finalizado'])
                        placar = f"{r['gols_a']} x {r['gols_b']}" if (r['modo_copa'] == "Só Ida" or r['fase'] in ["Final", "3º Lugar"]) else f"{r['ida_a']}+{r['volta_a']} x {r['ida_b']}+{r['volta_b']}"
                        if done and (r['pen_a'] + r['pen_b'] > 0): placar += f" <br>(P: {r['pen_a']}x{r['pen_b']})"
                        v, _ = obter_vencedor(r)
                        
                        # Estilo do Balão (Card)
                        bg_color = "#ffffff"
                        border_color = "#4CAF50" if done else "#ddd"
                        text_color = "#333"
                        
                        st.markdown(f"""
                        <div style="
                            background-color: {bg_color};
                            border: 2px solid {border_color};
                            border-radius: 15px;
                            padding: 12px;
                            margin-bottom: 15px;
                            text-align: center;
                            box-shadow: 2px 2px 5px rgba(0,0,0,0.1);
                            color: {text_color};
                        ">
                            <div style="font-size: 13px; font-weight: bold; border-bottom: 1px solid #eee; padding-bottom: 5px;">
                                {r['a']} <span style='color:#999'>vs</span> {r['b']}
                            </div>
                            <div style="font-size: 18px; font-weight: 800; padding: 10px 0;">{placar}</div>
                            <div style="font-size: 10px; color: #666; font-style: italic;">
                                Vencedor: <b style='color:#333'>{v}</b>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

            # PÓDIO FINAL
            final = df_t[df_t['fase'] == 'Final']
            if not final.empty and is_done(final.iloc[0]['finalizado']):
                st.divider()
                st.header("🏆 Pódio Final")
                camp, vice = obter_vencedor(final.iloc[0])
                st.balloons()
                c1, c2, c3 = st.columns(3)
                c1.markdown(f"<div style='text-align:center; padding:20px; background:#d4edda; border-radius:15px; border:2px solid #28a745;'>🥇 <b>CAMPEÃO</b><br><span style='font-size:24px'>{camp}</span></div>", unsafe_allow_html=True)
                c2.markdown(f"<div style='text-align:center; padding:20px; background:#d1ecf1; border-radius:15px; border:2px solid #17a2b8;'>🥈 <b>VICE</b><br><span style='font-size:20px'>{vice}</span></div>", unsafe_allow_html=True)
                t3_data = df_t[df_t['fase'] == '3º Lugar']
                if not t3_data.empty and is_done(t3_data.iloc[0]['finalizado']):
                    t3, _ = obter_vencedor(t3_data.iloc[0])
                    c3.markdown(f"<div style='text-align:center; padding:20px; background:#fff3cd; border-radius:15px; border:2px solid #ffc107;'>🥉 <b>3º LUGAR</b><br><span style='font-size:18px'>{t3}</span></div>", unsafe_allow_html=True)
