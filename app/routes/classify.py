from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session, joinedload
from app.config import get_db
from app.models import Atendimento, AnaliseIA, ScoreQualidade
from app.services.llm_service import classify_text
from pydantic import BaseModel
import pandas as pd
import io

router = APIRouter()


class Request(BaseModel):
    text: str


@router.get("/")
def home():
    return {"status": "online", "message": "API de Autoetiquetagem Ativa"}


@router.post("/classify")
def classify(req: Request, db: Session = Depends(get_db)):
    result = classify_text(req.text)

    if "error" in result:
        raise HTTPException(status_code=500, detail="Erro no processamento da IA")

    try:
        data = result["data"]
        qualidade = data.get("qualidade", {})

        novo_atendimento = Atendimento(
            texto_bruto=req.text,
            origem="Web"
        )
        db.add(novo_atendimento)
        db.flush()

        nova_analise = AnaliseIA(
            atendimento_id=novo_atendimento.id,
            categoria=data.get("categoria"),
            intencao=data.get("intencao"),
            sentimento=data.get("sentimento"),
            criticidade=data.get("criticidade"),
            resumo=str(data.get("resumo")),
            topicos=data.get("topicos"),
            json_raw=str(data)
        )
        db.add(nova_analise)
        db.flush()

        novo_score = ScoreQualidade(
            analise_id=nova_analise.id,
            empatia=qualidade.get("empatia"),
            clareza=qualidade.get("clareza"),
            objetividade=qualidade.get("objetividade"),
            resolutividade=qualidade.get("resolutividade"),
            score_final=qualidade.get("score_final")
        )
        db.add(novo_score)

        db.commit()

        return {
            "id": novo_atendimento.id,
            "data": data,
            "usage": result.get("usage")
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/atendimentos")
def list_atendimentos(db: Session = Depends(get_db)):
    try:
        atendimentos = db.query(Atendimento).options(
            joinedload(Atendimento.analises).joinedload(AnaliseIA.score_qualidade)
        ).all()

        return atendimentos
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/classify/batch")
async def classify_batch(file: UploadFile = File(...)):
    content = await file.read()
    text_data = content.decode("utf-8")

    lines = [line.strip() for line in text_data.splitlines() if line.strip()]

    if lines and lines[0].lower() in ["texto", "atendimento"]:
        lines = lines[1:]

    full_conversation = "\n".join(lines)

    try:
        response = classify_text(full_conversation)

        return {
            "total_messages": len(lines),
            "conversation": full_conversation,
            "data": response.get("data"),
            "usage": response.get("usage")
        }

    except Exception as e:
        return {
            "error": str(e)
        }