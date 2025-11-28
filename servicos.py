import streamlit as st
import pandas as pd
import json
import numpy as np
from conexao import conectar_google_sheets

# --- FUNÇÕES UTILITÁRIAS ---

def _remover_outliers(series):
    """
    Calcula a média removendo notas discrepantes (IQR Method).
    Só aplica se houver mais de 4 votos.
    """
    if len(series) < 4:
        return series.mean()
    
    q1 = series.quantile(0.25)
    q3 = series.quantile(0.75)
    iqr = q3 - q1
    limite_inferior = q1 - 1.5 * iqr
    limite_superior = q3 + 1.5 * iqr
    
    # Filtra apenas os valores dentro do intervalo aceitável
    saneada = series[(series >= limite_inferior) & (series <= limite_superior)]
    
    # Se filtrar tudo (muito raro), retorna a média original
    return saneada.mean() if not saneada.empty else series.mean()

# --- FUNÇÕES PRINCIPAIS ---

@st.cache_data(ttl=60)
def carregar_dados():
    """Carrega todas as abas necessárias da planilha."""
    planilha = conectar_google_sheets()
    
    config = pd.DataFrame(planilha.worksheet("CONFIG_GERAL").get_all_records())
    # Garante que Matricula e ID_Grupo sejam string para evitar erros de merge
    alunos = pd.DataFrame(planilha.worksheet("ALUNOS").get_all_records())
    alunos['Matricula'] = alunos['Matricula'].astype(str)
    alunos['ID_Grupo_Pertencente'] = alunos['ID_Grupo_Pertencente'].astype(str)
    
    grupos = pd.DataFrame(planilha.worksheet("GRUPOS").get_all_records())
    grupos['ID_Grupo'] = grupos['ID_Grupo'].astype(str)
    
    criterios = pd.DataFrame(planilha.worksheet("CRITERIOS").get_all_records())
    respostas = pd.DataFrame(planilha.worksheet("RESPOSTAS").get_all_records())
    
    return config, alunos, grupos, criterios, respostas

def gerar_estatisticas_avancadas(df_respostas, df_alunos, evento_atual):
    """
    Processa estatísticas com tratamento rigoroso de tipos (String/Int) para evitar erros no Radar.
    """
    if df_respostas.empty:
        return pd.DataFrame(), pd.DataFrame()

    # Filtra evento e copia
    df = df_respostas[df_respostas['ID_Avaliacao'] == evento_atual].copy()
    
    # === FORÇA TIPAGEM STRING NOS IDs PARA EVITAR ERROS DE MERGE ===
    df['ID_Grupo_Avaliado'] = df['ID_Grupo_Avaliado'].astype(str).str.strip()
    df_alunos['ID_Grupo_Pertencente'] = df_alunos['ID_Grupo_Pertencente'].astype(str).str.strip()
    
    # Garante numérico para nota
    df['Nota_Total_Calculada'] = pd.to_numeric(df['Nota_Total_Calculada'], errors='coerce').fillna(0)

    # Separação
    pares = df[df['Tipo'] == 'Par']
    auto = df[df['Tipo'] != 'Par']

    # --- ESTATÍSTICAS ---
    stats = pares.groupby('ID_Grupo_Avaliado')['Nota_Total_Calculada'].agg(
        Media_Bruta='mean',
        Desvio_Padrao='std',
        Contagem='count',
        Media_Saneada=_remover_outliers
    ).reset_index()
    stats['Desvio_Padrao'] = stats['Desvio_Padrao'].fillna(0)
    
    # --- AUTOAVALIAÇÃO ---
    auto_notas = auto.groupby('ID_Grupo_Avaliado')['Nota_Total_Calculada'].mean().reset_index()
    auto_notas.rename(columns={'Nota_Total_Calculada': 'Nota_Autoavaliacao'}, inplace=True)

    # --- CONSOLIDAÇÃO ---
    df_final = pd.merge(stats, auto_notas, on='ID_Grupo_Avaliado', how='left')
    df_final['Delta_Auto'] = df_final['Nota_Autoavaliacao'] - df_final['Media_Saneada']
    df_final['Delta_Auto'] = df_final['Delta_Auto'].fillna(0)

    # Merge com Nomes (Garante que chave da direita também é string)
    df_final = pd.merge(df_final, df_alunos[['ID_Grupo_Pertencente', 'Nome_Aluno', 'Matricula']], 
                        left_on='ID_Grupo_Avaliado', right_on='ID_Grupo_Pertencente', how='left')

    # --- RADAR (CRITÉRIOS) ---
    lista_detalhes = []
    for _, row in pares.iterrows():
        try:
            # Tenta ler o JSON
            notas_dict = json.loads(row['Detalhes_Notas'])
            # Garante que o ID anexado ao dict é string limpa
            notas_dict['ID_Grupo_Avaliado'] = str(row['ID_Grupo_Avaliado']).strip()
            lista_detalhes.append(notas_dict)
        except:
            continue
            
    if lista_detalhes:
        df_detalhado = pd.DataFrame(lista_detalhes)
        # Groupby usando a coluna de ID garantida como string
        df_radar = df_detalhado.groupby('ID_Grupo_Avaliado').mean(numeric_only=True).reset_index()
    else:
        df_radar = pd.DataFrame()

    return df_final, df_radar

def salvar_voto(dados):
    planilha = conectar_google_sheets()
    planilha.worksheet("RESPOSTAS").append_row(dados)
    carregar_dados.clear()

def salvar_relatorio_notas(df_final, nome_do_evento):
    planilha = conectar_google_sheets()
    nome_aba_destino = f"Notas_{nome_do_evento}"
    
    try:
        ws_notas = planilha.worksheet(nome_aba_destino)
        ws_notas.clear()
        mensagem = f"Aba '{nome_aba_destino}' atualizada!"
    except:
        ws_notas = planilha.add_worksheet(title=nome_aba_destino, rows=100, cols=20)
        mensagem = f"Aba '{nome_aba_destino}' criada!"
    
    dados_para_enviar = [df_final.columns.values.tolist()] + df_final.values.tolist()
    ws_notas.update(range_name="A1", values=dados_para_enviar)
    st.toast(mensagem, icon="💾")
    return nome_aba_destino