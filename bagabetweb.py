import streamlit as st
import pandas as pd
import random
from itertools import combinations
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="BAGA BET PRO", layout="wide", page_icon="⚽")
conn = st.connection("gsheets", type=GSheetsConnection)

# --- CSS VISUAL ---
st.markdown("""
    <style>
    .placar-box { background-color: #f1f3f5; border: 2px solid #333; border-radius: 12px; padding: 10px; text-align: center; }
    .fase-header { background: linear-gradient(90deg, #111, #444); color: #fff; padding: 10px; border-radius: 8px; margin: 15px 0; text-align: center; font-weight: bold; text-transform: uppercase; }
    .time-nome { font-weight: bold; font-size: 1.1rem; }
    .gols-res { color: #1b5e20; font-weight: 900; font-size: 1.8rem; }
    .status-badge { font-size: 0.7rem; padding: 2px 5px; border-radius: 4px; background: #eee; }
    </style>
    """, unsafe_allow_html=True)

# --- FUNÇÕES DE APOIO ---
def money(v):
    cor = "#28a745" if v > 0 else "#dc3545" if v < 0 else "#212529"
    val_fmt = f"R$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f'<span style="color:{cor}; font-weight:bold;">{val_fmt}</span>'

def carregar_tudo():
    try:
        st.cache_data.clear()
        df = conn.read(ttl=0)
        return df.dropna(how='all') if df is not None else pd.DataFrame()
    except: return pd.DataFrame()

def carregar_jogos(nome_torneio):
    df = carregar_tudo()
    if df.empty or 'torneio_id' not in df.columns: return []
    df_f = df[df['torneio_id'].astype(str).str.strip() == str(nome_torneio).strip()]
    
    jogos = []
    for _, r in df_f.iterrows():
        ap = []
        raw_ap = str(r.get('apostas', ''))
        if raw_ap not in ["nan", "", "None"]:
            for item in raw_ap.split("|"):
                p = item.split(":")
                if len(p) == 3: ap.append({"nome": p[0], "valor": float(p[1]), "opcao": p[2]})
        
        jogos.append({
            "a": str(r.get('a')), "b": str(r.get('b')),
            "ga": r.get('ga'), "gb": r.get('gb'),
            "ga1": r.get('ga1'), "gb1": r.get('gb1'),
            "ga2": r.get('ga2'), "gb2": r.get('gb2'),
            "pen_a": int(r.get('pen_a', 0)) if pd.notna(r.get('pen_a')) else 0,
            "pen_b": int(r.get('pen_b', 0)) if pd.notna(r.get('pen_b')) else 0,
            "finalizado": str(r.get('finalizado', '')).upper() == "TRUE",
            "fase": str(r.get('fase', 'Rodada')),
            "formato": str(r.get('formato', 'LIGA')),
            "apostas": ap
        })
    return jogos

def salvar_dados(jogos_atuais, nome_torneio, formato):
    df_full = carregar_tudo()
    nome_torneio = str(nome_torneio).strip()
    df_base = df_full[df_full['torneio_id'].astype(str).str.strip() != nome_torneio] if not df_full.empty else pd.DataFrame()
    
    df_novos = pd.DataFrame(jogos_atuais)
    df_novos['torneio_id'] = nome_torneio
    df_novos['formato'] = formato
    df_novos['apostas'] = df_novos['apostas'].apply(lambda x: "|".join([f"{a['nome']}:{a['valor']}:{a['opcao']}" for a in x]) if x else "")
    df_novos['finalizado'] = df_novos['finalizado'].apply(lambda x: "TRUE" if x else "FALSE")
    
    df_final = pd.concat([df_base, df_novos], ignore_index=True)
    conn.update(data=df_final)
    st.cache_data.clear()

# --- TELA INICIAL ---
if 'torneio_ativo' not in st.session_state:
    st.markdown("<h1 style='text-align: center;'>⚽ BAGA BET PRO</h1>", unsafe_allow_html=True)
    df_all = carregar_tudo()
    
    if not df_all.empty and 'torneio_id' in df_all.columns:
        st.subheader("📂 Abrir Torneio Salvo")
        t_list = df_all[['torneio_id', 'formato']].dropna().drop_duplicates()
        cols = st.columns(3)
        for i, row in enumerate(t_list.values):
            tid, tform = row[0], row[1]
            if cols[i%3].button(f"{'🏆' if tform=='COPA' else '📈'} {tid}", use_container_width=True):
                st.session_state.torneio_ativo, st.session_state.formato = tid, tform
                st.session_state.jogos = carregar_jogos(tid)
                st.rerun()

    st.divider()
    with st.expander("🆕 Criar Novo Torneio"):
        c1, c2 = st.columns(2)
        n_id = c1.text_input("ID do Torneio")
        n_form = c2.selectbox("Tipo", ["LIGA", "COPA"])
        if st.button("INICIAR NOVO"):
            if n_id:
                st.session_state.torneio_ativo, st.session_state.formato, st.session_state.jogos = n_id.strip(), n_form, []
                st.rerun()

