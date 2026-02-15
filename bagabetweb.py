import streamlit as st
import pandas as pd
import itertools
import random
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="BAGA BET PRO", layout="wide", page_icon="⚽")
conn = st.connection("gsheets", type=GSheetsConnection)

# --- FUNÇÕES DE SEGURANÇA E TRATAMENTO ---
def money(v):
    try:
        return f"R$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return "R$ 0,00"

def safe_int(val):
    try:
        if pd.isna(val) or str(val).strip() == "": return None
        return int(float(str(val).replace(",", ".")))
    except:
        return None

def safe_bool(val, padrao=False):
    """Lê booleano do Sheets mesmo que venha como texto, numero ou vazio"""
    if pd.isna(val) or str(val).strip() == "":
        return padrao
    s = str(val).upper().strip()
    return s in ["TRUE", "T", "VERDADEIRO", "1", "YES", "SIM"]

def parse_apostas(apostas_str):
    """Reconstroi a lista de apostas garantindo que não quebre"""
    lista = []
    if pd.isna(apostas_str) or str(apostas_str).strip() == "":
        return lista
    
    try:
        # Remove espaços extras e divide
        texto_limpo = str(apostas_str).strip()
        items = texto_limpo.split("|")
        for item in items:
            parts = item.split(":")
            if len(parts) >= 3: # Garante que tem Nome:Valor:Opcao
                lista.append({
                    "nome": parts[0].strip(),
                    "valor": float(parts[1]),
                    "opcao": parts[2].strip()
                })
    except:
        pass 
    return lista

# --- NUVEM (LEITURA E ESCRITA) ---
def carregar_dados():
    st.cache_data.clear() # FORÇA LIMPEZA DE CACHE SEMPRE QUE LER
    try:
        df = conn.read(ttl=0)
        if df is not None and not df.empty:
            df = df.dropna(subset=['a', 'b']) # Remove linhas vazias
            raw = df.to_dict('records')
            
            dados_limpos = []
            todos_times = set()

            for row in raw:
                # 1. Status do Jogo
                finalizado = safe_bool(row.get('finalizado'), False)
                
                # 2. Status das Apostas (CORREÇÃO AQUI)
                # Se o jogo NÃO está finalizado, o padrão de apostas é TRUE (Aberto)
                # Se o jogo ESTÁ finalizado, o padrão é FALSE (Fechado)
                padrao_aberto = not finalizado
                apostas_abertas = safe_bool(row.get('apostas_abertas'), padrao_aberto)

                jogo = {
                    "a": str(row.get('a', '')),
                    "b": str(row.get('b', '')),
                    "ga": safe_int(row.get('ga')),
                    "gb": safe_int(row.get('gb')),
                    "finalizado": finalizado,
                    "apostas_abertas": apostas_abertas,
                    "apostas": parse_apostas(row.get('apostas'))
                }
                dados_limpos.append(jogo)
                todos_times.add(jogo['a'])
                todos_times.add(jogo['b'])
            
            return dados_limpos, list(todos_times)
    except Exception as e:
        st.error(f"Erro ao conectar com a planilha: {e}")
        return [], []

def salvar_dados(lista):
    if not lista: return
    df = pd.DataFrame(lista)
    # Serializa apostas para texto
    df['apostas'] = df['apostas'].apply(
        lambda x: "|".join([f"{a['nome']}:{a['valor']}:{a['opcao']}" for a in x]) if isinstance(x, list) and x else ""
    )
    # Garante colunas
    cols = ['a', 'b', 'ga', 'gb', 'finalizado', 'apostas_abertas', 'apostas']
    for c in cols: 
        if c not in df.columns: df[c] = None
        
    conn.update(data=df[cols])
    st.cache_data.clear()

# --- INICIALIZAÇÃO ---
if 'jogos' not in st.session_state:
    st.session_state.jogos, st.session_state.times = carregar_dados()

# --- SIDEBAR ---
st.sidebar.title("BAGA BET ⚽")
senha = st.sidebar.text_input("Senha Admin", type="password")
sou_admin = (senha == "1234")

if st.sidebar.button("🔄 FORÇAR ATUALIZAÇÃO"):
    st.session_state.jogos, st.session_state.times = carregar_dados()
    st.rerun()

aba = st.sidebar.radio("Menu", ["Jogos e Apostas", "Classificação", "Ranking Financeiro", "Novo Torneio (Admin)"])

