"""Validación local de DTO, sin acceso a TEST."""
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[6]
sys.path.insert(0, str(ROOT))
from src.accounting_integration.infrastructure.dto.m07_dto import (  # noqa: E402
    DeprecarContratoDTO,
    RegistrarContratoDTO,
)


def cuerpo(version="4.0", gracia=30):
    return dict(contrato_version=version, tipo_cambio="MAJOR",
                fecha_vigencia=date.today() + timedelta(days=400),
                id_mapeo_anexo_aaef=2, mapeadores=["COMPRAS"],
                periodo_gracia_dias=gracia)


@pytest.mark.parametrize("version", ["4", "4.0.1", "v4.0", "4.x", "4.", ".4", ""])
def test_formato_invalido(version):
    with pytest.raises(ValidationError):
        RegistrarContratoDTO(**cuerpo(version))


def test_gracia_registro():
    with pytest.raises(ValidationError):
        RegistrarContratoDTO(**cuerpo(gracia=29))
    assert RegistrarContratoDTO(**cuerpo(gracia=30)).periodo_gracia_dias == 30


def test_gracia_deprecacion():
    with pytest.raises(ValidationError):
        DeprecarContratoDTO(dias_gracia=29)
    assert DeprecarContratoDTO(dias_gracia=30).dias_gracia == 30
