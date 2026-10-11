"""RF-05: el teléfono es opcional en la edición de perfil.

El formulario envía ``""`` cuando el campo queda vacío; antes el validador lo
rechazaba como "Número telefónico inválido" y no dejaba guardar nada.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.identity_access.infrastructure.dto.perfil_dto import EditarPerfilAdminDTO, EditarPerfilDTO

_BASE = {"nombre": "Ana", "apellidos": "Ruiz", "version": 1}


@pytest.mark.parametrize("dto_cls", [EditarPerfilDTO, EditarPerfilAdminDTO])
@pytest.mark.parametrize("vacio", ["", "   "])
def test_telefono_vacio_es_valido(dto_cls, vacio: str) -> None:
    assert dto_cls(**_BASE, telefono=vacio).telefono == ""


def test_telefono_ausente_sigue_siendo_no_cambiar() -> None:
    assert EditarPerfilDTO(**_BASE).telefono is None


@pytest.mark.parametrize("invalido", ["12345", "abc1234567", "1234567890123456"])
def test_telefono_escrito_sigue_validandose(invalido: str) -> None:
    with pytest.raises(ValidationError, match="Número telefónico inválido"):
        EditarPerfilDTO(**_BASE, telefono=invalido)


def test_telefono_valido_se_conserva_sin_espacios() -> None:
    assert EditarPerfilDTO(**_BASE, telefono=" 3001234567 ").telefono == "3001234567"
