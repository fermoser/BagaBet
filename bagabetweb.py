import streamlit as st
import pandas as pd
import itertools
import random
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="BAGA BET PRO", layout="wide", page_icon="⚽")
conn = st.connection("gsheets", type=GSheetsConnection)

# --- CSS VISUAL ---
st.markdown("""
    <style>
    .main { background-color: #f0f2f6; }
    .stButton>button { border-radius: 8px; font-weight: 600; }
    .placar-box {
        background-color: #ffffff; border: 2px solid #e0e0e0;
        border-radius: 12px; padding: 10px; text-align: center;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.05);
    }
    .gols-finalizado { color: #1b5e20 !important; font-weight: 900; font-size: 2rem; }
    .gols-aberto { color: #666 !important; font-weight: 900; font-size: 2rem; }
    .fase-header {
        background: #0e1117; color: white; padding: 10px;
        border-radius: 8px; margin: 20px 0 10px 0; text-align: center;
    }
    </style>
    """, unsafe_allow_html=True)

# --- FUNÇÕES DE DADOS ---
def carregar_tudo():
    df = conn.read(ttl=0)
    if df is None or df.empty: return [], []
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
            "ga": int(r['ga']) if pd.notna(r['ga']) else None,
            "gb": int(r['gb']) if pd.notna(r['gb']) else None,
            "finalizado": str(r.get('finalizado')).upper() == "TRUE",
            "apostas": ap, "fase": str(r.get('fase', 'LIGA')),
            "pen_a": int(r['pen_a']) if pd.notna(r.get('pen_a', 0)) else 0,
            "pen_b": int(r['pen_b']) if pd.notna(r.get('pen_b', 0)) else 0
        }
        jogos.append(j); times.add(j['a']); times.add(j['b'])
    return jogos, list(times)

def salvar_tudo(lista):
    if not lista:
        df_save = pd.DataFrame(columns=['a', 'b', 'ga', 'gb', 'finalizado', 'apostas', 'fase', 'pen_a', 'pen_b'])
    else:
        df_save = pd.DataFrame(lista)
        df_save['apostas'] = df_save['apostas'].apply(lambda x: "|".join([f"{a['nome']}:{a['valor']}:{a['opcao']}" for a in x]) if x else "")
        df_save['finalizado'] = df_save['finalizado'].apply(lambda x: "TRUE" if x else "FALSE")
    conn.update(data=df_save)
    st.cache_data.clear()

# --- ESTADO INICIAL ---
if 'estagio' not in st.session_state: st.session_state.estagio = 'inicio'
if 'autenticado' not in st.session_state: st.session_state.autenticado = False
if 'jogos' not in st.session_state: st.session_state.jogos, st.session_state.times = carregar_tudo()
if 'menu' not in st.session_state: st.session_state.menu = "Jogos"
if 'modo' not in st.session_state: st.session_state.modo = "COPA"

