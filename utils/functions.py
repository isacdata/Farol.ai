import re
import pandas as pd
import datetime
from groq import Groq
import os
import streamlit as st

def limpar_cnpj(cnpj_input: str) -> str:
    if not cnpj_input:
        return ""
    return re.sub(r'\D', '', cnpj_input)

def validar_comprimento_cnpj(cnpj_limpo: str) -> bool:
    return len(cnpj_limpo) == 14

def construir_dataframe_cnpj(dados_empresas) -> pd.DataFrame:
    if isinstance(dados_empresas, dict):
        dados_empresas = [dados_empresas]
        
    lista_linhas_planas = []
    
    for dados in dados_empresas:
        cnpj_bruto = dados.get('cnpj', '')
        cnpj_limpo = str(cnpj_bruto).strip().replace(".", "").replace("/", "").replace("-", "")
        
        linha = {
            "cnpj": cnpj_limpo,
            "razao_social": dados.get("razao_social"),
            "nome_fantasia": dados.get("nome_fantasia") or dados.get("razao_social"),
            "cnae_principal_codigo": dados.get("cnae_fiscal"),
            "cnae_principal_descricao": dados.get("cnae_fiscal_descricao"),
            "capital_social": float(dados.get("capital_social", 0.0)),
            "situacao_cadastral_codigo": dados.get("situacao_cadastral"),
            "situacao_cadastral_desc": dados.get("descricao_situacao_cadastral"),
            "data_inicio_atividade": dados.get("data_inicio_atividade"),
            "data_situacao_cadastral": dados.get("data_situacao_cadastral", "Não informada"),
            "data_opcao_pelo_simples": dados.get("data_opcao_pelo_simples"),
            "data_exclusao_do_simples": dados.get("data_exclusao_do_simples"),
            "cnaes_secundarios": dados.get("cnaes_secundarios", []),
            "qsa": dados.get("qsa", []),
            "faturamento_estimado": dados.get("faturamento_estimado"),
            "enquadramento_provavel": dados.get("enquadramento_provavel"),
            "gatilho_fiscal": dados.get("gatilho_fiscal"),
            "idade_empresa_anos": dados.get("idade_empresa_anos"),
            "saude_cadastral": dados.get("saude_cadastral"),
            "complexidade_venda": dados.get("complexidade_venda"),
            "total_socios_diretores": dados.get("total_socios_diretores"),
            "idade_predominante_board": dados.get("idade_predominante_board"),
            "ddd_telefone1": dados.get('ddd_telefone_1'),
            "ddd_telefone2": dados.get('ddd_telefone_2'),
            'pais': dados.get('pais'),
            'email': dados.get('email'),
            'porte': dados.get('porte'),
            'bairro': dados.get('bairro'),
            'numero': dados.get('numero'),
            'ddd_fax': dados.get('ddd_fax'),
            'municipio': dados.get('municipio'),
            'logradouro': dados.get('logradouro'),
            'descricao_identificador_matriz_filial': dados.get('descricao_identificador_matriz_filial'),
        }
        
        decisores = dados.get("decisores_principais", [])
        if isinstance(decisores, list):
            linha["decisores_principais"] = ", ".join(decisores)
        else:
            linha["decisores_principais"] = decisores
        
        lista_linhas_planas.append(linha)
        
    df_final = pd.DataFrame(lista_linhas_planas)
    if not df_final.empty:
        df_final.set_index('cnpj', inplace=True)
        
    return df_final

