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

# --- FUNÇÕES DE CONVERSÃO ROBUSTAS ---

def parse_bool(val):
    """Converte qualquer lixo do Sheets em Booleano Real"""
    v = str(val).strip().upper()
    return v in ["TRUE", "1", "VERDADEIRO", "T"]

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
                # AQUI ESTÁ A CORREÇÃO: Forçar a conversão de tipos na leitura
                fina = parse_bool(row.get('finalizado'))
                aber = parse_bool(row.get('apostas_abertas'))
                ga = row.get('ga')
                gb = row.get('gb')
                
                j = {
                    "a": str(row.get('a')), "b": str(row.get('b')),
                    "ga": int(float(ga)) if pd.notna(ga) and str(ga).strip() != "" else None,
                    "gb": int(float(gb)) if pd.notna(gb) and str(gb).strip() != "" else None,
                    "finalizado": fina, 
                    "apostas_abertas": aber,
                    "apostas": parse_apostas(row.get('apostas'))
                }
                jogos_lidos.append(j)
                times_lidos.add(j['a']); times_lidos.add(j['b'])
            return jogos_lidos, list(times_lidos)
    except: pass
    return [], []

def salvar_dados_nuvem(lista):
    df_save = pd.DataFrame(lista)
    # Garante que salve como STRING MAIÚSCULA para facilitar a leitura depois
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
senha = st.sidebar.text_input("Chave Admin", type="password")
sou_admin = (senha == "1234")

if st.sidebar.button("🔄 SINCRONIZAR TUDO"):
    st.session_state.jogos, st.session_state.times = carregar_dados_nuvem()
    st.rerun()

menu = st.sidebar.radio("Navegação", ["Jogos", "Classificação", "Ranking Apostas", "Novo Torneio"])

# --- INTERFACE JOGOS ---
if menu == "Jogos":
    st.header("⚽ Partidas")
    for i, j in enumerate(st.session_state.jogos):
        with st.container(border=True):
            # Layout do Placar
            c1, c2, c3 = st.columns([2, 1, 2])
            ga, gb = (j['ga'] if j['ga'] is not None else "-"), (j['gb'] if j['gb'] is not None else "-")
            c1.markdown(f"<h3 style='text-align:right;'>{j['a']}</h3>", unsafe_allow_html=True)
            c2.markdown(f"<h1 style='text-align:center; color:red;'>{ga} x {gb}</h1>", unsafe_allow_html=True)
            c3.markdown(f"<h3 style='text-align:left;'>{j['b']}</h3>", unsafe_allow_html=True)

            if sou_admin:
                col_adm = st.columns(2)
                if not j['finalizado']:
                    with col_adm[0].expander("⚙️ LANÇAR PLACAR"):
                        l1, l2 = st.columns(2)
                        v_ga = l1.number_input(f"Gols {j['a']}", 0, 20, key=f"ga_{i}")
                        v_gb = l2.number_input(f"Gols {j['b']}", 0, 20, key=f"gb_{i}")
                        if st.button("FINALIZAR JOGO", key=f"btn_{i}"):
                            st.session_state.jogos[i].update({'ga': int(v_ga), 'gb': int(v_gb), 'finalizado': True, 'apostas_abertas': False})
                            salvar_dados_nuvem(st.session_state.jogos)
                            st.rerun()
                else:
                    if col_adm[0].button("🔄 REABRIR JOGO", key=f"reopen_{i}"):
                        st.session_state.jogos[i].update({'finalizado': False, 'apostas_abertas': True})
                        salvar_dados_nuvem(st.session_state.jogos)
                        st.rerun()

            with st.expander("💰 APOSTAS"):
                col_ap, col_lst = st.columns([1, 2])
                with col_ap:
                    if sou_admin and j['apostas_abertas']:
                        n = st.text_input("Nome", key=f"n_{i}")
                        v = st.number_input("Valor R$", 1.0, 1000.0, 10.0, key=f"v_{i}")
                        o = st.radio("Palpite", [j['a'], "Empate", j['b']], key=f"o_{i}")
                        if st.button("Confirmar", key=f"b_{i}"):
                            opt = "A" if o == j['a'] else "B" if o == j['b'] else "E"
                            st.session_state.jogos[i]['apostas'].append({"nome": n, "valor": v, "opcao": opt})
                            salvar_dados_nuvem(st.session_state.jogos)
                            st.rerun()
                    else: st.write("Apostas Encerradas.")
                with col_lst:
                    if j['apostas']:
                        df_ap = pd.DataFrame(j['apostas'])
                        df_ap['Palpite'] = df_ap['opcao'].map({"A": j['a'], "B": j['b'], "E": "Empate"})
                        st.dataframe(df_ap[['nome', 'Palpite', 'valor']], hide_index=True)

