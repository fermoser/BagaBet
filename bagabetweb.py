import streamlit as st
import pandas as pd
import random
from streamlit_gsheets import GSheetsConnection

st.set_page_config(page_title="BAGA SUÍÇO PURO", layout="wide")
conn = st.connection("gsheets", type=GSheetsConnection)

# --- FUNÇÕES DE LÓGICA ---
def carregar_dados():
    try:
        df = conn.read(worksheet="Suico", ttl=0).dropna(how='all')
        if df.empty: return pd.DataFrame(columns=['torneio_id', 'rodada', 'a', 'b', 'gols_a', 'gols_b', 'finalizado', 'fase'])
        return df
    except: return pd.DataFrame(columns=['torneio_id', 'rodada', 'a', 'b', 'gols_a', 'gols_b', 'finalizado', 'fase'])

def calcular_stats(df_jogos, tid):
    jogos = df_jogos[df_jogos['torneio_id'] == tid].copy()
    times_info = {}
    
    # Pegar todos os times que já jogaram
    todos = pd.concat([jogos['a'], jogos['b']]).unique()
    for t in todos:
        if t and t != "BYE": times_info[t] = {'V': 0, 'D': 0, 'oponentes': [], 'status': 'Ativo'}
    
    # Calcular Vitórias, Derrotas e Oponentes
    for _, j in jogos[jogos['finalizado'] == 'SIM'].iterrows():
        if j['a'] != "BYE" and j['b'] != "BYE":
            times_info[j['a']]['oponentes'].append(j['b'])
            times_info[j['b']]['oponentes'].append(j['a'])
            if j['gols_a'] > j['gols_b']:
                times_info[j['a']]['V'] += 1; times_info[j['b']]['D'] += 1
            else:
                times_info[j['b']]['V'] += 1; times_info[j['a']]['D'] += 1
        elif j['b'] == "BYE":
            times_info[j['a']]['V'] += 1 # Vitória por BYE

    # Calcular Buchholz (Soma de vitórias dos oponentes)
    for t, info in times_info.items():
        buchholz = sum([times_info[op]['V'] for op in info['oponentes'] if op in times_info])
        info['Buchholz'] = buchholz
        if info['V'] >= 3: info['status'] = 'Classificado'
        elif info['D'] >= 3: info['status'] = 'Eliminado'
        
    return times_info

def realizar_pareamento(times_info, historico_jogos):
    ativos = [t for t, info in times_info.items() if info['status'] == 'Ativo']
    # Ordenar ativos: Vitórias desc, Buchholz desc
    ativos.sort(key=lambda x: (times_info[x]['V'], times_info[x]['Buchholz']), reverse=True)
    
    pareados = []
    ja_escolhidos = set()
    
    # Lógica de BYE (Se ímpar, o pior geral que nunca teve BYE ganha)
    if len(ativos) % 2 != 0:
        pior_sem_bye = None
        for t in reversed(ativos):
            # Verifica se já teve bye (jogo contra 'BYE')
            teve_bye = any(((h['a'] == t and h['b'] == 'BYE') or (h['b'] == t and h['a'] == 'BYE')) for h in historico_jogos)
            if not teve_bye:
                pior_sem_bye = t
                break
        if pior_sem_bye:
            pareados.append((pior_sem_bye, 'BYE'))
            ja_escolhidos.add(pior_sem_bye)

    # Pareamento por Score
    for i in range(len(ativos)):
        t1 = ativos[i]
        if t1 in ja_escolhidos: continue
        
        # Tenta achar oponente com mesmo score que não enfrentou
        for j in range(i + 1, len(ativos)):
            t2 = ativos[j]
            if t2 in ja_escolhidos: continue
            
            # Regra de Ineditismo
            ja_jogaram = any(((h['a'] == t1 and h['b'] == t2) or (h['a'] == t2 and h['b'] == t1)) for h in historico_jogos)
            if not ja_jogaram:
                pareados.append((t1, t2))
                ja_escolhidos.add(t1); ja_escolhidos.add(t2)
                break
                
    return pareados

# --- INTERFACE ---
df_total = carregar_dados()

