import time

from app.services import auth_service
from app.services.auth_service import (
    criar_token,
    hash_senha,
    validar_token,
    verificar_senha,
)


# ---------- hash de senha ----------

def test_senha_correta_verifica():
    h = hash_senha("minhasenha123")
    assert verificar_senha("minhasenha123", h) is True


def test_senha_errada_falha():
    h = hash_senha("minhasenha123")
    assert verificar_senha("outrasenha", h) is False


def test_hash_diferente_a_cada_chamada():
    # salt aleatório → hashes diferentes para a mesma senha
    assert hash_senha("abc123") != hash_senha("abc123")


def test_hash_malformado_nao_quebra():
    assert verificar_senha("qualquer", "formato-invalido") is False


# ---------- token ----------

def test_token_valido_decodifica():
    token = criar_token(42, "Maria")
    payload = validar_token(token)
    assert payload is not None
    assert payload["sub"] == 42
    assert payload["nome"] == "Maria"


def test_token_adulterado_rejeitado():
    token = criar_token(1, "João")
    payload = validar_token(token + "x")
    assert payload is None


def test_token_lixo_rejeitado():
    assert validar_token("isto.nao.e.um.token") is None
    assert validar_token("") is None


def test_token_expirado_rejeitado(monkeypatch):
    # gera token e simula que o tempo avançou além da validade
    token = criar_token(1, "João")
    futuro = time.time() + auth_service.TOKEN_VALIDADE_SEGUNDOS + 10
    monkeypatch.setattr(auth_service.time, "time", lambda: futuro)
    assert validar_token(token) is None
