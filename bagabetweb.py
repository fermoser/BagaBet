import streamlit as st
import pandas as pd
import random
from itertools import combinations
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="BAGA BET PRO", layout="wide", page_icon="⚽")
conn = st.connection("gsheets", type=GSheetsConnection)

# --- FUNÇÕES DE DADOS ---
def carregar_db():
    try:
        st.cache_data.clear()
        df = conn.read(ttl=0)
        if df is None or df.empty:
            # Se a planilha estiver vazia, cria um DataFrame com as colunas certas
            return pd.DataFrame(columns=[
                'torneio_id', 'formato', 'fase', 'a', 'b', 'finalizado', 'apostas',
                'gols_a', 'gols_b', 'ida_a', 'ida_b', 'volta_a', 'volta_b', 'pen_a', 'pen_b'
            ])
        return df
    except:
        return pd.DataFrame()

def salvar_db(df_novo):
    # Remove colunas fantasmas que o pandas cria as vezes
    df_save = df_novo.loc[:, ~df_novo.columns.str.contains('^Unnamed')]
    conn.update(data=df_save)
    st.cache_data.clear()

def money(v):
    cor = "#28a745" if v > 0 else "#dc3545" if v < 0 else "#212529"
    val = f"R$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f'<span style="color:{cor}; font-weight:bold;">{val}</span>'

# --- INTERFACE ---
df_atual = carregar_db()

if 'torneio_ativo' not in st.session_state:
    st.title("⚽ BAGA BET PRO")
    
    # Verifica se existe a coluna antes de tentar usar
    if not df_atual.empty and 'torneio_id' in df_atual.columns:
        st.subheader("📂 Abrir Torneio")
        torneios = df_atual[['torneio_id', 'formato']].dropna().drop_duplicates()
        cols = st.columns(3)
        for i, row in enumerate(torneios.values):
            if cols[i%3].button(f"{'🏆' if row[1]=='COPA' else '📈'} {row[0]}", use_container_width=True):
                st.session_state.torneio_ativo = row[0]
                st.session_state.formato = row[1]
                st.rerun()

    st.divider()
    with st.expander("🆕 Criar Novo Torneio"):
        c1, c2 = st.columns(2)
        n_id = c1.text_input("Nome (Ex: copa2026)")
        n_tp = c2.selectbox("Tipo", ["LIGA", "COPA"])
        if st.button("INICIAR"):
            if n_id:
                st.session_state.torneio_ativo, st.session_state.formato = n_id.strip(), n_tp
                st.rerun()

