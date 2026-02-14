import streamlit as st
import pandas as pd
import itertools
import random
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="BAGA BET ⚽", layout="wide")
conn = st.connection("gsheets", type=GSheetsConnection)

def money(v):
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# --- BUSCA DE DADOS ---
def buscar_dados():
    try:
        # ttl=0 força a leitura do Google Sheets sem cache
        df = conn.read(ttl=0)
        if df is not None and not df.empty:
            df = df.dropna(subset=['a', 'b'])
            lista = df.to_dict('records')
            for j in lista:
                # Recuperar Apostas
                j['apostas'] = []
                txt = str(j.get('apostas', ""))
                if txt and txt not in ["nan", "None", ""]:
                    for item in txt.split("|"):
                        p = item.split(":")
                        if len(p) == 3:
                            j['apostas'].append({"nome": p[0], "valor": float(p[1]), "opcao": p[2]})
                
                # Tratar Gols como números (essencial para a tabela)
                for col in ['ga', 'gb']:
                    val = str(j.get(col, ""))
                    # Se for número (mesmo que seja "1.0"), converte
                    if val.replace('.','',1).strip().isdigit():
                        j[col] = int(float(val))
                    else:
                        j[col] = None
                
                # Tratar Status
                status = str(j.get('finalizado', "")).upper()
                j['finalizado'] = status in ["TRUE", "1", "VERDADEIRO", "T"]
            return lista
    except:
        return []
    return []

def salvar_na_nuvem(dados):
    df_save = pd.DataFrame(dados)
    cols = ['a', 'b', 'ga', 'gb', 'finalizado', 'apostas_abertas', 'apostas']
    for c in cols:
        if c not in df_save.columns: df_save[c] = None
    
    df_save['apostas'] = df_save['apostas'].apply(lambda x: "|".join([f"{a['nome']}:{a['valor']}:{a['opcao']}" for a in x]) if isinstance(x, list) else "")
    conn.update(data=df_save[cols])
    st.cache_data.clear()

# --- INICIALIZAÇÃO ---
if 'jogos' not in st.session_state:
    st.session_state.jogos = buscar_dados()

# --- INTERFACE ---
st.sidebar.title("BAGA BET ⚽")
senha = st.sidebar.text_input("Senha Admin", type="password")
sou_admin = (senha == "1234")

if st.sidebar.button("🔄 FORÇAR ATUALIZAÇÃO"):
    st.session_state.jogos = buscar_dados()
    st.rerun()

aba = st.sidebar.radio("Navegação", ["Jogos", "Classificação", "Ranking"])

# --- NOVO TORNEIO ---
if aba == "Jogos" and sou_admin:
    with st.sidebar.expander("🏆 NOVO TORNEIO"):
        qtd = st.number_input("Times", 2, 8, 4)
        nomes = [st.text_input(f"Time {i+1}", key=f"t{i}") for i in range(int(qtd))]
        if st.button("GERAR CAMPEONATO"):
            times_lista = [n for n in nomes if n]
            if len(times_lista) >= 2:
                confrontos = list(itertools.combinations(times_lista, 2))
                random.shuffle(confrontos)
                novos = [{"a": p[0], "b": p[1], "ga": None, "gb": None, "finalizado": False, "apostas_abertas": True, "apostas": []} for p in confrontos]
                st.session_state.jogos = novos
                salvar_na_nuvem(novos)
                st.rerun()

# --- TELA DE JOGOS ---
if aba == "Jogos":
    st.header("⚽ Partidas")
    if not st.session_state.jogos:
        st.info("Crie o torneio no menu lateral.")
    else:
        for i, j in enumerate(st.session_state.jogos):
            with st.container(border=True):
                c1, c2, c3 = st.columns([2, 1, 2])
                ga = j['ga'] if j['ga'] is not None else "-"
                gb = j['gb'] if j['gb'] is not None else "-"
                c1.markdown(f"<h3 style='text-align:right;'>{j['a']}</h3>", unsafe_allow_html=True)
                c2.markdown(f"<h1 style='text-align:center;'>{ga} x {gb}</h1>", unsafe_allow_html=True)
                c3.markdown(f"<h3 style='text-align:left;'>{j['b']}</h3>", unsafe_allow_html=True)

                if sou_admin and not j['finalizado']:
                    with st.expander("⚙️ LANÇAR PLACAR"):
                        l1, l2 = st.columns(2)
                        v_ga = l1.number_input(f"Gols {j['a']}", 0, 20, key=f"ga_{i}")
                        v_gb = l2.number_input(f"Gols {j['b']}", 0, 20, key=f"gb_{i}")
                        if st.button("SALVAR RESULTADO", key=f"btn_{i}"):
                            st.session_state.jogos[i].update({'ga': int(v_ga), 'gb': int(v_gb), 'finalizado': True, 'apostas_abertas': False})
                            salvar_na_nuvem(st.session_state.jogos)
                            st.rerun()

# --- TELA DE CLASSIFICAÇÃO (LÓGICA BLINDADA) ---
elif aba == "Classificação":
    st.header("📊 Tabela de Classificação")
    df_nuvem = buscar_dados() # Lê o Sheets agora
    
    if not df_nuvem:
        st.error("Não foi possível ler os dados da nuvem.")
    else:
        times = sorted(list(set([j['a'] for j in df_nuvem] + [j['b'] for j in df_nuvem])))
        stats = {t: {"P":0,"V":0,"E":0,"D":0,"GP":0,"GC":0,"SG":0} for t in times}
        
        for j in df_nuvem:
            # NOVIDADE: Calcula se tiver gols, independente do campo 'finalizado'
            if j['ga'] is not None and j['gb'] is not None:
                a, b, ga, gb = j['a'], j['b'], int(j['ga']), int(j['gb'])
                stats[a]['GP'] += ga; stats[a]['GC'] += gb
                stats[b]['GP'] += gb; stats[b]['GC'] += ga
                if ga > gb: 
                    stats[a]['P'] += 3; stats[a]['V'] += 1; stats[b]['D'] += 1
                elif gb > ga: 
                    stats[b]['P'] += 3; stats[b]['V'] += 1; stats[a]['D'] += 1
                else: 
                    stats[a]['P'] += 1; stats[b]['P'] += 1; stats[a]['E'] += 1; stats[b]['E'] += 1
        
        for t in stats: stats[t]["SG"] = stats[t]["GP"] - stats[t]["GC"]
        
        df_tab = pd.DataFrame.from_dict(stats, orient='index').sort_values(by=["P", "V", "SG"], ascending=False)
        st.table(df_tab)

# --- RANKING ---
elif aba == "Ranking":
    st.header("💰 Saldo das Apostas")
    df_nuvem = buscar_dados()
    lucros = {}
    for j in df_nuvem:
        if j['ga'] is not None and j['gb'] is not None:
            res = "A" if j['ga'] > j['gb'] else "B" if j['ga'] < j['gb'] else "E"
            pote = sum(a['valor'] for a in j['apostas'])
            venc = sum(a['valor'] for a in j['apostas'] if a['opcao'] == res)
            for a in j['apostas']:
                lucros.setdefault(a['nome'], 0)
                if a['opcao'] == res and venc > 0:
                    lucros[a['nome']] += (a['valor']/venc*pote) - a['valor']
                else:
                    lucros[a['nome']] -= a['valor']
    if lucros:
        df_rk = pd.DataFrame([{"Nome": k, "Saldo": money(v), "val": v} for k, v in lucros.items()])
        st.table(df_rk.sort_values("val", ascending=False).drop(columns="val"))
