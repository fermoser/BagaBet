import streamlit as st
import pandas as pd
import random
from streamlit_gsheets import GSheetsConnection
from datetime import datetime, timedelta

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="BAGA GESTOR PRO", layout="wide")

# --- ESTILO CSS ---
st.markdown("""
    <style>
    input[type=number] { color: #F4D03F !important; font-weight: bold !important; font-size: 20px !important; }
    .stMarkdown div[style*="background:#eee"] { background-color: #333 !important; color: #F4D03F !important; font-weight: bold; border-radius: 5px; }
    [data-testid="stForm"] .stColumn { display: flex; align-items: center; justify-content: center; }
    </style>
    """, unsafe_allow_html=True)

conn = st.connection("gsheets", type=GSheetsConnection)
ABA_JOGOS = "Página1" 
ABA_SUICO = "Suico"
ABA_HISTORICO = "Historico"

COLUNAS_PADRAO = ['torneio_id', 'formato', 'fase', 'a', 'b', 'finalizado', 'gols_a', 'gols_b', 'ida_a', 'ida_b', 'volta_a', 'volta_b', 'pen_a', 'pen_b', 'modo_copa']
COLUNAS_SUICO = ['torneio_id', 'formato', 'fase', 'rodada', 'a', 'b', 'gols_a', 'gols_b', 'finalizado', 'ida_a', 'ida_b', 'volta_a', 'volta_b', 'pen_a', 'pen_b', 'modo_mata_mata']

ORDEM_FASES = {"Oitavas": 1, "Quartas": 2, "Semifinal": 3, "3º Lugar": 4, "Final": 5, "Suico": 0}

# --- FUNÇÕES DE DADOS ---
def carregar_dados(aba):
    try:
        df = conn.read(worksheet=aba, ttl="0s")
        cols_esperadas = COLUNAS_SUICO if aba == ABA_SUICO else (COLUNAS_PADRAO if aba == ABA_JOGOS else ['torneio_id','formato','campeao','vice','terceiro','data_fim'])
        if df is None or df.empty: return pd.DataFrame(columns=cols_esperadas)
        df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
        for c in cols_esperadas:
            if c not in df.columns: df[c] = None
        if aba != ABA_HISTORICO:
            for col in ['gols_a', 'gols_b', 'ida_a', 'ida_b', 'volta_a', 'volta_b', 'pen_a', 'pen_b']:
                if col in df.columns: df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
        return df
    except: return pd.DataFrame(columns=COLUNAS_PADRAO)

def salvar_dados(df, aba):
    if 'torneio_id' in df.columns: df = df.dropna(subset=['torneio_id'])
    conn.update(worksheet=aba, data=df)
    st.cache_data.clear()

def is_done(val): return str(val).upper().strip() in ["1", "SIM", "TRUE"]

def obter_vencedor_perdedor(r, modo="PADRAO"):
    if not is_done(r['finalizado']): return None, None
    if modo == "SUICO_FASE": sa, sb = int(r['gols_a']), int(r['gols_b'])
    elif r.get('modo_mata_mata') == "Ida e Volta" or (modo == "PADRAO" and r.get('modo_copa') == "Ida e Volta"):
        sa, sb = int(r['ida_a']) + int(r['volta_a']), int(r['ida_b']) + int(r['volta_b'])
    else: sa, sb = int(r['gols_a']), int(r['gols_b'])
    if sa > sb: return r['a'], r['b']
    elif sb > sa: return r['b'], r['a']
    else:
        pa, pb = int(r.get('pen_a', 0)), int(r.get('pen_b', 0))
        if pa > pb: return r['a'], r['b']
        if pb > pa: return r['b'], r['a']
        return None, None

# --- MOTOR SUÍÇO ---
def calcular_ranking_suico(df_t):
    times = set(df_t['a'].unique()) | set(df_t['b'].unique())
    if "BYE" in times: times.remove("BYE")
    stats = {t: {'V':0, 'D':0, 'Jogos': [], 'Buchholz': 0} for t in times if pd.notna(t)}
    for _, r in df_t[df_t['fase'] == 'Suico'].iterrows():
        if is_done(r['finalizado']):
            v, p = obter_vencedor_perdedor(r, "SUICO_FASE")
            if v and v in stats: stats[v]['V'] += 1; stats[v]['Jogos'].append(p)
            if p and p in stats: stats[p]['D'] += 1; stats[p]['Jogos'].append(v)
    for t in stats:
        stats[t]['Buchholz'] = sum([stats[op]['V'] for op in stats[t]['Jogos'] if op in stats])
        if stats[t]['V'] >= 3: stats[t]['Status'] = "Classificado"
        elif stats[t]['D'] >= 3: stats[t]['Status'] = "Eliminado"
        else: stats[t]['Status'] = "Ativo"
    return stats

