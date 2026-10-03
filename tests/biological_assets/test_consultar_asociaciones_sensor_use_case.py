"""RF-49 (INC-M02-68-G91 / issue #218): antes de este fix, `GET
/activos-biologicos/{id_activo}/sensores` respondía 405 Method Not Allowed —
no existía ningún endpoint de lectura para las asociaciones sensor-activo,
aunque se persistían correctamente en `modulo2.asociaciones_activos_sensores`.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.biological_assets.application.use_cases.gestion.consultar_asociaciones_sensor_use_case import (
    ConsultarAsociacionesSensorUseCase,
)
from src.biological_assets.domain.entities.activo_biologico import ActivoBiologico, AsociacionSensorActivo
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import NotFoundError, ValidationError


class ActivoRepoFake:
    def __init__(self, activo: ActivoBiologico | None) -> None:
        self.activo = activo
        self.ids_fincas_recibidos = 'no-llamado'

    def obtener_por_id(self, _id: int, *, ids_fincas_permitidas=None):
        self.ids_fincas_recibidos = ids_fincas_permitidas
        return self.activo


class AsociacionRepoFake:
    def __init__(self, activas: list, todas: list, heredadas_activas=None, heredadas_todas=None) -> None:
        self.activas = activas
        self.todas = todas
        self.heredadas_activas = heredadas_activas or []
        self.heredadas_todas = heredadas_todas or []

    def listar_activas_por_activo(self, id_activo_biologico, tipo_asociacion=None):
        return self.activas

    def listar_todas_por_activo(self, id_activo_biologico):
        return self.todas

    def listar_activas_por_infraestructura(self, id_infraestructura):
        return self.heredadas_activas

    def listar_todas_por_infraestructura(self, id_infraestructura):
        return self.heredadas_todas


class BitacoraRepoFake:
    def __init__(self) -> None:
        self.registrados = []

    def registrar(self, evento) -> None:
        self.registrados.append(evento)


class DbFake:
    def commit(self) -> None:
        pass

    def rollback(self) -> None:
        pass


def _activo() -> ActivoBiologico:
    return ActivoBiologico(
        id_especie=1, tipo='INDIVIDUAL', origen_financiero='compra',
        id_infraestructura=1, id_estado=1, id_usuario=1, id_activo_biologico=10,
    )


def _asociacion(estado: str, id_asociacion: int) -> AsociacionSensorActivo:
    return AsociacionSensorActivo(
        id_asociacion_activo_sensor=id_asociacion,
        tipo_activo='INDIVIDUAL',
        tipo_asociacion='directa',
        dispositivo_iot_id=1,
        sensor_id=3,
        id_infraestructura=1,
        id_usuario=7,
        fecha_inicio=datetime.now(timezone.utc),
        id_activo_biologico=10,
        estado_asociacion=estado,
    )


def _asociacion_ambiental_infraestructura(estado: str, id_asociacion: int) -> AsociacionSensorActivo:
    """RF-49 Tipo B (INC-M02-66-G90/#217): asociación a nivel de
    infraestructura, sin activo puntual."""
    return AsociacionSensorActivo(
        id_asociacion_activo_sensor=id_asociacion,
        id_activo_biologico=None,
        tipo_activo=None,
        tipo_asociacion='ambiental',
        dispositivo_iot_id=1,
        sensor_id=9,
        id_infraestructura=1,
        id_usuario=7,
        fecha_inicio=datetime.now(timezone.utc),
        estado_asociacion=estado,
    )


def _usuario() -> UsuarioActual:
    return UsuarioActual(id_usuario=7, id_token=1, id_rol=2)


def test_tipo_consulta_activa_devuelve_solo_activas() -> None:
    activas = [_asociacion('ACTIVA', 1)]
    todas = [_asociacion('ACTIVA', 1), _asociacion('SUPERADA', 2)]
    uc = ConsultarAsociacionesSensorUseCase(
        db=DbFake(),
        repo=AsociacionRepoFake(activas, todas),
        activo_repo=ActivoRepoFake(_activo()),
        bitacora_repo=BitacoraRepoFake(),
    )

    tipo, id_activo, resultado = uc.execute(10, 'ACTIVA', _usuario())

    assert tipo == 'ACTIVA'
    assert id_activo == 10
    assert resultado == activas


def test_tipo_consulta_historial_devuelve_todas_incluyendo_superadas() -> None:
    activas = [_asociacion('ACTIVA', 1)]
    todas = [_asociacion('ACTIVA', 1), _asociacion('SUPERADA', 2)]
    uc = ConsultarAsociacionesSensorUseCase(
        db=DbFake(),
        repo=AsociacionRepoFake(activas, todas),
        activo_repo=ActivoRepoFake(_activo()),
    )

    _, _, resultado = uc.execute(10, 'HISTORIAL', _usuario())

    assert resultado == todas
    assert any(a.estado_asociacion == 'SUPERADA' for a in resultado)


def test_activo_inexistente_es_404() -> None:
    uc = ConsultarAsociacionesSensorUseCase(
        db=DbFake(),
        repo=AsociacionRepoFake([], []),
        activo_repo=ActivoRepoFake(None),
    )

    with pytest.raises(NotFoundError) as exc_info:
        uc.execute(999, 'ACTIVA', _usuario())

    assert exc_info.value.code == 'ACTIVO_NO_ENCONTRADO'


def test_tipo_consulta_invalido_es_400() -> None:
    uc = ConsultarAsociacionesSensorUseCase(
        db=DbFake(),
        repo=AsociacionRepoFake([], []),
        activo_repo=ActivoRepoFake(_activo()),
    )

    with pytest.raises(ValidationError) as exc_info:
        uc.execute(10, 'INVALIDO', _usuario())

    assert exc_info.value.code == 'TIPO_CONSULTA_INVALIDO'


def test_sin_asociaciones_devuelve_lista_vacia_no_error() -> None:
    uc = ConsultarAsociacionesSensorUseCase(
        db=DbFake(),
        repo=AsociacionRepoFake([], []),
        activo_repo=ActivoRepoFake(_activo()),
    )

    _, _, resultado = uc.execute(10, 'ACTIVA', _usuario())

    assert resultado == []


def test_alcance_de_finca_se_propaga_al_repo_de_activos() -> None:
    activo_repo = ActivoRepoFake(_activo())
    uc = ConsultarAsociacionesSensorUseCase(
        db=DbFake(),
        repo=AsociacionRepoFake([], []),
        activo_repo=activo_repo,
    )

    uc.execute(10, 'ACTIVA', _usuario(), ids_fincas_permitidas=[1, 2])

    assert activo_repo.ids_fincas_recibidos == [1, 2]


def test_incluye_asociaciones_ambientales_heredadas_de_la_infraestructura() -> None:
    """RF-49 Tipo B (INC-M02-66-G90/#217): un sensor asociado a la
    infraestructura del activo (id_activo_biologico=None) debe aparecer al
    consultar cualquier activo que resida en esa infraestructura."""
    propia = [_asociacion('ACTIVA', 1)]
    heredada = [_asociacion_ambiental_infraestructura('ACTIVA', 2)]
    uc = ConsultarAsociacionesSensorUseCase(
        db=DbFake(),
        repo=AsociacionRepoFake(propia, [], heredadas_activas=heredada),
        activo_repo=ActivoRepoFake(_activo()),
    )

    _, _, resultado = uc.execute(10, 'ACTIVA', _usuario())

    assert resultado == [*propia, *heredada]
    assert any(a.id_activo_biologico is None and a.tipo_asociacion == 'ambiental' for a in resultado)


def test_historial_incluye_heredadas_superadas_de_la_infraestructura() -> None:
    todas = [_asociacion('ACTIVA', 1)]
    heredadas_todas = [
        _asociacion_ambiental_infraestructura('ACTIVA', 2),
        _asociacion_ambiental_infraestructura('SUPERADA', 3),
    ]
    uc = ConsultarAsociacionesSensorUseCase(
        db=DbFake(),
        repo=AsociacionRepoFake([], todas, heredadas_todas=heredadas_todas),
        activo_repo=ActivoRepoFake(_activo()),
    )

    _, _, resultado = uc.execute(10, 'HISTORIAL', _usuario())

    assert resultado == [*todas, *heredadas_todas]


def test_consulta_exitosa_queda_registrada_en_bitacora() -> None:
    bitacora = BitacoraRepoFake()
    uc = ConsultarAsociacionesSensorUseCase(
        db=DbFake(),
        repo=AsociacionRepoFake([_asociacion('ACTIVA', 1)], []),
        activo_repo=ActivoRepoFake(_activo()),
        bitacora_repo=bitacora,
    )

    uc.execute(10, 'ACTIVA', _usuario())

    assert len(bitacora.registrados) == 1
    assert bitacora.registrados[0].rf_origen == 'RF49'
    assert bitacora.registrados[0].tipo_evento == 'ASOCIACIONES_SENSOR_CONSULTADAS'
