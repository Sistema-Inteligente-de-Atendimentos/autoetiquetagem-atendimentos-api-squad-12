from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import get_db
from app.models import Avaliacao, ChannelChat, ChannelChatProtocol
from app.schemas import CanalStat, DashboardStats, NotaStat


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
        .all()
    )
    # Agrupa por faixa inteira (7.5 cai no bucket 8). Soma para não perder notas.
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
