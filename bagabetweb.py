import streamlit as st
import pandas as pd
from itertools import combinations
from streamlit_gsheets import GSheetsConnection
from datetime import datetime, timedelta

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="BAGA GESTOR PRO", layout="wide")

# --- ESTILO CSS ---
st.markdown("""
    <style>
    input[type=number] { color: #F4D03F !important; font-weight: bold !important; font-size: 20px !important; }
    .stMarkdown div[style*="background:#eee"] { background-color: #333 !important; color: #F4D03F !important; font-weight: bold; border-radius: 5px; }
    </style>
    """, unsafe_allow_html=True)

conn = st.connection("gsheets", type=GSheetsConnection)
ABA_JOGOS = "Página1" 
ABA_HISTORICO = "Historico"
COLUNAS = ['torneio_id', 'formato', 'fase', 'a', 'b', 'finalizado', 'gols_a', 'gols_b', 'ida_a', 'ida_b', 'volta_a', 'volta_b', 'pen_a', 'pen_b', 'modo_copa']

# Dicionário de Ordem para garantir que a Final seja a última
ORDEM_FASES = {"Oitavas": 1, "Quartas": 2, "Semifinal": 3, "3º Lugar": 4, "Final": 5, "Liga": 6, "Turno Único": 6}

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
    except: return pd.DataFrame(columns=COLUNAS)

def salvar_dados(df, aba):
    df = df.dropna(subset=['torneio_id'])
    conn.update(worksheet=aba, data=df)
    st.cache_data.clear()
    st.rerun()

def is_done(val): return str(val).upper().strip() in ["1", "SIM", "TRUE"]

def obter_vencedor_perdedor(r):
    if not is_done(r['finalizado']): return None, None
    if r['fase'] in ["Final", "3º Lugar"] or r['modo_copa'] == "Só Ida":
        sa, sb = int(r['gols_a']), int(r['gols_b'])
    else:
        sa, sb = int(r['ida_a']) + int(r['volta_a']), int(r['ida_b']) + int(r['volta_b'])
    
    if sa > sb: return r['a'], r['b']
    elif sb > sa: return r['b'], r['a']
    else:
        pa, pb = int(r.get('pen_a', 0)), int(r.get('pen_b', 0))
        if pa > pb: return r['a'], r['b']
        return r['b'], r['a']

# --- INICIALIZAÇÃO ---
df_db = carregar_dados(ABA_JOGOS)
df_hist = carregar_dados(ABA_HISTORICO)

if 'torneio_ativo' not in st.session_state:
    st.session_state.torneio_ativo = None

# --- TELA INICIAL ---
if st.session_state.torneio_ativo is None:
    st.title("⚽ BAGA GESTOR PRO")
    
    with st.expander("📜 HALL DA FAMA", expanded=False):
        if not df_hist.empty: st.dataframe(df_hist.sort_index(ascending=False), use_container_width=True)

    torneios = df_db['torneio_id'].unique() if not df_db.empty else []
    if len(torneios) > 0:
        st.subheader("📂 Torneios em Andamento")
        cols = st.columns(3)
        for i, t in enumerate(torneios):
            row_info = df_db[df_db['torneio_id'] == t].iloc[0]
            if cols[i%3].button(f"🏆 {t} ({row_info['formato']})", key=f"abrir_{t}", use_container_width=True):
                st.session_state.torneio_ativo = t
                st.session_state.formato = row_info['formato']
                st.rerun()

    st.divider()
    with st.form("novo_t"):
        st.subheader("🆕 Novo Torneio")
        c1, c2, c3 = st.columns(3)
        n = c1.text_input("Nome do Torneio")
        t = c2.selectbox("Tipo", ["COPA", "LIGA"])
        m = c3.selectbox("Modo", ["Só Ida", "Ida e Volta"]) if t == "COPA" else "Só Ida"
        if st.form_submit_button("CRIAR"):
            if n: 
                st.session_state.torneio_ativo, st.session_state.formato, st.session_state.modo = n, t, m
                st.rerun()

