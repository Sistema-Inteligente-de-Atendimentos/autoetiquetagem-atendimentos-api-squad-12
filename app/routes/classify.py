import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload

from app.config import get_db
from app.models import (
    Avaliacao,
    ChannelChat,
    ChannelChatMessage,
    ChannelChatProtocol,
)
from app.schemas import (
    AvaliacaoOut,
    ChatOut,
    ClassifyResponse,
    MensagemOut,
    ProtocoloDetalheOut,
)
from app.services.llm_service import classify_text


router = APIRouter(tags=["Atendimentos"])


class ClassifyRequest(BaseModel):
    text: str
    canal: str = "Web"
    cliente_nome: str | None = None
    atendente_nome: str | None = None
    remetente: str = "cliente"


def _to_text(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, list):
        return " | ".join(
            item if isinstance(item, str) else str(item) for item in value
        )
    if isinstance(value, dict):
        return str(value)
    return str(value)


def _to_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


@router.post("/classify", response_model=ClassifyResponse)
def classify(req: ClassifyRequest, db: Session = Depends(get_db)):
    response = classify_text(req.text)

    if "error" in response:
        raise HTTPException(status_code=500, detail=response["error"])

    data = response.get("data", {}) or {}
    qualidade = data.get("qualidade") or {}

    cliente_final = req.cliente_nome or (data.get("cliente_nome") or None)
    atendente_final = req.atendente_nome or (data.get("atendente_nome") or None)

    try:
        novo_chat = ChannelChat(
            cliente_nome=cliente_final,
            atendente_nome=atendente_final,
            canal=req.canal,
        )
        db.add(novo_chat)
        db.flush()

        novo_protocolo = ChannelChatProtocol(
            channel_chat_id=novo_chat.id,
            numero=str(uuid.uuid4()),
        )
        db.add(novo_protocolo)
        db.flush()

        nova_mensagem = ChannelChatMessage(
            channel_chat_id=novo_chat.id,
            protocolo_id=novo_protocolo.id,
            remetente=req.remetente,
            conteudo=req.text,
        )
        db.add(nova_mensagem)
        db.flush()

        comentario = _to_text(data.get("resumo"))
        nota = _to_int(qualidade.get("score_final", qualidade.get("nota", 0)))

        nova_avaliacao = Avaliacao(
            protocolo_id=novo_protocolo.id,
            nota=nota,
            comentario=comentario,
        )
        db.add(nova_avaliacao)
        db.flush()

        db.commit()

        return ClassifyResponse(
            status="sucesso",
            chat_id=novo_chat.id,
            protocolo_id=novo_protocolo.id,
            protocolo_numero=novo_protocolo.numero,
            mensagem_id=nova_mensagem.id,
            avaliacao_id=nova_avaliacao.id,
            data=data,
        )

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/atendimentos")
def list_atendimentos(db: Session = Depends(get_db)):
    protocolos = (
        db.query(ChannelChatProtocol)
        .options(
            joinedload(ChannelChatProtocol.chat),
            joinedload(ChannelChatProtocol.avaliacoes),
        )
        .order_by(ChannelChatProtocol.aberto_em.desc())
        .all()
    )

    resultado = []
    for p in protocolos:
        avaliacao = p.avaliacoes[0] if p.avaliacoes else None
        resultado.append(
            {
                "protocolo_id": p.id,
                "numero": p.numero,
                "cliente_nome": p.chat.cliente_nome if p.chat else None,
                "atendente_nome": p.chat.atendente_nome if p.chat else None,
                "canal": p.chat.canal if p.chat else None,
                "aberto_em": p.aberto_em,
                "fechado_em": p.fechado_em,
                "nota": avaliacao.nota if avaliacao else None,
                "comentario": avaliacao.comentario if avaliacao else None,
            }
        )
    return resultado


@router.get("/atendimentos/{protocolo_id}", response_model=ProtocoloDetalheOut)
def get_atendimento_detalhe(protocolo_id: int, db: Session = Depends(get_db)):
    protocolo = (
        db.query(ChannelChatProtocol)
        .options(
            joinedload(ChannelChatProtocol.chat),
            joinedload(ChannelChatProtocol.mensagens),
            joinedload(ChannelChatProtocol.avaliacoes),
        )
        .filter(ChannelChatProtocol.id == protocolo_id)
        .first()
    )

    if not protocolo:
        raise HTTPException(status_code=404, detail="Protocolo não encontrado")

    mensagens_ordenadas = sorted(
        protocolo.mensagens,
        key=lambda m: m.enviada_em or m.id,
    )

    return ProtocoloDetalheOut(
        id=protocolo.id,
        numero=protocolo.numero,
        aberto_em=protocolo.aberto_em,
        fechado_em=protocolo.fechado_em,
        chat=ChatOut.model_validate(protocolo.chat),
        mensagens=[MensagemOut.model_validate(m) for m in mensagens_ordenadas],
        avaliacao=(
            AvaliacaoOut.model_validate(protocolo.avaliacoes[0])
            if protocolo.avaliacoes
            else None
        ),
    )
