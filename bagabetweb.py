import streamlit as st
import pandas as pd
import itertools
import random
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="BAGA BET PRO", layout="wide", page_icon="⚽")
conn = st.connection("gsheets", type=GSheetsConnection)

def money(v):
    try: return f"R$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except: return "R$ 0,00"

# --- TRATAMENTO DE DADOS (O SEGREDO DA ESTABILIDADE) ---

def parse_apostas(txt):
    lista = []
    txt = str(txt).strip()
    if txt in ["nan", "None", ""]: return lista
    try:
        for item in txt.split("|"):
            p = item.split(":")
            if len(p) == 3:
                lista.append({"nome": p[0], "valor": float(p[1]), "opcao": p[2].upper()})
    except: pass
    return lista

def carregar_dados_nuvem():
    try:
        df = conn.read(ttl=0)
        if df is not None and not df.empty:
            df = df.dropna(subset=['a', 'b'])
            jogos_lidos = []
            times_lidos = set()
            for row in df.to_dict('records'):
                # Convertemos tudo para STRING e depois comparamos para evitar erro de tipo
                fina_raw = str(row.get('finalizado', 'FALSE')).upper().strip()
                aber_raw = str(row.get('apostas_abertas', 'TRUE')).upper().strip()
                
                ga = row.get('ga')
                gb = row.get('gb')
                
                j = {
                    "a": str(row.get('a')), 
                    "b": str(row.get('b')),
                    "ga": int(float(ga)) if pd.notna(ga) and str(ga).strip() != "" else None,
                    "gb": int(float(gb)) if pd.notna(gb) and str(gb).strip() != "" else None,
                    "finalizado": (fina_raw == "TRUE"), 
                    "apostas_abertas": (aber_raw == "TRUE"),
                    "apostas": parse_apostas(row.get('apostas'))
                }
                jogos_lidos.append(j)
                times_lidos.add(j['a']); times_lidos.add(j['b'])
            return jogos_lidos, list(times_lidos)
    except Exception as e:
        st.error(f"Erro na leitura: {e}")
    return [], []

def salvar_dados_nuvem(lista):
    df_save = pd.DataFrame(lista)
    # Serializa para garantir que o Sheets receba TEXTO puro
    df_save['apostas'] = df_save['apostas'].apply(lambda x: "|".join([f"{a['nome']}:{a['valor']}:{a['opcao']}" for a in x]) if x else "")
    df_save['finalizado'] = df_save['finalizado'].apply(lambda x: "TRUE" if x else "FALSE")
    df_save['apostas_abertas'] = df_save['apostas_abertas'].apply(lambda x: "TRUE" if x else "FALSE")
    conn.update(data=df_save)
    st.cache_data.clear()

# --- INICIALIZAÇÃO ---
if 'jogos' not in st.session_state:
    st.session_state.jogos, st.session_state.times = carregar_dados_nuvem()

# --- SIDEBAR ---
st.sidebar.title("BAGA BET ⚽")
senha = st.sidebar.text_input("Senha Admin", type="password")
sou_admin = (senha == "1234")

if st.sidebar.button("🔄 ATUALIZAR APP (FORÇAR)"):
    st.session_state.jogos, st.session_state.times = carregar_dados_nuvem()
    st.rerun()

menu = st.sidebar.radio("Navegação", ["Jogos e Apostas", "Ranking Financeiro", "Tabela Classificação", "Painel Admin"])

# --- 1. JOGOS E APOSTAS ---
if menu == "Jogos e Apostas":
    st.header("⚽ Partidas")
    for i, j in enumerate(st.session_state.jogos):
        with st.container(border=True):
            c1, c2, c3 = st.columns([2, 1, 2])
            ga_v = j['ga'] if j['ga'] is not None else "-"
            gb_v = j['gb'] if j['gb'] is not None else "-"
            
            c1.markdown(f"<h3 style='text-align:right;'>{j['a']}</h3>", unsafe_allow_html=True)
            c2.markdown(f"<h1 style='text-align:center; color:red;'>{ga_v} x {gb_v}</h1>", unsafe_allow_html=True)
            c3.markdown(f"<h3 style='text-align:left;'>{j['b']}</h3>", unsafe_allow_html=True)

            # Botões de controle (Somente Admin)
            if sou_admin:
                col_btn1, col_btn2 = st.columns(2)
                if not j['finalizado']:
                    with col_btn1.expander("Encerrar Jogo"):
                        res_a = st.number_input(f"Gols {j['a']}", 0, 20, key=f"ga_{i}")
                        res_b = st.number_input(f"Gols {j['b']}", 0, 20, key=f"gb_{i}")
                        if st.button("Salvar Resultado", key=f"sv_{i}"):
                            st.session_state.jogos[i].update({'ga': int(res_a), 'gb': int(res_b), 'finalizado': True, 'apostas_abertas': False})
                            salvar_dados_nuvem(st.session_state.jogos)
                            st.rerun()
                else:
                    if col_btn1.button("🔄 Reabrir Jogo", key=f"re_{i}"):
                        st.session_state.jogos[i].update({'finalizado': False, 'apostas_abertas': True})
                        salvar_dados_nuvem(st.session_state.jogos)
                        st.rerun()

            # Área de Apostas (Tabs para organizar)
            tab_ver, tab_add = st.tabs(["📋 Ver Apostas", "💰 Nova Aposta"])
            
            with tab_ver:
                if j['apostas']:
                    df_exibir = pd.DataFrame(j['apostas'])
                    df_exibir['Palpite'] = df_exibir['opcao'].map({"A": j['a'], "B": j['b'], "E": "Empate"})
                    st.table(df_exibir[['nome', 'Palpite', 'valor']])
                else:
                    st.write("Nenhuma aposta registrada.")

            with tab_add:
                if sou_admin and j['apostas_abertas']:
                    n_ap = st.text_input("Nome do Apostador", key=f"n_{i}")
                    v_ap = st.number_input("Valor (R$)", 5.0, 1000.0, 10.0, key=f"v_{i}")
                    o_ap = st.radio("Palpite", [j['a'], "Empate", j['b']], key=f"o_{i}", horizontal=True)
                    if st.button("Registrar Aposta", key=f"bt_{i}"):
                        cod = "A" if o_ap == j['a'] else "B" if o_ap == j['b'] else "E"
                        st.session_state.jogos[i]['apostas'].append({"nome": n_ap, "valor": v_ap, "opcao": cod})
                        salvar_dados_nuvem(st.session_state.jogos)
                        st.rerun()
                else:
                    st.info("Apostas encerradas para este jogo (ou você não é Admin).")

