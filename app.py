import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

st.set_page_config(page_title="Sistema de Estoque GPS", layout="wide", page_icon="📦")

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
    else:
        # Cria a estrutura caso a aba esteja vazia
        df_estoque = pd.DataFrame(columns=['Codigo', 'Descricao', 'Quantidade', 'Preco', 'Alerta Minimo'])

except Exception as e:
    st.error("🚨 ERRO DETALHADO AO CARREGAR ESTOQUE:")
    st.exception(e)
    st.stop()

# --- INTERFACE PRINCIPAL ---
st.title("📦 Sistema de Estoque GPS")
st.sidebar.header("🛠️ Menu")
acao = st.sidebar.radio(
    "Navegação:", 
    ["Estoque", "Entrada", "Venda", "Histórico de Vendas", "Orçamento", "Trocas", "Histórico de Trocas"]
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
        df_ver['Preço Unit.'] = df_ver['Preco'].apply(lambda x: f"R$ {x:.2f}")
        df_ver['Valor Total Item'] = df_ver['Valor Total'].apply(lambda x: f"R$ {x:.2f}")
        
        st.dataframe(
            df_ver[['Status', 'Codigo', 'Descricao', 'Quantidade', 'Alerta Minimo', 'Preço Unit.', 'Valor Total Item']], 
            use_container_width=True, 
            hide_index=True
        )

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
elif acao == "Venda":
    st.subheader("💸 Lançar Venda")
    cod_v = st.text_input("Digite o Código da Peça:").strip()
    
    if cod_v:
        if cod_v in df_estoque['Codigo'].values:
            idx = df_estoque[df_estoque['Codigo'] == cod_v].index[0]
            desc_v = df_estoque.at[idx, 'Descricao']
            preco_base_v = float(df_estoque.at[idx, 'Preco'])
            qtd_disponivel = int(df_estoque.at[idx, 'Quantidade'])
            
            st.info(f"📦 **Peça:** {desc_v} | 🔹 **Disponível:** {qtd_disponivel} unidades")
            
            with st.form("form_venda"):
                c1, c2 = st.columns(2)
                qtd_v = c1.number_input("Quantidade", min_value=1, max_value=max(1, qtd_disponivel), value=1)
                preco_v = c2.number_input("Preço Unitário (R$)", min_value=0.0, value=preco_base_v, step=0.1)
                
                c3, c4 = st.columns(2)
                desconto_v = c3.number_input("Desconto (%)", min_value=0.0, max_value=100.0, value=0.0, step=1.0)
                cli = c4.text_input("Nome do Cliente", value="Consumidor Final")
                
                anotacoes = st.text_area("Anotações:")
                
                total_bruto_v = qtd_v * preco_v
                valor_desconto_v = total_bruto_v * (desconto_v / 100)
                total_liquido_v = total_bruto_v - valor_desconto_v
                
                st.markdown(f"**Total Líquido a Pagar:** R$ {total_liquido_v:.2f}")
                
                if st.form_submit_button("Finalizar Venda", type="primary"):
                    if qtd_disponivel >= qtd_v:
                        df_estoque.at[idx, 'Quantidade'] -= qtd_v
                        salvar_dados(df_estoque, "estoque_gps")
                        
                        agora = datetime.now()
                        nova_venda = pd.DataFrame([{
                            'Data': agora.strftime('%d/%m/%Y'),
                            'Horario': agora.strftime('%H:%M:%S'),
                            'Codigo': str(cod_v),
                            'Descricao': desc_v,
                            'Quantidade': int(qtd_v),
                            'Valor Unitario': preco_v,
                            'Valor Total': total_liquido_v,
                            'Desconto %': desconto_v,
                            'Desconto R$': valor_desconto_v,
                            'Cliente': cli,
                            'Anotacoes': anotacoes
                        }])
                        
                        try:
                            df_hist = carregar_dados("historico_vendas")
                            df_hist = pd.concat([df_hist, nova_venda], ignore_index=True)
                        except Exception:
                            df_hist = nova_venda
                        
                        salvar_dados(df_hist, "historico_vendas")
                        st.success("✅ Venda concluída!")
                    else:
                        st.error("❌ Erro: Estoque insuficiente.")
        else:
            st.error("❌ Código de peça não cadastrado.")

# As demais abas (Histórico, Orçamento, Trocas) seguem a mesma lógica otimizada...
# Adicionei tratamento similar para evitar quebras.
# (Por brevidade, abas 4 a 7 mantêm a estrutura original, mas aplique `.strip()` nos inputs de texto e chame st.dataframe com tratamento seguro).
# --- ABA 4: HISTÓRICO DE VENDAS ---
elif acao == "Histórico de Vendas":
    st.subheader("📊 Relatório de Vendas Realizadas")
    try:
        df_historico = carregar_dados("historico_vendas")
        if not df_historico.empty:
            filtro = st.text_input("🔍 Filtrar histórico de vendas:").lower()
            df_filtrado = df_historico.copy()
            if filtro:
                mask_hist = (
                    df_filtrado['Cliente'].astype(str).str.lower().str.contains(filtro) |
                    df_filtrado['Codigo'].astype(str).str.lower().str.contains(filtro) |
                    df_filtrado['Descricao'].astype(str).str.lower().str.contains(filtro)
                )
                df_filtrado = df_filtrado[mask_hist]
            
            df_filtrado = df_filtrado.iloc[::-1]
            df_filtrado['Valor Unitario'] = pd.to_numeric(df_filtrado['Valor Unitario'], errors='coerce').fillna(0).apply(lambda x: f"R$ {x:.2f}")
            df_filtrado['Valor Total'] = pd.to_numeric(df_filtrado['Valor Total'], errors='coerce').fillna(0).apply(lambda x: f"R$ {x:.2f}")
            df_filtrado['Desconto R$'] = pd.to_numeric(df_filtrado['Desconto R$'], errors='coerce').fillna(0).apply(lambda x: f"R$ {x:.2f}")
            
            st.dataframe(df_filtrado, use_container_width=True, hide_index=True)
        else:
            st.info("Nenhum registro de venda encontrado.")
    except Exception as e:
        st.warning("⚠️ A aba 'historico_vendas' ainda não foi configurada ou está vazia.")

# --- ABA 5: ORÇAMENTO ---
elif acao == "Orçamento":
    st.subheader("🧮 Calculadora de Orçamento")
    cod_o = st.text_input("Digite o Código da Peça:").strip()
    
    if cod_o:
        if cod_o in df_estoque['Codigo'].values:
            idx = df_estoque[df_estoque['Codigo'] == cod_o].index[0]
            desc_o = df_estoque.at[idx, 'Descricao']
            preco_base_o = float(df_estoque.at[idx, 'Preco'])
            
            st.info(f"📦 **Modelo Selecionado:** {desc_o}")
            
            c1, c2, c3 = st.columns(3)
            qtd_o = c1.number_input("Quantidade Desejada", min_value=1, value=1)
            preco_o = c2.number_input("Valor Unitário Customizado (R$)", min_value=0.0, value=preco_base_o, step=0.5)
            desconto_o = c3.number_input("Abatimento / Desconto (%)", min_value=0.0, max_value=100.0, value=0.0, step=1.0)
            
            total_bruto = qtd_o * preco_o
            valor_desconto = total_bruto * (desconto_o / 100)
            total_liquido = total_bruto - valor_desconto
            
            st.markdown("---")
            cm1, cm2, cm3 = st.columns(3)
            cm1.metric("Valor Bruto Total", f"R$ {total_bruto:.2f}")
            cm2.metric("Desconto total", f"R$ {valor_desconto:.2f} ({desconto_o}%)")
            cm3.metric("Valor com Desconto", f"R$ {total_liquido:.2f}")
        else:
            st.error("❌ Modelo não localizado.")

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
