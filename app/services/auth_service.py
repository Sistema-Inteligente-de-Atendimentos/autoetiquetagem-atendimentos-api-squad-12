import base64
import hashlib
import hmac
import json
import os
import time
from typing import Optional

AUTH_SECRET = os.getenv("AUTH_SECRET", "dev-secret-troque-em-producao")
TOKEN_VALIDADE_SEGUNDOS = 60 * 60 * 24 * 7  # 7 dias

_PBKDF2_ITERACOES = 120_000


def hash_senha(senha: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", senha.encode(), salt, _PBKDF2_ITERACOES)
    return f"{salt.hex()}${dk.hex()}"


def verificar_senha(senha: str, senha_hash: str) -> bool:
    try:
        salt_hex, dk_hex = senha_hash.split("$")
        salt = bytes.fromhex(salt_hex)
        esperado = bytes.fromhex(dk_hex)
        calculado = hashlib.pbkdf2_hmac("sha256", senha.encode(), salt, _PBKDF2_ITERACOES)
        return hmac.compare_digest(esperado, calculado)
    except Exception:
        return False


def _b64url(dados: bytes) -> str:
    return base64.urlsafe_b64encode(dados).decode().rstrip("=")


def _b64url_decode(txt: str) -> bytes:
    pad = "=" * (-len(txt) % 4)
    return base64.urlsafe_b64decode(txt + pad)


def criar_token(user_id: int, nome: str) -> str:
    payload = {
        "sub": user_id,
        "nome": nome,
        "exp": int(time.time()) + TOKEN_VALIDADE_SEGUNDOS,
    }
    corpo = _b64url(json.dumps(payload, separators=(",", ":")).encode())
    assinatura = hmac.new(AUTH_SECRET.encode(), corpo.encode(), hashlib.sha256).digest()
    return f"{corpo}.{_b64url(assinatura)}"


def validar_token(token: str) -> Optional[dict]:
    try:
        corpo, assinatura = token.split(".")
        esperado = hmac.new(AUTH_SECRET.encode(), corpo.encode(), hashlib.sha256).digest()
        if not hmac.compare_digest(_b64url(esperado), assinatura):
            return None
        payload = json.loads(_b64url_decode(corpo))
        if payload.get("exp", 0) < int(time.time()):
            return None
        return payload
    except Exception:
        return None