# ==============================================================================
# 1. ABA JOGOS E APOSTAS (CORRIGIDA PARA VISITANTE VER TUDO)
# ==============================================================================
if aba == "Jogos e Apostas":
    st.header("⚽ Partidas da Rodada")
    
    if not st.session_state.jogos:
        st.info("Nenhum jogo encontrado.")
    
    for i, j in enumerate(st.session_state.jogos):
        with st.container(border=True):
            # --- PLACAR ---
            c1, c2, c3 = st.columns([2, 1, 2])
            ga_vis = j['ga'] if j['ga'] is not None else ""
            gb_vis = j['gb'] if j['gb'] is not None else ""
            
            cor_placar = "red" if j['finalizado'] else "gray"
            
            c1.markdown(f"<h3 style='text-align:right'>{j['a']}</h3>", unsafe_allow_html=True)
            c2.markdown(f"<h2 style='text-align:center; color:{cor_placar}'>{ga_vis} x {gb_vis}</h2>", unsafe_allow_html=True)
            c3.markdown(f"<h3 style='text-align:left'>{j['b']}</h3>", unsafe_allow_html=True)

            # --- STATUS ---
            status = "🔴 FINALIZADO" if j['finalizado'] else "🟢 APOSTAS ABERTAS" if j['apostas_abertas'] else "🟡 AGUARDANDO RESULTADO"
            st.caption(f"Status: {status} | Apostas: {len(j['apostas'])}")

            # --- ADMIN: CONTROLES ---
            if sou_admin:
                if not j['finalizado']:
                    with st.expander("⚙️ ADMIN: Definir Resultado"):
                        cc1, cc2, cc3 = st.columns([1,1,2])
                        v_ga = cc1.number_input(f"Gols {j['a']}", 0, 20, key=f"ga{i}")
                        v_gb = cc2.number_input(f"Gols {j['b']}", 0, 20, key=f"gb{i}")
                        if cc3.button("ENCERRAR JOGO", key=f"end{i}"):
                            st.session_state.jogos[i]['ga'] = int(v_ga)
                            st.session_state.jogos[i]['gb'] = int(v_gb)
                            st.session_state.jogos[i]['finalizado'] = True
                            st.session_state.jogos[i]['apostas_abertas'] = False
                            salvar_dados(st.session_state.jogos)
                            st.rerun()
                else:
                    if st.button("⚠️ REABRIR (Correção)", key=f"reopen{i}"):
                        st.session_state.jogos[i]['finalizado'] = False
                        st.session_state.jogos[i]['apostas_abertas'] = True
                        salvar_dados(st.session_state.jogos)
                        st.rerun()

            # --- ÁREA DE APOSTAS (VISÍVEL PARA TODOS) ---
            # Separamos em abas internas para ficar limpo
            tab_ver, tab_apostar = st.tabs(["📋 Ver Apostas Feitas", "💰 Fazer Aposta"])
            
            # Aba 1: Lista (Visitante VÊ TUDO AQUI)
            with tab_ver:
                if j['apostas']:
                    df_ap = pd.DataFrame(j['apostas'])
                    # Traduz opção
                    df_ap['Palpite'] = df_ap['opcao'].map({"A": j['a'], "B": j['b'], "E": "Empate"})
                    df_ap['R$'] = df_ap['valor'].apply(money)
                    
                    if j['finalizado']:
                        # Mostra Lucro se acabou
                        res = "A" if j['ga'] > j['gb'] else "B" if j['gb'] > j['ga'] else "E"
                        pote = sum(x['valor'] for x in j['apostas'])
                        venc = sum(x['valor'] for x in j['apostas'] if x['opcao'] == res)
                        
                        def calc_lucro(row):
                            if row['opcao'] == res and venc > 0:
                                return (row['valor']/venc*pote) - row['valor']
                            return -row['valor']
                        
                        df_ap['Lucro/Preju'] = df_ap.apply(calc_lucro, axis=1).apply(money)
                        st.dataframe(df_ap[['nome', 'Palpite', 'R$', 'Lucro/Preju']], hide_index=True)
                    else:
                        st.dataframe(df_ap[['nome', 'Palpite', 'R$']], hide_index=True)
                else:
                    st.write("Nenhuma aposta registrada ainda.")

            # Aba 2: Formulário (Só funciona se Admin + Aberto)
            with tab_apostar:
                if sou_admin:
                    if j['apostas_abertas'] and not j['finalizado']:
                        c_nm, c_vl, c_op, c_bt = st.columns([2, 1, 2, 1])
                        nm = c_nm.text_input("Nome", key=f"nm{i}")
                        vl = c_vl.number_input("R$", 5.0, 500.0, 10.0, key=f"vl{i}")
                        op = c_op.radio("Vencedor", [j['a'], "Empate", j['b']], key=f"op{i}", horizontal=True)
                        if c_bt.button("Enviar", key=f"send{i}"):
                            opt = "A" if op == j['a'] else "B" if op == j['b'] else "E"
                            st.session_state.jogos[i]['apostas'].append({"nome": nm, "valor": vl, "opcao": opt})
                            salvar_dados(st.session_state.jogos)
                            st.rerun()
                    else:
                        st.warning("Apostas encerradas para este jogo.")
                else:
                    st.info("Somente o Admin pode registrar novas apostas.")

