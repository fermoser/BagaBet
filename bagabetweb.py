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
        cols_num = ['gols_a', 'gols_b', 'ida_a', 'ida_b', 'volta_a', 'volta_b', 'pen_a', 'pen_b']
        for col in cols_num:
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
    if r['pen_a'] > r['pen_b']: return r['a'], r['b']
    return r['b'], r['a']

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
        nn = c1.text_input("Nome")
        nt = c2.selectbox("Tipo", ["LIGA", "COPA"])
        nm = c3.selectbox("Modo Copa", ["Ida e Volta", "Só Ida"])
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
        else: st.warning("Acesso restrito.")

    elif menu == "🏟️ Jogos":
        if df_t.empty: st.info("Sem jogos.")
        else:
            # AUTO-PROGRESSÃO COPA
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
                        proxs.append({'torneio_id': tid, 'formato': 'COPA', 'fase': 'Final', 'a': vencs[0], 'b': vencs[1], 'finalizado': '0', 'modo_copa': 'Jogo Único'})
                        proxs.append({'torneio_id': tid, 'formato': 'COPA', 'fase': '3º Lugar', 'a': perds[0], 'b': perds[1], 'finalizado': '0', 'modo_copa': 'Jogo Único'})
                    else:
                        for i in range(0, len(vencs), 2):
                            proxs.append({'torneio_id': tid, 'formato': 'COPA', 'fase': nova, 'a': vencs[i], 'b': vencs[i+1], 'finalizado': '0', 'modo_copa': modo_atual})
                    salvar_dados(pd.concat([df_db, pd.DataFrame(proxs)], ignore_index=True))

            for fase in df_t['fase'].unique():
                st.subheader(f"📍 {fase}")
                for idx, row in df_t[df_t['fase'] == fase].iterrows():
                    with st.container(border=True):
                        c1, c2, c3 = st.columns([2,1,2])
                        if fmt == "LIGA" or row['modo_copa'] == "Só Ida" or row['fase'] in ["Final", "3º Lugar"]:
                            pl = f"{row['gols_a']} x {row['gols_b']}"
                        else:
                            pl = f"({row['ida_a']}) {row['volta_a']} x {row['volta_b']} ({row['ida_b']})"
                        if is_done(row['finalizado']) and row['pen_a'] + row['pen_b'] > 0:
                            pl += f" (P: {row['pen_a']}x{row['pen_b']})"
                        
                        c1.markdown(f"<p style='text-align:right; font-size:18px;'><b>{row['a']}</b></p>", unsafe_allow_html=True)
                        c2.markdown(f"<div style='text-align:center; background:#eee; font-weight:bold; padding:5px; border-radius:5px;'>{pl}</div>", unsafe_allow_html=True)
                        c3.markdown(f"<p style='text-align:left; font-size:18px;'><b>{row['b']}</b></p>", unsafe_allow_html=True)

                        if is_admin:
                            with st.expander("✎ Editar Placar"):
                                with st.form(key=f"form_ed_{idx}"):
                                    if fmt == "LIGA" or row['modo_copa'] == "Só Ida" or row['fase'] in ["Final", "3º Lugar"]:
                                        col_a, col_b = st.columns(2)
                                        ga = col_a.number_input(f"Gols {row['a']}", 0, 99, int(row['gols_a']))
                                        gb = col_b.number_input(f"Gols {row['b']}", 0, 99, int(row['gols_b']))
                                        pa, pb = 0, 0
                                        if ga == gb and fmt == "COPA":
                                            st.warning("Empate! Pênaltis:")
                                            c_pa, c_pb = st.columns(2)
                                            pa = c_pa.number_input("Pên A", 0, 99, int(row['pen_a']))
                                            pb = c_pb.number_input("Pên B", 0, 99, int(row['pen_b']))
                                        if st.form_submit_button("✅ SALVAR PLACAR"):
                                            df_db.loc[idx, ['gols_a','gols_b','pen_a','pen_b','finalizado']] = [ga, gb, pa, pb, "SIM"]
                                            salvar_dados(df_db)
                                    else:
                                        c_i1, c_i2 = st.columns(2)
                                        i1 = c_i1.number_input(f"Ida: {row['a']}", 0, 99, int(row['ida_a']))
                                        i2 = c_i2.number_input(f"Ida: {row['b']}", 0, 99, int(row['ida_b']))
                                        c_v1, c_v2 = st.columns(2)
                                        v1 = c_v1.number_input(f"Volta: {row['a']}", 0, 99, int(row['volta_a']))
                                        v2 = c_v2.number_input(f"Volta: {row['b']}", 0, 99, int(row['volta_b']))
                                        pa, pb = 0, 0
                                        if (i1+v1) == (i2+v2):
                                            st.warning("Empate no Agregado! Pênaltis:")
                                            c_pa, c_pb = st.columns(2)
                                            pa = c_pa.number_input("Pên A", 0, 99, int(row['pen_a']))
                                            pb = c_pb.number_input("Pên B", 0, 99, int(row['pen_b']))
                                        if st.form_submit_button("✅ SALVAR PLACAR AGREGADO"):
                                            df_db.loc[idx, ['ida_a', 'ida_b', 'volta_a', 'volta_b', 'pen_a', 'pen_b', 'finalizado']] = [i1, i2, v1, v2, pa, pb, "SIM"]
                                            salvar_dados(df_db)

    elif menu == "📊 Chaveamento & Pódio":
        if fmt == "LIGA":
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
            fases = df_t['fase'].unique()
            cols = st.columns(len(fases))
            for i, fase in enumerate(fases):
                with cols[i]:
                    st.markdown(f"<div style='text-align:center; background:#444; color:white; border-radius:5px;'><b>{fase}</b></div>", unsafe_allow_html=True)
                    for _, r in df_t[df_t['fase'] == fase].iterrows():
                        done = is_done(r['finalizado'])
                        if r['modo_copa'] == "Só Ida" or r['fase'] in ["Final", "3º Lugar"]:
                            txt = f"{r['gols_a']} x {r['gols_b']}"
                        else:
                            txt = f"({r['ida_a']}) {r['volta_a']} x {r['volta_b']} ({r['ida_b']})"
                        if done and (r['pen_a'] > 0 or r['pen_b'] > 0):
                            txt += f"<br><small>P: {r['pen_a']}x{r['pen_b']}</small>"
                        
                        v, _ = obter_vencedor(r)
                        cor = "border-left: 5px solid #4CAF50;" if done else "border-left: 5px solid #ccc;"
                        st.markdown(f"""
                        <div style="{cor} background:#f0f2f6; padding:8px; border-radius:4px; margin-top:10px; color:black; font-size:13px;">
                            {r['a']}<br><b>{txt}</b><br>{r['b']}<br>
                            <hr style='margin:4px 0;'><small>Avançou: <b>{v}</b></small>
                        </div>
                        """, unsafe_allow_html=True)

            final = df_t[df_t['fase'] == 'Final']
            if not final.empty and is_done(final.iloc[0]['finalizado']):
                st.divider()
                camp, vice = obter_vencedor(final.iloc[0])
                st.balloons()
                st.success(f"🥇 **CAMPEÃO: {camp}**")
                st.info(f"🥈 **VICE: {vice}**")
