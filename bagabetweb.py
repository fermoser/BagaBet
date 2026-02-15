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

def safe_int(val):
    try:
        if pd.isna(val) or str(val).strip() == "": return None
        return int(float(str(val).replace(",", ".")))
    except: return None

def safe_bool(val, padrao=False):
    if pd.isna(val) or str(val).strip() == "": return padrao
    return str(val).upper().strip() in ["TRUE", "T", "VERDADEIRO", "1", "YES", "SIM"]

# --- O CORAÇÃO DO PROBLEMA: PARSE DE APOSTAS ---
def parse_apostas(apostas_str):
    lista = []
    texto = str(apostas_str).strip()
    if not texto or texto in ["nan", "None", ""]:
        return lista
    
    try:
        # Divide as apostas (Joao:10:A | Maria:20:B)
        blocos = texto.split("|")
        for bloco in blocos:
            if not bloco.strip(): continue
            parts = bloco.split(":")
            if len(parts) == 3:
                lista.append({
                    "nome": parts[0].strip(),
                    "valor": float(parts[1].strip()),
                    "opcao": parts[2].strip().upper() # A, B ou E
                })
    except Exception as e:
        print(f"Erro no parse de uma aposta: {e}")
    return lista

# --- NUVEM ---
def carregar_dados():
    try:
        df = conn.read(ttl=0)
        if df is not None and not df.empty:
            df = df.dropna(subset=['a', 'b'])
            raw = df.to_dict('records')
            
            dados_limpos = []
            todos_times = set()

            for row in raw:
                # Resolve o bug das apostas fechadas ao abrir
                fin = safe_bool(row.get('finalizado'), False)
                aberto_padrao = not fin
                
                jogo = {
                    "a": str(row.get('a', '')),
                    "b": str(row.get('b', '')),
                    "ga": safe_int(row.get('ga')),
                    "gb": safe_int(row.get('gb')),
                    "finalizado": fin,
                    "apostas_abertas": safe_bool(row.get('apostas_abertas'), aberto_padrao),
                    "apostas": parse_apostas(row.get('apostas'))
                }
                dados_limpos.append(jogo)
                todos_times.add(jogo['a'])
                todos_times.add(jogo['b'])
            
            return dados_limpos, list(todos_times)
    except: pass
    return [], []

def salvar_dados(lista):
    if not lista: return
    df = pd.DataFrame(lista)
    # Garante que as apostas virem STRING para o Sheets
    df['apostas'] = df['apostas'].apply(
        lambda x: "|".join([f"{a['nome']}:{a['valor']}:{a['opcao']}" for a in x]) if isinstance(x, list) and x else ""
    )
    cols = ['a', 'b', 'ga', 'gb', 'finalizado', 'apostas_abertas', 'apostas']
    conn.update(data=df[cols])
    st.cache_data.clear()

# --- INICIALIZAÇÃO DO APP ---
# Aqui forçamos a leitura toda vez que o script roda do zero (F5 ou Abrir)
if 'jogos' not in st.session_state or not st.session_state.jogos:
    st.session_state.jogos, st.session_state.times = carregar_dados()

# --- SIDEBAR ---
st.sidebar.title("BAGA BET ⚽")
senha = st.sidebar.text_input("Senha Admin", type="password")
sou_admin = (senha == "1234")

if st.sidebar.button("🔄 ATUALIZAR AGORA"):
    st.session_state.jogos, st.session_state.times = carregar_dados()
    st.rerun()

aba = st.sidebar.radio("Menu", ["Jogos e Apostas", "Classificação", "Ranking Financeiro", "Novo Torneio (Admin)"])

# --- ABA JOGOS ---
if aba == "Jogos e Apostas":
    st.header("⚽ Partidas")
    for i, j in enumerate(st.session_state.jogos):
        with st.container(border=True):
            c1, c2, c3 = st.columns([2, 1, 2])
            ga_v, gb_v = (j['ga'] if j['ga'] is not None else ""), (j['gb'] if j['gb'] is not None else "")
            c1.markdown(f"<h3 style='text-align:right'>{j['a']}</h3>", unsafe_allow_html=True)
            c2.markdown(f"<h2 style='text-align:center; color:red'>{ga_v} x {gb_v}</h2>", unsafe_allow_html=True)
            c3.markdown(f"<h3 style='text-align:left'>{j['b']}</h3>", unsafe_allow_html=True)

            # ADMIN LANÇAR RESULTADO
            if sou_admin and not j['finalizado']:
                with st.expander("⚙️ LANÇAR RESULTADO"):
                    l1, l2, l3 = st.columns([1,1,2])
                    v_ga = l1.number_input(f"Gols {j['a']}", 0, 20, key=f"ga{i}")
                    v_gb = l2.number_input(f"Gols {j['b']}", 0, 20, key=f"gb{i}")
                    if l3.button("SALVAR", key=f"sv{i}"):
                        st.session_state.jogos[i].update({'ga': int(v_ga), 'gb': int(v_gb), 'finalizado': True, 'apostas_abertas': False})
                        salvar_dados(st.session_state.jogos)
                        st.rerun()
            
            # APOSTAS
            t1, t2 = st.tabs(["📋 Apostas Feitas", "💰 Apostar"])
            with t1:
                if j['apostas']:
                    df_ap = pd.DataFrame(j['apostas'])
                    df_ap['Palpite'] = df_ap['opcao'].map({"A": j['a'], "B": j['b'], "E": "Empate"})
                    st.table(df_ap[['nome', 'Palpite', 'valor']])
                else: st.write("Sem apostas.")
            with t2:
                if sou_admin and j['apostas_abertas']:
                    n_ap = st.text_input("Nome", key=f"n{i}")
                    v_ap = st.number_input("Valor", 5.0, 500.0, 10.0, key=f"v{i}")
                    o_ap = st.radio("Lado", [j['a'], "Empate", j['b']], key=f"o{i}")
                    if st.button("Confirmar", key=f"bt{i}"):
                        cod = "A" if o_ap == j['a'] else "B" if o_ap == j['b'] else "E"
                        st.session_state.jogos[i]['apostas'].append({"nome": n_ap, "valor": v_ap, "opcao": cod})
                        salvar_dados(st.session_state.jogos)
                        st.rerun()
                else: st.info("Apostas fechadas ou modo visitante.")

