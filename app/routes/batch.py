import io
import json
import uuid
from typing import List

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from app.config import get_db
from app.models import (
    Avaliacao,
    ChannelChat,
    ChannelChatMessage,
    ChannelChatProtocol,
)
from app.services.chat_parser import dividir_mensagens
from app.services.llm_service import buscar_exemplos_aprovados, classify_text


router = APIRouter(tags=["Processamento em Lote"])

COLUNAS_TEXTO = ["texto", "atendimento", "mensagem", "conteudo", "text", "message"]
EXTENSOES_VALIDAS = {".csv", ".xlsx", ".xls"}
LIMITE_LINHAS = 50


def _normalizar(nome: str) -> str:
    # Remove BOM, espacos e caracteres invisiveis dos nomes de coluna
    return nome.replace("﻿", "").strip().lower()


def _encontrar_coluna_texto(colunas: List[str]) -> str | None:
    colunas_lower = {_normalizar(c): c for c in colunas}
    for nome in COLUNAS_TEXTO:
        if nome in colunas_lower:
            return colunas_lower[nome]
    return None


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


def _valor_ou_none(row, colunas_lower, chave) -> str | None:
    nome_real = colunas_lower.get(_normalizar(chave))
    if nome_real is None:
        return None
    val = row.get(nome_real)
    if pd.isna(val):
        return None
    return str(val).strip() or None


@router.post("/classify/batch")
async def classify_batch(file: UploadFile = File(...), db: Session = Depends(get_db)):
    filename = (file.filename or "").lower()
    extensao = ""
    for ext in EXTENSOES_VALIDAS:
        if filename.endswith(ext):
            extensao = ext
            break

    if not extensao:
        raise HTTPException(
            status_code=400,
            detail=f"Formato inválido. Envie arquivos: {', '.join(EXTENSOES_VALIDAS)}",
        )

    conteudo = await file.read()

    try:
        if extensao == ".csv":
            df = None
            ultimo_erro = None
            # Tenta separadores comuns na ordem. utf-8-sig remove BOM se existir.
            for sep in [",", ";", "\t", "|"]:
                try:
                    candidato = pd.read_csv(
                        io.BytesIO(conteudo),
                        sep=sep,
                        engine="python",
                        encoding="utf-8-sig",
                    )
                    if not candidato.empty:
                        df = candidato
                        break
                except Exception as e:
                    ultimo_erro = e
                    continue
            if df is None:
                raise ultimo_erro or ValueError("Nenhum separador valido detectado")
        else:
            df = pd.read_excel(io.BytesIO(conteudo))
        # Normaliza nomes das colunas (remove BOM e espacos)
        df.columns = [str(c).replace("﻿", "").strip() for c in df.columns]
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erro ao ler o arquivo: {str(e)}")

    if df.empty:
        raise HTTPException(status_code=400, detail="O arquivo está vazio.")

    if len(df) > LIMITE_LINHAS:
        raise HTTPException(
            status_code=400,
            detail=f"O arquivo tem {len(df)} linhas. O limite é {LIMITE_LINHAS} por envio.",
        )

    col_texto = _encontrar_coluna_texto(list(df.columns))
    if col_texto is None:
        raise HTTPException(
            status_code=400,
            detail=f"Nenhuma coluna de texto encontrada. Use uma destas: {', '.join(COLUNAS_TEXTO)}",
        )

    colunas_lower = {_normalizar(c): c for c in df.columns}

    resultados = []
    erros = []

    for idx, row in df.iterrows():
        texto = row.get(col_texto)
        if pd.isna(texto) or not str(texto).strip():
            erros.append({"linha": int(idx) + 2, "erro": "Texto vazio"})
            continue

        texto = str(texto).strip()
        canal = _valor_ou_none(row, colunas_lower, "canal") or "Arquivo"
        cliente_csv = _valor_ou_none(row, colunas_lower, "cliente") or _valor_ou_none(row, colunas_lower, "cliente_nome")
        atendente_csv = _valor_ou_none(row, colunas_lower, "atendente") or _valor_ou_none(row, colunas_lower, "atendente_nome")

        exemplos = buscar_exemplos_aprovados(db, limite=3, canal=canal)
        response = classify_text(texto, exemplos=exemplos)

        if "error" in response:
            erros.append({"linha": int(idx) + 2, "erro": response["error"]})
            continue

        data = response.get("data", {}) or {}
        qualidade = data.get("qualidade") or {}

        # CSV tem prioridade. Se não veio, usa o que a IA extraiu do texto.
        cliente = cliente_csv or (data.get("cliente_nome") or None)
        atendente = atendente_csv or (data.get("atendente_nome") or None)

        try:
            novo_chat = ChannelChat(
                cliente_nome=cliente,
                atendente_nome=atendente,
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

            mensagens_divididas = dividir_mensagens(
                texto,
                cliente_nome=cliente,
                atendente_nome=atendente,
            )
            if not mensagens_divididas:
                mensagens_divididas = [("cliente", texto)]

            for remetente, conteudo in mensagens_divididas:
                msg = ChannelChatMessage(
                    channel_chat_id=novo_chat.id,
                    protocolo_id=novo_protocolo.id,
                    remetente=remetente,
                    conteudo=conteudo,
                )
                db.add(msg)
            db.flush()

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

            resultados.append({
                "linha": int(idx) + 2,
                "protocolo_id": novo_protocolo.id,
                "protocolo_numero": novo_protocolo.numero,
                "categoria": data.get("categoria"),
                "sentimento": data.get("sentimento"),
                "nota": nota,
            })

        except Exception as e:
            erros.append({"linha": int(idx) + 2, "erro": str(e)})
            continue

    if resultados:
        db.commit()
    else:
        db.rollback()

    return {
        "total_enviados": len(df),
        "total_processados": len(resultados),
        "total_erros": len(erros),
        "resultados": resultados,
        "erros": erros,
    }
