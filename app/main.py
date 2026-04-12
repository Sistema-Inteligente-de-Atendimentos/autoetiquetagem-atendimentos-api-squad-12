from fastapi import FastAPI
from app.routes.classify import router as classify_router


app = FastAPI()


app.include_router(classify_router)