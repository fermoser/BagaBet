import streamlit as st
import pandas as pd
from itertools import combinations
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="GESTOR ESPORTIVO PRO", layout="wide", page_icon="⚽")
conn = st.connection("gsheets", type=GSheetsConnection)

# --- DEFINIÇÃO RIGOROSA DAS COLUNAS (SEM APOSTAS) ---
# Se a planilha estiver vazia, estas colunas serão criadas.
COLUNAS_PADRAO = [
    'torneio_id',   # Nome do torneio
    'formato',      # LIGA ou COPA
    'fase',         # Rodada 1, Quartas, Final (Para Copa)
    'a', 'b',       # Nome dos times
    'finalizado',   # 0 ou 1
    'gols_a', 'gols_b',       # Placar Liga
    'ida_a', 'ida_b',         # Placar Ida Copa
    'volta_a', 'volta_b'      # Placar Volta Copa
]

# --- FUNÇÕES DE SEGURANÇA (MOTOR DO SISTEMA) ---
def safe_int(val):
    """Converte qualquer lixo (texto, vazio, nan) em 0 ou inteiro."""
    try:
        if pd.isna(val) or val == "" or str(val).lower() == "nan": return 0
        return int(float(val))
    except: return 0

def is_done(val):
    """Verifica se o jogo está finalizado."""
    v = str(val).upper().strip()
    return v in ["1", "TRUE", "1.0", "VERDADEIRO", "SIM"]

def carregar_db():
    """Lê a planilha e corrige falhas estruturais automaticamente."""
    st.cache_data.clear()
    try:
        df = conn.read(ttl=0)
        # Se veio vazio ou nulo, cria do zero
        if df is None or df.empty:
            return pd.DataFrame(columns=COLUNAS_PADRAO)
        
        # Garante que todas as colunas essenciais existam
        for col in COLUNAS_PADRAO:
            if col not in df.columns:
                df[col] = None # Cria a coluna vazia se não existir
        
        # Remove colunas 'Unnamed' ou lixo
        df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
        return df
    except Exception as e:
        # Em caso de erro crítico de leitura, retorna estrutura virgem
        return pd.DataFrame(columns=COLUNAS_PADRAO)

def salvar_db(df):
    """Salva no Google Sheets limpando sujeira."""
    try:
        # Garante que estamos salvando apenas as colunas certas
        df_save = df[COLUNAS_PADRAO].copy()
        conn.update(data=df_save)
        st.cache_data.clear()
        st.toast("✅ Banco de dados atualizado com sucesso!")
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")

# --- INICIALIZAÇÃO ---
df_db = carregar_db()

# --- NAVEGAÇÃO PRINCIPAL ---
if 'torneio_ativo' not in st.session_state:
    st.title("⚽ GESTOR DE CAMPEONATOS")
    st.info("Sistema pronto. Se a planilha estava vazia, os cabeçalhos serão criados ao criar o primeiro torneio.")

    # 1. Listar Torneios Existentes
    existentes = df_db.dropna(subset=['torneio_id'])
    if not existentes.empty:
        st.subheader("📂 Torneios Encontrados")
        t_list = existentes[['torneio_id', 'formato']].drop_duplicates()
        
        cols = st.columns(3)
        for i, row in enumerate(t_list.values):
            nome_t = str(row[0])
            tipo_t = str(row[1]).upper()
            icone = "🏆" if tipo_t == "COPA" else "📈"
            
            if cols[i%3].button(f"{icone} {nome_t}", key=f"btn_open_{i}", use_container_width=True):
                st.session_state.torneio_ativo = nome_t
                st.session_state.formato = tipo_t
                st.rerun()

    st.divider()

    # 2. Criar Novo Torneio
    st.subheader("🆕 Novo Campeonato")
    with st.form("criar_torneio"):
        c1, c2 = st.columns(2)
        n_nome = c1.text_input("Nome do Campeonato (Ex: Brasileirão 2024)")
        n_tipo = c2.selectbox("Formato", ["LIGA", "COPA"])
        
        if st.form_submit_button("CRIAR AGORA"):
            if n_nome:
                # Apenas define a sessão, os dados serão gravados ao gerar jogos
                st.session_state.torneio_ativo = n_nome.strip()
                st.session_state.formato = n_tipo
                st.rerun()
            else:
                st.warning("Digite um nome para o torneio.")

