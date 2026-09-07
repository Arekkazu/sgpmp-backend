"""RF-38: el cierre de ciclo delega el cambio de estado en el componente centralizado.

El use case valida sus precondiciones (estado, sensores, fase, fecha) y luego
delega la transición a ``CERRADO`` en ``aplicar_cambio_estado`` con
``modulo_origen='RF-38'``.
"""
from __future__ import annotations

from datetime import date

import pytest

from src.biological_assets.application.use_cases.gestion.cerrar_ciclo_use_case import CerrarCicloUseCase
from src.biological_assets.domain.entities.activo_biologico import ActivoBiologico, HistoricoEstado
from src.biological_assets.domain.value_objects.estado_activo import EstadoActivo
from src.biological_assets.infrastructure.dto.cerrar_ciclo_dto import CerrarCicloDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual


class DbFake:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


class ActivoRepoFake:
    def __init__(self, activo: ActivoBiologico) -> None:
        self.activo = activo
        self.cierres = 0

    def obtener_por_id(self, _id: int):
        return self.activo

    def tiene_sensores_activos(self, _id: int) -> bool:
        return False

    def obtener_fase_activa(self, _id: int):
        return 'fase-activa'

    def cerrar_gestion_activa(self, id_activo, fecha_fin, motivo, usuario_id) -> None:
        self.cierres += 1


class EventoRepoFake:
    def obtener_ultima_fecha(self, _id: int):
        return None


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


def _dto() -> CerrarCicloDTO:
    return CerrarCicloDTO(fecha_cierre=date.today(), motivo_cierre='venta')


def test_cierre_delega_y_registra_origen_rf38() -> None:
    db = DbFake()
    activo = _activo(id_estado=EstadoActivo.ACTIVO)
    repo = ActivoRepoFake(activo)
    historico = HistoricoRepoFake()
    uc = CerrarCicloUseCase(db=db, repo=repo, evento_repo=EventoRepoFake(), historico_repo=historico)

    uc.execute(10, _dto(), _usuario())

    assert activo.id_estado == EstadoActivo.CERRADO
    assert repo.cierres == 1
    assert historico.registros[0]['modulo_origen'] == 'RF-38'
    assert historico.registros[0]['id_estado_nuevo'] == EstadoActivo.CERRADO
    assert db.commits == 1


def test_cierre_rechazado_sin_fase_activa() -> None:
    from src.shared.errors import BusinessRuleError

    db = DbFake()
    activo = _activo(id_estado=EstadoActivo.ACTIVO)
    repo = ActivoRepoFake(activo)
    repo.obtener_fase_activa = lambda _id: None
    uc = CerrarCicloUseCase(db=db, repo=repo, evento_repo=EventoRepoFake(), historico_repo=HistoricoRepoFake())

    with pytest.raises(BusinessRuleError):
        uc.execute(10, _dto(), _usuario())

    assert activo.id_estado == EstadoActivo.ACTIVO
    assert db.rollbacks == 0
