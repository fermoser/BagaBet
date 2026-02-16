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

# --- FUNÇÕES DE DADOS ---
def carregar_dados():
    try:
        df = conn.read(ttl=0)
        if df is None or df.empty: return pd.DataFrame(columns=COLUNAS)
        for c in COLUNAS:
            if c not in df.columns: df[c] = None
        df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
        cols_n = ['gols_a', 'gols_b', 'ida_a', 'ida_b', 'volta_a', 'volta_b', 'pen_a', 'pen_b']
        for col in cols_n:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
        return df
    except:
        return pd.DataFrame(columns=COLUNAS)

def salvar_dados(df):
    conn.update(data=df[COLUNAS].copy())
    st.cache_data.clear()
    st.rerun()

def is_done(val):
    return str(val).upper().strip() in ["1", "SIM", "TRUE"]

def obter_vencedor(r):
    if not is_done(r['finalizado']): return "---", ""
    if r['fase'] in ["Final", "3º Lugar"] or r['modo_copa'] == "Só Ida":
        sa, sb = int(r['gols_a']), int(r['gols_b'])
    else:
        sa, sb = int(r['ida_a']) + int(r['volta_a']), int(r['ida_b']) + int(r['volta_b'])
    if sa > sb: return r['a'], r['b']
    if sb > sa: return r['b'], r['a']
    return (r['a'], r['b']) if int(r['pen_a']) > int(r['pen_b']) else (r['b'], r['a'])

# --- INICIALIZAÇÃO ---
if 'torneio_ativo' not in st.session_state:
    st.session_state.torneio_ativo = None
df_db = carregar_dados()

# --- TELA DE SELEÇÃO ---
if st.session_state.torneio_ativo is None:
    st.title("⚽ BAGA GESTOR")
    torneios = df_db.dropna(subset=['torneio_id'])['torneio_id'].unique() if not df_db.empty else []
    if len(torneios) > 0:
        st.subheader("📂 Abrir Torneio")
        cols = st.columns(3)
        for i, t_nome in enumerate(torneios):
            fmt_t = df_db[df_db['torneio_id'] == t_nome]['formato'].iloc[0]
            if cols[i%3].button(f"🏆 {t_nome} ({fmt_t})", key=f"btn_{t_nome}"):
                st.session_state.torneio_ativo = t_nome
                st.session_state.formato = fmt_t
                st.rerun()
    st.divider()
    with st.form("criar"):
        st.subheader("🆕 Novo Torneio")
        c1, c2, c3 = st.columns(3)
        n, t, m = c1.text_input("Nome"), c2.selectbox("Tipo", ["LIGA", "COPA"]), c3.selectbox("Modo", ["Só Ida", "Ida e Volta"])
        if st.form_submit_button("CRIAR"):
            if n: st.session_state.torneio_ativo, st.session_state.formato, st.session_state.modo = n, t, m; st.rerun()

