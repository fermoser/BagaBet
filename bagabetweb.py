import streamlit as st
import pandas as pd
from itertools import combinations
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="GESTOR PRO", layout="wide", page_icon="⚽")
conn = st.connection("gsheets", type=GSheetsConnection)

# --- DEFINIÇÃO DAS COLUNAS (SEM APOSTAS, COM PENALTIS) ---
COLUNAS = [
    'torneio_id', 'formato', 'fase', 'a', 'b', 'finalizado',
    'gols_a', 'gols_b',       # Placar Liga
    'ida_a', 'ida_b',         # Placar Ida Copa
    'volta_a', 'volta_b',     # Placar Volta Copa
    'pen_a', 'pen_b'          # Penaltis (Desempate Copa)
]

# --- FUNÇÕES DE SUPORTE ---
def safe_int(val):
    try:
        if pd.isna(val) or val == "" or str(val).lower() == "nan": return 0
        return int(float(val))
    except: return 0

def is_done(val):
    return str(val).upper().strip() in ["1", "TRUE", "VERDADEIRO", "SIM"]

def carregar_db():
    st.cache_data.clear()
    try:
        df = conn.read(ttl=0)
        if df is None or df.empty: return pd.DataFrame(columns=COLUNAS)
        # Garante colunas
        for c in COLUNAS:
            if c not in df.columns: df[c] = None
        # Remove colunas lixo
        return df.loc[:, ~df.columns.str.contains('^Unnamed')]
    except: return pd.DataFrame(columns=COLUNAS)

def salvar_db(df):
    try:
        df_save = df[COLUNAS].copy()
        conn.update(data=df_save)
        st.cache_data.clear()
        st.toast("✅ Dados Salvos!")
    except Exception as e: st.error(f"Erro ao salvar: {e}")

# --- INÍCIO ---
df_db = carregar_db()

# --- SELEÇÃO DE TORNEIO ---
if 'torneio_ativo' not in st.session_state:
    st.title("⚽ GESTOR ESPORTIVO PRO")
    
    # Listar Torneios
    existentes = df_db.dropna(subset=['torneio_id'])
    if not existentes.empty:
        st.subheader("📂 Abrir Campeonato")
        ts = existentes[['torneio_id', 'formato']].drop_duplicates()
        cols = st.columns(3)
        for i, row in enumerate(ts.values):
            if cols[i%3].button(f"{row[0]} ({row[1]})", key=f"btn_{i}", use_container_width=True):
                st.session_state.torneio_ativo = row[0]
                st.session_state.formato = str(row[1]).upper()
                st.rerun()
    
    st.divider()
    st.subheader("🆕 Criar Novo")
    with st.form("novo_t"):
        c1, c2 = st.columns(2)
        nn = c1.text_input("Nome")
        nt = c2.selectbox("Tipo", ["LIGA", "COPA"])
        if st.form_submit_button("CRIAR"):
            if nn:
                st.session_state.torneio_ativo = nn.strip()
                st.session_state.formato = nt
                st.rerun()

