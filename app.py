import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from streamlit_pdf_viewer import pdf_viewer
import PyPDF2

st.set_page_config(page_title="Sistema de Estoque GPS", layout="wide", page_icon="📦")

# --- CONEXÃO GSPREAD ---
def get_gsheets_client():
    creds_dict = {
        "type": st.secrets["connections"]["gsheets"]["type"],
        "project_id": st.secrets["connections"]["gsheets"]["project_id"],
        "private_key_id": st.secrets["connections"]["gsheets"]["private_key_id"],
        "private_key": st.secrets["connections"]["gsheets"]["private_key"].replace('\\n', '\n'),
        "client_email": st.secrets["connections"]["gsheets"]["client_email"],
        "client_id": st.secrets["connections"]["gsheets"]["client_id"],
        "auth_uri": st.secrets["connections"]["gsheets"]["auth_uri"],
        "token_uri": st.secrets["connections"]["gsheets"]["token_uri"],
        "auth_provider_x509_cert_url": st.secrets["connections"]["gsheets"]["auth_provider_x509_cert_url"],
        "client_x509_cert_url": st.secrets["connections"]["gsheets"]["client_x509_cert_url"],
    }
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    return gspread.authorize(creds)

def carregar_dados(aba):
    client = get_gsheets_client()
    spreadsheet = client.open_by_url(st.secrets["connections"]["gsheets"]["spreadsheet"])
    worksheet = spreadsheet.worksheet(aba)
    return pd.DataFrame(worksheet.get_all_records())

def salvar_dados(df, aba):
    client = get_gsheets_client()
    spreadsheet = client.open_by_url(st.secrets["connections"]["gsheets"]["spreadsheet"])
    worksheet = spreadsheet.worksheet(aba)
    worksheet.clear()
    data = [df.columns.values.tolist()] + df.values.tolist()
    worksheet.update(data)
    st.cache_data.clear()

# --- INICIALIZAÇÃO ---
if "carrinho" not in st.session_state: st.session_state["carrinho"] = []
if "autenticado" not in st.session_state: st.session_state["autenticado"] = False

SENHA_SISTEMA = st.secrets["SENHA_SISTEMA"]

def processar_venda(itens, cliente, df_estoque, tipo="Venda"):
    for item in itens:
        idx = df_estoque[df_estoque['Codigo'] == item['Codigo']].index[0]
        df_estoque.at[idx, 'Quantidade'] -= item['Qtd']
    salvar_dados(df_estoque, "estoque_gps")
    
    df_novas = pd.DataFrame(itens).rename(columns={'Qtd': 'Quantidade', 'Preco': 'Valor Unitario', 'Desc %': 'Desconto %', 'Desc R$': 'Desconto R$'})
    agora = datetime.now()
    df_novas['ID_Venda'] = agora.strftime('%Y%m%d%H%M%S')
    df_novas['Data'] = agora.strftime('%d/%m/%Y')
    df_novas['Horario'] = agora.strftime('%H:%M:%S')
    df_novas['Cliente'] = cliente
    df_novas['Valor Total'] = df_novas['Quantidade'] * df_novas['Valor Unitario']
    
    try:
        df_hist = carregar_dados("historico_vendas")
    except:
        df_hist = pd.DataFrame()
    salvar_dados(pd.concat([df_hist, df_novas], ignore_index=True), "historico_vendas")
    
    st.session_state["carrinho"] = []
    st.success(f"✅ {tipo} concluída com sucesso!")
    st.rerun()

def atualizar_lista_compras(df_estoque):
    df_compras = df_estoque[df_estoque['Quantidade'] <= df_estoque['Alerta Minimo']].copy()
    df_compras = df_compras[['Codigo', 'Descricao', 'Quantidade', 'Alerta Minimo']]
    df_compras['Status'] = 'Aguardando'
    salvar_dados(df_compras, "Compras Necessárias")

# --- LÓGICA DE ACESSO ---
if not st.session_state["autenticado"]:
    st.title("🔒 Sistema GPS - Acesso Restrito")
    with st.form("login_form"):
        senha = st.text_input("Senha:", type="password")
        if st.form_submit_button("Entrar"):
            if senha == SENHA_SISTEMA:
                st.session_state["autenticado"] = True
                st.rerun()
            else:
                st.error("Senha incorreta!")
    st.stop()

# --- CARREGAMENTO ---
try:
    df_estoque = carregar_dados("estoque_gps")
    df_estoque['Codigo'] = df_estoque['Codigo'].astype(str).apply(lambda x: x[:-2] if x.endswith('.0') else x)
    df_estoque['Quantidade'] = pd.to_numeric(df_estoque['Quantidade'], errors='coerce').fillna(0).astype(int)
    df_estoque['Preco'] = pd.to_numeric(df_estoque['Preco'], errors='coerce').fillna(0.0)
    df_estoque['Alerta Minimo'] = pd.to_numeric(df_estoque['Alerta Minimo'], errors='coerce').fillna(5).astype(int)
except:
    st.error("Erro ao carregar dados.")
    st.stop()

# --- MENU E ABAS ---
st.title("📦 Sistema de Estoque GPS")
acao = st.sidebar.radio("Navegação:", ["Entrada", "Estoque", "Catálogo", "Venda", "Orçamento", "Trocas", "Pedidos", "Compras", "Histórico de Vendas", "Histórico de Trocas", "Dashboard"])

