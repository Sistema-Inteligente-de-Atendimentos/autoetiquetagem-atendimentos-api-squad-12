import re
from typing import List, Optional, Tuple

ROLE_CLIENTE = "cliente"
ROLE_ATENDENTE = "atendente"


def _normalizar_para_role(nome_match: str, mapa_nomes: dict) -> str:
    chave = nome_match.strip().lower()
    if chave in {"cliente", "client"}:
        return ROLE_CLIENTE
    if chave in {"atendente", "agent", "atendimento", "suporte"}:
        return ROLE_ATENDENTE
    return mapa_nomes.get(chave, ROLE_CLIENTE)


def dividir_mensagens(
    texto: str,
    cliente_nome: Optional[str] = None,
    atendente_nome: Optional[str] = None,
) -> List[Tuple[str, str]]:
    """Divide um texto de chat em uma lista de (remetente, conteudo).

    Reconhece marcadores como:
      - "Cliente:" / "Atendente:" (case-insensitive)
      - Nomes próprios identificados pela IA, como "Marcelo:" ou "Júlia:"

    Se nenhum marcador for encontrado, retorna o texto inteiro como uma única
    mensagem com remetente "cliente".

    Args:
        texto: texto bruto do chat.
        cliente_nome: nome do cliente (opcional) para reconhecer marcador.
        atendente_nome: nome do atendente (opcional) para reconhecer marcador.

    Returns:
        Lista de tuplas (remetente, conteudo). Remetente é "cliente" ou "atendente".
    """
    texto = (texto or "").strip()
    if not texto:
        return []

    padroes = ["Cliente", "Atendente"]
    mapa_nomes: dict = {}

    if cliente_nome and cliente_nome.strip():
        cn = cliente_nome.strip()
        padroes.append(re.escape(cn))
        mapa_nomes[cn.lower()] = ROLE_CLIENTE
        primeiro_nome = cn.split()[0]
        if primeiro_nome.lower() != cn.lower():
            padroes.append(re.escape(primeiro_nome))
            mapa_nomes[primeiro_nome.lower()] = ROLE_CLIENTE

    if atendente_nome and atendente_nome.strip():
        an = atendente_nome.strip()
        padroes.append(re.escape(an))
        mapa_nomes[an.lower()] = ROLE_ATENDENTE
        primeiro_nome = an.split()[0]
        if primeiro_nome.lower() != an.lower():
            padroes.append(re.escape(primeiro_nome))
            mapa_nomes[primeiro_nome.lower()] = ROLE_ATENDENTE

    padroes_unicos = list(dict.fromkeys(padroes))

    regex = re.compile(
        r"(?:^|[\s.,;\n])(" + "|".join(padroes_unicos) + r")\s*:\s*",
        re.IGNORECASE,
    )

    matches = list(regex.finditer(texto))
    if not matches:
        return [(ROLE_CLIENTE, texto)]

    mensagens: List[Tuple[str, str]] = []

    primeiro_inicio_nome = matches[0].start(1)
    pre = texto[:primeiro_inicio_nome].strip()
    if pre:
        mensagens.append((ROLE_CLIENTE, pre))

    for i, m in enumerate(matches):
        nome_match = m.group(1)
        remetente = _normalizar_para_role(nome_match, mapa_nomes)

        inicio_conteudo = m.end()
        if i + 1 < len(matches):
            fim_conteudo = matches[i + 1].start(1)
        else:
            fim_conteudo = len(texto)

        conteudo = texto[inicio_conteudo:fim_conteudo].strip()
        if conteudo:
            mensagens.append((remetente, conteudo))

    if not mensagens:
        return [(ROLE_CLIENTE, texto)]

    return mensagens
