import re
import pandas as pd
from groq import Groq
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
            "situacao_cadastral_desc": dados.get("descricao_situacao_cadastral"),
            "data_inicio_atividade": dados.get("data_inicio_atividade"),
            "qsa": dados.get("qsa", []),
            "enquadramento_provavel": dados.get("enquadramento_provavel"),
            "gatilho_fiscal": dados.get("gatilho_fiscal"),
            "idade_empresa_anos": dados.get("idade_empresa_anos"),
            "saude_cadastral": dados.get("saude_cadastral"),
            "complexidade_venda": dados.get("complexidade_venda"),
            "total_socios_diretores": dados.get("total_socios_diretores"),
            "ddd_telefone1": dados.get('ddd_telefone_1'),
            "ddd_telefone2": dados.get('ddd_telefone_2'),
            'email': dados.get('email'),
            'porte': dados.get('porte'),
            'bairro': dados.get('bairro'),
            'numero': dados.get('numero'),
            'municipio': dados.get('municipio'),
            'logradouro': dados.get('logradouro'),
            'decisores_principais': ", ".join(dados.get("decisores_principais", [])) if isinstance(dados.get("decisores_principais"), list) else dados.get("decisores_principais"),
            "cnaes_secundarios": dados.get("cnaes_secundarios", [])
        }
        
        lista_linhas_planas.append(linha)
        
    df_final = pd.DataFrame(lista_linhas_planas)
    if not df_final.empty:
        df_final.set_index('cnpj', inplace=True)
        
    return df_final

def exibir_painel_lead(df):
    """Exibe os dados estruturados do lead de forma visual e amigável no Streamlit"""
    lead = df.iloc[0]
    
    st.write(f"### 🏢 {lead.get('razao_social', 'Razão Social não informada')}")
    if lead.get('nome_fantasia') and lead['nome_fantasia'] != lead['razao_social']:
        st.caption(f"Conhecida como: {lead['nome_fantasia']}")

    def render_metrica(label, valor):
        st.markdown(f"""
            <div style="line-height: 1.4; margin-bottom: 14px;">
                <span style="font-size: 12px; color: #a5a5af; text-transform: uppercase; letter-spacing: 0.5px;">{label}</span><br>
                <span style="font-size: 16px; font-weight: 600; white-space: normal; word-wrap: break-word; display: inline-block; margin-top: 2px;">{valor}</span>
            </div>
        """, unsafe_allow_html=True)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        render_metrica("Capital Social", f"R$ {lead.get('capital_social', 0.0):,.2f}")
    with col2:
        render_metrica("Idade da Empresa", f"{lead.get('idade_empresa_anos', 0)} Anos")
    with col3:
        render_metrica("Saúde Cadastral", str(lead.get('saude_cadastral', '')).replace("🟢 ", "").replace("🔴 ", ""))
    with col4:
        render_metrica("Porte Cadastral", str(lead.get('porte', 'Não informado')).title())

    st.write("---")
    c1, c2 = st.columns(2)
    with c1:
        st.success(f"**Enquadramento Provável:**\n{lead.get('enquadramento_provavel', '')}")
    with c2:
        st.warning(f"**Gatilho Fiscal:**\n{lead.get('gatilho_fiscal', '')}")

    st.write("---")
    ca, cb = st.columns([1, 1])
    with ca:
        st.subheader("📞 Contatos")
        st.markdown(f"**Telefones:** {lead.get('ddd_telefone1', 'N/A')} / {lead.get('ddd_telefone2', 'N/A')}")
        st.markdown(f"**E-mail:** {lead.get('email', 'N/A')}")
        st.markdown(f"**Endereço:** {lead.get('logradouro', '')}, {lead.get('numero', '')} - {lead.get('bairro', '')}, {lead.get('municipio', '')}")
    
    with cb:
        st.subheader("👥 Quadro Decisor")
        st.markdown(f"**Decisores Principais:** `{lead.get('decisores_principais', '')}`")
        st.markdown(f"**Total Sócios/Diretores:** {lead.get('total_socios_diretores', 0)}")
        
        # AQUI MOSTRAMOS A IDADE NO ECRÃ
        with st.expander("Ver Quadro de Sócios Completo (QSA)"):
            qsa_lista = lead.get('qsa', [])
            if qsa_lista:
                for socio in qsa_lista:
                    st.markdown(f"👤 **{socio.get('nome_socio', '')}**")
                    st.markdown(f"↳ {socio.get('qualificacao_socio', 'Sócio')} | *Idade: {socio.get('faixa_etaria', 'N/A')}*")
            else:
                st.write("Quadro de sócios não disponível.")

    st.write("---")
    with st.expander("📋 Atividade Principal e Secundárias"):
        st.markdown(f"**Principal:** {lead.get('cnae_principal_descricao', '')}")
        st.write(lead.get('cnaes_secundarios', []))


