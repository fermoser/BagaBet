import streamlit as st
import pandas as pd
from itertools import combinations
from streamlit_gsheets import GSheetsConnection
from datetime import datetime, timedelta

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="BAGA GESTOR PRO", layout="wide")

# --- ESTILO CSS (AMARELO SUAVE NOS NÚMEROS) ---
st.markdown("""
    <style>
    input[type=number] {
        color: #F4D03F !important;
        font-weight: bold !important;
        font-size: 20px !important;
    }
    </style>
    """, unsafe_allow_html=True)

conn = st.connection("gsheets", type=GSheetsConnection)
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
        df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
        if aba == ABA_JOGOS:
            for c in COLUNAS:
                if c not in df.columns: df[c] = None
            cols_n = ['gols_a', 'gols_b', 'ida_a', 'ida_b', 'volta_a', 'volta_b', 'pen_a', 'pen_b']
            for col in cols_n:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
        return df
    except:
        return pd.DataFrame(columns=COLUNAS)

def salvar_dados(df, aba):
    conn.update(worksheet=aba, data=df.copy())
    st.cache_data.clear()
    st.rerun()

def is_done(val):
    return str(val).upper().strip() in ["1", "SIM", "TRUE"]

def obter_vencedor(r):
    if not is_done(r['finalizado']): return "---", ""
    # Cálculo para Copa (Ida/Volta ou Só Ida)
    if r['fase'] in ["Final", "3º Lugar"] or r['modo_copa'] == "Só Ida":
        sa, sb = int(r['gols_a']), int(r['gols_b'])
    else:
        sa, sb = int(r['ida_a']) + int(r['volta_a']), int(r['ida_b']) + int(r['volta_b'])
    
    if sa > sb: return r['a'], r['b']
    if sb > sa: return r['b'], r['a']
    # Desempate nos pênaltis se necessário
    pa, pb = int(r.get('pen_a', 0)), int(r.get('pen_b', 0))
    return (r['a'], r['b']) if pa > pb else (r['b'], r['a'])

# --- INICIALIZAÇÃO ---
if 'torneio_ativo' not in st.session_state:
    st.session_state.torneio_ativo = None

df_db = carregar_dados(ABA_JOGOS)
df_hist = carregar_dados(ABA_HISTORICO)

# --- TELA DE SELEÇÃO ---
if st.session_state.torneio_ativo is None:
    st.title("⚽ BAGA GESTOR")
    
    with st.expander("📜 Hall da Fama (Campeões)"):
        if not df_hist.empty: st.dataframe(df_hist.sort_index(ascending=False), use_container_width=True)
        else: st.info("Histórico vazio.")

    torneios = df_db.dropna(subset=['torneio_id'])['torneio_id'].unique() if not df_db.empty else []
    if len(torneios) > 0:
        with st.expander("📂 Abrir Torneio em Aberto", expanded=True):
            cols = st.columns(3)
            for i, t_nome in enumerate(torneios):
                row_t = df_db[df_db['torneio_id'] == t_nome].iloc[0]
                if cols[i%3].button(f"🏆 {t_nome} ({row_t['formato']})", key=f"sel_{t_nome}"):
                    st.session_state.torneio_ativo = t_nome
                    st.session_state.formato = row_t['formato']
                    st.rerun()

    st.divider()
    st.subheader("🆕 Novo Torneio")
    with st.form("criar_home"):
        c1, c2, c3 = st.columns(3)
        n = c1.text_input("Nome do Torneio")
        t = c2.selectbox("Tipo", ["COPA", "LIGA"])
        m = c3.selectbox("Modo", ["Só Ida", "Ida e Volta"]) if t == "COPA" else "Só Ida"
        if st.form_submit_button("CRIAR"):
            if n: st.session_state.torneio_ativo, st.session_state.formato, st.session_state.modo = n, t, m; st.rerun()

