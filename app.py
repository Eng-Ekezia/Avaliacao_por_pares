import streamlit as st
import pandas as pd
import gspread
import json
import plotly.express as px
from datetime import datetime
from gspread.utils import rowcol_to_a1

# --- CONFIGURAÇÃO VISUAL ---
st.set_page_config(page_title="Avaliação Dinâmica", layout="wide")

# --- CSS PERSONALIZADO ---
st.markdown("""
<style>
    .stButton button {
        width: 100%;
        height: 80px;
        border-radius: 10px;
        font-weight: bold;
        font-size: 18px;
    }
    div[data-testid="stMetric"] {
        background-color: #f0f2f6;
        padding: 10px;
        border-radius: 10px;
    }
</style>
""", unsafe_allow_html=True)

# --- CONEXÃO ---
@st.cache_resource
def conectar_google_sheets():
    # Tenta conectar usando segredos do Streamlit (Nuvem)
    if "gcp_service_account" in st.secrets:
        dados_credenciais = st.secrets["gcp_service_account"]
        client = gspread.service_account_from_dict(dados_credenciais)
    # Se não achar segredos, tenta procurar o arquivo local (Tablet/PC)
    else:
        client = gspread.service_account(filename="creds.json")
    # --- COLOQUE SEU ID AQUI ---
    id_da_planilha = "1RS5RrLAR_QjI8Ba55oXduBOlaobVNJnhfc6SKD9MpRI"
    return client.open_by_key(id_da_planilha)
try:
    planilha = conectar_google_sheets()
except Exception as e:
    st.error(f"Erro de conexão: {e}")
    st.stop()

# --- CARREGAMENTO DE DADOS (COM CACHE) ---
@st.cache_data(ttl=60)
def carregar_dados():
    config = pd.DataFrame(planilha.worksheet("CONFIG_GERAL").get_all_records())
    alunos = pd.DataFrame(planilha.worksheet("ALUNOS").get_all_records())
    grupos = pd.DataFrame(planilha.worksheet("GRUPOS").get_all_records())
    criterios = pd.DataFrame(planilha.worksheet("CRITERIOS").get_all_records())
    respostas = pd.DataFrame(planilha.worksheet("RESPOSTAS").get_all_records())
    return config, alunos, grupos, criterios, respostas

def salvar_voto(dados):
    planilha.worksheet("RESPOSTAS").append_row(dados)
    carregar_dados.clear()

# --- NOVA FUNÇÃO: SALVAR NOTAS FINAIS NA ABA 'NOTAS' ---
def salvar_relatorio_notas(df_final):
    ws_notas = planilha.worksheet("NOTAS")
    
    # Limpa o conteúdo antigo (mantendo o cabeçalho se quiser, mas aqui vamos reescrever tudo)
    ws_notas.clear()
    
    # Prepara os dados para envio (Lista de Listas)
    # Adiciona o cabeçalho manualmente para garantir
    dados_para_enviar = [df_final.columns.values.tolist()] + df_final.values.tolist()
    
    # Escreve na planilha
    ws_notas.update(range_name="A1", values=dados_para_enviar)
    st.toast("Notas salvas na aba NOTAS com sucesso!", icon="💾")