def gerar_pitch_ia(df: pd.DataFrame, api_key: str, num_cnpj: str) -> str:
    """
    Gera o pitch de vendas estratégico usando a API da Groq.
    Trata erros de codificação ASCII forçando UTF-8.
    """
    client = Groq(api_key=api_key)

    if num_cnpj not in df.index:
        return f"❌ Erro: O CNPJ {num_cnpj} não foi encontrado no DataFrame."

    lead = df.loc[num_cnpj]
    
Aqui está o bloco de código do prompt totalmente ajustado e polido para focar estritamente nesses três produtos, trazendo um argumento de venda personalizado para cada um deles com base nas informações coletadas do lead.

Também aproveitei para readequar as outras seções para garantir que todo o contexto da IA esteja girando em torno de Planos de Saúde e Seguros de Vida, mantendo a blindagem de codificação UTF-8 que aplicamos anteriormente:

Python
def gerar_pitch_ia(df: pd.DataFrame, api_key: str, num_cnpj: str) -> str:
    """
    Gera o pitch de vendas estratégico usando a API da Groq.
    Trata erros de codificação ASCII forçando UTF-8 em todo o bloco de dados.
    """
    client = Groq(api_key=api_key)

    if num_cnpj not in df.index:
        return f"❌ Erro: O CNPJ {num_cnpj} não foi encontrado no DataFrame."

    lead = df.loc[num_cnpj]
    
    # Extrai e limpa os dados do lead para garantir que nenhuma string quebre o encoding
    razao_social = str(lead.get('razao_social', '')).encode('utf-8', 'ignore').decode('utf-8')
    cnae_desc = str(lead.get('cnae_principal_descricao', '')).encode('utf-8', 'ignore').decode('utf-8')
    porte = str(lead.get('porte', '')).encode('utf-8', 'ignore').decode('utf-8')
    municipio = str(lead.get('municipio', '')).encode('utf-8', 'ignore').decode('utf-8')
    gatilho = str(lead.get('gatilho_fiscal', '')).encode('utf-8', 'ignore').decode('utf-8')
    enquadramento = str(lead.get('enquadramento_provavel', '')).encode('utf-8', 'ignore').decode('utf-8')
    complexidade = str(lead.get('complexidade_venda', '')).encode('utf-8', 'ignore').decode('utf-8')
    decisores = str(lead.get('decisores_principais', '')).encode('utf-8', 'ignore').decode('utf-8')
    nome_fantasia = str(lead.get('nome_fantasia', '')).encode('utf-8', 'ignore').decode('utf-8') or razao_social
    
    # Converte a lista do QSA com segurança para string UTF-8
    qsa_lista = str(lead.get('qsa', [])).encode('utf-8', 'ignore').decode('utf-8')

    prompt_contexto = f"""
    [DIRETRIZ DE MAX_TOKENS: Sua resposta completa NÃO PODE ultrapassar 500 tokens de saída. Seja extremamente direto, conciso e focado em conversão. Vá direto para os tópicos estruturais em Markdown. Elimine qualquer saudação ou introdução.]

    Você é um Diretor de Vendas de Seguros B2B de Elite no Brasil, especialista em estruturar benefícios corporativos de alto impacto.
    Sua missão é criar uma estratégia de abordagem comercial ultra-sintética para o lead abaixo, focando unicamente em Plano de Saúde, Seguro de Vida Individual e Seguro de Vida em Grupo.

    DADOS DO LEAD:
    - Razão Social: {razao_social}
    - Ramo de Atividade: {cnae_desc}
    - Capital Social: R$ {lead.get('capital_social', 0.0):,.2f} | Porte: {porte}
    - Gatilho Fiscal de Fechamento: {gatilho}
    - Regime Tributário Provável: {enquadramento}
    - Idade da Empresa: {lead.get('idade_empresa_anos', 0)} anos | Complexidade: {complexidade}
    - Decisores Principais a Chamar: {decisores}
    - PERFIL DOS SÓCIOS (IDADES): {qsa_lista}

    REQUISITOS DA SAÍDA (Gere estritamente em formato Markdown curto):
    
    # 💡 Estratégia de Abordagem Comercial — {nome_fantasia}

    ## 🎯 1. O Gancho de Abertura (Cold Call)
    Gere um roteiro exato de no máximo 3 frases focado em falar direto com os decisores mapeados para agendar uma reunião de diagnóstico de benefícios. ADAPTE O TOM DE VOZ com base na Faixa Etária dos sócios: Se forem acima de 50 anos, use um tom formal focado em blindagem patrimonial, sucessão societária estável e retenção de liderança sênior; se forem mais jovens, adote um tom dinâmico focado em atratividade de talentos no mercado, eficiência operacional e inovação digital em saúde corporativa.

    ## 💰 2. Argumentação de Impacto Financeiro
    Gere um argumento rápido de 2 frases conectando o regime tributário provável do lead com o gatilho fiscal enviado. Destaque como a implementação ou revisão do Plano de Saúde ou do Seguro de Vida pode trazer retorno financeiro e otimização de caixa (como a dedução fiscal no IRPJ se for Lucro Real) ou redução de desperdício em apólices mal dimensionadas.

    ## 🛡️ 3. Mapeamento de Riscos e Produtos
    Apresente obrigatoriamente APENAS os 3 produtos abaixo estruturados em bullet points rápidos. Para cada produto, crie um argumento de venda sob medida baseado nas informações coletadas (idade dos sócios, porte, capital social e tempo de mercado da empresa):
    - **Plano de Saúde:** [Crie o argumento focado no perfil, porte e localização do lead]
    - **Seguro de Vida Individual (para os Sócios):** [Crie o argumento focado na idade dos sócios e no capital social da empresa]
    - **Seguro de Vida em Grupo (para Colaboradores):** [Crie o argumento focado no ramo de atividade, riscos operacionais ou convenção coletiva do setor]

    ## ⚡ 4. Quebra de Objeção "Matadora"
    Uma resposta direta de no máximo 2 linhas para quando o decisor soltar a objeção: "Já temos corretor de seguros" ou "Nossos colaboradores já estão satisfeitos com o que têm".
    """

    # --- CORREÇÃO DO BUG DE ASCII PARA WINDOWS/NUVEM ---
    # Normaliza a string do prompt para UTF-8 puro, ignorando caracteres fantasmas
    prompt_normalizado = prompt_contexto.encode('utf-8', errors='ignore').decode('utf-8')

    try:
        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt_normalizado}], # Usando o prompt normalizado
            temperature=0.1,
            max_tokens=500,
            top_p=0.9,
            stream=False 
        )
        return completion.choices[0].message.content
                
    except Exception as e:
        return f"❌ Erro ao gerar o pitch na API da Groq: {str(e)}"