import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

st.set_page_config(page_title="Sistema de Estoque GPS", layout="wide")

# --- URL DA PLANILHA ---
URL_DA_PLANILHA = "https://docs.google.com/spreadsheets/d/1GixbU30cjCRFZ8FN-LOFWJfzxNgX-Ae3YH5cx2lQEZk/edit?pli=1&gid=771554962#gid=771554962"

# Conexão oficial (lendo do secrets.toml)
conn = st.connection("gsheets", type=GSheetsConnection)

def carregar_dados(aba):
    return conn.read(spreadsheet=URL_DA_PLANILHA, worksheet=aba, ttl=600)

def salvar_dados(df, aba):
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
    df_estoque['Codigo'] = df_estoque['Codigo'].astype(str).apply(lambda x: x[:-2] if x.endswith('.0') else x)
    df_estoque['Quantidade'] = pd.to_numeric(df_estoque['Quantidade']).fillna(0).astype(int)
    df_estoque['Preco'] = pd.to_numeric(df_estoque['Preco']).fillna(0.0)
    
    if 'Alerta Minimo' not in df_estoque.columns:
        df_estoque['Alerta Minimo'] = 5
    df_estoque['Alerta Minimo'] = pd.to_numeric(df_estoque['Alerta Minimo']).fillna(5).astype(int)

except Exception as e:
    st.error("🚨 ERRO DETALHADO AO CARREGAR ESTOQUE:")
    st.write(e)
    st.stop()

# --- INTERFACE PRINCIPAL ---
st.title("📦 Sistema de Estoque GPS")
st.sidebar.header("🛠️ Menu")
acao = st.sidebar.radio("Escolha:", ["Estoque", "Entrada", "Venda", "Histórico de Vendas", "Orçamento", "Trocas", "Histórico de Trocas"])

# --- ABA 1: ESTOQUE ---
if acao == "Estoque":
    st.subheader("📋 Estoque na Nuvem")
    
    df_estoque['Valor Total'] = df_estoque['Quantidade'] * df_estoque['Preco']
    total_patrimonio = df_estoque['Valor Total'].sum()
    total_pecas = df_estoque['Quantidade'].sum()
    itens_criticos = df_estoque[df_estoque['Quantidade'] <= df_estoque['Alerta Minimo']].shape[0]
    
    c_med1, c_med2, c_med3 = st.columns(3)
    c_med1.metric("Quantidade de Peças", f"{total_pecas} un")
    c_med2.metric("Valor Total do Estoque", f"R$ {total_patrimonio:.2f}")
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
    st.info("💡 Para alterar apenas o limite de Estoque Baixo ou o Preço de uma peça existente sem alterar a quantidade atual, deixe o campo 'Quantidade a Adicionar' em 0.")
    with st.form("f_entrada"):
        c1, c2 = st.columns(2)
        cod = c1.text_input("Código da Peça")
        qtd = c1.number_input("Quantidade a Adicionar", min_value=0, value=0)
        limite_min = c1.number_input("Definir Limite para Estoque Baixo", min_value=0, value=5)
        
        desc = c2.text_input("Descrição (Caso seja nova)")
        prec = c2.number_input("Preço Unitário (Novo)", min_value=0.0, step=0.5)
        
        if st.form_submit_button("Confirmar Ajuste/Entrada"):
            if cod in df_estoque['Codigo'].values:
                idx = df_estoque[df_estoque['Codigo'] == cod].index[0]
                df_estoque.loc[idx, 'Quantidade'] += qtd
                df_estoque.loc[idx, 'Alerta Minimo'] = limite_min
                if prec > 0:
                    df_estoque.loc[idx, 'Preco'] = prec
            else:
                nova = pd.DataFrame({'Codigo':[cod], 'Descricao':[desc], 'Quantidade':[qtd], 'Preco':[prec], 'Alerta Minimo':[limite_min]})
                df_estoque = pd.concat([df_estoque, nova], ignore_index=True)
                
            salvar_dados(df_estoque, "estoque_gps")
            st.success("Configurações atualizadas com sucesso!")
            st.rerun()

