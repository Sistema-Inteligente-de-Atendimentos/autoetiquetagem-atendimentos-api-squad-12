import io
from datetime import datetime, timezone
from typing import List, Optional

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import get_db
from app.core.taxonomy import CATEGORIAS_FIXAS
from app.models import CategoriaCustom, CronConfig, CronEstado


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


# ── Planilhas ──────────────────────────────────────────────────────────────────

class PlanilhaIn(BaseModel):
    url: str
    nome: Optional[str] = None
    criado_por: Optional[str] = None


def _testar_url(url: str) -> int:
    try:
        df = pd.read_csv(url, encoding="utf-8-sig", nrows=5)
        return len(pd.read_csv(url, encoding="utf-8-sig"))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"URL inacessível ou inválida: {str(e)}")


def _serializar_planilha(p: CronConfig, estado: Optional[CronEstado]) -> dict:
    return {
        "id": p.id,
        "url": p.url,
        "nome": p.nome,
        "ativo": p.ativo,
        "criado_por": p.criado_por,
        "criado_em": p.criado_em,
        "ultima_linha": estado.ultima_linha if estado else 0,
        "total_processados": estado.total_processados if estado else 0,
        "atualizado_em": estado.atualizado_em if estado else None,
    }


@router.get("/planilhas")
def list_planilhas(db: Session = Depends(get_db)):
    planilhas = db.query(CronConfig).order_by(CronConfig.criado_em.desc()).all()
    resultado = []
    for p in planilhas:
        estado = db.query(CronEstado).filter(CronEstado.fonte == p.url).first()
        resultado.append(_serializar_planilha(p, estado))
    return resultado


@router.post("/planilhas")
def add_planilha(req: PlanilhaIn, db: Session = Depends(get_db)):
    url = (req.url or "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="URL não pode ser vazia")

    existente = db.query(CronConfig).filter(CronConfig.url == url).first()
    if existente:
        raise HTTPException(status_code=400, detail="Esta planilha já está cadastrada")

    total_linhas = _testar_url(url)

    nova = CronConfig(
        url=url,
        nome=(req.nome or "").strip() or None,
        criado_por=(req.criado_por or "").strip() or None,
        ativo=True,
    )
    db.add(nova)
    db.commit()
    db.refresh(nova)

    return {**_serializar_planilha(nova, None), "linhas_detectadas": total_linhas}


@router.patch("/planilhas/{planilha_id}/ativar")
def ativar_planilha(planilha_id: int, db: Session = Depends(get_db)):
    p = db.query(CronConfig).filter(CronConfig.id == planilha_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Planilha não encontrada")
    p.ativo = True
    db.commit()
    return {"status": "ativada", "id": planilha_id}


@router.patch("/planilhas/{planilha_id}/desativar")
def desativar_planilha(planilha_id: int, db: Session = Depends(get_db)):
    p = db.query(CronConfig).filter(CronConfig.id == planilha_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Planilha não encontrada")
    p.ativo = False
    db.commit()
    return {"status": "desativada", "id": planilha_id}


@router.delete("/planilhas/{planilha_id}")
def remove_planilha(planilha_id: int, db: Session = Depends(get_db)):
    p = db.query(CronConfig).filter(CronConfig.id == planilha_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Planilha não encontrada")
    db.query(CronEstado).filter(CronEstado.fonte == p.url).delete()
    db.delete(p)
    db.commit()
    return {"status": "removida", "id": planilha_id}