else:
    # --- DENTRO DO TORNEIO ---
    t_id = st.session_state.torneio_ativo
    formato = st.session_state.formato
    
    # Filtra apenas os jogos deste torneio
    jogos_df = df_db[df_db['torneio_id'].astype(str) == str(t_id)].copy()

    # --- SIDEBAR ---
    with st.sidebar:
        st.title(f"⚽ {t_id}")
        st.caption(f"Modo: {formato}")
        
        opcoes = ["🏟️ Jogos & Resultados", "⚙️ Admin / Gerador"]
        if formato == "LIGA":
            opcoes.insert(1, "📊 Tabela de Classificação")
            
        menu = st.radio("Menu", opcoes)
        st.divider()
        
        # Login Simples
        senha = st.text_input("Senha Admin", type="password")
        is_admin = (senha == "1234")
        
        if st.button("⬅️ Voltar ao Início"):
            for key in list(st.session_state.keys()): del st.session_state[key]
            st.rerun()

    # =========================================================================
    # ABA: ADMIN / GERADOR
    # =========================================================================
    if menu == "⚙️ Admin / Gerador":
        st.header("⚙️ Administração")
        
        if not is_admin:
            st.warning("Digite a senha '1234' na barra lateral para acessar.")
        else:
            with st.expander("📝 Gerar Novos Jogos", expanded=True):
                st.write("Cole a lista de times abaixo (um por linha):")
                times_txt = st.text_area("Times", height=150)
                fase_nome = "Rodada Única"
                
                if formato == "COPA":
                    fase_nome = st.text_input("Nome da Fase (Ex: Oitavas, Quartas, Final)", "Quartas de Final")
                
                if st.button("🔥 GERAR CONFRONTOS"):
                    lista_times = [t.strip() for t in times_txt.split("\n") if t.strip()]
                    
                    if len(lista_times) < 2:
                        st.error("Preciso de pelo menos 2 times!")
                    else:
                        novos_jogos = []
                        
                        if formato == "LIGA":
                            # Gera todos contra todos
                            for time_a, time_b in combinations(lista_times, 2):
                                novos_jogos.append({
                                    "torneio_id": t_id, "formato": "LIGA", "fase": "Pontos Corridos",
                                    "a": time_a, "b": time_b, "finalizado": "0"
                                })
                        else:
                            # Gera pares (1x2, 3x4...)
                            for i in range(0, len(lista_times), 2):
                                if i + 1 < len(lista_times):
                                    novos_jogos.append({
                                        "torneio_id": t_id, "formato": "COPA", "fase": fase_nome,
                                        "a": lista_times[i], "b": lista_times[i+1], "finalizado": "0"
                                    })

                        # Salvar
                        if novos_jogos:
                            df_novos = pd.DataFrame(novos_jogos)
                            # Adiciona colunas faltantes no df_novos para bater com padrao
                            for col in COLUNAS_PADRAO:
                                if col not in df_novos.columns: df_novos[col] = None
                            
                            df_final = pd.concat([df_db, df_novos], ignore_index=True)
                            salvar_db(df_final)
                            st.success(f"{len(novos_jogos)} jogos gerados!")
                            st.rerun()

            st.divider()
            if st.button("⚠️ EXCLUIR ESTE TORNEIO (IRREVERSÍVEL)"):
                # Remove apenas as linhas deste torneio ID
                df_limpo = df_db[df_db['torneio_id'].astype(str) != str(t_id)]
                salvar_db(df_limpo)
                st.session_state.clear()
                st.rerun()

    # =========================================================================
    # ABA: JOGOS & RESULTADOS
    # =========================================================================
    elif menu == "🏟️ Jogos & Resultados":
        st.header("Resultados")
        
        if jogos_df.empty:
            st.info("Nenhum jogo encontrado. Vá em 'Admin' para gerar os confrontos.")
        else:
            # Agrupar por fase (importante para Copa, útil para Liga)
            fases = jogos_df['fase'].fillna("Geral").unique()
            
            for fase_atual in fases:
                st.markdown(f"### 📍 {fase_atual}")
                jogos_da_fase = jogos_df[jogos_df['fase'] == fase_atual]
                
                for idx, row in jogos_da_fase.iterrows():
                    with st.container(border=True):
                        # Layout Visual
                        c_timeA, c_placar, c_timeB = st.columns([2, 1, 2])
                        
                        nome_a = row['a']
                        nome_b = row['b']
                        
                        # Definição do Texto do Placar
                        if formato == "LIGA":
                            g_a = safe_int(row['gols_a'])
                            g_b = safe_int(row['gols_b'])
                            placar_txt = f"{g_a} x {g_b}"
                        else:
                            # Modo Copa (Ida e Volta)
                            ia, ib = safe_int(row['ida_a']), safe_int(row['ida_b'])
                            va, vb = safe_int(row['volta_a']), safe_int(row['volta_b'])
                            placar_txt = f"({ia}) {va} x {vb} ({ib})"

                        # Renderização
                        c_timeA.markdown(f"<h4 style='text-align:right'>{nome_a}</h4>", unsafe_allow_html=True)
                        c_placar.markdown(f"<div style='text-align:center; background:#eee; padding:5px; border-radius:8px; font-weight:bold'>{placar_txt}</div>", unsafe_allow_html=True)
                        c_timeB.markdown(f"<h4 style='text-align:left'>{nome_b}</h4>", unsafe_allow_html=True)
                        
                        # Área de Edição (Apenas Admin)
                        if is_admin:
                            with st.expander("📝 Editar Placar"):
                                with st.form(key=f"form_edit_{idx}"):
                                    if formato == "LIGA":
                                        col_ea, col_eb = st.columns(2)
                                        novo_a = col_ea.number_input(f"Gols {nome_a}", 0, 50, safe_int(row['gols_a']))
                                        novo_b = col_eb.number_input(f"Gols {nome_b}", 0, 50, safe_int(row['gols_b']))
                                        
                                        if st.form_submit_button("Salvar Liga"):
                                            df_db.loc[idx, ['gols_a', 'gols_b', 'finalizado']] = [novo_a, novo_b, "1"]
                                            salvar_db(df_db)
                                            st.rerun()
                                    else:
                                        # Edição Copa
                                        st.caption("Jogo de Ida")
                                        ci1, ci2 = st.columns(2)
                                        ni_a = ci1.number_input("Ida A", 0, 50, safe_int(row['ida_a']), key=f"ia_{idx}")
                                        ni_b = ci2.number_input("Ida B", 0, 50, safe_int(row['ida_b']), key=f"ib_{idx}")
                                        
                                        st.caption("Jogo de Volta")
                                        cv1, cv2 = st.columns(2)
                                        nv_a = cv1.number_input("Volta A", 0, 50, safe_int(row['volta_a']), key=f"va_{idx}")
                                        nv_b = cv2.number_input("Volta B", 0, 50, safe_int(row['volta_b']), key=f"vb_{idx}")
                                        
                                        if st.form_submit_button("Salvar Copa"):
                                            df_db.loc[idx, ['ida_a', 'ida_b', 'volta_a', 'volta_b', 'finalizado']] = [ni_a, ni_b, nv_a, nv_b, "1"]
                                            salvar_db(df_db)
                                            st.rerun()

    # =========================================================================
    # ABA: CLASSIFICAÇÃO (Apenas LIGA)
    # =========================================================================
    elif menu == "📊 Tabela de Classificação":
        st.header("Tabela")
        
        # 1. Identificar todos os times únicos
        times_unicos = pd.concat([jogos_df['a'], jogos_df['b']]).dropna().unique()
        
        if len(times_unicos) == 0:
            st.warning("Sem dados para gerar tabela.")
        else:
            # 2. Inicializar dicionário de estatísticas (Tudo Zero)
            stats = {t: {'P':0, 'J':0, 'V':0, 'E':0, 'D':0, 'GP':0, 'GC':0, 'SG':0} for t in times_unicos}
            
            # 3. Calcular pontos
            for _, row in jogos_df.iterrows():
                # Só calcula se estiver finalizado
                if is_done(row['finalizado']):
                    ta, tb = row['a'], row['b']
                    ga = safe_int(row['gols_a'])
                    gb = safe_int(row['gols_b'])
                    
                    # Atualiza Jogos e Gols
                    stats[ta]['J'] += 1; stats[tb]['J'] += 1
                    stats[ta]['GP'] += ga; stats[ta]['GC'] += gb
                    stats[tb]['GP'] += gb; stats[tb]['GC'] += ga
                    stats[ta]['SG'] += (ga - gb); stats[tb]['SG'] += (gb - ga)
                    
                    # Atualiza Pontos (Vitoria/Empate/Derrota)
                    if ga > gb:
                        stats[ta]['P'] += 3; stats[ta]['V'] += 1; stats[tb]['D'] += 1
                    elif gb > ga:
                        stats[tb]['P'] += 3; stats[tb]['V'] += 1; stats[ta]['D'] += 1
                    else:
                        stats[ta]['P'] += 1; stats[tb]['P'] += 1
                        stats[ta]['E'] += 1; stats[tb]['E'] += 1

            # 4. Converter para DataFrame e Exibir
            df_tabela = pd.DataFrame.from_dict(stats, orient='index')
            df_tabela.index.name = 'Equipe'
            df_tabela = df_tabela.reset_index()
            
            # Ordenação: Pontos > Vitórias > Saldo de Gols
            df_tabela = df_tabela.sort_values(by=['P', 'V', 'SG'], ascending=False)
            
            st.dataframe(
                df_tabela, 
                hide_index=True, 
                use_container_width=True,
                column_config={
                    "Equipe": st.column_config.TextColumn("Time", width="medium"),
                    "P": st.column_config.ProgressColumn("Pontos", format="%d", min_value=0, max_value=df_tabela['P'].max())
                }
            )
