import streamlit as st
import pandas as pd
import itertools
import random
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAÇÃO INICIAL ---
st.set_page_config(page_title="BAGA BET PRO", layout="wide", page_icon="⚽")
conn = st.connection("gsheets", type=GSheetsConnection)

# --- FUNÇÕES AUXILIARES DE TRATAMENTO DE DADOS (A BLINDAGEM) ---
def money(v):
    try:
        return f"R$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return "R$ 0,00"

def safe_int(val):
    """Converte qualquer coisa para int ou retorna None se vazio"""
    try:
        if pd.isna(val) or str(val).strip() == "": return None
        return int(float(str(val).replace(",", ".")))
    except:
        return None

def safe_bool(val):
    """Detecta True/False seja texto, numero ou booleano"""
    s = str(val).upper().strip()
    return s in ["TRUE", "T", "VERDADEIRO", "1", "YES", "SIM"]

def parse_apostas(apostas_str):
    """Reconstroi a lista de apostas a partir do texto salvo"""
    lista_recuperada = []
    if pd.isna(apostas_str) or str(apostas_str).strip() == "":
        return lista_recuperada
    
    try:
        items = str(apostas_str).split("|")
        for item in items:
            parts = item.split(":")
            # Esperamos: Nome:Valor:Opcao
            if len(parts) == 3:
                lista_recuperada.append({
                    "nome": parts[0],
                    "valor": float(parts[1]),
                    "opcao": parts[2]
                })
    except:
        pass # Se der erro em uma aposta, ignora para não quebrar o app
    return lista_recuperada

# --- GERENCIAMENTO DE NUVEM ---
def carregar_dados():
    """Lê do Google Sheets e aplica a blindagem"""
    # st.cache_data.clear() # Descomentar se notar cache teimoso
    try:
        df = conn.read(ttl=0) # ttl=0 obriga a ler o dado mais novo
        if df is not None and not df.empty:
            # Limpeza básica de linhas vazias
            df = df.dropna(subset=['a', 'b'])
            raw_data = df.to_dict('records')
            
            dados_limpos = []
            todos_times = set()

            for row in raw_data:
                # Processa cada linha com as funções seguras
                jogo = {
                    "a": str(row.get('a', '')),
                    "b": str(row.get('b', '')),
                    "ga": safe_int(row.get('ga')),
                    "gb": safe_int(row.get('gb')),
                    "finalizado": safe_bool(row.get('finalizado')),
                    "apostas_abertas": safe_bool(row.get('apostas_abertas', True)),
                    "apostas": parse_apostas(row.get('apostas'))
                }
                dados_limpos.append(jogo)
                todos_times.add(jogo['a'])
                todos_times.add(jogo['b'])
            
            return dados_limpos, list(todos_times)
    except Exception as e:
        st.error(f"Erro de conexão: {e}")
    return [], []

def salvar_dados(lista_jogos):
    """Prepara os dados e envia para a nuvem"""
    if not lista_jogos: return
    
    # Prepara DataFrame para salvar
    df_save = pd.DataFrame(lista_jogos)
    
    # Converte a lista de dicionarios de apostas em STRING única (ex: Joao:10:A|Maria:20:B)
    df_save['apostas'] = df_save['apostas'].apply(
        lambda x: "|".join([f"{a['nome']}:{a['valor']}:{a['opcao']}" for a in x]) if isinstance(x, list) and x else ""
    )
    
    # Garante que as colunas essenciais existem
    cols_order = ['a', 'b', 'ga', 'gb', 'finalizado', 'apostas_abertas', 'apostas']
    for col in cols_order:
        if col not in df_save.columns: df_save[col] = None
        
    conn.update(data=df_save[cols_order])
    st.cache_data.clear() # Limpa cache para a próxima leitura vir correta

# --- INICIALIZAÇÃO DO ESTADO ---
# Carrega os dados na inicialização se ainda não existirem
if 'jogos' not in st.session_state:
    dados, times = carregar_dados()
    st.session_state.jogos = dados
    st.session_state.times = times

