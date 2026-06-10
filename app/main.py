from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
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
from app.routes.cron import router as cron_router
from app.routes.categorias import router as categorias_router
from app.routes.auth import router as auth_router
from app.routes.golden_dataset import router as golden_dataset_router


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
    _aplicar_migrations_simples()


def _aplicar_migrations_simples() -> None:
    statements = [
        'ALTER TABLE avaliacoes ADD COLUMN IF NOT EXISTS "JsonRaw" TEXT',
        'ALTER TABLE avaliacoes ADD COLUMN IF NOT EXISTS "AprovadoComoExemplo" BOOLEAN NOT NULL DEFAULT FALSE',
        'ALTER TABLE avaliacoes ADD COLUMN IF NOT EXISTS "AprovadoPor" VARCHAR(150)',
        'ALTER TABLE avaliacoes ADD COLUMN IF NOT EXISTS "AprovadoEm" TIMESTAMP WITH TIME ZONE',
        'ALTER TABLE avaliacoes ADD COLUMN IF NOT EXISTS "ObservacaoAprovacao" TEXT',
        'CREATE INDEX IF NOT EXISTS ix_avaliacoes_aprovado_como_exemplo ON avaliacoes ("AprovadoComoExemplo")',
        'ALTER TABLE avaliacoes ALTER COLUMN "Nota" TYPE DOUBLE PRECISION USING "Nota"::double precision',
        'ALTER TABLE avaliacoes ADD COLUMN IF NOT EXISTS "AnalisadoPor" VARCHAR(150) DEFAULT \'IA\'',
        'ALTER TABLE avaliacoes ADD COLUMN IF NOT EXISTS "JsonRawIa" TEXT',
        'ALTER TABLE avaliacoes ADD COLUMN IF NOT EXISTS "CorrigidoEm" TIMESTAMP WITH TIME ZONE',
        'ALTER TABLE cron_estado ADD COLUMN IF NOT EXISTS "TotalErros" INTEGER NOT NULL DEFAULT 0',
        'ALTER TABLE cron_estado ADD COLUMN IF NOT EXISTS "UltimoErro" TEXT',
    ]
    with engine.begin() as conn:
        for stmt in statements:
            conn.execute(text(stmt))


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
app.include_router(cron_router)
app.include_router(categorias_router)
app.include_router(auth_router)
app.include_router(golden_dataset_router)
