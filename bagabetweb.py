import streamlit as st
import pandas as pd
from itertools import combinations
from streamlit_gsheets import GSheetsConnection
from datetime import datetime, timedelta

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="BAGA GESTOR PRO", layout="wide")

# --- ESTILO CSS (AMARELO SUAVE E PLACARES) ---
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
    if sb > sa: return r['b'], r['a']
    pa, pb = int(r.get('pen_a', 0)), int(r.get('pen_b', 0))
    return (r['a'], r['b']) if pa > pb else (r['b'], r['a'])

# --- INICIALIZAÇÃO ---
df_db = carregar_dados(ABA_JOGOS)
df_hist = carregar_dados(ABA_HISTORICO)

if 'torneio_ativo' not in st.session_state:
    st.session_state.torneio_ativo = None

# --- TELA INICIAL (HALL DA FAMA + CARREGAR + NOVO) ---
if st.session_state.torneio_ativo is None:
    st.title("⚽ BAGA GESTOR PRO")

    # 1. HALL DA FAMA
    with st.expander("📜 HALL DA FAMA (Campeões Anteriores)", expanded=True):
        if not df_hist.empty:
            st.dataframe(df_hist.sort_index(ascending=False), use_container_width=True)
        else:
            st.info("O histórico está vazio.")

    # 2. CARREGAR TORNEIO
    torneios = df_db.dropna(subset=['torneio_id'])['torneio_id'].unique() if not df_db.empty else []
    if len(torneios) > 0:
        with st.expander("📂 CARREGAR TORNEIO EM ABERTO", expanded=False):
            cols = st.columns(3)
            for i, t_nome in enumerate(torneios):
                row_t = df_db[df_db['torneio_id'] == t_nome].iloc[0]
                if cols[i%3].button(f"🏆 {t_nome} ({row_t['formato']})", key=f"btn_{t_nome}"):
                    st.session_state.torneio_ativo = t_nome
                    st.session_state.formato = row_t['formato']
                    st.rerun()

    st.divider()

    # 3. NOVO TORNEIO
    st.subheader("🆕 Criar Novo Torneio")
    with st.form("criar_novo"):
        c1, c2, c3 = st.columns(3)
        n = c1.text_input("Nome do Torneio")
        t = c2.selectbox("Tipo", ["COPA", "LIGA"])
        m = c3.selectbox("Modo", ["Só Ida", "Ida e Volta"]) if t == "COPA" else "Só Ida"
        if st.form_submit_button("CRIAR AGORA"):
            if n: 
                st.session_state.torneio_ativo, st.session_state.formato, st.session_state.modo = n, t, m
                st.rerun()

