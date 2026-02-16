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

# --- FUNÇÕES ---
def carregar_dados():
    # Removido st.cache_data.clear() daqui para evitar loops de carregamento
    try:
        df = conn.read(ttl=0)
        if df is None or df.empty: 
            return pd.DataFrame(columns=COLUNAS)
        
        # Garante que todas as colunas existem
        for c in COLUNAS:
            if c not in df.columns: df[c] = None
            
        # Limpa colunas fantasmas do Google Sheets
        df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
        
        # Converte números com segurança
        cols_n = ['gols_a', 'gols_b', 'ida_a', 'ida_b', 'volta_a', 'volta_b', 'pen_a', 'pen_b']
        for col in cols_n:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
            
        return df
    except Exception as e:
        st.error(f"Erro ao conectar com a planilha: {e}")
        return pd.DataFrame(columns=COLUNAS)

def salvar_dados(df):
    try:
        conn.update(data=df[COLUNAS].copy())
        st.cache_data.clear()
        st.success("Dados salvos com sucesso!")
        st.rerun()
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")

def is_done(val):
    return str(val).upper().strip() in ["1", "SIM", "TRUE"]

def obter_vencedor(r):
    if not is_done(r['finalizado']): return "---", ""
    if r['fase'] in ["Final", "3º Lugar"] or r['modo_copa'] == "Só Ida":
        sa, sb = r['gols_a'], r['gols_b']
    else:
        sa, sb = r['ida_a'] + r['volta_a'], r['ida_b'] + r['volta_b']
    if sa > sb: return r['a'], r['b']
    if sb > sa: return r['b'], r['a']
    # Critério de pênaltis caso empate no tempo real/agregado
    return (r['a'], r['b']) if int(r['pen_a']) > int(r['pen_b']) else (r['b'], r['a'])

# --- LOGICA DE INTERFACE ---
df_db = carregar_dados()

# Verifica se existem torneios salvos
torneios_salvos = []
if not df_db.empty and 'torneio_id' in df_db.columns:
    torneios_salvos = df_db.dropna(subset=['torneio_id'])['torneio_id'].unique().tolist()

if 'torneio_ativo' not in st.session_state:
    st.title("⚽ BAGA GESTOR")
    
    # SEÇÃO DE CARREGAMENTO
    if torneios_salvos:
        st.subheader("📂 Abrir Torneio Salvo")
        cols = st.columns(3)
        for i, t_nome in enumerate(torneios_salvos):
            # Busca o formato do torneio para exibir no botão
            fmt_t = df_db[df_db['torneio_id'] == t_nome]['formato'].iloc[0]
            if cols[i % 3].button(f"🏆 {t_nome} ({fmt_t})", key=f"load_{i}", use_container_width=True):
                st.session_state.torneio_ativo = t_nome
                st.session_state.formato = fmt_t
                st.rerun()
    else:
        st.info("Nenhum torneio encontrado na nuvem. Crie um novo abaixo.")

    st.divider()
    
    # SEÇÃO DE CRIAÇÃO
    st.subheader("🆕 Criar Novo Torneio")
    with st.form("novo_torneio"):
        c1, c2, c3 = st.columns(3)
        nome_novo = c1.text_input("Nome do Torneio")
        tipo_novo = c2.selectbox("Tipo", ["LIGA", "COPA"])
        modo_novo = c3.selectbox("Modo (Copa)", ["Ida e Volta", "Só Ida"])
        
        if st.form_submit_button("CRIAR"):
            if nome_novo:
                if nome_novo in torneios_salvos:
                    st.error("Já existe um torneio com este nome!")
                else:
                    st.session_state.torneio_ativo = nome_novo.strip()
                    st.session_state.formato = tipo_novo
                    st.session_state.modo = modo_novo
                    st.rerun()
            else:
                st.warning("Dê um nome ao torneio.")

