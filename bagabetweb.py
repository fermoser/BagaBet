import streamlit as st
import pandas as pd
import itertools
import random
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="BAGA BET PRO", layout="wide", page_icon="⚽")
conn = st.connection("gsheets", type=GSheetsConnection)

# --- CSS VISUAL (CORREÇÃO DE CORES) ---
st.markdown("""
    <style>
    .main { background-color: #f0f2f6; }
    .stButton>button { border-radius: 8px; font-weight: 600; }
    .placar-box {
        background-color: #ffffff; border: 2px solid #333;
        border-radius: 12px; padding: 10px; text-align: center;
    }
    .gols-finalizado { color: #1b5e20 !important; font-weight: 900; font-size: 2rem; }
    .gols-aberto { color: #333 !important; font-weight: 900; font-size: 2rem; }
    .fase-header {
        background: #111; color: #fff; padding: 10px;
        border-radius: 8px; margin: 15px 0; text-align: center; font-weight: bold;
    }
    /* Estilo das Chaves - Texto em Preto */
    .time-chave {
        color: #000000 !important; font-weight: bold; font-size: 1.1rem;
    }
    .vencedor-card {
        border: 2px solid #28a745 !important; background-color: #e8f5e9 !important;
    }
    </style>
    """, unsafe_allow_html=True)

# --- UTILITÁRIOS ---
def money(v):
    cor = "#28a745" if v > 0 else "#dc3545" if v < 0 else "#212529"
    val_fmt = f"R$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f'<span style="color:{cor}; font-weight:bold;">{val_fmt}</span>'

# --- FUNÇÕES DE DADOS ---
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

# --- ESTADO ---
if 'estagio' not in st.session_state: st.session_state.estagio = 'inicio'
if 'autenticado' not in st.session_state: st.session_state.autenticado = False
if 'menu' not in st.session_state: st.session_state.menu = "Jogos"

