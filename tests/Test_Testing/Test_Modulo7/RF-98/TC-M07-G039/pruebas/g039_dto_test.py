"""Valida el cuerpo de deprecaci?n usado por G039."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[6]))
from src.accounting_integration.infrastructure.dto.m07_dto import DeprecarContratoDTO


def test_deprecacion_g039():
    dto = DeprecarContratoDTO.model_validate({"dias_gracia": 90})
    assert dto.dias_gracia == 90