else:
    # --- TORNEIO SELECIONADO ---
    tid = st.session_state.torneio_ativo
    fmt = st.session_state.formato
    df_t = df_db[df_db['torneio_id'].astype(str) == str(tid)].copy()

    with st.sidebar:
        st.header(f"🏆 {tid}")
        menu = st.radio("Menu", ["🏟️ Jogos", "📊 Chaveamento & Pódio", "⚙️ Admin"])
        is_admin = (st.text_input("Senha Admin", type="password") == "1234")
        if st.button("🏠 Sair / Mudar Torneio"): 
            del st.session_state.torneio_ativo
            st.rerun()

    # --- ABA JOGOS ---
    if menu == "🏟️ Jogos":
        if df_t.empty:
            st.warning("Este torneio ainda não tem jogos gerados.")
            if is_admin: st.info("Vá em 'Admin' para gerar os confrontos.")
        else:
            # Lógica de progressão (Quartas -> Semi -> Final)
            if fmt == "COPA":
                todas_fases = df_t['fase'].unique()
                ultima_fase = todas_fases[-1]
                jogos_fase = df_t[df_t['fase'] == ultima_fase]
                
                if all(is_done(x) for x in jogos_fase['finalizado']) and ultima_fase not in ["Final", "3º Lugar"]:
                    vencs, perds = [], []
                    for _, r in jogos_fase.iterrows():
                        v, p = obter_vencedor(r)
                        vencs.append(v); perds.append(p)
                    
                    # Define próxima fase
                    prox = "Final" if len(vencs) == 2 else "Semifinal" if len(vencs) == 4 else "Quartas"
                    novos_jogos = []
                    modo_atual = df_t['modo_copa'].iloc[0]
                    
                    if prox == "Final":
                        novos_jogos.append({'torneio_id': tid, 'formato': 'COPA', 'fase': '3º Lugar', 'a': perds[0], 'b': perds[1], 'finalizado': '0', 'modo_copa': 'Jogo Único'})
                        novos_jogos.append({'torneio_id': tid, 'formato': 'COPA', 'fase': 'Final', 'a': vencs[0], 'b': vencs[1], 'finalizado': '0', 'modo_copa': 'Jogo Único'})
                    else:
                        for i in range(0, len(vencs), 2):
                            novos_jogos.append({'torneio_id': tid, 'formato': 'COPA', 'fase': prox, 'a': vencs[i], 'b': vencs[i+1], 'finalizado': '0', 'modo_copa': modo_atual})
                    
                    salvar_dados(pd.concat([df_db, pd.DataFrame(novos_jogos)], ignore_index=True))

            # Exibição dos Jogos por Fase
            f_ordem = sorted(df_t['fase'].unique(), key=lambda x: 1 if x == "Final" else 0)
            for fase in f_ordem:
                st.subheader(f"📍 {fase}")
                for idx, row in df_t[df_t['fase'] == fase].iterrows():
                    with st.container(border=True):
                        c1, c2, c3 = st.columns([2,1,2])
                        # Texto do placar principal
                        if row['modo_copa'] == "Só Ida" or row['fase'] in ["Final", "3º Lugar"]:
                            pl = f"{row['gols_a']} x {row['gols_b']}"
                        else:
                            pl = f"({row['ida_a']}) {row['volta_a']} x {row['volta_b']} ({row['ida_b']})"
                        
                        if is_done(row['finalizado']) and (row['pen_a'] > 0 or row['pen_b'] > 0):
                            pl += f" (P: {row['pen_a']}x{row['pen_b']})"
                        
                        c1.markdown(f"<p style='text-align:right'><b>{row['a']}</b></p>", unsafe_allow_html=True)
                        c2.markdown(f"<div style='text-align:center; background:#eee; padding:5px; border-radius:5px;'>{pl}</div>", unsafe_allow_html=True)
                        c3.markdown(f"<p style='text-align:left'><b>{row['b']}</b></p>", unsafe_allow_html=True)

                        if is_admin:
                            if row['modo_copa'] == "Só Ida" or row['fase'] in ["Final", "3º Lugar"]:
                                with st.expander("✎ Lançar Placar"):
                                    col_a, col_b = st.columns(2)
                                    ga = col_a.number_input(f"Gols {row['a']}", 0, 99, int(row['gols_a']), key=f"ga_{idx}")
                                    gb = col_b.number_input(f"Gols {row['b']}", 0, 99, int(row['gols_b']), key=f"gb_{idx}")
                                    pa, pb = 0, 0
                                    if ga == gb and fmt == "COPA":
                                        st.warning("Pênaltis:")
                                        cpa, cpb = st.columns(2)
                                        pa = cpa.number_input("Pên A", 0, 99, int(row['pen_a']), key=f"pa_{idx}")
                                        pb = cpb.number_input("Pên B", 0, 99, int(row['pen_b']), key=f"pb_{idx}")
                                    if st.button("✅ Confirmar Resultado", key=f"btn_{idx}"):
                                        df_db.loc[idx, ['gols_a','gols_b','pen_a','pen_b','finalizado']] = [ga, gb, pa, pb, "SIM"]
                                        salvar_dados(df_db)
                            else:
                                exp_ida = st.expander("🏟️ Jogo de Ida")
                                with exp_ida:
                                    ci1, ci2 = st.columns(2)
                                    i1 = ci1.number_input(f"{row['a']} ", 0, 99, int(row['ida_a']), key=f"i1_{idx}")
                                    i2 = ci2.number_input(f"{row['b']} ", 0, 99, int(row['ida_b']), key=f"i2_{idx}")
                                exp_volta = st.expander("🏟️ Jogo de Volta")
                                with exp_volta:
                                    cv1, cv2 = st.columns(2)
                                    v1 = cv1.number_input(f"{row['a']}  ", 0, 99, int(row['volta_a']), key=f"v1_{idx}")
                                    v2 = cv2.number_input(f"{row['b']}  ", 0, 99, int(row['volta_b']), key=f"v2_{idx}")
                                    pa, pb = 0, 0
                                    if (i1+v1) == (i2+v2):
                                        st.warning("Empate no Agregado! Pênaltis:")
                                        cpa, cpb = st.columns(2)
                                        pa = cpa.number_input("Pên A", 0, 99, int(row['pen_a']), key=f"pa_{idx}")
                                        pb = cpb.number_input("Pên B", 0, 99, int(row['pen_b']), key=f"pb_{idx}")
                                if st.button("✅ Salvar Agregado", key=f"btn_{idx}"):
                                    df_db.loc[idx, ['ida_a','ida_b','volta_a','volta_b','pen_a','pen_b','finalizado']] = [i1, i2, v1, v2, pa, pb, "SIM"]
                                    salvar_dados(df_db)

    # --- ABA CHAVEAMENTO (BALÕES) ---
    elif menu == "📊 Chaveamento & Pódio":
        if fmt == "COPA":
            st.subheader("🗺️ Chaveamento")
            f_ordem_map = {"Oitavas":0, "Quartas":1, "Semifinal":2, "3º Lugar":3, "Final":4}
            f_presentes = sorted(df_t['fase'].unique(), key=lambda x: f_ordem_map.get(x, 99))
            
            if f_presentes:
                cols_chave = st.columns(len(f_presentes))
                for i, fase in enumerate(f_presentes):
                    with cols_chave[i]:
                        st.markdown(f"<div style='text-align:center; background:#444; color:white; border-radius:10px; padding:5px; margin-bottom:15px;'>{fase.upper()}</div>", unsafe_allow_html=True)
                        for _, r in df_t[df_t['fase'] == fase].iterrows():
                            done = is_done(r['finalizado'])
                            venc, _ = obter_vencedor(r)
                            
                            if r['modo_copa'] == "Só Ida" or r['fase'] in ["Final", "3º Lugar"]:
                                score = f"{r['gols_a']} x {r['gols_b']}"
                            else:
                                score = f"{r['ida_a']+r['volta_a']} x {r['ida_b']+r['volta_b']}"
                            
                            if done and (r['pen_a'] > 0 or r['pen_b'] > 0):
                                score += f" <br><small>(P: {r['pen_a']}x{r['pen_b']})</small>"
                            
                            b_cor = "#4CAF50" if done else "#ccc"
                            st.markdown(f"""
                            <div style="border: 2px solid {b_cor}; background: white; border-radius: 20px; padding: 10px; margin-bottom: 20px; text-align: center; box-shadow: 2px 2px 8px rgba(0,0,0,0.1);">
                                <div style="font-size: 11px; font-weight: bold; color: #777;">{r['a']} x {r['b']}</div>
                                <div style="font-size: 20px; font-weight: 900; margin: 5px 0; color:black;">{score}</div>
                                <div style="border-top: 1px solid #eee; padding-top: 5px; font-size: 10px; color:black;">Vencedor: <b>{venc}</b></div>
                            </div>
                            """, unsafe_allow_html=True)
            
            # Pódio
            fin = df_t[df_t['fase'] == 'Final']
            if not fin.empty and is_done(fin.iloc[0]['finalizado']):
                st.divider()
                st.balloons()
                camp, vice = obter_vencedor(fin.iloc[0])
                st.header("🏆 Pódio Final")
                c1, c2, c3 = st.columns(3)
                c1.success(f"🥇 **CAMPEÃO**\n\n{camp}")
                c2.info(f"🥈 **VICE**\n\n{vice}")
                t3d = df_t[df_t['fase'] == '3º Lugar']
                if not t3d.empty and is_done(t3d.iloc[0]['finalizado']):
                    t3, _ = obter_vencedor(t3d.iloc[0])
                    c3.warning(f"🥉 **3º LUGAR**\n\n{t3}")
        else:
            st.info("Visual de chaveamento disponível apenas para modo COPA.")

    # --- ABA ADMIN ---
    elif menu == "⚙️ Admin":
        if is_admin:
            with st.expander("🚀 Iniciar Torneio"):
                times_txt = st.text_area("Times (um por linha)")
                if st.button("Gerar Jogos"):
                    lista = [t.strip() for t in times_txt.split('\n') if t.strip()]
                    if len(lista) < 2: 
                        st.error("Adicione pelo menos 2 times.")
                    else:
                        novos = []
                        modo_atual = st.session_state.modo if 'modo' in st.session_state else "Ida e Volta"
                        if fmt == "LIGA":
                            for a, b in combinations(lista, 2):
                                novos.append({'torneio_id': tid, 'formato': 'LIGA', 'fase': 'Pontos Corridos', 'a': a, 'b': b, 'finalizado': '0'})
                        else:
                            f_nome = "Oitavas" if len(lista) > 8 else "Quartas" if len(lista) > 4 else "Semifinal"
                            for i in range(0, len(lista), 2):
                                if i+1 < len(lista):
                                    novos.append({'torneio_id': tid, 'formato': 'COPA', 'fase': f_nome, 'a': lista[i], 'b': lista[i+1], 'finalizado': '0', 'modo_copa': modo_atual})
                        salvar_dados(pd.concat([df_db, pd.DataFrame(novos)], ignore_index=True))
            
            st.divider()
            if st.button("🚨 EXCLUIR ESTE TORNEIO"):
                df_restante = df_db[df_db['torneio_id'] != tid]
                salvar_dados(df_restante)
                del st.session_state.torneio_ativo
                st.rerun()
