import streamlit as st
import pandas as pd
import itertools
import random
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="BAGA BET PRO", layout="wide", page_icon="⚽")
conn = st.connection("gsheets", type=GSheetsConnection)

# --- CSS VISUAL (ESTILO CHAVES) ---
st.markdown("""
    <style>
    .main { background-color: #f0f2f6; }
    .stButton>button { border-radius: 8px; font-weight: 600; }
    .placar-box {
        background-color: #ffffff; border: 2px solid #e0e0e0;
        border-radius: 12px; padding: 10px; text-align: center;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.05);
    }
    .gols-finalizado { color: #2e7d32 !important; font-weight: 900; font-size: 2rem; }
    .gols-aberto { color: #666 !important; font-weight: 900; font-size: 2rem; }
    
    /* Estilo das Chaves */
    .bracket-node {
        background: white; border: 1px solid #ccc; padding: 8px;
        border-radius: 8px; margin-bottom: 5px; text-align: center;
        font-weight: bold; min-height: 40px; display: flex; 
        align-items: center; justify-content: center;
    }
    .bracket-title {
        background: #0e1117; color: white; padding: 5px;
        border-radius: 5px; text-align: center; margin-bottom: 10px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- FUNÇÕES DE DADOS ---
def money(v):
    cor = "#28a745" if v > 0 else "#dc3545" if v < 0 else "#212529"
    val_fmt = f"R$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f'<span style="color:{cor}; font-weight:bold;">{val_fmt}</span>'

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
if 'modo' not in st.session_state: st.session_state.modo = "LIGA"

# --- TELA INICIAL ---
if st.session_state.estagio == 'inicio':
    st.markdown("<h1 style='text-align: center;'>⚽ BAGA BET PRO</h1>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    
    if c1.button("🏆 NOVO TORNEIO LIGA", use_container_width=True):
        st.session_state.modo = "LIGA"; st.session_state.estagio = 'painel'; st.session_state.menu = "Admin"; st.rerun()
    
    if c2.button("⚔️ NOVO TORNEIO COPA", use_container_width=True):
        st.session_state.modo = "COPA"; st.session_state.estagio = 'painel'; st.session_state.menu = "Admin"; st.rerun()

    if c3.button("☁️ CARREGAR ÚLTIMO SALVO", type="primary", use_container_width=True):
        st.session_state.jogos, st.session_state.times = carregar_tudo()
        # Tenta detectar modo pela fase do primeiro jogo
        if st.session_state.jogos:
            st.session_state.modo = "COPA" if st.session_state.jogos[0]['fase'] != "LIGA" else "LIGA"
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
            
            # Botão Sync (RESTORED)
            if st.button("🔄 ATUALIZAR NUVEM (FORÇAR SYNC)"):
                st.session_state.jogos, st.session_state.times = carregar_tudo()
                st.rerun()

            st.divider()

            if st.session_state.modo == "COPA":
                st.subheader("⚔️ Configurar Chaves do Mata-Mata")
                qtd = st.number_input("Número de Equipes (Sempre Par)", 2, 16, 4, step=2)
                
                nomes_copa = []
                cols = st.columns(2)
                for i in range(qtd):
                    # Memória de nomes se já existir
                    val_mem = st.session_state.times[i] if i < len(st.session_state.times) else ""
                    n = cols[i%2].text_input(f"Equipe {i+1}", value=val_mem, key=f"cp{i}")
                    nomes_copa.append(n)
                
                if st.button("🚀 INICIAR COPA (LIMPAR ANTERIOR)", type="primary"):
                    equipes = [n.strip() for n in nomes_copa if n.strip()]
                    if len(equipes) == qtd:
                        random.shuffle(equipes)
                        novos = []
                        fase_inicial = "QUARTAS" if qtd > 4 else "SEMI" if qtd > 2 else "FINAL"
                        for j in range(0, len(equipes), 2):
                            novos.append({"a": equipes[j], "b": equipes[j+1], "ga": None, "gb": None, 
                                          "finalizado": False, "apostas": [], "fase": fase_inicial, "pen_a": 0, "pen_b": 0})
                        st.session_state.jogos = novos
                        st.session_state.times = equipes
                        salvar_tudo(novos)
                        st.success("Copa Gerada!")
                        st.rerun()
            
            # --- Lógica de Avanço de Fase (Manual) ---
            if st.session_state.modo == "COPA" and st.session_state.jogos:
                st.divider()
                st.subheader("🏁 Avançar Vencedores")
                fase_atual = st.session_state.jogos[-1]['fase']
                jogos_fase = [j for j in st.session_state.jogos if j['fase'] == fase_atual]
                
                if all(j['finalizado'] for j in jogos_fase) and fase_atual != "FINAL":
                    if st.button(f"CONFIRMAR VENCEDORES DA {fase_atual} ➡️ PRÓXIMA FASE"):
                        vencedores = []
                        for j in jogos_fase:
                            # Decide vencedor (Gols ou Pênaltis)
                            if j['ga'] > j['gb']: vencedores.append(j['a'])
                            elif j['gb'] > j['ga']: vencedores.append(j['b'])
                            else: vencedores.append(j['a'] if j['pen_a'] > j['pen_b'] else j['b'])
                        
                        proxima = "SEMI" if fase_atual == "QUARTAS" else "FINAL"
                        novos_confrontos = []
                        for i in range(0, len(vencedores), 2):
                            novos_confrontos.append({"a": vencedores[i], "b": vencedores[i+1], "ga": None, "gb": None, 
                                                     "finalizado": False, "apostas": [], "fase": proxima, "pen_a": 0, "pen_b": 0})
                        
                        st.session_state.jogos.extend(novos_confrontos)
                        salvar_tudo(st.session_state.jogos)
                        st.rerun()

        else: st.error("Acesso restrito.")

    # --- ABA JOGOS ---
    elif st.session_state.menu == "Jogos":
        st.title("🏟️ Partidas em Andamento")
        for i, j in enumerate(st.session_state.jogos):
            with st.container(border=True):
                st.caption(f"Fase: {j['fase']}")
                c1, c2, c3 = st.columns([2, 1, 2])
                ga = j['ga'] if j['ga'] is not None else "-"
                gb = j['gb'] if j['gb'] is not None else "-"
                cls = "gols-finalizado" if j['finalizado'] else "gols-aberto"
                
                c1.markdown(f"<h3 style='text-align:right;'>{j['a']}</h3>", unsafe_allow_html=True)
                c2.markdown(f"<div class='placar-box'><span class='{cls}'>{ga} : {gb}</span></div>", unsafe_allow_html=True)
                c3.markdown(f"<h3 style='text-align:left;'>{j['b']}</h3>", unsafe_allow_html=True)

                if j['finalizado'] and (j['pen_a'] > 0 or j['pen_b'] > 0):
                    st.markdown(f"<p style='text-align:center;'>Pênaltis: **{j['pen_a']} x {j['pen_b']}**</p>", unsafe_allow_html=True)

                if st.session_state.autenticado:
                    with st.expander("Lançar Resultado"):
                        l1, l2 = st.columns(2)
                        vga = l1.number_input(f"Gols {j['a']}", 0, 20, value=0, step=1, key=f"ga{i}")
                        vgb = l2.number_input(f"Gols {j['b']}", 0, 20, value=0, step=1, key=f"gb{i}")
                        pa, pb = 0, 0
                        if vga == vgb and st.session_state.modo == "COPA":
                            st.warning("Empate em Mata-Mata! Informe os Pênaltis:")
                            p1, p2 = st.columns(2)
                            pa = p1.number_input("Pên. A", 0, 20, step=1, key=f"pa{i}")
                            pb = p2.number_input("Pên. B", 0, 20, step=1, key=f"pb{i}")
                        
                        if st.button("SALVAR PLACAR", key=f"btn{i}"):
                            st.session_state.jogos[i].update({'ga': vga, 'gb': vgb, 'finalizado': True, 'pen_a': pa, 'pen_b': pb})
                            salvar_tudo(st.session_state.jogos); st.rerun()

                # --- APOSTAS (STEP 1) ---
                tabs = st.tabs(["Apostas", "Nova Aposta"])
                with tabs[1]:
                    if not j['finalizado'] and st.session_state.autenticado:
                        with st.form(f"f{i}", clear_on_submit=True):
                            n = st.text_input("Nome")
                            v = st.number_input("Valor R$", 1, 5000, 10, step=1)
                            o = st.radio("Palpite", [j['a'], "Empate", j['b']], horizontal=True)
                            if st.form_submit_button("Confirmar"):
                                code = "A" if o==j['a'] else "B" if o==j['b'] else "E"
                                st.session_state.jogos[i]['apostas'].append({"nome": n, "valor": v, "opcao": code})
                                salvar_tudo(st.session_state.jogos); st.rerun()

    # --- ABA TABELA / CHAVES ---
    elif st.session_state.menu == "Tabela":
        if st.session_state.modo == "COPA":
            st.title("⚔️ Chaves do Torneio")
            fases_disponiveis = ["QUARTAS", "SEMI", "FINAL"]
            cols_f = st.columns(len(fases_disponiveis))
            
            for idx, fase in enumerate(fases_disponiveis):
                with cols_f[idx]:
                    st.markdown(f"<div class='bracket-title'>{fase}</div>", unsafe_allow_html=True)
                    jogos_f = [jog for jog in st.session_state.jogos if jog['fase'] == fase]
                    if not jogos_f:
                        st.markdown("<div class='bracket-node' style='color:#ccc;'>Aguardando...</div>", unsafe_allow_html=True)
                    for jf in jogos_f:
                        cor_a = "color:#2e7d32;" if jf['finalizado'] and (jf['ga'] > jf['gb'] or jf['pen_a'] > jf['pen_b']) else ""
                        cor_b = "color:#2e7d32;" if jf['finalizado'] and (jf['gb'] > jf['ga'] or jf['pen_b'] > jf['pen_a']) else ""
                        st.markdown(f"""
                            <div style='border: 1px solid #ddd; padding: 5px; border-radius: 5px; margin-bottom: 10px; background: white;'>
                                <div style='{cor_a}'>{jf['a']} ({jf['ga'] if jf['ga'] is not None else ""})</div>
                                <div style='border-top: 1px dashed #eee; margin: 3px 0;'></div>
                                <div style='{cor_b}'>{jf['b']} ({jf['gb'] if jf['gb'] is not None else ""})</div>
                            </div>
                        """, unsafe_allow_html=True)
        else:
            st.title("📊 Classificação Liga")
            # Tabela da Liga Simplificada
            stats = {t: {"P":0, "V":0} for t in st.session_state.times}
            for j in st.session_state.jogos:
                if j['finalizado']:
                    if j['ga'] > j['gb']: stats[j['a']]["P"]+=3; stats[j['a']]["V"]+=1
                    elif j['gb'] > j['ga']: stats[j['b']]["P"]+=3; stats[j['b']]["V"]+=1
                    else: stats[j['a']]["P"]+=1; stats[j['b']]["P"]+=1
            st.table(pd.DataFrame(stats).T.sort_values("P", ascending=False))