# --- ABA 3: VENDA ---
elif acao == "Venda":
    st.subheader("💸 Lançar Venda")
    cod_v = st.text_input("Digite o Código da Peça:")
    
    if cod_v:
        if cod_v in df_estoque['Codigo'].values:
            idx = df_estoque[df_estoque['Codigo'] == cod_v].index[0]
            desc_v = df_estoque.at[idx, 'Descricao']
            preco_base_v = float(df_estoque.at[idx, 'Preco'])
            qtd_disponivel = df_estoque.at[idx, 'Quantidade']
            
            st.info(f"📦 **Peça:** {desc_v}  |  🔹 **Disponível em Estoque:** {qtd_disponivel} unidades")
            
            c1, c2 = st.columns(2)
            qtd_v = c1.number_input("Quantidade a Vender", min_value=1, max_value=int(qtd_disponivel) if qtd_disponivel > 0 else 1, value=1)
            preco_v = c2.number_input("Preço Unitário Praticado (R$)", min_value=0.0, value=preco_base_v, step=0.1)
            
            c3, c4 = st.columns(2)
            desconto_v = c3.number_input("Desconto na Venda (%)", min_value=0.0, max_value=100.0, value=0.0, step=1.0)
            cli = c4.text_input("Nome do Cliente", value="Consumidor Final")
            
            anotacoes = st.text_area("Anotações ou Comentários desta Venda:")
            
            total_bruto_v = qtd_v * preco_v
            valor_desconto_v = total_bruto_v * (desconto_v / 100)
            total_liquido_v = total_bruto_v - valor_desconto_v
            
            st.markdown("---")
            col_v1, col_v2, col_v3 = st.columns(3)
            col_v1.metric("Total Bruto", f"R$ {total_bruto_v:.2f}")
            col_v2.metric("Desconto Concedido", f"R$ {valor_desconto_v:.2f} ({desconto_v}%)")
            col_v3.metric("Total Líquido", f"R$ {total_liquido_v:.2f}")
            
            if st.button("Finalizar e Registrar Venda", type="primary"):
                if qtd_disponivel >= qtd_v:
                    df_estoque.at[idx, 'Quantidade'] -= qtd_v
                    salvar_dados(df_estoque, "estoque_gps")
                    
                    agora = datetime.now()
                    nova_venda = pd.DataFrame({
                        'Data': [agora.strftime('%d/%m/%Y')],
                        'Horario': [agora.strftime('%H:%M:%S')],
                        'Codigo': [str(cod_v)],
                        'Descricao': [desc_v],
                        'Quantidade': [int(qtd_v)],
                        'Valor Unitario': [preco_v],
                        'Valor Total': [total_liquido_v],
                        'Desconto %': [desconto_v],
                        'Desconto R$': [valor_desconto_v],
                        'Cliente': [cli],
                        'Anotacoes': [anotacoes]
                    })
                    
                    try:
                        df_hist = carregar_dados("historico_vendas")
                        df_hist = pd.concat([df_hist, nova_venda], ignore_index=True)
                    except Exception:
                        df_hist = nova_venda
                    
                    salvar_dados(df_hist, "historico_vendas")
                    st.success("✅ Venda concluída e salva no histórico!")
                    st.rerun()
                else:
                    st.error("❌ Erro: Estoque insuficiente.")
        else:
            st.error("❌ Código de peça não cadastrado.")

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
            df_filtrado['Valor Unitario'] = df_filtrado['Valor Unitario'].astype(float).apply(lambda x: f"R$ {x:.2f}")
            df_filtrado['Valor Total'] = df_filtrado['Valor Total'].astype(float).apply(lambda x: f"R$ {x:.2f}")
            df_filtrado['Desconto R$'] = df_filtrado['Desconto R$'].astype(float).apply(lambda x: f"R$ {x:.2f}")
            st.dataframe(df_filtrado, use_container_width=True, hide_index=True)
        else:
            st.info("Nenhum registro de venda encontrado.")
    except Exception:
        st.warning("⚠️ A aba 'historico_vendas' ainda não foi configurada ou está vazia.")

