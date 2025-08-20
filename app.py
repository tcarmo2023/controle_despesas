import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import plotly.express as px
from datetime import datetime, date
import re
import os

# Configuração das APIs do Google
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

@st.cache_resource
def get_google_client():
    try:
        service_account_info = dict(st.secrets["GOOGLE_SERVICE_ACCOUNT"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(service_account_info, scope)
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        st.error(f"❌ Erro de autenticação: {str(e)}")
        return None

client = get_google_client()

if client is not None:
    try:
        sheet = client.open("controle_despesas").sheet1
    except Exception as e:
        st.error(f"❌ Erro ao acessar planilha: {e}")
        st.stop()
else:
    st.error("❌ Não foi possível autenticar com o Google Sheets. Verifique as configurações.")
    st.stop()

@st.cache_data(ttl=300)
def load_data():
    try:
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
        if not df.empty:
            df["Data"] = pd.to_datetime(df["Data"], errors="coerce").dt.strftime("%d/%m/%Y")

            def parse_value(val):
                if isinstance(val, (int, float)):
                    return float(val)
                val_str = str(val).strip()
                val_str = re.sub(r'[^\d.,]', '', val_str)
                if ',' in val_str and '.' in val_str:
                    val_str = val_str.replace('.', '').replace(',', '.')
                elif ',' in val_str:
                    parts = val_str.split(',')
                    if len(parts) > 1 and len(parts[-1]) == 2:
                        val_str = val_str.replace(',', '.')
                    else:
                        val_str = val_str.replace(',', '')
                try:
                    return float(val_str)
                except ValueError:
                    return 0.0
            df["Valor"] = df["Valor"].apply(parse_value)
        return df
    except Exception as e:
        st.error(f"❌ Erro ao carregar dados: {e}")
        return pd.DataFrame()

def validate_inputs(data, tipo, valor):
    errors = []
    if data > date.today():
        errors.append("Data não pode ser futura")
    if not tipo.strip():
        errors.append("Tipo não pode estar vazio")
    try:
        valor_float = float(valor.replace(',', '.'))
        if valor_float <= 0:
            errors.append("Valor deve ser positivo")
    except ValueError:
        errors.append("Valor deve ser um número")
    return errors

def delete_row(row_index):
    try:
        # Adiciona 2 porque a planilha começa na linha 1 e a linha 1 é o cabeçalho
        sheet.delete_rows(row_index + 2)
        st.success("✅ Despesa excluída com sucesso!")
        st.cache_data.clear()
    except Exception as e:
        st.error(f"❌ Erro ao excluir: {e}")

st.title("📊 Controle de Despesas")

tab1, tab2, tab3 = st.tabs(["Registrar Despesa", "Visualizar Dados", "Relatórios"])

with tab1:
    st.subheader("➕ Nova Despesa")
    with st.form("registro_despesa"):
        data = st.date_input("Data", datetime.today(), max_value=date.today())
        tipo = st.text_input("Tipo*", "", help="Ex: Alimentação, Transporte, Moradia")
        valor = st.text_input("Valor (ex: 26,28 ou 26.28)*", "", help="Use vírgula ou ponto como separador decimal")
        
        submitted = st.form_submit_button("💾 Registrar Despesa")
        
        if submitted:
            errors = validate_inputs(data, tipo, valor)
            if errors:
                for error in errors:
                    st.error(f"❌ {error}")
            else:
                try:
                    valor_formatado = valor.replace('.', '').replace(',', '.')
                    sheet.append_row([data.strftime("%Y-%m-%d"), tipo.strip(), valor_formatado])
                    st.success("✅ Despesa registrada com sucesso!")
                    st.cache_data.clear()
                except Exception as e:
                    st.error(f"❌ Erro ao registrar: {e}")

with tab2:
    st.subheader("📅 Despesas Registradas")
    df = load_data()
    if not df.empty:
        col1, col2 = st.columns(2)
        with col1:
            tipos = df["Tipo"].unique()
            tipo_filtro = st.multiselect("Filtrar por Tipo", options=tipos, placeholder="Selecione os tipos")
        with col2:
            datas = df["Data"].unique()
            data_filtro = st.multiselect("Filtrar por Data", options=datas, placeholder="Selecione as datas")
        
        df_filtrado = df
        if tipo_filtro:
            df_filtrado = df_filtrado[df_filtrado["Tipo"].isin(tipo_filtro)]
        if data_filtro:
            df_filtrado = df_filtrado[df_filtrado["Data"].isin(data_filtro)]
        
        # Adiciona índice para referência
        df_filtrado_com_indice = df_filtrado.reset_index()
        
        st.dataframe(df_filtrado_com_indice[["Data", "Tipo", "Valor"]], use_container_width=True)
        
        # Seleção de linha para exclusão
        st.subheader("🗑️ Excluir Despesa")
        if len(df_filtrado_com_indice) > 0:
            row_to_delete = st.selectbox(
                "Selecione a despesa para excluir:",
                options=range(len(df_filtrado_com_indice)),
                format_func=lambda x: f"Data: {df_filtrado_com_indice.iloc[x]['Data']} | Tipo: {df_filtrado_com_indice.iloc[x]['Tipo']} | Valor: R$ {df_filtrado_com_indice.iloc[x]['Valor']:.2f}"
            )
            
            if st.button("❌ Excluir Despesa Selecionada", type="primary"):
                # Encontra o índice real na planilha original
                original_index = df_filtrado_com_indice.iloc[row_to_delete].name
                delete_row(original_index)
        else:
            st.info("Nenhuma despesa para excluir com os filtros atuais.")
        
        total = df_filtrado["Valor"].sum()
        media = df_filtrado["Valor"].mean()
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("💰 Total Gasto", f"R$ {total:,.2f}".replace(',', '_').replace('.', ',').replace('_', '.'))
        with col2:
            st.metric("📊 Média por Despesa", f"R$ {media:,.2f}".replace(',', '_').replace('.', ',').replace('_', '.'))
    else:
        st.info("📝 Nenhuma despesa registrada ainda.")

with tab3:
    st.subheader("📈 Análise de Despesas")
    df = load_data()
    if not df.empty:
        df_plot = df.copy()
        df_plot["Data"] = pd.to_datetime(df_plot["Data"], format="%d/%m/%Y")
        
        st.subheader("📆 Despesas por Data")
        fig = px.bar(df_plot, x="Data", y="Valor", color="Tipo", title="Despesas por Data", labels={"Valor": "Valor (R$)"})
        st.plotly_chart(fig, use_container_width=True)
        
        st.subheader("🥧 Distribuição por Tipo")
        por_tipo = df_plot.groupby("Tipo")["Valor"].sum().reset_index()
        fig2 = px.pie(por_tipo, values="Valor", names="Tipo", title="Percentual por Tipo de Despesa")
        st.plotly_chart(fig2, use_container_width=True)
        
        st.subheader("📈 Evolução Temporal")
        df_tendencia = df_plot.set_index("Data").resample('D').sum().reset_index()
        fig3 = px.line(df_tendencia, x="Data", y="Valor", title="Evolução das Despesas ao Longo do Tempo")
        st.plotly_chart(fig3, use_container_width=True)
    else:
        st.info("📊 Nenhuma despesa registrada para exibir relatórios.")
