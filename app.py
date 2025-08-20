import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import plotly.express as px
from datetime import datetime, date
import json
import re

# Configuração das APIs do Google
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

# Lê credenciais do Streamlit Secrets (string JSON → dicionário)
@st.cache_resource
def get_google_client():
    try:
        service_account_info = json.loads(st.secrets["GOOGLE_SERVICE_ACCOUNT"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(service_account_info, scope)
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        st.error(f"Erro de autenticação: {e}")
        return None

client = get_google_client()

# Abre a planilha
try:
    sheet = client.open("controle_despesas").sheet1
except Exception as e:
    st.error(f"Erro ao acessar planilha: {e}")
    st.stop()

# Função para carregar dados da planilha com cache
@st.cache_data(ttl=300)  # Cache de 5 minutos
def load_data():
    try:
        data = sheet.get_all_records()
        df = pd.DataFrame(data)

        if not df.empty:
            # Converte data para formato brasileiro
            df["Data"] = pd.to_datetime(df["Data"], errors="coerce").dt.strftime("%d/%m/%Y")

            # Ajusta valores com tratamento mais robusto
            def parse_value(val):
                if isinstance(val, (int, float)):
                    return float(val)
                
                val_str = str(val).strip()
                # Remove qualquer caractere não numérico exceto ponto e vírgula
                val_str = re.sub(r'[^\d.,]', '', val_str)
                
                # Substitui vírgula por ponto se for o separador decimal
                if ',' in val_str and '.' in val_str:
                    # Se tem ambos, assume que vírgula é decimal e ponto é milhar
                    val_str = val_str.replace('.', '').replace(',', '.')
                elif ',' in val_str:
                    # Se só tem vírgula, verifica se é decimal ou milhar
                    parts = val_str.split(',')
                    if len(parts) > 1 and len(parts[-1]) == 2:
                        # Assume que é decimal (formato brasileiro)
                        val_str = val_str.replace(',', '.')
                    else:
                        # Assume que é milhar (formato europeu)
                        val_str = val_str.replace(',', '')
                
                try:
                    return float(val_str)
                except ValueError:
                    return 0.0
            
            df["Valor"] = df["Valor"].apply(parse_value)
            
        return df
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        return pd.DataFrame()

# Validação dos campos
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

# Interface Streamlit
st.title("📊 Controle de Despesas")

# Abas para organização
tab1, tab2, tab3 = st.tabs(["Registrar Despesa", "Visualizar Dados", "Relatórios"])

with tab1:
    st.subheader("Nova Despesa")
    with st.form("registro_despesa"):
        data = st.date_input("Data", datetime.today(), max_value=date.today())
        tipo = st.text_input("Tipo*", "")
        valor = st.text_input("Valor (ex: 26,28 ou 26.28)*", "")
        submitted = st.form_submit_button("Registrar")
        
        if submitted:
            errors = validate_inputs(data, tipo, valor)
            if errors:
                for error in errors:
                    st.error(error)
            else:
                try:
                    # Formata valor para salvar no padrão brasileiro
                    valor_formatado = valor.replace('.', '').replace(',', '.')
                    # Salva na planilha no formato YYYY-MM-DD
                    sheet.append_row([data.strftime("%Y-%m-%d"), tipo.strip(), valor_formatado])
                    st.success("✅ Despesa registrada com sucesso!")
                    # Limpa cache para recarregar dados
                    load_data.clear()
                except Exception as e:
                    st.error(f"❌ Erro ao registrar: {e}")

with tab2:
    st.subheader("📅 Despesas Registradas")
    df = load_data()
    
    if not df.empty:
        # Filtros
        col1, col2 = st.columns(2)
        with col1:
            tipos = df["Tipo"].unique()
            tipo_filtro = st.multiselect("Filtrar por Tipo", options=tipos)
        with col2:
            datas = df["Data"].unique()
            data_filtro = st.multiselect("Filtrar por Data", options=datas)
        
        # Aplicar filtros
        df_filtrado = df
        if tipo_filtro:
            df_filtrado = df_filtrado[df_filtrado["Tipo"].isin(tipo_filtro)]
        if data_filtro:
            df_filtrado = df_filtrado[df_filtrado["Data"].isin(data_filtro)]
        
        # Exibir dados
        st.dataframe(df_filtrado, use_container_width=True)
        
        # Estatísticas
        total = df_filtrado["Valor"].sum()
        media = df_filtrado["Valor"].mean()
        st.metric("Total Gasto", f"R$ {total:,.2f}".replace(',', '_').replace('.', ',').replace('_', '.'))
        st.metric("Média por Despesa", f"R$ {media:,.2f}".replace(',', '_').replace('.', ',').replace('_', '.'))
    else:
        st.info("Nenhuma despesa registrada ainda.")

with tab3:
    st.subheader("📈 Análise de Despesas")
    df = load_data()
    
    if not df.empty:
        # Converter Data para datetime para agrupamento
        df_plot = df.copy()
        df_plot["Data"] = pd.to_datetime(df_plot["Data"], format="%d/%m/%Y")
        
        # Gráfico de barras por data
        fig = px.bar(df_plot, x="Data", y="Valor", color="Tipo", 
                    title="Despesas por Data", labels={"Valor": "Valor (R$)"})
        st.plotly_chart(fig, use_container_width=True)
        
        # Gráfico de pizza por tipo
        st.subheader("Distribuição por Tipo")
        por_tipo = df_plot.groupby("Tipo")["Valor"].sum().reset_index()
        fig2 = px.pie(por_tipo, values="Valor", names="Tipo", title="Percentual por Tipo de Despesa")
        st.plotly_chart(fig2, use_container_width=True)
        
        # Tendência temporal
        st.subheader("Evolução Temporal")
        df_tendencia = df_plot.set_index("Data").resample('D').sum().reset_index()
        fig3 = px.line(df_tendencia, x="Data", y="Valor", title="Evolução das Despesas ao Longo do Tempo")
        st.plotly_chart(fig3, use_container_width=True)
    else:
        st.info("Nenhuma despesa registrada para exibir relatórios.")
