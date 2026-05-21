from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session, joinedload

from app.config import Base, SessionLocal, engine


from app.models import (
    ChannelChat,
    ChannelChatProtocol,
    ChannelChatMessage,
    Avaliacao,
)
from app.routes.classify import router as classify_router
from app.routes.dashboard import router as dashboard_router
from app.routes.batch import router as batch_router


app = FastAPI(title="Auto-Etiquetagem de Atendimentos - Squad 12")


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "https://autoetiquetagem-atendimentos-web-sq.vercel.app",
    ],
    allow_origin_regex=r"https://autoetiquetagem-atendimentos-web-sq.*\.vercel\.app",
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


@app.on_event("startup")
def on_startup() -> None:

    Base.metadata.create_all(bind=engine)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/chats")
def list_chats(db: Session = Depends(get_db)):

    return (
        db.query(ChannelChat)
        .options(
            joinedload(ChannelChat.protocolos).joinedload(ChannelChatProtocol.mensagens),
            joinedload(ChannelChat.protocolos).joinedload(ChannelChatProtocol.avaliacoes),
        )
        .all()
    )


app.include_router(classify_router)
app.include_router(dashboard_router)
app.include_router(batch_router)
