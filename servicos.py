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
    Processa os dados brutos e retorna um DataFrame enriquecido com:
    - Média Saneada (sem outliers)
    - Desvio Padrão (Consenso)
    - Delta de Autoavaliação
    - Detalhamento por Critério (para Radar)
    """
    if df_respostas.empty:
        return pd.DataFrame(), pd.DataFrame()

    # Filtra apenas o evento atual
    df = df_respostas[df_respostas['ID_Avaliacao'] == evento_atual].copy()
    
    # Garante tipos corretos
    df['ID_Grupo_Avaliado'] = df['ID_Grupo_Avaliado'].astype(str)
    df['Nota_Total_Calculada'] = pd.to_numeric(df['Nota_Total_Calculada'])

    # --- 1. SEPARAÇÃO PAR vs AUTO ---
    pares = df[df['Tipo'] == 'Par']
    auto = df[df['Tipo'] != 'Par']

    # --- 2. CÁLCULO ESTATÍSTICO DOS PARES ---
    # Agrupa por grupo avaliado e aplica métricas
    stats = pares.groupby('ID_Grupo_Avaliado')['Nota_Total_Calculada'].agg(
        Media_Bruta='mean',
        Desvio_Padrao='std',
        Contagem='count',
        Media_Saneada=_remover_outliers
    ).reset_index()

    # Trata valores nulos (grupos com 1 voto têm std NaN)
    stats['Desvio_Padrao'] = stats['Desvio_Padrao'].fillna(0)
    
    # --- 3. PROCESSAMENTO DA AUTOAVALIAÇÃO ---
    # Pega a nota que o grupo se deu (se houver múltipla, tira média)
    auto_notas = auto.groupby('ID_Grupo_Avaliado')['Nota_Total_Calculada'].mean().reset_index()
    auto_notas.rename(columns={'Nota_Total_Calculada': 'Nota_Autoavaliacao'}, inplace=True)

    # --- 4. CONSOLIDAÇÃO FINAL ---
    df_final = pd.merge(stats, auto_notas, on='ID_Grupo_Avaliado', how='left')
    
    # Calcula o DELTA (Diferença entre o que acham e o que o grupo acha)
    # Delta Positivo = Grupo se superestimou | Delta Negativo = Grupo se subestimou
    df_final['Delta_Auto'] = df_final['Nota_Autoavaliacao'] - df_final['Media_Saneada']
    df_final['Delta_Auto'] = df_final['Delta_Auto'].fillna(0)

    # Traz nomes dos alunos e grupos para exibição
    df_final = pd.merge(df_final, df_alunos[['ID_Grupo_Pertencente', 'Nome_Aluno', 'Matricula']], 
                        left_on='ID_Grupo_Avaliado', right_on='ID_Grupo_Pertencente', how='left')

    # --- 5. DETALHAMENTO POR CRITÉRIO (Para Gráfico de Radar) ---
    # Expande o JSON de detalhes das notas
    lista_detalhes = []
    for _, row in pares.iterrows():
        try:
            notas_dict = json.loads(row['Detalhes_Notas'])
            notas_dict['ID_Grupo_Avaliado'] = row['ID_Grupo_Avaliado']
            lista_detalhes.append(notas_dict)
        except:
            continue
            
    df_detalhado = pd.DataFrame(lista_detalhes)
    # Calcula média de cada critério por grupo
    if not df_detalhado.empty:
        df_radar = df_detalhado.groupby('ID_Grupo_Avaliado').mean().reset_index()
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