# ==============================================================================
# 2. TABELA DE CLASSIFICAÇÃO
# ==============================================================================
elif aba == "Classificação":
    st.header("📊 Classificação")
    
    # Recarrega para garantir
    if not st.session_state.jogos:
        st.session_state.jogos, st.session_state.times = carregar_dados()

    tabela = {t: {"P":0, "J":0, "V":0, "E":0, "D":0, "GP":0, "GC":0, "SG":0} for t in st.session_state.times}
    
    for j in st.session_state.jogos:
        # Conta pontos se houver placar, independente do status 'finalizado'
        if j['ga'] is not None and j['gb'] is not None:
            a, b = j['a'], j['b']
            ga, gb = j['ga'], j['gb']
            
            if a in tabela:
                tabela[a]['J']+=1; tabela[a]['GP']+=ga; tabela[a]['GC']+=gb
            if b in tabela:
                tabela[b]['J']+=1; tabela[b]['GP']+=gb; tabela[b]['GC']+=ga
            
            if ga > gb:
                if a in tabela: tabela[a]['P']+=3; tabela[a]['V']+=1
                if b in tabela: tabela[b]['D']+=1
            elif gb > ga:
                if b in tabela: tabela[b]['P']+=3; tabela[b]['V']+=1
                if a in tabela: tabela[a]['D']+=1
            else:
                if a in tabela: tabela[a]['P']+=1; tabela[a]['E']+=1
                if b in tabela: tabela[b]['P']+=1; tabela[b]['E']+=1
    
    for t in tabela: tabela[t]['SG'] = tabela[t]['GP'] - tabela[t]['GC']
    
    if tabela:
        df = pd.DataFrame.from_dict(tabela, orient='index').sort_values(by=["P", "V", "SG"], ascending=False)
        st.dataframe(df, use_container_width=True)

# ==============================================================================
# 3. RANKING FINANCEIRO
# ==============================================================================
elif aba == "Ranking Financeiro":
    st.header("🤑 Quem está ganhando dinheiro?")
    
    # Recarrega para garantir
    if not st.session_state.jogos:
        st.session_state.jogos, st.session_state.times = carregar_dados()

    lucros = {}
    jogos_finalizados_count = 0
    
    for j in st.session_state.jogos:
        # Ranking só conta jogos FINALIZADOS (com resultado real)
        if j['finalizado'] and j['ga'] is not None:
            jogos_finalizados_count += 1
            res = "A" if j['ga'] > j['gb'] else "B" if j['gb'] > j['ga'] else "E"
            pote = sum(x['valor'] for x in j['apostas'])
            venc = sum(x['valor'] for x in j['apostas'] if x['opcao'] == res)
            
            for ap in j['apostas']:
                nome = ap['nome']
                val = ap['valor']
                lucros.setdefault(nome, {"Investido": 0.0, "Retorno": 0.0})
                
                lucros[nome]["Investido"] += val
                if ap['opcao'] == res and venc > 0:
                    lucros[nome]["Retorno"] += (val/venc*pote)
    
    if lucros:
        resumo = []
        for nome, dados in lucros.items():
            liq = dados["Retorno"] - dados["Investido"]
            resumo.append({
                "Apostador": nome,
                "Investido": money(dados["Investido"]),
                "Retorno": money(dados["Retorno"]),
                "Lucro Líquido": money(liq),
                "sort": liq
            })
        
        df_rank = pd.DataFrame(resumo).sort_values("sort", ascending=False).drop(columns="sort")
        st.dataframe(df_rank, use_container_width=True, hide_index=True)
    else:
        st.info("O Ranking aparecerá aqui assim que o primeiro jogo for finalizado pelo Admin.")
        if jogos_finalizados_count == 0:
            st.caption("(Atualmente nenhum jogo consta como finalizado na base de dados).")

# ==============================================================================
# 4. CONFIGURAÇÃO (ADMIN)
# ==============================================================================
elif aba == "Novo Torneio (Admin)":
    if sou_admin:
        st.header("⚠️ Resetar Campeonato")
        st.error("Isso apagará todos os dados atuais!")
        
        qtd = st.number_input("Número de Times", 2, 20, 4)
        nomes = [st.text_input(f"Time {i+1}", key=f"t{i}") for i in range(qtd)]
        
        if st.button("CRIAR NOVO CAMPEONATO"):
            ts = [n for n in nomes if n.strip()]
            if len(ts) >= 2:
                confrontos = list(itertools.combinations(ts, 2))
                random.shuffle(confrontos)
                novos = [{
                    "a": p[0], "b": p[1], 
                    "ga": None, "gb": None, 
                    "finalizado": False, 
                    "apostas_abertas": True, 
                    "apostas": []
                } for p in confrontos]
                salvar_dados(novos)
                st.session_state.jogos = novos
                st.session_state.times = ts
                st.success("Criado!")
                st.rerun()
    else:
        st.error("Área restrita.")