else:
    tid, fmt = st.session_state.torneio_ativo, st.session_state.formato
    df_t = df_db[df_db['torneio_id'] == tid].copy()

    with st.sidebar:
        st.header(f"🏆 {tid}")
        menu = st.radio("Menu", ["🏟️ Jogos", "📊 Consulta", "⚙️ Admin"])
        is_admin = (st.text_input("Senha", type="password") == "1234")
        if st.button("🏠 Sair"): st.session_state.torneio_ativo = None; st.rerun()

    # --- ABA JOGOS ---
    if menu == "🏟️ Jogos":
        fases_presentes = sorted(df_t['fase'].unique(), key=lambda x: ORDEM_FASES.get(x, 99))
        for f in fases_presentes:
            st.subheader(f"📍 {f}")
            for idx, r in df_t[df_t['fase'] == f].iterrows():
                with st.container(border=True):
                    c1, c2, c3 = st.columns([2,1,2])
                    p_txt = f"{r['gols_a']} x {r['gols_b']}" if r['modo_copa']=="Só Ida" or fmt=="LIGA" else f"({r['ida_a']}) {r['volta_a']} x {r['volta_b']} ({r['ida_b']})"
                    if is_done(r['finalizado']) and (int(r['pen_a'])+int(r['pen_b'])>0): p_txt += f" (P: {r['pen_a']}x{r['pen_b']})"
                    
                    c1.markdown(f"<p style='text-align:right'><b>{r['a']}</b></p>", unsafe_allow_html=True)
                    c2.markdown(f"<div style='text-align:center; background:#eee; padding:5px; color:black;'>{p_txt}</div>", unsafe_allow_html=True)
                    c3.markdown(f"<p style='text-align:left'><b>{r['b']}</b></p>", unsafe_allow_html=True)
                    
                    if is_admin:
                        with st.expander("✎ Editar"):
                            with st.form(f"ed_{idx}"):
                                ca, cb = st.columns(2)
                                if fmt=="LIGA" or r['modo_copa']=="Só Ida":
                                    ga, gb = ca.number_input("Gols A",0,99,int(r['gols_a'])), cb.number_input("Gols B",0,99,int(r['gols_b']))
                                    res, sa, sb = [ga, gb, ga, gb, 0, 0], ga, gb
                                else:
                                    ia, ib = ca.number_input("Ida A",0,99,int(r['ida_a'])), cb.number_input("Ida B",0,99,int(r['ida_b']))
                                    va, vb = ca.number_input("Volta A",0,99,int(r['volta_a'])), cb.number_input("Volta B",0,99,int(r['volta_b']))
                                    res, sa, sb = [ia+va, ib+vb, ia, ib, va, vb], (ia+va), (ib+vb)
                                
                                pa, pb = 0, 0
                                if fmt == "COPA" and sa == sb and r['a'] != "BYE" and r['b'] != "BYE":
                                    cpa, cpb = st.columns(2)
                                    pa, pb = cpa.number_input("Pen A",0,99,int(r['pen_a'])), cpb.number_input("Pen B",0,99,int(r['pen_b']))
                                
                                if st.form_submit_button("Confirmar"):
                                    df_db.loc[idx, ['gols_a','gols_b','ida_a','ida_b','volta_a','volta_b','pen_a','pen_b','finalizado']] = res + [pa, pb, "SIM"]
                                    
                                    # Lógica de Avanço Automático Integrada
                                    df_temp = df_db[df_db['torneio_id'] == tid]
                                    jogos_fase = df_temp[df_temp['fase'] == r['fase']]
                                    
                                    if all(jogos_fase['finalizado'].apply(is_done)):
                                        venc, perd = [], []
                                        for _, rf in jogos_fase.iterrows():
                                            v, p = obter_vencedor_perdedor(rf)
                                            if v: venc.append(v)
                                            if p: perd.append(p)
                                        
                                        novos = []
                                        if r['fase'] == "Semifinal":
                                            if len(venc) >= 2: novos.append({'torneio_id':tid,'formato':fmt,'fase':'Final','a':venc[0],'b':venc[1],'modo_copa':'Só Ida','finalizado':'NÃO'})
                                            if len(perd) >= 2: novos.append({'torneio_id':tid,'formato':fmt,'fase':'3º Lugar','a':perd[0],'b':perd[1],'modo_copa':'Só Ida','finalizado':'NÃO'})
                                        elif r['fase'] == "Quartas":
                                            for i in range(0, len(venc), 2):
                                                if i+1 < len(venc):
                                                    novos.append({'torneio_id':tid,'formato':fmt,'fase':'Semifinal','a':venc[i],'b':venc[i+1],'modo_copa':r['modo_copa'],'finalizado':'NÃO'})
                                        
                                        if novos:
                                            df_db = pd.concat([df_db, pd.DataFrame(novos)], ignore_index=True)
                                    
                                    salvar_dados(df_db, ABA_JOGOS)

    # --- ABA CONSULTA ---
    elif menu == "📊 Consulta":
        if fmt == "LIGA":
            st.subheader("📈 Tabela de Classificação")
            times = pd.concat([df_t['a'], df_t['b']]).unique()
            stats = {t: {'P':0,'J':0,'V':0,'E':0,'D':0,'GP':0,'GC':0,'SG':0} for t in times if pd.notna(t) and t != "BYE"}
            for _, r in df_t[df_t['finalizado'] == 'SIM'].iterrows():
                t1, t2, g1, g2 = r['a'], r['b'], int(r['gols_a']), int(r['gols_b'])
                if t1 in stats and t2 in stats:
                    stats[t1]['J']+=1; stats[t2]['J']+=1; stats[t1]['GP']+=g1; stats[t1]['GC']+=g2; stats[t2]['GP']+=g2; stats[t2]['GC']+=g1
                    if g1 > g2: stats[t1]['P']+=3; stats[t1]['V']+=1; stats[t2]['D']+=1
                    elif g2 > g1: stats[t2]['P']+=3; stats[t2]['V']+=1; stats[t1]['D']+=1
                    else: stats[t1]['P']+=1; stats[t2]['P']+=1; stats[t1]['E']+=1; stats[t2]['E']+=1
                    stats[t1]['SG'] = stats[t1]['GP'] - stats[t1]['GC']; stats[t2]['SG'] = stats[t2]['GP'] - stats[t2]['GC']
            st.table(pd.DataFrame.from_dict(stats, orient='index').sort_values(by=['P','V','SG','GP'], ascending=False))
        else:
            st.subheader("🗺️ Chaveamento do Torneio")
            f_p = ["Oitavas", "Quartas", "Semifinal", "3º Lugar", "Final"]
            cols = st.columns(len(f_p))
            for i, fase_nome in enumerate(f_p):
                with cols[i]:
                    st.markdown(f"**{fase_nome.upper()}**")
                    for _, r in df_t[df_t['fase'] == fase_nome].iterrows():
                        v, _ = obter_vencedor_perdedor(r)
                        b_c = "#F4D03F" if is_done(r['finalizado']) else "#ccc"
                        st.markdown(f'<div style="border:2px solid {b_c}; padding:8px; border-radius:10px; background:white; color:black; margin-bottom:10px; text-align:center; font-size:12px;"><b>{r["a"]} x {r["b"]}</b><br>V: {v if v else "---"}</div>', unsafe_allow_html=True)

    # --- ABA ADMIN ---
    elif menu == "⚙️ Admin" and is_admin:
        if df_t.empty:
            txt = st.text_area("Lista de Times (um por linha)")
            if st.button("GERAR"):
                times = [x.strip() for x in txt.split('\n') if x.strip()]
                if len(times)>=2:
                    jogos = []
                    if fmt=="LIGA":
                        for a,b in combinations(times, 2):
                            jogos.append({'torneio_id':tid,'formato':fmt,'fase':'Liga','a':a,'b':b,'modo_copa':'Só Ida','finalizado':'NÃO','gols_a':0,'gols_b':0,'ida_a':0,'ida_b':0,'volta_a':0,'volta_b':0,'pen_a':0,'pen_b':0})
                    else:
                        fase_ini = "Semifinal" if len(times)<=4 else "Quartas"
                        for i in range(0, len(times), 2):
                            t1 = times[i]
                            t2 = times[i+1] if i+1 < len(times) else "BYE"
                            jogos.append({'torneio_id':tid,'formato':fmt,'fase':fase_ini,'a':t1,'b':t2,'modo_copa':st.session_state.get('modo','Só Ida'),'finalizado':'NÃO','gols_a':0,'gols_b':0,'ida_a':0,'ida_b':0,'volta_a':0,'volta_b':0,'pen_a':0,'pen_b':0})
                    salvar_dados(pd.concat([df_db, pd.DataFrame(jogos)], ignore_index=True), ABA_JOGOS)
        else:
            if st.button("🏆 ENCERRAR E SALVAR NO HALL DA FAMA"):
                h_br = (datetime.utcnow() - timedelta(hours=3)).strftime("%d/%m/%Y %H:%M")
                camp, vice, terc = "---", "---", "---"
                if fmt == "COPA":
                    fin = df_t[df_t['fase'] == 'Final']
                    t3 = df_t[df_t['fase'] == '3º Lugar']
                    if not fin.empty: camp, vice = obter_vencedor_perdedor(fin.iloc[0])
                    if not t3.empty: terc, _ = obter_vencedor_perdedor(t3.iloc[0])
                else: # LIGA
                    times = pd.concat([df_t['a'], df_t['b']]).unique()
                    # (Reaproveita lógica da tabela para achar o campeão...)
                
                nova_h = pd.DataFrame([{'torneio_id':tid,'formato':fmt,'campeao':camp,'vice':vice,'terceiro':terc,'data_fim':h_br}])
                salvar_dados(pd.concat([df_hist, nova_h], ignore_index=True), ABA_HISTORICO)
            
            if st.button("🚨 EXCLUIR ESTE TORNEIO"):
                salvar_dados(df_db[df_db['torneio_id'] != tid], ABA_JOGOS)
                st.session_state.torneio_ativo = None; st.rerun()
