import streamlit as st
import pandas as pd
import random
from itertools import combinations
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="BAGA BET PRO", layout="wide", page_icon="⚽")
conn = st.connection("gsheets", type=GSheetsConnection)

# --- FUNÇÕES DE DADOS ---
def carregar_tudo():
    try:
        st.cache_data.clear()
        df = conn.read(ttl=0)
        if df is not None:
            # Garante que colunas de gols sejam números para não quebrar a tabela
            cols_gols = ['ga', 'gb', 'ga1', 'gb1', 'ga2', 'gb2', 'pen_a', 'pen_b']
            for col in cols_gols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            return df[df['torneio_id'].notna()]
        return pd.DataFrame()
    except: return pd.DataFrame()

def carregar_jogos(nome_torneio):
    df = carregar_tudo()
    if df.empty: return []
    df_f = df[df['torneio_id'].astype(str).str.strip() == str(nome_torneio).strip()]
    
    jogos = []
    for _, r in df_f.iterrows():
        ap = []
        raw_ap = str(r.get('apostas', ''))
        if raw_ap not in ["nan", "", "None"]:
            for item in raw_ap.split("|"):
                p = item.split(":")
                if len(p) == 3: ap.append({"nome": p[0], "valor": float(p[1]), "opcao": p[2]})
        
        jogos.append({
            "a": str(r.get('a')), "b": str(r.get('b')),
            "ga": r.get('ga'), "gb": r.get('gb'),
            "ga1": r.get('ga1'), "gb1": r.get('gb1'),
            "ga2": r.get('ga2'), "gb2": r.get('gb2'),
            "pen_a": r.get('pen_a', 0) if pd.notna(r.get('pen_a')) else 0,
            "pen_b": r.get('pen_b', 0) if pd.notna(r.get('pen_b')) else 0,
            "finalizado": str(r.get('finalizado', '')).upper() == "TRUE",
            "fase": str(r.get('fase', 'Fase')),
            "formato": str(r.get('formato', 'LIGA')),
            "apostas": ap
        })
    return jogos

def salvar_dados(jogos_atuais, nome_torneio, formato):
    df_full = carregar_tudo()
    nome_torneio = str(nome_torneio).strip()
    df_base = df_full[df_full['torneio_id'].astype(str).str.strip() != nome_torneio] if not df_full.empty else pd.DataFrame()
    
    df_novos = pd.DataFrame(jogos_atuais)
    df_novos['torneio_id'] = nome_torneio
    df_novos['formato'] = formato
    df_novos['finalizado'] = df_novos['finalizado'].apply(lambda x: "TRUE" if x else "FALSE")
    df_novos['apostas'] = df_novos['apostas'].apply(lambda x: "|".join([f"{a['nome']}:{a['valor']}:{a['opcao']}" for a in x]) if x else "")
    
    df_final = pd.concat([df_base, df_novos], ignore_index=True)
    conn.update(data=df_final)
    st.cache_data.clear()

# --- INTERFACE PRINCIPAL ---
if 'torneio_ativo' not in st.session_state:
    st.title("⚽ BAGA BET PRO")
    df_all = carregar_tudo()
    if not df_all.empty:
        t_list = df_all[['torneio_id', 'formato']].drop_duplicates()
        cols = st.columns(3)
        for i, row in enumerate(t_list.values):
            if cols[i%3].button(f"{row[0]} ({row[1]})", use_container_width=True):
                st.session_state.torneio_ativo, st.session_state.formato = row[0], row[1]
                st.session_state.jogos = carregar_jogos(row[0])
                st.rerun()
