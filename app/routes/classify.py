from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session
import pandas as pd
from pydantic import BaseModel

from app.config import get_db
from app.models import Atendimento, AnaliseIA, ScoreQualidade
from app.services.llm_service import classify_text

router = APIRouter()


class Request(BaseModel):
    text: str
    origem: str = "Web"


@router.post("/classify")
def classify(req: Request, db: Session = Depends(get_db)):
    response = classify_text(req.text)

    if "error" in response:
        raise HTTPException(status_code=500, detail=response["error"])

    data = response.get("data", {})

    try:
        novo_atendimento = Atendimento(
            texto_bruto=req.text,
            origem=req.origem
        )
        db.add(novo_atendimento)
        db.flush()

        nova_analise = AnaliseIA(
            atendimento_id=novo_atendimento.id,
            categoria=data.get("categoria"),
            intencao=data.get("intencao"),
            sentimento=data.get("sentimento"),
            criticidade=data.get("criticidade"),
            resumo=data.get("resumo"),
            topicos=data.get("topicos"),
            json_raw=str(response)
        )
        db.add(nova_analise)
        db.flush()

        scores_data = data.get("qualidade") or {}

        novo_score = ScoreQualidade(
            analise_id=nova_analise.id,
            empatia=scores_data.get("empatia", 0),
            clareza=scores_data.get("clareza", 0),
            objetividade=scores_data.get("objetividade", 0),
            resolutividade=scores_data.get("resolutividade", 0),
            score_final=scores_data.get("score_final", 0)
        )
        db.add(novo_score)

        db.commit()

        return {
            "status": "sucesso",
            "atendimento_id": novo_atendimento.id,
            "data": data
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/atendimentos")
def list_atendimentos(db: Session = Depends(get_db)):
    atendimentos = db.query(Atendimento).all()
    return atendimentos


@router.get("/auditoria/{atendimento_id}")
def get_auditoria(atendimento_id: int, db: Session = Depends(get_db)):
    atendimento = db.query(Atendimento).filter(Atendimento.id == atendimento_id).first()
    if not atendimento:
        raise HTTPException(status_code=404, detail="Atendimento não encontrado")
    return atendimento