def gerar_rodada_suica(df_t, tid):
    stats = calcular_ranking_suico(df_t)
    ativos = [t for t, s in stats.items() if s['Status'] == "Ativo"]
    if len(ativos) < 2: return None, "Fase Suíça Concluída!"
    pool = sorted(ativos, key=lambda x: (stats[x]['V'], stats[x]['Buchholz']), reverse=True)
    pareamentos = []
    while len(pool) > 1:
        t1 = pool.pop(0)
        op_idx = next((i for i, cand in enumerate(pool) if cand not in stats[t1]['Jogos']), 0)
        pareamentos.append((t1, pool.pop(op_idx)))
    bye = pool[0] if pool else None
    novos = []
    rd = int(df_t[df_t['fase']=='Suico']['rodada'].max() if not df_t[df_t['fase']=='Suico'].empty else 0) + 1
    for p in pareamentos:
        novos.append({'torneio_id':tid,'formato':'SUICO','fase':'Suico','rodada':rd,'a':p[0],'b':p[1],'finalizado':'NÃO'})
    if bye:
        novos.append({'torneio_id':tid,'formato':'SUICO','fase':'Suico','rodada':rd,'a':bye,'b':'BYE','gols_a':1,'gols_b':0,'finalizado':'SIM'})
    return novos, "Rodada Gerada!"

# --- INTERFACE ---
if 'torneio_ativo' not in st.session_state: st.session_state.torneio_ativo = None

df_padrao = carregar_dados(ABA_JOGOS)
df_suico = carregar_dados(ABA_SUICO)
df_hist = carregar_dados(ABA_HISTORICO)

if st.session_state.torneio_ativo is None:
    st.title("⚽ BAGA GESTOR PRO")
    with st.expander("📜 HALL DA FAMA"): st.dataframe(df_hist, use_container_width=True)
    
    # Listar Torneios
    all_t = list(set((df_padrao['torneio_id'].unique().tolist() if not df_padrao.empty else []) + (df_suico['torneio_id'].unique().tolist() if not df_suico.empty else [])))
    if all_t:
        st.subheader("📂 Torneios")
        c = st.columns(3)
        for i, t in enumerate(all_t):
            if c[i%3].button(f"🏆 {t}", use_container_width=True):
                st.session_state.torneio_ativo = t
                st.session_state.tipo_ativo = "SUICO" if t in (df_suico['torneio_id'].unique().tolist() if not df_suico.empty else []) else "PADRAO"
                st.rerun()

    st.divider()
    c1, c2, c3 = st.columns(3)
    with c1.container(border=True):
        n = st.text_input("Nome Liga")
        if st.button("Criar Liga"):
            salvar_dados(pd.concat([df_padrao, pd.DataFrame([{'torneio_id':n,'formato':'LIGA','fase':'Inscricao'}])]), ABA_JOGOS)
            st.rerun()
    with c2.container(border=True):
        n2 = st.text_input("Nome Copa")
        m = st.selectbox("Modo", ["Só Ida", "Ida e Volta"])
        if st.button("Criar Copa"):
            salvar_dados(pd.concat([df_padrao, pd.DataFrame([{'torneio_id':n2,'formato':'COPA','modo_copa':m,'fase':'Inscricao'}])]), ABA_JOGOS)
            st.rerun()
    with c3.container(border=True):
        n3 = st.text_input("Nome Suíço")
        if st.button("Criar Suíço"):
            salvar_dados(pd.concat([df_suico, pd.DataFrame([{'torneio_id':n3,'formato':'SUICO','fase':'Inscricao'}])]), ABA_SUICO)
            st.rerun()