else:
    # Sidebar
    formato = st.session_state.formato
    with st.sidebar:
        st.header(st.session_state.torneio_ativo)
        menu = st.radio("Menu", ["🏟️ Jogos", "📊 Tabela/Chaves", "🤑 Admin"])
        if st.button("🏠 Sair"):
            for k in list(st.session_state.keys()): del st.session_state[k]
            st.rerun()

    # ABA JOGOS (Idêntica à anterior, mantendo a funcionalidade de lançamento)
    if menu == "🏟️ Jogos":
        for idx, j in enumerate(st.session_state.jogos):
            with st.container(border=True):
                st.write(f"**{j['fase']}**")
                c1, c2, c3 = st.columns([2, 1, 2])
                c1.write(f"### {j['a']}")
                if formato == "LIGA":
                    placar = f"{int(j['ga']) if pd.notna(j['ga']) else '-'} x {int(j['gb']) if pd.notna(j['gb']) else '-'}"
                else:
                    placar = f"({int(j['ga1']) or 0}) {int(j['ga2']) or 0} x {int(j['gb2']) or 0} ({int(j['gb1']) or 0})"
                c2.write(f"## {placar}")
                c3.write(f"### {j['b']}")
                
                # Admin lança gols aqui
                with st.expander("Lançar"):
                    if formato == "LIGA":
                        ga = st.number_input("Gols A", 0, key=f"ga{idx}")
                        gb = st.number_input("Gols B", 0, key=f"gb{idx}")
                        if st.button("Confirmar", key=f"bt{idx}"):
                            j.update({"ga":ga, "gb":gb, "finalizado":True})
                            salvar_dados(st.session_state.jogos, st.session_state.torneio_ativo, formato); st.rerun()
                    else:
                        cIda, cVolta = st.columns(2)
                        ga1 = cIda.number_input("Ida A", 0, key=f"ga1{idx}")
                        gb1 = cIda.number_input("Ida B", 0, key=f"gb1{idx}")
                        ga2 = cVolta.number_input("Volta A", 0, key=f"ga2{idx}")
                        gb2 = cVolta.number_input("Volta B", 0, key=f"gb2{idx}")
                        if st.button("Confirmar Copa", key=f"btc{idx}"):
                            j.update({"ga1":ga1, "gb1":gb1, "ga2":ga2, "gb2":gb2, "finalizado":True})
                            salvar_dados(st.session_state.jogos, st.session_state.torneio_ativo, formato); st.rerun()

    # ABA TABELA / CHAVES (Onde estava o erro)
    elif menu == "📊 Tabela/Chaves":
        if formato == "LIGA":
            st.subheader("Tabela de Pontos")
            stats = {}
            for j in st.session_state.jogos:
                for t in [j['a'], j['b']]:
                    if t not in stats: stats[t] = {"P":0,"J":0,"V":0,"E":0,"D":0,"GP":0,"GC":0,"SG":0}
                if j['finalizado']:
                    ga, gb = int(j['ga']), int(j['gb'])
                    stats[j['a']]["J"]+=1; stats[j['b']]["J"]+=1
                    stats[j['a']]["GP"]+=ga; stats[j['a']]["GC"]+=gb
                    stats[j['b']]["GP"]+=gb; stats[j['b']]["GC"]+=ga
                    if ga > gb: stats[j['a']]["P"]+=3; stats[j['a']]["V"]+=1; stats[j['b']]["D"]+=1
                    elif gb > ga: stats[j['b']]["P"]+=3; stats[j['b']]["V"]+=1; stats[j['a']]["D"]+=1
                    else: stats[j['a']]["P"]+=1; stats[j['b']]["P"]+=1; stats[j['a']]["E"]+=1; stats[j['b']]["E"]+=1
            
            for t in stats: stats[t]["SG"] = stats[t]["GP"] - stats[t]["GC"]
            df_tab = pd.DataFrame.from_dict(stats, orient='index').reset_index().rename(columns={'index':'Time'})
            st.dataframe(df_tab.sort_values(by=["P", "V", "SG"], ascending=False), hide_index=True)
        
        else:
            st.subheader("Chaveamento Mata-Mata")
            for j in st.session_state.jogos:
                total_a = (j['ga1'] or 0) + (j['ga2'] or 0)
                total_b = (j['gb1'] or 0) + (j['gb2'] or 0)
                with st.container(border=True):
                    col1, col2 = st.columns(2)
                    status = "✅ Avançou" if j['finalizado'] else "⏳ Em andamento"
                    winner = j['a'] if total_a > total_b else j['b'] if total_b > total_a else "Empate"
                    col1.write(f"**{j['a']} {total_a} x {total_b} {j['b']}**")
                    col2.write(f"{status}: {winner if j['finalizado'] else ''}")

    elif menu == "🤑 Admin":
        if st.button("Limpar Cache e Sincronizar"):
            st.session_state.jogos = carregar_jogos(st.session_state.torneio_ativo)
            st.rerun()
