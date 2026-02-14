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

# --- FUNÇÕES DE DADOS (VERSÃO SIMPLES) ---
def carregar():
    try:
        # Forçamos a leitura bruta sem cache
        df = conn.read(ttl=0)
        if df is not None and not df.empty:
            # Remove qualquer lixo ou coluna fantasma
            df = df[['a', 'b', 'ga', 'gb', 'finalizado', 'apostas_abertas', 'apostas']].dropna(subset=['a', 'b'])
            jogos = df.to_dict('records')
            for j in jogos:
                # Recuperar apostas (formato texto seguro)
                j['apostas'] = []
                txt = str(j.get('apostas', ""))
                if txt and txt not in ["nan", "None", ""]:
                    for item in txt.split("|"):
                        p = item.split(":")
                        if len(p) == 3:
                            j['apostas'].append({"nome": p[0], "valor": float(p[1]), "opcao": p[2]})
                
                # Forçar gols para número puro
                j['ga'] = int(float(j['ga'])) if str(j.get('ga')) not in ["nan", "None", ""] else None
                j['gb'] = int(float(j['gb'])) if str(j.get('gb')) not in ["nan", "None", ""] else None
                j['finalizado'] = str(j.get('finalizado')) == "True"
                j['apostas_abertas'] = str(j.get('apostas_abertas', "True")) == "True"
            return jogos
    except:
        pass
    return []

def salvar(lista_jogos):
    df_save = pd.DataFrame(lista_jogos)
    # Converte apostas para texto antes de subir
    df_save['apostas'] = df_save['apostas'].apply(lambda x: "|".join([f"{a['nome']}:{a['valor']}:{a['opcao']}" for a in x]) if isinstance(x, list) else "")
    conn.update(data=df_save)
    st.cache_data.clear()

# --- CARREGAMENTO ---
if 'jogos' not in st.session_state:
    st.session_state.jogos = carregar()

# --- INTERFACE ---
st.sidebar.title("BAGA BET ⚽")
admin_key = st.sidebar.text_input("Senha Admin", type="password")
sou_admin = (admin_key == "1234")

if st.sidebar.button("🔄 ATUALIZAR TUDO"):
    st.session_state.jogos = carregar()
    st.rerun()

menu = st.sidebar.radio("Menu", ["Jogos", "Classificação", "Ranking"])

# --- NOVO TORNEIO ---
if menu == "Jogos" and sou_admin:
    with st.sidebar.expander("🛠️ CRIAR NOVO TORNEIO"):
        qtd = st.number_input("Qtd Times", 2, 10, 4)
        nomes = [st.text_input(f"Time {i+1}", key=f"t{i}") for i in range(int(qtd))]
        if st.button("GERAR"):
            ts = [n for n in nomes if n]
            if len(ts) >= 2:
                ps = list(itertools.combinations(ts, 2))
                random.shuffle(ps)
                novos_jogos = [{"a": p[0], "b": p[1], "ga": None, "gb": None, "finalizado": False, "apostas_abertas": True, "apostas": []} for p in ps]
                st.session_state.jogos = novos_jogos
                salvar(novos_jogos)
                st.rerun()

