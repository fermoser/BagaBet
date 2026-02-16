import streamlit as st
import pandas as pd
import random
from itertools import combinations
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="BAGA BET PRO", layout="wide", page_icon="⚽")
conn = st.connection("gsheets", type=GSheetsConnection)

# --- CSS VISUAL ---
st.markdown("""
    <style>
    .placar-box { background-color: #fff; border: 2px solid #333; border-radius: 12px; padding: 10px; text-align: center; }
    .fase-header { background: #111; color: #fff; padding: 8px; border-radius: 8px; margin: 10px 0; text-align: center; font-weight: bold; }
    .time-nome { font-weight: bold; font-size: 1.1rem; }
    .tabela-liga { width: 100%; border-collapse: collapse; background: white; color: black; }
    .tabela-liga th { background: #eee; padding: 8px; border: 1px solid #ddd; }
    .tabela-liga td { padding: 8px; border: 1px solid #ddd; text-align: center; }
    </style>
    """, unsafe_allow_html=True)

# --- FUNÇÕES DE DADOS ---
def money(v):
    cor = "#28a745" if v > 0 else "#dc3545" if v < 0 else "#212529"
    return f'<span style="color:{cor}; font-weight:bold;">R$ {float(v):,.2f}</span>'.replace(".", ",")

def carregar_tudo():
    try: return conn.read(ttl=0)
    except: return pd.DataFrame()

def carregar_dados_torneio(nome_torneio):
    df = carregar_tudo()
    if df.empty or 'torneio_id' not in df.columns: return []
    df_f = df[df['torneio_id'].astype(str) == str(nome_torneio)]
    jogos = []
    for _, r in df_f.iterrows():
        ap = []
        if str(r.get('apostas')) not in ["nan", "", "None"]:
            for item in str(r.get('apostas')).split("|"):
                p = item.split(":")
                if len(p) == 3: ap.append({"nome": p[0], "valor": float(p[1]), "opcao": p[2]})
        jogos.append({
            "a": str(r['a']), "b": str(r['b']),
            "ga": int(r['ga']) if pd.notna(r['ga']) else None,
            "gb": int(r['gb']) if pd.notna(r['gb']) else None,
            "pen_a": int(r['pen_a']) if pd.notna(r['pen_a']) else 0,
            "pen_b": int(r['pen_b']) if pd.notna(r['pen_b']) else 0,
            "finalizado": str(r['finalizado']).upper() == "TRUE",
            "fase": str(r['fase']), "formato": str(r.get('formato', 'COPA')), "apostas": ap
        })
    return jogos

def salvar_dados(jogos_atuais, nome_torneio, formato):
    df_base = carregar_tudo()
    if not df_base.empty and 'torneio_id' in df_base.columns:
        df_base = df_base[df_base['torneio_id'].astype(str) != str(nome_torneio)]
    df_novos = pd.DataFrame(jogos_atuais)
    df_novos['torneio_id'] = nome_torneio
    df_novos['formato'] = formato
    df_novos['apostas'] = df_novos['apostas'].apply(lambda x: "|".join([f"{a['nome']}:{a['valor']}:{a['opcao']}" for a in x]) if x else "")
    df_novos['finalizado'] = df_novos['finalizado'].apply(lambda x: "TRUE" if x else "FALSE")
    df_final = pd.concat([df_base, df_novos], ignore_index=True)
    conn.update(data=df_final)
    st.cache_data.clear()

# --- LÓGICA LIGA (CLASSIFICAÇÃO) ---
def calcular_classificacao(jogos):
    tabela = {}
    for j in jogos:
        for t in [j['a'], j['b']]:
            if t not in tabela: tabela[t] = {"P":0,"J":0,"V":0,"E":0,"D":0,"GP":0,"GC":0,"SG":0}
        if j['finalizado']:
            ga, gb = j['ga'], j['gb']
            tabela[j['a']]["J"] += 1; tabela[j['b']]["J"] += 1
            tabela[j['a']]["GP"] += ga; tabela[j['a']]["GC"] += gb
            tabela[j['b']]["GP"] += gb; tabela[j['b']]["GC"] += ga
            if ga > gb:
                tabela[j['a']]["P"] += 3; tabela[j['a']]["V"] += 1; tabela[j['b']]["D"] += 1
            elif gb > ga:
                tabela[j['b']]["P"] += 3; tabela[j['b']]["V"] += 1; tabela[j['a']]["D"] += 1
            else:
                tabela[j['a']]["P"] += 1; tabela[j['b']]["P"] += 1; tabela[j['a']]["E"] += 1; tabela[j['b']]["E"] += 1
    
    for t in tabela: tabela[t]["SG"] = tabela[t]["GP"] - tabela[t]["GC"]
    df = pd.DataFrame.from_dict(tabela, orient='index').reset_index().rename(columns={'index':'Time'})
    return df.sort_values(by=["P", "V", "SG", "GP"], ascending=False).reset_index(drop=True)

