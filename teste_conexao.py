import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Configuração
scope = ["https://spreadsheets.google.com/feeds", 'https://www.googleapis.com/auth/spreadsheets',
         "https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]

# Conecta usando o arquivo que você subiu
creds = ServiceAccountCredentials.from_json_keyfile_name("creds.json", scope)
client = gspread.authorize(creds)

# Tenta abrir a planilha (Coloque o nome EXATO da sua planilha aqui)
try:
    sheet = client.open("Avaliação-por-Pares-Python").sheet1
    print("Sucesso! Conectado à planilha.")
    print("Conteúdo da primeira linha:", sheet.row_values(1))
except Exception as e:
    print("Erro ao conectar:", e)