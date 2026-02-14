import streamlit as st
import pandas as pd
import itertools
import random
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="BAGA BET CLOUD", layout="wide")
conn = st.connection("gsheets", type=GSheetsConnection)

def money(v):
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# --- BANCO DE DADOS ---
def salvar_nuvem():
    if 'jogos' in st.session_state and st.session_state.jogos:
        df = pd.DataFrame(st.session_state.jogos)
        df['apostas'] = df['apostas'].apply(lambda x: "|".join([f"{a['nome']}:{a['valor']}:{a['opcao']}" for a in x]) if x else "")
        conn.update(data=df)

def carregar_nuvem():
    try:
        df = conn.read(ttl=0)
        if not df.empty:
            jogos_lidos = df.to_dict('records')
            for j in jogos_lidos:
                j['apostas'] = []
                if 'apostas' in j and str(j['apostas']) not in ["nan", "None", ""]:
                    for item in str(j['apostas']).split("|"):
                        partes = item.split(":")
                        if len(partes) == 3:
                            j['apostas'].append({"nome": partes[0], "valor": float(partes[1]), "opcao": partes[2]})
                j['ga'] = int(j['ga']) if str(j.get('ga')) not in ["None", "nan", ""] else None
                j['gb'] = int(j['gb']) if str(j.get('gb')) not in ["None", "nan", ""] else None
                j['finalizado'] = str(j.get('finalizado', "False")) == "True"
                j['apostas_abertas'] = str(j.get('apostas_abertas', "True")) == "True"
            st.session_state.jogos = jogos_lidos
            st.session_state.times = list(set([j['a'] for j in jogos_lidos] + [j['b'] for j in jogos_lidos]))
    except:
        st.session_state.jogos, st.session_state.times = [], []

if 'jogos' not in st.session_state:
    carregar_nuvem()

# --- SIDEBAR E SEGURANÇA ---
st.sidebar.title("BAGA BET ⚽")
admin_key = st.sidebar.text_input("Chave do Admin", type="password")
# DEFINIÇÃO GLOBAL DA VARIÁVEL SOU_ADMIN
sou_admin = (admin_key == "1234") 

menu = st.sidebar.radio("Navegação", ["Jogos", "Classificação", "Ranking Apostas", "Novo Torneio"])

if sou_admin:
    st.sidebar.success("Modo Admin Ativo")
    if st.sidebar.button("⚠️ RESETAR TORNEIO"):
        st.session_state.jogos, st.session_state.times = [], []
        salvar_nuvem(); st.rerun()

# --- CONTEÚDO ---
if menu == "Novo Torneio":
    if not sou_admin:
        st.error("Acesse como Admin para criar torneios.")
    else:
        st.header("🏆 Novo Torneio")
        qtd = st.number_input("Qtd Times", 2, 20, 4)
        nomes = [st.text_input(f"Time {i+1}", key=f"t{i}") for i in range(qtd)]
        if st.button("GERAR CONFRONTOS", type="primary"):
            times = [n for n in nomes if n]
            if len(times) >= 2:
                pares = list(itertools.combinations(times, 2))
                random.shuffle(pares)
                st.session_state.times, st.session_state.jogos = times, [{"a": p[0], "b": p[1], "ga": None, "gb": None, "finalizado": False, "apostas_abertas": True, "apostas": []} for p in pares]
                salvar_nuvem(); st.rerun()