# --- BARRA LATERAL (ADMIN E MENU) ---
st.sidebar.title("BAGA BET ⚽")
senha = st.sidebar.text_input("Acesso Admin", type="password", placeholder="Deixe vazio para visitar")
sou_admin = (senha == "1234")

status_text = "🔓 MODO ADMIN" if sou_admin else "👀 MODO VISITANTE"
st.sidebar.caption(f"Status: {status_text}")

if st.sidebar.button("🔄 ATUALIZAR DADOS"):
    st.session_state.jogos, st.session_state.times = carregar_dados()
    st.rerun()

menu = st.sidebar.radio("Navegar", ["Tabela de Classificação", "Jogos da Rodada", "Ranking Apostadores", "Configuração (Admin)"])

# --- LÓGICA DAS TELAS ---

# 1. TABELA DE CLASSIFICAÇÃO
if menu == "Tabela de Classificação":
    st.header("📊 Classificação Oficial")
    
    # Recalcula a tabela SEMPRE que entra nesta tela, usando os dados atuais
    if not st.session_state.jogos:
        st.info("Nenhum dado carregado.")
    else:
        # Inicializa estrutura
        table = {t: {"P":0, "J":0, "V":0, "E":0, "D":0, "GP":0, "GC":0, "SG":0} for t in st.session_state.times if t}
        
        for j in st.session_state.jogos:
            # Só conta se tiver gols E (finalizado ou não, mas precisa ter gols)
            if j['ga'] is not None and j['gb'] is not None:
                a, b = j['a'], j['b']
                ga, gb = j['ga'], j['gb']
                
                # Atualiza Gols
                if a in table: 
                    table[a]['GP'] += ga
                    table[a]['GC'] += gb
                    table[a]['J'] += 1
                if b in table: 
                    table[b]['GP'] += gb
                    table[b]['GC'] += ga
                    table[b]['J'] += 1
                
                # Atualiza Pontos
                if ga > gb:
                    if a in table: table[a]['P'] += 3; table[a]['V'] += 1
                    if b in table: table[b]['D'] += 1
                elif gb > ga:
                    if b in table: table[b]['P'] += 3; table[b]['V'] += 1
                    if a in table: table[a]['D'] += 1
                else:
                    if a in table: table[a]['P'] += 1; table[a]['E'] += 1
                    if b in table: table[b]['P'] += 1; table[b]['E'] += 1
        
        # Calcula Saldo
        for t in table:
            table[t]['SG'] = table[t]['GP'] - table[t]['GC']
            
        # Cria DataFrame e exibe
        if table:
            df_table = pd.DataFrame.from_dict(table, orient='index')
            df_table = df_table.sort_values(by=["P", "V", "SG", "GP"], ascending=False)
            st.dataframe(df_table, use_container_width=True)
        else:
            st.warning("Times não encontrados.")

