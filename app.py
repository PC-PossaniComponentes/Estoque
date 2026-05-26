import streamlit as st
import pandas as pd
from datetime import datetime
import plotly.express as px  # <--- ADICIONE ESTA LINHA AQUI

st.set_page_config(page_title="Sistema de Estoque GPS", layout="wide", page_icon="📦")

# --- CONEXÃO ---
conn = st.connection("gsheets", type=GSheetsConnection)
SENHA_SISTEMA = st.secrets["SENHA_SISTEMA"]

# --- FUNÇÕES OTIMIZADAS ---
def carregar_dados(aba):
    # O TTL define o tempo de cache. Se quiser garantir que sempre pegue o dado mais novo, 
    # você pode reduzir o TTL ou limpar o cache manualmente após salvar.
    return conn.read(worksheet=aba, ttl=60) 

def salvar_dados(df, aba):
    df = df.fillna("") 
    conn.update(worksheet=aba, data=df)
    # Limpa apenas a cache das funções de leitura, forçando a próxima leitura a buscar no Google Sheets
    st.cache_data.clear() 

def processar_venda(itens, cliente, tipo="Venda", envio="Retirada"):
    # 1. Recarrega o estoque AGORA para evitar conflitos de "estoque desatualizado"
    df_estoque_atual = carregar_dados("estoque_gps")
    df_estoque_atual['Quantidade'] = pd.to_numeric(df_estoque_atual['Quantidade'], errors='coerce').fillna(0).astype(int)
    
    # 2. Processa a lógica
    for item in itens:
        idx = df_estoque_atual[df_estoque_atual['Codigo'] == item['Codigo']].index
        if not idx.empty:
            if df_estoque_atual.at[idx[0], 'Quantidade'] < item['Qtd']:
                st.error(f"Estoque insuficiente para o código {item['Codigo']}!")
                st.stop()
                df_estoque_atual.at[idx[0], 'Quantidade'] -= item['Qtd']
    
    # 3. Salva o estoque
    salvar_dados(df_estoque_atual, "estoque_gps")
    
    # 4. Processa o Histórico
    df_novas = pd.DataFrame(itens)
    agora = datetime.now()
    df_novas['Data'] = agora.strftime('%d/%m/%Y')
    df_novas['Horario'] = agora.strftime('%H:%M:%S')
    df_novas['Cliente'] = cliente
    df_novas['Envio'] = envio
    
    df_hist = carregar_dados("historico_vendas")
    df_final = pd.concat([df_hist, df_novas], ignore_index=True)
    salvar_dados(df_final, "historico_vendas")
    
    st.session_state["carrinho"] = []
    st.success(f"✅ {tipo} concluída com sucesso!")
    st.rerun()
# --- INICIALIZAÇÃO ---
if "carrinho" not in st.session_state: st.session_state["carrinho"] = []
if "autenticado" not in st.session_state: st.session_state["autenticado"] = False

# --- AUTENTICAÇÃO ---
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
    # FORÇAR CÓDIGO COMO TEXTO E REMOVER O .0 SE JÁ EXISTIR
    df_estoque['Codigo'] = df_estoque['Codigo'].astype(str).str.replace('.0', '', regex=False)
    
    df_estoque['Quantidade'] = pd.to_numeric(df_estoque['Quantidade'], errors='coerce').fillna(0).astype(int)
    df_estoque['Preco'] = pd.to_numeric(df_estoque['Preco'], errors='coerce').fillna(0.0)
except:
    df_estoque = pd.DataFrame(columns=['Codigo', 'Descricao', 'Quantidade', 'Preco', 'Alerta Minimo', 'Anotacoes'])
# --- MENU E ABAS ---
st.title("📦 Sistema de Estoque GPS")
abas = ["Estoque", "Entrada", "Catálogo", "Venda", "Orçamento", "Trocas", "Pedidos", "Histórico de Vendas", "Histórico de Trocas", "Dashboard", "Compras"]
acao = st.sidebar.radio("Navegação:", abas)

