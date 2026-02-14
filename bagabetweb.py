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
        # Serializa apostas para texto
        df['apostas'] = df['apostas'].apply(lambda x: "|".join([f"{a['nome']}:{a['valor']}:{a['opcao']}" for a in x]) if x else "")
        conn.update(data=df)

def carregar_nuvem():
    try:
        df = conn.read(ttl=0)
        if not df.empty:
            jogos_lidos = df.to_dict('records')
            for j in jogos_lidos:
                # 1. Recuperar Apostas
                j['apostas'] = []
                if 'apostas' in j and str(j['apostas']) not in ["nan", "None", ""]:
                    for item in str(j['apostas']).split("|"):
                        partes = item.split(":")
                        if len(partes) == 3:
                            j['apostas'].append({"nome": partes[0], "valor": float(partes[1]), "opcao": partes[2]})
                
                # 2. Tipagem correta para evitar interferência entre jogos
                j['ga'] = int(j['ga']) if str(j.get('ga')) not in ["None", "nan", ""] else None
                j['gb'] = int(j['gb']) if str(j.get('gb')) not in ["None", "nan", ""] else None
                j['finalizado'] = str(j.get('finalizado')) == "True"
                
                # CORREÇÃO AQUI: Garantir que se o campo não existir, ele seja True apenas para aquele jogo
                if 'apostas_abertas' not in j or str(j['apostas_abertas']) == "nan":
                    j['apostas_abertas'] = True
                else:
                    j['apostas_abertas'] = str(j['apostas_abertas']) == "True"
            
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
                st.session_state.times = times
                st.session_state.jogos = [{"a": p[0], "b": p[1], "ga": None, "gb": None, "finalizado": False, "apostas_abertas": True, "apostas": []} for p in pares]
                salvar_nuvem(); st.rerun()

elif menu == "Jogos":
    st.header("⚽ Rodadas")
    if not st.session_state.get('jogos'):
        st.info("Nenhum jogo ativo.")
    else:
        for i, j in enumerate(st.session_state.jogos):
            with st.container(border=True):
                # CABEÇALHO DO JOGO
                c1, c2, c3 = st.columns([2, 1, 2])
                res_a, res_b = (j['ga'] if j['ga'] is not None else "-"), (j['gb'] if j['gb'] is not None else "-")
                c1.markdown(f"<h2 style='text-align:right; margin:0;'>{j['a']}</h2>", unsafe_allow_html=True)
                c2.markdown(f"<h1 style='text-align:center; margin:0; color:#FF4B4B;'>{res_a} x {res_b}</h1>", unsafe_allow_html=True)
                c3.markdown(f"<h2 style='text-align:left; margin:0;'>{j['b']}</h2>", unsafe_allow_html=True)

                # LANÇAMENTO DE RESULTADO (ADMIN)
                if sou_admin and not j['finalizado']:
                    st.divider()
                    l1, l2, l3, l4 = st.columns([1, 0.2, 1, 2])
                    ga_in = l1.number_input(f"Gols {j['a']}", 0, 99, key=f"ga_input_{i}")
                    l2.markdown("<h3 style='text-align:center;'>x</h3>", unsafe_allow_html=True)
                    gb_in = l3.number_input(f"Gols {j['b']}", 0, 99, key=f"gb_input_{i}")
                    if l4.button("🏆 FINALIZAR JOGO", key=f"btn_f_{i}", type="primary", use_container_width=True):
                        st.session_state.jogos[i]['ga'] = ga_in
                        st.session_state.jogos[i]['gb'] = gb_in
                        st.session_state.jogos[i]['finalizado'] = True
                        st.session_state.jogos[i]['apostas_abertas'] = False # Tranca ao finalizar
                        salvar_nuvem(); st.rerun()

                # FINANCEIRO
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

                # EXPANDER DE APOSTAS
                with st.expander("💰 Detalhes das Apostas"):
                    col_ap, col_hist = st.columns([1.2, 2])
                    
                    with col_ap:
                        # Verifica se as apostas estão abertas especificamente PARA ESTE JOGO
                        if j.get('apostas_abertas') == True and not j['finalizado']:
                            st.subheader("Nova Aposta")
                            n_ap = st.text_input("Nome", key=f"name_{i}")
                            v_ap = st.number_input("Valor R$", 1.0, 1000.0, 10.0, key=f"val_{i}")
                            o_ap = st.radio("Palpite", [j['a'], "Empate", j['b']], key=f"opt_{i}", horizontal=True)
                            if st.button("Confirmar", key=f"save_ap_{i}", use_container_width=True):
                                if n_ap:
                                    trad = "A" if o_ap == j['a'] else "B" if o_ap == j['b'] else "E"
                                    st.session_state.jogos[i]['apostas'].append({"nome": n_ap, "valor": v_ap, "opcao": trad})
                                    salvar_nuvem(); st.rerun()
                            
                            if sou_admin:
                                if st.button("🚫 Trancar Apostas", key=f"lock_{i}", use_container_width=True):
                                    st.session_state.jogos[i]['apostas_abertas'] = False
                                    salvar_nuvem(); st.rerun()
                        else:
                            st.warning("🔒 Apostas encerradas.")
                            if sou_admin and not j['finalizado']:
                                if st.button("🔓 Reabrir Apostas", key=f"unlock_{i}"):
                                    st.session_state.jogos[i]['apostas_abertas'] = True
                                    salvar_nuvem(); st.rerun()

                    with col_hist:
                        if ap:
                            df = pd.DataFrame(ap)
                            df['Palpite'] = df['opcao'].map({"A": j['a'], "B": j['b'], "E": "Empate"})
                            if j['finalizado']:
                                res = "A" if j['ga'] > j['gb'] else "B" if j['gb'] > j['ga'] else "E"
                                v_val = sum(x['valor'] for x in ap if x['opcao'] == res)
                                df['Bruto'] = df.apply(lambda r: (r['valor']/v_val*total_pote) if r['opcao']==res and v_val>0 else 0.0, axis=1)
                                df['Líquido'] = df['Bruto'] - df['valor']
                                df['Bruto'], df['Líquido'], df['Aposta'] = df['Bruto'].apply(money), df['Líquido'].apply(money), df['valor'].apply(money)
                                st.dataframe(df[['nome', 'Palpite', 'Aposta', 'Bruto', 'Líquido']], use_container_width=True, hide_index=True)
                            else:
                                df['Aposta'] = df['valor'].apply(money)
                                st.dataframe(df[['nome', 'Palpite', 'Aposta']], use_container_width=True, hide_index=True)

