import json
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import Base
from app.models import Avaliacao, ChannelChat, ChannelChatMessage, ChannelChatProtocol, GoldenDatasetItem, GoldenDatasetRun
from app.routes import golden_dataset as golden_dataset_module
from app.services import golden_dataset_service


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    yield db
    db.close()


def _criar_avaliacao_corrigida(db, json_raw_ia, json_raw):
    chat = ChannelChat(cliente_nome="Maria", canal="Web")
    db.add(chat); db.flush()
    protocolo = ChannelChatProtocol(channel_chat_id=chat.id, numero="P-1")
    db.add(protocolo); db.flush()
    db.add(ChannelChatMessage(channel_chat_id=chat.id, protocolo_id=protocolo.id, remetente="cliente", conteudo="Meu boleto não chegou"))
    db.add(ChannelChatMessage(channel_chat_id=chat.id, protocolo_id=protocolo.id, remetente="atendente", conteudo="Vou verificar"))
    db.flush()
    avaliacao = Avaliacao(
        protocolo_id=protocolo.id,
        json_raw=json.dumps(json_raw),
        json_raw_ia=json.dumps(json_raw_ia),
        analisado_por="Revisor",
    )
    db.add(avaliacao); db.commit()
    return avaliacao


def test_adicionar_item_snapshot_correto(db_session):
    av = _criar_avaliacao_corrigida(
        db_session,
        json_raw_ia={"categoria": "Técnico", "sentimento": "Negativo", "criticidade": "Alta", "qualidade": {"score_final": 5.0}},
        json_raw={"categoria": "Financeiro", "sentimento": "Neutro", "criticidade": "Média", "qualidade": {"score_final": 8.0}},
    )
    req = golden_dataset_module.GoldenDatasetItemIn(avaliacao_id=av.id, incluido_por="Ana")
    resultado = golden_dataset_module.adicionar_item(req, db_session)

    assert resultado["categoria_esperada"] == "Financeiro"
    assert resultado["sentimento_esperado"] == "Neutro"
    assert resultado["criticidade_esperada"] == "Média"
    assert resultado["score_esperado"] == 8.0
    assert "Cliente: Meu boleto não chegou" in db_session.query(GoldenDatasetItem).first().texto


def test_adicionar_item_rejeita_nao_revisado(db_session):
    chat = ChannelChat(canal="Web")
    db_session.add(chat); db_session.flush()
    protocolo = ChannelChatProtocol(channel_chat_id=chat.id, numero="P-2")
    db_session.add(protocolo); db_session.flush()
    av = Avaliacao(protocolo_id=protocolo.id, json_raw=json.dumps({"categoria": "Outros"}))
    db_session.add(av); db_session.commit()

    req = golden_dataset_module.GoldenDatasetItemIn(avaliacao_id=av.id)
    with pytest.raises(Exception):
        golden_dataset_module.adicionar_item(req, db_session)


def test_adicionar_item_rejeita_duplicado(db_session):
    av = _criar_avaliacao_corrigida(db_session, {"categoria": "A"}, {"categoria": "B"})
    req = golden_dataset_module.GoldenDatasetItemIn(avaliacao_id=av.id)
    golden_dataset_module.adicionar_item(req, db_session)

    with pytest.raises(Exception):
        golden_dataset_module.adicionar_item(req, db_session)


def test_remover_item(db_session):
    av = _criar_avaliacao_corrigida(db_session, {"categoria": "A"}, {"categoria": "B"})
    item = golden_dataset_module.adicionar_item(golden_dataset_module.GoldenDatasetItemIn(avaliacao_id=av.id), db_session)
    golden_dataset_module.remover_item(item["id"], db_session)
    assert db_session.query(GoldenDatasetItem).count() == 0


def test_executar_run_calcula_acuracia(db_session, monkeypatch):
    av1 = _criar_avaliacao_corrigida(
        db_session,
        json_raw_ia={"categoria": "Técnico", "sentimento": "Negativo", "criticidade": "Alta", "qualidade": {"score_final": 4.0}},
        json_raw={"categoria": "Financeiro", "sentimento": "Neutro", "criticidade": "Média", "qualidade": {"score_final": 8.0}},
    )
    golden_dataset_module.adicionar_item(golden_dataset_module.GoldenDatasetItemIn(avaliacao_id=av1.id), db_session)

    def fake_classify_text(text, exemplos=None, categorias_extras=None):
        return {
            "data": {
                "categoria": "Financeiro",
                "sentimento": "Negativo",
                "criticidade": "Média",
                "qualidade": {"score_final": 8.5},
            },
            "usage": {},
        }

    monkeypatch.setattr(golden_dataset_service, "classify_text", fake_classify_text)
    monkeypatch.setattr(golden_dataset_service, "buscar_exemplos_aprovados", lambda *a, **k: [])
    monkeypatch.setattr(golden_dataset_service, "get_categorias_extras", lambda db: [])
    monkeypatch.setattr(golden_dataset_service, "DELAY_ENTRE_CHAMADAS", 0)

    run = golden_dataset_service.executar_run(db_session)

    assert run.total_casos == 1
    assert run.acertos_categoria == 1
    assert run.acertos_sentimento == 0
    assert run.acertos_criticidade == 1
    assert run.acuracia_geral == round(2 / 3, 4)

    detalhes = json.loads(run.detalhes_json)
    assert detalhes[0]["acerto_score"] is True


def test_listar_runs_ordem_cronologica(db_session):
    db_session.add(GoldenDatasetRun(total_casos=1, acertos_categoria=1, acertos_sentimento=1, acertos_criticidade=1, acuracia_geral=1.0))
    db_session.add(GoldenDatasetRun(total_casos=2, acertos_categoria=1, acertos_sentimento=1, acertos_criticidade=1, acuracia_geral=0.5))
    db_session.commit()

    runs = golden_dataset_module.listar_runs(db_session)
    assert len(runs) == 2
    assert runs[0].total_casos == 1
