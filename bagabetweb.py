import streamlit as st
import pandas as pd
import random
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="BAGA BET PRO", layout="wide", page_icon="⚽")
conn = st.connection("gsheets", type=GSheetsConnection)

# --- CSS VISUAL ---
st.markdown("""
    <style>
    .placar-box { background-color: #fff; border: 2px solid #333; border-radius: 12px; padding: 10px; text-align: center; }
    .fase-header { background: #111; color: #fff; padding: 10px; border-radius: 8px; margin: 15px 0; text-align: center; font-weight: bold; }
    .time-chave { color: #000 !important; font-weight: bold; }
    .penaltis-chave { color: #d32f2f; font-weight: bold; font-size: 0.85rem; }
    .pódio-container { background: linear-gradient(145deg, #FFD700, #FFA500); padding: 20px; border-radius: 15px; text-align: center; color: #000; margin-bottom: 20px; }
    </style>
    """, unsafe_allow_html=True)

# --- UTILITÁRIOS ---
def money(v):
    cor = "#28a745" if v > 0 else "#dc3545" if v < 0 else "#212529"
    val_fmt = f"R$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f'<span style="color:{cor}; font-weight:bold;">{val_fmt}</span>'

# --- GESTÃO DE DADOS POR ABA (WORKSHEET) ---
def carregar_dados(nome_torneio):
    try:
        # Tenta ler a aba específica do torneio
        df = conn.read(worksheet=nome_torneio, ttl=0)
        if df is None or df.empty: return []
        jogos = []
        for _, r in df.iterrows():
            ap = []
            if str(r.get('apostas')) not in ["nan", "", "None"]:
                for item in str(r.get('apostas')).split("|"):
                    p = item.split(":")
                    if len(p) == 3: ap.append({"nome": p[0], "valor": float(p[1]), "opcao": p[2]})
            jogos.append({
                "a": str(r['a']), "b": str(r['b']),
                "ga1": int(r['ga1']) if pd.notna(r['ga1']) else None,
                "gb1": int(r['gb1']) if pd.notna(r['gb1']) else None,
                "ga2": int(r['ga2']) if pd.notna(r['ga2']) else None,
                "gb2": int(r['gb2']) if pd.notna(r['gb2']) else None,
                "pen_a": int(r['pen_a']) if pd.notna(r['pen_a']) else 0,
                "pen_b": int(r['pen_b']) if pd.notna(r['pen_b']) else 0,
                "finalizado": str(r['finalizado']).upper() == "TRUE",
                "fase": str(r['fase']), "tipo": str(r['tipo']), "apostas": ap
            })
        return jogos
    except: return []

def salvar_dados(jogos, nome_torneio):
    if not jogos: return
    df = pd.DataFrame(jogos)
    df['apostas'] = df['apostas'].apply(lambda x: "|".join([f"{a['nome']}:{a['valor']}:{a['opcao']}" for a in x]) if x else "")
    df['finalizado'] = df['finalizado'].apply(lambda x: "TRUE" if x else "FALSE")
    conn.update(worksheet=nome_torneio, data=df)
    st.cache_data.clear()

# --- LÓGICA DE AVANÇO AUTOMÁTICO ---
def atualizar_confrontos(jogos):
    fases = ["QUARTAS", "SEMI", "FINAL"]
    for fase in ["QUARTAS", "SEMI"]:
        jogos_fase = [j for j in jogos if j['fase'] == fase]
        if jogos_fase and all(j['finalizado'] for j in jogos_fase):
            # Verifica se a próxima fase já existe
            prox_fase = "SEMI" if fase == "QUARTAS" else "FINAL"
            if not any(j['fase'] == prox_fase for j in jogos):
                venc, perd = [], []
                for j in jogos_fase:
                    s1, s2 = (j['ga1'] or 0) + (j['ga2'] or 0), (j['gb1'] or 0) + (j['gb2'] or 0)
                    if s1 > s2 or (s1 == s2 and j['pen_a'] > j['pen_b']):
                        venc.append(j['a']); perd.append(j['b'])
                    else: venc.append(j['b']); perd.append(j['a'])
                
                novos = []
                for i in range(0, len(venc), 2):
                    novos.append({"a": venc[i], "b": venc[i+1], "ga1": None, "gb1": None, "ga2": None, "gb2": None, "pen_a": 0, "pen_b": 0, "finalizado": False, "fase": prox_fase, "tipo": jogos_fase[0]['tipo'], "apostas": []})
                
                if fase == "SEMI": # Cria disputa de 3º lugar
                    novos.append({"a": perd[0], "b": perd[1], "ga1": None, "gb1": None, "ga2": None, "gb2": None, "pen_a": 0, "pen_b": 0, "finalizado": False, "fase": "3º LUGAR", "tipo": jogos_fase[0]['tipo'], "apostas": []})
                
                jogos.extend(novos)
    return jogos