def exibir_painel_lead(df):
    """Exibe os dados estruturados do lead de forma visual e amigável no Streamlit"""
    lead = df.iloc[0]
    
    st.write(f"### 🏢 {lead['razao_social']}")
    if lead['nome_fantasia'] and lead['nome_fantasia'] != lead['razao_social']:
        st.caption(f"Conhecida como: {lead['nome_fantasia']}")

    # --- LINHA 1: MÉTRICAS DE SAÚDE E DINHEIRO ---
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Capital Social", f"R$ {lead['capital_social']:,.2f}")
    with col2:
        st.metric("Idade da Empresa", f"{lead['idade_empresa_anos']} Anos")
    with col3:
        # Simplificado para não bugar a engine do Streamlit
        st.metric("Saúde Cadastral", str(lead['saude_cadastral']).replace("🟢 ", "").replace("🟡 ", "").replace("🔴 ", ""))
    with col4:
        st.metric("Porte Cadastral", str(lead['porte']))

    # --- LINHA 2: INTELIGÊNCIA FISCAL E VENDAS ---
    st.write("---")
    c1, c2 = st.columns(2)
    with c1:
        st.success(f"**Enquadramento Provável:**\n{lead['enquadramento_provavel']}")
    with c2:
        st.warning(f"**Gatilho Fiscal:**\n{lead['gatilho_fiscal']}")

    # --- LINHA 3: CONTATOS E DECISORES ---
    st.write("---")
    ca, cb = st.columns([1, 1])
    with ca:
        st.subheader("📞 Contatos")
        st.markdown(f"**Telefones:** {lead.get('ddd_telefone1', 'Não informado')} / {lead.get('ddd_telefone2', 'Não informado')}")
        st.markdown(f"**E-mail:** {lead.get('email', 'Não informado')}")
        st.markdown(f"**Endereço:** {lead.get('logradouro', '')}, {lead.get('numero', '')} - {lead.get('bairro', '')}, {lead.get('municipio', '')}")
    
    with cb:
        st.subheader("👥 Quadro Decisor")
        st.markdown(f"**Decisores Principais:** `{lead['decisores_principais']}`")
        st.markdown(f"**Total Sócios/Diretores:** {lead['total_socios_diretores']}")
        with st.expander("Ver Quadro de Sócios Completo (QSA)"):
            st.write(lead['qsa'])

    # CNAEs
    st.write("---")
    with st.expander("📋 Atividade Principal e Secundárias"):
        st.markdown(f"**Principal:** {lead['cnae_principal_descricao']}")
        st.write(lead['cnaes_secundarios'])


def gerar_pitch_ia(df: pd.DataFrame, api_key: str, num_cnpj: str) -> str:
    """
    Gera o pitch de vendas estratégico usando a API da Groq.
    Retorna a string completa para ser exibida instantaneamente, sem efeito de digitação lenta.
    """
    client = Groq(api_key=api_key)

    if num_cnpj not in df.index:
        return f"❌ Erro: O CNPJ {num_cnpj} não foi encontrado no DataFrame."

    lead = df.loc[num_cnpj]
    
    prompt_contexto = f"""
    [DIRETRIZ DE MAX_TOKENS: Sua resposta completa NÃO PODE ultrapassar 500 tokens de saída. Seja extremamente direto, conciso, limpo e focado em conversão. Elimine introduções ou encerramentos cordiais. Vá direto para os tópicos estruturais em Markdown.]

    Você é um Diretor de Vendas B2B de Elite de seguros corporativos e planos de saúde empresariais no Brasil.
    Sua missão é criar uma estratégia de ataque comercial ultra-sintética para abordar o lead abaixo.

    DADOS DO LEAD:
    - Razão Social: {lead.get('razao_social')}
    - Ramo de Atividade: {lead.get('cnae_principal_descricao')}
    - Capital Social: R$ {lead.get('capital_social', 0.0):,.2f} | Porte: {lead.get('porte')}
    - Localização: {lead.get('municipio')} - {lead.get('situacao_cadastral_desc')}
    - Regime Tributário Provável: {lead.get('enquadramento_provavel')}
    - Gatilho Fiscal de Fechamento: {lead.get('gatilho_fiscal')}
    - Idade da Empresa: {lead.get('idade_empresa_anos')} anos | Complexidade: {lead.get('complexidade_venda')}
    - Decisores Principais a Chamar: {lead.get('decisores_principais')}

    REQUISITOS DA SAÍDA (Gere estritamente em formato Markdown curto):
    
    # 💡 Estratégia de Abordagem Comercial — {lead.get('nome_fantasia') or lead.get('razao_social')}

    ## 🎯 1. O Gancho de Abertura (Cold Call)
    [Gere um roteiro exato de no máximo 3 frases focado em falar direto com os `{lead.get('decisores_principais')}` usando o tempo de mercado de {lead.get('idade_empresa_anos')} anos como autoridade.]

    ## 💰 2. Argumentação de Impacto Financeiro
    [Gere um argumento rápido de 2 frases conectando o regime `{lead.get('enquadramento_provavel')}` com o `{lead.get('gatilho_fiscal')}`.]

    ## 🛡️ 3. Mapeamento de Riscos e Produtos
    [Indique em tópicos rápidos quais produtos oferecer com base na complexidade '{lead.get('complexidade_venda')}'.]

    ## ⚡ 4. Quebra de Objeção "Matadora"
    [Uma resposta direta de 2 linhas para quando o tomador disser: "Já temos corretor".]
    """

    try:
        # Execução full-speed na Groq sem stream
        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt_contexto}],
            temperature=0.1,
            max_tokens=500,
            top_p=0.9,
            stream=False  # <-- Desligado para não enrolar na tela
        )
        
        return completion.choices[0].message.content
                
    except Exception as e:
        return f"❌ Erro ao gerar o pitch na API da Groq: {str(e)}"