elif menu == "Classificação":
    st.header("📊 Classificação")
    if not st.session_state.get('jogos'):
        st.info("Sem dados.")
    else:
        cl = {t: {"P":0,"V":0,"E":0,"D":0,"GP":0,"GC":0,"SG":0} for t in st.session_state.times}
        for j in st.session_state.jogos:
            if not j["finalizado"]: continue
            a, b, ga, gb = j["a"], j["b"], j["ga"], j["gb"]
            cl[a]["GP"]+=ga; cl[a]["GC"]+=gb; cl[b]["GP"]+=gb; cl[b]["GC"]+=ga
            if ga > gb: cl[a]["P"]+=3; cl[a]["V"]+=1; cl[b]["D"]+=1
            elif gb > ga: cl[b]["P"]+=3; cl[b]["V"]+=1; cl[a]["D"]+=1
            else: cl[a]["P"]+=1; cl[b]["P"]+=1; cl[a]["E"]+=1; cl[b]["E"]+=1
        for t in cl: cl[t]["SG"] = cl[t]["GP"] - cl[t]["GC"]
        df_cl = pd.DataFrame.from_dict(cl, orient='index').sort_values(by=["P", "V", "SG"], ascending=False)
        st.table(df_cl)

elif menu == "Ranking Apostas":
    st.header("💰 Ranking de Apostadores")
    ranking = {}
    for j in st.session_state.get('jogos', []):
        if not j["finalizado"]: continue
        pool = sum(a["valor"] for a in j["apostas"])
        res = "A" if j["ga"] > j["gb"] else "B" if j["gb"] > j["ga"] else "E"
        venc_val = sum(a["valor"] for a in j["apostas"] if a["opcao"] == res)
        for a in j["apostas"]:
            ranking.setdefault(a["nome"], {"ap": 0, "ga": 0})
            ranking[a["nome"]]["ap"] += a["valor"]
            if a["opcao"] == res and venc_val > 0:
                ranking[a["nome"]]["ga"] += (a["valor"] / venc_val * pool)
    if ranking:
        dr = [{"Nome": n, "Investido": money(d['ap']), "Retorno": money(d['ga']), "Lucro": money(d['ga']-d['ap'])} for n, d in ranking.items()]
        st.dataframe(pd.DataFrame(dr).sort_values("Lucro", ascending=False), use_container_width=True, hide_index=True)
    else:
        st.info("O ranking será exibido após a finalização dos jogos.")