# --- LÓGICA DAS ABAS ---
# --- LÓGICA DA ABA ESTOQUE ---
# --- LÓGICA DA ABA ESTOQUE ---
if acao == "Estoque":
    st.subheader("📋 Estoque")
    
    # Fazemos uma cópia para não alterar o df original enquanto editamos
    df_exibicao = df_estoque.copy()
    
    # --- CORREÇÃO OBRIGATÓRIA DE TIPOS ---
    # Forçamos a coluna Anotacoes para texto para evitar conflito com o tipo FLOAT
    df_exibicao['Anotacoes'] = df_exibicao['Anotacoes'].astype(str).replace('nan', '')
    df_exibicao['Codigo'] = df_exibicao['Codigo'].astype(str)
    # -------------------------------------
    
    # Cálculo do total (apenas visual)
    df_exibicao['Total em Estoque'] = df_exibicao['Quantidade'] * df_exibicao['Preco']

    # Configuração das colunas
    col_config = {
        "Codigo": st.column_config.TextColumn("Código", disabled=True),
        "Descricao": st.column_config.TextColumn("Descrição", disabled=True),
        "Quantidade": st.column_config.NumberColumn("Quantidade", disabled=True),
        "Total em Estoque": st.column_config.NumberColumn("Valor Total", format="R$ %.2f", disabled=True),
        "Preco": st.column_config.NumberColumn("Preço", format="R$ %.2f", disabled=False),
        "Alerta Minimo": st.column_config.NumberColumn("Alerta Mínimo", disabled=False),
        "Anotacoes": st.column_config.TextColumn("Anotações", disabled=False)
    }

    # Renderiza o editor
    df_editado = st.data_editor(
        df_exibicao, 
        column_config=col_config, 
        use_container_width=True,
        hide_index=False, # Precisa ser False para selecionar linhas
        num_rows="fixed"  # Apenas edição, sem adicionar novas linhas
    )

    if st.button("💾 Salvar Alterações"):
        # Removemos a coluna calculada antes de salvar
        df_salvar = df_editado.drop(columns=['Total em Estoque'])
        
        # Garantir que os tipos estão corretos para o Sheets
        df_salvar['Quantidade'] = df_salvar['Quantidade'].astype(int)
        df_salvar['Alerta Minimo'] = df_salvar['Alerta Minimo'].astype(int)
        df_salvar['Preco'] = df_salvar['Preco'].astype(float)
        
        salvar_dados(df_salvar, "estoque_gps")
        st.success("Estoque salvo com sucesso!")
        st.rerun()

    st.write("---")
    
    
    # 3. Área exclusiva para Exclusão (Muito mais segura)
    with st.expander("🗑️ Excluir peça do estoque"):
        cod_para_excluir = st.selectbox("Selecione o código da peça para excluir:", options=df_estoque['Codigo'].unique())
        if st.button("⚠️ Confirmar Exclusão Definitiva"):
            df_atualizado = df_estoque[df_estoque['Codigo'] != cod_para_excluir]
            salvar_dados(df_atualizado, "estoque_gps")
            st.warning(f"Peça {cod_para_excluir} excluída com sucesso!")
            st.rerun()
elif acao == "Entrada":
    st.subheader("📥 Entrada de Mercadoria")
    with st.form("f_entrada", clear_on_submit=True):
        cod = st.text_input("Código").strip().upper()
        # Novo campo para a descrição
        desc = st.text_input("Descrição (Opcional se o item já existir)") 
        qtd = st.number_input("Qtd", min_value=1, value=1)
        prec = st.number_input("Preço", min_value=0.0, format="%.2f")
        
        if st.form_submit_button("Confirmar Entrada"):
            if not cod:
                st.error("O código é obrigatório!")
                st.stop()
                
            idx = df_estoque[df_estoque['Codigo'] == cod].index
            
            if not idx.empty:
                # ITEM EXISTENTE: Atualiza a quantidade e o preço
                df_estoque.at[idx[0], 'Quantidade'] += qtd
                df_estoque.at[idx[0], 'Preco'] = prec
                
                # Atualiza a descrição apenas se o usuário preencheu algo novo
                if desc:
                    df_estoque.at[idx[0], 'Descricao'] = desc
            
            else:
                # NOVO ITEM: Forçamos o Codigo a ser string explicitamente
                final_desc = desc if desc else "Nova Peça"
                nova = pd.DataFrame({
                    'Codigo': [str(cod)], # <--- AQUI: O código é forçado a string
                    'Descricao': [final_desc], 
                    'Quantidade': [qtd], 
                    'Preco': [prec], 
                    'Alerta Minimo': [5], 
                    'Anotacoes': [""]
                })
                
                # Garantimos que a coluna Codigo seja string para evitar conflitos na concatenação
                df_estoque['Codigo'] = df_estoque['Codigo'].astype(str)
                df_estoque = pd.concat([df_estoque, nova], ignore_index=True)
            
            salvar_dados(df_estoque, "estoque_gps")
            st.success(f"Entrada de {cod} registrada com sucesso!")
            st.rerun()

