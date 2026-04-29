from fastapi import APIRouter, UploadFile , File
import pandas as pd
from pydantic import BaseModel
from app.services.llm_service import classify_text

router = APIRouter()

class Request(BaseModel):
    text:str


@router.get("/")
def home():
    return {"message":"{API rodando}"}

@router.post("/classify")
def classify(req: Request):
    return classify_text(req.text)

@router.post("/classify/batch")
async def classify_batch(file:UploadFile = File(...)):
    if file.filename.endswith(".csv"):
        df = pd.read_csv(file.file)
    elif file.filename.endswith(".xlsx"):
        df = pd.read_excel(file.file)
    else:
        return {"error":"Formato inválido. Use CSV ou XLSX"}
    
    if "texto" not in df.columns and "atendimento" not in df.columns:
        return {"error": "Arquivo precisa ter coluna 'texto' ou 'atendimento' "}
    
    column = "texto" if "texto" in df.columns else "atendimento"

    results = []

    for index, row in df.iterrows():
        text =str(row[column])

        try:
            response = classify_text(text)
            results.append({
                 "index": index,
                "input": text,
                "data": response.get("data"),
                "usage": response.get("usage")
            })

        except Exception as e:
            results.append({
                "index": index,
                "error": str(e)
            })

        return {
            "total": len(results),
            "results": results
        }