import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAÇÕES ---
LIMITE_ESTOQUE = 5000

st.set_page_config(page_title="Sistema de Estoque GPS", layout="wide")

# Conexão oficial (lendo do secrets.toml)
conn = st.connection("gsheets", type=GSheetsConnection)

# --- AJUSTE NAS FUNÇÕES DE CONEXÃO ---

# COPIE O LINK DA SUA PLANILHA E COLE ENTRE AS ASPAS ABAIXO
URL_DA_PLANILHA = "https://docs.google.com/spreadsheets/d/1GixbU30cjCRFZ8FN-LOFWJfzxNgX-Ae3YH5cx2lQEZk/"

def carregar_dados(aba):
    # Passamos a URL diretamente aqui para não dar erro de "required"
    return conn.read(spreadsheet=URL_DA_PLANILHA, worksheet=aba, ttl=0)

def salvar_dados(df, aba):
    # Passamos a URL aqui também
    conn.update(spreadsheet=URL_DA_PLANILHA, worksheet=aba, data=df)
    st.cache_data.clear()
# --- LÓGICA DE ACESSO ---
if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False

if not st.session_state["autenticado"]:
    st.title("🔒 Sistema GPS - Acesso Restrito")
    senha = st.text_input("Digite a senha do sistema:", type="password")
    if st.button("Entrar"):
        if senha == "NOVAloja1!":
            st.session_state["autenticado"] = True
            st.rerun()
        else:
            st.error("Senha incorreta!")
    st.stop()

# --- CARREGAMENTO DE DADOS ---
try:
    df_estoque = carregar_dados("estoque_gps")
    # Limpeza básica de dados
    df_estoque['Codigo'] = df_estoque['Codigo'].astype(str)
    df_estoque['Quantidade'] = pd.to_numeric(df_estoque['Quantidade']).fillna(0).astype(int)
    df_estoque['Preco'] = pd.to_numeric(df_estoque['Preco']).fillna(0.0)
except Exception as e:
    st.error("🚨 ERRO DETALHADO:")
    st.write(e) # Isso vai imprimir na tela o motivo real (ex: aba não encontrada)
    st.stop()

# --- INTERFACE PRINCIPAL ---
st.title("📦 Sistema de Estoque GPS")
st.sidebar.header("🛠️ Menu")
acao = st.sidebar.radio("Escolha:", ["Estoque", "Entrada", "Venda", "Orçamento"])

if acao == "Estoque":
    st.subheader("📋 Estoque na Nuvem")
    termo = st.text_input("🔍 Buscar peça").lower()
    df_ver = df_estoque.copy()
    if termo:
        mask = df_ver['Codigo'].str.lower().str.contains(termo) | df_ver['Descricao'].str.lower().str.contains(termo)
        df_ver = df_ver[mask]
    
    df_ver['Preço Unit.'] = df_ver['Preco'].apply(lambda x: f"R$ {x:.2f}")
    st.dataframe(df_ver[['Codigo', 'Descricao', 'Quantidade', 'Preço Unit.']], use_container_width=True, hide_index=True)

elif acao == "Entrada":
    with st.form("f_entrada"):
        c1, c2 = st.columns(2)
        cod = c1.text_input("Código")
        qtd = c1.number_input("Qtd", min_value=1)
        desc = c2.text_input("Descrição (Nova)")
        prec = c2.number_input("Preço (Novo)", min_value=0.0)
        if st.form_submit_button("Confirmar"):
            if cod in df_estoque['Codigo'].values:
                df_estoque.loc[df_estoque['Codigo'] == cod, 'Quantidade'] += qtd
            else:
                nova = pd.DataFrame({'Codigo':[cod],'Descricao':[desc],'Quantidade':[qtd],'Preco':[prec]})
                df_estoque = pd.concat([df_estoque, nova], ignore_index=True)
            salvar_dados(df_estoque, "estoque_gps")
            st.success("Salvo com sucesso!")
            st.rerun()

elif acao == "Venda":
    with st.form("f_venda"):
        cod_v = st.text_input("Código")
        qtd_v = st.number_input("Qtd Vendida", min_value=1)
        cli = st.text_input("Cliente", value="Consumidor")
        if st.form_submit_button("Finalizar Venda"):
            if cod_v in df_estoque['Codigo'].values:
                idx = df_estoque[df_estoque['Codigo'] == cod_v].index[0]
                if df_estoque.at[idx, 'Quantidade'] >= qtd_v:
                    df_estoque.at[idx, 'Quantidade'] -= qtd_v
                    salvar_dados(df_estoque, "estoque_gps")
                    st.success("Venda realizada!")
                    st.rerun()
                else: st.error("Sem estoque!")
            else: st.error("Não encontrado!")

elif acao == "Orçamento":
    cod_o = st.text_input("Código para orçamento")
    if cod_o in df_estoque['Codigo'].values:
        p = df_estoque[df_estoque['Codigo'] == cod_o]['Preco'].values[0]
        st.info(f"Valor Unitário: R$ {p:.2f}")
