"""Comprueba los DTO públicos usados por G041 con datos locales sintéticos."""
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[6]))
from src.accounting_integration.infrastructure.dto.m07_dto import (  # noqa: E402
    DeprecarContratoDTO, RegistrarContratoDTO,
)
from src.identity_access.infrastructure.dto.usuario_dto import (  # noqa: E402
    LoginDTO,
)


def test_contrato_y_deprecacion():
    alta = RegistrarContratoDTO.model_validate({
        "contrato_version": "6.0", "tipo_cambio": "MINOR",
        "fecha_vigencia": "2027-01-01", "id_mapeo_anexo_aaef": 2,
        "mapeadores": ["COMPRAS"], "periodo_gracia_dias": None,
        "descripcion": None,
    })
    assert alta.contrato_version == "6.0"
    assert DeprecarContratoDTO.model_validate({"dias_gracia": 90}).dias_gracia == 90
    with pytest.raises(ValidationError):
        RegistrarContratoDTO.model_validate({"contrato_version": "invalida"})


def test_login_exige_correo_electronico():
    assert LoginDTO.model_validate({"correo_electronico": "local@example.com", "contrasena": "LOCAL"}).correo_electronico == "local@example.com"
    with pytest.raises(ValidationError):
        LoginDTO.model_validate({"correo": "local@example.com", "contrasena": "LOCAL"})
