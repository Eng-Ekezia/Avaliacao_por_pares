import streamlit as st
import gspread

def conectar_google_sheets():
    """
    Estabelece a conexão com o Google Sheets usando segredos do Streamlit 
    ou arquivo local, e retorna o objeto da planilha aberta.
    """
    # Tenta conectar usando segredos do Streamlit (Nuvem)
    if "gcp_service_account" in st.secrets:
        dados_credenciais = st.secrets["gcp_service_account"]
        client = gspread.service_account_from_dict(dados_credenciais)
    # Se não achar segredos, tenta procurar o arquivo local (Tablet/PC)
    else:
        client = gspread.service_account(filename="creds.json")

    # O ID agora vem do secrets (configurado no passo anterior)
    id_da_planilha = st.secrets["spreadsheet_id"]
    return client.open_by_key(id_da_planilha)