else:
    # --- DENTRO DO TORNEIO ---
    tid = st.session_state.torneio_ativo
    fmt = st.session_state.formato
    df_t = df_db[df_db['torneio_id'].astype(str) == str(tid)].copy()

    with st.sidebar:
        st.header(f"🏆 {tid}")
        st.caption(f"Modo: {fmt}")
        
        ops = ["🏟️ Jogos", "⚙️ Admin"]
        if fmt == "LIGA": ops.insert(1, "📊 Classificação")
        
        menu = st.radio("Navegação", ops)
        
        st.divider()
        senha = st.text_input("Senha Admin", type="password")
        is_admin = (senha == "1234")
        
        if st.button("🏠 Sair"):
            for k in list(st.session_state.keys()): del st.session_state[k]
            st.rerun()

    # =================================================================
    # ⚙️ ADMIN (GERAÇÃO E PROGRESSÃO)
    # =================================================================
    if menu == "⚙️ Admin":
        st.header("Painel Administrativo")
        if not is_admin:
            st.warning("Senha incorreta.")
        else:
            # 1. GERAR JOGOS INICIAIS
            with st.expander("🚀 Iniciar Torneio (Gerar 1ª Fase)", expanded=True):
                times_txt = st.text_area("Lista de Times (um por linha)")
                fase_ini = st.text_input("Nome da Fase Inicial", "Fase de Grupos" if fmt=="LIGA" else "Quartas de Final")
                
                if st.button("Gerar Jogos Iniciais"):
                    times = [t.strip() for t in times_txt.split('\n') if t.strip()]
                    novos = []
                    if len(times) < 2:
                        st.error("Mínimo 2 times.")
                    else:
                        if fmt == "LIGA":
                            for a, b in combinations(times, 2):
                                novos.append({'torneio_id': tid, 'formato': 'LIGA', 'fase': fase_ini, 'a': a, 'b': b, 'finalizado': '0'})
                        else:
                            # Copa (Pares)
                            for i in range(0, len(times), 2):
                                if i+1 < len(times):
                                    novos.append({'torneio_id': tid, 'formato': 'COPA', 'fase': fase_ini, 'a': times[i], 'b': times[i+1], 'finalizado': '0'})
                        
                        df_final = pd.concat([df_db, pd.DataFrame(novos)], ignore_index=True)
                        salvar_db(df_final); st.rerun()

            # 2. PROGRESSÃO DE COPA (AVANÇAR FASE)
            if fmt == "COPA" and not df_t.empty:
                st.divider()
                st.subheader("⏩ Progressão de Fase (Mata-Mata)")
                
                fases_disponiveis = df_t['fase'].unique()
                fase_origem = st.selectbox("Avançar vencedores da fase:", fases_disponiveis)
                nome_prox = st.text_input("Nome da Próxima Fase (Ex: Semifinal)", "Semifinal")
                
                if st.button(f"Gerar {nome_prox} com os Vencedores"):
                    jogos_fase = df_t[df_t['fase'] == fase_origem]
                    vencedores = []
                    
                    # Calcula vencedores
                    todos_finalizados = True
                    for _, r in jogos_fase.iterrows():
                        if not is_done(r['finalizado']):
                            todos_finalizados = False
                            break
                        
                        # Lógica Quem Passou
                        s_a = safe_int(r['ida_a']) + safe_int(r['volta_a'])
                        s_b = safe_int(r['ida_b']) + safe_int(r['volta_b'])
                        
                        if s_a > s_b: vencedores.append(r['a'])
                        elif s_b > s_a: vencedores.append(r['b'])
                        else:
                            # Penaltis
                            pa, pb = safe_int(r['pen_a']), safe_int(r['pen_b'])
                            vencedores.append(r['a'] if pa > pb else r['b'])
                    
                    if not todos_finalizados:
                        st.error("⚠️ Finalize TODOS os jogos desta fase antes de avançar!")
                    elif len(vencedores) < 2:
                        st.error("Não há vencedores suficientes para criar novos jogos.")
                    else:
                        # Cria confrontos da proxima fase (1º vencedor x 2º vencedor...)
                        novos_prox = []
                        for i in range(0, len(vencedores), 2):
                            if i+1 < len(vencedores):
                                novos_prox.append({
                                    'torneio_id': tid, 'formato': 'COPA', 'fase': nome_prox,
                                    'a': vencedores[i], 'b': vencedores[i+1], 'finalizado': '0'
                                })
                        
                        df_final = pd.concat([df_db, pd.DataFrame(novos_prox)], ignore_index=True)
                        salvar_db(df_final); st.rerun()

            st.divider()
            if st.button("🚨 APAGAR ESTE TORNEIO"):
                df_limpo = df_db[df_db['torneio_id'].astype(str) != str(tid)]
                salvar_db(df_limpo)
                for k in list(st.session_state.keys()): del st.session_state[k]
                st.rerun()

    # =================================================================
    # 🏟️ JOGOS (COM RESULTADOS E PÊNALTIS)
    # =================================================================
    elif menu == "🏟️ Jogos":
        if df_t.empty: st.info("Nenhum jogo. Vá em Admin para começar.")
        else:
            # Agrupa por fases para ficar bonito
            for fase in df_t['fase'].unique():
                st.markdown(f"### 📍 {fase}")
                subset = df_t[df_t['fase'] == fase]
                
                for idx, row in subset.iterrows():
                    with st.container(border=True):
                        c1, c2, c3 = st.columns([2,1,2])
                        
                        # Exibição do Placar
                        if fmt == "LIGA":
                            placar = f"{safe_int(row['gols_a'])} x {safe_int(row['gols_b'])}"
                        else:
                            ia, ib = safe_int(row['ida_a']), safe_int(row['ida_b'])
                            va, vb = safe_int(row['volta_a']), safe_int(row['volta_b'])
                            ag_a, ag_b = ia+va, ib+vb
                            placar = f"({ia}) {va} x {vb} ({ib})"
                            
                            # Mostra pênaltis se houve empate agregado
                            if ag_a == ag_b and is_done(row['finalizado']):
                                placar += f" [Pên: {safe_int(row['pen_a'])}x{safe_int(row['pen_b'])}]"

                        c1.markdown(f"<h4 style='text-align:right'>{row['a']}</h4>", unsafe_allow_html=True)
                        c2.markdown(f"<div style='text-align:center; background:#eee; padding:5px; border-radius:5px;'><b>{placar}</b></div>", unsafe_allow_html=True)
                        c3.markdown(f"<h4 style='text-align:left'>{row['b']}</h4>", unsafe_allow_html=True)

                        # Edição (Admin)
                        if is_admin:
                            with st.expander("📝 Editar Resultado"):
                                with st.form(key=f"ed_{idx}"):
                                    if fmt == "LIGA":
                                        na = st.number_input("Gols A", 0, 99, safe_int(row['gols_a']))
                                        nb = st.number_input("Gols B", 0, 99, safe_int(row['gols_b']))
                                        if st.form_submit_button("Salvar"):
                                            df_db.loc[idx, ['gols_a','gols_b','finalizado']] = [na, nb, "1"]
                                            salvar_db(df_db); st.rerun()
                                    else:
                                        # Copa (Ida/Volta/Pênaltis)
                                        ci, cv = st.columns(2)
                                        i1 = ci.number_input("Ida A", 0, value=safe_int(row['ida_a']))
                                        i2 = ci.number_input("Ida B", 0, value=safe_int(row['ida_b']))
                                        v1 = cv.number_input("Volta A", 0, value=safe_int(row['volta_a']))
                                        v2 = cv.number_input("Volta B", 0, value=safe_int(row['volta_b']))
                                        
                                        # Checa se precisa de pênaltis (Empate Agregado)
                                        soma_a = i1 + v1
                                        soma_b = i2 + v2
                                        pa, pb = 0, 0
                                        
                                        if soma_a == soma_b:
                                            st.warning("Empate no agregado! Informe os Pênaltis:")
                                            cp = st.columns(2)
                                            pa = cp[0].number_input("Penaltis A", 0, value=safe_int(row['pen_a']))
                                            pb = cp[1].number_input("Penaltis B", 0, value=safe_int(row['pen_b']))
                                        
                                        if st.form_submit_button("Salvar Resultado"):
                                            df_db.loc[idx, ['ida_a','ida_b','volta_a','volta_b','pen_a','pen_b','finalizado']] = [i1, i2, v1, v2, pa, pb, "1"]
                                            salvar_db(df_db); st.rerun()

    # =================================================================
    # 📊 CLASSIFICAÇÃO (SÓ LIGA)
    # =================================================================
    elif menu == "📊 Classificação":
        st.header("Tabela de Pontos")
        
        times = pd.concat([df_t['a'], df_t['b']]).unique()
        stats = {t: {'P':0, 'J':0, 'V':0, 'E':0, 'D':0, 'GP':0, 'GC':0, 'SG':0} for t in times if pd.notna(t)}
        
        for _, r in df_t.iterrows():
            if is_done(r['finalizado']):
                t1, t2 = r['a'], r['b']
                g1, g2 = safe_int(r['gols_a']), safe_int(r['gols_b'])
                
                stats[t1]['J']+=1; stats[t2]['J']+=1
                stats[t1]['GP']+=g1; stats[t1]['GC']+=g2
                stats[t2]['GP']+=g2; stats[t2]['GC']+=g1
                stats[t1]['SG'] = stats[t1]['GP'] - stats[t1]['GC']
                stats[t2]['SG'] = stats[t2]['GP'] - stats[t2]['GC']
                
                if g1 > g2:
                    stats[t1]['P']+=3; stats[t1]['V']+=1; stats[t2]['D']+=1
                elif g2 > g1:
                    stats[t2]['P']+=3; stats[t2]['V']+=1; stats[t1]['D']+=1
                else:
                    stats[t1]['P']+=1; stats[t2]['P']+=1
                    stats[t1]['E']+=1; stats[t2]['E']+=1
        
        df_class = pd.DataFrame.from_dict(stats, orient='index')
        if not df_class.empty:
            df_class = df_class.sort_values(by=['P','V','SG'], ascending=False).reset_index().rename(columns={'index':'Time'})
            st.dataframe(df_class, hide_index=True, use_container_width=True)
        else:
            st.info("Aguardando jogos.")
