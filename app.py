import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# --- CONFIGURAÇÕES DE CONEXÃO ---
def conectar_sheets():
    scope = ["https://spreadsheets.google.com/feeds", 'https://www.googleapis.com/auth/spreadsheets',
             "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name('credenciais.json', scope)
    client = gspread.authorize(creds)
    return client.open("Estoque")

# --- FUNÇÕES DE DADOS (GOOGLE SHEETS) ---
def carregar_estoque():
    sh = conectar_sheets()
    sheet = sh.worksheet("Estoque")
    data = sheet.get_all_records()
    return pd.DataFrame(data)

def salvar_estoque(df):
    sh = conectar_sheets()
    sheet = sh.worksheet("Estoque")
    sheet.clear()
    sheet.update([df.columns.values.tolist()] + df.values.tolist())

def carregar_historico():
    sh = conectar_sheets()
    sheet = sh.worksheet("Histórico")
    data = sheet.get_all_records()
    return pd.DataFrame(data)

def salvar_no_historico(cliente, codigo, descricao, qtd, total_venda):
    sh = conectar_sheets()
    sheet = sh.worksheet("Histórico")
    data_hora = datetime.now().strftime("%d/%m/%Y %H:%M")
    sheet.append_row([data_hora, cliente, codigo, descricao, qtd, total_venda])

def verificar_senha():
    # O Streamlit busca a chave 'SENHA_DO_SISTEMA' do arquivo secrets.toml
    # Se ela não existir, ele retorna None para evitar quebrar o app
    senha_correta = st.secrets.get("SENHA_DO_SISTEMA")
    
    if st.session_state.get("senha_digitada") == senha_correta:
        st.session_state["autenticado"] = True
        st.session_state["senha_digitada"] = "" 
    else:
        st.error("Senha incorreta!")

if not st.session_state["autenticado"]:
    st.title("🔒 Acesso Restrito")
    st.text_input("Digite a senha:", type="password", key="senha_digitada")
    st.button("Entrar", on_click=verificar_senha)
    st.stop()

# Carrega os dados para a sessão atual
df_estoque = carregar_estoque()

# --- INTERFACE PRINCIPAL ---
st.title("📦 Sistema de Estoque GPS - Versão Web")
st.markdown(f"*Lembrete:* Peças destacadas em vermelho estão com estoque de *{LIMITE_ESTOQUE} un. ou menos*.")

# --- MENU LATERAL (AÇÕES RÁPIDAS) ---
st.sidebar.header("🛠️ Ações do Sistema")
acao = st.sidebar.radio("Escolha uma operação:", ["Entrada / Novo", "Registrar Venda", "Simular Orçamento"])

if acao == "Entrada / Novo":
    st.sidebar.subheader("➕ Entrada de Estoque")
    with st.sidebar.form("form_entrada"):
        st.caption("Se a peça já existe, preencha apenas CÓDIGO e QUANTIDADE.")
        codigo = st.text_input("Código da Peça")
        qtd = st.number_input("Quantidade (chegou/inicial)", min_value=1, step=1)
        
        st.markdown("---")
        st.caption("PARA PEÇAS NOVAS:")
        desc = st.text_input("Descrição (Nome)")
        preco = st.number_input("Preço de Venda Unitário (Ex: 150.50)", min_value=0.0, step=0.1)
        
        submit = st.form_submit_button("Confirmar Entrada")
        
        if submit:
            if not codigo:
                st.sidebar.error("Código é obrigatório!")
            else:
                if codigo in df_estoque['Codigo'].values:
                    df_estoque.loc[df_estoque['Codigo'] == codigo, 'Quantidade'] += qtd
                    salvar_estoque(df_estoque)
                    st.sidebar.success("Estoque atualizado com sucesso!")
                    st.rerun() # Atualiza a página
                else:
                    if not desc or preco <= 0:
                        st.sidebar.error("Para peças novas, preencha a Descrição e o Preço!")
                    else:
                        nova_linha = pd.DataFrame({'Codigo': [codigo], 'Descricao': [desc], 'Quantidade': [qtd], 'Preco': [preco]})
                        df_estoque = pd.concat([df_estoque, nova_linha], ignore_index=True)
                        salvar_estoque(df_estoque)
                        st.sidebar.success("Nova peça cadastrada!")
                        st.rerun()

elif acao == "Registrar Venda":
    st.sidebar.subheader("💲 Registrar Venda")
    with st.sidebar.form("form_venda"):
        codigo = st.text_input("Código da Peça")
        qtd = st.number_input("Quantidade Vendida", min_value=1, step=1)
        cliente = st.text_input("Nome do Cliente / Empresa", value="Não Informado")
        
        submit = st.form_submit_button("Confirmar Venda")
        
        if submit:
            if codigo not in df_estoque['Codigo'].values:
                st.sidebar.error("Código não encontrado no estoque!")
            else:
                estoque_atual = int(df_estoque.loc[df_estoque['Codigo'] == codigo, 'Quantidade'].iloc[0])
                if qtd > estoque_atual:
                    st.sidebar.error(f"Estoque insuficiente! Você tem apenas {estoque_atual} un.")
                else:
                    preco = float(df_estoque.loc[df_estoque['Codigo'] == codigo, 'Preco'].iloc[0])
                    descricao = df_estoque.loc[df_estoque['Codigo'] == codigo, 'Descricao'].iloc[0]
                    total_venda = qtd * preco
                    
                    df_estoque.loc[df_estoque['Codigo'] == codigo, 'Quantidade'] -= qtd
                    salvar_estoque(df_estoque)
                    salvar_no_historico(cliente, codigo, descricao, qtd, total_venda)
                    
                    st.sidebar.success(f"Venda Registrada!\n\nCliente: {cliente}\nPeça: {descricao}\nTotal: R$ {total_venda:.2f}")
                    st.rerun()

elif acao == "Simular Orçamento":
    st.sidebar.subheader("📝 Simular Orçamento")
    with st.sidebar.form("form_simulador"):
        codigo = st.text_input("Código da Peça")
        qtd = st.number_input("Quantidade simulada", min_value=1, step=1)
        
        submit = st.form_submit_button("Calcular Orçamento")
        
        if submit:
            if codigo in df_estoque['Codigo'].values:
                preco = float(df_estoque.loc[df_estoque['Codigo'] == codigo, 'Preco'].iloc[0])
                descricao = df_estoque.loc[df_estoque['Codigo'] == codigo, 'Descricao'].iloc[0]
                total = qtd * preco
                st.sidebar.info(f"*Peça:* {descricao}\n\n*Quantidade:* {qtd}\n\n*VALOR TOTAL:* R$ {total:.2f}")
            else:
                st.sidebar.error("Código não encontrado!")

# --- ABAS PRINCIPAIS (TELA CENTRAL) ---
aba1, aba2 = st.tabs(["📦 Meu Estoque", "📜 Histórico de Vendas"])

with aba1:
    # Barra de busca
    termo_busca = st.text_input("🔍 Buscar Peça (digite o código ou parte do nome)")
    
    df_exibicao = df_estoque.copy()
    
    # Filtro da busca
    if termo_busca:
        termo = termo_busca.lower()
        mask_cod = df_exibicao['Codigo'].astype(str).str.lower().str.contains(termo)
        mask_desc = df_exibicao['Descricao'].astype(str).str.lower().str.contains(termo)
        df_exibicao = df_exibicao[mask_cod | mask_desc]

    # Formatação de Moeda
    df_exibicao['Preço Unit.'] = df_exibicao['Preco'].apply(lambda x: f"R$ {float(x):.2f}")
    df_exibicao['Total Acumulado'] = (df_exibicao['Preco'] * df_exibicao['Quantidade']).apply(lambda x: f"R$ {float(x):.2f}")

    # Função para colorir linhas com estoque baixo
    def destacar_estoque_baixo(row):
        cor = '#ffcccc' if row['Quantidade'] <= LIMITE_ESTOQUE else ''
        return [f'background-color: {cor}' if cor else '' for _ in row]

    # Exibe a tabela interativa
    st.dataframe(
        df_exibicao[['Codigo', 'Descricao', 'Quantidade', 'Preço Unit.', 'Total Acumulado']].style.apply(destacar_estoque_baixo, axis=1),
        use_container_width=True,
        hide_index=True
    )

with aba2:
    df_hist = carregar_historico()
    if not df_hist.empty:
        df_hist['Total Venda'] = df_hist['Total Venda'].apply(lambda x: f"R$ {float(x):.2f}")
        st.dataframe(df_hist, use_container_width=True, hide_index=True)
    else:
        st.info("O histórico de vendas está vazio.")
