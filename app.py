import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection
from streamlit_pdf_viewer import pdf_viewer
import PyPDF2

st.set_page_config(page_title="Sistema de Estoque GPS", layout="wide", page_icon="📦")

# --- INICIALIZAÇÃO ---
if "carrinho" not in st.session_state:
    st.session_state["carrinho"] = []
if "carrinho_pedidos" not in st.session_state:
    st.session_state["carrinho_pedidos"] = []
if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False

# --- CONFIGURAÇÕES SEGURAS ---
if "connections" not in st.secrets or "gsheets" not in st.secrets["connections"]:
    st.error("🚨 Erro: Arquivo secrets.toml mal configurado.")
    st.stop()

conn = st.connection("gsheets", type=GSheetsConnection)
SENHA_SISTEMA = st.secrets["SENHA_SISTEMA"]

# --- FUNÇÕES ---
def carregar_dados(aba):
    return conn.read(worksheet=aba, ttl=600)

def salvar_dados(df, aba):
    conn.update(worksheet=aba, data=df)
    st.cache_data.clear()

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

# --- CARREGAMENTO DE DADOS ---
try:
    df_estoque = carregar_dados("estoque_gps")
    if not df_estoque.empty:
        df_estoque['Codigo'] = df_estoque['Codigo'].astype(str).apply(lambda x: x[:-2] if x.endswith('.0') else x)
        df_estoque['Quantidade'] = pd.to_numeric(df_estoque['Quantidade'], errors='coerce').fillna(0).astype(int)
        df_estoque['Preco'] = pd.to_numeric(df_estoque['Preco'], errors='coerce').fillna(0.0)
        df_estoque['Alerta Minimo'] = pd.to_numeric(df_estoque['Alerta Minimo'], errors='coerce').fillna(5).astype(int)
        df_estoque['Anotacoes'] = df_estoque['Anotacoes'].fillna("").astype(str)
    else:
        df_estoque = pd.DataFrame(columns=['Codigo', 'Descricao', 'Quantidade', 'Preco', 'Alerta Minimo', 'Anotacoes'])
except Exception as e:
    st.error(f"Erro ao carregar: {e}")
    st.stop()

# --- MENU NAVEGAÇÃO ---
st.title("📦 Sistema de Estoque GPS")
acao = st.sidebar.radio("Navegação:", ["Entrada", "Estoque", "Catálogo", "Venda", "Orçamento", "Trocas", "Histórico de Vendas", "Histórico de Trocas", "Pedidos", "Dashboard", "Compras"])

# --- ABAS ---
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
    termo = st.text_input("Buscar código:").strip().upper()
    pag = None
    if termo:
        with open(arquivo, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for i, p in enumerate(reader.pages):
                if termo in p.extract_text().upper():
                    pag = i + 1
                    break
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
        if st.button("❌ Limpar"):
            st.session_state["carrinho"] = []
            st.rerun()

elif acao == "Dashboard":
    st.subheader("📊 Dashboard Gerencial")
    try:
        df_hist = carregar_dados("historico_vendas")
        if not df_hist.empty:
            df_hist['Data'] = pd.to_datetime(df_hist['Data'], dayfirst=True)
            c1, c2 = st.columns(2)
            with c1:
                st.write("### 🔝 Top 5 Itens")
                st.bar_chart(df_hist.groupby('Descricao')['Quantidade'].sum().nlargest(5))
            with c2:
                st.write("### 💰 Faturamento")
                df_hist['Mes'] = df_hist['Data'].dt.strftime('%m/%Y')
                st.line_chart(df_hist.groupby('Mes')['Valor Total'].sum())
    except:
        st.error("Erro ao carregar Dashboard.")

elif acao == "Compras":
    st.subheader("🛒 Lista de Compras Necessárias")
    if st.button("🔄 Atualizar Lista de Compras Agora"):
        atualizar_lista_compras(df_estoque)
        st.success("Lista sincronizada com a planilha!")
        st.rerun()
    
    df_nec = df_estoque[df_estoque['Quantidade'] <= df_estoque['Alerta Minimo']]
    if not df_nec.empty:
        st.warning(f"⚠️ {len(df_nec)} itens precisam de reposição!")
        st.table(df_nec[['Codigo', 'Descricao', 'Quantidade', 'Alerta Minimo']])
    else:
        st.success("✅ Tudo ok!")

elif acao == "Histórico de Vendas":
    st.dataframe(carregar_dados("historico_vendas"))

elif acao == "Pedidos":
    st.write("Aba de Pedidos ativa.")
