import json
import os
import uuid
from datetime import datetime, timezone
from typing import List, Optional

import pandas as pd
from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.config import SessionLocal, get_db
from app.models import (
    Avaliacao,
    ChannelChat,
    ChannelChatMessage,
    ChannelChatProtocol,
    CronEstado,
)
from app.services.chat_parser import dividir_mensagens
from app.services.llm_service import buscar_exemplos_aprovados, classify_text


router = APIRouter(prefix="/cron", tags=["Cron"])

COLUNAS_TEXTO = ["texto", "atendimento", "mensagem", "conteudo", "text", "message"]


def _normalizar(nome: str) -> str:
    return str(nome).replace("﻿", "").strip().lower()


def _encontrar_coluna_texto(colunas: List[str]) -> Optional[str]:
    colunas_lower = {_normalizar(c): c for c in colunas}
    for nome in COLUNAS_TEXTO:
        if nome in colunas_lower:
            return colunas_lower[nome]
    return None


def _valor_ou_none(row, colunas_lower, chave) -> Optional[str]:
    nome_real = colunas_lower.get(_normalizar(chave))
    if nome_real is None:
        return None
    val = row.get(nome_real)
    if pd.isna(val):
        return None
    return str(val).strip() or None


def _to_text(value) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, list):
        return " | ".join(item if isinstance(item, str) else str(item) for item in value)
    if isinstance(value, dict):
        return str(value)
    return str(value)


def _to_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _montar_url_csv() -> Optional[str]:
    url = os.getenv("GOOGLE_SHEET_CSV_URL")
    if url:
        return url
    sheet_id = os.getenv("GOOGLE_SHEET_ID")
    if sheet_id:
        gid = os.getenv("GOOGLE_SHEET_GID", "0")
        return f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"
    return None


def _ler_planilha(url: str) -> pd.DataFrame:
    df = pd.read_csv(url, encoding="utf-8-sig")
    df.columns = [str(c).replace("﻿", "").strip() for c in df.columns]
    return df


def _processar_linha(db: Session, texto: str, canal: str, cliente, atendente) -> None:
    exemplos = buscar_exemplos_aprovados(db, limite=3, canal=canal)
    response = classify_text(texto, exemplos=exemplos)

    if "error" in response:
        raise ValueError(response["error"])

    data = response.get("data", {}) or {}
    qualidade = data.get("qualidade") or {}

    cliente_final = cliente or (data.get("cliente_nome") or None)
    atendente_final = atendente or (data.get("atendente_nome") or None)

    novo_chat = ChannelChat(
        cliente_nome=cliente_final,
        atendente_nome=atendente_final,
        canal=canal,
    )
    db.add(novo_chat)
    db.flush()

    novo_protocolo = ChannelChatProtocol(
        channel_chat_id=novo_chat.id,
        numero=str(uuid.uuid4()),
    )
    db.add(novo_protocolo)
    db.flush()

    mensagens = dividir_mensagens(texto, cliente_nome=cliente_final, atendente_nome=atendente_final)
    if not mensagens:
        mensagens = [("cliente", texto)]
    for remetente, conteudo in mensagens:
        db.add(ChannelChatMessage(
            channel_chat_id=novo_chat.id,
            protocolo_id=novo_protocolo.id,
            remetente=remetente,
            conteudo=conteudo,
        ))
    db.flush()

    db.add(Avaliacao(
        protocolo_id=novo_protocolo.id,
        nota=_to_int(qualidade.get("score_final", qualidade.get("nota", 0))),
        comentario=_to_text(data.get("resumo")),
        json_raw=json.dumps(data, ensure_ascii=False),
    ))


def _executar_analise() -> None:
    url = _montar_url_csv()
    if not url:
        return

    db = SessionLocal()
    try:
        df = _ler_planilha(url)
        if df.empty:
            return

        col_texto = _encontrar_coluna_texto(list(df.columns))
        if col_texto is None:
            return

        colunas_lower = {_normalizar(c): c for c in df.columns}

        estado = db.query(CronEstado).filter(CronEstado.fonte == url).first()
        if estado is None:
            estado = CronEstado(fonte=url, ultima_linha=0, total_processados=0)
            db.add(estado)
            db.flush()

        inicio = estado.ultima_linha
        total_linhas = len(df)
        if inicio >= total_linhas:
            estado.atualizado_em = datetime.now(timezone.utc)
            db.commit()
            return

        novas = df.iloc[inicio:]
        processados = 0

        for _, row in novas.iterrows():
            texto = row.get(col_texto)
            if pd.isna(texto) or not str(texto).strip():
                continue
            texto = str(texto).strip()
            canal = _valor_ou_none(row, colunas_lower, "canal") or "Planilha"
            cliente = _valor_ou_none(row, colunas_lower, "cliente") or _valor_ou_none(row, colunas_lower, "cliente_nome")
            atendente = _valor_ou_none(row, colunas_lower, "atendente") or _valor_ou_none(row, colunas_lower, "atendente_nome")

            try:
                _processar_linha(db, texto, canal, cliente, atendente)
                db.commit()
                processados += 1
            except Exception:
                db.rollback()
                continue

        estado.ultima_linha = total_linhas
        estado.total_processados = (estado.total_processados or 0) + processados
        estado.atualizado_em = datetime.now(timezone.utc)
        db.commit()
    finally:
        db.close()


@router.post("/analisar")
def cron_analisar(
    background_tasks: BackgroundTasks,
    authorization: Optional[str] = Header(None),
):
    token = os.getenv("CRON_TOKEN")
    if not token:
        raise HTTPException(status_code=500, detail="CRON_TOKEN não configurado no servidor")
    if authorization != f"Bearer {token}":
        raise HTTPException(status_code=401, detail="Não autorizado")

    if not _montar_url_csv():
        raise HTTPException(status_code=400, detail="GOOGLE_SHEET_ID ou GOOGLE_SHEET_CSV_URL não configurado")

    background_tasks.add_task(_executar_analise)
    return {"status": "processando", "mensagem": "Análise da planilha iniciada em background"}


@router.get("/status")
def cron_status(db: Session = Depends(get_db)):
    estados = db.query(CronEstado).all()
    return [
        {
            "fonte": e.fonte,
            "ultima_linha": e.ultima_linha,
            "total_processados": e.total_processados,
            "atualizado_em": e.atualizado_em,
        }
        for e in estados
    ]


@router.post("/reset")
def cron_reset(db: Session = Depends(get_db)):
    total = db.query(CronEstado).count()
    db.query(CronEstado).delete()
    db.commit()
    return {"status": "resetado", "fontes_removidas": total}