# --- TELA INICIAL ---
if 'torneio_ativo' not in st.session_state:
    st.markdown("<h1 style='text-align: center;'>⚽ BAGA BET PRO</h1>", unsafe_allow_html=True)
    
    df_all = carregar_tudo()
    if not df_all.empty:
        st.subheader("📂 Acessar Torneio Existente")
        # Criamos um dicionário para saber se o torneio é Liga ou Copa
        dict_formatos = dict(zip(df_all['torneio_id'], df_all['formato']))
        cols = st.columns(3)
        for i, (id_t, form_t) in enumerate(dict_formatos.items()):
            icon = "🏆" if form_t == "COPA" else "📈"
            if cols[i%3].button(f"{icon} {id_t}", use_container_width=True):
                st.session_state.torneio_ativo = id_t
                st.session_state.formato = form_t
                st.session_state.jogos = carregar_dados_torneio(id_t)
                st.rerun()

    st.divider()
    st.subheader("🆕 Criar Novo Torneio")
    c1, c2 = st.columns(2)
    novo_id = c1.text_input("ID do Torneio")
    formato_escolhido = c2.selectbox("Tipo de Torneio", ["COPA", "LIGA"])
    if st.button("COMEÇAR NOVO", use_container_width=True):
        if novo_id:
            st.session_state.torneio_ativo = novo_id
            st.session_state.formato = formato_escolhido
            st.session_state.jogos = []
            st.rerun()