# 2. JOGOS (APOSTAS E RESULTADOS)
elif menu == "Jogos da Rodada":
    st.header("⚽ Partidas")
    
    if not st.session_state.jogos:
        st.warning("Nenhum jogo cadastrado.")
    
    for i, j in enumerate(st.session_state.jogos):
        with st.container(border=True):
            # Cabeçalho do Placar
            col_a, col_x, col_b = st.columns([2, 1, 2])
            display_ga = j['ga'] if j['ga'] is not None else ""
            display_gb = j['gb'] if j['gb'] is not None else ""
            
            col_a.markdown(f"<h3 style='text-align:right'>{j['a']}</h3>", unsafe_allow_html=True)
            col_x.markdown(f"<h2 style='text-align:center; color:#FF4B4B'>{display_ga} x {display_gb}</h2>", unsafe_allow_html=True)
            col_b.markdown(f"<h3 style='text-align:left'>{j['b']}</h3>", unsafe_allow_html=True)
            
            # --- ÁREA DO ADMIN (Lançar Resultado) ---
            if sou_admin:
                if not j['finalizado']:
                    with st.expander("⚙️ ADMIN: Lançar Resultado"):
                        c1, c2, c3 = st.columns([1, 1, 2])
                        n_ga = c1.number_input(f"Gols {j['a']}", 0, 20, key=f"ga_{i}")
                        n_gb = c2.number_input(f"Gols {j['b']}", 0, 20, key=f"gb_{i}")
                        if c3.button("✅ Finalizar Jogo", key=f"btn_fin_{i}"):
                            st.session_state.jogos[i]['ga'] = int(n_ga)
                            st.session_state.jogos[i]['gb'] = int(n_gb)
                            st.session_state.jogos[i]['finalizado'] = True
                            st.session_state.jogos[i]['apostas_abertas'] = False
                            salvar_dados(st.session_state.jogos)
                            st.rerun()
                else:
                    # Botão para reabrir caso tenha errado (Só Admin)
                    if st.button("⚠️ Reabrir Jogo (Correção)", key=f"reopen_{i}"):
                        st.session_state.jogos[i]['finalizado'] = False
                        st.session_state.jogos[i]['apostas_abertas'] = True # Opcional
                        salvar_dados(st.session_state.jogos)
                        st.rerun()

            # --- ÁREA DE APOSTAS ---
            # Mostra dados financeiros para todos
            total_ap = sum(ap['valor'] for ap in j['apostas'])
            st.caption(f"Total Apostado no Pote: {money(total_ap)} | Apostas: {len(j['apostas'])}")

            with st.expander("💰 Ver Apostas / Apostar"):
                c_form, c_list = st.columns([1, 2])
                
                # Coluna Esquerda: Formulário (SÓ SE FOR ADMIN OU SE QUISER LIBERAR USUARIO)
                # O prompt pediu: "quem nao colocar a senha... nao poder lancar dados". 
                # Assumo que "lancar dados" inclui fazer a aposta (escrita).
                with c_form:
                    if j['apostas_abertas'] and not j['finalizado']:
                        if sou_admin:
                            st.write("**Nova Aposta**")
                            nome_ap = st.text_input("Nome", key=f"nome_{i}")
                            valor_ap = st.number_input("Valor", 5.0, 500.0, 10.0, key=f"val_{i}")
                            palpite = st.radio("Palpite", [j['a'], "Empate", j['b']], key=f"palp_{i}")
                            
                            if st.button("Confirmar", key=f"add_bet_{i}"):
                                opt = "A" if palpite == j['a'] else "B" if palpite == j['b'] else "E"
                                st.session_state.jogos[i]['apostas'].append({
                                    "nome": nome_ap,
                                    "valor": valor_ap,
                                    "opcao": opt
                                })
                                salvar_dados(st.session_state.jogos)
                                st.rerun()
                        else:
                            st.info("Logue como Admin para registrar apostas.")
                    else:
                        st.warning("Apostas Encerradas.")

                # Coluna Direita: Lista de Apostas (Visível para todos)
                with c_list:
                    if j['apostas']:
                        df_bets = pd.DataFrame(j['apostas'])
                        # Traduz opcao A/B/E para nomes reais
                        mapa = {"A": j['a'], "B": j['b'], "E": "Empate"}
                        df_bets['Palpite'] = df_bets['opcao'].map(mapa)
                        df_bets['Valor'] = df_bets['valor'].apply(money)
                        
                        # Se jogo finalizado, calcula retorno simulado
                        if j['finalizado']:
                            venc = "A" if j['ga'] > j['gb'] else "B" if j['gb'] > j['ga'] else "E"
                            pote = sum(x['valor'] for x in j['apostas'])
                            ganhadores = sum(x['valor'] for x in j['apostas'] if x['opcao'] == venc)
                            
                            def calc_retorno(row):
                                if row['opcao'] == venc and ganhadores > 0:
                                    return (row['valor'] / ganhadores) * pote
                                return 0.0
                            
                            df_bets['Retorno'] = df_bets.apply(calc_retorno, axis=1)
                            df_bets['Lucro'] = df_bets['Retorno'] - df_bets['valor']
                            df_bets['Lucro'] = df_bets['Lucro'].apply(money)
                            st.dataframe(df_bets[['nome', 'Palpite', 'Valor', 'Lucro']], hide_index=True)
                        else:
                            st.dataframe(df_bets[['nome', 'Palpite', 'Valor']], hide_index=True)
                    else:
                        st.write("Nenhuma aposta registrada.")

