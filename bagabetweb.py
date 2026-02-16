import streamlit as st
import pandas as pd
from itertools import combinations
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="BAGA BET PRO", layout="wide", page_icon="⚽")
conn = st.connection("gsheets", type=GSheetsConnection)

# Colunas padrão baseadas no seu cabeçalho
COLUNAS_PADRAO = [
    'torneio_id', 'formato', 'fase', 'a', 'b', 'finalizado', 
    'gols_a', 'gols_b', 'ida_a', 'ida_b', 'volta_a', 'volta_b', 
    'pen_a', 'pen_b', 'apostas'
]

# --- FUNÇÕES DE SEGURANÇA ---
def safe_int(val):
    try:
        if pd.isna(val) or val == "" or str(val).lower() == "nan": return 0
        return int(float(val))
    except: return 0

def is_done(val):
    v = str(val).upper().strip()
    return v in ["1", "TRUE", "1.0", "VERDADEIRO"]

def carregar_db():
    st.cache_data.clear()
    try:
        df = conn.read(ttl=0)
        # Se a planilha estiver vazia ou sem as colunas certas, força a criação delas
        if df is None or df.empty:
            return pd.DataFrame(columns=COLUNAS_PADRAO)
        
        # Garante que TODAS as colunas necessárias existam no DF
        for col in COLUNAS_PADRAO:
            if col not in df.columns:
                df[col] = None
        return df
    except:
        return pd.DataFrame(columns=COLUNAS_PADRAO)

def salvar_db(df):
    # Limpa colunas fantasmas geradas pelo Pandas/Excel
    df_save = df.loc[:, ~df.columns.str.contains('^Unnamed')]
    conn.update(data=df_save)
    st.cache_data.clear()
    st.toast("Dados sincronizados com o Google Sheets! ✅")

# --- CARREGAMENTO INICIAL ---
df_db = carregar_db()

# --- TELA DE ENTRADA ---
if 'torneio_ativo' not in st.session_state:
    st.title("⚽ BAGA BET PRO")
    
    # Listar Torneios Existentes
    existentes = df_db.dropna(subset=['torneio_id'])
    if not existentes.empty:
        st.subheader("📂 Selecione um Torneio")
        t_list = existentes[['torneio_id', 'formato']].drop_duplicates()
        cols = st.columns(3)
        for i, row in enumerate(t_list.values):
            icone = "🏆" if str(row[1]).upper() == "COPA" else "📈"
            if cols[i%3].button(f"{icone} {row[0]}", use_container_width=True):
                st.session_state.torneio_ativo = row[0]
                st.session_state.formato = str(row[1]).upper()
                st.rerun()

    st.divider()
    st.subheader("🆕 Criar Novo Torneio")
    c1, c2 = st.columns(2)
    n_nome = c1.text_input("Nome do Torneio")
    n_tipo = c2.selectbox("Tipo", ["LIGA", "COPA"])
    if st.button("🚀 CRIAR TORNEIO", use_container_width=True):
        if n_nome:
            st.session_state.torneio_ativo = n_nome.strip()
            st.session_state.formato = n_tipo
            st.rerun()

