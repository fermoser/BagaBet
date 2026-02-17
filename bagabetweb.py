import streamlit as st
import pandas as pd
import random
from streamlit_gsheets import GSheetsConnection

st.set_page_config(page_title="BAGA GESTOR PRO", layout="wide")
conn = st.connection("gsheets", type=GSheetsConnection)

def carregar():
    try:
        df = conn.read(worksheet="Suico", ttl=0)
        df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
        
        # --- BLINDAGEM DE COLUNAS ---
        # Se a coluna 'rodada' sumiu da planilha, a gente cria ela aqui na memória
        if 'rodada' not in df.columns:
            df['rodada'] = 1
        if 'finalizado' not in df.columns:
            df['finalizado'] = 'NÃO'
            
        # Garante que números sejam números
        for col in ['gols_a', 'gols_b', 'rodada']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col]).fillna(0).astype(int)
            else:
                df[col] = 0
        return df
    except:
        return pd.DataFrame(columns=['torneio_id', 'fase', 'rodada', 'a', 'b', 'gols_a', 'gols_b', 'finalizado'])

df_total = carregar()

# --- ESTADO DO TORNEIO ---
if 'torneio_ativo' not in st.session_state:
    st.title("⚽ BAGA GESTOR PRO")
    ids = [str(x) for x in df_total['torneio_id'].dropna().unique() if str(x).strip() not in ["", "-", "None"]]
    if ids:
        st.subheader("Meus Torneios")
        for tid in sorted(ids):
            if st.button(f"🏟️ {tid}", use_container_width=True):
                st.session_state.torneio_ativo = tid
                st.rerun()
else:
    tid = st.session_state.torneio_ativo
    jogos_tid = df_total[df_total['torneio_id'] == tid].copy()
    
    st.header(f"🏆 {tid}")
    if st.button("⬅️ Sair"):
        st.session_state.torneio_ativo = None
        st.rerun()

    tab1, tab2, tab3 = st.tabs(["🏟️ Jogos", "📊 Classificação", "⚙️ Admin"])

    with tab2: # CLASSIFICAÇÃO
        jogos_fin = jogos_tid[jogos_tid['finalizado'] == 'SIM']
        stats = {}
        # Inicializa todos os times que aparecem no torneio
        todos_times = pd.concat([jogos_tid['a'], jogos_tid['b']]).unique()
        for t in todos_times:
            if t not in ["BYE", "-", None]:
                stats[t] = {'Pts':0, 'V':0, 'SG':0}
        
        for _, j in jogos_fin.iterrows():
            if j['b'] == "BYE":
                if j['a'] in stats:
                    stats[j['a']]['Pts'] += 3; stats[j['a']]['V'] += 1
            else:
                if j['a'] in stats and j['b'] in stats:
                    if j['gols_a'] > j['gols_b']: 
                        stats[j['a']]['Pts'] += 3; stats[j['a']]['V'] += 1
                    elif j['gols_b'] > j['gols_a']: 
                        stats[j['b']]['Pts'] += 3; stats[j['b']]['V'] += 1
                    else: 
                        stats[j['a']]['Pts'] += 1; stats[j['b']]['Pts'] += 1
        
        ranking = pd.DataFrame.from_dict(stats, orient='index').sort_values(by=['Pts', 'V'], ascending=False)
        st.table(ranking)

    with tab3: # ADMIN
        senha = st.text_input("Senha Admin", type="password")
        if senha == "123":
            # Botão para criar 1ª Rodada (Se estiver vazio)
            with st.expander("🆕 Iniciar Novo Sorteio"):
                txt = st.text_area("Times (um por linha)")
                if st.button("GERAR 1ª RODADA"):
                    lista = [t.strip() for t in txt.split('\n') if t.strip()]
                    if len(lista) >= 2:
                        random.shuffle(lista)
                        novos = []
                        for i in range(0, len(lista), 2):
                            t1, t2 = lista[i], (lista[i+1] if i+1 < len(lista) else "BYE")
                            novos.append({'torneio_id': tid, 'fase': 'Suico', 'rodada': 1, 'a': t1, 'b': t2, 'gols_a': (1 if t2=="BYE" else 0), 'gols_b': 0, 'finalizado': ('SIM' if t2=="BYE" else 'NÃO')})
                        df_limpo = df_total[df_total['torneio_id'] != tid]
                        conn.update(worksheet="Suico", data=pd.concat([df_limpo, pd.DataFrame(novos)]))
                        st.cache_data.clear(); st.rerun()

            # Botão para Próxima Rodada (Suíço)
            if not ranking.empty:
                if st.button("🚀 GERAR PRÓXIMA RODADA"):
                    lista_ordenada = ranking.index.tolist()
                    rodada_atual = int(jogos_tid['rodada'].max()) if not jogos_tid.empty else 1
                    proximos = []
                    for i in range(0, len(lista_ordenada), 2):
                        t1 = lista_ordenada[i]
                        t2 = lista_ordenada[i+1] if i+1 < len(lista_ordenada) else "BYE"
                        proximos.append({'torneio_id': tid, 'fase': 'Suico', 'rodada': rodada_atual + 1, 'a': t1, 'b': t2, 'gols_a': 0, 'gols_b': 0, 'finalizado': 'NÃO'})
                    conn.update(worksheet="Suico", data=pd.concat([df_total, pd.DataFrame(proximos)]))
                    st.cache_data.clear(); st.rerun()

    with tab1: # JOGOS
        if jogos_tid.empty:
            st.info("Vá em Admin e gere os jogos.")
        else:
            rodadas = sorted(jogos_tid['rodada'].unique(), reverse=True)
            for r in rodadas:
                st.subheader(f"Rodada {r}")
                jogos_r = jogos_tid[jogos_tid['rodada'] == r]
                for idx, row in jogos_r.iterrows():
                    with st.container(border=True):
                        c1, c2, c3 = st.columns([2,1,2])
                        c1.write(row['a'])
                        c2.write(f"{row['gols_a']} x {row['gols_b']}")
                        c3.write(row['b'])
                        if row['b'] != "BYE" and row['finalizado'] != 'SIM':
                            with st.expander("Lançar Placar"):
                                with st.form(f"f_{idx}"):
                                    ga = st.number_input("Gols A", 0, 20, key=f"ga_{idx}")
                                    gb = st.number_input("Gols B", 0, 20, key=f"gb_{idx}")
                                    if st.form_submit_button("Confirmar"):
                                        df_total.loc[idx, ['gols_a', 'gols_b', 'finalizado']] = [ga, gb, 'SIM']
                                        conn.update(worksheet="Suico", data=df_total)
                                        st.cache_data.clear(); st.rerun()
