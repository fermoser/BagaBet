with t3:
        if st.text_input("Senha", type="password") == "123":
            jogos_tid = df_total[df_total['torneio_id'] == tid]
            rodada_max = jogos_tid['rodada'].max()
            pendentes = jogos_tid[jogos_tid['finalizado'] == 'NÃO']
            
            # Lista quem ainda está jogando
            ativos = [t for t, info in stats.items() if info['status'] == 'Ativo']
            classificados = [t for t, info in stats.items() if info['status'] == 'Classificado']
            eliminados = [t for t, info in stats.items() if info['status'] == 'Eliminado']

            st.write(f"**Status atual:** {len(ativos)} Ativos | {len(classificados)} Classificados | {len(eliminados)} Eliminados")

            if not pendentes.empty:
                st.warning(f"Existem {len(pendentes)} jogos pendentes na Rodada {rodada_max}. Finalize-os primeiro.")
            
            # SE AINDA HÁ TIMES ATIVOS -> CONTINUA SUÍÇO
            elif len(ativos) >= 2:
                if st.button("Gerar Próxima Rodada Suíça"):
                    hist = jogos_tid.to_dict('records')
                    novos_pares = realizar_pareamento(stats, hist)
                    if novos_pares:
                        novos_jogos = []
                        for p in novos_pares:
                            novos_jogos.append({'torneio_id': tid, 'rodada': rodada_max+1, 'a': p[0], 'b': p[1], 'gols_a': 1 if p[1]=="BYE" else 0, 'gols_b': 0, 'finalizado': 'SIM' if p[1]=="BYE" else 'NÃO', 'fase': 'Suíça'})
                        conn.update(worksheet="Suico", data=pd.concat([df_total, pd.DataFrame(novos_jogos)]))
                        st.cache_data.clear(); st.rerun()
                    else:
                        st.error("Não foi possível gerar novos pares sem repetir confrontos!")

            # SE NÃO HÁ MAIS ATIVOS -> HORA DO MATA-MATA
            else:
                st.success("🏁 Fase Suíça Encerrada!")
                
                # Ordenar classificados pelo ranking (V -> Buchholz)
                classificados.sort(key=lambda x: (stats[x]['V'], stats[x]['Buchholz']), reverse=True)
                
                # CASO 1: 3 CLASSIFICADOS (Para torneios de 6 times)
                if len(classificados) == 3:
                    st.info(f"Mata-Mata (Caso 1): 1º ({classificados[0]}) na Final. Semifinal: {classificados[1]} vs {classificados[2]}")
                    if st.button("Gerar Semifinal"):
                        jogo_final = [
                            {'torneio_id': tid, 'rodada': rodada_max + 1, 'a': classificados[1], 'b': classificados[2], 'gols_a': 0, 'gols_b': 0, 'finalizado': 'NÃO', 'fase': 'Semifinal'}
                        ]
                        # O 1º lugar não joga agora, ele espera o vencedor
                        conn.update(worksheet="Suico", data=pd.concat([df_total, pd.DataFrame(jogo_final)]))
                        st.cache_data.clear(); st.rerun()
                
                # Se houver mais ou menos, o sistema avisa (podemos expandir os outros Casos aqui)
                else:
                    st.write("Ranking Final dos Classificados:")
                    st.write(classificados)
                    if st.button("Apagar Torneio para Novo Teste"):
                        conn.update(worksheet="Suico", data=df_total[df_total['torneio_id'] != tid])
                        st.cache_data.clear(); st.rerun()
