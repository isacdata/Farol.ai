import re
from datetime import datetime
import requests
import pandas as pd
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

def buscar_dados_cnpj_brasilapi(cnpj_limpo: str) -> dict:
    """
    Consome a BrasilAPI com proteção nativa (Exponential Backoff) contra Erro 429.
    """
    if len(cnpj_limpo) != 14:
        raise ValueError("O CNPJ deve conter exatamente 14 dígitos numéricos.")
        
    url = f"https://brasilapi.com.br/api/cnpj/v1/{cnpj_limpo}"
    
    # ---------------------------------------------------------
    # CONFIGURAÇÃO DE RETRY (EXPONENTIAL BACKOFF)
    # ---------------------------------------------------------
    session = requests.Session()
    retry_strategy = Retry(
        total=4,  # Tentar até 4 vezes antes de estourar o erro
        status_forcelist=[429, 500, 502, 503, 504], # Status que engatilham nova tentativa
        allowed_methods=["GET"],
        backoff_factor=2 # Espera 2s, depois 4s, 8s, 16s...
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    
    try:
        response = session.get(url, timeout=30) # Timeout ligeiramente maior
        
        if response.status_code == 404:
            raise KeyError(f"CNPJ {cnpj_limpo} não encontrado na base de dados.")
        elif response.status_code != 200:
            raise requests.exceptions.HTTPError(f"Erro na API externa: Status {response.status_code}")
            
        return response.json()
        
    except requests.exceptions.RequestException as e:
        raise ConnectionError(f"Falha de conexão ao buscar o CNPJ: {e}")

def buscar_dados_cnpj_ws(cnpj_limpo: str) -> dict:
    """
    Plano A: Consome o endpoint público da CNPJ.ws.
    Se falhar por limite de requisições (429) ou erro de rede, 
    aciona automaticamente o Plano B (BrasilAPI).
    """
    if len(cnpj_limpo) != 14:
        raise ValueError("O CNPJ deve conter exatamente 14 dígitos numéricos.")
        
    url = f"https://publica.cnpj.ws/cnpj/{cnpj_limpo}"
    headers = {"X-Type": "Public"}

    try:
        # --- TENTATIVA 1: CNPJ.ws ---
        response = requests.get(url, headers=headers, timeout=10)
        
        # Se der erro de limite (429) ou qualquer erro de servidor, joga pro bloco except acionar o Plano B
        if response.status_code in [429, 500, 502, 503, 504]:
            raise requests.exceptions.RequestException("CNPJ.ws indisponível ou limitando requisições.")
            
        if response.status_code == 404:
            raise KeyError(f"CNPJ {cnpj_limpo} não encontrado na base da CNPJ.ws.")
        elif response.status_code != 200:
            raise requests.exceptions.HTTPError(f"Erro na CNPJ.ws: Status {response.status_code}")
            
        dados_ws = response.json()
        
        # Tradutor CNPJ.ws -> Padrão Farol.ai
        estabelecimento = dados_ws.get("estabelecimento", {})
        cnae_principal = estabelecimento.get("cnae_fiscal_principal", {})
        
        return {
            "cnpj": cnpj_limpo,
            "razao_social": dados_ws.get("razao_social"),
            "nome_fantasia": estabelecimento.get("nome_fantasia") or dados_ws.get("razao_social"),
            "cnae_fiscal": cnae_principal.get("codigo"),
            "cnae_fiscal_descricao": cnae_principal.get("descricao"),
            "capital_social": float(dados_ws.get("capital_social", 0.0)),
            "descricao_situacao_cadastral": estabelecimento.get("situacao_cadastral"),
            "data_inicio_atividade": estabelecimento.get("data_inicio_atividade"),
            "ddd_telefone_1": f"({estabelecimento.get('ddd1', '')}) {estabelecimento.get('telefone1', '')}" if estabelecimento.get('telefone1') else None,
            "ddd_telefone_2": f"({estabelecimento.get('ddd2', '')}) {estabelecimento.get('telefone2', '')}" if estabelecimento.get('telefone2') else None,
            "email": estabelecimento.get("email"),
            "porte": dados_ws.get("porte", {}).get("descricao"),
            "bairro": estabelecimento.get("bairro"),
            "numero": estabelecimento.get("numero"),
            "municipio": estabelecimento.get("municipio", {}).get("nome"),
            "logradouro": f"{estabelecimento.get('tipo_logradouro', '')} {estabelecimento.get('logradouro', '')}".strip(),
            "descricao_identificador_matriz_filial": estabelecimento.get("tipo"),
            "qsa": [
                {
                    "nome_socio": socio.get("nome"),
                    "qualificacao_socio": socio.get("qualificacao_socio", {}).get("descricao")
                } for socio in dados_ws.get("socios", [])
            ],
            "cnaes_secundarios": [
                {
                    "codigo": cnae.get("codigo"),
                    "descricao": cnae.get("descricao")
                } for cnae in estabelecimento.get("cnaes_fiscal_secundarios", [])
            ]
        }
        
    except (requests.exceptions.RequestException, Exception) as e:
        # --- PLANO B: Ativado se o Plano A falhar ---
        try:
            dados_brasilapi = buscar_dados_cnpj_brasilapi(cnpj_limpo)
            return dados_brasilapi
        except Exception as erro_fatal:
            # Se as duas APIs falharem miseravelmente, aí sim estouramos o erro pro app.py segurar a onda
            raise ConnectionError(f"Falha total em ambas as APIs (CNPJ.ws e BrasilAPI). Motivo: {erro_fatal}")