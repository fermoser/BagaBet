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
    .gols-finalizado { color: #1b5e20 !important; font-weight: 900; font-size: 2.2rem; }
    .gols-aberto { color: #666 !important; font-weight: 900; font-size: 2.2rem; }
    .fase-header {
        background: #0e1117; color: white; padding: 8px;
        border-radius: 8px; margin: 15px 0; text-align: center; font-weight: bold;
    }
    </style>
    """, unsafe_allow_html=True)

# --- UTILITÁRIOS ---
def money(v):
    cor = "#28a745" if v > 0 else "#dc3545" if v < 0 else "#212529"
    val_fmt = f"R$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f'<span style="color:{cor}; font-weight:bold;">{val_fmt}</span>'

def money_raw(v):
    return f"R$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# --- FUNÇÕES DE DADOS (COM TRAVA DE MODO) ---
def carregar_tudo(modo_atual):
    try:
        df = conn.read(ttl=0)
        if df is None or df.empty: return [], []
        # Filtra apenas jogos do modo atual (LIGA ou COPA)
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
                "ga": int(r['ga']) if pd.notna(r['ga']) else None,
                "gb": int(r['gb']) if pd.notna(r['gb']) else None,
                "finalizado": str(r.get('finalizado')).upper() == "TRUE",
                "apostas": ap, "fase": str(r.get('fase')), "modo": str(r.get('modo')),
                "pen_a": int(r['pen_a']) if pd.notna(r.get('pen_a')) else 0,
                "pen_b": int(r['pen_b']) if pd.notna(r.get('pen_b')) else 0
            }
            jogos.append(j); times.add(j['a']); times.add(j['b'])
        return jogos, list(times)
    except: return [], []

def salvar_tudo(lista_nova, modo_atual):
    # Primeiro lemos o que já existe de OUTROS modos para não apagar
    try:
        df_antigo = conn.read(ttl=0)
        df_outros = df_antigo[df_antigo['modo'] != modo_atual] if df_antigo is not None else pd.DataFrame()
    except:
        df_outros = pd.DataFrame()

    if not lista_nova:
        df_save = df_outros
    else:
        df_atual = pd.DataFrame(lista_nova)
        df_atual['apostas'] = df_atual['apostas'].apply(lambda x: "|".join([f"{a['nome']}:{a['valor']}:{a['opcao']}" for a in x]) if x else "")
        df_atual['finalizado'] = df_atual['finalizado'].apply(lambda x: "TRUE" if x else "FALSE")
        df_atual['modo'] = modo_atual
        df_save = pd.concat([df_outros, df_atual], ignore_index=True)
    
    conn.update(data=df_save)
    st.cache_data.clear()

# --- ESTADO INICIAL ---
if 'estagio' not in st.session_state: st.session_state.estagio = 'inicio'
if 'autenticado' not in st.session_state: st.session_state.autenticado = False
if 'menu' not in st.session_state: st.session_state.menu = "Jogos"
if 'modo' not in st.session_state: st.session_state.modo = "LIGA"

# --- TELA INICIAL ---
if st.session_state.estagio == 'inicio':
    st.markdown("<h1 style='text-align: center;'>⚽ BAGA BET PRO</h1>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    if c1.button("🏆 LIGA", use_container_width=True):
        st.session_state.modo = "LIGA"; st.session_state.jogos, st.session_state.times = carregar_tudo("LIGA")
        st.session_state.estagio = 'painel'; st.rerun()
    if c2.button("⚔️ COPA", use_container_width=True):
        st.session_state.modo = "COPA"; st.session_state.jogos, st.session_state.times = carregar_tudo("COPA")
        st.session_state.estagio = 'painel'; st.rerun()

else:
    # --- SIDEBAR ---
    with st.sidebar:
        st.header(f"MODO: {st.session_state.modo}")
        if not st.session_state.autenticado:
            if st.text_input("Senha Admin", type="password") == "1234": st.session_state.autenticado = True; st.rerun()
        else:
            if st.button("Sair Admin"): st.session_state.autenticado = False; st.rerun()
        
        st.divider()
        if st.button("🏟️ VER JOGOS", use_container_width=True): st.session_state.menu = "Jogos"; st.rerun()
        if st.button("📊 TABELA / CHAVES", use_container_width=True): st.session_state.menu = "Tabela"; st.rerun()
        if st.button("🤑 RANKING", use_container_width=True): st.session_state.menu = "Ranking"; st.rerun()
        if st.button("⚙️ ADMIN", use_container_width=True): st.session_state.menu = "Admin"; st.rerun()
        st.divider()
        if st.button("🏠 INÍCIO", use_container_width=True): st.session_state.estagio = 'inicio'; st.rerun()

    # --- ABA ADMIN ---
    if st.session_state.menu == "Admin" and st.session_state.autenticado:
        st.title("⚙️ Gerenciamento")
        if st.button("🔄 ATUALIZAR NUVEM (Sync)"):
            st.session_state.jogos, st.session_state.times = carregar_tudo(st.session_state.modo); st.rerun()

        if st.session_state.modo == "COPA":
            st.subheader("Configurar Times da Copa")
            qtd = st.number_input("Qtd Times", 2, 16, 4, step=2)
            nomes = [st.text_input(f"Equipe {i+1}", key=f"cp{i}") for i in range(qtd)]
            if st.button("🚀 GERAR PRIMEIRA FASE"):
                equipes = [n.strip() for n in nomes if n.strip()]
                random.shuffle(equipes)
                fase_ini = "QUARTAS" if qtd > 4 else "SEMI" if qtd > 2 else "FINAL"
                novos = [{"a": equipes[j], "b": equipes[j+1], "ga": None, "gb": None, "finalizado": False, "apostas": [], "fase": fase_ini, "pen_a": 0, "pen_b": 0, "modo": "COPA"} for j in range(0, len(equipes), 2)]
                st.session_state.jogos = novos; salvar_tudo(novos, "COPA"); st.rerun()

            # Avanço de Fase
            if st.session_state.jogos:
                fases_ordem = ["QUARTAS", "SEMI", "FINAL"]
                fase_atual = st.session_state.jogos[-1]['fase']
                jogos_fase = [j for j in st.session_state.jogos if j['fase'] == fase_atual]
                if all(j['finalizado'] for j in jogos_fase) and fase_atual != "FINAL":
                    if st.button(f"➡️ CONFIRMAR VENCEDORES E GERAR {fases_ordem[fases_ordem.index(fase_atual)+1]}"):
                        venc = []
                        for j in jogos_fase:
                            if j['ga'] > j['gb']: venc.append(j['a'])
                            elif j['gb'] > j['ga']: venc.append(j['b'])
                            else: venc.append(j['a'] if j['pen_a'] > j['pen_b'] else j['b'])
                        prox = fases_ordem[fases_ordem.index(fase_atual) + 1]
                        novos_j = [{"a": venc[i], "b": venc[i+1], "ga": None, "gb": None, "finalizado": False, "apostas": [], "fase": prox, "pen_a": 0, "pen_b": 0, "modo": "COPA"} for i in range(0, len(venc), 2)]
                        st.session_state.jogos.extend(novos_j)
                        salvar_tudo(st.session_state.jogos, "COPA"); st.rerun()

    # --- ABA JOGOS ---
    elif st.session_state.menu == "Jogos":
        for fase in sorted(list(set(j['fase'] for j in st.session_state.jogos))):
            st.markdown(f"<div class='fase-header'>{fase}</div>", unsafe_allow_html=True)
            for i, j in enumerate(st.session_state.jogos):
                if j['fase'] == fase:
                    with st.container(border=True):
                        c1, c2, c3 = st.columns([2, 1, 2])
                        c1.markdown(f"<h3 style='text-align:right;'>{j['a']}</h3>", unsafe_allow_html=True)
                        ga, gb = (j['ga'] if j['ga'] is not None else "-"), (j['gb'] if j['gb'] is not None else "-")
                        c2.markdown(f"<div class='placar-box'><span class='{'gols-finalizado' if j['finalizado'] else 'gols-aberto'}'>{ga} : {gb}</span></div>", unsafe_allow_html=True)
                        c3.markdown(f"<h3 style='text-align:left;'>{j['b']}</h3>", unsafe_allow_html=True)

                        if j['finalizado'] and (j['pen_a'] > 0 or j['pen_b'] > 0):
                            st.markdown(f"<p style='text-align:center;'>Pênaltis: **{j['pen_a']} x {j['pen_b']}**</p>", unsafe_allow_html=True)

                        if st.session_state.autenticado:
                            with st.expander("Lançar Resultado"):
                                col1, col2 = st.columns(2)
                                vga = col1.number_input(f"Gols {j['a']}", 0, 20, step=1, key=f"ga{i}{fase}")
                                vgb = col2.number_input(f"Gols {j['b']}", 0, 20, step=1, key=f"gb{i}{fase}")
                                pa, pb = 0, 0
                                if vga == vgb and st.session_state.modo == "COPA":
                                    p1, p2 = st.columns(2)
                                    pa = p1.number_input("Pên. A", 0, 20, step=1, key=f"pa{i}{fase}")
                                    pb = p2.number_input("Pên. B", 0, 20, step=1, key=f"pb{i}{fase}")
                                if st.button("SALVAR PLACAR", key=f"btn{i}{fase}"):
                                    j.update({'ga': vga, 'gb': vgb, 'finalizado': True, 'pen_a': pa, 'pen_b': pb})
                                    salvar_tudo(st.session_state.jogos, st.session_state.modo); st.rerun()

                        # --- [RESTORED] APOSTAS DETALHADAS ---
                        tab_v, tab_n = st.tabs(["Ver Apostas", "Nova Aposta"])
                        with tab_v:
                            if j['apostas']:
                                df_a = pd.DataFrame(j['apostas'])
                                if j['finalizado']:
                                    res = "A" if j['ga'] > j['gb'] else "B" if j['gb'] > j['ga'] else "E"
                                    if res == "E" and st.session_state.modo == "COPA" and (j['pen_a'] != j['pen_b']):
                                        res = "A" if j['pen_a'] > j['pen_b'] else "B"
                                    
                                    pote = sum(df_a['valor'])
                                    venc_v = sum(df_a[df_a['opcao'] == res]['valor'])
                                    df_a['Retorno'] = df_a.apply(lambda r: (r['valor']/venc_v * pote) if r['opcao'] == res and venc_v > 0 else 0.0, axis=1)
                                    df_a['Lucro'] = df_a['Retorno'] - df_a['valor']
                                    df_show = df_a.copy()
                                    df_show['Lucro'] = df_show['Lucro'].apply(money)
                                    st.write(df_show[['nome', 'opcao', 'valor', 'Lucro']].to_html(escape=False, index=False), unsafe_allow_html=True)
                                else: st.table(df_a)
                        with tab_n:
                            if st.session_state.autenticado and not j['finalizado']:
                                with st.form(f"f{i}{fase}"):
                                    n = st.text_input("Nome")
                                    v = st.number_input("R$", 1, 5000, 10, step=1)
                                    o = st.radio("Vence", ["A", "E", "B"], horizontal=True)
                                    if st.form_submit_button("Lançar"):
                                        j['apostas'].append({"nome": n, "valor": v, "opcao": o})
                                        salvar_tudo(st.session_state.jogos, st.session_state.modo); st.rerun()

    # --- ABA RANKING ---
    elif st.session_state.menu == "Ranking":
        st.title("🤑 Ranking Financeiro")
        res_rank = {}
        for j in st.session_state.jogos:
            if j['finalizado'] and j['apostas']:
                res = "A" if j['ga'] > j['gb'] else "B" if j['gb'] > j['ga'] else "E"
                if res == "E" and st.session_state.modo == "COPA":
                    res = "A" if j['pen_a'] > j['pen_b'] else "B"
                
                pote = sum(a['valor'] for a in j['apostas'])
                venc_v = sum(a['valor'] for a in j['apostas'] if a['opcao'] == res)
                for a in j['apostas']:
                    res_rank.setdefault(a['nome'], 0)
                    retorno = (a['valor']/venc_v * pote) if a['opcao'] == res and venc_v > 0 else 0
                    res_rank[a['nome']] += (retorno - a['valor'])
        
        if res_rank:
            df_r = pd.DataFrame([{"Nome": k, "Lucro Total": money(v)} for k, v in res_rank.items()])
            st.write(df_r.to_html(escape=False, index=False), unsafe_allow_html=True)

    # --- ABA TABELA / CHAVES ---
    elif st.session_state.menu == "Tabela":
        if st.session_state.modo == "COPA":
            st.title("⚔️ Chaves do Mata-Mata")
            cols = st.columns(3)
            for idx, f_nome in enumerate(["QUARTAS", "SEMI", "FINAL"]):
                with cols[idx]:
                    st.markdown(f"<div class='fase-header'>{f_nome}</div>", unsafe_allow_html=True)
                    for jf in [j for j in st.session_state.jogos if j['fase'] == f_nome]:
                        v_a = "border:2px solid green;" if jf['finalizado'] and (jf['ga'] > jf['gb'] or jf['pen_a'] > jf['pen_b']) else ""
                        v_b = "border:2px solid green;" if jf['finalizado'] and (jf['gb'] > jf['ga'] or jf['pen_b'] > jf['pen_a']) else ""
                        st.markdown(f"""
                            <div style='background:white; padding:10px; border-radius:10px; margin-bottom:10px; border:1px solid #ccc;'>
                                <div style='padding:5px; {v_a}'>{jf['a']} <span style='float:right;'>{jf['ga'] if jf['ga'] is not None else ""}</span></div>
                                <div style='padding:5px; {v_b}'>{jf['b']} <span style='float:right;'>{jf['gb'] if jf['gb'] is not None else ""}</span></div>
                            </div>
                        """, unsafe_allow_html=True)
