import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import Base
from app.models import CronEstado
from app.routes import cron as cron_module


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    yield db
    db.close()


def test_processar_url_loga_erro_e_preserva_progresso(db_session, monkeypatch, caplog):
    df = pd.DataFrame({"texto": ["ok 1", "falha", "ok 2"]})
    monkeypatch.setattr(cron_module, "_ler_planilha", lambda url: df)

    def fake_processar_linha(db, texto, canal, cliente, atendente):
        if texto == "falha":
            raise ValueError("erro simulado")

    monkeypatch.setattr(cron_module, "_processar_linha", fake_processar_linha)

    with caplog.at_level("ERROR"):
        processados = cron_module._processar_url(db_session, "http://fake-url")

    estado = db_session.query(CronEstado).filter_by(fonte="http://fake-url").first()

    assert processados == 2
    assert estado.ultima_linha == 3
    assert estado.total_processados == 2
    assert estado.total_erros == 1
    assert "erro simulado" in (estado.ultimo_erro or "")
    assert any("Falha ao processar linha" in r.getMessage() for r in caplog.records)


def test_processar_url_sem_erro_nao_seta_ultimo_erro(db_session, monkeypatch):
    df = pd.DataFrame({"texto": ["ok 1", "ok 2"]})
    monkeypatch.setattr(cron_module, "_ler_planilha", lambda url: df)
    monkeypatch.setattr(cron_module, "_processar_linha", lambda *a, **k: None)

    processados = cron_module._processar_url(db_session, "http://fake-url")

    estado = db_session.query(CronEstado).filter_by(fonte="http://fake-url").first()

    assert processados == 2
    assert estado.total_erros == 0
    assert estado.ultimo_erro is None
