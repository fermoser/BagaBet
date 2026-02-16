import streamlit as st
import pandas as pd
import random
from itertools import combinations
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="BAGA BET PRO", layout="wide", page_icon="⚽")
conn = st.connection("gsheets", type=GSheetsConnection)

# --- FUNÇÕES DE DADOS ---
def carregar_tudo_da_nuvem():
    """Lê a planilha bruta e remove linhas totalmente vazias"""
    try:
        st.cache_data.clear()
        df = conn.read(ttl=0)
        if df is not None:
            df = df.dropna(how='all') # Remove linhas 100% vazias
            if 'torneio_id' in df.columns:
                df['torneio_id'] = df['torneio_id'].astype(str).str.strip()
            return df
        return pd.DataFrame()
    except:
        return pd.DataFrame()

def carregar_jogos_torneio(nome_torneio):
    df = carregar_tudo_da_nuvem()
    if df.empty or 'torneio_id' not in df.columns: return []
    
    # Filtro exato
    df_f = df[df['torneio_id'] == str(nome_torneio).strip()]
    
    jogos = []
    for _, r in df_f.iterrows():
        # Processar Apostas com segurança
        ap = []
        raw_ap = str(r.get('apostas', ''))
        if raw_ap not in ["nan", "", "None"]:
            for item in raw_ap.split("|"):
                p = item.split(":")
                if len(p) >= 2:
                    ap.append({"nome": p[0], "valor": float(p[1]), "opcao": p[2] if len(p)==3 else "A"})
        
        jogos.append({
            "a": str(r.get('a', 'Time A')), "b": str(r.get('b', 'Time B')),
            "ga1": r.get('ga1'), "gb1": r.get('gb1'),
            "ga2": r.get('ga2'), "gb2": r.get('gb2'),
            "ga": r.get('ga'), "gb": r.get('gb'),
            "pen_a": r.get('pen_a', 0), "pen_b": r.get('pen_b', 0),
            "finalizado": str(r.get('finalizado', '')).upper() == "TRUE",
            "fase": str(r.get('fase', 'Rodada')),
            "formato": str(r.get('formato', 'LIGA')),
            "apostas": ap
        })
    return jogos

def salvar_na_nuvem(jogos_atuais, nome_torneio, formato):
    df_full = carregar_tudo_da_nuvem()
    nome_torneio = str(nome_torneio).strip()
    
    # Remove apenas o torneio atual para sobrescrever
    if not df_full.empty and 'torneio_id' in df_full.columns:
        df_base = df_full[df_full['torneio_id'] != nome_torneio]
    else:
        df_base = pd.DataFrame()
    
    df_novos = pd.DataFrame(jogos_atuais)
    df_novos['torneio_id'] = nome_torneio
    df_novos['formato'] = formato
    df_novos['apostas'] = df_novos['apostas'].apply(lambda x: "|".join([f"{a['nome']}:{a['valor']}:{a['opcao']}" for a in x]) if x else "")
    df_novos['finalizado'] = df_novos['finalizado'].apply(lambda x: "TRUE" if x else "FALSE")
    
    df_final = pd.concat([df_base, df_novos], ignore_index=True)
    conn.update(data=df_final)
    st.cache_data.clear()

# --- NAVEGAÇÃO ---
if 'torneio_ativo' not in st.session_state:
    st.title("⚽ BAGA BET PRO")
    df_all = carregar_tudo_da_nuvem()
    
    if not df_all.empty and 'torneio_id' in df_all.columns:
        st.subheader("📂 Torneios Encontrados")
        # Pega a lista real de quem tem torneio_id preenchido
        lista_t = df_all[df_all['torneio_id'] != 'nan'][['torneio_id', 'formato']].drop_duplicates()
        
        cols = st.columns(3)
        for i, row in enumerate(lista_t.values):
            tid, tform = row[0], row[1]
            if cols[i%3].button(f"{'🏆' if tform=='COPA' else '📈'} {tid}", use_container_width=True):
                st.session_state.torneio_ativo = tid
                st.session_state.formato = tform
                st.session_state.jogos = carregar_jogos_torneio(tid)
                st.rerun()

    st.divider()
    st.subheader("🆕 Novo Torneio")
    c1, c2 = st.columns(2)
    id_novo = c1.text_input("Nome (Ex: copa2026)")
    tipo_novo = c2.selectbox("Tipo", ["LIGA", "COPA"])
    if st.button("CRIAR"):
        if id_novo:
            st.session_state.torneio_ativo, st.session_state.formato, st.session_state.jogos = id_novo, tipo_novo, []
            st.rerun()

