import streamlit as st
import pandas as pd
import itertools
import random
import math
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="BAGA BET PRO", layout="wide", page_icon="⚽")
conn = st.connection("gsheets", type=GSheetsConnection)

# --- CSS VISUAL ---
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stButton>button { border-radius: 8px; font-weight: 600; }
    .placar-box {
        background-color: #ffffff; border: 2px solid #e0e0e0;
        border-radius: 15px; padding: 10px; text-align: center;
    }
    .gols-finalizado { color: #1b5e20 !important; font-weight: 900; font-size: 2.2rem; }
    .gols-aberto { color: #444444 !important; font-weight: 900; font-size: 2.2rem; }
    .chave-title { background: #0747a6; color: white; padding: 5px; border-radius: 5px; text-align: center; font-weight: bold; margin-bottom: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --- UTILITÁRIOS ---
def money(v):
    try:
        cor = "#28a745" if v > 0 else "#dc3545" if v < 0 else "#212529"
        val_fmt = f"R$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return f'<span style="color:{cor}; font-weight:bold;">{val_fmt}</span>'
    except: return "R$ 0,00"

def money_raw(v):
    try: return f"R$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except: return "R$ 0,00"

def salvar_tudo(lista):
    if not lista:
        df_save = pd.DataFrame(columns=['a', 'b', 'ga', 'gb', 'finalizado', 'apostas_abertas', 'apostas', 'fase', 'id_jogo', 'pen_a', 'pen_b'])
    else:
        df_save = pd.DataFrame(lista)
        df_save['apostas'] = df_save['apostas'].apply(lambda x: "|".join([f"{a['nome']}:{a['valor']}:{a['opcao']}" for a in x]) if x else "")
    conn.update(data=df_save)
    st.cache_data.clear()

def carregar_tudo():
    df = conn.read(ttl=0)
    if df is None or df.empty: return [], []
    jogos = []
    times = set()
    for _, r in df.iterrows():
        # Parse Apostas
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
            "apostas": ap,
            "fase": str(r.get('fase', 'LIGA')),
            "id_jogo": int(r.get('id_jogo', 0)),
            "pen_a": int(r['pen_a']) if pd.notna(r.get('pen_a')) else 0,
            "pen_b": int(r['pen_b']) if pd.notna(r.get('pen_b')) else 0
        }
        jogos.append(j); times.add(j['a']); times.add(j['b'])
    return jogos, list(times)

# --- INICIALIZAÇÃO ---
if 'estagio' not in st.session_state: st.session_state.estagio = 'inicio'
if 'autenticado' not in st.session_state: st.session_state.autenticado = False
if 'jogos' not in st.session_state: st.session_state.jogos, st.session_state.times = carregar_tudo()
if 'menu' not in st.session_state: st.session_state.menu = "Jogos"

# --- TELA INICIAL ---
if st.session_state.estagio == 'inicio':
    st.markdown("<h1 style='text-align: center;'>⚽ BAGA BET PRO</h1>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    if c1.button("🏆 NOVA LIGA", use_container_width=True): 
        st.session_state.modo = "LIGA"; st.session_state.estagio = 'painel'; st.rerun()
    if c2.button("⚔️ NOVA COPA", use_container_width=True): 
        st.session_state.modo = "COPA"; st.session_state.estagio = 'painel'; st.rerun()
    if st.button("☁️ CARREGAR SALVO", use_container_width=True, type="primary"):
        st.session_state.jogos, st.session_state.times = carregar_tudo()
        st.session_state.estagio = 'painel'; st.rerun()

else:
    # --- SIDEBAR ---
    with st.sidebar:
        st.title("MENU")
        if not st.session_state.autenticado:
            if st.text_input("Senha", type="password") == "1234": st.session_state.autenticado = True; st.rerun()
        else:
            if st.button("Sair Admin"): st.session_state.autenticado = False; st.rerun()
        
        st.divider()
        if st.button("🏟️ JOGOS"): st.session_state.menu = "Jogos"; st.rerun()
        if st.button("📊 TABELA/CHAVE"): st.session_state.menu = "Tabela"; st.rerun()
        if st.button("🤑 RANKING"): st.session_state.menu = "Ranking"; st.rerun()
        if st.button("⚙️ ADMIN"): st.session_state.menu = "Admin"; st.rerun()

    sou_admin = st.session_state.autenticado

    # --- TELA ADMIN ---
    if st.session_state.menu == "Admin":
        st.title("⚙️ Configurações")
        
        # Sincronização (RESTORED)
        if st.button("🔄 ATUALIZAR NUVEM (Sync)", type="primary"):
            st.session_state.jogos, st.session_state.times = carregar_tudo()
            st.toast("Dados sincronizados!")
        
        st.divider()

        if st.session_state.modo == "COPA":
            st.subheader("⚔️ Configurar Mata-Mata")
            qtd = st.number_input("Qtd de Times (Par)", 2, 16, 4, step=2)
            tipo_copa = st.radio("Formato", ["Mata-Mata Único", "Ida e Volta"], horizontal=True)
            
            nomes = []
            cols = st.columns(2)
            for i in range(qtd):
                n = cols[i%2].text_input(f"Time {i+1}", key=f"t{i}")
                nomes.append(n)
            
            if st.button("🚀 GERAR CHAVES DA COPA"):
                times_validos = [t for t in nomes if t.strip()]
                random.shuffle(times_validos)
                novos = []
                # Gera a primeira fase
                for i in range(0, len(times_validos), 2):
                    novos.append({
                        "a": times_validos[i], "b": times_validos[i+1], "ga": None, "gb": None,
                        "finalizado": False, "apostas": [], "fase": "OITAVAS" if qtd==16 else "QUARTAS" if qtd==8 else "SEMI",
                        "id_jogo": i//2, "pen_a": 0, "pen_b": 0
                    })
                st.session_state.jogos = novos
                salvar_tudo(novos); st.session_state.menu = "Jogos"; st.rerun()

        elif st.session_state.modo == "LIGA":
            st.subheader("🏆 Configurar Liga")
            qtd = st.number_input("Qtd de Times", 2, 20, 4, step=1)
            nomes = [st.text_input(f"Time {i+1}", key=f"l{i}") for i in range(qtd)]
            if st.button("🚀 GERAR LIGA"):
                ts = [t for t in nomes if t.strip()]
                combs = list(itertools.combinations(ts, 2))
                novos = [{"a": c[0], "b": c[1], "ga": None, "gb": None, "finalizado": False, "apostas": [], "fase": "LIGA", "id_jogo": i} for i, c in enumerate(combs)]
                st.session_state.jogos = novos; salvar_tudo(novos); st.rerun()

    # --- TELA JOGOS ---
    elif st.session_state.menu == "Jogos":
        st.title(f"🏟️ Partidas - {st.session_state.modo}")
        for i, j in enumerate(st.session_state.jogos):
            with st.container(border=True):
                c1, c2, c3 = st.columns([2, 2, 2])
                ga, gb = (j['ga'] if j['ga'] is not None else "-"), (j['gb'] if j['gb'] is not None else "-")
                
                c1.markdown(f"<h3 style='text-align:right;'>{j['a']}</h3>", unsafe_allow_html=True)
                c2.markdown(f"<div class='placar-box'><span class='{'gols-finalizado' if j['finalizado'] else 'gols-aberto'}'>{ga} : {gb}</span></div>", unsafe_allow_html=True)
                c3.markdown(f"<h3 style='text-align:left;'>{j['b']}</h3>", unsafe_allow_html=True)

                if j['finalizado'] and j['pen_a'] + j['pen_b'] > 0:
                    st.caption(f"Pênaltis: {j['pen_a']} x {j['pen_b']}")

                if sou_admin:
                    with st.expander("Lançar Placar"):
                        col1, col2, col3 = st.columns(3)
                        vga = col1.number_input("Gols A", 0, 20, key=f"ga{i}", step=1)
                        vgb = col2.number_input("Gols B", 0, 20, key=f"gb{i}", step=1)
                        pen = st.toggle("Houve Pênaltis?", key=f"p{i}")
                        pa, pb = 0, 0
                        if pen:
                            pa = st.number_input("Pên. A", 0, 20, key=f"pa{i}", step=1)
                            pb = st.number_input("Pên. B", 0, 20, key=f"pb{i}", step=1)
                        
                        if st.button("FINALIZAR", key=f"btn{i}"):
                            st.session_state.jogos[i].update({'ga': vga, 'gb': vgb, 'finalizado': True, 'pen_a': pa, 'pen_b': pb})
                            salvar_tudo(st.session_state.jogos); st.rerun()

                # Apostas com Step=1 (RESTORED)
                t1, t2 = st.tabs(["Ver Apostas", "Nova Aposta"])
                with t1:
                    if j['apostas']:
                        df_a = pd.DataFrame(j['apostas'])
                        df_a['Palpite'] = df_a['opcao'].map({"A": j['a'], "B": j['b'], "E": "Empate"})
                        if j['finalizado']:
                            res = "A" if j['ga'] > j['gb'] else "B" if j['gb'] > j['ga'] else "E"
                            # Lógica de desempate por penaltis se empate no tempo normal
                            if j['ga'] == j['gb'] and (j['pen_a'] > 0 or j['pen_b'] > 0):
                                res = "A" if j['pen_a'] > j['pen_b'] else "B"
                            
                            pote = sum(df_a['valor'])
                            venc_v = sum(df_a[df_a['opcao'] == res]['valor'])
                            df_a['Retorno'] = df_a.apply(lambda r: (r['valor']/venc_v * pote) if r['opcao'] == res and venc_v > 0 else 0.0, axis=1)
                            df_a['Lucro'] = df_a['Retorno'] - df_a['valor']
                            st.write(df_a[['nome', 'Palpite', 'valor', 'Lucro']].to_html(escape=False), unsafe_allow_html=True)
                        else: st.table(df_a[['nome', 'Palpite', 'valor']])

                with t2:
                    if sou_admin and not j['finalizado']:
                        with st.form(f"f{i}"):
                            n = st.text_input("Nome")
                            v = st.number_input("R$", 1, 5000, 10, step=1) # STEP 1 UNIDADE
                            o = st.radio("Vence", [j['a'], "Empate", j['b']])
                            if st.form_submit_button("Salvar"):
                                cod = "A" if o == j['a'] else "B" if o == j['b'] else "E"
                                st.session_state.jogos[i]['apostas'].append({"nome": n, "valor": v, "opcao": cod})
                                salvar_tudo(st.session_state.jogos); st.rerun()

    # --- TELA CHAVES (TABELA) ---
    elif st.session_state.menu == "Tabela":
        if st.session_state.modo == "COPA":
            st.title("⚔️ Chaves do Mata-Mata")
            # Desenha as colunas da copa
            fases = ["OITAVAS", "QUARTAS", "SEMI", "FINAL"]
            # Aqui entrará a lógica visual de avanço de chaves
            st.info("As chaves progridem conforme os jogos são finalizados.")
        else:
            st.title("📊 Classificação Liga")
            # Tabela da liga (mesma lógica anterior)
