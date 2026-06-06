import sys
import os

# Força a raiz do Farol.ai ser a prioridade número 1 de leitura do Python
diretorio_atual = os.path.dirname(os.path.abspath(__file__))
raiz_projeto = os.path.abspath(os.path.join(diretorio_atual, ".."))
if raiz_projeto not in sys.path:
    sys.path.insert(0, raiz_projeto) # <-- A mágica da prioridade acontece no insert(0)

from groq import Groq
import streamlit as st
import pandas as pd
from datetime import datetime

from utils.extractions_apis import buscar_dados_cnpj
from utils.functions import (
    limpar_cnpj,
    validar_comprimento_cnpj,
    construir_dataframe_cnpj,
    exibir_painel_lead,
    gerar_pitch_ia
)

st.set_page_config(
    page_title="Farol.ai — Sales Intelligence",
    page_icon="💡",
    layout="wide"
)

def calcular_metricas_venda(dados_api: dict) -> dict:
    metricas = {}
    
    # Proteção de parsing de data
    try:
        dt_string = dados_api.get("data_inicio_atividade", "")
        if dt_string:
            dt_abertura = datetime.strptime(dt_string, "%Y-%m-%d")
            metricas["idade_empresa_anos"] = datetime.now().year - dt_abertura.year
        else:
            metricas["idade_empresa_anos"] = 0
    except Exception:
        metricas["idade_empresa_anos"] = 0

    porte = str(dados_api.get("porte", "")).upper()
    razao_social = str(dados_api.get("razao_social", "")).upper()
    
    if any(termo in razao_social for termo in ["ASSOCIACAO", "INSTITUTO", "COMUNIDADE", "IGREJA", "FUNDACAO"]):
        metricas["enquadramento_provavel"] = "Imune / Isenta (Sem Fins Lucrativos)"
        metricas["gatilho_fiscal"] = "Foco em Proteção Patrimonial, Responsabilidade Civil e Planos por Adesão."
    elif "MICRO" in porte or porte == "1":
        metricas["enquadramento_provavel"] = "Simples Nacional"
        metricas["gatilho_fiscal"] = "Foco em Custo por Vida baixo e tabelas PME para retenção."
    elif "PEQUENO" in porte or porte == "3":
        metricas["enquadramento_provavel"] = "Simples Nacional ou Lucro Presumido"
        metricas["gatilho_fiscal"] = "Apresentar tabelas PME corporativas com carência reduzida."
    else:
        metricas["enquadramento_provavel"] = "Lucro Real ou Presumido (Grande Porte)"
        metricas["gatilho_fiscal"] = "GATILHO DE OURO: Dedução integral do valor do benefício no IRPJ!"

    situacao = str(dados_api.get("descricao_situacao_cadastral", "")).upper()
    if "ATIVA" in situacao:
        metricas["saude_cadastral"] = "🟢 EXCELENTE" if metricas["idade_empresa_anos"] >= 5 else "🟡 MODERADA (Empresa Jovem)"
    else:
        metricas["saude_cadastral"] = f"🔴 ALTO RISCO (Status: {situacao})"

    qsa = dados_api.get("qsa", [])
    metricas["total_socios_diretores"] = len(qsa)
    
    if len(qsa) > 10:
        metricas["complexidade_venda"] = "Altíssima (Decisão via Comitê corporativo)"
        metricas["idade_predominante_board"] = "Mista (Diretoria Executiva Sênior)"
    else:
        metricas["complexidade_venda"] = "Média/Baixa (Contato Direto com Sócios)"
        metricas["idade_predominante_board"] = "Focada nos Sócios Administradores"

    decisores = [s.get("nome_socio") for s in qsa if str(s.get("qualificacao_socio")).upper() in ["PRESIDENTE", "ADMINISTRADOR", "DIRETOR", "PASTOR", "DIRETOR EXECUTIVO"]]
    metricas["decisores_principais"] = ", ".join(decisores) if decisores else "Diretoria / Responsáveis Diretos"

    return metricas

st.title("💡 Farol.ai — Inteligência de Vendas B2B")
st.markdown("Busque CNPJs, analise a saúde fiscal e gere argumentos de impacto instantâneos.")
st.write("---")

with st.sidebar:
    st.header("🔑 Configurações do Sistema")
    
    api_key_default = ""
    try:
        if "GROQ_API_KEY" in st.secrets:
            api_key_default = st.secrets["GROQ_API_KEY"]
    except Exception:
        pass
        
    if not api_key_default:
        try:
            caminho_manual = os.path.normpath(os.path.join(raiz_projeto, ".streamlit", "secrets.toml"))
            if os.path.exists(caminho_manual):
                with open(caminho_manual, "r", encoding="utf-8") as f:
                    for linha in f:
                        if "GROQ_API_KEY" in linha and "=" in linha:
                            api_key_default = linha.split("=")[1].replace('"', '').replace("'", "").strip()
        except Exception:
            pass
        
    api_key_input = st.text_input("Groq API Key (gsk_...):", value=api_key_default, type="password")
    st.markdown("---")
    st.info("⚡ Motor Atual: Llama 3.1 8B Instant")

cnpj_usuario = st.text_input("Digite o CNPJ da Empresa:", placeholder="00.000.000/0000-00")

if st.button("💡 Acender o Farol", type="primary"):
    cnpj_limpo = limpar_cnpj(cnpj_usuario)
    
    if not validar_comprimento_cnpj(cnpj_limpo):
        st.error("❌ Erro: O CNPJ deve conter exatamente 14 números.")
    elif not api_key_input:
        st.warning("⚠️ Atenção: Forneça sua Groq API Key na barra lateral para gerar o pitch.")
    else:
        dados_brutos = None
        
        # A Mágica Acontece Aqui: 3 APIs tentam buscar o dado silenciosamente
        try:
            with st.spinner("🔍 Varrendo ecossistema corporativo (Tentando 3 bases de dados)..."):
                dados_brutos = buscar_dados_cnpj(cnpj_limpo)
                # Mostra no cantinho da tela qual API salvou a pátria
                st.toast(f"✅ Dados obtidos via {dados_brutos.get('fonte', 'API')}", icon="📡")
        except Exception as e:
            st.error(f"❌ Nenhuma base pública respondeu. Detalhes: {e}")
            st.stop()
        
        if dados_brutos:
            try:
                metricas_calculadas = calcular_metricas_venda(dados_brutos)
                for chave, valor in metricas_calculadas.items():
                    dados_brutos[chave] = valor
                
                df_lead = construir_dataframe_cnpj(dados_brutos)
                
                st.success("🏢 Dados mapeados com sucesso!")
                exibir_painel_lead(df_lead)
                
                st.write("---")
                st.subheader("⚡ Estratégia de Venda (Farol.ai)")
                
                with st.spinner("Iluminando a estratégia instantaneamente..."):
                    pitch_markdown = gerar_pitch_ia(df_lead, api_key_input, cnpj_limpo)
                    
                    if "❌ Erro" in pitch_markdown:
                        st.error(pitch_markdown)
                    else:
                        st.markdown(pitch_markdown)
                    
            except Exception as e:
                st.error(f"❌ Ocorreu um erro na plotagem dos dados: {str(e)}")