else:
    # --- INTERFACE DO TORNEIO ---
    formato = st.session_state.formato
    with st.sidebar:
        st.title(st.session_state.torneio_ativo)
        menu = st.radio("Menu", ["Jogos", "Tabela/Chaves", "Ranking", "Admin"])
        is_admin = (st.text_input("Senha Admin", type="password") == "1234")
        if st.button("🏠 Sair"):
            for k in list(st.session_state.keys()): del st.session_state[k]
            st.rerun()

    if menu == "Admin":
        if st.button("🔄 FORÇAR ATUALIZAÇÃO (Puxar da Nuvem)"):
            st.session_state.jogos = carregar_jogos_torneio(st.session_state.torneio_ativo)
            st.rerun()
        if is_admin:
            with st.form("reset"):
                st.warning("Isso criará novos jogos!")
                times_txt = st.text_area("Times (um por linha)")
                if st.form_submit_button("GERAR"):
                    lista = [t.strip() for t in times_txt.split("\n") if t.strip()]
                    novos = []
                    if formato == "LIGA":
                        for a, b in combinations(lista, 2):
                            novos.append({"a":a,"b":b,"ga":None,"gb":None,"finalizado":False,"fase":"Única","formato":"LIGA","apostas":[]})
                    else:
                        for i in range(0, len(lista), 2):
                            novos.append({"a":lista[i],"b":lista[i+1],"ga1":None,"gb1":None,"ga2":None,"gb2":None,"finalizado":False,"fase":"Oitavas","formato":"COPA","apostas":[]})
                    salvar_na_nuvem(novos, st.session_state.torneio_ativo, formato)
                    st.session_state.jogos = novos; st.rerun()

    elif menu == "Jogos":
        for idx, j in enumerate(st.session_state.jogos):
            with st.container(border=True):
                c1, c2, c3 = st.columns([2, 1, 2])
                c1.write(f"**{j['a']}**")
                
                if formato == "LIGA":
                    res_p = f"{int(j['ga']) if pd.notna(j['ga']) else '-'} x {int(j['gb']) if pd.notna(j['gb']) else '-'}"
                else:
                    res_p = f"({int(j['ga1']) if pd.notna(j['ga1']) else 0}) {int(j['ga2']) if pd.notna(j['ga2']) else 0} x {int(j['gb2']) if pd.notna(j['gb2']) else 0} ({int(j['gb1']) if pd.notna(j['gb1']) else 0})"
                
                c2.write(res_p)
                c3.write(f"**{j['b']}**")
                
                if is_admin:
                    with st.expander("Lançar"):
                        if formato == "LIGA":
                            v1 = st.number_input("Gols A", 0, 20, key=f"la{idx}")
                            v2 = st.number_input("Gols B", 0, 20, key=f"lb{idx}")
                            if st.button("Salvar Liga", key=f"sl{idx}"):
                                j.update({"ga":v1, "gb":v2, "finalizado":True})
                                salvar_na_nuvem(st.session_state.jogos, st.session_state.torneio_ativo, "LIGA")
                                st.rerun()
                        else:
                            # Campos da Copa Ida e Volta
                            g1a = st.number_input("Ida A", 0, key=f"g1a{idx}")
                            g1b = st.number_input("Ida B", 0, key=f"g1b{idx}")
                            g2a = st.number_input("Volta A", 0, key=f"g2a{idx}")
                            g2b = st.number_input("Volta B", 0, key=f"g2b{idx}")
                            if st.button("Salvar Copa", key=f"sc{idx}"):
                                j.update({"ga1":g1a, "gb1":g1b, "ga2":g2a, "gb2":g2b, "finalizado":True})
                                salvar_na_nuvem(st.session_state.jogos, st.session_state.torneio_ativo, "COPA")
                                st.rerun()