elif menu == "Jogos":
    st.header("⚽ Jogos")
    if not st.session_state.jogos:
        st.info("Nenhum jogo ativo.")
    else:
        for i, j in enumerate(st.session_state.jogos):
            with st.container(border=True):
                # 1. Placar Compacto
                c1, c2, c3 = st.columns([1.5, 1, 1.5])
                res_a, res_b = (j['ga'] if j['ga'] is not None else "-"), (j['gb'] if j['gb'] is not None else "-")
                c1.markdown(f"<p style='text-align:right; font-size:18px; font-weight:bold; margin:0;'>{j['a']}</p>", unsafe_allow_html=True)
                c2.markdown(f"<h3 style='text-align:center; margin:0;'>{res_a} x {res_b}</h3>", unsafe_allow_html=True)
                c3.markdown(f"<p style='text-align:left; font-size:18px; font-weight:bold; margin:0;'>{j['b']}</p>", unsafe_allow_html=True)

                # 2. Resumo Financeiro Alinhado (Colunas Fixas)
                ap = j['apostas']
                t_a = sum(x['valor'] for x in ap if x['opcao'] == "A")
                t_e = sum(x['valor'] for x in ap if x['opcao'] == "E")
                t_b = sum(x['valor'] for x in ap if x['opcao'] == "B")
                total_pote = t_a + t_e + t_b

                m1, m2, m3, m4 = st.columns(4)
                m1.metric(j['a'], money(t_a))
                m2.metric("Empate", money(t_e))
                m3.metric(j['b'], money(t_b))
                m4.metric("POTE TOTAL", money(total_pote))

                # 3. Painel de Controle (Admin e Apostas)
                exp = st.expander("💰 Gerenciar Apostas e Placar")
                with exp:
                    col_ap, col_hist = st.columns([1, 2])
                    
                    with col_ap:
                        # Seção de Aposta
                        if j.get('apostas_abertas', True) and not j['finalizado']:
                            st.markdown("**Nova Aposta**")
                            n_ap = st.text_input("Nome", key=f"nap{i}", label_visibility="collapsed", placeholder="Nome")
                            v_ap = st.number_input("R$", 1.0, 5000.0, 10.0, key=f"vap{i}")
                            o_ap = st.radio("Palpite", [j['a'], "Empate", j['b']], key=f"oap{i}", horizontal=True)
                            if st.button("Confirmar", key=f"bap{i}", use_container_width=True):
                                if n_ap:
                                    trad = "A" if o_ap == j['a'] else "B" if o_ap == j['b'] else "E"
                                    st.session_state.jogos[i]['apostas'].append({"nome": n_ap, "valor": v_ap, "opcao": trad})
                                    salvar_nuvem(); st.rerun()
                        
                        # Botões do Admin
                        if sou_admin:
                            st.divider()
                            if not j['finalizado']:
                                if j.get('apostas_abertas', True):
                                    if st.button("🚫 Trancar Apostas", key=f"tr{i}", use_container_width=True):
                                        st.session_state.jogos[i]['apostas_abertas'] = False
                                        salvar_nuvem(); st.rerun()
                                else:
                                    if st.button("🔓 Reabrir Apostas", key=f"re{i}", use_container_width=True):
                                        st.session_state.jogos[i]['apostas_abertas'] = True
                                        salvar_nuvem(); st.rerun()
                                
                                st.markdown("**Finalizar Partida**")
                                ga_val = st.number_input(f"Gols {j['a']}", 0, 99, key=f"ga{i}")
                                gb_val = st.number_input(f"Gols {j['b']}", 0, 99, key=f"gb{i}")
                                if st.button("🏆 SALVAR RESULTADO", key=f"f{i}", use_container_width=True, type="primary"):
                                    st.session_state.jogos[i].update({'ga': ga_val, 'gb': gb_val, 'finalizado': True, 'apostas_abertas': False})
                                    salvar_nuvem(); st.rerun()
                            else:
                                st.success("Jogo Finalizado")

                    with col_hist:
                        st.markdown("**Histórico**")
                        if ap:
                            df = pd.DataFrame(ap)
                            df['Palpite'] = df['opcao'].map({"A": j['a'], "B": j['b'], "E": "Empate"})
                            if j['finalizado']:
                                res = "A" if j['ga'] > j['gb'] else "B" if j['gb'] > j['ga'] else "E"
                                v_val = sum(x['valor'] for x in ap if x['opcao'] == res)
                                df['Bruto'] = df.apply(lambda r: (r['valor']/v_val*total_pote) if r['opcao']==res and v_val>0 else 0.0, axis=1)
                                df['Líquido'] = df['Bruto'] - df['valor']
                                df['Aposta'], df['Bruto'], df['Líquido'] = df['valor'].apply(money), df['Bruto'].apply(money), df['Líquido'].apply(money)
                                st.dataframe(df[['nome', 'Palpite', 'Aposta', 'Bruto', 'Líquido']], use_container_width=True, hide_index=True)
                            else:
                                df['Aposta'] = df['valor'].apply(money)
                                st.dataframe(df[['nome', 'Palpite', 'Aposta']], use_container_width=True, hide_index=True)
                        else:
                            st.write("Sem apostas.")

elif menu == "Classificação":
    st.header("📊 Classificação")
    # ... (mesma lógica de classificação anterior)
    if 'jogos' in st.session_state and st.session_state.jogos:
        # Coloque aqui a função gerar_classificacao() se desejar exibir
        st.table(pd.DataFrame([{"Time": "Aguardando Resultados"}])) # Placeholder

elif menu == "Ranking Apostas":
    st.header("💰 Ranking Geral")
    # ... (mesma lógica de ranking anterior)
