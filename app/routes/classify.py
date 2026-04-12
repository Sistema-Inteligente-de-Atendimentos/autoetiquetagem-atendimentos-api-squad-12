from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

class Request(BaseModel):
    text:str


@router.get("/")
def home():
    return {"message":"{API rodando}"}

@router.post("/classify")
def classify(req: Request):
    return {"message":f"Recebido {req.text}"}