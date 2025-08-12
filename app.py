import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import plotly.express as px
from datetime import datetime
import json

# Configuração das APIs do Google
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

# Lê credenciais do Streamlit Secrets
service_account_info = dict(st.secrets["GOOGLE_SERVICE_ACCOUNT"])
creds = ServiceAccountCredentials.from_json_keyfile_dict(service_account_info, scope)
client = gspread.authorize(creds)

# Abre a planilha
sheet = client.open("controle_despesas").sheet1

# Função para carregar dados da planilha
def load_data():
    data = sheet.get_all_records()
    df = pd.DataFrame(data)

    if not df.empty:
        # Converte data para formato brasileiro
        df["Data"] = pd.to_datetime(df["Data"], errors="coerce").dt.strftime("%d/%m/%Y")

        # Ajusta valores
        df["Valor"] = (
            df["Valor"]
            .astype(str)
            .str.replace("R$", "", regex=False)
            .str.replace(",", ".", regex=False)
            .astype(float)
        )
    return df

# Interface Streamlit
st.title("📊 Controle de Despesas")

# Formulário de registro
with st.form("registro_despesa"):
    data = st.date_input("Data", datetime.today())
    tipo = st.text_input("Tipo", "")
    valor = st.text_input("Valor (ex: 26,28 ou 26.28)", "")

    submitted = st.form_submit_button("Registrar")
    if submitted:
        try:
            # Salva na planilha no formato YYYY-MM-DD
            sheet.append_row([data.strftime("%Y-%m-%d"), tipo, valor])
            st.success("✅ Despesa registrada com sucesso!")
        except Exception as e:
            st.error(f"❌ Erro ao registrar: {e}")

# Exibe dados e gráfico
df = load_data()

if not df.empty:
    st.subheader("📅 Despesas Registradas")
    st.dataframe(df)

    st.subheader("📈 Gráfico de Despesas")
    fig = px.bar(df, x="Data", y="Valor", color="Tipo", title="Despesas por Data")
    st.plotly_chart(fig)
else:
    st.info("Nenhuma despesa registrada ainda.")
