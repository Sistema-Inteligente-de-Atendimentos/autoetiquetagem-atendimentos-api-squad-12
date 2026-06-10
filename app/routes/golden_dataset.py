import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.config import get_db
from app.models import Avaliacao, ChannelChatProtocol, GoldenDatasetItem, GoldenDatasetRun
from app.schemas import GoldenDatasetItemIn, GoldenDatasetRunDetalheOut, GoldenDatasetRunOut
from app.services.golden_dataset_service import executar_run, montar_texto_avaliacao


router = APIRouter(prefix="/golden-dataset", tags=["Golden Dataset"])


def _serializar_item(item: GoldenDatasetItem) -> dict:
    avaliacao = item.avaliacao
    protocolo = avaliacao.protocolo if avaliacao else None
    chat = protocolo.chat if protocolo else None
    return {
        "id": item.id,
        "avaliacao_id": item.avaliacao_id,
        "protocolo_id": protocolo.id if protocolo else None,
        "numero": protocolo.numero if protocolo else None,
        "canal": chat.canal if chat else None,
        "cliente_nome": chat.cliente_nome if chat else None,
        "categoria_esperada": item.categoria_esperada,
        "sentimento_esperado": item.sentimento_esperado,
        "criticidade_esperada": item.criticidade_esperada,
        "score_esperado": item.score_esperado,
        "incluido_por": item.incluido_por,
        "incluido_em": item.incluido_em,
    }


@router.post("/itens", status_code=201)
def adicionar_item(req: GoldenDatasetItemIn, db: Session = Depends(get_db)):
    avaliacao = (
        db.query(Avaliacao)
        .options(
            joinedload(Avaliacao.protocolo).joinedload(ChannelChatProtocol.mensagens),
            joinedload(Avaliacao.protocolo).joinedload(ChannelChatProtocol.chat),
        )
        .filter(Avaliacao.id == req.avaliacao_id)
        .first()
    )
    if not avaliacao:
        raise HTTPException(status_code=404, detail="Avaliação não encontrada")

    if not (avaliacao.aprovado_como_exemplo or avaliacao.json_raw_ia is not None):
        raise HTTPException(
            status_code=400,
            detail="Avaliação ainda não foi revisada (aprovada como exemplo ou corrigida)",
        )

    if db.query(GoldenDatasetItem).filter(GoldenDatasetItem.avaliacao_id == req.avaliacao_id).first():
        raise HTTPException(status_code=409, detail="Esta avaliação já está no golden dataset")

    try:
        dados = json.loads(avaliacao.json_raw) if avaliacao.json_raw else {}
    except (TypeError, ValueError):
        dados = {}
    qualidade = dados.get("qualidade") or {}

    item = GoldenDatasetItem(
        avaliacao_id=avaliacao.id,
        texto=montar_texto_avaliacao(avaliacao),
        categoria_esperada=dados.get("categoria"),
        sentimento_esperado=dados.get("sentimento"),
        criticidade_esperada=dados.get("criticidade"),
        score_esperado=qualidade.get("score_final"),
        incluido_por=(req.incluido_por or "").strip() or None,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return _serializar_item(item)


@router.get("/itens")
def listar_itens(db: Session = Depends(get_db)):
    itens = (
        db.query(GoldenDatasetItem)
        .options(
            joinedload(GoldenDatasetItem.avaliacao)
            .joinedload(Avaliacao.protocolo)
            .joinedload(ChannelChatProtocol.chat)
        )
        .order_by(GoldenDatasetItem.incluido_em.desc())
        .all()
    )
    return [_serializar_item(i) for i in itens]


@router.delete("/itens/{item_id}")
def remover_item(item_id: int, db: Session = Depends(get_db)):
    item = db.query(GoldenDatasetItem).filter(GoldenDatasetItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item não encontrado")
    db.delete(item)
    db.commit()
    return {"status": "removido", "id": item_id}


@router.post("/executar", response_model=GoldenDatasetRunOut)
def executar(db: Session = Depends(get_db)):
    if db.query(GoldenDatasetItem).count() == 0:
        raise HTTPException(status_code=400, detail="Nenhum item no golden dataset")
    return executar_run(db)


@router.get("/runs", response_model=list[GoldenDatasetRunOut])
def listar_runs(db: Session = Depends(get_db)):
    return db.query(GoldenDatasetRun).order_by(GoldenDatasetRun.executado_em.asc()).all()


@router.get("/runs/{run_id}", response_model=GoldenDatasetRunDetalheOut)
def detalhe_run(run_id: int, db: Session = Depends(get_db)):
    run = db.query(GoldenDatasetRun).filter(GoldenDatasetRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run não encontrada")
    try:
        detalhes = json.loads(run.detalhes_json) if run.detalhes_json else []
    except (TypeError, ValueError):
        detalhes = []
    return GoldenDatasetRunDetalheOut(
        id=run.id,
        executado_em=run.executado_em,
        total_casos=run.total_casos,
        acertos_categoria=run.acertos_categoria,
        acertos_sentimento=run.acertos_sentimento,
        acertos_criticidade=run.acertos_criticidade,
        acuracia_geral=run.acuracia_geral,
        detalhes=detalhes,
    )
