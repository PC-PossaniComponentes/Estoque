import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

st.set_page_config(page_title="Sistema de Estoque GPS", layout="wide", page_icon="📦")

# --- INICIALIZAÇÃO DOS CARRINHOS ---
if "carrinho" not in st.session_state:
    st.session_state["carrinho"] = []

if "carrinho_pedidos" not in st.session_state: # <--- ADICIONE ESTA LINHA
    st.session_state["carrinho_pedidos"] = []

# --- ALARME DE CREDENCIAIS (NOVO) ---
if "connections" not in st.secrets or "gsheets" not in st.secrets["connections"]:
    st.error("🚨 Erro: O arquivo secrets.toml não está configurado corretamente (bloco [connections.gsheets] ausente).")
    st.stop()

if st.secrets["connections"]["gsheets"].get("type") != "service_account":
    st.error("🚨 Erro: A linha `type = \"service_account\"` está faltando ou escrita errada no secrets.toml.")
    st.stop()

# --- CONFIGURAÇÕES SEGURAS ---
URL_DA_PLANILHA = st.secrets.get("URL_DA_PLANILHA")
SENHA_SISTEMA = st.secrets["SENHA_SISTEMA"]

# Conexão oficial
conn = st.connection("gsheets", type=GSheetsConnection)

# --- TRAVA DE SEGURANÇA FINAL ---
# Bloqueia e avisa se o robô virou anônimo por causa de erro no secrets.toml
if "Public" in str(type(conn.client)):
    st.error("🚨 O Streamlit achou um erro invisível no seu secrets.toml e tentou entrar como Anônimo.")
    st.warning("👉 **Como resolver:** \n1. Verifique se você trocou os traços `-` por `=` como falamos. \n2. Verifique se a sua `private_key` está exata, não pode faltar nenhuma aspa ou `\\n`. \n3. **CRÍTICO:** Pare o robô no terminal (Ctrl + C) e rode `streamlit run app.py` novamente!")
    st.stop()

def carregar_dados(aba):
    # O bot VIP agora pode usar a rota expressa sem tomar Erro 404!
    return conn.read(worksheet=aba, ttl=600)

def salvar_dados(df, aba):
    conn.update(worksheet=aba, data=df)
    st.cache_data.clear()

# ... DAQUI PARA BAIXO O SEU CÓDIGO (Lógica de acesso, menus, etc) CONTINUA EXATAMENTE IGUAL ...

# --- LÓGICA DE ACESSO ---
if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False

if not st.session_state["autenticado"]:
    st.title("🔒 Sistema GPS - Acesso Restrito")
    
    with st.form("login_form"):
        senha = st.text_input("Digite a senha do sistema:", type="password")
        submit = st.form_submit_button("Entrar")
        
        if submit:
            if senha == SENHA_SISTEMA:
                st.session_state["autenticado"] = True
                st.rerun()
            else:
                st.error("Senha incorreta!")
    st.stop()

# --- CARREGAMENTO DE DADOS ---
try:
    df_estoque = carregar_dados("estoque_gps")
    
    # Validação e Limpeza Básica
    if not df_estoque.empty:
        df_estoque['Codigo'] = df_estoque['Codigo'].astype(str).apply(lambda x: x[:-2] if x.endswith('.0') else x)
        df_estoque['Quantidade'] = pd.to_numeric(df_estoque['Quantidade'], errors='coerce').fillna(0).astype(int)
        df_estoque['Preco'] = pd.to_numeric(df_estoque['Preco'], errors='coerce').fillna(0.0)
        
        if 'Alerta Minimo' not in df_estoque.columns:
            df_estoque['Alerta Minimo'] = 5
        df_estoque['Alerta Minimo'] = pd.to_numeric(df_estoque['Alerta Minimo'], errors='coerce').fillna(5).astype(int)
        
        # 👇 TRECHO NOVO: Garante que a coluna Anotações exista 👇
        if 'Anotacoes' not in df_estoque.columns:
            df_estoque['Anotacoes'] = ""
        df_estoque['Anotacoes'] = df_estoque['Anotacoes'].fillna("").astype(str)
        
    else:
        # Cria a estrutura caso a aba esteja vazia (AGORA COM ANOTAÇÕES)
        df_estoque = pd.DataFrame(columns=['Codigo', 'Descricao', 'Quantidade', 'Preco', 'Alerta Minimo', 'Anotacoes'])