if 'torneio_ativo' not in st.session_state:
    st.title("⚽ BAGA GESTOR - FORMATO SUÍÇO")
    with st.expander("🆕 Iniciar Novo Torneio (6-16 times)"):
        novo_id = st.text_input("Nome do Torneio")
        lista_t = st.text_area("Times (um por linha)")
        if st.button("Iniciar Fase Suíça"):
            times = [x.strip() for x in lista_t.split('\n') if x.strip()]
            if 6 <= len(times) <= 16:
                random.shuffle(times)
                jogos = []
                for i in range(0, len(times), 2):
                    t1 = times[i]; t2 = times[i+1] if i+1 < len(times) else "BYE"
                    jogos.append({'torneio_id': novo_id, 'rodada': 1, 'a': t1, 'b': t2, 'gols_a': 1 if t2=="BYE" else 0, 'gols_b': 0, 'finalizado': 'SIM' if t2=="BYE" else 'NÃO', 'fase': 'Suíça'})
                conn.update(worksheet="Suico", data=pd.concat([df_total, pd.DataFrame(jogos)]))
                st.cache_data.clear(); st.rerun()
            else: st.error("Mínimo 6, Máximo 16 times.")
    
    st.divider()
    ids = df_total['torneio_id'].unique()
    for i in ids:
        if st.button(f"Abrir {i}"): st.session_state.torneio_ativo = i; st.rerun()

else:
    tid = st.session_state.torneio_ativo
    st.header(f"Torneio: {tid}")
    if st.button("Voltar"): st.session_state.torneio_ativo = None; st.rerun()
    
    stats = calcular_stats(df_total, tid)
    
    t1, t2, t3 = st.tabs(["🎮 Jogos", "📊 Classificação", "🛠️ Admin"])
    
    with t2:
        st.subheader("Ranking Suíço (Buchholz)")
        ranking_df = pd.DataFrame.from_dict(stats, orient='index').sort_values(by=['V', 'Buchholz'], ascending=False)
        st.dataframe(ranking_df, use_container_width=True)

    with t3:
        if st.text_input("Senha", type="password") == "123":
            jogos_tid = df_total[df_total['torneio_id'] == tid]
            rodada_atual = jogos_tid['rodada'].max()
            pendentes = jogos_tid[jogos_tid['finalizado'] == 'NÃO']
            
            ativos = [t for t, info in stats.items() if info['status'] == 'Ativo']
            
            if not pendentes.empty:
                st.warning(f"Finalize a rodada {rodada_atual} primeiro.")
            elif len(ativos) < 2:
                st.success("Fase Suíça encerrada! Todos classificados ou eliminados.")
                if st.button("Gerar Mata-Mata Final"):
                    classificados = [t for t, info in stats.items() if info['status'] == 'Classificado']
                    classificados.sort(key=lambda x: (stats[x]['V'], stats[x]['Buchholz']), reverse=True)
                    # Aqui entra a sua lógica de Caso 1, 2, 3 ou 4 de mata-mata (implementarei conforme avançar)
                    st.write(f"Classificados: {classificados}")
            else:
                if st.button("Gerar Próxima Rodada"):
                    hist = jogos_tid.to_dict('records')
                    novos_pares = realizar_pareamento(stats, hist)
                    novos_jogos = []
                    for p in novos_pares:
                        novos_jogos.append({'torneio_id': tid, 'rodada': rodada_atual+1, 'a': p[0], 'b': p[1], 'gols_a': 1 if p[1]=="BYE" else 0, 'gols_b': 0, 'finalizado': 'SIM' if p[1]=="BYE" else 'NÃO', 'fase': 'Suíça'})
                    conn.update(worksheet="Suico", data=pd.concat([df_total, pd.DataFrame(novos_jogos)]))
                    st.cache_data.clear(); st.rerun()

    with t1:
        jogos_view = df_total[df_total['torneio_id'] == tid]
        for r in sorted(jogos_view['rodada'].unique(), reverse=True):
            st.subheader(f"Rodada {r}")
            for idx, row in jogos_view[jogos_view['rodada'] == r].iterrows():
                with st.container(border=True):
                    c1, c2, c3 = st.columns([2,1,2])
                    c1.write(row['a'])
                    c2.write(f"{row['gols_a']} x {row['gols_b']}")
                    c3.write(row['b'])
                    if row['finalizado'] == 'NÃO' and row['b'] != 'BYE':
                        with st.expander("Lançar"):
                            with st.form(f"f_{idx}"):
                                ga = st.number_input("A", 0, 100, key=f"a{idx}")
                                gb = st.number_input("B", 0, 100, key=f"b{idx}")
                                if st.form_submit_button("Ok"):
                                    df_total.at[idx, 'gols_a'] = ga
                                    df_total.at[idx, 'gols_b'] = gb
                                    df_total.at[idx, 'finalizado'] = 'SIM'
                                    conn.update(worksheet="Suico", data=df_total)
                                    st.cache_data.clear(); st.rerun()
