import json
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.config import get_db
from app.models import Avaliacao, ChannelChat, ChannelChatProtocol
from app.schemas import AcuraciaStats, CanalStat, DashboardStats, NotaStat


router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


def _parse_periodo(inicio: Optional[str], fim: Optional[str]):
    dt_inicio = None
    dt_fim = None
    try:
        if inicio:
            dt_inicio = datetime.fromisoformat(inicio)
    except Exception:
        dt_inicio = None
    try:
        if fim:
            dt_fim = datetime.fromisoformat(fim) + timedelta(days=1)
    except Exception:
        dt_fim = None
    return dt_inicio, dt_fim


def _aplicar_periodo(query, dt_inicio, dt_fim):
    if dt_inicio is not None:
        query = query.filter(ChannelChatProtocol.aberto_em >= dt_inicio)
    if dt_fim is not None:
        query = query.filter(ChannelChatProtocol.aberto_em < dt_fim)
    return query


@router.get("/stats", response_model=DashboardStats)
def get_dashboard_stats(
    db: Session = Depends(get_db),
    inicio: Optional[str] = Query(None),
    fim: Optional[str] = Query(None),
):
    dt_inicio, dt_fim = _parse_periodo(inicio, fim)

    volume_q = (
        db.query(ChannelChat.canal, func.count(ChannelChatProtocol.id))
        .join(ChannelChatProtocol, ChannelChatProtocol.channel_chat_id == ChannelChat.id)
    )
    volume_q = _aplicar_periodo(volume_q, dt_inicio, dt_fim).group_by(ChannelChat.canal)
    volume_por_canal = [
        CanalStat(canal=(canal or "Desconhecido"), total=int(total))
        for canal, total in volume_q.all()
    ]

    notas_q = (
        db.query(Avaliacao.nota, func.count(Avaliacao.id))
        .join(ChannelChatProtocol, ChannelChatProtocol.id == Avaliacao.protocolo_id)
        .filter(Avaliacao.nota.isnot(None))
    )
    notas_q = _aplicar_periodo(notas_q, dt_inicio, dt_fim).group_by(Avaliacao.nota)
    notas_map: dict = {}
    for nota, total in notas_q.all():
        bucket = max(1, min(10, int(round(float(nota)))))
        notas_map[bucket] = notas_map.get(bucket, 0) + int(total)
    distribuicao_notas = [
        NotaStat(nota=n, total=notas_map.get(n, 0)) for n in range(1, 11)
    ]

    media_q = (
        db.query(func.avg(Avaliacao.nota))
        .join(ChannelChatProtocol, ChannelChatProtocol.id == Avaliacao.protocolo_id)
    )
    media = _aplicar_periodo(media_q, dt_inicio, dt_fim).scalar()
    media_qualidade = round(float(media), 2) if media is not None else 0.0

    total_q = db.query(func.count(ChannelChatProtocol.id))
    total_atendimentos = _aplicar_periodo(total_q, dt_inicio, dt_fim).scalar() or 0

    exemplos_q = (
        db.query(func.count(Avaliacao.id))
        .join(ChannelChatProtocol, ChannelChatProtocol.id == Avaliacao.protocolo_id)
        .filter(Avaliacao.aprovado_como_exemplo.is_(True))
    )
    total_exemplos = _aplicar_periodo(exemplos_q, dt_inicio, dt_fim).scalar() or 0

    return DashboardStats(
        total_atendimentos=int(total_atendimentos),
        media_qualidade=media_qualidade,
        volume_por_canal=volume_por_canal,
        distribuicao_notas=distribuicao_notas,
        total_exemplos_aprovados=int(total_exemplos),
    )


@router.get("/acuracia", response_model=AcuraciaStats)
def get_acuracia(
    db: Session = Depends(get_db),
    inicio: Optional[str] = Query(None),
    fim: Optional[str] = Query(None),
):
    """Mede a acurácia da IA com base na revisão humana.

    Universo: avaliações revisadas por humano = aprovadas como exemplo
    (a IA acertou e foi endossada) OU corrigidas (json_raw_ia preenchido).
    A IA "acertou" quando o caso foi aprovado sem precisar de correção.
    """
    dt_inicio, dt_fim = _parse_periodo(inicio, fim)

    query = (
        db.query(Avaliacao)
        .join(ChannelChatProtocol, ChannelChatProtocol.id == Avaliacao.protocolo_id)
        .filter(
            or_(
                Avaliacao.aprovado_como_exemplo.is_(True),
                Avaliacao.json_raw_ia.isnot(None),
            )
        )
    )
    revisadas = _aplicar_periodo(query, dt_inicio, dt_fim).all()

    total = len(revisadas)
    corrigidos = 0
    erros_por_campo = {"categoria": 0, "sentimento": 0, "criticidade": 0}

    for av in revisadas:
        if not av.json_raw_ia:
            continue

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