# 3. RANKING FINANCEIRO
elif menu == "Ranking Apostadores":
    st.header("🤑 Ranking de Lucratividade")
    
    ranking_data = {}
    
    if st.session_state.jogos:
        for j in st.session_state.jogos:
            # Só calcula jogos finalizados com placar
            if j['finalizado'] and j['ga'] is not None:
                resultado_final = "A" if j['ga'] > j['gb'] else "B" if j['gb'] > j['ga'] else "E"
                
                # Cálculos do pote
                pote_total = sum(x['valor'] for x in j['apostas'])
                total_vencedor = sum(x['valor'] for x in j['apostas'] if x['opcao'] == resultado_final)
                
                for aposta in j['apostas']:
                    nome = aposta['nome']
                    investido = aposta['valor']
                    
                    if nome not in ranking_data:
                        ranking_data[nome] = {"Investido": 0.0, "Retorno": 0.0}
                    
                    ranking_data[nome]["Investido"] += investido
                    
                    if aposta['opcao'] == resultado_final and total_vencedor > 0:
                        # Regra de 3 do pote
                        ganho = (investido / total_vencedor) * pote_total
                        ranking_data[nome]["Retorno"] += ganho
    
    if ranking_data:
        df_rank = pd.DataFrame.from_dict(ranking_data, orient='index')
        df_rank['Lucro Líquido'] = df_rank['Retorno'] - df_rank['Investido']
        
        # Formatação para exibição
        df_display = df_rank.copy()
        df_display['Investido'] = df_display['Investido'].apply(money)
        df_display['Retorno'] = df_display['Retorno'].apply(money)
        df_display['Lucro Líquido'] = df_display['Lucro Líquido'].apply(money)
        
        # Ordenar pelo valor numérico real (df_rank) mas exibir o formatado
        df_display = df_display.sort_values(by="Lucro Líquido", ascending=False)
        
        st.dataframe(df_display, use_container_width=True)
    else:
        st.info("Ainda não há jogos finalizados para gerar ranking.")

# 4. CONFIGURAÇÃO (CRIAR NOVO TORNEIO)
elif menu == "Configuração (Admin)":
    if not sou_admin:
        st.error("Acesso Negado. Insira a senha na barra lateral.")
    else:
        st.header("🛠️ Configurações do Torneio")
        st.warning("Cuidado: Criar um novo torneio apaga todos os dados atuais da planilha!")
        
        with st.form("novo_torneio"):
            qtd = st.number_input("Quantidade de Times", 2, 20, 4)
            # Gera inputs dinamicamente
            nomes_times = []
            cols = st.columns(2)
            for i in range(qtd):
                with cols[i % 2]:
                    nomes_times.append(st.text_input(f"Nome do Time {i+1}"))
            
            submit = st.form_submit_button("🚀 CRIAR NOVO CAMPEONATO")
            
            if submit:
                # Filtra nomes vazios
                validos = [n.strip() for n in nomes_times if n.strip()]
                
                if len(validos) < 2:
                    st.error("Precisa de pelo menos 2 times.")
                else:
                    # Gera confrontos (Todos contra Todos)
                    confrontos = list(itertools.combinations(validos, 2))
                    random.shuffle(confrontos)
                    
                    # Cria estrutura limpa
                    novos_jogos = []
                    for c in confrontos:
                        novos_jogos.append({
                            "a": c[0], "b": c[1],
                            "ga": None, "gb": None,
                            "finalizado": False,
                            "apostas_abertas": True,
                            "apostas": []
                        })
                    
                    # Salva e reseta sessão
                    salvar_dados(novos_jogos)
                    st.session_state.jogos = novos_jogos
                    st.session_state.times = validos
                    st.success("Novo campeonato criado com sucesso!")
                    st.rerun()
