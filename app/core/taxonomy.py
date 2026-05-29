"""Taxonomia fechada e regras de pontuação do sistema de classificação.

Edite as listas abaixo para ajustar as categorias/valores permitidos.
A IA é instruída a escolher dentro dessas opções e a saída é normalizada
por validar_classificacao().
"""
import unicodedata
from typing import Dict, List

# ---------------------------------------------------------------------------
# Taxonomia fechada
# ---------------------------------------------------------------------------
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

# Categoria usada quando a IA retorna algo fora da lista
CATEGORIA_PADRAO = "Outros"
SENTIMENTO_PADRAO = "Neutro"
CRITICIDADE_PADRAO = "Média"

# ---------------------------------------------------------------------------
# Pesos do score final (devem somar 1.0)
# ---------------------------------------------------------------------------
PESOS_QUALIDADE: Dict[str, float] = {
    "empatia": 0.25,
    "clareza": 0.25,
    "objetividade": 0.25,
    "resolutividade": 0.25,
}


def _normalizar(texto: str) -> str:
    """Remove acentos, espaços e deixa minúsculo para comparação tolerante."""
    if texto is None:
        return ""
    texto = str(texto).strip().lower()
    nfkd = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _casar_opcao(valor: str, opcoes: List[str], padrao: str) -> str:
    """Mapeia um valor livre para a opção oficial mais próxima (ou o padrão)."""
    alvo = _normalizar(valor)
    if not alvo:
        return padrao
    mapa = {_normalizar(op): op for op in opcoes}
    # match exato (ignorando acento/caixa)
    if alvo in mapa:
        return mapa[alvo]
    # match parcial: a opção aparece no valor ou vice-versa
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
    """Calcula o score final como média ponderada dos 4 critérios.

    Usa os PESOS_QUALIDADE definidos acima. Retorna um float (0-10)
    arredondado em 2 casas. Não confia no score_final que a IA enviou.
    """
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
    """Normaliza a saída da IA contra a taxonomia fechada.

    - categoria: força uma das CATEGORIAS (ou 'Outros')
    - sentimento: força um dos SENTIMENTOS (ou 'Neutro')
    - criticidade: força uma das CRITICIDADES (ou 'Média')
    - qualidade.score_final: recalculado pela média ponderada

    Retorna o mesmo dict modificado (in-place) por conveniência.
    """
    data = data or {}

    data["categoria"] = _casar_opcao(data.get("categoria"), CATEGORIAS, CATEGORIA_PADRAO)
    data["sentimento"] = _casar_opcao(data.get("sentimento"), SENTIMENTOS, SENTIMENTO_PADRAO)
    data["criticidade"] = _casar_opcao(data.get("criticidade"), CRITICIDADES, CRITICIDADE_PADRAO)

    qualidade = data.get("qualidade") or {}
    qualidade["score_final"] = calcular_score_final(qualidade)
    data["qualidade"] = qualidade

    return data
