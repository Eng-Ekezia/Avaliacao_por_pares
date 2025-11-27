import streamlit as st
import pandas as pd
import json
from conexao import conectar_google_sheets

# --- FUNÇÕES DE SERVIÇO (Backend Lógico) ---

@st.cache_data(ttl=60)
def carregar_dados():
    """Carrega todas as abas necessárias da planilha."""
    # Conecta a cada chamada (ou usa cache interno do gspread se houver)
    planilha = conectar_google_sheets()
    
    config = pd.DataFrame(planilha.worksheet("CONFIG_GERAL").get_all_records())
    alunos = pd.DataFrame(planilha.worksheet("ALUNOS").get_all_records())
    grupos = pd.DataFrame(planilha.worksheet("GRUPOS").get_all_records())
    criterios = pd.DataFrame(planilha.worksheet("CRITERIOS").get_all_records())
    respostas = pd.DataFrame(planilha.worksheet("RESPOSTAS").get_all_records())
    return config, alunos, grupos, criterios, respostas

def salvar_voto(dados):
    """Salva uma nova linha na aba RESPOSTAS e limpa o cache."""
    planilha = conectar_google_sheets()
    planilha.worksheet("RESPOSTAS").append_row(dados)
    # Limpa o cache para que o novo voto apareça imediatamente se recarregar
    carregar_dados.clear()

def salvar_relatorio_notas(df_final, nome_do_evento):
    """Cria ou atualiza uma aba específica com as notas consolidadas."""
    planilha = conectar_google_sheets()
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