# --- ABA CLASSIFICAÇÃO ---
elif aba == "Classificação":
    st.header("📊 Classificação")
    resumo = {t: {"P":0,"J":0,"V":0,"E":0,"D":0,"GP":0,"GC":0,"SG":0} for t in st.session_state.times}
    for j in st.session_state.jogos:
        if j['ga'] is not None and j['gb'] is not None:
            a, b, ga, gb = j['a'], j['b'], j['ga'], j['gb']
            resumo[a]['J']+=1; resumo[b]['J']+=1; resumo[a]['GP']+=ga; resumo[a]['GC']+=gb; resumo[b]['GP']+=gb; resumo[b]['GC']+=ga
            if ga > gb: resumo[a]['P']+=3; resumo[a]['V']+=1; resumo[b]['D']+=1
            elif gb > ga: resumo[b]['P']+=3; resumo[b]['V']+=1; resumo[a]['D']+=1
            else: resumo[a]['P']+=1; resumo[b]['P']+=1; resumo[a]['E']+=1; resumo[b]['E']+=1
    for t in resumo: resumo[t]['SG'] = resumo[t]['GP'] - resumo[t]['GC']
    df = pd.DataFrame.from_dict(resumo, orient='index').sort_values(["P", "V", "SG"], ascending=False)
    st.dataframe(df, use_container_width=True)

# --- ABA RANKING (REFEITA PARA SEMPRE LER DA SESSÃO ATUALIZADA) ---
elif aba == "Ranking Financeiro":
    st.header("🤑 Ranking Financeiro")
    ranking = {}
    jogos_processados = 0

    for j in st.session_state.jogos:
        # Só entra no ranking se o jogo acabou E tem apostas
        if j['finalizado'] and j['ga'] is not None and j['apostas']:
            jogos_processados += 1
            res = "A" if j['ga'] > j['gb'] else "B" if j['gb'] > j['ga'] else "E"
            pote = sum(x['valor'] for x in j['apostas'])
            venc = sum(x['valor'] for x in j['apostas'] if x['opcao'] == res)
            
            for ap in j['apostas']:
                n = ap['nome']
                ranking.setdefault(n, {"Investido": 0.0, "Retorno": 0.0})
                ranking[n]["Investido"] += ap['valor']
                if ap['opcao'] == res and venc > 0:
                    ranking[n]["Retorno"] += (ap['valor']/venc*pote)
    
    if ranking:
        dados = []
        for nome, d in ranking.items():
            liq = d["Retorno"] - d["Investido"]
            dados.append({"Nome": nome, "Investido": money(d['Investido']), "Retorno": money(d['Retorno']), "Saldo": money(liq), "val": liq})
        df_r = pd.DataFrame(dados).sort_values("val", ascending=False).drop(columns="val")
        st.dataframe(df_r, use_container_width=True, hide_index=True)
    else:
        st.info("O Ranking está vazio. Verifique se existem jogos FINALIZADOS com apostas registradas.")

# --- ABA NOVO TORNEIO ---
elif aba == "Novo Torneio (Admin)":
    if sou_admin:
        st.header("⚠️ Novo Torneio")
        qtd = st.number_input("Times", 2, 20, 4)
        nms = [st.text_input(f"Time {i+1}", key=f"tm{i}") for i in range(qtd)]
        if st.button("RESETAR E CRIAR"):
            ts = [n for n in nms if n.strip()]
            if len(ts) >= 2:
                confs = list(itertools.combinations(ts, 2))
                random.shuffle(confs)
                novos = [{"a": p[0], "b": p[1], "ga": None, "gb": None, "finalizado": False, "apostas_abertas": True, "apostas": []} for p in confs]
                salvar_dados(novos)
                st.session_state.jogos = novos
                st.session_state.times = ts
                st.rerun()
    else: st.error("Área restrita.")
