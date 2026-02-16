import streamlit as st
import pandas as pd
from itertools import combinations
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="BAGA GESTOR - CHECKPOINT 2", layout="wide")
conn = st.connection("gsheets", type=GSheetsConnection)

COLUNAS = [
    'torneio_id', 'formato', 'fase', 'a', 'b', 'finalizado',
    'gols_a', 'gols_b', 'ida_a', 'ida_b', 'volta_a', 'volta_b', 'pen_a', 'pen_b', 'modo_copa'
]

# --- FUNÇÕES DE APOIO ---
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
    # Se for Final ou Jogo Único, usa gols_a/b. Se for Ida e Volta, usa soma.
    if r['fase'] in ["Final", "3º Lugar"] or r['modo_copa'] == "Só Ida":
        sa, sb = r['gols_a'], r['gols_b']
    else:
        sa, sb = r['ida_a'] + r['volta_a'], r['ida_b'] + r['volta_b']
    
    if sa > sb: return r['a'], r['b']
    if sb > sa: return r['b'], r['a']
    return (r['a'], r['b']) if r['pen_a'] > r['pen_b'] else (r['b'], r['a'])

# --- INICIALIZAÇÃO ---
df_db = carregar_dados()

if 'torneio_ativo' not in st.session_state:
    st.title("⚽ BAGA GESTOR - INÍCIO")
    ts = df_db.dropna(subset=['torneio_id'])[['torneio_id', 'formato']].drop_duplicates()
    if not ts.empty:
        st.subheader("📂 Abrir Torneio")
        cols = st.columns(3)
        for i, row in enumerate(ts.values):
            if cols[i%3].button(f"{row[0]} ({row[1]})", key=f"t_{i}", use_container_width=True):
                st.session_state.torneio_ativo, st.session_state.formato = row[0], row[1]
                st.rerun()

    st.divider()
    st.subheader("🆕 Criar Novo Torneio")
    with st.form("novo"):
        c1, c2, c3 = st.columns(3)
        nn = c1.text_input("Nome")
        nt = c2.selectbox("Tipo", ["LIGA", "COPA"])
        nm = c3.selectbox("Modo (Se Copa)", ["Ida e Volta", "Só Ida"])
        if st.form_submit_button("CRIAR"):
            if nn: 
                st.session_state.torneio_ativo, st.session_state.formato, st.session_state.modo = nn.strip(), nt, nm
                st.rerun()
