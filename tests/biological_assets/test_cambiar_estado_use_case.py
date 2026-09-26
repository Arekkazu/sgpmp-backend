"""RF-44: el cambio manual de estado pasa por el componente centralizado.

El use case ya no valida ni registra el histórico por su cuenta: delega en
``aplicar_cambio_estado``, que muta la entidad y registra ``modulo_origen``
``MANUAL``.
"""
from __future__ import annotations

from datetime import date

import pytest

from src.biological_assets.application.use_cases.gestion.cambiar_estado_use_case import CambiarEstadoUseCase
from src.biological_assets.domain.entities.activo_biologico import ActivoBiologico, HistoricoEstado
from src.biological_assets.infrastructure.dto.cambiar_estado_dto import CambiarEstadoDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import NotFoundError


class DbFake:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


class ActivoRepoFake:
    def __init__(self, activo: ActivoBiologico | None) -> None:
        self.activo = activo

    def obtener_por_id(self, _id: int):
        return self.activo


class HistoricoRepoFake:
    def __init__(self) -> None:
        self.registros: list[dict] = []

    def registrar(self, **kwargs) -> HistoricoEstado:
        self.registros.append(kwargs)
        return HistoricoEstado(
            id_activo_biologico=kwargs['id_activo'],
            id_estado_anterior=kwargs['id_estado_anterior'],
            id_estado_nuevo=kwargs['id_estado_nuevo'],
            fecha_cambio=kwargs['fecha'],
            modulo_origen=kwargs['modulo_origen'],
            id_usuario=kwargs['usuario_id'],
            motivo_cambio=kwargs['motivo'],
        )


def _activo(id_estado: int) -> ActivoBiologico:
    return ActivoBiologico(
        id_especie=1,
        tipo='INDIVIDUAL',
        origen_financiero='compra',
        id_infraestructura=1,
        id_estado=id_estado,
        id_usuario=1,
        id_activo_biologico=10,
    )


def _usuario() -> UsuarioActual:
    return UsuarioActual(id_usuario=7, id_token=1, id_rol=2)


def _dto(estado: str = 'INACTIVO') -> CambiarEstadoDTO:
    return CambiarEstadoDTO(estado_nuevo=estado, fecha_cambio_estado=date.today(), motivo_cambio='motivo')


def test_cambiar_estado_delega_y_registra_origen_manual() -> None:
    db = DbFake()
    activo = _activo(id_estado=1)
    historico = HistoricoRepoFake()
    uc = CambiarEstadoUseCase(db=db, repo=ActivoRepoFake(activo), historico_repo=historico)

    uc.execute(10, _dto('INACTIVO'), _usuario())

    assert activo.id_estado == 2
    assert historico.registros[0]['modulo_origen'] == 'MANUAL'
    assert historico.registros[0]['id_estado_nuevo'] == 2
    assert db.commits == 1
    assert db.rollbacks == 0


def test_cambiar_estado_activo_inexistente() -> None:
    db = DbFake()
    uc = CambiarEstadoUseCase(db=db, repo=ActivoRepoFake(None), historico_repo=HistoricoRepoFake())

    with pytest.raises(NotFoundError):
        uc.execute(999, _dto(), _usuario())

    assert db.rollbacks == 0