# --- ABA 5: ORÇAMENTO ---
elif acao == "Orçamento":
    st.subheader("🧮 Calculadora de Orçamento")
    cod_o = st.text_input("Digite o Código da Peça:")
    
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

# --- ABA 6: REALIZAR TROCAS (NOVA!) ---
elif acao == "Trocas":
    st.subheader("🔄 Registrar Troca de Peça Defeituosa")
    cod_t = st.text_input("Digite o Código da Peça para Troca:")
    
    if cod_t:
        if cod_t in df_estoque['Codigo'].values:
            idx = df_estoque[df_estoque['Codigo'] == cod_t].index[0]
            desc_t = df_estoque.at[idx, 'Descricao']
            qtd_disponivel = df_estoque.at[idx, 'Quantidade']
            
            st.info(f"📦 **Peça:** {desc_t}  |  🔹 **Disponível para reposição:** {qtd_disponivel} unidades")
            
            c1, c2 = st.columns(2)
            qtd_chegou = c1.number_input("Quantidade de peças DEFEITUOSAS que CHEGARAM", min_value=0, value=1)
            qtd_saiu = c2.number_input("Quantidade de peças NOVAS que SAÍRAM", min_value=0, max_value=int(qtd_disponivel), value=1)
            
            cli_t = st.text_input("Nome do Cliente / Fabricante:")
            anotacoes_t = st.text_area("Motivo do defeito ou observações sobre a troca:")
            
            # Cálculo de diferença
            diferenca = qtd_saiu - qtd_chegou
            
            st.markdown("---")
            if diferenca > 0:
                st.warning(f"⚠️ O cliente está levando {diferenca} peça(s) a mais do que devolveu.")
            elif diferenca < 0:
                st.info(f"📉 O cliente devolveu {abs(diferenca)} peça(s) a mais do que levou (Ficou com crédito).")
            else:
                st.success("✅ Troca equivalente (1 por 1). Nenhuma diferença de quantidade.")
                
            if st.button("Finalizar e Registrar Troca", type="primary"):
                if qtd_disponivel >= qtd_saiu:
                    # Dá baixa no estoque com base nas peças novas que saíram
                    df_estoque.at[idx, 'Quantidade'] -= qtd_saiu
                    salvar_dados(df_estoque, "estoque_gps")
                    
                    agora = datetime.now()
                    nova_troca = pd.DataFrame({
                        'Data': [agora.strftime('%d/%m/%Y')],
                        'Horario': [agora.strftime('%H:%M:%S')],
                        'Codigo': [str(cod_t)],
                        'Descricao': [desc_t],
                        'Qtd Defeituosas': [int(qtd_chegou)],
                        'Qtd Novas Sairam': [int(qtd_saiu)],
                        'Diferenca': [int(diferenca)],
                        'Cliente': [cli_t],
                        'Anotacoes': [anotacoes_t]
                    })
                    
                    try:
                        df_hist_t = carregar_dados("historico_trocas")
                        df_hist_t = pd.concat([df_hist_t, nova_troca], ignore_index=True)
                    except Exception:
                        df_hist_t = nova_troca
                        
                    salvar_dados(df_hist_t, "historico_trocas")
                    st.success("✅ Troca registrada e salva no histórico com sucesso!")
                    st.rerun()
                else:
                    st.error("❌ Não há estoque novo suficiente para realizar essa saída.")
        else:
            st.error("❌ Peça não encontrada no estoque.")

# --- ABA 7: HISTÓRICO DE TROCAS (NOVA!) ---
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
        st.warning("⚠️ A aba 'historico_trocas' ainda não foi criada no Google Sheets.")
