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