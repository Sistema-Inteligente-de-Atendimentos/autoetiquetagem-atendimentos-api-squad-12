from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import get_db
from app.core.taxonomy import CATEGORIAS_FIXAS
from app.models import CategoriaCustom


router = APIRouter(prefix="/config", tags=["Configuração"])


class CategoriaIn(BaseModel):
    nome: str
    criada_por: Optional[str] = None


def get_categorias_extras(db: Session) -> List[str]:
    return [c.nome for c in db.query(CategoriaCustom).order_by(CategoriaCustom.id).all()]


@router.get("/categorias")
def list_categorias(db: Session = Depends(get_db)):
    extras = db.query(CategoriaCustom).order_by(CategoriaCustom.id).all()
    return {
        "fixas": list(CATEGORIAS_FIXAS),
        "extras": [
            {
                "id": e.id,
                "nome": e.nome,
                "criada_por": e.criada_por,
                "criado_em": e.criado_em,
            }
            for e in extras
        ],
    }


@router.post("/categorias")
def add_categoria(req: CategoriaIn, db: Session = Depends(get_db)):
    nome = (req.nome or "").strip()
    if not nome:
        raise HTTPException(status_code=400, detail="Nome da categoria não pode ser vazio")
    if len(nome) > 100:
        raise HTTPException(status_code=400, detail="Nome muito longo (máx 100 caracteres)")

    nome_lower = nome.lower()
    if nome_lower in {c.lower() for c in CATEGORIAS_FIXAS}:
        raise HTTPException(status_code=400, detail="Esta categoria já existe como categoria fixa do sistema")

    existente = db.query(CategoriaCustom).filter(CategoriaCustom.nome.ilike(nome)).first()
    if existente:
        raise HTTPException(status_code=400, detail="Esta categoria já foi adicionada")

    nova = CategoriaCustom(nome=nome, criada_por=(req.criada_por or "").strip() or None)
    db.add(nova)
    db.commit()
    db.refresh(nova)

    return {
        "id": nova.id,
        "nome": nova.nome,
        "criada_por": nova.criada_por,
        "criado_em": nova.criado_em,
    }


@router.delete("/categorias/{categoria_id}")
def remove_categoria(categoria_id: int, db: Session = Depends(get_db)):
    c = db.query(CategoriaCustom).filter(CategoriaCustom.id == categoria_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Categoria não encontrada")
    db.delete(c)
    db.commit()
    return {"status": "removida", "id": categoria_id}