else:
    # --- INTERIOR DO TORNEIO ---
    t_id = st.session_state.torneio_ativo
    formato = st.session_state.formato
    
    # Filtro de segurança para pegar apenas os jogos deste torneio
    jogos_df = df_db[df_db['torneio_id'].astype(str) == str(t_id)].copy()

    with st.sidebar:
        st.header(f"⚽ {t_id}")
        st.write(f"Formato: **{formato}**")
        menu = st.radio("Menu", ["🏟️ Jogos", "📊 Classificação", "🤑 Ranking", "⚙️ Admin"])
        is_admin = (st.text_input("Senha Admin", type="password") == "1234")
        if st.button("🏠 Sair do Torneio"):
            for k in list(st.session_state.keys()): del st.session_state[k]
            st.rerun()

    # --- ABA ADMIN (GERADOR) ---
    if menu == "⚙️ Admin":
        if is_admin:
            st.subheader("Configurar Equipes")
            times_txt = st.text_area("Lista de Times (um por linha)")
            if st.button("GERAR JOGOS"):
                lista = [t.strip() for t in times_txt.split("\n") if t.strip()]
                if len(lista) < 2:
                    st.error("Adicione pelo menos 2 times!")
                else:
                    novos = []
                    if formato == "LIGA":
                        for a, b in combinations(lista, 2):
                            novos.append({"torneio_id":t_id, "formato":"LIGA", "a":a, "b":b, "finalizado":"0"})
                    else:
                        for i in range(0, len(lista), 2):
                            if i+1 < len(lista):
                                novos.append({"torneio_id":t_id, "formato":"COPA", "a":lista[i], "b":lista[i+1], "finalizado":"0"})
                    
                    df_novos = pd.DataFrame(novos)
                    # Mantém os outros torneios e substitui apenas o atual
                    df_final = pd.concat([df_db[df_db['torneio_id'].astype(str) != str(t_id)], df_novos], ignore_index=True)
                    salvar_db(df_final)
                    st.rerun()
        else:
            st.warning("Área restrita para administradores.")

    # --- ABA JOGOS ---
    elif menu == "🏟️ Jogos":
        if jogos_df.empty:
            st.info("Vá em Admin para gerar os jogos.")
        else:
            for idx, row in jogos_df.iterrows():
                with st.container(border=True):
                    c1, c2, c3 = st.columns([2, 1, 2])
                    c1.markdown(f"<p style='text-align:right; font-size:20px;'><b>{row['a']}</b></p>", unsafe_allow_html=True)
                    
                    # Lógica de Placar
                    if formato == "LIGA":
                        placar = f"{safe_int(row.get('gols_a'))} x {safe_int(row.get('gols_b'))}"
                    else:
                        ia, ib = safe_int(row.get('ida_a')), safe_int(row.get('ida_b'))
                        va, vb = safe_int(row.get('volta_a')), safe_int(row.get('volta_b'))
                        placar = f"({ia}) {va} x {vb} ({ib})"
                    
                    c2.markdown(f"<h3 style='text-align:center; background:#f0f2f6; border-radius:10px; padding:5px;'>{placar}</h3>", unsafe_allow_html=True)
                    c3.markdown(f"<p style='text-align:left; font-size:20px;'><b>{row['b']}</b></p>", unsafe_allow_html=True)

                    if is_admin:
                        with st.expander("📝 Editar Resultado"):
                            if formato == "LIGA":
                                ra = st.number_input(f"Gols {row['a']}", 0, key=f"ra{idx}")
                                rb = st.number_input(f"Gols {row['b']}", 0, key=f"rb{idx}")
                                if st.button("Confirmar Liga", key=f"sl{idx}"):
                                    df_db.loc[idx, ['gols_a', 'gols_b', 'finalizado']] = [ra, rb, "1"]
                                    salvar_db(df_db); st.rerun()
                            else:
                                ci, cv = st.columns(2)
                                i1 = ci.number_input("Ida A", 0, key=f"i1{idx}")
                                i2 = ci.number_input("Ida B", 0, key=f"i2{idx}")
                                v1 = cv.number_input("Vol A", 0, key=f"v1{idx}")
                                v2 = cv.number_input("Vol B", 0, key=f"v2{idx}")
                                if st.button("Confirmar Copa", key=f"sc{idx}"):
                                    df_db.loc[idx, ['ida_a','ida_b','volta_a','volta_b', 'finalizado']] = [i1, i2, v1, v2, "1"]
                                    salvar_db(df_db); st.rerun()

                    # --- SISTEMA DE APOSTAS ---
                    with st.expander("🤑 Apostas"):
                        lista_ap = []
                        raw_ap = str(row.get('apostas', ''))
                        if raw_ap and raw_ap != "nan":
                            for item in raw_ap.split("|"):
                                p = item.split(":")
                                if len(p) == 3: lista_ap.append({"Nome": p[0], "R$": float(p[1]), "Vence": p[2]})
                        
                        if not is_done(row.get('finalizado')):
                            with st.form(f"f_ap{idx}"):
                                ca1, ca2, ca3 = st.columns([2,1,2])
                                u_nome = ca1.text_input("Nome")
                                u_valor = ca2.number_input("R$", 1, 500, 10)
                                opcs = ["A", "B", "Empate"] if formato == "LIGA" else ["A", "B"]
                                u_vence = ca3.radio("Quem vence?", opcs, horizontal=True)
                                if st.form_submit_button("Lançar Aposta"):
                                    if u_nome:
                                        nova = f"{u_nome}:{u_valor}:{u_vence}"
                                        txt_ap = f"{raw_ap}|{nova}" if raw_ap and raw_ap != "nan" else nova
                                        df_db.loc[idx, 'apostas'] = txt_ap
                                        salvar_db(df_db); st.rerun()
                        
                        if lista_ap: st.dataframe(pd.DataFrame(lista_ap), hide_index=True, use_container_width=True)

    # --- ABA CLASSIFICAÇÃO (PARA LIGA) ---
    elif menu == "📊 Classificação":
        if formato == "LIGA":
            st.subheader("Tabela de Pontos")
            stats = {}
            times = pd.concat([jogos_df['a'], jogos_df['b']]).unique()
            for t in times: stats[t] = {"P":0,"J":0,"V":0,"E":0,"D":0,"GP":0,"GC":0}
            
            for _, r in jogos_df.iterrows():
                if is_done(r.get('finalizado')):
                    ga, gb = safe_int(r['gols_a']), safe_int(r['gols_b'])
                    stats[r['a']]["J"]+=1; stats[r['b']]["J"]+=1
                    stats[r['a']]["GP"]+=ga; stats[r['a']]["GC"]+=gb
                    stats[r['b']]["GP"]+=gb; stats[r['b']]["GC"]+=ga
                    if ga > gb: stats[r['a']]["P"]+=3; stats[r['a']]["V"]+=1; stats[r['b']]["D"]+=1
                    elif gb > ga: stats[r['b']]["P"]+=3; stats[r['b']]["V"]+=1; stats[r['a']]["D"]+=1
                    else: stats[r['a']]["P"]+=1; stats[r['b']]["P"]+=1; stats[r['a']]["E"]+=1; stats[r['b']]["E"]+=1
            
            df_tab = pd.DataFrame.from_dict(stats, orient='index').reset_index().rename(columns={'index':'Time'})
            df_tab['SG'] = df_tab['GP'] - df_tab['GC']
            st.table(df_tab.sort_values(by=["P", "V", "SG"], ascending=False))
        else:
            st.info("A Copa não utiliza tabela de pontos. Veja os vencedores na aba Jogos.")

    # --- ABA RANKING (QUEM GANHOU MAIS DINHEIRO) ---
    elif menu == "🤑 Ranking":
        st.subheader("💰 Lucros e Prejuízos")
        financeiro = {}
        
        for _, r in jogos_df.iterrows():
            if is_done(r.get('finalizado')):
                # Define o vencedor real do jogo
                if formato == "LIGA":
                    ga, gb = safe_int(r['gols_a']), safe_int(r['gols_b'])
                    vencedor_real = "A" if ga > gb else "B" if gb > ga else "Empate"
                else:
                    total_a = safe_int(r['ida_a']) + safe_int(r['volta_a'])
                    total_b = safe_int(r['ida_b']) + safe_int(r['volta_b'])
                    vencedor_real = "A" if total_a > total_b else "B"
                
                # Processa as apostas desse jogo
                raw = str(r.get('apostas', ''))
                if raw and raw != "nan":
                    for item in raw.split("|"):
                        parts = item.split(":")
                        if len(parts) == 3:
                            nome, valor, palpite = parts[0], float(parts[1]), parts[2]
                            if nome not in financeiro: financeiro[nome] = 0
                            if palpite == vencedor_real: financeiro[nome] += valor
                            else: financeiro[nome] -= valor
        
        if financeiro:
            res_fin = pd.DataFrame.from_dict(financeiro, orient='index', columns=['Saldo R$']).reset_index()
            res_fin = res_fin.rename(columns={'index': 'Apostador'}).sort_values(by='Saldo R$', ascending=False)
            st.table(res_fin)
        else:
            st.info("O ranking será atualizado assim que os jogos forem finalizados.")
