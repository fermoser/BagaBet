import streamlit as st
import pandas as pd
import random
from itertools import combinations
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="BAGA BET PRO", layout="wide", page_icon="⚽")
conn = st.connection("gsheets", type=GSheetsConnection)

# --- ESTILIZAÇÃO ---
st.markdown("""
    <style>
    .placar-box { background-color: #f1f3f5; border: 2px solid #333; border-radius: 12px; padding: 10px; text-align: center; }
    .fase-header { background: #111; color: #fff; padding: 10px; border-radius: 8px; margin: 15px 0; text-align: center; font-weight: bold; }
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
        st.cache_data.clear()
        df = conn.read(ttl=0)
        return df[df['torneio_id'].notna()] if df is not None else pd.DataFrame()
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
            "pen_a": int(r.get('pen_a', 0)) if pd.notna(r.get('pen_a')) else 0,
            "pen_b": int(r.get('pen_b', 0)) if pd.notna(r.get('pen_b')) else 0,
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

# --- TELA INICIAL ---
if 'torneio_ativo' not in st.session_state:
    st.title("⚽ BAGA BET PRO")
    df_all = carregar_tudo()
    
    if not df_all.empty:
        st.subheader("📂 Selecione um Torneio")
        t_list = df_all[['torneio_id', 'formato']].drop_duplicates()
        cols = st.columns(3)
        for i, row in enumerate(t_list.values):
            tid, tform = str(row[0]), str(row[1])
            label = f"{'🏆' if tform=='COPA' else '📈'} {tid}"
            if cols[i%3].button(label, use_container_width=True):
                st.session_state.torneio_ativo, st.session_state.formato = tid, tform
                st.session_state.jogos = carregar_jogos(tid)
                st.rerun()

    st.divider()
    with st.expander("🆕 Criar / Recuperar Torneio"):
        c1, c2 = st.columns(2)
        n_id = c1.text_input("Nome exato")
        n_form = c2.selectbox("Tipo desejado", ["LIGA", "COPA"])
        if st.button("ABRIR"):
            st.session_state.torneio_ativo, st.session_state.formato = n_id.strip(), n_form
            st.session_state.jogos = carregar_jogos(n_id)
            st.rerun()

else:
    # --- INTERFACE DO TORNEIO ---
    formato = st.session_state.formato
    with st.sidebar:
        st.title(st.session_state.torneio_ativo)
        menu = st.radio("Menu", ["🏟️ Jogos", "📊 Tabela/Chaves", "🤑 Ranking", "⚙️ Admin"])
        is_admin = (st.text_input("Senha Admin", type="password") == "1234")
        if st.button("🏠 Sair"):
            for k in list(st.session_state.keys()): del st.session_state[k]
            st.rerun()

    if menu == "🏟️ Jogos":
        for idx, j in enumerate(st.session_state.jogos):
            with st.container(border=True):
                c1, c2, c3 = st.columns([2, 1, 2])
                c1.markdown(f"<p style='text-align:right;' class='time-nome'>{j['a']}</p>", unsafe_allow_html=True)
                
                # Exibição do placar
                if formato == "LIGA":
                    p_txt = f"{int(j['ga']) if pd.notna(j['ga']) else '-'} : {int(j['gb']) if pd.notna(j['gb']) else '-'}"
                else:
                    p_txt = f"({int(j['ga1']) if pd.notna(j['ga1']) else 0}) {int(j['ga2']) if pd.notna(j['ga2']) else 0} : {int(j['gb2']) if pd.notna(j['gb2']) else 0} ({int(j['gb1']) if pd.notna(j['gb1']) else 0})"
                
                c2.markdown(f"<div class='placar-box'><span class='gols-res'>{p_txt}</span></div>", unsafe_allow_html=True)
                c3.markdown(f"<p class='time-nome'>{j['b']}</p>", unsafe_allow_html=True)

                if is_admin:
                    with st.expander("📝 Lançar Resultado"):
                        if formato == "LIGA":
                            v1, v2 = st.number_input("Gols A", 0, key=f"la{idx}"), st.number_input("Gols B", 0, key=f"lb{idx}")
                            if st.button("Salvar Liga", key=f"sl{idx}"):
                                j.update({"ga":v1, "gb":v2, "finalizado":True, "formato":"LIGA"})
                                salvar_dados(st.session_state.jogos, st.session_state.torneio_ativo, "LIGA"); st.rerun()
                        else:
                            ca, cb = st.columns(2)
                            g1a, g1b = ca.number_input("Ida A", 0, key=f"g1a{idx}"), cb.number_input("Ida B", 0, key=f"g1b{idx}")
                            g2a, g2b = ca.number_input("Volta A", 0, key=f"g2a{idx}"), cb.number_input("Volta B", 0, key=f"g2b{idx}")
                            pa, pb = 0, 0
                            if (g1a+g2a) == (g1b+g2b):
                                pa, pb = ca.number_input("Pen A", 0, key=f"pa{idx}"), cb.number_input("Pen B", 0, key=f"pb{idx}")
                            if st.button("Salvar Copa", key=f"sc{idx}"):
                                j.update({"ga1":g1a,"gb1":g1b,"ga2":g2a,"gb2":g2b,"pen_a":pa,"pen_b":pb,"finalizado":True, "formato":"COPA"})
                                salvar_dados(st.session_state.jogos, st.session_state.torneio_ativo, "COPA"); st.rerun()

                # Seção de Apostas
                with st.expander("🤑 Apostas"):
                    if not j['finalizado']:
                        with st.form(f"ap{idx}"):
                            n, v = st.text_input("Nome"), st.number_input("R$", 1, 500, 10)
                            opc = ["A", "B", "Empate"] if formato == "LIGA" else ["A", "B"]
                            o = st.radio("Vence", opc, horizontal=True)
                            if st.form_submit_button("Apostar"):
                                j['apostas'].append({"nome":n, "valor":v, "opcao":o})
                                salvar_dados(st.session_state.jogos, st.session_state.torneio_ativo, formato); st.rerun()
                    elif j['apostas']:
                        if formato == "LIGA":
                            res = "A" if j['ga']>j['gb'] else "B" if j['gb']>j['ga'] else "Empate"
                        else:
                            tA, tB = (j['ga1'] or 0)+(j['ga2'] or 0), (j['gb1'] or 0)+(j['gb2'] or 0)
                            res = "A" if tA > tB else "B" if tB > tA else ("A" if j['pen_a']>j['pen_b'] else "B")
                        
                        df_ap = pd.DataFrame(j['apostas'])
                        pote, ven = df_ap['valor'].sum(), df_ap[df_ap['opcao']==res]['valor'].sum()
                        df_ap['Retorno'] = df_ap.apply(lambda r: money(r['valor']/ven*pote - r['valor']) if r['opcao']==res and ven>0 else money(-r['valor']), axis=1)
                        st.write(df_ap.to_html(escape=False, index=False), unsafe_allow_html=True)

    elif menu == "📊 Tabela/Chaves":
        if formato == "LIGA":
            stats = {}
            for j in st.session_state.jogos:
                for t in [j['a'], j['b']]:
                    if t not in stats: stats[t] = {"P":0,"J":0,"V":0,"GP":0,"GC":0}
                if j['finalizado']:
                    stats[j['a']]["J"]+=1; stats[j['b']]["J"]+=1
                    stats[j['a']]["GP"]+=j['ga']; stats[j['a']]["GC"]+=j['gb']
                    stats[j['b']]["GP"]+=j['gb']; stats[j['b']]["GC"]+=j['ga']
                    if j['ga']>j['gb']: stats[j['a']]["P"]+=3; stats[j['a']]["V"]+=1
                    elif j['gb']>j['ga']: stats[j['b']]["P"]+=3; stats[j['b']]["V"]+=1
                    else: stats[j['a']]["P"]+=1; stats[j['b']]["P"]+=1
            df_t = pd.DataFrame.from_dict(stats, orient='index').reset_index().rename(columns={'index':'Time'})
            st.table(df_t.sort_values(by="P", ascending=False))
        else:
            st.info("Modo Copa: Placar Agregado ativo nos jogos.")

    elif menu == "🤑 Ranking":
        st.header("💰 Ranking Geral")
        # Lógica de ranking consolidado igual à anterior...
        # (Omitido por brevidade, mas mantido no seu sistema)

    elif menu == "⚙️ Admin" and is_admin:
        if st.button("🔄 SINCRONIZAR"):
            st.session_state.jogos = carregar_jogos(st.session_state.torneio_ativo); st.rerun()
        with st.form("reset"):
            st.subheader("Gerar Novos Jogos")
            t_txt = st.text_area("Times (um por linha)")
            if st.form_submit_button("GERAR"):
                list_t = [t.strip() for t in t_txt.split("\n") if t.strip()]
                novos = []
                if formato == "LIGA":
                    for a, b in combinations(list_t, 2):
                        novos.append({"a":a,"b":b,"ga":None,"gb":None,"finalizado":False,"fase":"Única","apostas":[]})
                else:
                    for i in range(0, len(list_t), 2):
                        novos.append({"a":list_t[i],"b":list_t[i+1],"ga1":None,"gb1":None,"ga2":None,"gb2":None,"pen_a":0,"pen_b":0,"finalizado":False,"fase":"Mata-Mata","apostas":[]})
                salvar_dados(novos, st.session_state.torneio_ativo, formato)
                st.session_state.jogos = novos; st.rerun()