# --- INTERFACE DO TORNEIO ---
else:
    formato = st.session_state.formato
    with st.sidebar:
        st.title(f"{'🏆' if formato=='COPA' else '📈'} {st.session_state.torneio_ativo}")
        menu = st.radio("Menu", ["🏟️ Jogos", "📊 Classificação/Chaves", "🤑 Ranking", "⚙️ Admin"])
        senha_admin = st.text_input("Senha Admin", type="password")
        is_admin = (senha_admin == "1234")
        if st.button("🏠 Sair"):
            for k in list(st.session_state.keys()): del st.session_state[k]
            st.rerun()

    # --- ADMIN: GERAÇÃO DE JOGOS ---
    if menu == "⚙️ Admin":
        st.header("⚙️ Configuração")
        if is_admin:
            if st.button("🔄 SINCRONIZAR NUVEM"):
                st.session_state.jogos = carregar_dados_torneio(st.session_state.torneio_ativo)
                st.rerun()
            
            with st.form("setup"):
                qtd = st.number_input("Qtd Times", 2, 20, 4)
                nomes = [st.text_input(f"Time {i+1}", key=f"t{i}") for i in range(qtd)]
                if st.form_submit_button("🚀 GERAR TORNEIO"):
                    nomes_f = [n for n in nomes if n]
                    random.shuffle(nomes_f)
                    novos = []
                    if formato == "LIGA":
                        # Gera todos contra todos
                        for a, b in combinations(nomes_f, 2):
                            novos.append({"a":a,"b":b,"ga":None,"gb":None,"pen_a":0,"pen_b":0,"finalizado":False,"fase":"Rodada Única","apostas":[]})
                    else:
                        f_ini = "FINAL" if qtd==2 else "SEMI" if qtd==4 else "QUARTAS"
                        for i in range(0, len(nomes_f), 2):
                            novos.append({"a":nomes_f[i],"b":nomes_f[i+1],"ga":None,"gb":None,"pen_a":0,"pen_b":0,"finalizado":False,"fase":f_ini,"apostas":[]})
                    salvar_dados(novos, st.session_state.torneio_ativo, formato)
                    st.session_state.jogos = novos; st.rerun()
        else: st.warning("Área de Admin")

    # --- JOGOS (LIGA E COPA) ---
    elif menu == "🏟️ Jogos":
        for fase in sorted(list(set([j['fase'] for j in st.session_state.jogos]))):
            st.markdown(f"<div class='fase-header'>{fase}</div>", unsafe_allow_html=True)
            for idx, jogo in enumerate(st.session_state.jogos):
                if jogo['fase'] == fase:
                    with st.container(border=True):
                        c1, c2, c3 = st.columns([2, 1, 2])
                        c1.markdown(f"<p style='text-align:right;' class='time-nome'>{jogo['a']}</p>", unsafe_allow_html=True)
                        txt_p = f"{jogo['ga'] if jogo['ga'] is not None else '-'} : {jogo['gb'] if jogo['gb'] is not None else '-'}"
                        c2.markdown(f"<div class='placar-box'>{txt_p}</div>", unsafe_allow_html=True)
                        c3.markdown(f"<p class='time-nome'>{jogo['b']}</p>", unsafe_allow_html=True)
                        
                        if is_admin:
                            if not jogo['finalizado']:
                                with st.expander("Lançar"):
                                    v1 = st.number_input("Gols A", 0, 20, key=f"v1{idx}")
                                    v2 = st.number_input("Gols B", 0, 20, key=f"v2{idx}")
                                    pa, pb = 0, 0
                                    if formato == "COPA" and v1 == v2:
                                        pa = st.number_input("Pên A", 0, 20, key=f"pa{idx}")
                                        pb = st.number_input("Pên B", 0, 20, key=f"pb{idx}")
                                    if st.button("Salvar", key=f"s{idx}"):
                                        jogo.update({"ga":v1,"gb":v2,"pen_a":pa,"pen_b":pb,"finalizado":True})
                                        if formato == "COPA": st.session_state.jogos = atualizar_confrontos(st.session_state.jogos)
                                        salvar_dados(st.session_state.jogos, st.session_state.torneio_ativo, formato); st.rerun()
                            else:
                                if st.button("🔄 Refazer", key=f"r{idx}"):
                                    jogo['finalizado'] = False; st.rerun()

                        # APOSTAS
                        with st.expander("🤑 Apostas"):
                            if not jogo['finalizado']:
                                with st.form(f"ap{idx}"):
                                    n, v = st.text_input("Nome"), st.number_input("R$", 1, 500, 10)
                                    o = st.radio("Vence", ["A", "B", "Empate"], horizontal=True)
                                    if st.form_submit_button("Apostar"):
                                        jogo['apostas'].append({"nome":n,"valor":v,"opcao":o})
                                        salvar_dados(st.session_state.jogos, st.session_state.torneio_ativo, formato); st.rerun()
                            elif jogo['apostas']:
                                res = "A" if jogo['ga'] > jogo['gb'] else "B" if jogo['gb'] > jogo['ga'] else "Empate"
                                # Em caso de empate na COPA, quem passa nos penaltis vence a aposta
                                if formato == "COPA" and jogo['ga'] == jogo['gb']:
                                    res = "A" if jogo['pen_a'] > jogo['pen_b'] else "B"
                                df_a = pd.DataFrame(jogo['apostas'])
                                pote, v_v = df_a['valor'].sum(), df_a[df_a['opcao']==res]['valor'].sum()
                                df_a['Lucro'] = df_a.apply(lambda r: money(r['valor']/v_v*pote - r['valor']) if r['opcao']==res and v_v>0 else money(-r['valor']), axis=1)
                                st.write(df_a.to_html(escape=False, index=False), unsafe_allow_html=True)

    # --- ABA CLASSIFICAÇÃO / CHAVES ---
    elif menu == "📊 Classificação/Chaves":
        if formato == "LIGA":
            st.header("📈 Classificação")
            df_cl = calcular_classificacao(st.session_state.jogos)
            st.table(df_cl)
        else:
            # (Lógica de Chaves da Copa que já tínhamos...)
            st.info("Visualização de Chaves de Mata-Mata Ativa")
            # 

[Image of a tournament bracket]