# --- 2. RANKING FINANCEIRO (BLINDADO) ---
elif menu == "Ranking Financeiro":
    st.header("🤑 Ranking de Apostadores")
    ranking = {}
    
    # Garantimos que ele calcule com os dados mais frescos
    for j in st.session_state.jogos:
        if j['finalizado'] and j['ga'] is not None:
            # Determina o resultado real
            if j['ga'] > j['gb']: res_real = "A"
            elif j['gb'] > j['ga']: res_real = "B"
            else: res_real = "E"
            
            pote_total = sum(a['valor'] for a in j['apostas'])
            vencedores_valor = sum(a['valor'] for a in j['apostas'] if a['opcao'] == res_real)
            
            for a in j['apostas']:
                nome = a['nome']
                ranking.setdefault(nome, {"investido": 0.0, "retorno": 0.0})
                ranking[nome]["investido"] += a['valor']
                
                if a['opcao'] == res_real and vencedores_valor > 0:
                    ranking[nome]["retorno"] += (a['valor'] / vencedores_valor) * pote_total

    if ranking:
        dados_rank = []
        for nome, valores in ranking.items():
            lucro = valores['retorno'] - valores['investido']
            dados_rank.append({"Nome": nome, "Investido": valores['investido'], "Lucro Líquido": lucro})
        
        df_rank = pd.DataFrame(dados_rank).sort_values("Lucro Líquido", ascending=False)
        st.dataframe(df_rank.style.format({"Investido": "R$ {:.2f}", "Lucro Líquido": "R$ {:.2f}"}), use_container_width=True)
    else:
        st.info("O ranking será exibido quando houver jogos finalizados com apostas.")

# --- 3. TABELA CLASSIFICAÇÃO ---
elif menu == "Tabela Classificação":
    st.header("📊 Classificação do Torneio")
    cl = {t: {"P":0,"J":0,"V":0,"E":0,"D":0,"GP":0,"GC":0,"SG":0} for t in st.session_state.times}
    for j in st.session_state.jogos:
        if j['ga'] is not None and j['gb'] is not None:
            a, b, ga, gb = j['a'], j['b'], j['ga'], j['gb']
            cl[a]["J"]+=1; cl[b]["J"]+=1; cl[a]["GP"]+=ga; cl[a]["GC"]+=gb; cl[b]["GP"]+=gb; cl[b]["GC"]+=ga
            if ga > gb: cl[a]["P"]+=3; cl[a]["V"]+=1; cl[b]["D"]+=1
            elif gb > ga: cl[b]["P"]+=3; cl[b]["V"]+=1; cl[a]["D"]+=1
            else: cl[a]["P"]+=1; cl[b]["P"]+=1; cl[a]["E"]+=1; cl[b]["E"]+=1
    for t in cl: cl[t]["SG"] = cl[t]["GP"] - cl[t]["GC"]
    df_cl = pd.DataFrame.from_dict(cl, orient='index').sort_values(["P", "V", "SG"], ascending=False)
    st.table(df_cl)

# --- 4. PAINEL ADMIN ---
elif menu == "Painel Admin":
    if sou_admin:
        st.subheader("Configurar Novo Torneio")
        times_input = st.text_area("Lista de Times (um por linha)")
        if st.button("Resetar e Criar Torneio"):
            lista_t = [t.strip() for t in times_input.split("\n") if t.strip()]
            if len(lista_t) >= 2:
                comb = list(itertools.combinations(lista_t, 2))
                random.shuffle(comb)
                novos_j = [{"a": c[0], "b": c[1], "ga": None, "gb": None, "finalizado": False, "apostas_abertas": True, "apostas": []} for c in comb]
                salvar_dados_nuvem(novos_j)
                st.session_state.jogos = novos_j; st.session_state.times = lista_t
                st.rerun()
    else:
        st.error("Acesso restrito.")
