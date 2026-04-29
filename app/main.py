from fastapi import FastAPI
from app.routes.classify import router as classify_router
from fastapi.middleware.cors import CORSMiddleware


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


app.include_router(classify_router)