except Exception as e:
    st.error("🚨 ERRO DETALHADO AO CARREGAR ESTOQUE:")
    st.exception(e)
    st.stop()
# --- INTERFACE PRINCIPAL ---
st.title("📦 Sistema de Estoque GPS")
st.sidebar.header("🛠️ Menu")
acao = st.sidebar.radio(
    "Navegação:", 
    ["Entrada", "Estoque", "Venda", "Orçamento", "Trocas", "Histórico de Vendas", "Histórico de Trocas", "Pedidos"]
)

# --- ABA 1: ESTOQUE ---
if acao == "Estoque":
    st.subheader("📋 Estoque na Nuvem")
    
    if df_estoque.empty:
        st.warning("O estoque está vazio. Vá para a aba 'Entrada' para cadastrar produtos.")
    else:
        df_estoque['Valor Total'] = df_estoque['Quantidade'] * df_estoque['Preco']
        total_patrimonio = df_estoque['Valor Total'].sum()
        total_pecas = df_estoque['Quantidade'].sum()
        itens_criticos = df_estoque[df_estoque['Quantidade'] <= df_estoque['Alerta Minimo']].shape[0]
        
        c_med1, c_med2, c_med3 = st.columns(3)
        c_med1.metric("Quantidade de Peças", f"{total_pecas} un")
        c_med2.metric("Valor Total do Estoque", f"R$ {total_patrimonio:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        
        if itens_criticos > 0:
            c_med3.metric("⚠️ Itens Abaixo do Limite", f"{itens_criticos} itens", delta="- Crítico", delta_color="inverse")
        else:
            c_med3.metric("Status do Estoque", "✅ Tudo OK")
        
        st.markdown("---")
        termo = st.text_input("🔍 Buscar peça (Código ou Descrição)").lower()
        df_ver = df_estoque.copy()
        
        if termo:
            mask = df_ver['Codigo'].str.lower().str.contains(termo) | df_ver['Descricao'].str.lower().str.contains(termo)
            df_ver = df_ver[mask]
        
        df_ver['Status'] = df_ver.apply(lambda r: "⚠️ Baixo" if r['Quantidade'] <= r['Alerta Minimo'] else "✅ OK", axis=1)
        df_ver['Valor Total Item'] = df_ver['Valor Total'].apply(lambda x: f"R$ {x:.2f}")
        
       # --- A TABELA EDITÁVEL COM EXCLUSÃO ---
        st.markdown("### ✏️ Edição e Exclusão")
        st.caption("Altere os dados diretamente na tabela ou selecione linhas para excluir.")

        # Adicionamos uma coluna de seleção para facilitar a exclusão
        df_editado = st.data_editor(
            df_ver[['Status', 'Codigo', 'Descricao', 'Quantidade', 'Preco', 'Alerta Minimo', 'Anotacoes', 'Valor Total Item']], 
            use_container_width=True, 
            hide_index=True,
            disabled=['Status', 'Codigo', 'Descricao', 'Quantidade', 'Valor Total Item'],
            column_config={
                "Preco": st.column_config.NumberColumn("Preço Unit. (R$)", min_value=0.0, format="R$ %.2f"),
                "Alerta Minimo": st.column_config.NumberColumn("Alerta Mínimo", min_value=0, step=1),
                "Anotacoes": st.column_config.TextColumn("Anotações")
            }
        )

        # Colunas para organizar os botões
        c1, c2 = st.columns([1, 4])
        
        # Botão de Salvar
        if c1.button("💾 Salvar Alterações", type="primary"):
            df_estoque.set_index('Codigo', inplace=True)
            df_editado.set_index('Codigo', inplace=True)
            df_estoque.update(df_editado[['Preco', 'Alerta Minimo', 'Anotacoes']])
            df_estoque.reset_index(inplace=True)
            salvar_dados(df_estoque, "estoque_gps")
            st.success("✅ Alterações salvas!")
            st.rerun()

        # Botão de Excluir (lógica segura)
        st.markdown("---")
        with st.expander("🗑️ Excluir Produto"):
            cod_excluir = st.selectbox("Selecione o código do produto para excluir:", options=[""] + df_ver['Codigo'].tolist())
            if cod_excluir:
                if st.button(f"Confirmar exclusão definitiva do código {cod_excluir}?", type="secondary"):
                    df_estoque = df_estoque[df_estoque['Codigo'] != cod_excluir]
                    salvar_dados(df_estoque, "estoque_gps")
                    st.warning(f"Produto {cod_excluir} removido!")
                    st.rerun()

# --- ABA 2: ENTRADA ---
elif acao == "Entrada":
    st.subheader("📥 Dar Entrada / Ajustar Peças")
    st.info("💡 Para alterar apenas o limite ou o preço, deixe a 'Quantidade a Adicionar' em 0.")
    
    with st.form("f_entrada", clear_on_submit=True):
        c1, c2 = st.columns(2)
        cod = c1.text_input("Código da Peça").strip()
        qtd = c1.number_input("Quantidade a Adicionar", min_value=0, value=0)
        limite_min = c1.number_input("Definir Limite para Estoque Baixo", min_value=0, value=5)
        
        desc = c2.text_input("Descrição (Caso seja nova)").strip()
        prec = c2.number_input("Preço Unitário (Novo)", min_value=0.0, step=0.5)
        
        submit = st.form_submit_button("Confirmar Ajuste/Entrada", type="primary")
        
        if submit and cod:
            if cod in df_estoque['Codigo'].values:
                idx = df_estoque[df_estoque['Codigo'] == cod].index[0]
                df_estoque.loc[idx, 'Quantidade'] += qtd
                df_estoque.loc[idx, 'Alerta Minimo'] = limite_min
                if prec > 0:
                    df_estoque.loc[idx, 'Preco'] = prec
                st.success(f"Estoque do código {cod} atualizado com sucesso!")
            else:
                if not desc:
                    st.error("Para novas peças, a descrição é obrigatória!")
                    st.stop()
                    
                nova = pd.DataFrame({'Codigo': [cod], 'Descricao': [desc], 'Quantidade': [qtd], 'Preco': [prec], 'Alerta Minimo': [limite_min]})
                df_estoque = pd.concat([df_estoque, nova], ignore_index=True)
                st.success("Nova peça cadastrada com sucesso!")
                
            salvar_dados(df_estoque, "estoque_gps")
            # st.rerun() omitido aqui intencionalmente para que o usuário consiga ler a mensagem de sucesso.

# --- ABA 3: VENDA ---
# --- ABA 3: VENDA ---
elif acao == "Venda":
    st.subheader("💸 Lançar Venda Multi-itens")
    
    # 1. EXPANDER PARA ADICIONAR PEÇAS
    with st.expander("➕ Adicionar Peças ao Carrinho", expanded=True):
        cod_v = st.text_input("Código da Peça:").strip()
        
        if cod_v in df_estoque['Codigo'].values:
            idx = df_estoque[df_estoque['Codigo'] == cod_v].index[0]
            desc_v = df_estoque.at[idx, 'Descricao']
            qtd_disp = int(df_estoque.at[idx, 'Quantidade'])
            preco_base = float(df_estoque.at[idx, 'Preco'])
            
            c1, c2, c3 = st.columns(3)
            qtd_sel = c1.number_input("Qtd", min_value=1, max_value=qtd_disp, value=1)
            preco_unit = c2.number_input("Preço Unit.", min_value=0.0, value=preco_base)
            desc_pct = c3.number_input("Desc %", min_value=0.0, max_value=100.0, value=0.0)
            
            val_desconto_rs = (preco_unit * (desc_pct / 100))
            preco_final = preco_unit - val_desconto_rs
            st.write(f"Preço Final Unit.: **R$ {preco_final:.2f}**")
            
            if st.button("Adicionar ao Carrinho"):
                st.session_state["carrinho"].append({
                    "Codigo": cod_v, "Descricao": desc_v, "Qtd": qtd_sel, 
                    "Preco": preco_unit, "Desc %": desc_pct, 
                    "Desc R$": val_desconto_rs * qtd_sel
                })
                st.rerun()

    # 2. VISUALIZAÇÃO DO CARRINHO
    if st.session_state["carrinho"]:
        st.write("### 🛒 Itens no Carrinho")
        df_carrinho = pd.DataFrame(st.session_state["carrinho"])
        df_carrinho['Subtotal'] = df_carrinho['Qtd'] * df_carrinho['Preco']
        df_carrinho['Total Líquido'] = df_carrinho['Subtotal'] - df_carrinho['Desc R$']
        
        st.table(df_carrinho[['Codigo', 'Descricao', 'Qtd', 'Preco', 'Desc %', 'Desc R$', 'Total Líquido']])
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Bruto", f"R$ {df_carrinho['Subtotal'].sum():.2f}")
        col2.metric("Total Descontos", f"R$ {df_carrinho['Desc R$'].sum():.2f}")
        col3.metric("TOTAL A PAGAR", f"R$ {df_carrinho['Total Líquido'].sum():.2f}")
        
        if st.button("❌ Limpar Carrinho"):
            st.session_state["carrinho"] = []
            st.rerun()
            
        # 3. FINALIZAÇÃO
        cli = st.text_input("Nome do Cliente:", value="Consumidor Final")
        if st.button("✅ Finalizar Venda", type="primary"):
            agora = datetime.now()
            id_venda = agora.strftime('%Y%m%d%H%M%S')
            itens = st.session_state["carrinho"].copy()
            
            # Desconta estoque
            for item in itens:
                idx = df_estoque[df_estoque['Codigo'] == item['Codigo']].index[0]
                df_estoque.at[idx, 'Quantidade'] -= item['Qtd']
            salvar_dados(df_estoque, "estoque_gps")
            
            # Salva histórico
            df_novas = pd.DataFrame(itens).rename(columns={'Qtd': 'Quantidade', 'Preco': 'Valor Unitario', 'Desc %': 'Desconto %', 'Desc R$': 'Desconto R$'})
            df_novas['ID_Venda'] = id_venda
            df_novas['Data'] = agora.strftime('%d/%m/%Y')
            df_novas['Horario'] = agora.strftime('%H:%M:%S')
            df_novas['Cliente'] = cli
            df_novas['Valor Total'] = df_novas['Quantidade'] * df_novas['Valor Unitario']
            
            try:
                df_hist = carregar_dados("historico_vendas")
            except:
                df_hist = pd.DataFrame()
            
            salvar_dados(pd.concat([df_hist, df_novas], ignore_index=True), "historico_vendas")
            
            st.session_state["carrinho"] = []
            st.success("✅ Venda concluída!")
            st.rerun()
            
            salvar_dados(df_estoque, "estoque_gps")
            
            # 2. Prepara histórico (usa os itens_para_vender)
            novas_vendas = pd.DataFrame(itens_para_vender)
            
            # Ajuste de nomes para bater com o histórico antigo
            novas_vendas = novas_vendas.rename(columns={'Qtd': 'Quantidade', 'Preco': 'Valor Unitario'})
            
            novas_vendas['ID_Venda'] = id_venda
            novas_vendas['Data'] = agora.strftime('%d/%m/%Y')
            novas_vendas['Horario'] = agora.strftime('%H:%M:%S')
            novas_vendas['Cliente'] = cli
            novas_vendas['Valor Total'] = novas_vendas['Quantidade'] * novas_vendas['Valor Unitario']
            novas_vendas['Desconto %'] = 0.0
            novas_vendas['Desconto R$'] = 0.0
            novas_vendas['Anotacoes'] = ""
            
            # Carrega e concatena
            try:
                df_hist = carregar_dados("historico_vendas")
            except:
                df_hist = pd.DataFrame()
            
            # Adiciona apenas as novas linhas
            df_hist = pd.concat([df_hist, novas_vendas], ignore_index=True)
            salvar_dados(df_hist, "historico_vendas")
            
            # 3. LIMPA O CARRINHO E RECARREGA
            st.session_state["carrinho"] = []
            st.success(f"✅ Venda {id_venda} concluída e salva!")
            st.rerun()
            
            # GARANTE QUE AS COLUNAS ESTEJAM NA MESMA ORDEM E FORMA
            df_hist = pd.concat([df_hist, novas_vendas], ignore_index=True)
            salvar_dados(df_hist, "historico_vendas")
            
            df_hist = pd.concat([df_hist, novas_vendas], ignore_index=True)
            salvar_dados(df_hist, "historico_vendas")
            
            st.session_state["carrinho"] = []
            st.success(f"✅ Venda {id_venda} concluída!")
            st.rerun()
            
            salvar_dados(df_estoque, "estoque_gps")
            
            # 2. Salva no histórico de vendas
            try:
                df_hist = carregar_dados("historico_vendas")
            except:
                df_hist = pd.DataFrame()
            
            novas_vendas = pd.DataFrame(st.session_state["carrinho"])
            novas_vendas['Data'] = agora.strftime('%d/%m/%Y')
            novas_vendas['Horario'] = agora.strftime('%H:%M:%S')
            novas_vendas['Cliente'] = cli
            novas_vendas['Valor Total'] = novas_vendas['Qtd'] * novas_vendas['Preco']
            
            df_hist = pd.concat([df_hist, novas_vendas], ignore_index=True)
            salvar_dados(df_hist, "historico_vendas")
            
            st.session_state["carrinho"] = [] # Limpa carrinho
            st.success("✅ Venda concluída e salva!")
            st.rerun()

# As demais abas (Histórico, Orçamento, Trocas) seguem a mesma lógica otimizada...
# Adicionei tratamento similar para evitar quebras.
# (Por brevidade, abas 4 a 7 mantêm a estrutura original, mas aplique `.strip()` nos inputs de texto e chame st.dataframe com tratamento seguro).
# --- ABA 4: HISTÓRICO DE VENDAS ---
elif acao == "Histórico de Vendas":
    st.subheader("📊 Relatório de Vendas")
    try:
        df_hist = carregar_dados("historico_vendas")
        
        if not df_hist.empty:
            # Proteção para dados antigos
            if 'ID_Venda' not in df_hist.columns:
                df_hist['ID_Venda'] = "ANTIGO"
            
            # --- SEÇÃO DE EXCLUSÃO ---
            with st.expander("🗑️ Excluir Venda"):
                # Lista apenas IDs únicos
                ids_unicos = df_hist['ID_Venda'].unique().tolist()
                id_para_deletar = st.selectbox("Selecione o ID da venda para excluir:", ids_unicos)
                
                if st.button("🚨 Confirmar Exclusão da Venda"):
                    # Filtra removendo todas as linhas que contêm aquele ID
                    df_hist = df_hist[df_hist['ID_Venda'] != id_para_deletar]
                    salvar_dados(df_hist, "historico_vendas")
                    st.warning(f"Venda {id_para_deletar} excluída com sucesso!")
                    st.rerun()

            # --- EXIBIÇÃO ---
            resumo = df_hist.groupby('ID_Venda').agg({
                'Data': 'first',
                'Cliente': 'first',
                'Valor Total': 'sum'
            }).rename(columns={'Valor Total': 'Total da Venda'})
            
            st.write("### Vendas Realizadas (Agrupadas)")
            st.dataframe(resumo.sort_index(ascending=False), use_container_width=True)
            
            st.write("### Detalhes dos itens vendidos")
            st.dataframe(df_hist.sort_values(by='ID_Venda', ascending=False), use_container_width=True)
        else:
            st.info("Nenhuma venda registrada.")
            
    except Exception as e:
        st.error(f"Erro ao carregar histórico: {e}")
# --- ABA 5: ORÇAMENTO ---
elif acao == "Orçamento":
    st.subheader("🧮 Simulador de Orçamento")
    
    # 1. ADICIONAR AO CARRINHO DE ORÇAMENTO
    with st.expander("➕ Adicionar Peças ao Orçamento", expanded=True):
        cod_o = st.text_input("Código da Peça (Orçamento):").strip()
        
        if cod_o in df_estoque['Codigo'].values:
            idx = df_estoque[df_estoque['Codigo'] == cod_o].index[0]
            desc_o = df_estoque.at[idx, 'Descricao']
            preco_base = float(df_estoque.at[idx, 'Preco'])
            
            c1, c2, c3 = st.columns(3)
            qtd_o = c1.number_input("Qtd", min_value=1, value=1)
            preco_unit = c2.number_input("Preço Unit.", min_value=0.0, value=preco_base)
            desc_pct = c3.number_input("Desc %", min_value=0.0, max_value=100.0, value=0.0)
            
            val_desconto_rs = (preco_unit * (desc_pct / 100))
            preco_final = preco_unit - val_desconto_rs
            st.write(f"Preço Final por unidade: **R$ {preco_final:.2f}**")
            
            if st.button("Adicionar ao Orçamento"):
                st.session_state["carrinho"].append({
                    "Codigo": cod_o, "Descricao": desc_o, "Qtd": qtd_o, 
                    "Preco": preco_unit, "Desc %": desc_pct, 
                    "Desc R$": val_desconto_rs * qtd_o
                })
                st.rerun()

    # 2. VISUALIZAÇÃO DO ORÇAMENTO
    if st.session_state["carrinho"]:
        st.write("### 📋 Itens do Orçamento")
        df_orc = pd.DataFrame(st.session_state["carrinho"])
        
        # Cálculos de exibição
        df_orc['Subtotal Bruto'] = df_orc['Qtd'] * df_orc['Preco']
        df_orc['Total Líquido'] = df_orc['Subtotal Bruto'] - df_orc['Desc R$']
        
        st.table(df_orc[['Codigo', 'Descricao', 'Qtd', 'Preco', 'Subtotal Bruto', 'Desc %', 'Desc R$', 'Total Líquido']])
        
        # Totais Finais
        total_bruto = df_orc['Subtotal Bruto'].sum()
        total_descontos = df_orc['Desc R$'].sum()
        total_final = df_orc['Total Líquido'].sum()
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Bruto (Sem Desc)", f"R$ {total_bruto:.2f}")
        col2.metric("Total em Descontos", f"R$ {total_descontos:.2f}")
        col3.metric("VALOR FINAL COM DESCONTO", f"R$ {total_final:.2f}")
        
        if st.button("❌ Limpar Orçamento"):
            st.session_state["carrinho"] = []
            st.rerun()
            
        st.info("💡 Dica: Esta é uma simulação. Para transformar em venda, lance os itens na aba Venda.")

# --- ABA 6: REALIZAR TROCAS ---
elif acao == "Trocas":
    st.subheader("🔄 Registrar Troca de Peça Defeituosa")
    cod_t = st.text_input("Digite o Código da Peça para Troca:").strip()
    
    if cod_t:
        if cod_t in df_estoque['Codigo'].values:
            idx = df_estoque[df_estoque['Codigo'] == cod_t].index[0]
            desc_t = df_estoque.at[idx, 'Descricao']
            qtd_disponivel = int(df_estoque.at[idx, 'Quantidade'])
            
            st.info(f"📦 **Peça:** {desc_t}  |  🔹 **Disponível para reposição:** {qtd_disponivel} unidades")
            
            with st.form("form_trocas"):
                c1, c2 = st.columns(2)
                qtd_chegou = c1.number_input("Qtd de peças DEFEITUOSAS que CHEGARAM", min_value=0, value=1)
                qtd_saiu = c2.number_input("Qtd de peças NOVAS que SAÍRAM", min_value=0, max_value=max(1, qtd_disponivel), value=1)
                
                cli_t = st.text_input("Nome do Cliente / Fabricante:")
                anotacoes_t = st.text_area("Motivo do defeito ou observações:")
                
                diferenca = qtd_saiu - qtd_chegou
                
                st.markdown("---")
                if diferenca > 0:
                    st.warning(f"⚠️ O cliente está levando {diferenca} peça(s) a mais do que devolveu.")
                elif diferenca < 0:
                    st.info(f"📉 O cliente devolveu {abs(diferenca)} peça(s) a mais do que levou (Ficou com crédito).")
                else:
                    st.success("✅ Troca equivalente (1 por 1). Nenhuma diferença de quantidade.")
                    
                submit_troca = st.form_submit_button("Finalizar e Registrar Troca", type="primary")
                
                if submit_troca:
                    if qtd_disponivel >= qtd_saiu:
                        df_estoque.at[idx, 'Quantidade'] -= qtd_saiu
                        salvar_dados(df_estoque, "estoque_gps")
                        
                        agora = datetime.now()
                        nova_troca = pd.DataFrame([{
                            'Data': agora.strftime('%d/%m/%Y'),
                            'Horario': agora.strftime('%H:%M:%S'),
                            'Codigo': str(cod_t),
                            'Descricao': desc_t,
                            'Qtd Defeituosas': int(qtd_chegou),
                            'Qtd Novas Sairam': int(qtd_saiu),
                            'Diferenca': int(diferenca),
                            'Cliente': cli_t,
                            'Anotacoes': anotacoes_t
                        }])
                        
                        try:
                            df_hist_t = carregar_dados("historico_trocas")
                            df_hist_t = pd.concat([df_hist_t, nova_troca], ignore_index=True)
                        except Exception:
                            df_hist_t = nova_troca
                            
                        salvar_dados(df_hist_t, "historico_trocas")
                        st.success("✅ Troca registrada e salva no histórico com sucesso!")
                    else:
                        st.error("❌ Não há estoque novo suficiente para realizar essa saída.")
        else:
            st.error("❌ Peça não encontrada no estoque.")

# --- ABA 7: HISTÓRICO DE TROCAS ---
elif acao == "Histórico de Trocas":
    st.subheader("📊 Histórico Geral de Trocas e Peças Defeituosas")
    try:
        df_hist_trocas = carregar_dados("historico_trocas")
        if not df_hist_trocas.empty:
            filtro_t = st.text_input("🔍 Filtrar por Cliente, Código ou Defeito:").lower()
            df_f_t = df_hist_trocas.copy()
            
            if filtro_t:
                mask_t = (
                    df_f_t['Cliente'].astype(str).str.lower().str.contains(filtro_t) |
                    df_f_t['Codigo'].astype(str).str.lower().str.contains(filtro_t) |
                    df_f_t['Anotacoes'].astype(str).str.lower().str.contains(filtro_t)
                )
                df_f_t = df_f_t[mask_t]
                
            st.dataframe(df_f_t.iloc[::-1], use_container_width=True, hide_index=True)
        else:
            st.info("Nenhum registro de troca foi localizado.")
    except Exception:
        st.warning("⚠️ A aba 'historico_trocas' ainda não foi criada no Google Sheets ou está vazia.")
# --- ABA: PEDIDOS ---
elif acao == "Pedidos":
    st.subheader("📝 Gestão de Pedidos (Multi-itens)")

    # 1. EXPANDER PARA ADICIONAR PEÇAS AO PEDIDO
    with st.expander("➕ Adicionar Peças à Encomenda", expanded=True):
        cod_p = st.text_input("Código da Peça para Pedido:").strip()
        
        if cod_p in df_estoque['Codigo'].values:
            idx = df_estoque[df_estoque['Codigo'] == cod_p].index[0]
            desc_p = df_estoque.at[idx, 'Descricao']
            
            c1, c2 = st.columns(2)
            qtd_p = c1.number_input("Quantidade Pedida", min_value=1, value=1)
            
            if st.button("Adicionar ao Carrinho de Pedidos"):
                st.session_state["carrinho_pedidos"].append({
                    "Codigo": cod_p, 
                    "Descricao": desc_p, 
                    "Quantidade": qtd_p
                })
                st.rerun()

    # 2. VISUALIZAÇÃO DO CARRINHO DE PEDIDOS
    if st.session_state["carrinho_pedidos"]:
        st.write("### 🛒 Itens deste Pedido")
        df_carrinho_p = pd.DataFrame(st.session_state["carrinho_pedidos"])
        st.table(df_carrinho_p)
        
        if st.button("❌ Limpar este Pedido"):
            st.session_state["carrinho_pedidos"] = []
            st.rerun()
            
        st.markdown("---")
        # 3. DADOS DE ENTREGA E FINALIZAÇÃO
        c_cli, c_data = st.columns(2)
        cli_p = c_cli.text_input("Nome do Cliente (Pedido):")
        data_entrega = c_data.date_input("Data de Entrega Prometida:")
        
    if st.button("✅ Confirmar Pedido Completo", type="primary"):
            agora = datetime.now()
            id_pedido = agora.strftime('%Y%m%d%H%M%S')
            
            # --- CORREÇÃO DO NOME DA VARIÁVEL ---
            # Vamos usar "novos_itens_pedido" (com "o") em tudo
            novos_itens_pedido = pd.DataFrame(st.session_state["carrinho_pedidos"].copy())
            
            novos_itens_pedido['ID_Pedido'] = id_pedido
            novos_itens_pedido['Data do Pedido'] = agora.strftime('%d/%m/%Y')
            novos_itens_pedido['Horario'] = agora.strftime('%H:%M:%S')
            novos_itens_pedido['Cliente'] = cli_p
            novos_itens_pedido['Data de Entrega'] = data_entrega.strftime('%d/%m/%Y')
            
            try:
                df_pedidos_existentes = carregar_dados("pedidos")
            except:
                df_pedidos_existentes = pd.DataFrame()
                
            # Agora concatenamos a variável que definimos acima
            salvar_dados(pd.concat([df_pedidos_existentes, novos_itens_pedido], ignore_index=True), "pedidos")
            
            st.session_state["carrinho_pedidos"] = [] # Limpa carrinho
            st.success(f"✅ Pedido {id_pedido} registrado com sucesso!")
            st.rerun()

    # --- 4. LISTAGEM DE PEDIDOS PENDENTES (AGRUPADA) ---
    st.markdown("---")
    st.write("### 📋 Pedidos na Fila de Espera")
    try:
        df_p_lista = carregar_dados("pedidos")
        if not df_p_lista.empty:
            # Resumo por ID_Pedido
            resumo_p = df_p_lista.groupby('ID_Pedido').agg({
                'Cliente': 'first',
                'Data de Entrega': 'first',
                'Quantidade': 'sum'
            }).rename(columns={'Quantidade': 'Total de Peças'})
            
            st.dataframe(resumo_p.sort_values(by='Data de Entrega'), use_container_width=True)
            
            with st.expander("🔍 Ver Detalhes / Finalizar Pedido"):
                id_sel = st.selectbox("Selecione o ID do Pedido:", df_p_lista['ID_Pedido'].unique().tolist())
                # Mostra o que tem dentro desse pedido específico
                st.write(df_p_lista[df_p_lista['ID_Pedido'] == id_sel][['Codigo', 'Descricao', 'Quantidade']])
                
                if st.button("🗑️ Marcar como Entregue / Excluir"):
                    df_p_lista = df_p_lista[df_p_lista['ID_Pedido'] != id_sel]
                    salvar_dados(df_p_lista, "pedidos")
                    st.warning(f"Pedido {id_sel} removido da fila!")
                    st.rerun()
        else:
            st.info("Não há pedidos pendentes.")
    except:
        st.info("Aba 'pedidos' ainda não contém registros.")
