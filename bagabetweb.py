import streamlit as st
import pandas as pd
from itertools import combinations
from streamlit_gsheets import GSheetsConnection
from datetime import datetime, timedelta

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="BAGA GESTOR PRO", layout="wide")

# --- ESTILO CSS MODERNO ---
st.markdown("""
    <style>
    input[type=number] { color: #F4D03F !important; font-weight: bold !important; font-size: 20px !important; }
    .stMarkdown div[style*="background:#eee"] { background-color: #333 !important; color: #F4D03F !important; font-weight: bold; border-radius: 5px; }
    [data-testid="stForm"] .stColumn { display: flex; align-items: center; justify-content: center; }
    
    /* Estilos para o Chaveamento */
    .match-card {
        background-color: #1E1E1E;
        border-radius: 10px;
        padding: 10px;
        margin-bottom: 15px;
        border: 2px solid #333;
        color: white;
        box-shadow: 3px 3px 10px rgba(0,0,0,0.5);
    }
    .winner-card {
        border: 2px solid #28a745 !important;
        box-shadow: 0 0 10px #28a745;
    }
    .team-row {
        display: flex;
        justify-content: space-between;
        padding: 5px 0;
        font-size: 14px;
    }
    .score-box {
        background: #F4D03F;
        color: black;
        padding: 2px 8px;
        border-radius: 4px;
        font-weight: bold;
    }
    .winner-label {
        color: #28a745;
        font-size: 10px;
        font-weight: bold;
        text-transform: uppercase;
    }
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

# --- INICIALIZAÇÃO ---
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
        st.subheader("📂 Meus Torneios")
        cols = st.columns(3)
        for i, t in enumerate(torneios):
            if cols[i%3].button(f"🏆 {t}", key=f"sel_{t}", use_container_width=True):
                st.session_state.torneio_ativo = t
                st.rerun()

    st.divider()
    st.subheader("🆕 Criar Novo")
    col_l, col_c = st.columns(2)
    with col_l.container(border=True):
        st.markdown("### 🏆 MODO LIGA")
        nome_liga = st.text_input("Nome da Liga", key="n_liga")
        if st.button("CRIAR LIGA", use_container_width=True):
            if nome_liga:
                df_init = pd.DataFrame([{'torneio_id':nome_liga, 'formato':'LIGA', 'modo_copa':'Só Ida', 'finalizado':'NÃO'}])
                salvar_dados(pd.concat([df_db, df_init], ignore_index=True), ABA_JOGOS)
                st.session_state.torneio_ativo = nome_liga
                st.rerun()

    with col_c.container(border=True):
        st.markdown("### ⚔️ MODO COPA")
        nome_copa = st.text_input("Nome da Copa", key="n_copa")
        modo_copa = st.selectbox("Formato da Copa", ["Só Ida", "Ida e Volta"])
        if st.button("CRIAR COPA", use_container_width=True):
            if nome_copa:
                df_init = pd.DataFrame([{'torneio_id':nome_copa, 'formato':'COPA', 'modo_copa':modo_copa, 'finalizado':'NÃO'}])
                salvar_dados(pd.concat([df_db, df_init], ignore_index=True), ABA_JOGOS)
                st.session_state.torneio_ativo = nome_copa
                st.rerun()

else:
    tid = st.session_state.torneio_ativo
    df_t = df_db[df_db['torneio_id'] == tid].copy()
    row_info = df_t.iloc[0]
    fmt = row_info['formato']
    modo_fixo = row_info['modo_copa']

    with st.sidebar:
        st.header(f"🏆 {tid}")
        menu = st.radio("Menu", ["🏟️ Jogos", "📊 Consulta", "⚙️ Admin"])
        is_admin = (st.text_input("Senha Admin", type="password") == "1234")
        if st.button("🏠 Sair"): st.session_state.torneio_ativo = None; st.rerun()

    if menu == "🏟️ Jogos":
        if df_t['a'].isnull().all(): st.info("Acesse 'Admin' para gerar os jogos.")
        else:
            for f in sorted(df_t['fase'].dropna().unique(), key=lambda x: ORDEM_FASES.get(x, 99)):
                st.subheader(f"📍 {f}")
                for idx, r in df_t[df_t['fase'] == f].iterrows():
                    with st.container(border=True):
                        c1, c2, c3 = st.columns([2,1,2])
                        p_txt = f"{r['gols_a']} x {r['gols_b']}" if fmt == "LIGA" or r['modo_copa'] == "Só Ida" else f"({r['ida_a']}) {r['volta_a']} x {r['volta_b']} ({r['ida_b']})"
                        if is_done(r['finalizado']) and (int(r['pen_a'])+int(r['pen_b'])>0): p_txt += f" (P: {r['pen_a']}x{r['pen_b']})"
                        c1.markdown(f"<p style='text-align:right'><b>{r['a']}</b></p>", unsafe_allow_html=True)
                        c2.markdown(f"<div style='text-align:center; background:#eee; padding:5px; color:black;'>{p_txt}</div>", unsafe_allow_html=True)
                        c3.markdown(f"<p style='text-align:left'><b>{r['b']}</b></p>", unsafe_allow_html=True)
                        if is_admin:
                            with st.expander("✎ Editar Placar"):
                                with st.form(f"f_{idx}"):
                                    if fmt == "LIGA" or r['modo_copa'] == "Só Ida":
                                        ca, cb = st.columns(2)
                                        ga, gb = ca.number_input(f"Gols {r['a']}",0,99,int(r['gols_a'])), cb.number_input(f"Gols {r['b']}",0,99,int(r['gols_b']))
                                        res, tot_a, tot_b = [ga, gb, ga, gb, 0, 0], ga, gb
                                    else:
                                        with st.expander("⚽ IDA", expanded=True):
                                            cia, cib = st.columns(2)
                                            ia, ib = cia.number_input(f"Gols {r['a']}",0,99,int(r['ida_a'])), cib.number_input(f"Gols {r['b']}",0,99,int(r['ida_b']))
                                        with st.expander("⚽ VOLTA", expanded=True):
                                            cva, cvb = st.columns(2)
                                            va, vb = cva.number_input(f"Gols {r['a']}",0,99,int(r['volta_a'])), cvb.number_input(f"Gols {r['b']}",0,99,int(r['volta_b']))
                                        res, tot_a, tot_b = [ia+va, ib+vb, ia, ib, va, vb], (ia+va), (ib+vb)
                                    pa, pb = 0, 0
                                    if fmt == "COPA" and tot_a == tot_b and r['a'] != "BYE" and r['b'] != "BYE":
                                        with st.expander("🎯 PÊNALTIS", expanded=True):
                                            cpa, cpb = st.columns(2)
                                            pa, pb = cpa.number_input(f"Pênaltis {r['a']}",0,99,int(r['pen_a'])), cpb.number_input(f"Pênaltis {r['b']}",0,99,int(r['pen_b']))
                                    if st.form_submit_button("SALVAR"):
                                        df_db.loc[idx, ['gols_a','gols_b','ida_a','ida_b','volta_a','volta_b','pen_a','pen_b','finalizado']] = res + [pa, pb, "SIM"]
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
            tm = pd.concat([df_t['a'], df_t['b']]).dropna().unique()
            stt = {t: {'P':0,'J':0,'V':0,'E':0,'D':0,'GP':0,'GC':0,'SG':0} for t in tm if t != "BYE"}
            for _, r in df_t[df_t['finalizado'] == 'SIM'].iterrows():
                t1, t2, g1, g2 = r['a'], r['b'], int(r['gols_a']), int(r['gols_b'])
                if t1 in stt and t2 in stt:
                    stt[t1]['J']+=1; stt[t2]['J']+=1; stt[t1]['GP']+=g1; stt[t1]['GC']+=g2; stt[t2]['GP']+=g2; stt[t2]['GC']+=g1
                    if g1 > g2: stt[t1]['P']+=3; stt[t1]['V']+=1; stt[t2]['D']+=1
                    elif g2 > g1: stt[t2]['P']+=3; stt[t2]['V']+=1; stt[t1]['D']+=1
                    else: stt[t1]['P']+=1; stt[t2]['P']+=1; stt[t1]['E']+=1; stt[t2]['E']+=1
                    stt[t1]['SG'] = stt[t1]['GP'] - stt[t1]['GC']; stt[t2]['SG'] = stt[t2]['GP'] - stt[t2]['GC']
            st.table(pd.DataFrame.from_dict(stt, orient='index').sort_values(by=['P','V','SG','GP'], ascending=False))
        else:
            f_p = ["Oitavas", "Quartas", "Semifinal", "3º Lugar", "Final"]
            cols = st.columns(len(f_p))
            for i, fn in enumerate(f_p):
                with cols[i]:
                    st.markdown(f"#### {fn.upper()}")
                    for _, r in df_t[df_t['fase'] == fn].iterrows():
                        v_win, _ = obter_vencedor_perdedor(r)
                        done = is_done(r['finalizado'])
                        
                        # Definição dos placares para o card
                        if r['modo_copa'] == "Só Ida":
                            sc_a, sc_b = int(r['gols_a']), int(r['gols_b'])
                        else:
                            sc_a, sc_b = int(r['ida_a']) + int(r['volta_a']), int(r['ida_b']) + int(r['volta_b'])
                        
                        # Card HTML dinâmico
                        card_class = "match-card winner-card" if done else "match-card"
                        st.markdown(f"""
                        <div class="{card_class}">
                            <div class="team-row">
                                <span style="{'color:#28a745; font-weight:bold;' if v_win == r['a'] else ''}">{r['a']}</span>
                                <span class="score-box">{sc_a}</span>
                            </div>
                            <div class="team-row">
                                <span style="{'color:#28a745; font-weight:bold;' if v_win == r['b'] else ''}">{r['b']}</span>
                                <span class="score-box">{sc_b}</span>
                            </div>
                            {f'<div class="winner-label">🏆 {v_win}</div>' if v_win else ''}
                        </div>
                        """, unsafe_allow_html=True)

    elif menu == "⚙️ Admin" and is_admin:
        if df_t['a'].isnull().all():
            txt = st.text_area("Lista de Times (um por linha)")
            if st.button("GERAR JOGOS"):
                times = [x.strip() for x in txt.split('\n') if x.strip()]
                if len(times)>=2:
                    jogos = []
                    if fmt == "LIGA":
                        for a, b in combinations(times, 2): jogos.append({'torneio_id':tid,'formato':'LIGA','fase':'Liga','a':a,'b':b,'modo_copa':'Só Ida','finalizado':'NÃO'})
                    else:
                        f_ini = "Semifinal" if len(times)<=4 else "Quartas"
                        for i in range(0, len(times), 2):
                            t1, t2 = times[i], (times[i+1] if i+1 < len(times) else "BYE")
                            jogos.append({'torneio_id':tid,'formato':'COPA','fase':f_ini,'a':t1,'b':t2,'modo_copa':modo_fixo,'finalizado':'NÃO'})
                    salvar_dados(pd.concat([df_db[~((df_db['torneio_id'] == tid) & (df_db['a'].isnull()))], pd.DataFrame(jogos)], ignore_index=True), ABA_JOGOS); st.rerun()
        else:
            if st.button("🏆 ENCERRAR E GERAR PÓDIO"):
                st.balloons()
                h_br = (datetime.utcnow() - timedelta(hours=3)).strftime("%d/%m/%Y %H:%M")
                c, v, t = "---", "---", "---"
                if fmt == "COPA":
                    fin, t3 = df_t[df_t['fase'] == 'Final'], df_t[df_t['fase'] == '3º Lugar']
                    if not fin.empty: c, v = obter_vencedor_perdedor(fin.iloc[0])
                    if not t3.empty: t, _ = obter_vencedor_perdedor(t3.iloc[0])
                else:
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
                    if len(res_l) >= 1: c = res_l[0]; v = res_l[1] if len(res_l)>1 else "---"; t = res_l[2] if len(res_l)>2 else "---"
                
                # Exibição do Pódio Visual
                st.markdown("## 🥇 RESULTADO FINAL")
                p1, p2, p3 = st.columns(3)
                p1.success(f"🥇 CAMPEÃO: **{c}**")
                p2.warning(f"🥈 VICE: **{v}**")
                p3.info(f"🥉 3º LUGAR: **{t}**")
                
                salvar_dados(pd.concat([df_hist, pd.DataFrame([{'torneio_id':tid,'formato':fmt,'campeao':c,'vice':v,'terceiro':t,'data_fim':h_br}])], ignore_index=True), ABA_HISTORICO)
                st.toast("Torneio Finalizado com Sucesso!", icon="🏆")

            if st.button("🚨 EXCLUIR TORNEIO"):
                salvar_dados(df_db[df_db['torneio_id'] != tid], ABA_JOGOS); st.session_state.torneio_ativo = None; st.rerun()