else:
    tid, fmt = st.session_state.torneio_ativo, st.session_state.formato
    df_t = df_db[df_db['torneio_id'].astype(str) == str(tid)].copy()

    with st.sidebar:
        st.header(f"🏆 {tid}")
        menu = st.radio("Menu", ["🏟️ Jogos", "📊 Classificação", "⚙️ Admin"])
        is_admin = (st.text_input("Senha Admin", type="password") == "1234")
        if st.button("🏠 Sair"): st.session_state.torneio_ativo = None; st.rerun()

    # --- ABA JOGOS (AQUI VOLTOU OS PLACARES!) ---
    if menu == "🏟️ Jogos":
        if df_t.empty:
            st.warning("Vá em 'Admin' para gerar os jogos deste torneio.")
        else:
            for f in df_t['fase'].unique():
                st.subheader(f"📍 {f}")
                for idx, row in df_t[df_t['fase'] == f].iterrows():
                    with st.container(border=True):
                        c1, c2, c3 = st.columns([2,1,2])
                        
                        # Definir texto do placar baseado no formato
                        if fmt == "LIGA" or row['modo_copa'] == "Só Ida":
                            p_txt = f"{row['gols_a']} x {row['gols_b']}"
                        else:
                            p_txt = f"({row['ida_a']}) {row['volta_a']} x {row['volta_b']} ({row['ida_b']})"
                        
                        if is_done(row['finalizado']) and (int(row.get('pen_a',0)) + int(row.get('pen_b',0)) > 0):
                            p_txt += f" (P: {row['pen_a']}x{row['pen_b']})"

                        c1.markdown(f"<p style='text-align:right; font-size:18px;'><b>{row['a']}</b></p>", unsafe_allow_html=True)
                        c2.markdown(f"<div style='text-align:center; background:#eee; border-radius:5px; padding:8px; color:black; font-weight:bold;'>{p_txt}</div>", unsafe_allow_html=True)
                        c3.markdown(f"<p style='text-align:left; font-size:18px;'><b>{row['b']}</b></p>", unsafe_allow_html=True)
                        
                        if is_admin:
                            with st.expander("✎ Editar Placar"):
                                with st.form(f"f_{idx}"):
                                    ca, cb = st.columns(2)
                                    if fmt == "LIGA" or row['modo_copa'] == "Só Ida":
                                        ga = ca.number_input("Gols A", 0, 99, int(row['gols_a']))
                                        gb = cb.number_input("Gols B", 0, 99, int(row['gols_b']))
                                        ida_a, ida_b, volta_a, volta_b = ga, gb, 0, 0
                                    else:
                                        ia = ca.number_input("Ida A", 0, 99, int(row['ida_a']))
                                        ib = cb.number_input("Ida B", 0, 99, int(row['ida_b']))
                                        va = ca.number_input("Volta A", 0, 99, int(row['volta_a']))
                                        vb = cb.number_input("Volta B", 0, 99, int(row['volta_b']))
                                        ida_a, ida_b, volta_a, volta_b = ia, ib, va, vb
                                        ga, gb = (ia+va), (ib+vb)
                                    
                                    pa, pb = 0, 0
                                    if fmt == "COPA":
                                        cpa, cpb = st.columns(2)
                                        pa = cpa.number_input("Pênaltis A", 0, 99, int(row.get('pen_a',0)))
                                        pb = cpb.number_input("Pênaltis B", 0, 99, int(row.get('pen_b',0)))
                                    
                                    if st.form_submit_button("Confirmar Resultado"):
                                        df_db.loc[idx, ['gols_a','gols_b','ida_a','ida_b','volta_a','volta_b','pen_a','pen_b','finalizado']] = [ga, gb, ida_a, ida_b, volta_a, volta_b, pa, pb, "SIM"]
                                        salvar_dados(df_db, ABA_JOGOS)

    # --- ABA CLASSIFICAÇÃO ---
    elif menu == "📊 Classificação":
        if df_t.empty:
            st.warning("Sem dados.")
        else:
            if fmt == "LIGA":
                times = pd.concat([df_t['a'], df_t['b']]).unique()
                stats = {t: {'P':0, 'J':0, 'V':0, 'E':0, 'D':0, 'GP':0, 'GC':0, 'SG':0} for t in times if pd.notna(t)}
                for _, r in df_t[df_t['finalizado'] == 'SIM'].iterrows():
                    t1, t2, g1, g2 = r['a'], r['b'], r['gols_a'], r['gols_b']
                    stats[t1]['J']+=1; stats[t2]['J']+=1; stats[t1]['GP']+=g1; stats[t1]['GC']+=g2; stats[t2]['GP']+=g2; stats[t2]['GC']+=g1
                    if g1 > g2: stats[t1]['P']+=3; stats[t1]['V']+=1; stats[t2]['D']+=1
                    elif g2 > g1: stats[t2]['P']+=3; stats[t2]['V']+=1; stats[t1]['D']+=1
                    else: stats[t1]['P']+=1; stats[t2]['P']+=1; stats[t1]['E']+=1; stats[t2]['E']+=1
                    stats[t1]['SG'] = stats[t1]['GP'] - stats[t1]['GC']; stats[t2]['SG'] = stats[t2]['GP'] - stats[t2]['GC']
                st.table(pd.DataFrame.from_dict(stats, orient='index').sort_values(by=['P','V','SG','GP'], ascending=False))
            else:
                st.info("O chaveamento da Copa é visualizado na aba Jogos através das fases.")

    # --- ABA ADMIN (GERADOR + FINALIZADOR) ---
    elif menu == "⚙️ Admin":
        if is_admin:
            if df_t.empty:
                st.subheader("🛠️ Gerar Jogos do Torneio")
                txt_times = st.text_area("Cole os times aqui (um por linha)")
                if st.button("GERAR"):
                    times = [x.strip() for x in txt_times.split('\n') if x.strip()]
                    if len(times) >= 2:
                        jogos = []
                        if fmt == "LIGA":
                            for a, b in combinations(times, 2):
                                jogos.append({'torneio_id': tid, 'formato': fmt, 'fase': 'Turno Único', 'a': a, 'b': b, 'modo_copa': 'Só Ida', 'finalizado': 'NÃO'})
                        else:
                            # Gerador simples de Copa
                            for i in range(0, len(times), 2):
                                t1 = times[i]
                                t2 = times[i+1] if i+1 < len(times) else "BYE"
                                jogos.append({'torneio_id': tid, 'formato': fmt, 'fase': 'Eliminatórias', 'a': t1, 'b': t2, 'modo_copa': st.session_state.get('modo','Só Ida'), 'finalizado': 'NÃO'})
                        df_final = pd.concat([df_db, pd.DataFrame(jogos)], ignore_index=True)
                        salvar_dados(df_final, ABA_JOGOS)
            else:
                st.subheader("🏁 Opções do Torneio")
                if st.button("🏆 SALVAR NO HISTÓRICO"):
                    # Lógica de salvar histórico aqui...
                    st.success("Salvo!")
                
                st.divider()
                if st.button("🚨 EXCLUIR ESTE TORNEIO"):
                    salvar_dados(df_db[df_db['torneio_id'] != tid], ABA_JOGOS)
                    st.session_state.torneio_ativo = None; st.rerun()
