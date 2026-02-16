import streamlit as st
import pandas as pd
from itertools import combinations
from streamlit_gsheets import GSheetsConnection
from datetime import datetime, timedelta

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="BAGA GESTOR PRO", layout="wide")

# --- ESTILO CSS (NÚMEROS EM AMARELO SUAVE) ---
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
    conn.update(worksheet=aba, data=df.copy())
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
        elif pb > pa: return r['b'], r['a']
        return None, None # Empate total sem pênaltis definidos

# --- LÓGICA DE AVANÇO AUTOMÁTICO ---
def verificar_e_avancar(df_atual, tid, fmt):
    df_t = df_atual[df_atual['torneio_id'] == tid]
    if df_t.empty: return df_atual
    
    ultima_fase = df_t['fase'].unique()[-1]
    if ultima_fase in ["Final", "3º Lugar"]: return df_atual
    
    jogos_fase = df_t[df_t['fase'] == ultima_fase]
    if all(jogos_fase['finalizado'].apply(is_done)):
        venc, perd = [], []
        for _, r in jogos_fase.iterrows():
            v, p = obter_vencedor_perdedor(r)
            if v: venc.append(v)
            if p: perd.append(p)
        
        # Só avança se todos os jogos tiverem um vencedor (pênaltis decididos se empate)
        if len(venc) == len(jogos_fase):
            novos = []
            prox_fase = "Final" if ultima_fase == "Semifinal" else ("Semifinal" if ultima_fase == "Quartas" else "Quartas")
            modo_c = jogos_fase.iloc[0]['modo_copa']
            
            for i in range(0, len(venc), 2):
                if i+1 < len(venc):
                    novos.append({'torneio_id':tid,'formato':fmt,'fase':prox_fase,'a':venc[i],'b':venc[i+1],'modo_copa':modo_c,'finalizado':'NÃO'})
            
            if ultima_fase == "Semifinal":
                for i in range(0, len(perd), 2):
                    if i+1 < len(perd):
                        novos.append({'torneio_id':tid,'formato':fmt,'fase':'3º Lugar','a':perd[i],'b':perd[i+1],'modo_copa':modo_c,'finalizado':'NÃO'})
            
            if novos:
                return pd.concat([df_atual, pd.DataFrame(novos)], ignore_index=True)
    return df_atual

# --- APP ---
df_db = carregar_dados(ABA_JOGOS)
df_hist = carregar_dados(ABA_HISTORICO)

if 'torneio_ativo' not in st.session_state: st.session_state.torneio_ativo = None

if st.session_state.torneio_ativo is None:
    st.title("⚽ BAGA GESTOR PRO")
    with st.expander("📜 HALL DA FAMA", expanded=True):
        if not df_hist.empty: st.dataframe(df_hist.sort_index(ascending=False), use_container_width=True)
    
    torneios = df_db['torneio_id'].unique() if not df_db.empty else []
    if len(torneios) > 0:
        with st.expander("📂 CARREGAR TORNEIO", expanded=True):
            cols = st.columns(3)
            for i, t in enumerate(torneios):
                if cols[i%3].button(f"🏆 {t}", key=f"t_{t}"):
                    st.session_state.torneio_ativo = t
                    st.session_state.formato = df_db[df_db['torneio_id']==t]['formato'].iloc[0]
                    st.rerun()
    
    with st.form("novo"):
        st.subheader("🆕 Novo Torneio")
        c1, c2, c3 = st.columns(3)
        n, t, m = c1.text_input("Nome"), c2.selectbox("Tipo", ["COPA", "LIGA"]), c3.selectbox("Modo", ["Só Ida", "Ida e Volta"])
        if st.form_submit_button("CRIAR"):
            if n: st.session_state.torneio_ativo, st.session_state.formato, st.session_state.modo = n, t, m; st.rerun()

