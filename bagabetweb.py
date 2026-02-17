import streamlit as st
import pandas as pd
import random
from streamlit_gsheets import GSheetsConnection

# Configuração e Conexão
st.set_page_config(page_title="BAGA GESTOR PRO", layout="wide")
conn = st.connection("gsheets", type=GSheetsConnection)

def carregar():
    try:
        df = conn.read(worksheet="Suico", ttl=0)
        df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
        for col in ['gols_a', 'gols_b', 'rodada']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col]).fillna(0).astype(int)
        if 'finalizado' not in df.columns: df['finalizado'] = 'NÃO'
        if 'fase' not in df.columns: df['fase'] = 'Suico'
        return df
    except:
        return pd.DataFrame(columns=['torneio_id', 'fase', 'rodada', 'a', 'b', 'gols_a', 'gols_b', 'finalizado'])

df_total = carregar()

if 'torneio_ativo' not in st.session_state:
    st.title("⚽ BAGA GESTOR PRO")
    ids = [str(x) for x in df_total['torneio_id'].dropna().unique() if str(x).strip() not in ["", "-", "None"]]
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

    # --- CÁLCULO DE RANKING (Sempre atualizado) ---
    stats = {}
    times_fase_grupo = jogos_tid[jogos_tid['fase'] == 'Suico']
    todos_times = pd.concat([times_fase_grupo['a'], times_fase_grupo['b']]).unique()
    for t in todos_times:
        if t not in ["BYE", "-", None, ""]: stats[t] = {'Pts':0, 'V':0, 'SG':0, 'GP':0}
    
    for _, j in times_fase_grupo[times_fase_grupo['finalizado'] == 'SIM'].iterrows():
        for t in [j['a'], j['b']]:
            if t in stats:
                if j['b'] == "BYE":
                    if t == j['a']: stats[t]['Pts'] += 3; stats[t]['V'] += 1; stats[t]['GP'] += 1
                else:
                    gp = j['gols_a'] if t == j['a'] else j['gols_b']
                    gc = j['gols_b'] if t == j['a'] else j['gols_a']
                    stats[t]['GP'] += gp
                    stats[t]['SG'] += (gp - gc)
                    if gp > gc: stats[t]['Pts'] += 3; stats[t]['V'] += 1
                    elif gp == gc: stats[t]['Pts'] += 1

    ranking = pd.DataFrame.from_dict(stats, orient='index').sort_values(by=['Pts', 'V', 'SG', 'GP'], ascending=False)

    with tab3: # ADMIN INTELIGENTE
        senha = st.text_input("Senha Admin", type="password")
        if senha == "123":
            if st.button("🚨 RESETAR/APAGAR TORNEIO"):
                conn.update(worksheet="Suico", data=df_total[df_total['torneio_id'] != tid])
                st.cache_data.clear(); st.session_state.torneio_ativo = None; st.rerun()

            st.divider()
            
            # 1. Se não existe rodada, cria a 1ª
            if jogos_tid.empty:
                st.subheader("Iniciar Torneio (6 Jogadores)")
                txt = st.text_area("Lista de Nomes")
                if st.button("GERAR 1ª RODADA"):
                    lista = [t.strip() for t in txt.split('\n') if t.strip()]
                    if len(lista) == 6:
                        random.shuffle(lista)
                        novos = []
                        for i in range(0, 6, 2):
                            novos.append({'torneio_id': tid, 'fase': 'Suico', 'rodada': 1, 'a': lista[i], 'b': lista[i+1], 'finalizado': 'NÃO'})
                        conn.update(worksheet="Suico", data=pd.concat([df_total, pd.DataFrame(novos)]))
                        st.cache_data.clear(); st.rerun()
                    else: st.error("Por favor, insira exatamente 6 nomes.")

            # 2. Lógica de Próxima Rodada Automática
            else:
                rodada_max = jogos_tid['rodada'].max()
                pendentes = jogos_tid[(jogos_tid['rodada'] == rodada_max) & (jogos_tid['finalizado'] == 'NÃO')]
                
                if pendentes.empty:
                    # FASE SUÍÇA (Até Rodada 4)
                    if rodada_max < 4:
                        if st.button(f"🚀 GERAR RODADA {rodada_max + 1}"):
                            # Pareamento Suíço Simples (1v2, 3v4, 5v6 do ranking)
                            lista = ranking.index.tolist()
                            novos = []
                            for i in range(0, 6, 2):
                                novos.append({'torneio_id': tid, 'fase': 'Suico', 'rodada': rodada_max + 1, 'a': lista[i], 'b': lista[i+1], 'finalizado': 'NÃO'})
                            conn.update(worksheet="Suico", data=pd.concat([df_total, pd.DataFrame(novos)]))
                            st.cache_data.clear(); st.rerun()
                    
                    # MATA-MATA: SEMIFINAIS (Rodada 5)
                    elif rodada_max == 4 and (jogos_tid['fase'] == 'Suico').all():
                        if st.button("🔥 GERAR SEMIFINAIS"):
                            lista = ranking.index.tolist()
                            novos = [
                                {'torneio_id': tid, 'fase': 'Eliminatoria', 'rodada': 5, 'a': lista[0], 'b': lista[3], 'finalizado': 'NÃO'}, # 1x4
                                {'torneio_id': tid, 'fase': 'Eliminatoria', 'rodada': 5, 'a': lista[1], 'b': lista[2], 'finalizado': 'NÃO'}, # 2x3
                                {'torneio_id': tid, 'fase': 'Repescagem', 'rodada': 5, 'a': lista[4], 'b': lista[5], 'finalizado': 'NÃO'}   # 5x6
                            ]
                            conn.update(worksheet="Suico", data=pd.concat([df_total, pd.DataFrame(novos)]))
                            st.cache_data.clear(); st.rerun()

                    # MATA-MATA: FINAIS (Rodada 6)
                    elif rodada_max == 5:
                        if st.button("🏆 GERAR FINAIS"):
                            semis = jogos_tid[jogos_tid['rodada'] == 5]
                            vencedores = []
                            perdedores = []
                            for _, s in semis.iterrows():
                                if s['fase'] == 'Eliminatoria':
                                    if s['gols_a'] > s['gols_b']: vencedores.append(s['a']); perdedores.append(s['b'])
                                    else: vencedores.append(s['b']); perdedores.append(s['a'])
                            
                            finais = [
                                {'torneio_id': tid, 'fase': 'FINAL', 'rodada': 6, 'a': vencedores[0], 'b': vencedores[1], 'finalizado': 'NÃO'},
                                {'torneio_id': tid, 'fase': '3º LUGAR', 'rodada': 6, 'a': perdedores[0], 'b': perdedores[1], 'finalizado': 'NÃO'}
                            ]
                            conn.update(worksheet="Suico", data=pd.concat([df_total, pd.DataFrame(finais)]))
                            st.cache_data.clear(); st.rerun()
                else:
                    st.warning(f"Finalize os jogos da Rodada {rodada_max} primeiro!")

    with tab2: # CLASSIFICAÇÃO
        st.subheader("Classificação Fase Suíça")
        st.table(ranking)

    with tab1: # JOGOS
        for r in sorted(jogos_tid['rodada'].unique(), reverse=True):
            fase_nome = "SUÍÇO" if r <= 4 else ("SEMIFINAIS" if r == 5 else "FINAIS")
            st.subheader(f"Rodada {r} - {fase_nome}")
            for idx, row in jogos_tid[jogos_tid['rodada'] == r].iterrows():
                with st.container(border=True):
                    c1, c2, c3 = st.columns([2,1,2])
                    c1.write(f"**{row['a']}**")
                    c2.write(f"{row['gols_a']} x {row['gols_b']}")
                    c3.write(f"**{row['b']}**")
                    if row['finalizado'] == 'NÃO':
                        with st.expander("Resultado"):
                            with st.form(f"f_{idx}"):
                                ga = st.number_input("Gols A", 0, 20, key=f"ga_{idx}")
                                gb = st.number_input("Gols B", 0, 20, key=f"gb_{idx}")
                                if st.form_submit_button("Confirmar"):
                                    df_total.at[idx, 'gols_a'] = ga
                                    df_total.at[idx, 'gols_b'] = gb
                                    df_total.at[idx, 'finalizado'] = 'SIM'
                                    conn.update(worksheet="Suico", data=df_total)
                                    st.cache_data.clear(); st.rerun()