# --- INTERFACE ---
if 'torneio_ativo' not in st.session_state:
    st.title("⚽ BAGA BET PRO")
    nome = st.text_input("Nome do Torneio (ex: Copa_2026_01)")
    col1, col2 = st.columns(2)
    if col1.button("🏆 Acessar/Criar LIGA"):
        st.session_state.torneio_ativo = nome; st.session_state.modo = "LIGA"; st.rerun()
    if col2.button("⚔️ Acessar/Criar COPA"):
        st.session_state.torneio_ativo = nome; st.session_state.modo = "COPA"; st.rerun()
else:
    # Carregar dados do torneio específico
    if 'jogos' not in st.session_state:
        st.session_state.jogos = carregar_dados(st.session_state.torneio_ativo)
        st.session_state.menu = "Jogos"

    with st.sidebar:
        st.header(st.session_state.torneio_ativo)
        senha = st.text_input("Admin", type="password")
        st.session_state.admin = (senha == "1234")
        st.divider()
        if st.button("🏟️ Jogos"): st.session_state.menu = "Jogos"; st.rerun()
        if st.button("📊 Chaves"): st.session_state.menu = "Tabela"; st.rerun()
        if st.button("🤑 Ranking"): st.session_state.menu = "Ranking"; st.rerun()
        if st.button("⚙️ Config"): st.session_state.menu = "Admin"; st.rerun()
        if st.button("🏠 Sair do Torneio"): del st.session_state['torneio_ativo']; st.rerun()

    # --- ABA ADMIN: CRIAR TORNEIO ---
    if st.session_state.menu == "Admin" and st.session_state.admin:
        st.subheader("Configurar Novo Torneio")
        tipo = st.radio("Formato", ["UNICO", "VOLTA"], horizontal=True)
        qtd = st.number_input("Times", 2, 16, 4, step=2)
        nomes = [st.text_input(f"Time {i+1}", key=f"t{i}") for i in range(qtd)]
        if st.button("🚀 Inicializar Planilha"):
            equipes = [n for n in nomes if n]
            random.shuffle(equipes)
            fase_ini = "SEMI" if qtd == 4 else "QUARTAS"
            novos = [{"a": equipes[j], "b": equipes[j+1], "ga1": None, "gb1": None, "ga2": None, "gb2": None, "pen_a": 0, "pen_b": 0, "finalizado": False, "fase": fase_ini, "tipo": tipo, "apostas": []} for j in range(0, len(equipes), 2)]
            salvar_dados(novos, st.session_state.torneio_ativo)
            st.session_state.jogos = novos; st.rerun()

    # --- ABA JOGOS: LANÇAR E APOSTAR ---
    elif st.session_state.menu == "Jogos":
        for fase in ["QUARTAS", "SEMI", "3º LUGAR", "FINAL"]:
            jogos_f = [j for j in st.session_state.jogos if j['fase'] == fase]
            if jogos_f:
                st.markdown(f"<div class='fase-header'>{fase}</div>", unsafe_allow_html=True)
                for idx, j in enumerate(st.session_state.jogos):
                    if j['fase'] == fase:
                        with st.container(border=True):
                            c1, c2, c3 = st.columns([2, 1, 2])
                            c1.markdown(f"<h3 style='text-align:right;'>{j['a']}</h3>", unsafe_allow_html=True)
                            placar = f"{j['ga1'] if j['ga1'] is not None else '-'} : {j['gb1'] if j['gb1'] is not None else '-'}" if j['tipo']=="UNICO" else f"({j['ga1'] or 0}) {j['ga2'] or 0} : {j['gb2'] or 0} ({j['gb1'] or 0})"
                            c2.markdown(f"<div class='placar-box'>{placar}</div>", unsafe_allow_html=True)
                            c3.markdown(f"<h3 style='text-align:left;'>{j['b']}</h3>", unsafe_allow_html=True)

                            if st.session_state.admin:
                                with st.expander("Lançar Placar"):
                                    vga1 = st.number_input(f"Gols A", 0, 20, key=f"vga1{idx}{fase}")
                                    vgb1 = st.number_input(f"Gols B", 0, 20, key=f"vgb1{idx}{fase}")
                                    vga2, vgb2, pa, pb = 0, 0, 0, 0
                                    if j['tipo'] == "VOLTA":
                                        vga2 = st.number_input(f"Volta A", 0, 20, key=f"vga2{idx}{fase}")
                                        vgb2 = st.number_input(f"Volta B", 0, 20, key=f"vgb2{idx}{fase}")
                                    if (vga1+vga2) == (vgb1+vgb2):
                                        pa = st.number_input("Pên A", 0, 20, key=f"pa{idx}{fase}")
                                        pb = st.number_input("Pên B", 0, 20, key=f"pb{idx}{fase}")
                                    if st.button("Salvar", key=f"s{idx}{fase}"):
                                        j.update({"ga1": vga1, "gb1": vgb1, "ga2": vga2, "gb2": vgb2, "pen_a": pa, "pen_b": pb, "finalizado": True})
                                        st.session_state.jogos = atualizar_confrontos(st.session_state.jogos)
                                        salvar_dados(st.session_state.jogos, st.session_state.torneio_ativo); st.rerun()

                            # APOSTAS
                            with st.expander("🤑 Apostas"):
                                if j['finalizado']:
                                    res = "A" if (j['ga1']+j['ga2']) > (j['gb1']+j['gb2']) or ( (j['ga1']+j['ga2']) == (j['gb1']+j['gb2']) and j['pen_a'] > j['pen_b']) else "B"
                                    df_ap = pd.DataFrame(j['apostas'])
                                    if not df_ap.empty:
                                        pote = df_ap['valor'].sum()
                                        venc_v = df_ap[df_ap['opcao'] == res]['valor'].sum()
                                        df_ap['Lucro'] = df_ap.apply(lambda r: money(r['valor']/venc_v*pote - r['valor']) if r['opcao']==res and venc_v>0 else money(-r['valor']), axis=1)
                                        st.write(df_ap.to_html(escape=False, index=False), unsafe_allow_html=True)
                                elif not j['finalizado']:
                                    with st.form(f"f{idx}{fase}"):
                                        n = st.text_input("Nome")
                                        v = st.number_input("R$", 1, 1000, 10)
                                        o = st.radio("Passa", ["A", "B"], horizontal=True)
                                        if st.form_submit_button("Apostar"):
                                            j['apostas'].append({"nome": n, "valor": v, "opcao": o})
                                            salvar_dados(st.session_state.jogos, st.session_state.torneio_ativo); st.rerun()

    # --- ABA CHAVES: PÓDIO E GRÁFICO ---
    elif st.session_state.menu == "Tabela":
        # Lógica de Campeão
        f = next((j for j in st.session_state.jogos if j['fase'] == "FINAL" and j['finalizado']), None)
        if f:
            t3 = next((j for j in st.session_state.jogos if j['fase'] == "3º LUGAR" and j['finalizado']), None)
            camp = f['a'] if (f['ga1']+f['ga2']) > (f['gb1']+f['gb2']) or (f['pen_a'] > f['pen_b']) else f['b']
            vice = f['b'] if camp == f['a'] else f['a']
            terc = (t3['a'] if (t3['ga1']+t3['ga2']) > (t3['gb1']+t3['gb2']) or (t3['pen_a'] > t3['pen_b']) else t3['b']) if t3 else "?"
            st.markdown(f"<div class='pódio-container'><h1>🏆 CAMPEÃO: {camp}</h1><p>🥈 {vice} | 🥉 {terc}</p></div>", unsafe_allow_html=True)

        cols = st.columns(4)
        for i, fase in enumerate(["QUARTAS", "SEMI", "3º LUGAR", "FINAL"]):
            with cols[i]:
                st.markdown(f"<div class='fase-header'>{fase}</div>", unsafe_allow_html=True)
                for j in [jog for jog in st.session_state.jogos if jog['fase'] == fase]:
                    s1, s2 = (j['ga1'] or 0) + (j['ga2'] or 0), (j['gb1'] or 0) + (j['gb2'] or 0)
                    pa = f"<span class='penaltis-chave'>({j['pen_a']})</span>" if j['pen_a'] or j['pen_b'] else ""
                    pb = f"<span class='penaltis-chave'>({j['pen_b']})</span>" if j['pen_a'] or j['pen_b'] else ""
                    st.markdown(f"""
                        <div style='background:white; padding:10px; border-radius:10px; border:2px solid #333; margin-bottom:10px;'>
                            <div class='time-chave'>{j['a']} {pa} <span style='float:right;'>{s1 if j['finalizado'] else ''}</span></div>
                            <div style='height:1px; background:#ccc; margin:5px 0;'></div>
                            <div class='time-chave'>{j['b']} {pb} <span style='float:right;'>{s2 if j['finalizado'] else ''}</span></div>
                        </div>
                    """, unsafe_allow_html=True)

    # --- ABA RANKING ---
    elif st.session_state.menu == "Ranking":
        st.title("🤑 Ranking do Torneio")
        rank = {}
        for j in st.session_state.jogos:
            if j['finalizado'] and j['apostas']:
                res = "A" if (j['ga1']+j['ga2']) > (j['gb1']+j['gb2']) or (j['pen_a'] > j['pen_b']) else "B"
                pote = sum(a['valor'] for a in j['apostas'])
                venc_v = sum(a['valor'] for a in j['apostas'] if a['opcao'] == res)
                for a in j['apostas']:
                    rank[a['nome']] = rank.get(a['nome'], 0) + ((a['valor']/venc_v*pote - a['valor']) if a['opcao']==res and venc_v>0 else -a['valor'])
        if rank:
            df_r = pd.DataFrame([{"Nome": k, "Lucro": money(v)} for k, v in rank.items()])
            st.write(df_r.to_html(escape=False, index=False), unsafe_allow_html=True)