# --- TELA INICIAL ---
if st.session_state.estagio == 'inicio':
    st.markdown("<h1 style='text-align: center;'>⚽ BAGA BET PRO</h1>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    if c1.button("🏆 NOVO TORNEIO LIGA", use_container_width=True):
        st.session_state.modo = "LIGA"; st.session_state.estagio = 'painel'; st.session_state.menu = "Admin"; st.rerun()
    if c2.button("⚔️ NOVO TORNEIO COPA", use_container_width=True):
        st.session_state.modo = "COPA"; st.session_state.estagio = 'painel'; st.session_state.menu = "Admin"; st.rerun()
    if c3.button("☁️ CARREGAR SALVO", type="primary", use_container_width=True):
        st.session_state.jogos, st.session_state.times = carregar_tudo()
        if st.session_state.jogos: st.session_state.modo = "COPA" if st.session_state.jogos[0]['fase'] != "LIGA" else "LIGA"
        st.session_state.estagio = 'painel'; st.rerun()

else:
    # --- SIDEBAR ---
    with st.sidebar:
        st.markdown(f"### 🏟️ MODO: {st.session_state.modo}")
        if not st.session_state.autenticado:
            if st.text_input("Senha Admin", type="password") == "1234": st.session_state.autenticado = True; st.rerun()
        else:
            if st.button("Sair Admin"): st.session_state.autenticado = False; st.rerun()
        
        st.divider()
        if st.button("🏟️ VER JOGOS", use_container_width=True): st.session_state.menu = "Jogos"; st.rerun()
        if st.button("📊 CHAVES / TABELA", use_container_width=True): st.session_state.menu = "Tabela"; st.rerun()
        if st.button("🤑 RANKING", use_container_width=True): st.session_state.menu = "Ranking"; st.rerun()
        if st.button("⚙️ PAINEL ADMIN", use_container_width=True): st.session_state.menu = "Admin"; st.rerun()
        st.divider()
        if st.button("🏠 MENU INICIAL", use_container_width=True): st.session_state.estagio = 'inicio'; st.rerun()

    # --- ABA ADMIN ---
    if st.session_state.menu == "Admin":
        if st.session_state.autenticado:
            st.title("⚙️ Painel do Organizador")
            if st.button("🔄 ATUALIZAR NUVEM (Sync)"):
                st.session_state.jogos, st.session_state.times = carregar_tudo(); st.rerun()

            st.divider()
            if st.session_state.modo == "COPA":
                st.subheader("⚔️ Iniciar Novo Mata-Mata")
                qtd = st.number_input("Número de Equipes", 2, 16, 4, step=2)
                nomes = []
                cols = st.columns(2)
                for i in range(qtd):
                    n = cols[i%2].text_input(f"Equipe {i+1}", key=f"cp{i}")
                    nomes.append(n)
                
                if st.button("🚀 GERAR PRIMEIRA FASE", type="primary"):
                    equipes = [n.strip() for n in nomes if n.strip()]
                    if len(equipes) == qtd:
                        random.shuffle(equipes)
                        fase_ini = "QUARTAS" if qtd > 4 else "SEMI" if qtd > 2 else "FINAL"
                        novos = [{"a": equipes[j], "b": equipes[j+1], "ga": None, "gb": None, "finalizado": False, "apostas": [], "fase": fase_ini, "pen_a": 0, "pen_b": 0} for j in range(0, len(equipes), 2)]
                        st.session_state.jogos = novos; salvar_tudo(novos); st.rerun()

            # --- BOTÃO DE AVANÇO (MANUAL) ---
            if st.session_state.modo == "COPA" and st.session_state.jogos:
                fases_ordem = ["QUARTAS", "SEMI", "FINAL"]
                fase_atual = st.session_state.jogos[-1]['fase']
                jogos_fase = [j for j in st.session_state.jogos if j['fase'] == fase_atual]
                
                if all(j['finalizado'] for j in jogos_fase) and fase_atual != "FINAL":
                    st.divider()
                    st.success(f"Todos os jogos da {fase_atual} foram finalizados!")
                    if st.button(f"➡️ GERAR CONFRONTOS DA PRÓXIMA FASE", use_container_width=True):
                        vencedores = []
                        for j in jogos_fase:
                            if j['ga'] > j['gb']: vencedores.append(j['a'])
                            elif j['gb'] > j['ga']: vencedores.append(j['b'])
                            else: vencedores.append(j['a'] if j['pen_a'] > j['pen_b'] else j['b'])
                        
                        prox_fase = fases_ordem[fases_ordem.index(fase_atual) + 1]
                        novos_confrontos = [{"a": vencedores[i], "b": vencedores[i+1], "ga": None, "gb": None, "finalizado": False, "apostas": [], "fase": prox_fase, "pen_a": 0, "pen_b": 0} for i in range(0, len(vencedores), 2)]
                        st.session_state.jogos.extend(novos_confrontos)
                        salvar_tudo(st.session_state.jogos)
                        st.rerun()

    # --- ABA JOGOS ---
    elif st.session_state.menu == "Jogos":
        if not st.session_state.jogos:
            st.info("Nenhum jogo criado.")
        else:
            # Agrupar por fase
            fases_no_app = []
            for j in st.session_state.jogos:
                if j['fase'] not in fases_no_app: fases_no_app.append(j['fase'])
            
            for f in fases_no_app:
                st.markdown(f"<div class='fase-header'>{f}</div>", unsafe_allow_html=True)
                jogos_f = [j for j in st.session_state.jogos if j['fase'] == f]
                
                for i, j in enumerate(st.session_state.jogos):
                    if j['fase'] == f:
                        with st.container(border=True):
                            c1, c2, c3 = st.columns([2, 1, 2])
                            ga, gb = (j['ga'] if j['ga'] is not None else "-"), (j['gb'] if j['gb'] is not None else "-")
                            
                            c1.markdown(f"<h3 style='text-align:right;'>{j['a']}</h3>", unsafe_allow_html=True)
                            c2.markdown(f"<div class='placar-box'><span class='{'gols-finalizado' if j['finalizado'] else 'gols-aberto'}'>{ga} : {gb}</span></div>", unsafe_allow_html=True)
                            c3.markdown(f"<h3 style='text-align:left;'>{j['b']}</h3>", unsafe_allow_html=True)

                            if j['finalizado'] and (j['pen_a'] > 0 or j['pen_b'] > 0):
                                st.markdown(f"<p style='text-align:center;'>Pênaltis: **{j['pen_a']} x {j['pen_b']}**</p>", unsafe_allow_html=True)

                            if st.session_state.autenticado:
                                with st.expander("Lançar Placar"):
                                    l1, l2 = st.columns(2)
                                    vga = l1.number_input(f"Gols {j['a']}", 0, 20, step=1, key=f"ga{f}{i}")
                                    vgb = l2.number_input(f"Gols {j['b']}", 0, 20, step=1, key=f"gb{f}{i}")
                                    pa, pb = 0, 0
                                    if vga == vgb and st.session_state.modo == "COPA":
                                        p1, p2 = st.columns(2)
                                        pa = p1.number_input("Pên. A", 0, 20, step=1, key=f"pa{f}{i}")
                                        pb = p2.number_input("Pên. B", 0, 20, step=1, key=f"pb{f}{i}")
                                    if st.button("SALVAR", key=f"btn{f}{i}"):
                                        j.update({'ga': vga, 'gb': vgb, 'finalizado': True, 'pen_a': pa, 'pen_b': pb})
                                        salvar_tudo(st.session_state.jogos); st.rerun()

                            # Apostas Step=1
                            t1, t2 = st.tabs(["Ver Apostas", "Nova Aposta"])
                            with t2:
                                if not j['finalizado'] and st.session_state.autenticado:
                                    with st.form(f"form{f}{i}", clear_on_submit=True):
                                        n = st.text_input("Nome")
                                        v = st.number_input("Valor R$", 1, 5000, 10, step=1)
                                        o = st.radio("Palpite", [j['a'], "Empate", j['b']], horizontal=True)
                                        if st.form_submit_button("Confirmar"):
                                            cod = "A" if o==j['a'] else "B" if o==j['b'] else "E"
                                            j['apostas'].append({"nome": n, "valor": v, "opcao": cod})
                                            salvar_tudo(st.session_state.jogos); st.rerun()

    # --- ABA TABELA / CHAVES ---
    elif st.session_state.menu == "Tabela":
        if st.session_state.modo == "COPA":
            st.title("⚔️ Chaves do Torneio")
            fases_visual = ["QUARTAS", "SEMI", "FINAL"]
            cols = st.columns(len(fases_visual))
            for idx, fase in enumerate(fases_visual):
                with cols[idx]:
                    st.markdown(f"<div class='fase-header' style='background:#1f4e79;'>{fase}</div>", unsafe_allow_html=True)
                    jogos_f = [jog for jog in st.session_state.jogos if jog['fase'] == fase]
                    for jf in jogos_f:
                        venc_a = "border: 2px solid #2e7d32; background:#e8f5e9;" if jf['finalizado'] and (jf['ga'] > jf['gb'] or jf['pen_a'] > jf['pen_b']) else "background:white;"
                        venc_b = "border: 2px solid #2e7d32; background:#e8f5e9;" if jf['finalizado'] and (jf['gb'] > jf['ga'] or jf['pen_b'] > jf['pen_a']) else "background:white;"
                        st.markdown(f"""
                            <div style='border:1px solid #ccc; border-radius:10px; padding:8px; margin-bottom:15px; background:#f9f9f9;'>
                                <div style='padding:5px; border-radius:5px; {venc_a}'>{jf['a']} <span style='float:right;'>{jf['ga'] if jf['ga'] is not None else ""}</span></div>
                                <div style='height:5px;'></div>
                                <div style='padding:5px; border-radius:5px; {venc_b}'>{jf['b']} <span style='float:right;'>{jf['gb'] if jf['gb'] is not None else ""}</span></div>
                            </div>
                        """, unsafe_allow_html=True)