if acao == "Estoque":
    st.subheader("📋 Estoque")
    termo = st.text_input("🔍 Buscar").lower()
    df_ver = df_estoque[df_estoque['Codigo'].str.lower().str.contains(termo) | df_estoque['Descricao'].str.lower().str.contains(termo)] if termo else df_estoque
    df_editado = st.data_editor(df_ver, use_container_width=True)
    if st.button("💾 Salvar"):
        df_estoque.set_index('Codigo', inplace=True)
        df_editado.set_index('Codigo', inplace=True)
        df_estoque.update(df_editado[['Preco', 'Alerta Minimo', 'Anotacoes']])
        df_estoque.reset_index(inplace=True)
        salvar_dados(df_estoque, "estoque_gps")
        st.rerun()

elif acao == "Entrada":
    with st.form("f_entrada"):
        cod = st.text_input("Código").strip()
        qtd = st.number_input("Qtd", value=0)
        desc = st.text_input("Desc").strip()
        prec = st.number_input("Preço", value=0.0)
        if st.form_submit_button("Confirmar"):
            if cod in df_estoque['Codigo'].values:
                idx = df_estoque[df_estoque['Codigo'] == cod].index[0]
                df_estoque.at[idx, 'Quantidade'] += qtd
            else:
                nova = pd.DataFrame({'Codigo': [cod], 'Descricao': [desc], 'Quantidade': [qtd], 'Preco': [prec], 'Alerta Minimo': [5], 'Anotacoes': [""]})
                df_estoque = pd.concat([df_estoque, nova], ignore_index=True)
            salvar_dados(df_estoque, "estoque_gps")
            st.rerun()

 elif acao == "Catálogo":
    arquivo = "catalogo_oficial.pdf"

    # 1. Função que lê o PDF e cria um índice de texto (Roda só uma vez)
    @st.cache_data
    def criar_indice_pdf(caminho):
        indice = {}
        with open(caminho, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for i, p in enumerate(reader.pages):
                texto = p.extract_text()
                if texto:
                    indice[i + 1] = texto.upper()
        return indice

    # 2. Carrega o índice na memória
    with st.spinner("Otimizando catálogo..."):
        indice_paginas = criar_indice_pdf(arquivo)

    # 3. Interface de Busca
    termo = st.sidebar.text_input("🔍 Buscar código:").strip().upper()
    btn_buscar = st.sidebar.button("Buscar no Catálogo")
    
    pag = None
    
    # 4. Busca rápida no índice (não precisa ler o PDF de novo!)
    if btn_buscar and termo:
        encontrado = False
        for num_pag, texto_pag in indice_paginas.items():
            if termo in texto_pag:
                pag = num_pag
                encontrado = True
                break
        
        if not encontrado:
            st.warning("Código não encontrado.")
        else:
            st.success(f"Código encontrado na página {pag}!")

    # 5. Exibe o PDF
    pdf_viewer(arquivo, scroll_to_page=pag if pag else 1)


elif acao == "Venda":
    cod_v = st.text_input("Código:").strip()
    if cod_v in df_estoque['Codigo'].values:
        idx = df_estoque[df_estoque['Codigo'] == cod_v].index[0]
        qtd_s = st.number_input("Qtd", min_value=1, max_value=int(df_estoque.at[idx, 'Quantidade']), value=1)
        if st.button("Adicionar"):
            st.session_state["carrinho"].append({"Codigo": cod_v, "Descricao": df_estoque.at[idx, 'Descricao'], "Qtd": qtd_s, "Preco": df_estoque.at[idx, 'Preco'], "Desc %": 0, "Desc R$": 0})
            st.rerun()
    if st.session_state["carrinho"]:
        st.table(pd.DataFrame(st.session_state["carrinho"]))
        cli = st.text_input("Cliente:").strip()
        if st.button("✅ Finalizar Venda"):
            processar_venda(st.session_state["carrinho"], cli, df_estoque, tipo="Venda")

elif acao == "Orçamento":
    cod_o = st.text_input("Código:").strip()
    if cod_o in df_estoque['Codigo'].values:
        idx = df_estoque[df_estoque['Codigo'] == cod_o].index[0]
        qtd_o = st.number_input("Qtd", min_value=1, value=1)
        if st.button("Adicionar"):
            st.session_state["carrinho"].append({"Codigo": cod_o, "Descricao": df_estoque.at[idx, 'Descricao'], "Qtd": qtd_o, "Preco": df_estoque.at[idx, 'Preco'], "Desc %": 0, "Desc R$": 0})
            st.rerun()
    if st.session_state["carrinho"]:
        st.table(pd.DataFrame(st.session_state["carrinho"]))
        cli_o = st.text_input("Cliente:").strip()
        if st.button("🚀 Converter em Venda"):
            processar_venda(st.session_state["carrinho"], cli_o, df_estoque, tipo="Conversão")

elif acao == "Dashboard":
    st.subheader("📊 Dashboard")
    try:
        df_hist = carregar_dados("historico_vendas")
        df_hist['Data'] = pd.to_datetime(df_hist['Data'], dayfirst=True)
        c1, c2 = st.columns(2)
        with c1: st.bar_chart(df_hist.groupby('Descricao')['Quantidade'].sum().nlargest(5))
        with c2: 
            df_hist['Mes'] = df_hist['Data'].dt.strftime('%m/%Y')
            st.line_chart(df_hist.groupby('Mes')['Valor Total'].sum())
    except: st.error("Erro no Dashboard.")

elif acao == "Compras":
    st.subheader("🛒 Lista de Compras")
    if st.button("🔄 Atualizar"):
        atualizar_lista_compras(df_estoque)
        st.rerun()
    st.table(df_estoque[df_estoque['Quantidade'] <= df_estoque['Alerta Minimo']])
