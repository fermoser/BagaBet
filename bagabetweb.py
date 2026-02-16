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
    .main { background-color: #f8f9fa; }
    .stButton>button { border-radius: 8px; font-weight: 600; text-transform: uppercase; }
    
    /* Box do Placar - Ajuste Fino */
    div[data-testid="stVerticalBlock"] > div > div[data-testid="stVerticalBlock"] {
        background-color: transparent;
    }
    .placar-box {
        background-color: #ffffff; 
        border: 2px solid #e0e0e0;
        border-radius: 15px; 
        padding: 15px; 
        text-align: center;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
    }
    .gols-finalizado { 
        color: #2e7d32; /* Verde Esmeralda Sóbrio */
        font-weight: 900; 
        font-size: 2.8rem;
        font-family: 'Arial Black', sans-serif;
    }
    .gols-aberto { 
        color: #b0bec5; /* Cinza claro placeholder */
        font-weight: 900;
        font-size: 2.8rem;
        font-family: 'Arial Black', sans-serif;
    }
    .modo-badge {
        background-color: #0d6efd; color: white; padding: 4px 8px; border-radius: 4px; font-size: 0.8rem;
    }
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

# --- DADOS ---
def carregar_tudo():
    try:
        df = conn.read(ttl=0)
        if df is None or df.empty: return [], [], df
        
        jogos = []
        times = set()
        for _, row in df.iterrows():
            fina = str(row.get('finalizado')).strip().upper() in ["TRUE", "1", "T"]
            aberta = str(row.get('apostas_abertas')).strip().upper() in ["TRUE", "1", "T"] if 'apostas_abertas' in row else True
            
            # Parse Apostas
            ap_lista = []
            raw_ap = str(row.get('apostas'))
            if raw_ap not in ["nan", "None", ""]:
                for item in raw_ap.split("|"):
                    p = item.split(":")
                    if len(p) == 3: ap_lista.append({"nome": p[0], "valor": float(p[1]), "opcao": p[2].upper()})

            j = {
                "a": str(row.get('a', '')), "b": str(row.get('b', '')),
                "ga": int(float(row.get('ga'))) if pd.notna(row.get('ga')) else None,
                "gb": int(float(row.get('gb'))) if pd.notna(row.get('gb')) else None,
                "finalizado": fina, "apostas_abertas": aberta, "apostas": ap_lista
            }
            jogos.append(j); times.add(j['a']); times.add(j['b'])
        return jogos, list(times), df
    except:
        return [], [], pd.DataFrame()

def salvar_tudo(lista):
    if not lista:
        df_save = pd.DataFrame(columns=['a', 'b', 'ga', 'gb', 'finalizado', 'apostas_abertas', 'apostas'])
    else:
        df_save = pd.DataFrame(lista)
        df_save['apostas'] = df_save['apostas'].apply(lambda x: "|".join([f"{a['nome']}:{a['valor']}:{a['opcao']}" for a in x]) if x else "")
        df_save['finalizado'] = df_save['finalizado'].apply(lambda x: "TRUE" if x else "FALSE")
        df_save['apostas_abertas'] = df_save['apostas_abertas'].apply(lambda x: "TRUE" if x else "FALSE")
    
    conn.update(data=df_save)
    st.cache_data.clear()

# --- ESTADO E INICIALIZAÇÃO ---
if 'estagio' not in st.session_state: st.session_state.estagio = 'inicio' # inicio | painel
if 'jogos' not in st.session_state: st.session_state.jogos = []
if 'times' not in st.session_state: st.session_state.times = []
if 'modo_jogo' not in st.session_state: st.session_state.modo_jogo = "LIGA"
if 'autenticado' not in st.session_state: st.session_state.autenticado = False
if 'menu_ativo' not in st.session_state: st.session_state.menu_ativo = "Jogos"

# --- TELA INICIAL (MENU DE ENTRADA) ---
if st.session_state.estagio == 'inicio':
    c1, c2, c3 = st.columns([1,2,1])
    with c2:
        st.markdown("<h1 style='text-align: center; font-size: 60px;'>⚽ BAGA BET</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: gray;'>Sistema Profissional de Gerenciamento de Torneios</p>", unsafe_allow_html=True)
        st.divider()
        
        # Botão Carregar Nuvem
        if st.button("☁️ CARREGAR TORNEIO SALVO", use_container_width=True, type="primary"):
            js, ts, _ = carregar_tudo()
            if js:
                st.session_state.jogos = js
                st.session_state.times = ts
                st.session_state.estagio = 'painel'
                st.session_state.modo_jogo = "LIGA" # Por enquanto default
                st.rerun()
            else:
                st.warning("Nenhum torneio encontrado na nuvem. Crie um novo abaixo.")

        st.markdown("### Criar Novo Jogo")
        col_a, col_b = st.columns(2)
        
        if col_a.button("🏆 MODO LIGA (Pontos Corridos)", use_container_width=True):
            st.session_state.modo_jogo = "LIGA"
            st.session_state.estagio = 'painel'
            st.session_state.menu_ativo = "Admin"
            st.rerun()
            
        if col_b.button("⚔️ MODO COPA (Mata-Mata)", use_container_width=True):
            # AQUI ENTRA A LÓGICA DA COPA FUTURAMENTE
            st.session_state.modo_jogo = "COPA"
            st.session_state.estagio = 'painel'
            st.session_state.menu_ativo = "Admin"
            st.rerun()

# --- TELA DO PAINEL (DASHBOARD) ---
else:
    # --- SIDEBAR ---
    with st.sidebar:
        st.title("BAGA BET PRO")
        st.markdown(f"<span class='modo-badge'>MODO {st.session_state.modo_jogo}</span>", unsafe_allow_html=True)
        
        if not st.session_state.autenticado:
            if st.text_input("Senha Admin", type="password") == "1234":
                st.session_state.autenticado = True; st.rerun()
        else:
            if st.button("Sair Admin"): st.session_state.autenticado = False; st.rerun()
        
        st.divider()
        if st.button("🏟️ JOGOS", use_container_width=True): st.session_state.menu_ativo = "Jogos"; st.rerun()
        if st.button("🤑 RANKING", use_container_width=True): st.session_state.menu_ativo = "Ranking"; st.rerun()
        if st.button("📊 TABELA", use_container_width=True): st.session_state.menu_ativo = "Classificação"; st.rerun()
        if st.button("⚙️ ADMIN", use_container_width=True): st.session_state.menu_ativo = "Admin"; st.rerun()
        
        st.divider()
        if st.button("🏠 VOLTAR AO INÍCIO", use_container_width=True):
            st.session_state.estagio = 'inicio'
            st.rerun()

    sou_admin = st.session_state.autenticado

    # --- ABA JOGOS ---
    if st.session_state.menu_ativo == "Jogos":
        st.header(f"Partidas - {st.session_state.modo_jogo}")
        if not st.session_state.jogos:
            st.info("Nenhum jogo criado. Vá em ADMIN para iniciar o torneio.")
        
        for i, j in enumerate(st.session_state.jogos):
            with st.container(border=False):
                c1, c2, c3 = st.columns([2, 2, 2])
                
                # Placar Visual
                ga_txt = j['ga'] if j['ga'] is not None else "-"
                gb_txt = j['gb'] if j['gb'] is not None else "-"
                cls_placar = "gols-finalizado" if j['finalizado'] else "gols-aberto"
                
                c1.markdown(f"<h3 style='text-align:right; padding-top:15px;'>{j['a']}</h3>", unsafe_allow_html=True)
                c2.markdown(f"""
                    <div class="placar-box">
                        <span class="{cls_placar}">{ga_txt} : {gb_txt}</span>
                    </div>
                """, unsafe_allow_html=True)
                c3.markdown(f"<h3 style='text-align:left; padding-top:15px;'>{j['b']}</h3>", unsafe_allow_html=True)

                # Admin Score
                if sou_admin:
                    with st.expander("⚙️ Gerenciar Resultado"):
                        cc1, cc2, cc3 = st.columns([1,1,1])
                        vga = cc1.number_input(f"Gols {j['a']}", 0, 20, key=f"g1_{i}")
                        vgb = cc2.number_input(f"Gols {j['b']}", 0, 20, key=f"g2_{i}")
                        if cc3.button("SALVAR", key=f"sv_{i}"):
                            st.session_state.jogos[i].update({'ga': int(vga), 'gb': int(vgb), 'finalizado': True, 'apostas_abertas': False})
                            salvar_tudo(st.session_state.jogos); st.rerun()

                # Apostas
                tab_v, tab_n = st.tabs(["Ver Apostas", "Nova Aposta"])
                with tab_v:
                    if j['apostas']:
                        df_Show = pd.DataFrame(j['apostas'])
                        df_Show['Palpite'] = df_Show['opcao'].map({"A": j['a'], "B": j['b'], "E": "Empate"})
                        st.dataframe(df_Show[['nome', 'Palpite', 'valor']], use_container_width=True)
                    else: st.caption("Nenhuma aposta ainda.")
                with tab_n:
                    if sou_admin and not j['finalizado']:
                        with st.form(key=f"bet_{i}", clear_on_submit=True):
                            col_n, col_v = st.columns(2)
                            nome = col_n.text_input("Nome")
                            val = col_v.number_input("Valor", 1.0, 5000.0, 10.0)
                            op = st.radio("Vencedor", [j['a'], "Empate", j['b']], horizontal=True)
                            if st.form_submit_button("Lançar Aposta"):
                                code = "A" if op == j['a'] else "B" if op == j['b'] else "E"
                                st.session_state.jogos[i]['apostas'].append({"nome": nome, "valor": val, "opcao": code})
                                salvar_tudo(st.session_state.jogos); st.rerun()

    # --- ABA ADMIN ---
    elif st.session_state.menu_ativo == "Admin":
        if sou_admin:
            st.header("⚙️ Configuração do Torneio")
            
            # BLUCO 1: RESET
            with st.container(border=True):
                st.subheader("⚠️ Zona de Perigo")
                c_res1, c_res2 = st.columns(2)
                if c_res1.button("🧹 LIMPAR JOGOS (Manter Times)", use_container_width=True):
                    # Limpa jogos, salva vazio na nuvem, mas mantem st.session_state.times
                    salvar_tudo([]) 
                    st.session_state.jogos = []
                    st.success("Jogos resetados! Times mantidos.")
                    st.rerun()
                    
                if c_res2.button("🔥 RESET TOTAL (Apagar Tudo)", type="primary", use_container_width=True):
                    salvar_tudo([])
                    st.session_state.jogos = []
                    st.session_state.times = []
                    st.warning("Tudo apagado!")
                    st.rerun()

            # BLOCO 2: CRIAÇÃO
            if st.session_state.modo_jogo == "LIGA":
                st.subheader("🏆 Criar Nova Liga")
                
                # Método Input Antigo
                qtd_times = st.number_input("Quantidade de Times", min_value=2, max_value=20, value=4, step=1)
                
                # Se já houver times na memória (pelo reset), pré-carrega
                novos_times = []
                cols = st.columns(2)
                for k in range(qtd_times):
                    # Tenta pegar o nome antigo se existir, senão vazio
                    val_padrao = st.session_state.times[k] if k < len(st.session_state.times) else f"Time {k+1}"
                    t_nome = cols[k % 2].text_input(f"Nome do Time {k+1}", value=val_padrao, key=f"t_in_{k}")
                    novos_times.append(t_nome)
                
                if st.button("🚀 GERAR CONFRONTOS DA LIGA", use_container_width=True, type="primary"):
                    ts = [t.strip() for t in novos_times if t.strip()]
                    if len(ts) >= 2:
                        combs = list(itertools.combinations(ts, 2))
                        random.shuffle(combs)
                        novos_jogos = [{"a": c[0], "b": c[1], "ga": None, "gb": None, "finalizado": False, "apostas_abertas": True, "apostas": []} for c in combs]
                        
                        salvar_tudo(novos_jogos)
                        st.session_state.jogos = novos_jogos
                        st.session_state.times = ts
                        st.session_state.menu_ativo = "Jogos"
                        st.rerun()
            
            elif st.session_state.modo_jogo == "COPA":
                st.subheader("⚔️ Configurar Copa (Mata-Mata)")
                st.info("Aguardando regras do formato Copa...")
                # Aqui vamos inserir os inputs da Copa depois

        else: st.error("Faça login no menu lateral.")

    # --- ABA RANKING ---
    elif st.session_state.menu_ativo == "Ranking":
        st.header("🤑 Ranking Financeiro")
        # (Lógica de Ranking igual à anterior, mantida para economizar espaço visual aqui)
        rank = {}
        for j in st.session_state.jogos:
            if j['finalizado'] and j['ga'] is not None:
                res = "A" if j['ga'] > j['gb'] else "B" if j['gb'] > j['ga'] else "E"
                pote = sum(a['valor'] for a in j['apostas'])
                venc_v = sum(a['valor'] for a in j['apostas'] if a['opcao'] == res)
                for a in j['apostas']:
                    rank.setdefault(a['nome'], {"ganho": 0.0, "pago": 0.0})
                    rank[a['nome']]["pago"] += a['valor']
                    if a['opcao'] == res and venc_v > 0:
                        rank[a['nome']]["ganho"] += (a['valor'] / venc_v) * pote
        if rank:
            l_r = [{"Apostador": k, "Investido": money_raw(v['pago']), "Retorno": money_raw(v['ganho']), "Saldo": v['ganho']-v['pago']} for k, v in rank.items()]
            df_r = pd.DataFrame(l_r).sort_values("Saldo", ascending=False)
            df_r['Saldo'] = df_r['Saldo'].apply(money)
            st.write(df_r.to_html(escape=False, index=False), unsafe_allow_html=True)
        else: st.info("Sem dados finalizados.")

    # --- ABA TABELA ---
    elif st.session_state.menu_ativo == "Classificação":
        if st.session_state.modo_jogo == "LIGA":
            st.header("📊 Tabela Pontos Corridos")
            stats = {t: {"P":0,"J":0,"V":0,"E":0,"D":0,"SG":0} for t in st.session_state.times}
            for j in st.session_state.jogos:
                if j['ga'] is not None and j['gb'] is not None:
                    a, b = j['a'], j['b']
                    # Garante que times existam no dict (caso de mudança manual)
                    if a not in stats: stats[a] = {"P":0,"J":0,"V":0,"E":0,"D":0,"SG":0}
                    if b not in stats: stats[b] = {"P":0,"J":0,"V":0,"E":0,"D":0,"SG":0}
                    
                    stats[a]["J"]+=1; stats[b]["J"]+=1
                    if j['ga'] > j['gb']: stats[a]["P"]+=3; stats[a]["V"]+=1; stats[b]["D"]+=1
                    elif j['gb'] > j['ga']: stats[b]["P"]+=3; stats[b]["V"]+=1; stats[a]["D"]+=1
                    else: stats[a]["P"]+=1; stats[b]["P"]+=1; stats[a]["E"]+=1; stats[b]["E"]+=1
                    stats[a]["SG"]+=(j['ga']-j['gb']); stats[b]["SG"]+=(j['gb']-j['ga'])
            st.dataframe(pd.DataFrame.from_dict(stats, orient='index').sort_values(["P", "SG"], ascending=False), use_container_width=True)
        else:
            st.info("Visualização da chave da Copa em breve...")