# --- TELAS ---
if menu == "Jogos":
    st.header("⚽ Partidas")
    if not st.session_state.jogos:
        st.info("Crie um torneio na lateral.")
    else:
        for i, j in enumerate(st.session_state.jogos):
            with st.container(border=True):
                # Placar Visual
                c1, c2, c3 = st.columns([2, 1, 2])
                ga_ex = j['ga'] if j['ga'] is not None else "-"
                gb_ex = j['gb'] if j['gb'] is not None else "-"
                c1.markdown(f"<h3 style='text-align:right;'>{j['a']}</h3>", unsafe_allow_html=True)
                c2.markdown(f"<h1 style='text-align:center; color:red;'>{ga_ex} x {gb_ex}</h1>", unsafe_allow_html=True)
                c3.markdown(f"<h3 style='text-align:left;'>{j['b']}</h3>", unsafe_allow_html=True)

                # Admin - Lançar Gols (Expandido só para Admin)
                if sou_admin and not j['finalizado']:
                    with st.expander("⚙️ LANÇAR RESULTADO (ADMIN)"):
                        l1, l2, l3 = st.columns(3)
                        v_ga = l1.number_input(f"Gols {j['a']}", 0, 20, key=f"ga{i}")
                        v_gb = l2.number_input(f"Gols {j['b']}", 0, 20, key=f"gb{i}")
                        if l3.button("SALVAR", key=f"sv{i}"):
                            st.session_state.jogos[i]['ga'] = int(v_ga)
                            st.session_state.jogos[i]['gb'] = int(v_gb)
                            st.session_state.jogos[i]['finalizado'] = True
                            st.session_state.jogos[i]['apostas_abertas'] = False
                            salvar(st.session_state.jogos)
                            st.rerun()

                # Apostas
                with st.expander("💰 APOSTAR"):
                    col1, col2 = st.columns([1, 2])
                    with col1:
                        if j['apostas_abertas'] and not j['finalizado']:
                            n_ap = st.text_input("Nome", key=f"n{i}")
                            v_ap = st.number_input("R$", 1.0, 1000.0, 10.0, key=f"v{i}")
                            o_ap = st.radio("Vence:", [j['a'], "Empate", j['b']], key=f"o{i}")
                            if st.button("Confirmar", key=f"bt{i}"):
                                t = "A" if o_ap == j['a'] else "B" if o_ap == j['b'] else "E"
                                st.session_state.jogos[i]['apostas'].append({"nome": n_ap, "valor": v_ap, "opcao": t})
                                salvar(st.session_state.jogos)
                                st.rerun()
                    with col2:
                        if j['apostas']:
                            st.table(pd.DataFrame(j['apostas']))

elif menu == "Classificação":
    st.header("📊 Classificação")
    # Recarregar para garantir que pegou o resultado salvo
    st.session_state.jogos = carregar()
    if st.session_state.jogos:
        # Pegar times únicos
        times = sorted(list(set([j['a'] for j in st.session_state.jogos] + [j['b'] for j in st.session_state.jogos])))
        # Tabela manual (mais estável)
        tabela = {t: {"P":0,"V":0,"E":0,"D":0,"GP":0,"GC":0} for t in times}
        for j in st.session_state.jogos:
            if j['finalizado'] and j['ga'] is not None:
                a, b, ga, gb = j['a'], j['b'], int(j['ga']), int(j['gb'])
                tabela[a]['GP']+=ga; tabela[a]['GC']+=gb; tabela[b]['GP']+=gb; tabela[b]['GC']+=ga
                if ga > gb: tabela[a]['P']+=3; tabela[a]['V']+=1; tabela[b]['D']+=1
                elif gb > ga: tabela[b]['P']+=3; tabela[b]['V']+=1; tabela[a]['D']+=1
                else: tabela[a]['P']+=1; tabela[b]['P']+=1; tabela[a]['E']+=1; tabela[b]['E']+=1
        
        df_tab = pd.DataFrame.from_dict(tabela, orient='index').sort_values(by="P", ascending=False)
        st.table(df_tab)

elif menu == "Ranking":
    st.header("💰 Ranking")
    st.session_state.jogos = carregar()
    rk = {}
    for j in st.session_state.jogos:
        if j['finalizado']:
            res = "A" if j['ga'] > j['gb'] else "B" if j['ga'] < j['gb'] else "E"
            pote = sum(a['valor'] for a in j['apostas'])
            venc = sum(a['valor'] for a in j['apostas'] if a['opcao'] == res)
            for a in j['apostas']:
                rk.setdefault(a['nome'], 0)
                if a['opcao'] == res and venc > 0:
                    rk[a['nome']] += (a['valor']/venc*pote) - a['valor']
                else:
                    rk[a['nome']] -= a['valor']
    if rk:
        df_rk = pd.DataFrame([{"Nome": k, "Saldo Lucro": money(v)} for k, v in rk.items()])
        st.table(df_rk)