else:
    tid, fmt = st.session_state.torneio_ativo, st.session_state.formato
    df_t = df_db[df_db['torneio_id'].astype(str) == str(tid)].copy()

    with st.sidebar:
        st.header(f"🏆 {tid}")
        menu = st.radio("Menu", ["🏟️ Jogos", "📊 Classificação/Chave", "⚙️ Admin"])
        is_admin = (st.text_input("Senha Admin", type="password") == "1234")
        if st.button("🏠 Sair"): st.session_state.torneio_ativo = None; st.rerun()

    # --- ABA JOGOS ---
    if menu == "🏟️ Jogos":
        if df_t.empty: st.info("Sem jogos.")
        else:
            # Progressão Copa
            if fmt == "COPA":
                fases = list(df_t['fase'].unique())
                u_fase = fases[-1]
                jogos_u = df_t[df_t['fase'] == u_fase]
                if all(is_done(x) for x in jogos_u['finalizado']) and u_fase not in ["Final", "3º Lugar"]:
                    v, p = [], []
                    for _, r in jogos_u.iterrows():
                        v_n, p_n = obter_vencedor(r)
                        v.append(v_n); p.append(p_n)
                    prox = "Final" if len(v) == 2 else "Semifinal" if len(v) == 4 else "Quartas"
                    novos = []
                    m_c = df_t['modo_copa'].iloc[0]
                    if prox == "Final":
                        novos.append({'torneio_id': tid, 'formato': 'COPA', 'fase': '3º Lugar', 'a': p[0], 'b': p[1], 'finalizado': '0', 'modo_copa': 'Só Ida'})
                        novos.append({'torneio_id': tid, 'formato': 'COPA', 'fase': 'Final', 'a': v[0], 'b': v[1], 'finalizado': '0', 'modo_copa': 'Só Ida'})
                    else:
                        for i in range(0, len(v), 2): novos.append({'torneio_id': tid, 'formato': 'COPA', 'fase': prox, 'a': v[i], 'b': v[i+1], 'finalizado': '0', 'modo_copa': m_c})
                    salvar_dados(pd.concat([df_db, pd.DataFrame(novos)], ignore_index=True))

            # Renderização dos Jogos (Com Form para não travar)
            for f in df_t['fase'].unique():
                st.subheader(f"📍 {f}")
                for idx, row in df_t[df_t['fase'] == f].iterrows():
                    with st.container(border=True):
                        c1, c2, c3 = st.columns([2,1,2])
                        p_txt = f"{row['gols_a']} x {row['gols_b']}" if (row['modo_copa'] == "Só Ida" or fmt == "LIGA") else f"({row['ida_a']}) {row['volta_a']} x {row['volta_b']} ({row['ida_b']})"
                        if is_done(row['finalizado']) and (int(row['pen_a'])+int(row['pen_b']) > 0): p_txt += f" (P: {row['pen_a']}x{row['pen_b']})"
                        c1.markdown(f"<p style='text-align:right'><b>{row['a']}</b></p>", unsafe_allow_html=True)
                        c2.markdown(f"<div style='text-align:center; background:#eee; border-radius:5px; padding:5px;'>{p_txt}</div>", unsafe_allow_html=True)
                        c3.markdown(f"<p style='text-align:left'><b>{row['b']}</b></p>", unsafe_allow_html=True)
                        if is_admin:
                            with st.expander("✎ Editar"):
                                with st.form(f"f_{idx}"):
                                    if row['modo_copa'] == "Só Ida" or fmt == "LIGA":
                                        ca, cb = st.columns(2)
                                        ga = ca.number_input(f"Gols {row['a']}", 0, 99, int(row['gols_a']))
                                        gb = cb.number_input(f"Gols {row['b']}", 0, 99, int(row['gols_b']))
                                        pa, pb = 0, 0
                                        if ga == gb and fmt == "COPA":
                                            cpa, cpb = st.columns(2); pa = cpa.number_input("Pên A",0,99,int(row['pen_a'])); pb = cpb.number_input("Pên B",0,99,int(row['pen_b']))
                                        if st.form_submit_button("Salvar"):
                                            df_db.loc[idx,['gols_a','gols_b','pen_a','pen_b','finalizado']] = [ga, gb, pa, pb, "SIM"]; salvar_dados(df_db)
                                    else:
                                        ci1, ci2 = st.columns(2); i1 = ci1.number_input("Ida A",0,99,int(row['ida_a'])); i2 = ci2.number_input("Ida B",0,99,int(row['ida_b']))
                                        cv1, cv2 = st.columns(2); v1 = cv1.number_input("Volta A",0,99,int(row['volta_a'])); v2 = cv2.number_input("Volta B",0,99,int(row['volta_b']))
                                        pa, pb = 0, 0
                                        if (i1+v1) == (i2+v2):
                                            cpa, cpb = st.columns(2); pa = cpa.number_input("Pên A",0,99,int(row['pen_a'])); pb = cpb.number_input("Pên B",0,99,int(row['pen_b']))
                                        if st.form_submit_button("Salvar Agregado"):
                                            df_db.loc[idx,['ida_a','ida_b','volta_a','volta_b','pen_a','pen_b','finalizado']] = [i1, i2, v1, v2, pa, pb, "SIM"]; salvar_dados(df_db)

    # --- ABA CLASSIFICAÇÃO / CHAVEAMENTO ---
    elif menu == "📊 Classificação/Chave":
        if fmt == "LIGA":
            st.subheader("📈 Tabela de Classificação")
            times = pd.concat([df_t['a'], df_t['b']]).unique()
            stats = {t: {'P':0, 'J':0, 'V':0, 'E':0, 'D':0, 'GP':0, 'GC':0, 'SG':0} for t in times if pd.notna(t)}
            for _, r in df_t[df_t['finalizado'] == 'SIM'].iterrows():
                t1, t2, g1, g2 = r['a'], r['b'], r['gols_a'], r['gols_b']
                stats[t1]['J']+=1; stats[t2]['J']+=1
                stats[t1]['GP']+=g1; stats[t1]['GC']+=g2; stats[t2]['GP']+=g2; stats[t2]['GC']+=g1
                if g1 > g2: stats[t1]['P']+=3; stats[t1]['V']+=1; stats[t2]['D']+=1
                elif g2 > g1: stats[t2]['P']+=3; stats[t2]['V']+=1; stats[t1]['D']+=1
                else: stats[t1]['P']+=1; stats[t2]['P']+=1; stats[t1]['E']+=1; stats[t2]['E']+=1
                stats[t1]['SG'] = stats[t1]['GP'] - stats[t1]['GC']
                stats[t2]['SG'] = stats[t2]['GP'] - stats[t2]['GC']
            
            df_tab = pd.DataFrame.from_dict(stats, orient='index').sort_values(by=['P','V','SG','GP'], ascending=False)
            st.table(df_tab)
        else:
            # Visual de Balões para COPA
            st.subheader("🗺️ Chaveamento")
            f_map = {"Oitavas":0, "Quartas":1, "Semifinal":2, "3º Lugar":3, "Final":4}
            f_p = sorted(df_t['fase'].unique(), key=lambda x: f_map.get(x, 99))
            cols = st.columns(len(f_p))
            for i, fase in enumerate(f_p):
                with cols[i]:
                    st.markdown(f"<div style='text-align:center; background:#444; color:white; border-radius:10px; padding:5px; margin-bottom:15px;'>{fase.upper()}</div>", unsafe_allow_html=True)
                    for _, r in df_t[df_t['fase'] == fase].iterrows():
                        done = is_done(r['finalizado'])
                        v, _ = obter_vencedor(r)
                        sc = f"{r['gols_a']} x {r['gols_b']}" if r['modo_copa'] == "Só Ida" else f"{r['ida_a']+r['volta_a']} x {r['ida_b']+r['volta_b']}"
                        if done and (int(r['pen_a'])+int(r['pen_b']) > 0): sc += f" <br><small>(P: {r['pen_a']}x{r['pen_b']})</small>"
                        b_c = "#4CAF50" if done else "#ccc"
                        st.markdown(f"""<div style="border: 2px solid {b_c}; background: white; border-radius: 20px; padding: 10px; margin-bottom: 20px; text-align: center; color:black;"><div style="font-size: 11px; font-weight: bold; color: #777;">{r['a']} x {r['b']}</div><div style="font-size: 20px; font-weight: 900; margin: 5px 0;">{sc}</div><div style="border-top: 1px solid #eee; padding-top: 5px; font-size: 10px;">Vencedor: <b>{v}</b></div></div>""", unsafe_allow_html=True)

    # --- ABA ADMIN ---
    elif menu == "⚙️ Admin":
        if is_admin:
            with st.expander("🚀 Iniciar Torneio"):
                txt = st.text_area("Times")
                if st.button("Gerar"):
                    l = [x.strip() for x in txt.split('\n') if x.strip()]
                    novos = []
                    if fmt == "LIGA":
                        for a, b in combinations(l, 2): novos.append({'torneio_id': tid, 'formato': 'LIGA', 'fase': 'Pontos Corridos', 'a': a, 'b': b, 'finalizado': '0'})
                    else:
                        f_n = "Oitavas" if len(l) > 8 else "Quartas" if len(l) > 4 else "Semifinal"
                        for i in range(0, len(l), 2):
                            if i+1 < len(l): novos.append({'torneio_id': tid, 'formato': 'COPA', 'fase': f_n, 'a': l[i], 'b': l[i+1], 'finalizado': '0', 'modo_copa': st.session_state.get('modo', 'Só Ida')})
                    salvar_dados(pd.concat([df_db, pd.DataFrame(novos)], ignore_index=True))
            if st.button("🚨 EXCLUIR"): salvar_dados(df_db[df_db['torneio_id'] != tid]); st.session_state.torneio_ativo = None; st.rerun()
