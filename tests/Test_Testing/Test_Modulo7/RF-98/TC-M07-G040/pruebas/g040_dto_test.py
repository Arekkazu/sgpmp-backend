"""Valida el DTO real del token de canal sin credenciales reales."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[6]))
from src.identity_access.infrastructure.dto.agrofusion_dto import AgroFusionTokenDTO
from src.identity_access.infrastructure.schema.agrofusion_schema import AgroFusionTokenResponse


def test_token_g040():
    dto = AgroFusionTokenDTO.model_validate({
        "client_id": "LOCAL_CLIENT", "client_secret": "LOCAL_SECRET",
        "email": "local@example.com",
    })
    assert dto.client_id == "LOCAL_CLIENT"
    assert dto.email == "local@example.com"
    respuesta = AgroFusionTokenResponse.model_validate({"access_token": "LOCAL_TOKEN", "expires_in": 300})
    assert respuesta.expires_in == 300
