# | Fecha      | Nombre   | Que se hizo                                                     |
# |------------|----------|-----------------------------------------------------------------|
# | 2026-11-02 | Arekkazu | RFC-021 RF-110 C21.1: validaciones de las aristas de transmisión |
"""RF-110 mínimo: una arista une dos áreas activas, accesibles y de la misma finca."""
from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src.configuration.application.use_cases.topologia.desactivar_arista_transmision_use_case import (
    DesactivarAristaTransmisionUseCase,
)
from src.configuration.application.use_cases.topologia.listar_aristas_transmision_use_case import (
    ListarAristasTransmisionUseCase,
)
from src.configuration.application.use_cases.topologia.registrar_arista_transmision_use_case import (
    RegistrarAristaTransmisionUseCase,
)
from src.configuration.domain.entities.arista_transmision import AristaTransmision
from src.configuration.infrastructure.dto.registrar_arista_transmision_dto import RegistrarAristaTransmisionDTO
from src.shared.errors import BusinessRuleError, NotFoundError

AREAS = {
    2: SimpleNamespace(id_infraestructura=2, id_finca=1, es_activo=True),
    3: SimpleNamespace(id_infraestructura=3, id_finca=1, es_activo=True),
    8: SimpleNamespace(id_infraestructura=8, id_finca=9, es_activo=True),
    9: SimpleNamespace(id_infraestructura=9, id_finca=1, es_activo=False),
}


def _registrar(origen, destino, **cambios):
    repo = Mock()
    repo.guardar.side_effect = lambda a: a
    db = Mock()
    infra = SimpleNamespace(obtener_por_id=lambda id_area, ids_fincas_permitidas=None: AREAS.get(id_area))
    dto = RegistrarAristaTransmisionDTO(id_infraestructura_origen=origen, id_infraestructura_destino=destino,
                                        via="AGUA", intensidad=Decimal("0.6"), **cambios)
    arista = RegistrarAristaTransmisionUseCase(db, repo, infra).execute(dto, id_usuario=29)
    return arista, repo, db


def test_declara_la_arista_con_su_peso_y_hace_commit():
    arista, repo, db = _registrar(2, 3, factor_barrera=Decimal("0.5"), direccion="BIDIRECCIONAL")
    assert (arista.via, arista.direccion, arista.peso, arista.id_usuario) == ("AGUA", "BIDIRECCIONAL", Decimal("0.3"), 29)
    repo.guardar.assert_called_once()
    db.commit.assert_called_once()


@pytest.mark.parametrize(("origen", "destino", "error", "codigo"), [
    (2, 2, BusinessRuleError, "ARISTA_MISMA_AREA"),
    (2, 8, BusinessRuleError, "AREAS_DE_DISTINTA_FINCA"),
    (2, 9, BusinessRuleError, "AREA_INACTIVA"),
    (2, 77, NotFoundError, "AREA_NO_ENCONTRADA"),
])
def test_rechazos(origen, destino, error, codigo):
    with pytest.raises(error) as exc:
        _registrar(origen, destino)
    assert exc.value.code == codigo


def test_listar_fuera_del_alcance_es_404_y_desactivar_dos_veces_es_422():
    with pytest.raises(NotFoundError):
        ListarAristasTransmisionUseCase(Mock()).execute(5, ids_fincas_permitidas=[1])

    arista = AristaTransmision(2, 3, "AGUA", "DIRIGIDA", Decimal("0.6"), id_arista_transmision=1)
    repo = Mock()
    repo.obtener_por_id.return_value = arista
    repo.actualizar.side_effect = lambda a: a
    uc = DesactivarAristaTransmisionUseCase(Mock(), repo)
    assert uc.execute(1).es_activo is False
    with pytest.raises(BusinessRuleError):
        uc.execute(1)
