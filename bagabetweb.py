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
    .main { background-color: #f0f2f6; }
    .placar-box {
        background-color: #ffffff; border: 2px solid #333;
        border-radius: 12px; padding: 10px; text-align: center;
    }
    .fase-header {
        background: #111; color: #fff; padding: 10px;
        border-radius: 8px; margin: 15px 0; text-align: center; font-weight: bold;
    }
    .time-chave { color: #000; font-weight: bold; font-size: 1.1rem; }
    .penaltis-chave { color: #d32f2f; font-size: 0.85rem; font-weight: bold; }
    .pódio-container {
        background: linear-gradient(145deg, #FFD700, #FFA500);
        padding: 20px; border-radius: 15px; text-align: center;
        color: #000; margin-bottom: 20px; box-shadow: 0px 4px 15px rgba(0,0,0,0.2);
    }
    </style>
    """, unsafe_allow_html=True)

# --- FUNÇÕES DE DADOS ---
def money(v):
    cor = "#28a745" if v > 0 else "#dc3545" if v < 0 else "#212529"
    val_fmt = f"R$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f'<span style="color:{cor}; font-weight:bold;">{val_fmt}</span>'

def carregar_tudo(modo_atual):
    try:
        df = conn.read(ttl=0)
        if df is None or df.empty: return [], []
        df = df[df['modo'] == modo_atual]
        jogos = []
        times = set()
        for _, r in df.iterrows():
            ap = []
            if str(r.get('apostas')) not in ["nan", "", "None"]:
                for item in str(r.get('apostas')).split("|"):
                    p = item.split(":")
                    if len(p) == 3: ap.append({"nome": p[0], "valor": float(p[1]), "opcao": p[2]})
            j = {
                "a": str(r.get('a')), "b": str(r.get('b')),
                "ga1": int(r['ga1']) if pd.notna(r.get('ga1')) else None,
                "gb1": int(r['gb1']) if pd.notna(r.get('gb1')) else None,
                "ga2": int(r['ga2']) if pd.notna(r.get('ga2')) else None,
                "gb2": int(r['gb2']) if pd.notna(r.get('gb2')) else None,
                "finalizado": str(r.get('finalizado')).upper() == "TRUE",
                "apostas": ap, "fase": str(r.get('fase')), "modo": str(r.get('modo')),
                "tipo": str(r.get('tipo', 'UNICO')),
                "pen_a": int(r['pen_a']) if pd.notna(r.get('pen_a')) else 0,
                "pen_b": int(r['pen_b']) if pd.notna(r.get('pen_b')) else 0
            }
            jogos.append(j); times.add(j['a']); times.add(j['b'])
        return jogos, list(times)
    except: return [], []

def salvar_tudo(lista_nova, modo_atual):
    try:
        df_antigo = conn.read(ttl=0)
        df_outros = df_antigo[df_antigo['modo'] != modo_atual] if df_antigo is not None else pd.DataFrame()
    except: df_outros = pd.DataFrame()

    if not lista_nova: df_save = df_outros
    else:
        df_atual = pd.DataFrame(lista_nova)
        df_atual['apostas'] = df_atual['apostas'].apply(lambda x: "|".join([f"{a['nome']}:{a['valor']}:{a['opcao']}" for a in x]) if x else "")
        df_atual['finalizado'] = df_atual['finalizado'].apply(lambda x: "TRUE" if x else "FALSE")
        df_save = pd.concat([df_outros, df_atual], ignore_index=True)
    conn.update(data=df_save)
    st.cache_data.clear()

# --- INICIALIZAÇÃO ---
if 'estagio' not in st.session_state: st.session_state.estagio = 'inicio'
if 'autenticado' not in st.session_state: st.session_state.autenticado = False
if 'menu' not in st.session_state: st.session_state.menu = "Jogos"

# --- TELA INICIAL ---
if st.session_state.estagio == 'inicio':
    st.markdown("<h1 style='text-align: center;'>⚽ BAGA BET PRO</h1>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    if c1.button("🏆 LIGA", use_container_width=True):
        st.session_state.modo = "LIGA"; st.session_state.jogos, st.session_state.times = carregar_tudo("LIGA")
        st.session_state.estagio = 'painel'; st.rerun()
    if c2.button("⚔️ COPA", use_container_width=True):
        st.session_state.modo = "COPA"; st.session_state.jogos, st.session_state.times = carregar_tudo("COPA")
        st.session_state.estagio = 'painel'; st.rerun()
else:
    # --- SIDEBAR ---
    with st.sidebar:
        st.header(f"⚽ {st.session_state.modo}")
        if not st.session_state.autenticado:
            if st.text_input("Senha", type="password") == "1234": st.session_state.autenticado = True; st.rerun()
        else:
            if st.button("Sair Admin"): st.session_state.autenticado = False; st.rerun()
        st.divider()
        if st.button("🏟️ JOGOS"): st.session_state.menu = "Jogos"; st.rerun()
        if st.button("📊 CHAVES"): st.session_state.menu = "Tabela"; st.rerun()
        if st.button("🤑 RANKING"): st.session_state.menu = "Ranking"; st.rerun()
        if st.button("⚙️ ADMIN"): st.session_state.menu = "Admin"; st.rerun()
        st.divider()
        if st.button("🏠 INÍCIO"): st.session_state.estagio = 'inicio'; st.rerun()

    # --- ADMIN ---
    if st.session_state.menu == "Admin" and st.session_state.autenticado:
        st.title("⚙️ Painel Copa")
        tipo_mata = st.radio("Formato", ["Mata-Mata Único", "Ida e Volta"], horizontal=True)
        qtd = st.number_input("Equipes", 2, 16, 4, step=2)
        nomes = [st.text_input(f"Equipe {i+1}", key=f"cp{i}") for i in range(qtd)]
        
        if st.button("🚀 INICIAR TORNEIO"):
            equipes = [n.strip() for n in nomes if n.strip()]
            random.shuffle(equipes)
            fase = "QUARTAS" if qtd > 4 else "SEMI"
            novos = [{"a": equipes[j], "b": equipes[j+1], "ga1": None, "gb1": None, "ga2": None, "gb2": None, 
                      "finalizado": False, "apostas": [], "fase": fase, "pen_a": 0, "pen_b": 0, 
                      "modo": "COPA", "tipo": "VOLTA" if tipo_mata == "Ida e Volta" else "UNICO"} for j in range(0, len(equipes), 2)]
            st.session_state.jogos = novos; salvar_tudo(novos, "COPA"); st.rerun()

        if st.session_state.jogos:
            fase_atual = st.session_state.jogos[-1]['fase']
            jogos_fase = [j for j in st.session_state.jogos if j['fase'] == fase_atual]
            if all(j['finalizado'] for j in jogos_fase) and fase_atual not in ["FINAL", "3º LUGAR"]:
                if st.button(f"➡️ CONFIRMAR VENCEDORES DA {fase_atual}"):
                    venc, perd = [], []
                    for j in jogos_fase:
                        soma_a, soma_b = (j['ga1'] or 0) + (j['ga2'] or 0), (j['gb1'] or 0) + (j['gb2'] or 0)
                        if soma_a > soma_b or (soma_a == soma_b and j['pen_a'] > j['pen_b']):
                            venc.append(j['a']); perd.append(j['b'])
                        else: venc.append(j['b']); perd.append(j['a'])
                    
                    if fase_atual == "QUARTAS":
                        prox = "SEMI"
                        novos_j = [{"a": venc[i], "b": venc[i+1], "ga1": None, "gb1": None, "ga2": None, "gb2": None, 
                                    "finalizado": False, "apostas": [], "fase": prox, "pen_a": 0, "pen_b": 0, 
                                    "modo": "COPA", "tipo": j['tipo']} for i in range(0, len(venc), 2)]
                    else: # Avançando da SEMI para FINAL e 3º LUGAR
                        novos_j = [
                            {"a": venc[0], "b": venc[1], "ga1": None, "gb1": None, "ga2": None, "gb2": None, 
                             "finalizado": False, "apostas": [], "fase": "FINAL", "pen_a": 0, "pen_b": 0, "modo": "COPA", "tipo": j['tipo']},
                            {"a": perd[0], "b": perd[1], "ga1": None, "gb1": None, "ga2": None, "gb2": None, 
                             "finalizado": False, "apostas": [], "fase": "3º LUGAR", "pen_a": 0, "pen_b": 0, "modo": "COPA", "tipo": j['tipo']}
                        ]
                    st.session_state.jogos.extend(novos_j); salvar_tudo(st.session_state.jogos, "COPA"); st.rerun()

    # --- JOGOS ---
    elif st.session_state.menu == "Jogos":
        # Ordem de exibição manual para as fases
        for fase in ["QUARTAS", "SEMI", "3º LUGAR", "FINAL"]:
            jogos_f = [j for j in st.session_state.jogos if j['fase'] == fase]
            if jogos_f:
                st.markdown(f"<div class='fase-header'>{fase}</div>", unsafe_allow_html=True)
                for i, j in enumerate(st.session_state.jogos):
                    if j['fase'] == fase:
                        with st.container(border=True):
                            c1, c2, c3 = st.columns([2, 1, 2])
                            c1.markdown(f"<h3 style='text-align:right;'>{j['a']}</h3>", unsafe_allow_html=True)
                            placar = f"{j['ga1'] if j['ga1'] is not None else '-'} : {j['gb1'] if j['gb1'] is not None else '-'}" if j['tipo']=="UNICO" else f"({j['ga1'] or 0}) {j['ga2'] or 0} : {j['gb2'] or 0} ({j['gb1'] or 0})"
                            c2.markdown(f"<div class='placar-box'><span class='{'gols-finalizado' if j['finalizado'] else 'gols-aberto'}'>{placar}</span></div>", unsafe_allow_html=True)
                            c3.markdown(f"<h3 style='text-align:left;'>{j['b']}</h3>", unsafe_allow_html=True)

                            if j['finalizado'] and (j['pen_a'] > 0 or j['pen_b'] > 0):
                                st.markdown(f"<p style='text-align:center;'>Pênaltis: **({j['pen_a']}) x ({j['pen_b']})**</p>", unsafe_allow_html=True)

                            if st.session_state.autenticado:
                                with st.expander("Placar"):
                                    col1, col2 = st.columns(2)
                                    vga1 = col1.number_input(f"Ida/Único {j['a']}", 0, 20, step=1, key=f"g1{i}{fase}")
                                    vgb1 = col2.number_input(f"Ida/Único {j['b']}", 0, 20, step=1, key=f"g2{i}{fase}")
                                    vga2, vgb2 = 0, 0
                                    if j['tipo'] == "VOLTA":
                                        vga2 = col1.number_input(f"Volta {j['a']}", 0, 20, step=1, key=f"v1{i}{fase}")
                                        vgb2 = col2.number_input(f"Volta {j['b']}", 0, 20, step=1, key=f"v2{i}{fase}")
                                    pa, pb = 0, 0
                                    if (vga1 + vga2) == (vgb1 + vgb2):
                                        p1, p2 = st.columns(2)
                                        pa, pb = p1.number_input("Pên. A", 0, 20, step=1, key=f"pa{i}{fase}"), p2.number_input("Pên. B", 0, 20, step=1, key=f"pb{i}{fase}")
                                    if st.button("SALVAR", key=f"sv{i}{fase}"):
                                        j.update({'ga1': vga1, 'gb1': vgb1, 'ga2': vga2, 'gb2': vgb2, 'finalizado': True, 'pen_a': pa, 'pen_b': pb})
                                        salvar_tudo(st.session_state.jogos, "COPA"); st.rerun()

    # --- CHAVES (TABELA) ---
    elif st.session_state.menu == "Tabela":
        st.title("⚔️ Chaves do Mata-Mata")
        
        # Lógica de Pódio
        jogo_final = next((j for j in st.session_state.jogos if j['fase'] == "FINAL"), None)
        jogo_3 = next((j for j in st.session_state.jogos if j['fase'] == "3º LUGAR"), None)
        
        if jogo_final and jogo_final['finalizado']:
            tot_a, tot_b = (jogo_final['ga1'] or 0) + (jogo_final['ga2'] or 0), (jogo_final['gb1'] or 0) + (jogo_final['gb2'] or 0)
            camp = jogo_final['a'] if tot_a > tot_b or (tot_a == tot_b and jogo_final['pen_a'] > jogo_final['pen_b']) else jogo_final['b']
            vice = jogo_final['b'] if camp == jogo_final['a'] else jogo_final['a']
            terc = ""
            if jogo_3 and jogo_3['finalizado']:
                s3a, s3b = (jogo_3['ga1'] or 0) + (jogo_3['ga2'] or 0), (jogo_3['gb1'] or 0) + (jogo_3['gb2'] or 0)
                terc = jogo_3['a'] if s3a > s3b or (s3a == s3b and jogo_3['pen_a'] > jogo_3['pen_b']) else jogo_3['b']
            
            st.markdown(f"""
                <div class='pódio-container'>
                    <h1>🏆 CAMPEÃO: {camp} 🏆</h1>
                    <p style='font-size:1.2rem;'>🥈 2º Lugar: {vice} | 🥉 3º Lugar: {terc}</p>
                </div>
            """, unsafe_allow_html=True)

        cols = st.columns(4)
        for idx, f_nome in enumerate(["QUARTAS", "SEMI", "FINAL", "3º LUGAR"]):
            with cols[idx]:
                st.markdown(f"<div class='fase-header'>{f_nome}</div>", unsafe_allow_html=True)
                for jf in [j for j in st.session_state.jogos if j['fase'] == f_nome]:
                    ta, tb = (jf['ga1'] or 0) + (jf['ga2'] or 0), (jf['gb1'] or 0) + (jf['gb2'] or 0)
                    pen_txt_a = f" <span class='penaltis-chave'>({jf['pen_a']})</span>" if jf['finalizado'] and jf['pen_a']+jf['pen_b']>0 else ""
                    pen_txt_b = f" <span class='penaltis-chave'>({jf['pen_b']})</span>" if jf['finalizado'] and jf['pen_a']+jf['pen_b']>0 else ""
                    v_a = "border-left: 5px solid green; background:#e8f5e9;" if jf['finalizado'] and (ta > tb or (ta==tb and jf['pen_a'] > jf['pen_b'])) else ""
                    v_b = "border-left: 5px solid green; background:#e8f5e9;" if jf['finalizado'] and (tb > ta or (ta==tb and jf['pen_b'] > jf['pen_a'])) else ""
                    
                    st.markdown(f"""
                        <div style='background:white; padding:10px; border-radius:10px; margin-bottom:10px; border:2px solid #333;'>
                            <div class='time-chave' style='padding:5px; {v_a}'>{jf['a']} {pen_txt_a} <span style='float:right;'>{ta if jf['finalizado'] else ""}</span></div>
                            <div style='height:2px; background:#eee; margin:5px 0;'></div>
                            <div class='time-chave' style='padding:5px; {v_b}'>{jf['b']} {pen_txt_b} <span style='float:right;'>{tb if jf['finalizado'] else ""}</span></div>
                        </div>
                    """, unsafe_allow_html=True)

    # --- RANKING ---
    elif st.session_state.menu == "Ranking":
        st.title("🤑 Ranking")
        res_rank = {}
        for j in st.session_state.jogos:
            if j['finalizado'] and j['apostas']:
                tot_a, tot_b = (j['ga1'] or 0) + (j['ga2'] or 0), (j['gb1'] or 0) + (j['gb2'] or 0)
                res = "A" if tot_a > tot_b or (tot_a == tot_b and j['pen_a'] > j['pen_b']) else "B"
                pote = sum(a['valor'] for a in j['apostas'])
                venc_v = sum(a['valor'] for a in j['apostas'] if a['opcao'] == res)
                for a in j['apostas']:
                    res_rank.setdefault(a['nome'], 0)
                    retorno = (a['valor']/venc_v * pote) if a['opcao'] == res and venc_v > 0 else 0
                    res_rank[a['nome']] += (retorno - a['valor'])
        if res_rank:
            df_r = pd.DataFrame([{"Nome": k, "Lucro Total": money(v)} for k, v in res_rank.items()])
            st.write(df_r.to_html(escape=False, index=False), unsafe_allow_html=True)