else:
    t_id = st.session_state.torneio_ativo
    formato = st.session_state.formato
    
    # Filtro Seguro
    if not df_atual.empty and 'torneio_id' in df_atual.columns:
        jogos_df = df_atual[df_atual['torneio_id'] == t_id].copy()
    else:
        jogos_df = pd.DataFrame()

    with st.sidebar:
        st.header(t_id)
        menu = st.radio("Menu", ["🏟️ Jogos", "📊 Classificação", "🤑 Ranking", "⚙️ Admin"])
        is_admin = (st.text_input("Senha Admin", type="password") == "1234")
        if st.button("🏠 Sair"):
            for k in list(st.session_state.keys()): del st.session_state[k]
            st.rerun()

    if menu == "🏟️ Jogos":
        if jogos_df.empty:
            st.info("Aguardando geração de jogos no Admin...")
        else:
            for idx, row in jogos_df.iterrows():
                with st.container(border=True):
                    c1, c2, c3 = st.columns([2, 1, 2])
                    c1.write(f"### {row['a']}")
                    
                    if formato == "LIGA":
                        ga, gb = row.get('gols_a'), row.get('gols_b')
                        txt = f"{int(ga) if pd.notna(ga) else '-'} x {int(gb) if pd.notna(gb) else '-'}"
                    else:
                        ia, ib = row.get('ida_a', 0), row.get('ida_b', 0)
                        va, vb = row.get('volta_a', 0), row.get('volta_b', 0)
                        txt = f"({int(ia) or 0}) {int(va) or 0} x {int(vb) or 0} ({int(ib) or 0})"
                    
                    c2.markdown(f"## {txt}")
                    c3.write(f"### {row['b']}")

                    # LANÇAMENTO ADMIN
                    if is_admin:
                        with st.expander("📝 Lançar Resultado"):
                            if formato == "LIGA":
                                res_a = st.number_input(f"Gols {row['a']}", 0, key=f"ga{idx}")
                                res_b = st.number_input(f"Gols {row['b']}", 0, key=f"gb{idx}")
                                if st.button("Salvar Liga", key=f"btl{idx}"):
                                    df_atual.loc[idx, ['gols_a', 'gols_b', 'finalizado']] = [res_a, res_b, "TRUE"]
                                    salvar_db(df_atual); st.rerun()
                            else:
                                col1, col2 = st.columns(2)
                                i_a = col1.number_input("Ida A", 0, key=f"ia{idx}")
                                i_b = col1.number_input("Ida B", 0, key=f"ib{idx}")
                                v_a = col2.number_input("Volta A", 0, key=f"va{idx}")
                                v_b = col2.number_input("Volta B", 0, key=f"vb{idx}")
                                if st.button("Salvar Copa", key=f"btc{idx}"):
                                    df_atual.loc[idx, ['ida_a','ida_b','volta_a','volta_b','finalizado']] = [i_a, i_b, v_a, v_b, "TRUE"]
                                    salvar_db(df_atual); st.rerun()

                    # SISTEMA DE APOSTAS
                    with st.expander("🤑 Apostas"):
                        # Exibir apostas existentes
                        lista_ap = []
                        if pd.notna(row.get('apostas')) and row['apostas'] != "":
                            for item in str(row['apostas']).split("|"):
                                p = item.split(":")
                                if len(p) == 3: lista_ap.append({"nome": p[0], "valor": float(p[1]), "opcao": p[2]})
                        
                        if str(row.get('finalizado')).upper() != "TRUE":
                            with st.form(f"f_ap{idx}"):
                                nome = st.text_input("Seu Nome")
                                valor = st.number_input("Valor R$", 1, 500, 10)
                                opc = ["A", "B", "Empate"] if formato == "LIGA" else ["A", "B"]
                                venci = st.radio("Quem vence?", opc, horizontal=True)
                                if st.form_submit_button("Confirmar Aposta"):
                                    nova_ap = f"{nome}:{valor}:{venci}"
                                    string_ap = f"{row['apostas']}|{nova_ap}" if lista_ap else nova_ap
                                    df_atual.loc[idx, 'apostas'] = string_ap
                                    salvar_db(df_atual); st.rerun()
                        
                        if lista_ap:
                            st.table(pd.DataFrame(lista_ap))

    elif menu == "📊 Classificação" and formato == "LIGA":
        st.subheader("Tabela de Pontos")
        # Lógica de tabela simplificada para teste
        stats = {}
        for _, r in jogos_df.iterrows():
            for t in [r['a'], r['b']]:
                if t not in stats: stats[t] = {"P":0,"J":0}
            if str(r.get('finalizado')).upper() == "TRUE":
                stats[r['a']]["J"]+=1; stats[r['b']]["J"]+=1
                ga, gb = r['gols_a'], r['gols_b']
                if ga > gb: stats[r['a']]["P"]+=3
                elif gb > ga: stats[r['b']]["P"]+=3
                else: stats[r['a']]["P"]+=1; stats[r['b']]["P"]+=1
        st.table(pd.DataFrame.from_dict(stats, orient='index'))

    elif menu == "⚙️ Admin" and is_admin:
        st.warning("Zona de Configuração")
        times_raw = st.text_area("Lista de Times (um por linha)")
        if st.button("GERAR CONFRONTOS"):
            times = [t.strip() for t in times_raw.split("\n") if t.strip()]
            novos = []
            if formato == "LIGA":
                for a, b in combinations(times, 2):
                    novos.append({"torneio_id":t_id, "formato":"LIGA", "a":a, "b":b, "finalizado":"FALSE", "apostas":""})
            else:
                for i in range(0, len(times), 2):
                    novos.append({"torneio_id":t_id, "formato":"COPA", "a":times[i], "b":times[i+1], "finalizado":"FALSE", "apostas":""})
            
            df_novos = pd.DataFrame(novos)
            df_final = pd.concat([df_atual[df_atual['torneio_id'] != t_id], df_novos], ignore_index=True)
            salvar_db(df_final)
            st.rerun()
