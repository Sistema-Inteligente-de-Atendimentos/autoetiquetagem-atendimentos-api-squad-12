from fastapi import APIRouter
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