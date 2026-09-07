"""RF-45: el registro de baja delega el cambio de estado en el componente centralizado.

En una baja total (individual o lote que llega a cero) el use case delega la
transición a ``BAJA`` en ``aplicar_cambio_estado`` con ``modulo_origen='RF-45'``.
"""
from __future__ import annotations

from datetime import date

from src.biological_assets.application.use_cases.gestion.registrar_evento_baja_use_case import (
    RegistrarEventoBajaUseCase,
)
from src.biological_assets.domain.entities.activo_biologico import (
    ActivoBiologico,
    DetallePoblacional,
    EventoActivo,
    HistoricoEstado,
)
from src.biological_assets.domain.value_objects.estado_activo import EstadoActivo
from src.biological_assets.infrastructure.dto.registrar_evento_baja_dto import RegistrarEventoBajaDTO
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

    def obtener_por_id(self, _id: int):
        return self.activo

    def obtener_fase_activa(self, _id: int):
        return None

    def cerrar_gestion_activa(self, id_activo, fecha_fin, motivo, usuario_id) -> None:
        pass

    def actualizar_detalle_poblacional(self, activo: ActivoBiologico) -> ActivoBiologico:
        return activo


class EventoRepoFake:
    def __init__(self) -> None:
        self.guardado: EventoActivo | None = None

    def obtener_ultima_fecha(self, _id: int):
        return None

    def guardar(self, evento: EventoActivo) -> EventoActivo:
        self.guardado = evento
        return evento


class InfraPortFake:
    def obtener_activa(self, _id: int):
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


def _activo_individual(id_estado: int) -> ActivoBiologico:
    return ActivoBiologico(
        id_especie=1,
        tipo='INDIVIDUAL',
        origen_financiero='compra',
        id_infraestructura=1,
        id_estado=id_estado,
        id_usuario=1,
        id_activo_biologico=10,
    )


def _activo_lote(id_estado: int, cantidad_actual: int) -> ActivoBiologico:
    return ActivoBiologico(
        id_especie=1,
        tipo='POBLACIONAL',
        origen_financiero='compra',
        id_infraestructura=1,
        id_estado=id_estado,
        id_usuario=1,
        id_activo_biologico=10,
        detalle_poblacional=DetallePoblacional(
            cantidad_inicial=cantidad_actual,
            cantidad_actual=cantidad_actual,
        ),
    )


def _usuario() -> UsuarioActual:
    return UsuarioActual(id_usuario=7, id_token=1, id_rol=2)


def _dto(cantidad_afectada=None) -> RegistrarEventoBajaDTO:
    return RegistrarEventoBajaDTO(
        tipo_baja='venta',
        fecha_baja=date.today(),
        motivo_baja='motivo de baja',
        cantidad_afectada=cantidad_afectada,
    )


def _uc(db, activo, evento_repo, historico) -> RegistrarEventoBajaUseCase:
    return RegistrarEventoBajaUseCase(
        db=db,
        activo_repo=ActivoRepoFake(activo),
        evento_repo=evento_repo,
        infra_port=InfraPortFake(),
        historico_repo=historico,
    )


def test_baja_individual_total_delega_y_registra_origen_rf45() -> None:
    db = DbFake()
    activo = _activo_individual(id_estado=EstadoActivo.ACTIVO)
    evento_repo = EventoRepoFake()
    historico = HistoricoRepoFake()
    uc = _uc(db, activo, evento_repo, historico)

    uc.execute(10, _dto(), _usuario())

    assert activo.id_estado == EstadoActivo.BAJA
    assert historico.registros[0]['modulo_origen'] == 'RF-45'
    assert historico.registros[0]['id_estado_nuevo'] == EstadoActivo.BAJA
    assert evento_repo.guardado is not None
    assert evento_repo.guardado.baja.cantidad_afectada == 1
    assert db.commits == 1


def test_baja_lote_total_delega_y_registra_origen_rf45() -> None:
    db = DbFake()
    activo = _activo_lote(id_estado=EstadoActivo.ACTIVO, cantidad_actual=5)
    evento_repo = EventoRepoFake()
    historico = HistoricoRepoFake()
    uc = _uc(db, activo, evento_repo, historico)

    uc.execute(10, _dto(cantidad_afectada=None), _usuario())

    assert activo.detalle_poblacional.cantidad_actual == 0
    assert activo.id_estado == EstadoActivo.BAJA
    assert historico.registros[0]['modulo_origen'] == 'RF-45'
    assert db.commits == 1


def test_baja_lote_parcial_no_cambia_estado() -> None:
    db = DbFake()
    activo = _activo_lote(id_estado=EstadoActivo.ACTIVO, cantidad_actual=5)
    evento_repo = EventoRepoFake()
    historico = HistoricoRepoFake()
    uc = _uc(db, activo, evento_repo, historico)

    uc.execute(10, _dto(cantidad_afectada=2), _usuario())

    assert activo.detalle_poblacional.cantidad_actual == 3
    assert activo.id_estado == EstadoActivo.ACTIVO
    assert historico.registros == []
    assert db.commits == 1