# --- APP ---
try:
    df_config, df_alunos, df_grupos, df_criterios, df_respostas = carregar_dados()

    if df_config.empty: st.stop()
    evento_atual = df_config.iloc[0]['ID_Avaliacao_Atual']
    status_sistema = df_config.iloc[0]['Status_Sistema']
    senha_professor = str(df_config.iloc[0]['Senha_Professor'])

    st.sidebar.title("Navegação")
    modo = st.sidebar.radio("Acesso:", ["Área do Aluno", "Área do Professor"])

    # ==========================================================
    #                 ÁREA DO ALUNO (CARDS)
    # ==========================================================
    if modo == "Área do Aluno":
        st.title(f"🚀 Avaliação: {evento_atual}")
        
        if status_sistema != "ABERTO":
            st.warning("Avaliações Fechadas.")
            st.stop()

        if 'aluno_logado' not in st.session_state:
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
            col_u1, col_u2 = st.columns([3,1])
            col_u1.success(f"Olá, **{aluno['Nome_Aluno']}** (Seu Grupo: {aluno['ID_Grupo_Pertencente']})")
            if col_u2.button("Sair"):
                del st.session_state['aluno_logado']
                st.rerun()

            if 'grupo_selecionado_id' not in st.session_state:
                st.subheader("Quem está apresentando agora?")
                
                meus_votos = pd.DataFrame()
                if not df_respostas.empty:
                    meus_votos = df_respostas[
                        (df_respostas['ID_Avaliacao'] == evento_atual) & 
                        (df_respostas['Matricula_Avaliador'].astype(str) == str(aluno['Matricula']))
                    ]
                
                colunas = st.columns(3)
                for index, linha in df_grupos.iterrows():
                    grupo_id = linha['ID_Grupo']
                    grupo_nome = linha['Nome_Tema_Projeto']
                    
                    ja_avaliou = False
                    if not meus_votos.empty:
                        if grupo_id in meus_votos['ID_Grupo_Avaliado'].values:
                            ja_avaliou = True
                    
                    eh_meu_grupo = str(grupo_id) == str(aluno['ID_Grupo_Pertencente'])
                    
                    with colunas[index % 3]:
                        if ja_avaliou:
                            st.button(f"✅ {grupo_nome}\n(Concluído)", key=f"btn_{grupo_id}", disabled=True)
                        elif eh_meu_grupo:
                            if st.button(f"🟦 {grupo_nome}\n(Autoavaliação)", key=f"btn_{grupo_id}"):
                                st.session_state['grupo_selecionado_id'] = grupo_id
                                st.session_state['grupo_selecionado_nome'] = grupo_nome
                                st.session_state['tipo_avaliacao'] = "Autoavaliacao"
                                st.rerun()
                        else:
                            if st.button(f"⬜ {grupo_nome}\n(Avaliar)", key=f"btn_{grupo_id}"):
                                st.session_state['grupo_selecionado_id'] = grupo_id
                                st.session_state['grupo_selecionado_nome'] = grupo_nome
                                st.session_state['tipo_avaliacao'] = "Par"
                                st.rerun()

            else:
                st.markdown(f"## 📝 Avaliando: {st.session_state['grupo_selecionado_nome']}")
                if st.button("⬅️ Voltar"):
                    del st.session_state['grupo_selecionado_id']
                    st.rerun()
                
                with st.form("form_dinamico"):
                    st.info("Use a escala de 1 a 5 para cada critério.")
                    notas_dadas = {}
                    pontos_totais = 0
                    
                    for i, crit in df_criterios.iterrows():
                        st.markdown(f"**{crit['Nome_Criterio']}** (Peso: {crit['Peso']})")
                        st.caption(crit['Descricao'])
                        nota = st.radio(f"Nota {crit['Nome_Criterio']}:", [1, 2, 3, 4, 5], horizontal=True, key=f"crit_{i}")
                        pontos = nota * crit['Peso']
                        pontos_totais += pontos
                        notas_dadas[crit['Nome_Criterio']] = nota
                        st.divider()

                    comentarios = st.text_area("Comentários Finais")
                    
                    if st.form_submit_button("Confirmar Avaliação"):
                        json_detalhes = json.dumps(notas_dadas, ensure_ascii=False)
                        dados_salvar = [
                            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            evento_atual,
                            str(aluno['Matricula']),
                            int(st.session_state['grupo_selecionado_id']),
                            st.session_state['grupo_selecionado_nome'],
                            pontos_totais,
                            json_detalhes,
                            comentarios,
                            st.session_state['tipo_avaliacao']
                        ]
                        salvar_voto(dados_salvar)
                        st.success("Salvo!")
                        del st.session_state['grupo_selecionado_id']
                        st.rerun()

    # ==========================================================
    #                 ÁREA DO PROFESSOR (DASHBOARD)
    # ==========================================================
    elif modo == "Área do Professor":
        senha = st.sidebar.text_input("Senha", type="password")
        if senha == senha_professor:
            st.title("📊 Painel do Professor")
            
            if st.button("🔄 Atualizar Dados"):
                carregar_dados.clear()
                st.rerun()

            if df_respostas.empty:
                st.info("Sem dados.")
            else:
                # 1. Calcula as médias por Grupo (Considerando apenas PARES)
                df_foco = df_respostas[
                    (df_respostas['ID_Avaliacao'] == evento_atual) & 
                    (df_respostas['Tipo'] == 'Par')
                ].copy()

                if not df_foco.empty:
                    # Agrupa por ID do Grupo para garantir precisão
                    ranking = df_foco.groupby('ID_Grupo_Avaliado')['Nota_Total_Calculada'].mean().reset_index()
                    ranking.columns = ['ID_Grupo', 'Nota_Media_Grupo']
                    
                    # 2. Cruza com os Alunos para gerar a lista final
                    # Merge: Tabela Alunos + Tabela de Notas dos Grupos
                    df_consolidado = pd.merge(
                        df_alunos, 
                        ranking, 
                        left_on='ID_Grupo_Pertencente', 
                        right_on='ID_Grupo', 
                        how='left'
                    )
                    
                    # Limpeza e formatação
                    df_consolidado['Nota_FINAL'] = df_consolidado['Nota_Media_Grupo'].fillna(0).round(2)
                    
                    # Seleciona apenas as colunas pedidas
                    df_exportacao = df_consolidado[['Matricula', 'Nome_Aluno', 'ID_Grupo_Pertencente', 'Nota_FINAL']]

                    st.subheader("📋 Prévia das Notas Finais (Alunos)")
                    st.dataframe(df_exportacao.style.background_gradient(subset=['Nota_FINAL'], cmap='RdYlGn'))

                    # --- BOTÃO MÁGICO PARA SALVAR ---
                    st.markdown("---")
                    st.subheader("💾 Fechamento")
                    st.write("Clique abaixo para escrever essas notas na aba 'NOTAS' da planilha.")
                    
                    if st.button("Salvar Notas Finais na Planilha"):
                        with st.spinner("Escrevendo na aba NOTAS..."):
                            salvar_relatorio_notas(df_exportacao)
                        st.success("Sucesso! Verifique a aba 'NOTAS' no Google Sheets.")
                
                else:
                    st.warning("Não há votos de pares suficientes para calcular médias.")

except Exception as e:
    st.error(f"Erro no sistema: {e}")