else:
    # --- INTERFACE DO TORNEIO ---
    formato = st.session_state.formato
    with st.sidebar:
        st.title(st.session_state.torneio_ativo)
        st.info(f"Modo: {formato}")
        menu = st.radio("Menu", ["🏟️ Jogos", "📊 Classificação", "🤑 Ranking", "⚙️ Admin"])
        is_admin = (st.text_input("Senha Admin", type="password") == "1234")
        if st.button("🏠 Sair"):
            for k in list(st.session_state.keys()): del st.session_state[k]
            st.rerun()

    # --- JOGOS ---
    if menu == "🏟️ Jogos":
        if not st.session_state.jogos:
            st.warning("Nenhum jogo encontrado. Vá em Admin.")
        else:
            fases = sorted(list(set([j['fase'] for j in st.session_state.jogos])))
            for fase in fases:
                st.markdown(f"<div class='fase-header'>{fase}</div>", unsafe_allow_html=True)
                for idx, j in enumerate(st.session_state.jogos):
                    if j['fase'] == fase:
                        with st.container(border=True):
                            c1, c2, c3 = st.columns([2, 1, 2])
                            c1.markdown(f"<p style='text-align:right;' class='time-nome'>{j['a']}</p>", unsafe_allow_html=True)
                            
                            # Placar Híbrido
                            if formato == "LIGA":
                                p_txt = f"{int(j['ga']) if pd.notna(j['ga']) else '-'} : {int(j['gb']) if pd.notna(j['gb']) else '-'}"
                            else:
                                p_txt = f"({int(j['ga1']) if pd.notna(j['ga1']) else 0}) {int(j['ga2']) if pd.notna(j['ga2']) else 0} : {int(j['gb2']) if pd.notna(j['gb2']) else 0} ({int(j['gb1']) if pd.notna(j['gb1']) else 0})"
                            
                            c2.markdown(f"<div class='placar-box'><span class='gols-res'>{p_txt}</span></div>", unsafe_allow_html=True)
                            c3.markdown(f"<p class='time-nome'>{j['b']}</p>", unsafe_allow_html=True)

                            # Área Admin de Lançamento
                            if is_admin:
                                with st.expander("📝 Lançar Resultado"):
                                    if formato == "LIGA":
                                        v1, v2 = st.number_input("Gols A", 0, key=f"v1{idx}"), st.number_input("Gols B", 0, key=f"v2{idx}")
                                        if st.button("Salvar Placar", key=f"sv{idx}"):
                                            j.update({"ga":v1, "gb":v2, "finalizado":True})
                                            salvar_dados(st.session_state.jogos, st.session_state.torneio_ativo, formato); st.rerun()
                                    else:
                                        ca, cb = st.columns(2)
                                        ga1, gb1 = ca.number_input("Ida A", 0, key=f"i1{idx}"), cb.number_input("Ida B", 0, key=f"i2{idx}")
                                        ga2, gb2 = ca.number_input("Volta A", 0, key=f"v1{idx}"), cb.number_input("Volta B", 0, key=f"v2{idx}")
                                        pa, pb = 0, 0
                                        if (ga1+ga2) == (gb1+gb2):
                                            pa, pb = ca.number_input("Pen A", 0, key=f"pa{idx}"), cb.number_input("Pen B", 0, key=f"pb{idx}")
                                        if st.button("Confirmar Copa", key=f"sv{idx}"):
                                            j.update({"ga1":ga1,"gb1":gb1,"ga2":ga2,"gb2":gb2,"pen_a":pa,"pen_b":pb,"finalizado":True})
                                            salvar_dados(st.session_state.jogos, st.session_state.torneio_ativo, formato); st.rerun()
                                if j['finalizado'] and st.button("🔄 Resetar Jogo", key=f"rs{idx}"):
                                    j['finalizado'] = False; st.rerun()

                            # Área de Apostas
                            with st.expander("🤑 Apostas"):
                                if not j['finalizado']:
                                    with st.form(f"ap{idx}"):
                                        n, v = st.text_input("Nome"), st.number_input("Valor R$", 1, 500, 10)
                                        opc = ["A", "B", "Empate"] if formato == "LIGA" else ["A", "B"]
                                        o = st.radio("Vencedor", opc, horizontal=True)
                                        if st.form_submit_button("Apostar"):
                                            j['apostas'].append({"nome":n, "valor":v, "opcao":o})
                                            salvar_dados(st.session_state.jogos, st.session_state.torneio_ativo, formato); st.rerun()
                                elif j['apostas']:
                                    # Lógica de Resultado para Apostas
                                    if formato == "LIGA":
                                        res = "A" if j['ga']>j['gb'] else "B" if j['gb']>j['ga'] else "Empate"
                                    else:
                                        totA, totB = (j['ga1'] or 0)+(j['ga2'] or 0), (j['gb1'] or 0)+(j['gb2'] or 0)
                                        res = "A" if totA > totB else "B" if totB > totA else ("A" if j['pen_a']>j['pen_b'] else "B")
                                    
                                    df_a = pd.DataFrame(j['apostas'])
                                    v_pote, v_venc = df_a['valor'].sum(), df_a[df_a['opcao']==res]['valor'].sum()
                                    df_a['Lucro'] = df_a.apply(lambda r: money(r['valor']/v_venc*v_pote - r['valor']) if r['opcao']==res and v_venc>0 else money(-r['valor']), axis=1)
                                    st.write(df_a.to_html(escape=False, index=False), unsafe_allow_html=True)

    # --- CLASSIFICAÇÃO ---
    elif menu == "📊 Classificação":
        if formato == "LIGA":
            stats = {}
            for j in st.session_state.jogos:
                for t in [j['a'], j['b']]:
                    if t not in stats: stats[t] = {"P":0,"J":0,"V":0,"E":0,"D":0,"GP":0,"GC":0}
                if j['finalizado']:
                    ga, gb = j['ga'], j['gb']
                    stats[j['a']]["J"]+=1; stats[j['b']]["J"]+=1
                    stats[j['a']]["GP"]+=ga; stats[j['a']]["GC"]+=gb
                    stats[j['b']]["GP"]+=gb; stats[j['b']]["GC"]+=ga
                    if ga>gb: stats[j['a']]["P"]+=3; stats[j['a']]["V"]+=1; stats[j['b']]["D"]+=1
                    elif gb>ga: stats[j['b']]["P"]+=3; stats[j['b']]["V"]+=1; stats[j['a']]["D"]+=1
                    else: stats[j['a']]["P"]+=1; stats[j['b']]["P"]+=1; stats[j['a']]["E"]+=1; stats[j['b']]["E"]+=1
            df_tab = pd.DataFrame.from_dict(stats, orient='index').reset_index().rename(columns={'index':'Equipe'})
            st.table(df_tab.sort_values(by=["P", "V", "GP"], ascending=False))
        else:
            st.info("Modo Copa: Acompanhe o chaveamento pelos jogos.")

    # --- RANKING FINANCEIRO ---
    elif menu == "🤑 Ranking":
        st.header("💰 Ranking Geral de Lucros")
        rk = {}
        for j in st.session_state.jogos:
            if j['finalizado'] and j['apostas']:
                if formato == "LIGA": res = "A" if j['ga']>j['gb'] else "B" if j['gb']>j['ga'] else "Empate"
                else:
                    tA, tB = (j['ga1'] or 0)+(j['ga2'] or 0), (j['gb1'] or 0)+(j['gb2'] or 0)
                    res = "A" if tA > tB else "B" if tB > tA else ("A" if j['pen_a']>j['pen_b'] else "B")
                pote, venc = sum(a['valor'] for a in j['apostas']), sum(a['valor'] for a in j['apostas'] if a['opcao']==res)
                for a in j['apostas']:
                    lucro = (a['valor']/venc*pote - a['valor']) if a['opcao']==res and venc>0 else -a['valor']
                    rk[a['nome']] = rk.get(a['nome'], 0) + lucro
        if rk:
            df_rk = pd.DataFrame([{"Apostador": k, "Saldo": money(v)} for k, v in rk.items()]).sort_values("Saldo", ascending=False)
            st.write(df_rk.to_html(escape=False, index=False), unsafe_allow_html=True)

    # --- ADMIN ---
    elif menu == "⚙️ Admin":
        if st.button("🔄 SINCRONIZAR COM A PLANILHA"):
            st.session_state.jogos = carregar_jogos(st.session_state.torneio_ativo); st.rerun()
        if is_admin:
            with st.form("reset_torneio"):
                st.subheader("Gerar Estrutura")
                txt_times = st.text_area("Times (um por linha)")
                if st.form_submit_button("GERAR CONFRONTOS"):
                    times = [t.strip() for t in txt_times.split("\n") if t.strip()]
                    random.shuffle(times)
                    novos = []
                    if formato == "LIGA":
                        for a, b in combinations(times, 2):
                            novos.append({"a":a,"b":b,"ga":None,"gb":None,"finalizado":False,"fase":"Única","formato":"LIGA","apostas":[]})
                    else:
                        for i in range(0, len(times), 2):
                            novos.append({"a":times[i],"b":times[i+1],"ga1":None,"gb1":None,"ga2":None,"gb2":None,"pen_a":0,"pen_b":0,"finalizado":False,"fase":"Mata-Mata","formato":"COPA","apostas":[]})
                    salvar_dados(novos, st.session_state.torneio_ativo, formato)
                    st.session_state.jogos = novos; st.rerun()
