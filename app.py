import streamlit as st
import pandas as pd
import json
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
from servicos import carregar_dados, salvar_voto, salvar_relatorio_notas, gerar_estatisticas_avancadas

# --- CONFIGURAÇÃO VISUAL ---
st.set_page_config(page_title="Avaliação 360°", layout="wide", page_icon="🎓")

# --- CSS PERSONALIZADO ---
st.markdown("""
<style>
    /* Botões grandes */
    .stButton button {
        width: 100%;
        height: 60px;
        border-radius: 8px;
        font-weight: 600;
    }
    /* CORREÇÃO DO DARK MODE NOS CARDS DE KPI */
    div[data-testid="stMetric"] {
        background-color: #f0f2f6; /* Fundo cinza claro */
        padding: 15px;
        border-radius: 10px;
        border: 1px solid #d6d6d6;
    }
    /* Força texto escuro nos valores e labels dentro do card */
    div[data-testid="stMetric"] label {
        color: #31333F !important; /* Cinza escuro */
    }
    div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
        color: #000000 !important; /* Preto absoluto */
    }
</style>
""", unsafe_allow_html=True)

# --- APP ---
try:
    # Carregamento de dados
    df_config, df_alunos, df_grupos, df_criterios, df_respostas = carregar_dados()

    # === LÓGICA DE SELEÇÃO DE EVENTO ===
    evento_ativo = df_config[df_config['Status_Sistema'].str.upper() == 'ABERTO']

    if evento_ativo.empty:
        config_atual = df_config.iloc[0]
        status_sistema = "FECHADO"
        evento_atual = config_atual['ID_Avaliacao_Atual']
        senha_professor = str(config_atual['Senha_Professor'])
        if 'modo' not in st.session_state: st.session_state['modo'] = "Área do Professor"
    else:
        config_atual = evento_ativo.iloc[0]
        evento_atual = config_atual['ID_Avaliacao_Atual']
        status_sistema = "ABERTO"
        senha_professor = str(config_atual['Senha_Professor'])

    # Navegação Lateral
    with st.sidebar:
        st.header("Navegação")
        modo = st.radio("Selecione o perfil:", ["Área do Aluno", "Área do Professor"])
        st.divider()
        st.caption(f"📅 Evento: {evento_atual}")
        st.caption(f"🔴 Status: {status_sistema}")

    # ==========================================================
    #                 ÁREA DO ALUNO
    # ==========================================================
    if modo == "Área do Aluno":
        st.title(f"🚀 Avaliação: {evento_atual}")
        
        if status_sistema != "ABERTO":
            st.warning("Este evento já foi encerrado.")
            st.stop()

        if 'aluno_logado' not in st.session_state:
            col1, col2 = st.columns([1, 2])
            with col1:
                matricula = st.text_input("Digite sua Matrícula:")
                if st.button("Entrar"):
                    df_alunos['Matricula'] = df_alunos['Matricula'].astype(str)
                    busca = df_alunos[df_alunos['Matricula'] == str(matricula)]
                    if not busca.empty:
                        st.session_state['aluno_logado'] = busca.iloc[0]
                        st.rerun()
                    else:
                        st.error("Matrícula não encontrada.")
        
        else:
            aluno = st.session_state['aluno_logado']
            c1, c2 = st.columns([4,1])
            c1.success(f"👋 Olá, **{aluno['Nome_Aluno']}** | Grupo: {aluno['ID_Grupo_Pertencente']}")
            if c2.button("Sair"):
                del st.session_state['aluno_logado']
                st.rerun()

            # Lógica de seleção de Cards (Mantida similar, apenas visual ajustado)
            if 'grupo_selecionado_id' not in st.session_state:
                st.subheader("Quem está apresentando?")
                meus_votos = pd.DataFrame()
                if not df_respostas.empty:
                    meus_votos = df_respostas[
                        (df_respostas['ID_Avaliacao'] == evento_atual) & 
                        (df_respostas['Matricula_Avaliador'].astype(str) == str(aluno['Matricula']))
                    ]
                
                colunas = st.columns(3)
                for index, linha in df_grupos.iterrows():
                    grupo_id = str(linha['ID_Grupo'])
                    grupo_nome = linha['Nome_Tema_Projeto']
                    
                    ja_avaliou = False
                    if not meus_votos.empty:
                        if grupo_id in meus_votos['ID_Grupo_Avaliado'].astype(str).values:
                            ja_avaliou = True
                    
                    eh_meu_grupo = grupo_id == str(aluno['ID_Grupo_Pertencente'])
                    
                    with colunas[index % 3]:
                        if ja_avaliou:
                            st.button(f"✅ {grupo_nome}", key=grupo_id, disabled=True)
                        elif eh_meu_grupo:
                            if st.button(f"🟦 {grupo_nome} (Auto)", key=grupo_id):
                                st.session_state['grupo_selecionado_id'] = grupo_id
                                st.session_state['grupo_selecionado_nome'] = grupo_nome
                                st.session_state['tipo_avaliacao'] = "Autoavaliacao"
                                st.rerun()
                        else:
                            if st.button(f"⬜ {grupo_nome} (Avaliar)", key=grupo_id):
                                st.session_state['grupo_selecionado_id'] = grupo_id
                                st.session_state['grupo_selecionado_nome'] = grupo_nome
                                st.session_state['tipo_avaliacao'] = "Par"
                                st.rerun()

            else:
                st.markdown(f"### 📝 Avaliando: {st.session_state['grupo_selecionado_nome']}")
                if st.button("⬅️ Voltar"):
                    del st.session_state['grupo_selecionado_id']
                    st.rerun()
                
                with st.form("form_av"):
                    notas = {}
                    total = 0
                    for _, crit in df_criterios.iterrows():
                        st.write(f"**{crit['Nome_Criterio']}**")
                        n = st.slider(f"Nota (1-5) para {crit['Nome_Criterio']}", 1, 5, 3, key=crit['Nome_Criterio'])
                        total += n * crit['Peso']
                        notas[crit['Nome_Criterio']] = n
                    
                    obs = st.text_area("Feedback (Opcional)")
                    
                    if st.form_submit_button("Confirmar"):
                        dados = [
                            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            evento_atual,
                            str(aluno['Matricula']),
                            str(st.session_state['grupo_selecionado_id']),
                            st.session_state['grupo_selecionado_nome'],
                            total,
                            json.dumps(notas, ensure_ascii=False),
                            obs,
                            st.session_state['tipo_avaliacao']
                        ]
                        salvar_voto(dados)
                        st.success("Voto computado!")
                        del st.session_state['grupo_selecionado_id']
                        st.rerun()

    # ==========================================================
    #                 ÁREA DO PROFESSOR (DASHBOARD 2.0)
    # ==========================================================
    elif modo == "Área do Professor":
        senha = st.sidebar.text_input("Senha Admin", type="password")
        if senha == senha_professor:
            st.title(f"📊 Dashboard Analítico: {evento_atual}")
            
            if st.button("🔄 Recalcular Estatísticas"):
                carregar_dados.clear()
                st.rerun()

            # --- PROCESSAMENTO INTELIGENTE ---
            df_final, df_radar = gerar_estatisticas_avancadas(df_respostas, df_alunos, evento_atual)

            if df_final.empty:
                st.info("Aguardando votos para gerar estatísticas.")
            else:
                # KPIS GERAIS
                k1, k2, k3, k4 = st.columns(4)
                k1.metric("Grupos Avaliados", len(df_final))
                k2.metric("Total de Votos", int(df_final['Contagem'].sum()))
                k3.metric("Média Geral da Turma", f"{df_final['Media_Saneada'].mean():.2f}")
                
                # Alerta de Polêmica (Maior Desvio Padrão)
                max_std = df_final.loc[df_final['Desvio_Padrao'].idxmax()]
                k4.metric("Maior Polêmica", max_std['Nome_Aluno'], f"Std: {max_std['Desvio_Padrao']:.2f}", delta_color="inverse")

                st.divider()

                # --- ABAS DE ANÁLISE ---
                tab1, tab2, tab3 = st.tabs(["🏆 Ranking & Deltas", "🕸️ Radar de Competências", "📈 Dispersão & Outliers"])

                with tab1:
                    st.subheader("Notas Finais Consolidadas")
                    st.caption("A 'Nota Final' já desconsidera outliers (notas extremas). O 'Delta' mostra a diferença entre a Autoavaliação e a nota da Turma.")
                    
                    # Formatação para exibição
                    df_show = df_final[['Nome_Aluno', 'ID_Grupo_Pertencente', 'Media_Saneada', 'Nota_Autoavaliacao', 'Delta_Auto', 'Contagem']].copy()
                    df_show = df_show.sort_values('Media_Saneada', ascending=False)
                    
                    st.dataframe(
                        df_show.style.format("{:.2f}", subset=['Media_Saneada', 'Nota_Autoavaliacao', 'Delta_Auto'])
                        .background_gradient(subset=['Media_Saneada'], cmap='Greens')
                        .bar(subset=['Delta_Auto'], align='mid', color=['#d65f5f', '#5fba7d'])
                    , use_container_width=True)

                    if st.button(f"💾 Exportar Relatório Oficial de '{evento_atual}'"):
                        aba = salvar_relatorio_notas(df_show, evento_atual)

                with tab2:
                    st.subheader("Análise por Critério")
                    if not df_radar.empty:
                        # Seletor de Grupos para comparar
                        grupos_disp = df_final['Nome_Aluno'].unique()
                        selecao = st.multiselect("Compare Grupos:", grupos_disp, default=grupos_disp[:2])
                        
                        if selecao:
                            # Filtra IDs baseados nos nomes selecionados
                            ids_sel = df_final[df_final['Nome_Aluno'].isin(selecao)]['ID_Grupo_Pertencente'].values
                            df_radar_filt = df_radar[df_radar['ID_Grupo_Avaliado'].isin(ids_sel)]
                            
                            # Criação do Radar Chart
                            fig = go.Figure()
                            categories = df_radar.columns.difference(['ID_Grupo_Avaliado'])
                            
                            for g_id in ids_sel:
                                nome_g = df_final[df_final['ID_Grupo_Pertencente']==g_id]['Nome_Aluno'].values[0]
                                valores = df_radar_filt[df_radar_filt['ID_Grupo_Avaliado']==g_id][categories].values.flatten().tolist()
                                # Fecha o ciclo do radar
                                valores += valores[:1]
                                cats_closed = list(categories) + [list(categories)[0]]
                                
                                fig.add_trace(go.Scatterpolar(
                                    r=valores, theta=cats_closed, fill='toself', name=nome_g
                                ))

                            fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 5])), showlegend=True)
                            st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.warning("Sem dados detalhados para o radar.")

                with tab3:
                    st.subheader("Dispersão e Consenso")
                    st.caption("Grupos no topo têm notas maiores. Grupos à direita têm maior divergência de opinião (polêmicos).")
                    
                    fig_scat = px.scatter(
                        df_final, 
                        x="Desvio_Padrao", 
                        y="Media_Saneada", 
                        size="Contagem", 
                        color="Delta_Auto",
                        hover_name="Nome_Aluno",
                        text="ID_Grupo_Pertencente",
                        color_continuous_scale="RdYlGn_r", # Vermelho se delta for alto (superestimado)
                        labels={"Desvio_Padrao": "Divergência (Desvio Padrão)", "Media_Saneada": "Nota Final (Saneada)"}
                    )
                    fig_scat.add_vline(x=0.8, line_dash="dash", annotation_text="Alta Polêmica")
                    st.plotly_chart(fig_scat, use_container_width=True)

except Exception as e:
    st.error(f"Erro na aplicação: {e}")