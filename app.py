import streamlit as st
import pandas as pd
import os
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAÇÕES ---
LIMITE_ESTOQUE = 5000

# Configuração da página da web
st.set_page_config(page_title="Sistema de Estoque GPS", layout="wide")

# --- CONEXÃO COM GOOGLE SHEETS ---
conn = st.connection("gsheets", type=GSheetsConnection)

def carregar_dados(aba):
    # Mudança: Vamos dizer ao código exatamente qual é o link aqui dentro também
    url = "https://docs.google.com/spreadsheets/d/1GixbU30cjCRFZ8FN-LOFWJfzxNgX-Ae3YH5cx2lQEZk/edit?pli=1&gid=47618822#gid=47618822"
    return conn.read(spreadsheet=url, worksheet=aba, ttl=0)

def salvar_dados(df, aba):
    # Atualiza a planilha no Google Sheets
    conn.update(worksheet=aba, data=df)
    st.cache_data.clear() # Limpa o cache para o Streamlit mostrar o dado novo imediatamente

# --- LÓGICA DE SENHA ---
if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False

def verificar_senha():
    senha_correta = "NOVAloja1!"
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

# --- CARREGAMENTO INICIAL DOS DADOS DA NUVEM ---
df_estoque = pd.DataFrame(columns=['Codigo', 'Descricao', 'Quantidade', 'Preco']) # Cria um vazio por segurança

try:
    df_estoque = carregar_dados("estoque_gps")
    # Garante que as colunas tenham o formato correto
    df_estoque['Codigo'] = df_estoque['Codigo'].astype(str)
    df_estoque['Quantidade'] = pd.to_numeric(df_estoque['Quantidade']).fillna(0).astype(int)
    df_estoque['Preco'] = pd.to_numeric(df_estoque['Preco']).fillna(0.0)
except Exception as e:
    st.error(f"Atenção: Não foi possível conectar ao Google Sheets. Verifique o arquivo secrets.toml e os nomes das abas. Erro: {e}")
    # O código vai continuar, mas com a tabela vazia até conectar

# --- INTERFACE PRINCIPAL ---
st.title("📦 Sistema de Estoque GPS - Google Sheets")
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
                    salvar_dados(df_estoque, "estoque_gps")
                    st.sidebar.success("Estoque atualizado com sucesso no Google Sheets!")
                    st.rerun()
                else:
                    if not desc or preco <= 0:
                        st.sidebar.error("Para peças novas, preencha a Descrição e o Preço!")
                    else:
                        nova_linha = pd.DataFrame({'Codigo': [codigo], 'Descricao': [desc], 'Quantidade': [qtd], 'Preco': [preco]})
                        df_estoque = pd.concat([df_estoque, nova_linha], ignore_index=True)
                        salvar_dados(df_estoque, "estoque_gps")
                        st.sidebar.success("Nova peça cadastrada no Google Sheets!")
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
                    preco_unit = float(df_estoque.loc[df_estoque['Codigo'] == codigo, 'Preco'].iloc[0])
                    descricao = df_estoque.loc[df_estoque['Codigo'] == codigo, 'Descricao'].iloc[0]
                    total_venda = qtd * preco_unit
                    
                    # 1. Desconta do estoque e atualiza a aba do estoque
                    df_estoque.loc[df_estoque['Codigo'] == codigo, 'Quantidade'] -= qtd
                    salvar_dados(df_estoque, "estoque_gps")
                    
                    # 2. Puxa o histórico atual da nuvem, adiciona a nova linha e salva de volta
                    try:
                        df_hist = carregar_dados("historico_vendas")
                        novo_registro = pd.DataFrame({
                            'Data': [datetime.now().strftime("%d/%m/%Y %H:%M")], 
                            'Cliente': [cliente], 
                            'Codigo': [codigo], 
                            'Descricao': [descricao], 
                            'Qtd Vendida': [qtd], 
                            'Total Venda': [total_venda]
                        })
                        df_hist = pd.concat([df_hist, novo_registro], ignore_index=True)
                        salvar_dados(df_hist, "historico_vendas")
                        
                        st.sidebar.success(f"Venda salva na nuvem!\n\nCliente: {cliente}\nPeça: {descricao}\nTotal: R$ {total_venda:.2f}")
                        st.rerun()
                    except:
                        st.sidebar.error("Erro ao salvar no histórico. Verifique a aba 'historico_vendas'.")

elif acao == "Simular Orçamento":
    st.sidebar.subheader("📝 Simular Orçamento")
    with st.sidebar.form("form_simulador"):
        codigo = st.text_input("Código da Peça")
        qtd = st.number_input("Quantidade simulada", min_value=1, step=1)
        
        submit = st.form_submit_button("Calcular Orçamento")
        
        if submit:
            if codigo in df_estoque['Codigo'].values:
                preco_unit = float(df_estoque.loc[df_estoque['Codigo'] == codigo, 'Preco'].iloc[0])
                descricao = df_estoque.loc[df_estoque['Codigo'] == codigo, 'Descricao'].iloc[0]
                total = qtd * preco_unit
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

    # Cria colunas calculadas bonitas apenas para exibição visual na tela
    df_exibicao['Preço Unit.'] = df_exibicao['Preco'].apply(lambda x: f"R$ {float(x):.2f}")
    df_exibicao['Total Acumulado'] = (df_exibicao['Preco'] * df_exibicao['Quantidade']).apply(lambda x: f"R$ {float(x):.2f}")

    # Função para colorir linhas com estoque baixo
    def destacar_estoque_baixo(row):
        cor = '#ffcccc' if int(row['Quantidade']) <= LIMITE_ESTOQUE else ''
        return [f'background-color: {cor}' if cor else '' for _ in row]

    # Exibe a tabela do estoque
    st.dataframe(
        df_exibicao[['Codigo', 'Descricao', 'Quantidade', 'Preço Unit.', 'Total Acumulado']].style.apply(destacar_estoque_baixo, axis=1),
        use_container_width=True,
        hide_index=True
    )

with aba2:
    try:
        df_hist = carregar_dados("historico_vendas")
        if not df_hist.empty:
            # Formata a coluna de preço se ela tiver dados numéricos
            df_hist_exibicao = df_hist.copy()
            df_hist_exibicao['Total Venda'] = pd.to_numeric(df_hist_exibicao['Total Venda']).apply(lambda x: f"R$ {float(x):.2f}")
            st.dataframe(df_hist_exibicao, use_container_width=True, hide_index=True)
        else:
            st.info("O histórico de vendas na nuvem está vazio.")
    except:
        st.info("Não foi possível carregar o histórico ou a aba 'historico_vendas' está vazia.")