else:
    tid, fmt = st.session_state.torneio_ativo, st.session_state.formato
    df_t = df_db[df_db['torneio_id'] == tid].copy()

    with st.sidebar:
        menu = st.radio("Menu", ["🏟️ Jogos", "📊 Consulta", "⚙️ Admin"])
        is_admin = (st.text_input("Senha", type="password") == "1234")
        if st.button("🏠 Sair"): st.session_state.torneio_ativo = None; st.rerun()

    if menu == "🏟️ Jogos":
        for f in df_t['fase'].unique():
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
                        with st.expander("✎ Editar Placar"):
                            with st.form(f"ed_{idx}"):
                                ca, cb = st.columns(2)
                                if fmt=="LIGA" or r['modo_copa']=="Só Ida":
                                    ga, gb = ca.number_input("Gols A",0,99,int(r['gols_a'])), cb.number_input("Gols B",0,99,int(r['gols_b']))
                                    res, saldo_a, saldo_b = [ga, gb, ga, gb, 0, 0], ga, gb
                                else:
                                    ia, ib = ca.number_input("Ida A",0,99,int(r['ida_a'])), cb.number_input("Ida B",0,99,int(r['ida_b']))
                                    va, vb = ca.number_input("Volta A",0,99,int(r['volta_a'])), cb.number_input("Volta B",0,99,int(r['volta_b']))
                                    res, saldo_a, saldo_b = [ia+va, ib+vb, ia, ib, va, vb], (ia+va), (ib+vb)
                                
                                pa, pb = 0, 0
                                if fmt == "COPA" and saldo_a == saldo_b and r['a'] != "BYE" and r['b'] != "BYE":
                                    st.warning("Empate detectado! Informe os Pênaltis:")
                                    cpa, cpb = st.columns(2)
                                    pa = cpa.number_input("Pen A", 0, 99, int(r['pen_a']))
                                    pb = cpb.number_input("Pen B", 0, 99, int(r['pen_b']))
                                
                                if st.form_submit_button("Confirmar"):
                                    if fmt == "COPA" and saldo_a == saldo_b and pa == pb:
                                        st.error("Em caso de empate no saldo, os pênaltis não podem ser iguais!")
                                    else:
                                        df_db.loc[idx, ['gols_a','gols_b','ida_a','ida_b','volta_a','volta_b','pen_a','pen_b','finalizado']] = res + [pa, pb, "SIM"]
                                        # AVANÇO AUTOMÁTICO AQUI
                                        df_db = verificar_e_avancar(df_db, tid, fmt)
                                        salvar_dados(df_db, ABA_JOGOS)

    elif menu == "📊 Consulta":
        if fmt == "LIGA":
            times = pd.concat([df_t['a'], df_t['b']]).unique()
            stats = {t: {'P':0,'J':0,'V':0,'E':0,'D':0,'GP':0,'GC':0,'SG':0} for t in times if pd.notna(t)}
            for _, r in df_t[df_t['finalizado'] == 'SIM'].iterrows():
                t1, t2, g1, g2 = r['a'], r['b'], int(r['gols_a']), int(r['gols_b'])
                stats[t1]['J']+=1; stats[t2]['J']+=1; stats[t1]['GP']+=g1; stats[t1]['GC']+=g2; stats[t2]['GP']+=g2; stats[t2]['GC']+=g1
                if g1 > g2: stats[t1]['P']+=3; stats[t1]['V']+=1; stats[t2]['D']+=1
                elif g2 > g1: stats[t2]['P']+=3; stats[t2]['V']+=1; stats[t1]['D']+=1
                else: stats[t1]['P']+=1; stats[t2]['P']+=1; stats[t1]['E']+=1; stats[t2]['E']+=1
                stats[t1]['SG'] = stats[t1]['GP'] - stats[t1]['GC']; stats[t2]['SG'] = stats[t2]['GP'] - stats[t2]['GC']
            st.table(pd.DataFrame.from_dict(stats, orient='index').sort_values(by=['P','V','SG','GP'], ascending=False))
        else:
            f_p = ["Oitavas", "Quartas", "Semifinal", "Final", "3º Lugar"]
            cols = st.columns(len(f_p))
            for i, fase in enumerate(f_p):
                with cols[i]:
                    st.markdown(f"**{fase.upper()}**")
                    for _, r in df_t[df_t['fase'] == fase].iterrows():
                        v, _ = obter_vencedor_perdedor(r)
                        b_c = "#F4D03F" if is_done(r['finalizado']) else "#ccc"
                        st.markdown(f'<div style="border:2px solid {b_c}; padding:8px; border-radius:10px; background:white; color:black; margin-bottom:10px; text-align:center; font-size:12px;"><b>{r["a"]} x {r["b"]}</b><br>Vencedor: {v if v else "---"}</div>', unsafe_allow_html=True)

    elif menu == "⚙️ Admin" and is_admin:
        if df_t.empty:
            txt = st.text_area("Times (um por linha)")
            if st.button("GERAR TORNEIO"):
                times = [x.strip() for x in txt.split('\n') if x.strip()]
                if len(times)>=2:
                    jogos = []
                    if fmt=="LIGA":
                        for a,b in combinations(times,2):
                            jogos.append({'torneio_id':tid,'formato':fmt,'fase':'Turno Único','a':a,'b':b,'modo_copa':'Só Ida','finalizado':'NÃO'})
                    else:
                        fase = "Semifinal" if len(times)<=4 else ("Quartas" if len(times)<=8 else "Oitavas")
                        for i in range(0, len(times), 2):
                            jogos.append({'torneio_id':tid,'formato':fmt,'fase':fase,'a':times[i],'b':times[i+1] if i+1<len(times) else "BYE",'modo_copa':st.session_state.get('modo','Só Ida'),'finalizado':'NÃO'})
                    salvar_dados(pd.concat([df_db, pd.DataFrame(jogos)], ignore_index=True), ABA_JOGOS)
        else:
            if st.button("🏆 FINALIZAR E SALVAR NO HALL DA FAMA"):
                h_br = (datetime.utcnow() - timedelta(hours=3)).strftime("%d/%m/%Y %H:%M")
                camp, vice, terc = "---", "---", "---"
                fin = df_t[df_t['fase'] == 'Final']
                t3 = df_t[df_t['fase'] == '3º Lugar']
                if not fin.empty: camp, vice = obter_vencedor_perdedor(fin.iloc[0])
                if not t3.empty: terc, _ = obter_vencedor_perdedor(t3.iloc[0])
                nova_h = pd.DataFrame([{'torneio_id':tid,'formato':fmt,'campeao':camp,'vice':vice,'terceiro':terc,'data_fim':h_br}])
                salvar_dados(pd.concat([df_hist, nova_h], ignore_index=True), ABA_HISTORICO)
            st.button("🚨 EXCLUIR", on_click=lambda: salvar_dados(df_db[df_db['torneio_id'] != tid], ABA_JOGOS))