# --- RANKING (AQUI O CÁLCULO ESTÁ BLINDADO) ---
elif menu == "Ranking Apostas":
    st.header("💰 Ranking de Lucros")
    
    # Recalcula do zero toda vez que entra na aba
    ranking = {}
    for j in st.session_state.jogos:
        # Verifica se o jogo está finalizado (usando a conversão segura)
        if j['finalizado'] == True and j['ga'] is not None:
            res = "A" if j['ga'] > j['gb'] else "B" if j['gb'] > j['ga'] else "E"
            pote = sum(a['valor'] for a in j['apostas'])
            venc = sum(a['valor'] for a in j['apostas'] if a['opcao'] == res)
            
            for a in j['apostas']:
                nome = a['nome']
                ranking.setdefault(nome, {"Investido": 0.0, "Ganho": 0.0})
                ranking[nome]["Investido"] += a['valor']
                if a['opcao'] == res and venc > 0:
                    ranking[nome]["Ganho"] += (a['valor']/venc*pote)
    
    if ranking:
        dados = []
        for k, v in ranking.items():
            saldo = v['Ganho'] - v['Investido']
            dados.append({"Apostador": k, "Saldo Líquido": saldo})
        
        df_r = pd.DataFrame(dados).sort_values("Saldo Líquido", ascending=False)
        
        # Formatação Visual Direta
        st.write("### Tabela de Lucros/Prejuízos")
        st.dataframe(df_r.style.format({"Saldo Líquido": "R$ {:.2f}"}), use_container_width=True)
    else:
        st.info("Nenhum jogo finalizado no sistema. Finalize um jogo como Admin para gerar o ranking.")

# --- DEMAIS ABAS ---
elif menu == "Classificação":
    st.header("📊 Classificação")
    stats = {t: {"P":0,"J":0,"V":0,"E":0,"D":0,"GP":0,"GC":0,"SG":0} for t in st.session_state.times}
    for j in st.session_state.jogos:
        if j['ga'] is not None and j['gb'] is not None:
            a, b, ga, gb = j['a'], j['b'], j['ga'], j['gb']
            stats[a]["J"]+=1; stats[b]["J"]+=1; stats[a]["GP"]+=ga; stats[a]["GC"]+=gb; stats[b]["GP"]+=gb; stats[b]["GC"]+=ga
            if ga > gb: stats[a]["P"]+=3; stats[a]["V"]+=1; stats[b]["D"]+=1
            elif gb > ga: stats[b]["P"]+=3; stats[b]["V"]+=1; stats[a]["D"]+=1
            else: stats[a]["P"]+=1; stats[b]["P"]+=1; stats[a]["E"]+=1; stats[b]["E"]+=1
    for t in stats: stats[t]["SG"] = stats[t]["GP"] - stats[t]["GC"]
    st.table(pd.DataFrame.from_dict(stats, orient='index').sort_values(["P", "V", "SG"], ascending=False))

elif menu == "Novo Torneio":
    if sou_admin:
        st.header("🏆 Reiniciar Campeonato")
        qtd = st.number_input("Qtd Times", 2, 10, 4)
        nms = [st.text_input(f"Time {i+1}", key=f"tm_{i}") for i in range(qtd)]
        if st.button("LIMPAR PLANILHA E CRIAR NOVOS JOGOS"):
            times = [n for n in nms if n.strip()]
            if len(times) >= 2:
                pares = list(itertools.combinations(times, 2))
                random.shuffle(pares)
                novos = [{"a": p[0], "b": p[1], "ga": None, "gb": None, "finalizado": False, "apostas_abertas": True, "apostas": []} for p in pares]
                salvar_dados_nuvem(novos)
                st.session_state.jogos = novos; st.session_state.times = times
                st.rerun()
