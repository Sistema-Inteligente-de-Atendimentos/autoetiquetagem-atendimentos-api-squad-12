import csv
import io
import json
import uuid
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
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
    AprovarExemploRequest,
    AvaliacaoOut,
    ChatOut,
    ClassifyResponse,
    MensagemOut,
    ProtocoloDetalheOut,
)
from app.routes.categorias import get_categorias_extras
from app.services.chat_parser import dividir_mensagens
from app.services.llm_service import buscar_exemplos_aprovados, classify_text


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


def _to_float(value, default: float = 0.0) -> float:
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return default


@router.post("/classify", response_model=ClassifyResponse)
def classify(req: ClassifyRequest, db: Session = Depends(get_db)):
    exemplos = buscar_exemplos_aprovados(db, limite=3, canal=req.canal)
    categorias_extras = get_categorias_extras(db)
    response = classify_text(req.text, exemplos=exemplos, categorias_extras=categorias_extras)

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

        mensagens_divididas = dividir_mensagens(
            req.text,
            cliente_nome=cliente_final,
            atendente_nome=atendente_final,
        )

        if not mensagens_divididas:
            mensagens_divididas = [(req.remetente or "cliente", req.text)]

        mensagens_criadas = []
        for remetente, conteudo in mensagens_divididas:
            msg = ChannelChatMessage(
                channel_chat_id=novo_chat.id,
                protocolo_id=novo_protocolo.id,
                remetente=remetente,
                conteudo=conteudo,
            )
            db.add(msg)
            mensagens_criadas.append(msg)
        db.flush()

        primeira_mensagem = mensagens_criadas[0]

        comentario = _to_text(data.get("resumo"))
        nota = _to_float(qualidade.get("score_final", 0))

        nova_avaliacao = Avaliacao(
            protocolo_id=novo_protocolo.id,
            nota=nota,
            comentario=comentario,
            json_raw=json.dumps(data, ensure_ascii=False),
        )
        db.add(nova_avaliacao)
        db.flush()

        db.commit()

        usage_obj = response.get("usage")
        usage_dict = None
        if usage_obj is not None:
            if hasattr(usage_obj, "model_dump"):
                usage_dict = usage_obj.model_dump()
            elif hasattr(usage_obj, "dict"):
                usage_dict = usage_obj.dict()
            elif isinstance(usage_obj, dict):
                usage_dict = usage_obj

        return ClassifyResponse(
            status="sucesso",
            chat_id=novo_chat.id,
            protocolo_id=novo_protocolo.id,
            protocolo_numero=novo_protocolo.numero,
            mensagem_id=primeira_mensagem.id,
            avaliacao_id=nova_avaliacao.id,
            data=data,
            usage=usage_dict,
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

        categoria = None
        sentimento = None
        criticidade = None
        if avaliacao and avaliacao.json_raw:
            try:
                dados_ia = json.loads(avaliacao.json_raw)
                categoria = dados_ia.get("categoria")
                sentimento = dados_ia.get("sentimento")
                criticidade = dados_ia.get("criticidade")
            except Exception:
                pass

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
                "categoria": categoria,
                "sentimento": sentimento,
                "criticidade": criticidade,
                "aprovado_como_exemplo": bool(avaliacao.aprovado_como_exemplo) if avaliacao else False,
            }
        )
    return resultado


@router.get("/atendimentos/export")
def export_atendimentos(db: Session = Depends(get_db)):
    protocolos = (
        db.query(ChannelChatProtocol)
        .options(
            joinedload(ChannelChatProtocol.chat),
            joinedload(ChannelChatProtocol.avaliacoes),
        )
        .order_by(ChannelChatProtocol.aberto_em.desc())
        .all()
    )

    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";")
    writer.writerow([
        "protocolo_id", "numero", "cliente", "atendente", "canal",
        "aberto_em", "nota", "aprovado_como_exemplo", "comentario",
    ])

    for p in protocolos:
        avaliacao = p.avaliacoes[0] if p.avaliacoes else None
        writer.writerow([
            p.id,
            p.numero,
            (p.chat.cliente_nome if p.chat else "") or "",
            (p.chat.atendente_nome if p.chat else "") or "",
            (p.chat.canal if p.chat else "") or "",
            p.aberto_em.isoformat() if p.aberto_em else "",
            avaliacao.nota if avaliacao and avaliacao.nota is not None else "",
            "Sim" if (avaliacao and avaliacao.aprovado_como_exemplo) else "Não",
            (avaliacao.comentario if avaliacao else "") or "",
        ])

    buffer.seek(0)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    headers = {
        "Content-Disposition": f'attachment; filename="atendimentos_{timestamp}.csv"'
    }
    conteudo = "﻿" + buffer.getvalue()
    return StreamingResponse(
        iter([conteudo]),
        media_type="text/csv; charset=utf-8",
        headers=headers,
    )


@router.post("/atendimentos/{protocolo_id}/aprovar-exemplo")
def aprovar_como_exemplo(
    protocolo_id: int,
    req: AprovarExemploRequest,
    db: Session = Depends(get_db),
):
    avaliacao = (
        db.query(Avaliacao)
        .filter(Avaliacao.protocolo_id == protocolo_id)
        .first()
    )
    if not avaliacao:
        raise HTTPException(status_code=404, detail="Avaliação não encontrada para este protocolo")

    avaliacao.aprovado_como_exemplo = True
    avaliacao.aprovado_por = req.revisor.strip() or "Anônimo"
    avaliacao.aprovado_em = datetime.now(timezone.utc)
    avaliacao.observacao_aprovacao = (req.observacao or "").strip() or None

    db.commit()
    db.refresh(avaliacao)

    return {
        "status": "aprovado",
        "avaliacao_id": avaliacao.id,
        "aprovado_por": avaliacao.aprovado_por,
        "aprovado_em": avaliacao.aprovado_em,
    }


@router.post("/atendimentos/{protocolo_id}/remover-exemplo")
def remover_exemplo(protocolo_id: int, db: Session = Depends(get_db)):
    avaliacao = (
        db.query(Avaliacao)
        .filter(Avaliacao.protocolo_id == protocolo_id)
        .first()
    )
    if not avaliacao:
        raise HTTPException(status_code=404, detail="Avaliação não encontrada")

    avaliacao.aprovado_como_exemplo = False
    avaliacao.aprovado_por = None
    avaliacao.aprovado_em = None
    avaliacao.observacao_aprovacao = None

    db.commit()

    return {"status": "removido", "avaliacao_id": avaliacao.id}


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
        key=lambda m: m.id,
    )

    avaliacao = protocolo.avaliacoes[0] if protocolo.avaliacoes else None

    classificacao = None
    if avaliacao and avaliacao.json_raw:
        try:
            classificacao = json.loads(avaliacao.json_raw)
        except Exception:
            classificacao = None

    return ProtocoloDetalheOut(
        id=protocolo.id,
        numero=protocolo.numero,
        aberto_em=protocolo.aberto_em,
        fechado_em=protocolo.fechado_em,
        chat=ChatOut.model_validate(protocolo.chat),
        mensagens=[MensagemOut.model_validate(m) for m in mensagens_ordenadas],
        avaliacao=AvaliacaoOut.model_validate(avaliacao) if avaliacao else None,
        classificacao=classificacao,
    )
