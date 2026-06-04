from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import get_db
from app.models import Usuario
from app.services.auth_service import (
    criar_token,
    hash_senha,
    validar_token,
    verificar_senha,
)


router = APIRouter(prefix="/auth", tags=["Autenticação"])


class RegisterIn(BaseModel):
    nome: str
    email: str
    senha: str


class LoginIn(BaseModel):
    email: str
    senha: str


def _serializar(u: Usuario) -> dict:
    return {"id": u.id, "nome": u.nome, "email": u.email}


@router.post("/register")
def register(req: RegisterIn, db: Session = Depends(get_db)):
    nome = req.nome.strip()
    email = req.email.strip().lower()
    if not nome or not req.senha:
        raise HTTPException(status_code=400, detail="Nome e senha são obrigatórios")
    if len(req.senha) < 6:
        raise HTTPException(status_code=400, detail="A senha deve ter ao menos 6 caracteres")

    if db.query(Usuario).filter(Usuario.email == email).first():
        raise HTTPException(status_code=400, detail="Já existe uma conta com este e-mail")

    usuario = Usuario(nome=nome, email=email, senha_hash=hash_senha(req.senha))
    db.add(usuario)
    db.commit()
    db.refresh(usuario)

    token = criar_token(usuario.id, usuario.nome)
    return {"token": token, "usuario": _serializar(usuario)}


@router.post("/login")
def login(req: LoginIn, db: Session = Depends(get_db)):
    email = req.email.strip().lower()
    usuario = db.query(Usuario).filter(Usuario.email == email).first()
    if not usuario or not verificar_senha(req.senha, usuario.senha_hash):
        raise HTTPException(status_code=401, detail="E-mail ou senha incorretos")

    token = criar_token(usuario.id, usuario.nome)
    return {"token": token, "usuario": _serializar(usuario)}


def get_current_user(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
) -> Usuario:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Não autenticado")
    token = authorization.split(" ", 1)[1]
    payload = validar_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Token inválido ou expirado")
    usuario = db.query(Usuario).filter(Usuario.id == payload.get("sub")).first()
    if not usuario:
        raise HTTPException(status_code=401, detail="Usuário não encontrado")
    return usuario


def get_optional_user(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
) -> Optional[Usuario]:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    payload = validar_token(authorization.split(" ", 1)[1])
    if not payload:
        return None
    return db.query(Usuario).filter(Usuario.id == payload.get("sub")).first()


@router.get("/me")
def me(usuario: Usuario = Depends(get_current_user)):
    return _serializar(usuario)