elif acao == "Catálogo":
    st.subheader("📖 Catálogo")
    st.link_button("🔗 Abrir PDF", "https://drive.google.com/file/d/1yf2NTjeVkVESKjPt_seKPc0Vga8n9ALS/view")

elif acao == "Venda" or acao == "Orçamento":
    st.subheader(f"🛒 {acao}")
    cod_v = st.text_input("Código:").strip().upper()
    if cod_v in df_estoque['Codigo'].values:
        idx = df_estoque[df_estoque['Codigo'] == cod_v].index[0]
        c1, c2, c3 = st.columns(3)
        with c1: qtd = st.number_input("Qtd", min_value=1, value=1)
        with c2: val = st.number_input("Preço", value=float(df_estoque.at[idx, 'Preco']))
        with c3: desc = st.number_input("Desc (%)", value=0.0)
        if st.button("Adicionar"):
            st.session_state["carrinho"].append({"Codigo": cod_v, "Qtd": qtd, "Preco Unitario": val, "Total R$": (qtd * val) * (1 - desc/100)})
            st.rerun()
    if st.session_state["carrinho"]:
        st.table(pd.DataFrame(st.session_state["carrinho"]))
        cli = st.text_input("Cliente")
        if st.button("Finalizar"):
            processar_venda(st.session_state["carrinho"], cli, df_estoque, tipo=acao)

elif acao == "Trocas":
    st.subheader("🔄 Trocas")
    with st.form("f_troca"):
        cli = st.text_input("Cliente")
        c1, c2 = st.columns(2)
        with c1: cod_d = st.text_input("Cod Defeito"); qtd_d = st.number_input("Qtd Defeito", value=1)
        with c2: cod_n = st.text_input("Cod Nova"); qtd_n = st.number_input("Qtd Nova", value=1)
        if st.form_submit_button("Registrar"):
            # Salvar no histórico de trocas aqui
            st.success("Troca registrada!")

elif acao == "Pedidos":
    st.subheader("📦 Pedidos")
    cli_p = st.text_input("Cliente")
    cod_p = st.text_input("Código")
    if st.button("Registrar"):
        # Lógica de pedido
        st.success("Pedido registrado!")

elif acao == "Histórico de Vendas":
    st.dataframe(carregar_dados("historico_vendas"))

elif acao == "Histórico de Trocas":
    st.dataframe(carregar_dados("historico_trocas"))

elif acao == "Dashboard":
    st.subheader("📊 Dashboard de Vendas")
    df_hist = carregar_dados("historico_vendas")
    
    # Criando o gráfico com Plotly
    # .reset_index() é importante para o Plotly entender as colunas
    df_agrupado = df_hist.groupby('Codigo')['Quantidade'].sum().reset_index()
    
    fig = px.bar(
        df_agrupado, 
        x='Codigo', 
        y='Quantidade', 
        title="Vendas por Código",
        labels={'Codigo': 'Código do Produto', 'Quantidade': 'Total Vendido'}
    )
    
    st.plotly_chart(fig, use_container_width=True)

elif acao == "Compras":
    st.table(df_estoque[df_estoque['Quantidade'] <= df_estoque['Alerta Minimo']])
