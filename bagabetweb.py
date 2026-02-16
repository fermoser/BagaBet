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
    .gols-res { color: #1b5e20; font-weight: 900; font-size: 1.8rem; }
    </style>
    """, unsafe_allow_html=True)

# --- FUNÇÕES DE DADOS ---
def money(v):
    cor = "#28a745" if v > 0 else "#dc3545" if v < 0 else "#212529"
    val_fmt = f"R$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f'<span style="color:{cor}; font-weight:bold;">{val_fmt}</span>'

def carregar_tudo():
    try: 
        df = conn.read(ttl=0)
        return df if df is not None else pd.DataFrame()
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
            "fase": str(r['fase']), "apostas": ap
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

def atualizar_confrontos_copa(jogos):
    for fase_atual in ["QUARTAS", "SEMI"]:
        jf = [j for j in jogos if j['fase'] == fase_atual]
        if jf and all(j['finalizado'] for j in jf):
            prox_f = "SEMI" if fase_atual == "QUARTAS" else "FINAL"
            if not any(j['fase'] == prox_f for j in jogos):
                venc, perd = [], []
                for j in jf:
                    if j['ga'] > j['gb'] or (j['ga'] == j['gb'] and j['pen_a'] > j['pen_b']):
                        venc.append(j['a']); perd.append(j['b'])
                    else: venc.append(j['b']); perd.append(j['a'])
                novos = []
                for i in range(0, len(venc), 2):
                    if i+1 < len(venc):
                        novos.append({"a":venc[i],"b":venc[i+1],"ga":None,"gb":None,"pen_a":0,"pen_b":0,"finalizado":False,"fase":prox_f,"apostas":[]})
                if fase_atual == "SEMI" and len(perd) >= 2:
                    novos.append({"a":perd[0],"b":perd[1],"ga":None,"gb":None,"pen_a":0,"pen_b":0,"finalizado":False,"fase":"3º LUGAR","apostas":[]})
                jogos.extend(novos)
    return jogos

# --- TELA INICIAL ---
if 'torneio_ativo' not in st.session_state:
    st.markdown("<h1 style='text-align: center;'>⚽ BAGA BET PRO</h1>", unsafe_allow_html=True)
    df_all = carregar_tudo()
    
    if not df_all.empty and 'torneio_id' in df_all.columns:
        st.subheader("📂 Torneios Salvos")
        # Correção aqui: Verifica se a coluna formato existe, se não, preenche com 'COPA'
        if 'formato' not in df_all.columns:
            df_all['formato'] = 'COPA'
        
        dict_f = dict(zip(df_all['torneio_id'], df_all['formato']))
        cols = st.columns(3)
        for i, (tid, form) in enumerate(dict_f.items()):
            if cols[i%3].button(f"{'🏆' if form=='COPA' else '📈'} {tid}", use_container_width=True):
                st.session_state.torneio_ativo = tid
                st.session_state.formato = form
                st.session_state.jogos = carregar_dados_torneio(tid)
                st.rerun()
                
    st.divider()
    c1, c2 = st.columns(2)
    n_id = c1.text_input("Novo ID")
    n_form = c2.selectbox("Tipo", ["COPA", "LIGA"])
    if st.button("CRIAR NOVO"):
        if n_id:
            st.session_state.torneio_ativo, st.session_state.formato, st.session_state.jogos = n_id, n_form, []
            st.rerun()
else:
    # --- INTERFACE DO TORNEIO (O RESTANTE SEGUE O MESMO) ---
    formato = st.session_state.formato
    with st.sidebar:
        st.title(f"{st.session_state.torneio_ativo}")
        menu = st.radio("Menu", ["🏟️ Jogos", "📊 Tabela/Chaves", "🤑 Ranking", "⚙️ Admin"])
        is_admin = (st.text_input("Senha Admin", type="password") == "1234")
        if st.button("🏠 Sair"):
            for k in list(st.session_state.keys()): del st.session_state[k]
            st.rerun()

    if menu == "⚙️ Admin" and is_admin:
        st.header("⚙️ Admin")
        if st.button("🔄 Sincronizar"):
            st.session_state.jogos = carregar_dados_torneio(st.session_state.torneio_ativo); st.rerun()
        with st.form("setup"):
            qtd = st.number_input("Times", 2, 16, 4)
            nomes = [st.text_input(f"Time {i+1}", key=f"t{i}") for i in range(qtd)]
            if st.form_submit_button("GERAR"):
                nomes_f = [n for n in nomes if n]
                random.shuffle(nomes_f)
                novos = []
                if formato == "LIGA":
                    for a, b in combinations(nomes_f, 2):
                        novos.append({"a":a,"b":b,"ga":None,"gb":None,"pen_a":0,"pen_b":0,"finalizado":False,"fase":"Rodada Única","apostas":[]})
                else:
                    f_i = "FINAL" if qtd==2 else "SEMI" if qtd==4 else "QUARTAS"
                    for i in range(0, len(nomes_f), 2):
                        novos.append({"a":nomes_f[i],"b":nomes_f[i+1],"ga":None,"gb":None,"pen_a":0,"pen_b":0,"finalizado":False,"fase":f_i,"apostas":[]})
                salvar_dados(novos, st.session_state.torneio_ativo, formato)
                st.session_state.jogos = novos; st.rerun()

    elif menu == "🏟️ Jogos":
        for fase in sorted(list(set([j['fase'] for j in st.session_state.jogos]))):
            st.markdown(f"<div class='fase-header'>{fase}</div>", unsafe_allow_html=True)
            for idx, j in enumerate(st.session_state.jogos):
                if j['fase'] == fase:
                    with st.container(border=True):
                        c1, c2, c3 = st.columns([2, 1, 2])
                        c1.markdown(f"<p style='text-align:right;' class='time-nome'>{j['a']}</p>", unsafe_allow_html=True)
                        c2.markdown(f"<div class='placar-box'><span class='gols-res'>{j['ga'] if j['ga'] is not None else '-'} : {j['gb'] if j['gb'] is not None else '-'}</span></div>", unsafe_allow_html=True)
                        c3.markdown(f"<p class='time-nome'>{j['b']}</p>", unsafe_allow_html=True)
                        if is_admin:
                            if not j['finalizado']:
                                with st.expander("Lançar"):
                                    v1, v2 = st.number_input("Gols A",0,20,key=f"v1{idx}"), st.number_input("Gols B",0,20,key=f"v2{idx}")
                                    pa, pb = 0, 0
                                    if formato=="COPA" and v1==v2:
                                        pa, pb = st.number_input("Pen A",0,20,key=f"pa{idx}"), st.number_input("Pen B",0,20,key=f"pb{idx}")
                                    if st.button("Confirmar", key=f"btn{idx}"):
                                        j.update({"ga":v1,"gb":v2,"pen_a":pa,"pen_b":pb,"finalizado":True})
                                        if formato=="COPA": st.session_state.jogos = atualizar_confrontos_copa(st.session_state.jogos)
                                        salvar_dados(st.session_state.jogos, st.session_state.torneio_ativo, formato); st.rerun()
                            else:
                                if st.button("🔄 Refazer", key=f"ref{idx}"):
                                    j['finalizado'] = False; st.rerun()
                        with st.expander("🤑 Apostas"):
                            if not j['finalizado']:
                                with st.form(f"f{idx}"):
                                    n, v = st.text_input("Nome"), st.number_input("R$",1,500,10)
                                    o = st.radio("Passa", ["A", "B"] if formato=="COPA" else ["A", "B", "Empate"], horizontal=True)
                                    if st.form_submit_button("Apostar"):
                                        j['apostas'].append({"nome":n,"valor":v,"opcao":o})
                                        salvar_dados(st.session_state.jogos, st.session_state.torneio_ativo, formato); st.rerun()
                            elif j['apostas']:
                                res = "A" if j['ga'] > j['gb'] else "B" if j['gb'] > j['ga'] else "Empate"
                                if formato=="COPA" and j['ga']==j['gb']: res = "A" if j['pen_a']>j['pen_b'] else "B"
                                df_a = pd.DataFrame(j['apostas'])
                                pote, v_v = df_a['valor'].sum(), df_a[df_a['opcao']==res]['valor'].sum()
                                df_a['Lucro'] = df_a.apply(lambda r: money(r['valor']/v_v*pote - r['valor']) if r['opcao']==res and v_v>0 else money(-r['valor']), axis=1)
                                st.write(df_a.to_html(escape=False, index=False), unsafe_allow_html=True)

    elif menu == "📊 Tabela/Chaves":
        if formato == "LIGA":
            st.header("Tabela de Classificação")
            res = {}
            for j in st.session_state.jogos:
                for t in [j['a'], j['b']]:
                    if t not in res: res[t] = {"P":0,"J":0,"V":0,"E":0,"D":0,"GP":0,"GC":0}
                if j['finalizado']:
                    res[j['a']]["J"] += 1; res[j['b']]["J"] += 1
                    res[j['a']]["GP"] += j['ga']; res[j['a']]["GC"] += j['gb']
                    res[j['b']]["GP"] += j['gb']; res[j['b']]["GC"] += j['ga']
                    if j['ga']>j['gb']: res[j['a']]["P"]+=3; res[j['a']]["V"]+=1; res[j['b']]["D"]+=1
                    elif j['gb']>j['ga']: res[j['b']]["P"]+=3; res[j['b']]["V"]+=1; res[j['a']]["D"]+=1
                    else: res[j['a']]["P"]+=1; res[j['b']]["P"]+=1; res[j['a']]["E"]+=1; res[j['b']]["E"]+=1
            df_t = pd.DataFrame.from_dict(res, orient='index').reset_index().rename(columns={'index':'Time'})
            st.table(df_t.sort_values(["P","V","GP"], ascending=False))
        else:
            st.info("Mata-Mata em andamento. Veja os resultados na aba Jogos.")

    elif menu == "🤑 Ranking":
        st.header("Ranking Financeiro")
        rk = {}
        for j in st.session_state.jogos:
            if j['finalizado'] and j['apostas']:
                res = "A" if j['ga']>j['gb'] else "B" if j['gb']>j['ga'] else "Empate"
                if formato=="COPA" and j['ga']==j['gb']: res = "A" if j['pen_a']>j['pen_b'] else "B"
                p, vv = sum(a['valor'] for a in j['apostas']), sum(a['valor'] for a in j['apostas'] if a['opcao']==res)
                for a in j['apostas']:
                    rk[a['nome']] = rk.get(a['nome'],0) + ((a['valor']/vv*p - a['valor']) if a['opcao']==res and vv>0 else -a['valor'])
        if rk:
            st.write(pd.DataFrame([{"Nome":k, "Lucro":money(v)} for k,v in rk.items()]).to_html(escape=False, index=False), unsafe_allow_html=True)
