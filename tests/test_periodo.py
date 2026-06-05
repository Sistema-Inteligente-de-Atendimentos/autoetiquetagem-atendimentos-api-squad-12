from datetime import datetime

from app.routes.dashboard import _parse_periodo


def test_periodo_completo():
    ini, fim = _parse_periodo("2026-06-01", "2026-06-10")
    assert ini == datetime(2026, 6, 1)
    # fim recebe +1 dia para incluir o dia inteiro
    assert fim == datetime(2026, 6, 11)


def test_periodo_sem_datas():
    ini, fim = _parse_periodo(None, None)
    assert ini is None
    assert fim is None


def test_periodo_so_inicio():
    ini, fim = _parse_periodo("2026-06-01", None)
    assert ini == datetime(2026, 6, 1)
    assert fim is None


def test_periodo_data_invalida_ignorada():
    ini, fim = _parse_periodo("data-errada", "2026-06-10")
    assert ini is None
    assert fim == datetime(2026, 6, 11)


def test_periodo_fim_inclui_dia_inteiro():
    # um atendimento às 23h do dia 10 deve cair dentro do filtro
    _, fim = _parse_periodo(None, "2026-06-10")
    assert datetime(2026, 6, 10, 23, 0) < fim
