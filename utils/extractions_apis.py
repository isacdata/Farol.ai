import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

def _criar_sessao_segura():
    """
    Cria uma sessão HTTP que finge ser um navegador real para evitar
    bloqueios de segurança (Cloudflare/WAF) comuns em APIs públicas.
    """
    session = requests.Session()
    retry = Retry(total=1, backoff_factor=0.5, status_forcelist=[429, 500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    # Disfarce de Navegador:
    session.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
    return session

def _buscar_receitaws(cnpj: str, session: requests.Session) -> dict:
    url = f"https://receitaws.com.br/v1/cnpj/{cnpj}"
    resp = session.get(url, timeout=10)
    if resp.status_code != 200:
        raise ValueError(f"Status {resp.status_code}")
    
    data = resp.json()
    if data.get("status") == "ERROR":
        raise ValueError(data.get("message"))
    
    # Conversão de Data DD/MM/YYYY para YYYY-MM-DD
    dt_abertura = data.get("abertura", "")
    if "/" in dt_abertura:
        dt_abertura = "-".join(reversed(dt_abertura.split("/")))
        
    return {
        "cnpj": cnpj,
        "razao_social": data.get("nome"),
        "nome_fantasia": data.get("fantasia") or data.get("nome"),
        "cnae_fiscal": data.get("atividade_principal", [{}])[0].get("code", "").replace(".", "").replace("-", ""),
        "cnae_fiscal_descricao": data.get("atividade_principal", [{}])[0].get("text"),
        "capital_social": float(data.get("capital_social", 0.0) if data.get("capital_social") else 0.0),
        "descricao_situacao_cadastral": data.get("situacao"),
        "data_inicio_atividade": dt_abertura,
        "ddd_telefone_1": data.get("telefone"),
        "ddd_telefone_2": None,
        "email": data.get("email"),
        "porte": data.get("porte"),
        "bairro": data.get("bairro"),
        "numero": data.get("numero"),
        "municipio": data.get("municipio"),
        "logradouro": data.get("logradouro"),
        "descricao_identificador_matriz_filial": data.get("tipo"),
        # CAPTURANDO A FAIXA ETÁRIA AQUI:
        "qsa": [{"nome_socio": s.get("nome"), "qualificacao_socio": s.get("qual"), "faixa_etaria": s.get("faixa_etaria", "Não informada")} for s in data.get("qsa", [])],
        "cnaes_secundarios": [{"codigo": c.get("code", "").replace(".", "").replace("-", ""), "descricao": c.get("text")} for c in data.get("atividades_secundarias", [])],
        "fonte": "ReceitaWS"
    }

def _buscar_brasilapi(cnpj: str, session: requests.Session) -> dict:
    url = f"https://brasilapi.com.br/api/cnpj/v1/{cnpj}"
    resp = session.get(url, timeout=10)
    if resp.status_code != 200:
        raise ValueError(f"Status {resp.status_code}")
        
    data = resp.json()
    return {
        "cnpj": cnpj,
        "razao_social": data.get("razao_social"),
        "nome_fantasia": data.get("nome_fantasia") or data.get("razao_social"),
        "cnae_fiscal": data.get("cnae_fiscal"),
        "cnae_fiscal_descricao": data.get("cnae_fiscal_descricao"),
        "capital_social": float(data.get("capital_social", 0.0) if data.get("capital_social") else 0.0),
        "descricao_situacao_cadastral": data.get("descricao_situacao_cadastral"),
        "data_inicio_atividade": data.get("data_inicio_atividade"),
        "ddd_telefone_1": f"({data.get('ddd_telefone_1', '')}) {data.get('telefone_1', '')}".strip() if data.get('telefone_1') else None,
        "ddd_telefone_2": f"({data.get('ddd_telefone_2', '')}) {data.get('telefone_2', '')}".strip() if data.get('telefone_2') else None,
        "email": data.get("email"),
        "porte": data.get("porte"),
        "bairro": data.get("bairro"),
        "numero": data.get("numero"),
        "municipio": data.get("municipio"),
        "logradouro": data.get("logradouro"),
        "descricao_identificador_matriz_filial": data.get("descricao_identificador_matriz_filial"),
        # CAPTURANDO A FAIXA ETÁRIA AQUI:
        "qsa": [{"nome_socio": s.get("nome_socio"), "qualificacao_socio": s.get("qualificacao_socio"), "faixa_etaria": s.get("faixa_etaria", "Não informada")} for s in data.get("qsa", [])],
        "cnaes_secundarios": [{"codigo": c.get("codigo"), "descricao": c.get("descricao")} for c in data.get("cnaes_secundarios", [])],
        "fonte": "BrasilAPI"
    }

def _buscar_cnpjws(cnpj: str, session: requests.Session) -> dict:
    url = f"https://publica.cnpj.ws/cnpj/{cnpj}"
    resp = session.get(url, timeout=10)
    if resp.status_code != 200:
        raise ValueError(f"Status {resp.status_code}")
        
    data = resp.json()
    est = data.get("estabelecimento", {})
    cnae = est.get("cnae_fiscal_principal", {})
    
    # Valida porte com segurança
    porte_bruto = data.get("porte")
    porte_str = porte_bruto.get("descricao") if isinstance(porte_bruto, dict) else porte_bruto

    return {
        "cnpj": cnpj,
        "razao_social": data.get("razao_social"),
        "nome_fantasia": est.get("nome_fantasia") or data.get("razao_social"),
        "cnae_fiscal": cnae.get("codigo"),
        "cnae_fiscal_descricao": cnae.get("descricao"),
        "capital_social": float(data.get("capital_social", 0.0) if data.get("capital_social") else 0.0),
        "descricao_situacao_cadastral": est.get("situacao_cadastral"),
        "data_inicio_atividade": est.get("data_inicio_atividade"),
        "ddd_telefone_1": f"({est.get('ddd1', '')}) {est.get('telefone1', '')}".strip() if est.get('telefone1') else None,
        "ddd_telefone_2": f"({est.get('ddd2', '')}) {est.get('telefone2', '')}".strip() if est.get('telefone2') else None,
        "email": est.get("email"),
        "porte": porte_str,
        "bairro": est.get("bairro"),
        "numero": est.get("numero"),
        "municipio": est.get("municipio", {}).get("nome") if isinstance(est.get("municipio"), dict) else est.get("municipio"),
        "logradouro": f"{est.get('tipo_logradouro', '')} {est.get('logradouro', '')}".strip(),
        "descricao_identificador_matriz_filial": est.get("tipo"),
        # CAPTURANDO A FAIXA ETÁRIA AQUI (Exatamente do JSON que enviou):
        "qsa": [{"nome_socio": s.get("nome"), "qualificacao_socio": s.get("qualificacao_socio", {}).get("descricao"), "faixa_etaria": s.get("faixa_etaria", "Não informada")} for s in data.get("socios", [])],
        "cnaes_secundarios": [{"codigo": c.get("codigo"), "descricao": c.get("descricao")} for c in est.get("cnaes_fiscal_secundarios", [])],
        "fonte": "CNPJ.ws"
    }

def buscar_dados_cnpj(cnpj_limpo: str) -> dict:
    """
    Função mestra: Tenta 3 bases de dados diferentes em sequência. 
    Garante o retorno do CNPJ independentemente de instabilidades.
    """
    if len(cnpj_limpo) != 14:
        raise ValueError("O CNPJ deve conter exatamente 14 dígitos.")
        
    session = _criar_sessao_segura()
    erros = []
    
    # 1. Tenta CNPJ.ws
    try:
        return _buscar_cnpjws(cnpj_limpo, session)
    except Exception as e:
        erros.append(f"CNPJ.ws falhou: {str(e)}")
        
    # 2. Tenta BrasilAPI
    try:
        return _buscar_brasilapi(cnpj_limpo, session)
    except Exception as e:
        erros.append(f"BrasilAPI falhou: {str(e)}")
        
    # 3. Tenta ReceitaWS
    try:
        return _buscar_receitaws(cnpj_limpo, session)
    except Exception as e:
        erros.append(f"ReceitaWS falhou: {str(e)}")
        
    raise ConnectionError(f"Bloqueio total nas 3 APIs públicas. Erros: {' | '.join(erros)}")