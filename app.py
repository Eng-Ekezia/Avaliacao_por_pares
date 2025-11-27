import streamlit as st
import pandas as pd
import gspread
import json
import plotly.express as px
from datetime import datetime

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

    # Busca o ID nos segredos (seja local ou na nuvem)
    id_da_planilha = st.secrets["spreadsheet_id"]
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

# --- NOVA FUNÇÃO INTELIGENTE: SALVAR NOTAS EM ABA ESPECÍFICA ---
def salvar_relatorio_notas(df_final, nome_do_evento):
    # Define o nome da aba baseado no evento atual (ex: "Notas_Seminario_1")
    nome_aba_destino = f"Notas_{nome_do_evento}"
    
    try:
        # Tenta abrir a aba. Se ela existir, limpamos o conteúdo para atualizar
        ws_notas = planilha.worksheet(nome_aba_destino)
        ws_notas.clear()
        mensagem = f"Aba '{nome_aba_destino}' atualizada com sucesso!"
    except:
        # Se der erro (não existe), criamos uma aba nova
        ws_notas = planilha.add_worksheet(title=nome_aba_destino, rows=100, cols=10)
        mensagem = f"Aba '{nome_aba_destino}' criada e salva com sucesso!"
    
    # Prepara os dados para envio (Cabeçalho + Dados)
    dados_para_enviar = [df_final.columns.values.tolist()] + df_final.values.tolist()
    
    # Escreve na planilha
    ws_notas.update(range_name="A1", values=dados_para_enviar)
    st.toast(mensagem, icon="💾")
    return nome_aba_destino

# --- APP ---
try:
    df_config, df_alunos, df_grupos, df_criterios, df_respostas = carregar_dados()

    # === LÓGICA INTELIGENTE DE SELEÇÃO DE EVENTO ===
    evento_ativo = df_config[df_config['Status_Sistema'].str.upper() == 'ABERTO']

    if evento_ativo.empty:
        # Se fechado, pega o primeiro da lista apenas para referência
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
    st.sidebar.title("Navegação")
    modo = st.sidebar.radio("Acesso:", ["Área do Aluno", "Área do Professor"])

    # ==========================================================
    #                 ÁREA DO ALUNO (CARDS)
    # ==========================================================
    if modo == "Área do Aluno":
        st.title(f"🚀 Avaliação: {evento_atual}")
        
        if status_sistema != "ABERTO":
            st.warning(f"O evento '{evento_atual}' está encerrado.")
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
            st.title(f"📊 Painel do Professor ({evento_atual})")
            
            if st.button("🔄 Atualizar Dados"):
                carregar_dados.clear()
                st.rerun()

            if df_respostas.empty:
                st.info("Sem dados.")
            else:
                df_foco = df_respostas[
                    (df_respostas['ID_Avaliacao'] == evento_atual) & 
                    (df_respostas['Tipo'] == 'Par')
                ].copy()

                if not df_foco.empty:
                    ranking = df_foco.groupby('ID_Grupo_Avaliado')['Nota_Total_Calculada'].mean().reset_index()
                    ranking.columns = ['ID_Grupo', 'Nota_Media_Grupo']
                    
                    df_consolidado = pd.merge(
                        df_alunos, 
                        ranking, 
                        left_on='ID_Grupo_Pertencente', 
                        right_on='ID_Grupo', 
                        how='left'
                    )
                    
                    df_consolidado['Nota_FINAL'] = df_consolidado['Nota_Media_Grupo'].fillna(0).round(2)
                    df_exportacao = df_consolidado[['Matricula', 'Nome_Aluno', 'ID_Grupo_Pertencente', 'Nota_FINAL']]

                    st.subheader("📋 Prévia das Notas Finais")
                    st.dataframe(df_exportacao.style.background_gradient(subset=['Nota_FINAL'], cmap='RdYlGn'))

                    # --- BOTÃO MÁGICO PARA SALVAR NA ABA ESPECÍFICA ---
                    st.markdown("---")
                    st.subheader("💾 Consolidar e Arquivar")
                    st.write(f"Ao clicar abaixo, o sistema criará (ou atualizará) a aba **'Notas_{evento_atual}'** no Google Sheets.")
                    
                    if st.button(f"Salvar Notas de '{evento_atual}'"):
                        with st.spinner(f"Gerando aba Notas_{evento_atual}..."):
                            nome_aba_criada = salvar_relatorio_notas(df_exportacao, evento_atual)
                        st.success(f"Sucesso! Os dados estão salvos na aba: {nome_aba_criada}")
                
                else:
                    st.warning("Não há votos de pares suficientes para calcular médias.")

except Exception as e:
    st.error(f"Erro no sistema: {e}")