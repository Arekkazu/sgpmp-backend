"""SEG-M01-02 (#438): el token SSO de AgroFusion debe traer aud, exp e iss."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jose import jwt

from src.identity_access.infrastructure.adapters.agrofusion_sso_adapter import AgroFusionSsoAdapter
from src.shared.errors import AuthenticationError

_AUD = 'SGPMP'
_ISS = 'agrofusion-auth'


@pytest.fixture
def firmar(tmp_path, monkeypatch):
    clave = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    publica = tmp_path / 'agrofusion.pub'
    publica.write_bytes(clave.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo,
    ))
    monkeypatch.setenv('AGROFUSION_SSO_PUBLIC_KEY_PATH', str(publica))
    monkeypatch.setenv('AGROFUSION_PROJECT_CODE', _AUD)
    monkeypatch.setenv('AGROFUSION_ISSUER', _ISS)
    privada = clave.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption(),
    )

    def _firmar(sin: str = '') -> str:
        claims = {
            'sub': '42', 'email': 'sso@example.com', 'aud': _AUD, 'iss': _ISS,
            'exp': datetime.now(timezone.utc) + timedelta(minutes=2),
        }
        claims.pop(sin, None)
        return jwt.encode(claims, privada, algorithm='RS256')

    return _firmar


def test_token_con_todos_los_claims_sigue_aceptandose(firmar) -> None:
    identidad = AgroFusionSsoAdapter().verificar(firmar())
    assert identidad.sub_externo == '42'


@pytest.mark.parametrize('claim', ['aud', 'exp', 'iss'])
def test_token_sin_claim_obligatorio_es_rechazado(firmar, claim: str) -> None:
    with pytest.raises(AuthenticationError) as exc:
        AgroFusionSsoAdapter().verificar(firmar(sin=claim))
    assert exc.value.code == 'SSO_TOKEN_INVALIDO'