# --- TELA INICIAL ---
if st.session_state.estagio == 'inicio':
    st.markdown("<h1 style='text-align: center;'>⚽ BAGA BET PRO</h1>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    if c1.button("🏆 MODO LIGA", use_container_width=True):
        st.session_state.modo = "LIGA"; st.session_state.jogos, st.session_state.times = carregar_tudo("LIGA")
        st.session_state.estagio = 'painel'; st.rerun()
    if c2.button("⚔️ MODO COPA", use_container_width=True):
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
        st.title("⚙️ Configuração Copa")
        tipo_mata = st.radio("Formato da Copa", ["Mata-Mata Único", "Ida e Volta"], horizontal=True)
        qtd = st.number_input("Equipes", 2, 16, 4, step=2)
        nomes = [st.text_input(f"Equipe {i+1}", key=f"cp{i}") for i in range(qtd)]
        
        if st.button("🚀 GERAR TORNEIO"):
            equipes = [n.strip() for n in nomes if n.strip()]
            random.shuffle(equipes)
            fase = "QUARTAS" if qtd > 4 else "SEMI" if qtd > 2 else "FINAL"
            novos = [{"a": equipes[j], "b": equipes[j+1], "ga1": None, "gb1": None, "ga2": None, "gb2": None, 
                      "finalizado": False, "apostas": [], "fase": fase, "pen_a": 0, "pen_b": 0, 
                      "modo": "COPA", "tipo": "VOLTA" if tipo_mata == "Ida e Volta" else "UNICO"} for j in range(0, len(equipes), 2)]
            st.session_state.jogos = novos; salvar_tudo(novos, "COPA"); st.rerun()

        # Botão de Avançar Manual
        if st.session_state.jogos:
            fases_ordem = ["QUARTAS", "SEMI", "FINAL"]
            fase_atual = st.session_state.jogos[-1]['fase']
            jogos_fase = [j for j in st.session_state.jogos if j['fase'] == fase_atual]
            if all(j['finalizado'] for j in jogos_fase) and fase_atual != "FINAL":
                if st.button(f"➡️ CONFIRMAR VENCEDORES E IR PARA A PRÓXIMA FASE"):
                    venc = []
                    for j in jogos_fase:
                        soma_a = (j['ga1'] or 0) + (j['ga2'] or 0)
                        soma_b = (j['gb1'] or 0) + (j['gb2'] or 0)
                        if soma_a > soma_b: venc.append(j['a'])
                        elif soma_b > soma_a: venc.append(j['b'])
                        else: venc.append(j['a'] if j['pen_a'] > j['pen_b'] else j['b'])
                    
                    prox = fases_ordem[fases_ordem.index(fase_atual) + 1]
                    novos_j = [{"a": venc[i], "b": venc[i+1], "ga1": None, "gb1": None, "ga2": None, "gb2": None, 
                                "finalizado": False, "apostas": [], "fase": prox, "pen_a": 0, "pen_b": 0, 
                                "modo": "COPA", "tipo": j['tipo']} for i in range(0, len(venc), 2)]
                    st.session_state.jogos.extend(novos_j); salvar_tudo(st.session_state.jogos, "COPA"); st.rerun()

    # --- JOGOS ---
    elif st.session_state.menu == "Jogos":
        for fase in sorted(list(set(j['fase'] for j in st.session_state.jogos))):
            st.markdown(f"<div class='fase-header'>{fase}</div>", unsafe_allow_html=True)
            for i, j in enumerate(st.session_state.jogos):
                if j['fase'] == fase:
                    with st.container(border=True):
                        c1, c2, c3 = st.columns([2, 1, 2])
                        c1.markdown(f"<h3 style='text-align:right;'>{j['a']}</h3>", unsafe_allow_html=True)
                        
                        # Exibição de Placar (Unico ou Agregado)
                        if j['tipo'] == "UNICO":
                            txt_placar = f"{j['ga1'] if j['ga1'] is not None else '-'} : {j['gb1'] if j['gb1'] is not None else '-'}"
                        else:
                            txt_placar = f"({j['ga1'] or 0}) {j['ga2'] or 0} : {j['gb2'] or 0} ({j['gb1'] or 0})"
                        
                        c2.markdown(f"<div class='placar-box'><span class='{'gols-finalizado' if j['finalizado'] else 'gols-aberto'}'>{txt_placar}</span></div>", unsafe_allow_html=True)
                        c3.markdown(f"<h3 style='text-align:left;'>{j['b']}</h3>", unsafe_allow_html=True)
                        
                        if j['finalizado'] and (j['pen_a'] > 0 or j['pen_b'] > 0):
                            st.markdown(f"<p style='text-align:center;'>Pênaltis: **{j['pen_a']} x {j['pen_b']}**</p>", unsafe_allow_html=True)

                        if st.session_state.autenticado:
                            with st.expander("Preencher Placar"):
                                col1, col2 = st.columns(2)
                                if j['tipo'] == "UNICO":
                                    vga1 = col1.number_input(f"Gols {j['a']}", 0, 20, step=1, key=f"g1{i}{fase}")
                                    vgb1 = col2.number_input(f"Gols {j['b']}", 0, 20, step=1, key=f"g2{i}{fase}")
                                    vga2, vgb2 = 0, 0
                                else:
                                    st.write("**Jogo de Ida**")
                                    vga1 = col1.number_input(f"Ida {j['a']}", 0, 20, step=1, key=f"g1{i}{fase}")
                                    vgb1 = col2.number_input(f"Ida {j['b']}", 0, 20, step=1, key=f"g2{i}{fase}")
                                    st.write("**Jogo de Volta**")
                                    vga2 = col1.number_input(f"Volta {j['a']}", 0, 20, step=1, key=f"v1{i}{fase}")
                                    vgb2 = col2.number_input(f"Volta {j['b']}", 0, 20, step=1, key=f"v2{i}{fase}")
                                
                                pa, pb = 0, 0
                                if (vga1 + vga2) == (vgb1 + vgb2):
                                    st.warning("Empate no agregado! Informe os pênaltis:")
                                    p1, p2 = st.columns(2)
                                    pa = p1.number_input("Pên. A", 0, 20, step=1, key=f"pa{i}{fase}")
                                    pb = p2.number_input("Pên. B", 0, 20, step=1, key=f"pb{i}{fase}")
                                
                                if st.button("SALVAR", key=f"sv{i}{fase}"):
                                    j.update({'ga1': vga1, 'gb1': vgb1, 'ga2': vga2, 'gb2': vgb2, 'finalizado': True, 'pen_a': pa, 'pen_b': pb})
                                    salvar_tudo(st.session_state.jogos, "COPA"); st.rerun()

                        # Apostas
                        with st.expander("Apostas"):
                            if j['apostas']:
                                df_a = pd.DataFrame(j['apostas'])
                                if j['finalizado']:
                                    tot_a = (j['ga1'] or 0) + (j['ga2'] or 0)
                                    tot_b = (j['gb1'] or 0) + (j['gb2'] or 0)
                                    res = "A" if tot_a > tot_b else "B" if tot_b > tot_a else ("A" if j['pen_a'] > j['pen_b'] else "B")
                                    pote = sum(df_a['valor'])
                                    venc_v = sum(df_a[df_a['opcao'] == res]['valor'])
                                    df_a['Lucro'] = df_a.apply(lambda r: (r['valor']/venc_v * pote - r['valor']) if r['opcao'] == res and venc_v > 0 else -r['valor'], axis=1)
                                    df_a['Lucro'] = df_a['Lucro'].apply(money)
                                    st.write(df_a[['nome', 'opcao', 'valor', 'Lucro']].to_html(escape=False, index=False), unsafe_allow_html=True)
                                else: st.table(df_a)
                            if st.session_state.autenticado and not j['finalizado']:
                                with st.form(f"bet{i}{fase}"):
                                    n = st.text_input("Nome")
                                    v = st.number_input("R$", 1, 5000, 10, step=1)
                                    o = st.radio("Quem passa?", ["A", "B"], horizontal=True)
                                    if st.form_submit_button("Lançar"):
                                        j['apostas'].append({"nome": n, "valor": v, "opcao": o})
                                        salvar_tudo(st.session_state.jogos, "COPA"); st.rerun()

    # --- CHAVES (TABELA) ---
    elif st.session_state.menu == "Tabela":
        st.title("⚔️ Chaves do Mata-Mata")
        
        cols = st.columns(3)
        for idx, f_nome in enumerate(["QUARTAS", "SEMI", "FINAL"]):
            with cols[idx]:
                st.markdown(f"<div class='fase-header'>{f_nome}</div>", unsafe_allow_html=True)
                for jf in [j for j in st.session_state.jogos if j['fase'] == f_nome]:
                    # Lógica de quem venceu para destacar
                    tot_a = (jf['ga1'] or 0) + (jf['ga2'] or 0)
                    tot_b = (jf['gb1'] or 0) + (jf['gb2'] or 0)
                    venc_a = jf['finalizado'] and (tot_a > tot_b or (tot_a == tot_b and jf['pen_a'] > jf['pen_b']))
                    venc_b = jf['finalizado'] and (tot_b > tot_a or (tot_a == tot_b and jf['pen_b'] > jf['pen_a']))
                    
                    st.markdown(f"""
                        <div style='background:white; padding:10px; border-radius:10px; margin-bottom:10px; border:2px solid #333;'>
                            <div class='time-chave' style='padding:5px; {"border-left: 5px solid green; background:#e8f5e9;" if venc_a else ""}'>
                                {jf['a']} <span style='float:right;'>{tot_a if jf['finalizado'] else ""}</span>
                            </div>
                            <div style='height:2px; background:#eee; margin:5px 0;'></div>
                            <div class='time-chave' style='padding:5px; {"border-left: 5px solid green; background:#e8f5e9;" if venc_b else ""}'>
                                {jf['b']} <span style='float:right;'>{tot_b if jf['finalizado'] else ""}</span>
                            </div>
                        </div>
                    """, unsafe_allow_html=True)

    # --- RANKING ---
    elif st.session_state.menu == "Ranking":
        st.title("🤑 Ranking Financeiro")
        res_rank = {}
        for j in st.session_state.jogos:
            if j['finalizado'] and j['apostas']:
                tot_a, tot_b = (j['ga1'] or 0) + (j['ga2'] or 0), (j['gb1'] or 0) + (j['gb2'] or 0)
                res = "A" if tot_a > tot_b else "B" if tot_b > tot_a else ("A" if j['pen_a'] > j['pen_b'] else "B")
                pote = sum(a['valor'] for a in j['apostas'])
                venc_v = sum(a['valor'] for a in j['apostas'] if a['opcao'] == res)
                for a in j['apostas']:
                    res_rank.setdefault(a['nome'], 0)
                    retorno = (a['valor']/venc_v * pote) if a['opcao'] == res and venc_v > 0 else 0
                    res_rank[a['nome']] += (retorno - a['valor'])
        if res_rank:
            df_r = pd.DataFrame([{"Nome": k, "Lucro Total": money(v)} for k, v in res_rank.items()])
            st.write(df_r.to_html(escape=False, index=False), unsafe_allow_html=True)