else:
    tid = st.session_state.torneio_ativo
    tipo = st.session_state.tipo_ativo
    df_t = (df_suico if tipo=="SUICO" else df_padrao)[(df_suico if tipo=="SUICO" else df_padrao)['torneio_id']==tid].copy()
    
    with st.sidebar:
        st.header(f"🏆 {tid}")
        menu = st.radio("Menu", ["🏟️ Jogos", "📊 Classificação", "⚙️ Admin"])
        if st.button("🏠 Sair"): st.session_state.torneio_ativo = None; st.rerun()

    if tipo == "SUICO":
        if menu == "🏟️ Jogos":
            for f in sorted(df_t['fase'].unique(), key=lambda x: ORDEM_FASES.get(x, 99)):
                if f == "Inscricao": continue
                st.subheader(f"📍 {f}")
                for idx, r in df_t[df_t['fase']==f].iterrows():
                    with st.container(border=True):
                        col1, col2, col3 = st.columns([2,1,2])
                        col1.write(r['a'])
                        col3.write(r['b'])
                        if f == "Suico":
                            with col2:
                                if st.button(f"{r['gols_a']} x {r['gols_b']}", key=f"btn_{idx}"):
                                    st.session_state[f"ed_{idx}"] = True
                            if st.session_state.get(f"ed_{idx}"):
                                with st.form(f"f_{idx}"):
                                    ga, gb = st.columns(2)[0].number_input("A",0,99,int(r['gols_a'])), st.columns(2)[1].number_input("B",0,99,int(r['gols_b']))
                                    if st.form_submit_button("Salvar"):
                                        df_suico.loc[idx, ['gols_a','gols_b','finalizado']] = [ga, gb, "SIM"]
                                        salvar_dados(df_suico, ABA_SUICO); st.rerun()
                        else:
                            col2.write(f"({r['ida_a']}) {r['volta_a']} x {r['volta_b']} ({r['ida_b']})")
                            with st.expander("Editar"):
                                with st.form(f"fm_{idx}"):
                                    ia, ib = st.columns(2)[0].number_input("Ida A",0,99), st.columns(2)[1].number_input("Ida B",0,99)
                                    va, vb = st.columns(2)[0].number_input("Volta A",0,99), st.columns(2)[1].number_input("Volta B",0,99)
                                    if st.form_submit_button("Ok"):
                                        df_suico.loc[idx,['ida_a','ida_b','volta_a','volta_b','finalizado']]=[ia,ib,va,vb,"SIM"]
                                        salvar_dados(df_suico, ABA_SUICO); st.rerun()

        elif menu == "📊 Classificação":
            stats = calcular_ranking_suico(df_t)
            df_rank = pd.DataFrame(stats).T.sort_values(['V','Buchholz'], ascending=False)
            st.table(df_rank)

        elif menu == "⚙️ Admin":
            st.header("🔐 Painel de Controle (Admin)")
            senha = st.text_input("Senha de Acesso", type="password")
            
            if senha == "123": # Use a sua senha padrão aqui
                st.success("Acesso Liberado!")
                
                # Botão de Excluir sempre visível para o Admin
                if st.button("🚨 EXCLUIR ESTE TORNEIO"):
                    df_suico = df_suico[df_suico['torneio_id'] != tid]
                    salvar_dados(df_suico, ABA_SUICO)
                    st.session_state.torneio_ativo = None
                    st.rerun()
                
                st.divider()

                # LÓGICA DE INSCRIÇÃO (SÓ APARECE SE NÃO HOUVER JOGOS)
                jogos_fase_suica = df_t[df_t['fase'] == 'Suico']
                if jogos_fase_suica.empty:
                    st.subheader("📝 Iniciar Novo Torneio Suíço")
                    t_list = st.text_area("Insira a lista de times (um por linha)", height=200, help="Mínimo 6, Máximo 16 times")
                    
                    if st.button("🚀 GERAR 1ª RODADA"):
                        times = [x.strip() for x in t_list.split('\n') if x.strip()]
                        if 6 <= len(times) <= 16:
                            random.shuffle(times)
                            jogos = []
                            for i in range(0, len(times), 2):
                                t1 = times[i]
                                t2 = times[i+1] if i+1 < len(times) else "BYE"
                                status_bye = "SIM" if t2 == "BYE" else "NÃO"
                                g_a = 1 if t2 == "BYE" else 0
                                
                                jogos.append({
                                    'torneio_id': tid, 'formato': 'SUICO', 'fase': 'Suico', 
                                    'rodada': 1, 'a': t1, 'b': t2, 
                                    'gols_a': g_a, 'gols_b': 0, 'finalizado': status_bye
                                })
                            
                            novo_df = pd.concat([df_suico, pd.DataFrame(jogos)], ignore_index=True)
                            salvar_dados(novo_df, ABA_SUICO)
                            st.success("Torneio iniciado com sucesso!")
                            st.rerun()
                        else:
                            st.error("Erro: O formato suíço requer entre 6 e 16 participantes.")
                
                # LÓGICA DE PRÓXIMAS RODADAS
                else:
                    st.subheader("🎮 Gerenciar Rodadas")
                    ult_rd = int(jogos_fase_suica['rodada'].max())
                    pendentes = jogos_fase_suica[(jogos_fase_suica['rodada'] == ult_rd) & (jogos_fase_suica['finalizado'] != "SIM")]
                    
                    if pendentes.empty:
                        st.info(f"✅ Rodada {ult_rd} finalizada.")
                        if st.button(f"✨ GERAR RODADA {ult_rd + 1}"):
                            novos_jogos, msg = gerar_rodada_suica(df_t, tid)
                            if novos_jogos:
                                novo_df = pd.concat([df_suico, pd.DataFrame(novos_jogos)], ignore_index=True)
                                salvar_dados(novo_df, ABA_SUICO)
                                st.rerun()
                            else:
                                st.warning(msg)
                    else:
                        st.warning(f"Aguardando resultados de {len(pendentes)} jogo(s) da Rodada {ult_rd}.")

            elif senha != "":
                st.error("Senha incorreta!")
            else:
                if df_t[df_t['finalizado']!='SIM'].empty:
                    if st.button("Próxima Rodada / Mata-Mata"):
                        novos, msg = gerar_rodada_suica(df_t, tid)
                        if novos: salvar_dados(pd.concat([df_suico, pd.DataFrame(novos)]), ABA_SUICO); st.rerun()
                        else:
                            st.write("Suíço encerrado. Gerando Mata-Mata...")
                            # Lógica de Quartas/Semis simplificada
                            stats = calcular_ranking_suico(df_t)
                            classif = [t for t,s in stats.items() if s['Status']=="Classificado"]
                            # Gerar jogos de Ida e Volta aqui...
                            st.rerun()