else:
    tid, fmt = st.session_state.torneio_ativo, st.session_state.formato
    df_t = df_db[df_db['torneio_id'].astype(str) == str(tid)].copy()

    with st.sidebar:
        st.header(f"🏆 {tid}")
        menu = st.radio("Menu", ["🏟️ Jogos/Chaveamento", "📊 Classificação/Pódio", "⚙️ Admin"])
        is_admin = (st.text_input("Senha Admin", type="password") == "1234")
        if st.button("🏠 Sair"): st.session_state.clear(); st.rerun()

    if menu == "⚙️ Admin":
        if is_admin:
            with st.expander("🚀 Iniciar Torneio", expanded=True):
                times_txt = st.text_area("Times (um por linha)")
                if st.button("Gerar Primeira Fase"):
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
        else: st.warning("Acesse com senha.")

    elif menu == "🏟️ Jogos/Chaveamento":
        if df_t.empty: st.info("Sem jogos. Vá no Admin.")
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

            # EXIBIÇÃO POR FASE (CHAVEAMENTO)
            for fase in df_t['fase'].unique():
                st.markdown(f"### 📍 {fase}")
                for idx, row in df_t[df_t['fase'] == fase].iterrows():
                    with st.container(border=True):
                        c1, c2, c3 = st.columns([2,1,2])
                        # Lógica de exibição de placar conforme o modo
                        if fmt == "LIGA" or row['modo_copa'] == "Só Ida" or row['fase'] in ["Final", "3º Lugar"]:
                            pl = f"{row['gols_a']} x {row['gols_b']}"
                        else:
                            pl = f"({row['ida_a']}) {row['volta_a']} x {row['volta_b']} ({row['ida_b']})"
                        
                        if is_done(row['finalizado']) and row['pen_a'] + row['pen_b'] > 0:
                            pl += f"  (P: {row['pen_a']}x{row['pen_b']})"

                        c1.markdown(f"<p style='text-align:right'><b>{row['a']}</b></p>", unsafe_allow_html=True)
                        c2.markdown(f"<div style='text-align:center; background:#eee; padding:5px; border-radius:5px;'>{pl}</div>", unsafe_allow_html=True)
                        c3.markdown(f"<p style='text-align:left'><b>{row['b']}</b></p>", unsafe_allow_html=True)
                        
                        if is_admin:
                            with st.expander("Editar Resultado"):
                                with st.form(f"form_{idx}"):
                                    # Interface dinâmica conforme o modo do jogo
                                    if fmt == "LIGA" or row['modo_copa'] == "Só Ida" or row['fase'] in ["Final", "3º Lugar"]:
                                        ca, cb = st.columns(2)
                                        ga = ca.number_input(f"Gols {row['a']}", 0, 99, row['gols_a'])
                                        gb = cb.number_input(f"Gols {row['b']}", 0, 99, row['gols_b'])
                                        if ga == gb and fmt == "COPA":
                                            st.warning("Empate em jogo eliminatório! Pênaltis:")
                                            pa, pb = st.columns(2)
                                            p_a = pa.number_input("Pên A", 0, 99, row['pen_a'])
                                            p_b = pb.number_input("Pên B", 0, 99, row['pen_b'])
                                        else: p_a, p_b = 0, 0
                                        if st.form_submit_button("Salvar"):
                                            df_db.loc[idx, ['gols_a','gols_b','pen_a','pen_b','finalizado']] = [ga, gb, p_a, p_b, "SIM"]; salvar_dados(df_db)
                                    else:
                                        c_ida, c_volta = st.columns(2)
                                        i1, i2 = c_ida.number_input("Ida A",0,99,row['ida_a']), c_ida.number_input("Ida B",0,99,row['ida_b'])
                                        v1, v2 = c_volta.number_input("Volta A",0,99,row['volta_a']), c_volta.number_input("Volta B",0,99,row['volta_b'])
                                        if (i1+v1) == (i2+v2):
                                            st.warning("Empate no agregado! Pênaltis:")
                                            pa, pb = st.columns(2)
                                            p_a = pa.number_input("Pên A", 0, 99, row['pen_a'])
                                            p_b = pb.number_input("Pên B", 0, 99, row['pen_b'])
                                        else: p_a, p_b = 0, 0
                                        if st.form_submit_button("Salvar Placar"):
                                            df_db.loc[idx, ['ida_a','ida_b','volta_a','volta_b','pen_a','pen_b','finalizado']] = [i1, i2, v1, v2, p_a, p_b, "SIM"]; salvar_dados(df_db)

    elif menu == "📊 Classificação/Pódio":
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
            final = df_t[df_t['fase'] == 'Final']
            if not final.empty and is_done(final.iloc[0]['finalizado']):
                st.header("🏆 Pódio Final")
                camp, vice = obter_vencedor(final.iloc[0])
                st.balloons()
                st.success(f"🥇 **CAMPEÃO: {camp}**")
                st.info(f"🥈 **VICE: {vice}**")
                terceiro = df_t[df_t['fase'] == '3º Lugar']
                if not terceiro.empty and is_done(terceiro.iloc[0]['finalizado']):
                    t3, _ = obter_vencedor(terceiro.iloc[0])
                    st.warning(f"🥉 **3º LUGAR: {t3}**")
            else:
                st.info("O pódio aparecerá após a Final.")
