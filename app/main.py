from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session, joinedload
from app.routes.classify import router as classify_router
from app.config import SessionLocal
from app.models import Atendimento, AnaliseIA # Importe seus modelos

app = FastAPI()


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "https://autoetiquetagem-atendimentos-web-squad-12-7qna8pypr.vercel.app"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/atendimentos")
def get_atendimentos(db: Session = Depends(get_db)):

    return db.query(Atendimento).options(
        joinedload(Atendimento.analises).joinedload(AnaliseIA.score_qualidade)
    ).all()


app.include_router(classify_router)