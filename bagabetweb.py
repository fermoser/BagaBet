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
        st.session_state.jogos = []

if 'jogos' not in st.session_state:
    carregar_nuvem()

# --- SEGURANÇA ---
st.sidebar.title("BAGA BET ⚽")
admin_key = st.sidebar.text_input("Chave do Admin", type="password")
sou_admin = (admin_key == "1234") 

menu = st.sidebar.radio("Navegação", ["Jogos", "Classificação", "Ranking Apostas", "Novo Torneio"])

if sou_admin:
    st.sidebar.success("MODO ADMIN")
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
    st.header("⚽ Rodadas do Torneio")
    if not st.session_state.get('jogos'):
        st.info("Nenhum jogo ativo.")
    else:
        for i, j in enumerate(st.session_state.jogos):
            with st.container(border=True):
                # 1. PLACAR PRINCIPAL (Nomes Grandes)
                c1, c2, c3 = st.columns([2, 1, 2])
                res_a = j['ga'] if j['ga'] is not None else "-"
                res_b = j['gb'] if j['gb'] is not None else "-"
                
                c1.markdown(f"<h2 style='text-align:right; margin:0;'>{j['a']}</h2>", unsafe_allow_html=True)
                c2.markdown(f"<h1 style='text-align:center; margin:0; color:#FF4B4B;'>{res_a} x {res_b}</h1>", unsafe_allow_html=True)
                c3.markdown(f"<h2 style='text-align:left; margin:0;'>{j['b']}</h2>", unsafe_allow_html=True)

                # 2. ÁREA DE LANÇAMENTO (Só para Admin e se não finalizado)
                if sou_admin and not j['finalizado']:
                    st.markdown("---")
                    st.markdown("#### 📝 Lançar Resultado Final")
                    l1, l2, l3, l4 = st.columns([1, 0.2, 1, 2])
                    ga_in = l1.number_input(f"Gols {j['a']}", 0, 99, key=f"ga{i}", label_visibility="collapsed")
                    l2.markdown("<h3 style='text-align:center;'>x</h3>", unsafe_allow_html=True)
                    gb_in = l3.number_input(f"Gols {j['b']}", 0, 99, key=f"gb{i}", label_visibility="collapsed")
                    if l4.button("🏆 FINALIZAR JOGO", key=f"btn_f{i}", type="primary", use_container_width=True):
                        st.session_state.jogos[i].update({'ga': ga_in, 'gb': gb_in, 'finalizado': True, 'apostas_abertas': False})
                        salvar_nuvem(); st.rerun()
                    st.markdown("---")

                # 3. MÉTRICAS FINANCEIRAS (Alinhadas)
                ap = j['apostas']
                t_a = sum(x['valor'] for x in ap if x['opcao'] == "A")
                t_e = sum(x['valor'] for x in ap if x['opcao'] == "E")
                t_b = sum(x['valor'] for x in ap if x['opcao'] == "B")
                total_pote = t_a + t_e + t_b

                # Layout fixo de 4 colunas para não entortar
                m1, m2, m3, m4 = st.columns(4)
                m1.metric(f"No {j['a']}", money(t_a))
                m2.metric("No Empate", money(t_e))
                m3.metric(f"No {j['b']}", money(t_b))
                m4.metric("POTE TOTAL", money(total_pote), delta="Acumulado")

                # 4. PAINEL DE APOSTAS E HISTÓRICO
                with st.expander("💰 Fazer Aposta / Ver Histórico"):
                    col_ap, col_hist = st.columns([1.2, 2])
                    
                    with col_ap:
                        if j.get('apostas_abertas', True) and not j['finalizado']:
                            st.subheader("Nova Aposta")
                            n_ap = st.text_input("Seu Nome", key=f"nap{i}", placeholder="Ex: João")
                            v_ap = st.number_input("Valor R$", 1.0, 1000.0, 10.0, key=f"vap{i}")
                            o_ap = st.radio("Seu Palpite", [j['a'], "Empate", j['b']], key=f"oap{i}", horizontal=True)
                            if st.button("Confirmar Aposta 💸", key=f"bap{i}", use_container_width=True):
                                if n_ap:
                                    trad = "A" if o_ap == j['a'] else "B" if o_ap == j['b'] else "E"
                                    st.session_state.jogos[i]['apostas'].append({"nome": n_ap, "valor": v_ap, "opcao": trad})
                                    salvar_nuvem(); st.rerun()
                            
                            if sou_admin:
                                st.divider()
                                if st.button("🚫 Encerrar Apostas", key=f"tr{i}", use_container_width=True):
                                    st.session_state.jogos[i]['apostas_abertas'] = False
                                    salvar_nuvem(); st.rerun()
                        else:
                            st.warning("🔒 Apostas encerradas para este jogo.")
                            if sou_admin and not j['finalizado']:
                                if st.button("🔓 Reabrir Apostas", key=f"re{i}"):
                                    st.session_state.jogos[i]['apostas_abertas'] = True
                                    salvar_nuvem(); st.rerun()

                    with col_hist:
                        st.subheader("Quem apostou")
                        if ap:
                            df = pd.DataFrame(ap)
                            df['Palpite'] = df['opcao'].map({"A": j['a'], "B": j['b'], "E": "Empate"})
                            if j['finalizado']:
                                res = "A" if j['ga'] > j['gb'] else "B" if j['gb'] > j['ga'] else "E"
                                v_val = sum(x['valor'] for x in ap if x['opcao'] == res)
                                df['Bruto'] = df.apply(lambda r: (r['valor']/v_val*total_pote) if r['opcao']==res and v_val>0 else 0.0, axis=1)
                                df['Líquido'] = df['Bruto'] - df['valor']
                                # Formatação para exibição
                                df_show = df.copy()
                                df_show['Aposta'] = df_show['valor'].apply(money)
                                df_show['Bruto'] = df_show['Bruto'].apply(money)
                                df_show['Líquido'] = df_show['Líquido'].apply(money)
                                st.dataframe(df_show[['nome', 'Palpite', 'Aposta', 'Bruto', 'Líquido']], use_container_width=True, hide_index=True)
                            else:
                                df_show = df.copy()
                                df_show['Aposta'] = df_show['valor'].apply(money)
                                st.dataframe(df_show[['nome', 'Palpite', 'Aposta']], use_container_width=True, hide_index=True)
                        else:
                            st.info("Aguardando primeira aposta.")

elif menu == "Classificação":
    st.header("📊 Tabela do Campeonato")
    # ... (lógica de classificação igual)

elif menu == "Ranking Apostas":
    st.header("💰 Ranking de Apostadores")
    # ... (lógica de ranking igual)
