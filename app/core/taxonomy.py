import unicodedata
from typing import Dict, List

CATEGORIAS: List[str] = [
    "Financeiro",
    "Técnico",
    "Comercial",
    "Logística",
    "Reclamação",
    "Elogio",
    "Cancelamento",
    "Dúvida",
    "Outros",
]

SENTIMENTOS: List[str] = ["Positivo", "Neutro", "Negativo"]

CRITICIDADES: List[str] = ["Baixa", "Média", "Alta"]

CATEGORIA_PADRAO = "Outros"
SENTIMENTO_PADRAO = "Neutro"
CRITICIDADE_PADRAO = "Média"

PESOS_QUALIDADE: Dict[str, float] = {
    "empatia": 0.25,
    "clareza": 0.25,
    "objetividade": 0.25,
    "resolutividade": 0.25,
}


def _normalizar(texto: str) -> str:
    if texto is None:
        return ""
    texto = str(texto).strip().lower()
    nfkd = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _casar_opcao(valor: str, opcoes: List[str], padrao: str) -> str:
    alvo = _normalizar(valor)
    if not alvo:
        return padrao
    mapa = {_normalizar(op): op for op in opcoes}
    if alvo in mapa:
        return mapa[alvo]
    for chave_norm, oficial in mapa.items():
        if chave_norm and (chave_norm in alvo or alvo in chave_norm):
            return oficial
    return padrao


def _to_num(valor, default: float = 0.0) -> float:
    try:
        return float(valor)
    except (TypeError, ValueError):
        return default


def calcular_score_final(qualidade: dict) -> float:
    qualidade = qualidade or {}
    total = 0.0
    soma_pesos = 0.0
    for criterio, peso in PESOS_QUALIDADE.items():
        nota = _to_num(qualidade.get(criterio))
        total += nota * peso
        soma_pesos += peso
    if soma_pesos == 0:
        return 0.0
    return round(total / soma_pesos, 2)


def validar_classificacao(data: dict) -> dict:
    data = data or {}

    data["categoria"] = _casar_opcao(data.get("categoria"), CATEGORIAS, CATEGORIA_PADRAO)
    data["sentimento"] = _casar_opcao(data.get("sentimento"), SENTIMENTOS, SENTIMENTO_PADRAO)
    data["criticidade"] = _casar_opcao(data.get("criticidade"), CRITICIDADES, CRITICIDADE_PADRAO)

    qualidade = data.get("qualidade") or {}
    qualidade["score_final"] = calcular_score_final(qualidade)
    data["qualidade"] = qualidade

    return data
