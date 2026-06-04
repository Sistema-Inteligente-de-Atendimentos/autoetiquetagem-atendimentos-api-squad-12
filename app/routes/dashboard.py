import json

from fastapi import APIRouter, Depends
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.config import get_db
from app.models import Avaliacao, ChannelChat, ChannelChatProtocol
from app.schemas import AcuraciaStats, CanalStat, DashboardStats, NotaStat


router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/stats", response_model=DashboardStats)
def get_dashboard_stats(db: Session = Depends(get_db)):
    volume_canal_rows = (
        db.query(ChannelChat.canal, func.count(ChannelChatProtocol.id))
        .join(ChannelChatProtocol, ChannelChatProtocol.channel_chat_id == ChannelChat.id)
        .group_by(ChannelChat.canal)
        .all()
    )
    volume_por_canal = [
        CanalStat(canal=(canal or "Desconhecido"), total=int(total))
        for canal, total in volume_canal_rows
    ]

    notas_rows = (
        db.query(Avaliacao.nota, func.count(Avaliacao.id))
        .filter(Avaliacao.nota.isnot(None))
        .group_by(Avaliacao.nota)
        .all()
    )
    notas_map: dict = {}
    for nota, total in notas_rows:
        bucket = max(1, min(10, int(round(float(nota)))))
        notas_map[bucket] = notas_map.get(bucket, 0) + int(total)
    distribuicao_notas = [
        NotaStat(nota=n, total=notas_map.get(n, 0)) for n in range(1, 11)
    ]

    media = db.query(func.avg(Avaliacao.nota)).scalar()
    media_qualidade = round(float(media), 2) if media is not None else 0.0

    total_atendimentos = db.query(func.count(ChannelChatProtocol.id)).scalar() or 0

    total_exemplos = db.query(func.count(Avaliacao.id)).filter(
        Avaliacao.aprovado_como_exemplo.is_(True)
    ).scalar() or 0

    return DashboardStats(
        total_atendimentos=int(total_atendimentos),
        media_qualidade=media_qualidade,
        volume_por_canal=volume_por_canal,
        distribuicao_notas=distribuicao_notas,
        total_exemplos_aprovados=int(total_exemplos),
    )


@router.get("/acuracia", response_model=AcuraciaStats)
def get_acuracia(db: Session = Depends(get_db)):
    """Mede a acurácia da IA com base na revisão humana.

    Universo: avaliações revisadas por humano = aprovadas como exemplo
    (a IA acertou e foi endossada) OU corrigidas (json_raw_ia preenchido).
    A IA "acertou" quando o caso foi aprovado sem precisar de correção.
    """
    revisadas = (
        db.query(Avaliacao)
        .filter(
            or_(
                Avaliacao.aprovado_como_exemplo.is_(True),
                Avaliacao.json_raw_ia.isnot(None),
            )
        )
        .all()
    )

    total = len(revisadas)
    corrigidos = 0
    erros_por_campo = {"categoria": 0, "sentimento": 0, "criticidade": 0}

    for av in revisadas:
        if not av.json_raw_ia:
            continue  # aprovada sem correção → IA acertou

        corrigidos += 1
        try:
            ia = json.loads(av.json_raw_ia)
            final = json.loads(av.json_raw or "{}")
        except Exception:
            continue

        for campo in erros_por_campo:
            if (ia.get(campo) or "") != (final.get(campo) or ""):
                erros_por_campo[campo] += 1

    acertos = total - corrigidos
    acuracia = round(acertos / total, 4) if total > 0 else 0.0

    return AcuraciaStats(
        total_revisados=total,
        acertos=acertos,
        corrigidos=corrigidos,
        acuracia=acuracia,
        erros_por_campo=erros_por_campo,
    )
