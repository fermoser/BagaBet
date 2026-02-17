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
    /* Ajuste para alinhar inputs lado a lado */
    [data-testid="stForm"] .stColumn { display: flex; align-items: center; justify-content: center; }
    </style>
    """, unsafe_allow_html=True)

conn = st.connection("gsheets", type=GSheetsConnection)
ABA_JOGOS = "Página1" 
ABA_HISTORICO = "Historico"
COLUNAS = ['torneio_id', 'formato', 'fase', 'a', 'b', 'finalizado', 'gols_a', 'gols_b', 'ida_a', 'ida_b', 'volta_a', 'volta_b', 'pen_a', 'pen_b', 'modo_copa']

ORDEM_FASES = {"Oitavas": 1, "Quartas": 2, "Semifinal": 3, "3º Lugar": 4, "Final": 5, "Liga": 6, "Turno Único": 6}

# --- FUNÇÕES DE DADOS ---
def carregar_dados(aba):
    try:
        df = conn.read(worksheet=aba, ttl="0s")
        if df is None or df.empty:
            return pd.DataFrame(columns=COLUNAS) if aba == ABA_JOGOS else pd.DataFrame(columns=['torneio_id','formato','campeao','vice','terceiro','data_fim'])
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

def is_done(val): return str(val).upper().strip() in ["1", "SIM", "TRUE"]

def obter_vencedor_perdedor(r):
    if not is_done(r['finalizado']): return None, None
    if r['fase'] in ["Final", "3º Lugar", "Liga", "Turno Único"] or r['modo_copa'] == "Só Ida":
        sa, sb = int(r['gols_a']), int(r['gols_b'])
    else:
        sa, sb = int(r['ida_a']) + int(r['volta_a']), int(r['ida_b']) + int(r['volta_b'])
    
    if sa > sb: return r['a'], r['b']
    elif sb > sa: return r['b'], r['a']
    else:
        pa, pb = int(r.get('pen_a', 0)), int(r.get('pen_b', 0))
        if pa > pb: return r['a'], r['b']
        if pb > pa: return r['b'], r['a']
        return None, None

# --- GESTÃO DE ESTADO ---
if 'torneio_ativo' not in st.session_state: st.session_state.torneio_ativo = None

df_db = carregar_dados(ABA_JOGOS)
df_hist = carregar_dados(ABA_HISTORICO)

# --- TELA INICIAL ---
if st.session_state.torneio_ativo is None:
    st.title("⚽ BAGA GESTOR PRO")
    with st.expander("📜 HALL DA FAMA"):
        if not df_hist.empty: st.dataframe(df_hist.sort_index(ascending=False), use_container_width=True)
    torneios = df_db['torneio_id'].unique() if not df_db.empty else []
    if len(torneios) > 0:
        st.subheader("📂 Abrir Torneio")
        cols = st.columns(3)
        for i, t in enumerate(torneios):
            if cols[i%3].button(f"🏆 {t}", key=f"t_{t}", use_container_width=True):
                st.session_state.torneio_ativo = t
                st.rerun()
    st.divider()
    with st.form("novo_t"):
        st.subheader("🆕 Criar Novo")
        c1, c2, c3 = st.columns(3)
        n = c1.text_input("Nome")
        tipo_t = c2.selectbox("Tipo", ["COPA", "LIGA"])
        modo_t = c3.selectbox("Modo", ["Só Ida", "Ida e Volta"]) if tipo_t == "COPA" else "Só Ida"
        if st.form_submit_button("CRIAR"):
            if n: st.session_state.torneio_ativo = n; st.session_state.temp_fmt = tipo_t; st.session_state.temp_modo = modo_t; st.rerun()

else:
    tid = st.session_state.torneio_ativo
    df_t = df_db[df_db['torneio_id'] == tid].copy()
    fmt = df_t['formato'].iloc[0] if not df_t.empty else st.session_state.get('temp_fmt', 'COPA')

    with st.sidebar:
        st.header(f"🏆 {tid}")
        menu = st.radio("Menu", ["🏟️ Jogos", "📊 Consulta", "⚙️ Admin"])
        is_admin = (st.text_input("Senha Admin", type="password") == "1234")
        if st.button("🏠 Sair"): st.session_state.torneio_ativo = None; st.rerun()

    if menu == "🏟️ Jogos":
        if df_t.empty: st.info("Gere os jogos no Admin.")
        else:
            for f in sorted(df_t['fase'].unique(), key=lambda x: ORDEM_FASES.get(x, 99)):
                st.subheader(f"📍 {f}")
                for idx, r in df_t[df_t['fase'] == f].iterrows():
                    with st.container(border=True):
                        c1, c2, c3 = st.columns([2,1,2])
                        # Lógica de exibição visual do placar
                        if fmt == "LIGA" or r['modo_copa'] == "Só Ida":
                            p_txt = f"{r['gols_a']} x {r['gols_b']}"
                        else:
                            p_txt = f"({r['ida_a']}) {r['volta_a']} x {r['volta_b']} ({r['ida_b']})"
                        
                        if is_done(r['finalizado']) and (int(r['pen_a'])+int(r['pen_b'])>0):
                            p_txt += f" (P: {r['pen_a']}x{r['pen_b']})"
                        
                        c1.markdown(f"<p style='text-align:right'><b>{r['a']}</b></p>", unsafe_allow_html=True)
                        c2.markdown(f"<div style='text-align:center; background:#eee; padding:5px; color:black;'>{p_txt}</div>", unsafe_allow_html=True)
                        c3.markdown(f"<p style='text-align:left'><b>{r['b']}</b></p>", unsafe_allow_html=True)
                        
                        if is_admin:
                            with st.expander("✎ Lançar Resultado"):
                                with st.form(f"form_{idx}"):
                                    # --- PARTE DA LIGA OU SÓ IDA ---
                                    if fmt == "LIGA" or r['modo_copa'] == "Só Ida":
                                        ca, cb = st.columns(2)
                                        ga = ca.number_input(f"Gols {r['a']}", 0, 99, int(r['gols_a']), key=f"ga_{idx}")
                                        gb = cb.number_input(f"Gols {r['b']}", 0, 99, int(r['gols_b']), key=f"gb_{idx}")
                                        res, total_a, total_b = [ga, gb, ga, gb, 0, 0], ga, gb
                                    
                                    # --- PARTE DA COPA IDA E VOLTA ---
                                    else:
                                        with st.expander("⚽ JOGO DE IDA", expanded=True):
                                            c_ida_a, c_ida_b = st.columns(2)
                                            ia = c_ida_a.number_input(f"Gols {r['a']}", 0, 99, int(r['ida_a']), key=f"ia_{idx}")
                                            ib = c_ida_b.number_input(f"Gols {r['b']}", 0, 99, int(r['ida_b']), key=f"ib_{idx}")
                                        with st.expander("⚽ JOGO DE VOLTA", expanded=True):
                                            c_v_a, c_v_b = st.columns(2)
                                            va = c_v_a.number_input(f"Gols {r['a']}", 0, 99, int(r['volta_a']), key=f"va_{idx}")
                                            vb = c_v_b.number_input(f"Gols {r['b']}", 0, 99, int(r['volta_b']), key=f"vb_{idx}")
                                        res, total_a, total_b = [ia+va, ib+vb, ia, ib, va, vb], (ia+va), (ib+vb)

                                    # --- PÊNALTIS (SÓ SE HOUVER EMPATE) ---
                                    pa, pb = 0, 0
                                    if fmt == "COPA" and total_a == total_b and r['a'] != "BYE" and r['b'] != "BYE":
                                        with st.expander("🎯 DISPUTA DE PÊNALTIS", expanded=True):
                                            cpa, cpb = st.columns(2)
                                            pa = cpa.number_input(f"Pênaltis {r['a']}", 0, 99, int(r['pen_a']), key=f"pa_{idx}")
                                            pb = cpb.number_input(f"Pênaltis {r['b']}", 0, 99, int(r['pen_b']), key=f"pb_{idx}")

                                    if st.form_submit_button("CONFIRMAR RESULTADO"):
                                        df_db.loc[idx, ['gols_a','gols_b','ida_a','ida_b','volta_a','volta_b','pen_a','pen_b','finalizado']] = res + [pa, pb, "SIM"]
                                        # Lógica de Avanço Automático para Copa
                                        if fmt == "COPA":
                                            df_fase = df_db[(df_db['torneio_id'] == tid) & (df_db['fase'] == r['fase'])]
                                            if all(df_fase['finalizado'].apply(is_done)):
                                                v, p = [], []
                                                for _, rf in df_fase.iterrows():
                                                    vw, pl = obter_vencedor_perdedor(rf)
                                                    if vw: v.append(vw); p.append(pl)
                                                novos = []
                                                if r['fase'] == "Semifinal" and len(v)>=2:
                                                    novos.append({'torneio_id':tid,'formato':'COPA','fase':'Final','a':v[0],'b':v[1],'modo_copa':'Só Ida','finalizado':'NÃO'})
                                                    novos.append({'torneio_id':tid,'formato':'COPA','fase':'3º Lugar','a':p[0],'b':p[1],'modo_copa':'Só Ida','finalizado':'NÃO'})
                                                elif r['fase'] == "Quartas" and len(v)>=4:
                                                    for i in range(0, len(v), 2): novos.append({'torneio_id':tid,'formato':'COPA','fase':'Semifinal','a':v[i],'b':v[i+1],'modo_copa':r['modo_copa'],'finalizado':'NÃO'})
                                                if novos: df_db = pd.concat([df_db, pd.DataFrame(novos)], ignore_index=True)
                                        salvar_dados(df_db, ABA_JOGOS); st.rerun()

    elif menu == "📊 Consulta":
        if fmt == "LIGA":
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
            f_p = ["Oitavas", "Quartas", "Semifinal", "3º Lugar", "Final"]
            cols = st.columns(len(f_p))
            for i, fn in enumerate(f_p):
                with cols[i]:
                    st.markdown(f"**{fn.upper()}**")
                    for _, r in df_t[df_t['fase'] == fn].iterrows():
                        vw, _ = obter_vencedor_perdedor(r)
                        b_c = "#F4D03F" if is_done(r['finalizado']) else "#ccc"
                        st.markdown(f'<div style="border:2px solid {b_c}; padding:5px; border-radius:5px; background:white; color:black; margin-bottom:5px; text-align:center; font-size:11px;">{r["a"]} x {r["b"]}<br><b>V: {vw if vw else "-"}</b></div>', unsafe_allow_html=True)

    elif menu == "⚙️ Admin" and is_admin:
        if df_t.empty:
            txt = st.text_area("Lista de Times")
            if st.button("GERAR TORNEIO"):
                times = [x.strip() for x in txt.split('\n') if x.strip()]
                if len(times)>=2:
                    jogos = []
                    # LIGA INTACTA
                    if fmt == "LIGA":
                        for a, b in combinations(times, 2): jogos.append({'torneio_id':tid,'formato':'LIGA','fase':'Liga','a':a,'b':b,'modo_copa':'Só Ida','finalizado':'NÃO'})
                    # COPA CORRIGIDA
                    else:
                        f_ini = "Semifinal" if len(times)<=4 else "Quartas"
                        for i in range(0, len(times), 2):
                            t1, t2 = times[i], (times[i+1] if i+1 < len(times) else "BYE")
                            jogos.append({'torneio_id':tid,'formato':'COPA','fase':f_ini,'a':t1,'b':t2,'modo_copa':st.session_state.get('temp_modo', 'Só Ida'),'finalizado':'NÃO'})
                    salvar_dados(pd.concat([df_db, pd.DataFrame(jogos)], ignore_index=True), ABA_JOGOS); st.rerun()
        else:
            if st.button("🏆 ENCERRAR (HALL DA FAMA)"):
                h_br = (datetime.utcnow() - timedelta(hours=3)).strftime("%d/%m/%Y %H:%M")
                c, v, t = "---", "---", "---"
                if fmt == "COPA":
                    fin, t3 = df_t[df_t['fase'] == 'Final'], df_t[df_t['fase'] == '3º Lugar']
                    if not fin.empty: c, v = obter_vencedor_perdedor(fin.iloc[0])
                    if not t3.empty: t, _ = obter_vencedor_perdedor(t3.iloc[0])
                else: # Lógica de Liga preservada
                    tm = pd.concat([df_t['a'], df_t['b']]).unique()
                    stt = {tmx: {'P':0,'V':0,'SG':0,'GP':0} for tmx in tm if pd.notna(tmx) and tmx != "BYE"}
                    for _, r in df_t[df_t['finalizado'] == 'SIM'].iterrows():
                        t1, t2, g1, g2 = r['a'], r['b'], int(r['gols_a']), int(r['gols_b'])
                        if t1 in stt and t2 in stt:
                            stt[t1]['GP']+=g1; stt[t2]['GP']+=g2
                            if g1 > g2: stt[t1]['P']+=3; stt[t1]['V']+=1
                            elif g2 > g1: stt[t2]['P']+=3; stt[t2]['V']+=1
                            else: stt[t1]['P']+=1; stt[t2]['P']+=1
                            stt[t1]['SG'] = stt[t1]['GP'] - g2; stt[t2]['SG'] = stt[t2]['GP'] - g1
                    res_l = pd.DataFrame.from_dict(stt, orient='index').sort_values(by=['P','V','SG','GP'], ascending=False).index.tolist()
                    if len(res_l) >= 1: c = res_l[0]
                    if len(res_l) >= 2: v = res_l[1]
                    if len(res_l) >= 3: t = res_l[2]
                nova_h = pd.DataFrame([{'torneio_id':tid,'formato':fmt,'campeao':c,'vice':v,'terceiro':t,'data_fim':h_br}])
                salvar_dados(pd.concat([df_hist, nova_h], ignore_index=True), ABA_HISTORICO); st.rerun()
            if st.button("🚨 EXCLUIR"):
                salvar_dados(df_db[df_db['torneio_id'] != tid], ABA_JOGOS); st.session_state.torneio_ativo = None; st.rerun()
