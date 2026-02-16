import streamlit as st
import pandas as pd
from itertools import combinations
from streamlit_gsheets import GSheetsConnection
from datetime import datetime, timedelta

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="BAGA GESTOR PRO", layout="wide")
conn = st.connection("gsheets", type=GSheetsConnection)

# Nomes das abas
ABA_JOGOS = "Página1" 
ABA_HISTORICO = "Historico"

COLUNAS = [
    'torneio_id', 'formato', 'fase', 'a', 'b', 'finalizado',
    'gols_a', 'gols_b', 'ida_a', 'ida_b', 'volta_a', 'volta_b', 'pen_a', 'pen_b', 'modo_copa'
]

# --- FUNÇÕES DE DADOS ---
def carregar_dados(aba):
    try:
        df = conn.read(worksheet=aba, ttl=0)
        if df is None or df.empty:
            if aba == ABA_JOGOS: return pd.DataFrame(columns=COLUNAS)
            return pd.DataFrame(columns=['torneio_id','formato','campeao','vice','terceiro','data_fim'])
        
        if aba == ABA_JOGOS:
            for c in COLUNAS:
                if c not in df.columns: df[c] = None
            df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
            cols_n = ['gols_a', 'gols_b', 'ida_a', 'ida_b', 'volta_a', 'volta_b', 'pen_a', 'pen_b']
            for col in cols_n:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
        return df
    except:
        return pd.DataFrame()

def salvar_dados(df, aba):
    conn.update(worksheet=aba, data=df.copy())
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

df_db = carregar_dados(ABA_JOGOS)
df_hist = carregar_dados(ABA_HISTORICO)

# --- TELA DE SELEÇÃO ---
if st.session_state.torneio_ativo is None:
    st.title("⚽ BAGA GESTOR")
    
    # 1. Hall da Fama
    with st.expander("📜 Hall da Fama (Campeões Anteriores)"):
        if not df_hist.empty:
            st.dataframe(df_hist.sort_index(ascending=False), use_container_width=True)
        else:
            st.info("Nenhum torneio finalizado no histórico ainda.")

    # 2. Torneios para Carregar (Minimizado por padrão)
    torneios = df_db.dropna(subset=['torneio_id'])['torneio_id'].unique() if not df_db.empty else []
    if len(torneios) > 0:
        with st.expander("📂 Carregar Torneio em Aberto", expanded=False):
            cols = st.columns(3)
            for i, t_nome in enumerate(torneios):
                fmt_t = df_db[df_db['torneio_id'] == t_nome]['formato'].iloc[0]
                if cols[i%3].button(f"🏆 {t_nome} ({fmt_t})", key=f"btn_{t_nome}"):
                    st.session_state.torneio_ativo = t_nome
                    st.session_state.formato = fmt_t
                    st.rerun()
    
    st.divider()
    
    # 3. Novo Torneio (Lógica de Modo Ida e Volta dinâmica)
    st.subheader("🆕 Novo Torneio")
    with st.form("criar"):
        c1, c2 = st.columns(2)
        n = c1.text_input("Nome do Torneio")
        t = c2.selectbox("Tipo", ["COPA", "LIGA"])
        
        # Só mostra opção de Ida e Volta se for COPA
        if t == "COPA":
            m = st.selectbox("Modo", ["Só Ida", "Ida e Volta"])
        else:
            m = "Só Ida" # Liga é sempre ida (pontos corridos)
            st.caption("ℹ️ Ligas são criadas automaticamente no modo 'Só Ida'.")
            
        if st.form_submit_button("CRIAR"):
            if n: 
                st.session_state.torneio_ativo, st.session_state.formato, st.session_state.modo = n, t, m
                st.rerun()

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
                                ca, cb = st.columns(2)
                                ga = ca.number_input("Gols A",0,99,int(row['gols_a']))
                                gb = cb.number_input("Gols B",0,99,int(row['gols_b']))
                                pa, pb = 0, 0
                                if fmt == "COPA":
                                    cpa, cpb = st.columns(2); pa = cpa.number_input("Pên A",0,99,int(row['pen_a'])); pb = cpb.number_input("Pên B",0,99,int(row['pen_b']))
                                if st.form_submit_button("Salvar"):
                                    df_db.loc[idx,['gols_a','gols_b','pen_a','pen_b','finalizado']] = [ga, gb, pa, pb, "SIM"]; salvar_dados(df_db, ABA_JOGOS)

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
            st.subheader("🗺️ Chaveamento")
            f_map = {"Oitavas":0, "Quartas":1, "Semifinal":2, "3º Lugar":3, "Final":4}
            f_p = sorted([f for f in df_t['fase'].unique() if f in f_map], key=lambda x: f_map.get(x, 99))
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
            st.subheader("🏁 Finalizar e Imortalizar Torneio")
            if st.button("🏆 SALVAR NO HISTÓRICO"):
                try:
                    camp, vice, terc = "", "", ""
                    if fmt == "LIGA":
                        times = pd.concat([df_t['a'], df_t['b']]).unique()
                        stats = {t: {'P':0, 'V':0, 'SG':0, 'GP':0} for t in times if pd.notna(t)}
                        for _, r in df_t[df_t['finalizado'] == 'SIM'].iterrows():
                            t1, t2, g1, g2 = r['a'], r['b'], int(r['gols_a']), int(r['gols_b'])
                            stats[t1]['GP']+=g1; stats[t1]['SG']+= (g1-g2); stats[t2]['GP']+=g2; stats[t2]['SG']+= (g2-g1)
                            if g1 > g2: stats[t1]['P']+=3; stats[t1]['V']+=1
                            elif g2 > g1: stats[t2]['P']+=3; stats[t2]['V']+=1
                            else: stats[t1]['P']+=1; stats[t2]['P']+=1
                        df_res = pd.DataFrame.from_dict(stats, orient='index').sort_values(by=['P','V','SG','GP'], ascending=False)
                        if len(df_res) >= 1: camp = df_res.index[0]
                        if len(df_res) >= 2: vice = df_res.index[1]
                        if len(df_res) >= 3: terc = df_res.index[2]
                    else:
                        fin = df_t[df_t['fase'] == 'Final']; t3d = df_t[df_t['fase'] == '3º Lugar']
                        if not fin.empty: camp, vice = obter_vencedor(fin.iloc[0])
                        if not t3d.empty: terc, _ = obter_vencedor(t3d.iloc[0])

                    # AJUSTE DE HORÁRIO (Brasil -3h do servidor padrão)
                    hora_brasil = datetime.now() - timedelta(hours=3)
                    
                    nova_linha = pd.DataFrame([{
                        'torneio_id': tid, 'formato': fmt, 'campeao': camp, 'vice': vice, 'terceiro': terc,
                        'data_fim': hora_brasil.strftime("%d/%m/%Y %H:%M")
                    }])
                    
                    df_hist_novo = pd.concat([df_hist, nova_linha], ignore_index=True)
                    conn.update(worksheet=ABA_HISTORICO, data=df_hist_novo)
                    st.success("Copiado para o Histórico!")
                    st.balloons()
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro: {e}")

            st.divider()
            if st.button("🚨 EXCLUIR TORNEIO (CUIDADO)"):
                salvar_dados(df_db[df_db['torneio_id'] != tid], ABA_JOGOS)
                st.session_state.torneio_ativo = None
                st.rerun()
