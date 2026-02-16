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

    # --- ADMIN ---
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
        else: st.warning("Acesso restrito.")

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
                        
                        c1.markdown(f"<p style='text-align:right'>{row['a']}</p>", unsafe_allow_html=True)
                        c2.markdown(f"<div style='text-align:center; background:#eee; font-weight:bold;'>{pl}</div>", unsafe_allow_html=True)
                        c3.markdown(f"<p style='text-align:left'>{row['b']}</p>", unsafe_allow_html=True)

                        if is_admin:
                            with st.expander("Lançar Placar"):
                                def btn_placar(label, chave, val_atual):
                                    col_l, col_m, col_p = st.columns([2,1,1])
                                    col_l.write(label)
                                    novo_val = val_atual
                                    if col_m.button("➖", key=f"m_{chave}_{idx}"): novo_val = max(0, val_atual - 1)
                                    if col_p.button("➕", key=f"p_{chave}_{idx}"): novo_val = val_atual + 1
                                    return novo_val

                                if fmt == "LIGA" or row['modo_copa'] == "Só Ida" or row['fase'] in ["Final", "3º Lugar"]:
                                    ga = btn_placar(row['a'], "ga", row['gols_a'])
                                    gb = btn_placar(row['b'], "gb", row['gols_b'])
                                    pa, pb = 0, 0
                                    if ga == gb and fmt == "COPA":
                                        st.caption("Pênaltis:")
                                        pa = st.number_input("Pên A", 0, value=row['pen_a'], key=f"pa_{idx}")
                                        pb = st.number_input("Pên B", 0, value=row['pen_b'], key=f"pb_{idx}")
                                    if st.button("Confirmar Resultado", key=f"save_{idx}"):
                                        df_db.loc[idx, ['gols_a','gols_b','pen_a','pen_b','finalizado']] = [ga, gb, pa, pb, "SIM"]; salvar_dados(df_db)
                                else:
                                    st.write("**Ida**")
                                    i1 = btn_placar(row['a'], "i1", row['ida_a'])
                                    i2 = btn_placar(row['b'], "i2", row['ida_b'])
                                    st.write("**Volta**")
                                    v1 = btn_placar(row['a'], "v1", row['volta_a'])
                                    v2 = btn_placar(row['b'], "v2", row['volta_b'])
                                    pa, pb = 0, 0
                                    if (i1+v1) == (i2+v2):
                                        st.caption("Pênaltis:")
                                        pa = st.number_input("Pên A", 0, value=row['pen_a'], key=f"pa_{idx}")
                                        pb = st.number_input("Pên B", 0, value=row['pen_b'], key=f"pb_{idx}")
                                    if st.button("Confirmar Resultado", key=f"save_{idx}"):
                                        df_db.loc[idx, ['ida_a','ida_b','volta_a','volta_b','pen_a','pen_b','finalizado']] = [i1, i2, v1, v2, pa, pb, "SIM"]; salvar_dados(df_db)

    # --- CHAVEAMENTO GRÁFICO & PÓDIO ---
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
            st.subheader("🗺️ Chaveamento do Torneio")
            fases_disponiveis = df_t['fase'].unique()
            cols_chave = st.columns(len(fases_disponiveis))
            
            for i, fase in enumerate(fases_disponiveis):
                with cols_chave[i]:
                    st.markdown(f"<div style='text-align:center; background:#262730; color:white; padding:5px; border-radius:5px; margin-bottom:15px;'><b>{fase.upper()}</b></div>", unsafe_allow_html=True)
                    jogos_fase = df_t[df_t['fase'] == fase]
                    for _, r in jogos_fase.iterrows():
                        finalizado = is_done(r['finalizado'])
                        # Formatação do Placar para o Card
                        if r['modo_copa'] == "Só Ida" or r['fase'] in ["Final", "3º Lugar"]:
                            txt_placar = f"{r['gols_a']} x {r['gols_b']}"
                        else:
                            txt_placar = f"({r['ida_a']}) {r['volta_a']} x {r['volta_b']} ({r['ida_b']})"
                        
                        if finalizado and r['pen_a'] + r['pen_b'] > 0:
                            txt_placar += f"<br><small>Pên: {r['pen_a']}x{r['pen_b']}</small>"
                        
                        venc, _ = obter_vencedor(r) if finalizado else ("?", "")
                        cor_borda = "#4CAF50" if finalizado else "#555"
                        
                        st.markdown(f"""
                        <div style="border:2px solid {cor_borda}; padding:10px; border-radius:8px; margin-bottom:15px; background-color:#f9f9f9; text-align:center; color: black;">
                            <div style="font-weight:bold; font-size:14px;">{r['a']}</div>
                            <div style="background:#eee; margin:5px 0; padding:3px; border-radius:4px; font-family:monospace; font-weight:bold;">{txt_placar}</div>
                            <div style="font-weight:bold; font-size:14px;">{r['b']}</div>
                            <hr style="margin:8px 0;">
                            <div style="font-size:11px; color:#666;">Vencedor: <b>{venc}</b></div>
                        </div>
                        """, unsafe_allow_html=True)

            # Pódio Exclusivo
            final = df_t[df_t['fase'] == 'Final']
            if not final.empty and is_done(final.iloc[0]['finalizado']):
                st.divider()
                st.header("🏆 Resultado Final")
                camp, vice = obter_vencedor(final.iloc[0])
                st.balloons()
                col1, col2, col3 = st.columns(3)
                col1.success(f"🥇 **CAMPEÃO**\n\n{camp}")
                col2.info(f"🥈 **VICE**\n\n{vice}")
                terceiro = df_t[df_t['fase'] == '3º Lugar']
                if not terceiro.empty and is_done(terceiro.iloc[0]['finalizado']):
                    t3, _ = obter_vencedor(terceiro.iloc[0])
                    col3.warning(f"🥉 **3º LUGAR**\n\n{t3}")
