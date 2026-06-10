import json
import time
from typing import Optional

from sqlalchemy.orm import Session, joinedload

from app.models import Avaliacao, ChannelChatProtocol, GoldenDatasetItem, GoldenDatasetRun
from app.routes.categorias import get_categorias_extras
from app.services.llm_service import buscar_exemplos_aprovados, classify_text

SCORE_TOLERANCIA = 1.0
DELAY_ENTRE_CHAMADAS = 0.5  # segundos, evita rajada de chamadas ao Groq


def montar_texto_avaliacao(avaliacao: Avaliacao) -> str:
    protocolo = avaliacao.protocolo
    mensagens = sorted(protocolo.mensagens, key=lambda m: m.id) if protocolo else []
    return "\n".join(
        f"{(m.remetente or 'cliente').capitalize()}: {m.conteudo}" for m in mensagens
    )


def _num(v) -> Optional[float]:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def comparar_resultado(esperado: dict, obtido: dict) -> dict:
    def _str_eq(a, b):
        return str(a or "").strip().lower() == str(b or "").strip().lower()

    qualidade_obtido = obtido.get("qualidade") or {}
    score_esperado = _num(esperado.get("score_final"))
    score_obtido = _num(qualidade_obtido.get("score_final"))

    return {
        "categoria_esperada": esperado.get("categoria"),
        "categoria_obtida": obtido.get("categoria"),
        "acerto_categoria": _str_eq(esperado.get("categoria"), obtido.get("categoria")),
        "sentimento_esperado": esperado.get("sentimento"),
        "sentimento_obtido": obtido.get("sentimento"),
        "acerto_sentimento": _str_eq(esperado.get("sentimento"), obtido.get("sentimento")),
        "criticidade_esperada": esperado.get("criticidade"),
        "criticidade_obtida": obtido.get("criticidade"),
        "acerto_criticidade": _str_eq(esperado.get("criticidade"), obtido.get("criticidade")),
        "score_esperado": score_esperado,
        "score_obtido": score_obtido,
        "acerto_score": (
            score_esperado is not None
            and score_obtido is not None
            and abs(score_esperado - score_obtido) <= SCORE_TOLERANCIA
        ),
    }


def executar_run(db: Session) -> GoldenDatasetRun:
    itens = (
        db.query(GoldenDatasetItem)
        .options(
            joinedload(GoldenDatasetItem.avaliacao)
            .joinedload(Avaliacao.protocolo)
            .joinedload(ChannelChatProtocol.chat)
        )
        .all()
    )

    categorias_extras = get_categorias_extras(db)

    detalhes = []
    acertos_categoria = acertos_sentimento = acertos_criticidade = 0

    for idx, item in enumerate(itens):
        esperado = {
            "categoria": item.categoria_esperada,
            "sentimento": item.sentimento_esperado,
            "criticidade": item.criticidade_esperada,
            "score_final": item.score_esperado,
        }

        protocolo = item.avaliacao.protocolo if item.avaliacao else None
        canal = protocolo.chat.canal if protocolo and protocolo.chat else None

        exemplos = buscar_exemplos_aprovados(db, limite=3, canal=canal)
        resultado = classify_text(item.texto, exemplos=exemplos, categorias_extras=categorias_extras)

        obtido = {} if "error" in resultado else (resultado.get("data", {}) or {})
        comparacao = comparar_resultado(esperado, obtido)
        if "error" in resultado:
            comparacao["erro"] = resultado.get("error")

        if comparacao["acerto_categoria"]:
            acertos_categoria += 1
        if comparacao["acerto_sentimento"]:
            acertos_sentimento += 1
        if comparacao["acerto_criticidade"]:
            acertos_criticidade += 1

        detalhes.append({
            "golden_item_id": item.id,
            "avaliacao_id": item.avaliacao_id,
            "protocolo_id": protocolo.id if protocolo else None,
            "numero": protocolo.numero if protocolo else None,
            **comparacao,
        })

        if idx < len(itens) - 1:
            time.sleep(DELAY_ENTRE_CHAMADAS)

    total = len(itens)
    # acurácia geral = média das taxas de acerto de categoria/sentimento/criticidade
    acuracia_geral = (
        round((acertos_categoria + acertos_sentimento + acertos_criticidade) / (3 * total), 4)
        if total > 0 else 0.0
    )

    run = GoldenDatasetRun(
        total_casos=total,
        acertos_categoria=acertos_categoria,
        acertos_sentimento=acertos_sentimento,
        acertos_criticidade=acertos_criticidade,
        acuracia_geral=acuracia_geral,
        detalhes_json=json.dumps(detalhes, ensure_ascii=False),
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run