else:
    tid, fmt = st.session_state.torneio_ativo, st.session_state.formato
    df_t = df_db[df_db['torneio_id'] == tid].copy()

    with st.sidebar:
        st.header(f"🏆 {tid}")
        menu = st.radio("Menu", ["🏟️ Jogos", "📊 Consulta", "⚙️ Admin"])
        is_admin = (st.text_input("Senha Admin", type="password") == "1234")
        if st.button("🏠 Sair do Torneio"):
            st.session_state.torneio_ativo = None
            st.rerun()

    # --- ABA JOGOS ---
    if menu == "🏟️ Jogos":
        if df_t.empty:
            st.warning("Torneio sem jogos. Vá no menu 'Admin' para gerar a tabela.")
        else:
            for f in df_t['fase'].unique():
                st.subheader(f"📍 {f}")
                for idx, r in df_t[df_t['fase'] == f].iterrows():
                    with st.container(border=True):
                        c1, c2, c3 = st.columns([2,1,2])
                        p_txt = f"{r['gols_a']} x {r['gols_b']}" if r['modo_copa']=="Só Ida" or fmt=="LIGA" else f"({r['ida_a']}) {r['volta_a']} x {r['volta_b']} ({r['ida_b']})"
                        if is_done(r['finalizado']) and (r['pen_a']+r['pen_b']>0): p_txt += f" (P: {r['pen_a']}x{r['pen_b']})"
                        
                        c1.markdown(f"<p style='text-align:right'><b>{r['a']}</b></p>", unsafe_allow_html=True)
                        c2.markdown(f"<div style='text-align:center; background:#eee; padding:5px; color:black;'>{p_txt}</div>", unsafe_allow_html=True)
                        c3.markdown(f"<p style='text-align:left'><b>{r['b']}</b></p>", unsafe_allow_html=True)
                        
                        if is_admin:
                            with st.expander("✎ Editar Placar"):
                                with st.form(f"ed_{idx}"):
                                    ca, cb = st.columns(2)
                                    if fmt=="LIGA" or r['modo_copa']=="Só Ida":
                                        ga, gb = ca.number_input("Gols A",0,99,int(r['gols_a'])), cb.number_input("Gols B",0,99,int(r['gols_b']))
                                        res = [ga, gb, ga, gb, 0, 0]
                                    else:
                                        ia, ib = ca.number_input("Ida A",0,99,int(r['ida_a'])), cb.number_input("Ida B",0,99,int(r['ida_b']))
                                        va, vb = ca.number_input("Volta A",0,99,int(r['volta_a'])), cb.number_input("Volta B",0,99,int(r['volta_b']))
                                        res = [ia+va, ib+vb, ia, ib, va, vb]
                                    pa, pb = ca.number_input("Pen A",0,99,int(r['pen_a'])), cb.number_input("Pen B",0,99,int(r['pen_b']))
                                    if st.form_submit_button("Salvar Resultado"):
                                        df_db.loc[idx, ['gols_a','gols_b','ida_a','ida_b','volta_a','volta_b','pen_a','pen_b','finalizado']] = res + [pa, pb, "SIM"]
                                        salvar_dados(df_db, ABA_JOGOS)

    # --- ABA CONSULTA ---
    elif menu == "📊 Consulta":
        if fmt == "LIGA":
            st.subheader("📈 Classificação")
            times = pd.concat([df_t['a'], df_t['b']]).unique()
            stats = {t: {'P':0,'J':0,'V':0,'E':0,'D':0,'GP':0,'GC':0,'SG':0} for t in times if pd.notna(t)}
            for _, r in df_t[df_t['finalizado'] == 'SIM'].iterrows():
                t1, t2, g1, g2 = r['a'], r['b'], r['gols_a'], r['gols_b']
                stats[t1]['J']+=1; stats[t2]['J']+=1; stats[t1]['GP']+=g1; stats[t1]['GC']+=g2; stats[t2]['GP']+=g2; stats[t2]['GC']+=g1
                if g1 > g2: stats[t1]['P']+=3; stats[t1]['V']+=1; stats[t2]['D']+=1
                elif g2 > g1: stats[t2]['P']+=3; stats[t2]['V']+=1; stats[t1]['D']+=1
                else: stats[t1]['P']+=1; stats[t2]['P']+=1; stats[t1]['E']+=1; stats[t2]['E']+=1
                stats[t1]['SG'] = stats[t1]['GP'] - stats[t1]['GC']; stats[t2]['SG'] = stats[t2]['GP'] - stats[t2]['GC']
            st.table(pd.DataFrame.from_dict(stats, orient='index').sort_values(by=['P','V','SG','GP'], ascending=False))
        else:
            st.subheader("🗺️ Chaveamento")
            f_p = ["Oitavas", "Quartas", "Semifinal", "Final", "3º Lugar"]
            cols = st.columns(len(f_p))
            for i, fase in enumerate(f_p):
                with cols[i]:
                    st.markdown(f"**{fase.upper()}**")
                    for _, r in df_t[df_t['fase'] == fase].iterrows():
                        v, _ = obter_vencedor_perdedor(r)
                        b_c = "#F4D03F" if is_done(r['finalizado']) else "#ccc"
                        st.markdown(f'<div style="border:2px solid {b_c}; padding:8px; border-radius:10px; background:white; color:black; margin-bottom:10px; text-align:center; font-size:12px;"><b>{r["a"]} x {r["b"]}</b><br>Vencedor: {v if v else "---"}</div>', unsafe_allow_html=True)

    # --- ABA ADMIN ---
    elif menu == "⚙️ Admin" and is_admin:
        if df_t.empty:
            st.subheader("🛠️ Gerar Jogos")
            txt = st.text_area("Times (um por linha)")
            if st.button("GERAR TABELA"):
                times = [x.strip() for x in txt.split('\n') if x.strip()]
                if len(times)>=2:
                    jogos = []
                    if fmt=="LIGA":
                        for a,b in combinations(times,2):
                            jogos.append({'torneio_id':tid,'formato':fmt,'fase':'Pontos Corridos','a':a,'b':b,'modo_copa':'Só Ida','finalizado':'NÃO'})
                    else:
                        fase = "Semifinal" if len(times)<=4 else "Quartas"
                        for i in range(0, len(times), 2):
                            jogos.append({'torneio_id':tid,'formato':fmt,'fase':fase,'a':times[i],'b':times[i+1] if i+1<len(times) else "BYE",'modo_copa':st.session_state.get('modo','Só Ida'),'finalizado':'NÃO'})
                    salvar_dados(pd.concat([df_db, pd.DataFrame(jogos)], ignore_index=True), ABA_JOGOS)
        else:
            # BOTÃO DE AVANÇAR FASE
            if df_t[df_t['finalizado'] != "SIM"].empty:
                ultima = df_t['fase'].iloc[-1]
                if ultima != "Final" and ultima != "3º Lugar":
                    if st.button("🔥 GERAR PRÓXIMA FASE"):
                        venc, perd = [], []
                        for _, r in df_t[df_t['fase'] == ultima].iterrows():
                            v, p = obter_vencedor_perdedor(r)
                            venc.append(v); perd.append(p)
                        novos = []
                        if len(venc)>=2: novos.append({'torneio_id':tid,'formato':fmt,'fase':'Final','a':venc[0],'b':venc[1],'modo_copa':'Só Ida','finalizado':'NÃO'})
                        if len(perd)>=2: novos.append({'torneio_id':tid,'formato':fmt,'fase':'3º Lugar','a':perd[0],'b':perd[1],'modo_copa':'Só Ida','finalizado':'NÃO'})
                        salvar_dados(pd.concat([df_db, pd.DataFrame(novos)], ignore_index=True), ABA_JOGOS)
            
            st.divider()
            if st.button("🏆 FINALIZAR E SALVAR NO HISTÓRICO"):
                h_br = (datetime.utcnow() - timedelta(hours=3)).strftime("%d/%m/%Y %H:%M")
                # Busca campeão na final
                camp, vice, terc = "---", "---", "---"
                fin = df_t[df_t['fase'] == 'Final']
                t3 = df_t[df_t['fase'] == '3º Lugar']
                if not fin.empty: camp, vice = obter_vencedor_perdedor(fin.iloc[0])
                if not t3.empty: terc, _ = obter_vencedor_perdedor(t3.iloc[0])
                
                nova_h = pd.DataFrame([{'torneio_id':tid,'formato':fmt,'campeao':camp,'vice':vice,'terceiro':terc,'data_fim':h_br}])
                salvar_dados(pd.concat([df_hist, nova_h], ignore_index=True), ABA_HISTORICO)
            
            st.button("🚨 EXCLUIR TORNEIO ATIVO", on_click=lambda: salvar_dados(df_db[df_db['torneio_id'] != tid], ABA_JOGOS))
