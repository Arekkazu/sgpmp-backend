"""RF-49 R3 / FA-04: compatibilidad biologica sensor-especie."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.biological_assets.application.use_cases.gestion.asociar_sensor_activo_use_case import (
    AsociarSensorActivoUseCase,
)
from src.biological_assets.domain.entities.activo_biologico import (
    ActivoBiologico,
    AsociacionSensorActivo,
)
from src.biological_assets.domain.repositories.infraestructura_consulta_port import (
    InfraestructuraConsulta,
)
from src.biological_assets.domain.repositories.sensor_consulta_port import (
    CompatibilidadSensorEspecie,
    SensorConsulta,
)
from src.biological_assets.domain.value_objects.estado_activo import EstadoActivo
from src.biological_assets.infrastructure.dto.asociar_sensor_activo_dto import AsociarSensorActivoDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import ConflictError, ValidationError


class ActivoRepoFake:
    def __init__(self, activo: ActivoBiologico) -> None:
        self.activo = activo

    def obtener_por_id(self, _id: int, *, ids_fincas_permitidas=None):
        return self.activo


class DbFake:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


class BitacoraFake:
    def __init__(self) -> None:
        self.eventos = []

    def registrar(self, evento) -> None:
        self.eventos.append(evento)


class SensorPortFake:
    def __init__(self, compatibilidad: CompatibilidadSensorEspecie | None) -> None:
        self.compatibilidad = compatibilidad
        self.consultas_compatibilidad = 0

    def obtener_sensor_con_contexto(self, _id: int):
        return SensorConsulta(
            id_sensor=7,
            nombre='Sensor avicola',
            es_activo=True,
            id_dispositivo_iot=3,
            dispositivo_es_activo=True,
            id_infraestructura_dispositivo=11,
            id_infraestructura_area=11,
        )

    def obtener_compatibilidad_especie(self, _sensor_id: int, _especie_id: int):
        self.consultas_compatibilidad += 1
        return self.compatibilidad


class InfraPortFake:
    def __init__(self, fincas: dict[int, int]) -> None:
        self.fincas = fincas

    def obtener_activa(self, id_infraestructura: int):
        return InfraestructuraConsulta(
            id_infraestructura=id_infraestructura,
            nombre=f'Infra {id_infraestructura}',
            tipo='Galpon',
            es_activo=True,
            id_finca=self.fincas[id_infraestructura],
        )


class AsociacionRepoFake:
    def __init__(self, conflicto: AsociacionSensorActivo | None = None) -> None:
        self.conflicto = conflicto
        self.guardados = 0

    def listar_activas_por_sensor(self, _sensor_id: int, _tipo: str):
        return [self.conflicto] if self.conflicto is not None else []

    def listar_activas_por_activo(self, _id_activo: int, _tipo: str):
        return []

    def obtener_activa_por_sensor_y_activo(self, _sensor_id: int, _id_activo: int):
        return None

    def guardar(self, entidad):
        self.guardados += 1
        return entidad


def _activo() -> ActivoBiologico:
    return ActivoBiologico(
        id_especie=40,
        tipo='INDIVIDUAL',
        origen_financiero='PROPIO',
        id_infraestructura=12,
        id_estado=EstadoActivo.ACTIVO,
        id_usuario=1,
        id_activo_biologico=279,
    )


def _dto() -> AsociarSensorActivoDTO:
    return AsociarSensorActivoDTO(
        tipo_activo='INDIVIDUAL',
        tipo_asociacion='DIRECTA',
        dispositivo_iot_id=3,
        sensor_id=7,
        id_infraestructura=12,
    )


def _usuario() -> UsuarioActual:
    return UsuarioActual(id_usuario=1, id_token=1, id_rol=1)


def _uc(
    compatibilidad: CompatibilidadSensorEspecie | None,
    *,
    fincas: dict[int, int] | None = None,
    conflicto: AsociacionSensorActivo | None = None,
    db=None,
    bitacora_repo=None,
):
    sensor_port = SensorPortFake(compatibilidad)
    repo = AsociacionRepoFake(conflicto)
    uc = AsociarSensorActivoUseCase(
        db=db,
        repo=repo,
        activo_repo=ActivoRepoFake(_activo()),
        sensor_port=sensor_port,
        infra_port=InfraPortFake(fincas or {11: 5, 12: 5}),
        bitacora_repo=bitacora_repo,
    )
    return uc, sensor_port, repo


def test_rechaza_sensor_parametrizado_para_otra_especie_con_http_400():
    uc, _, repo = _uc(CompatibilidadSensorEspecie(
        configurada=True,
        es_compatible=False,
        nombre_especie_activo='Bovino',
        especies_compatibles=('Ave',),
    ))

    with pytest.raises(ValidationError) as exc:
        uc.execute(279, _dto(), _usuario())

    assert exc.value.status_code == 400
    assert exc.value.code == 'INCOMPATIBILIDAD_ESPECIE_SENSOR'
    assert exc.value.field == 'sensor_id'
    assert exc.value.message == (
        'Incompatibilidad biológica. El sensor 7 está parametrizado para Ave, '
        'no es compatible con el activo 279 de tipo Bovino.'
    )
    assert repo.guardados == 0


def test_rechaza_sensor_sin_catalogo_configurado():
    uc, _, repo = _uc(CompatibilidadSensorEspecie(
        configurada=False,
        es_compatible=False,
        nombre_especie_activo='Bovino',
        especies_compatibles=(),
    ))

    with pytest.raises(ValidationError) as exc:
        uc.execute(279, _dto(), _usuario())

    assert exc.value.code == 'COMPATIBILIDAD_SENSOR_NO_CONFIGURADA'
    assert repo.guardados == 0


def test_conflicto_territorial_conserva_prioridad_sobre_compatibilidad():
    uc, sensor_port, _ = _uc(
        CompatibilidadSensorEspecie(
            configurada=True,
            es_compatible=False,
            nombre_especie_activo='Bovino',
            especies_compatibles=('Ave',),
        ),
        fincas={11: 1, 12: 57},
    )

    with pytest.raises(ConflictError) as exc:
        uc.execute(279, _dto(), _usuario())

    assert exc.value.code == 'INFRAESTRUCTURA_INCOMPATIBLE'
    assert sensor_port.consultas_compatibilidad == 0


def test_sensor_compatible_continua_hasta_las_reglas_de_cardinalidad():
    conflicto = AsociacionSensorActivo(
        id_activo_biologico=100,
        tipo_activo='INDIVIDUAL',
        tipo_asociacion='directa',
        dispositivo_iot_id=3,
        sensor_id=7,
        id_infraestructura=12,
        id_usuario=1,
        fecha_inicio=datetime.now(timezone.utc),
        estado_asociacion='ACTIVA',
        id_asociacion_activo_sensor=88,
    )
    uc, sensor_port, _ = _uc(CompatibilidadSensorEspecie(
        configurada=True,
        es_compatible=True,
        nombre_especie_activo='Bovino',
        especies_compatibles=('Bovino',),
    ), conflicto=conflicto)

    with pytest.raises(ConflictError) as exc:
        uc.execute(279, _dto(), _usuario())

    assert exc.value.code == 'SENSOR_YA_VINCULADO'
    assert sensor_port.consultas_compatibilidad == 1


def test_incompatibilidad_queda_registrada_como_rechazo_rf49():
    db = DbFake()
    bitacora = BitacoraFake()
    uc, _, _ = _uc(
        CompatibilidadSensorEspecie(
            configurada=True,
            es_compatible=False,
            nombre_especie_activo='Bovino',
            especies_compatibles=('Ave',),
        ),
        db=db,
        bitacora_repo=bitacora,
    )

    with pytest.raises(ValidationError):
        uc.execute(279, _dto(), _usuario())

    assert db.rollbacks == 1
    assert db.commits == 1
    assert len(bitacora.eventos) == 1
    evento = bitacora.eventos[0]
    assert evento.rf_origen == 'RF49'
    assert evento.tipo_evento == 'ASOCIACION_IOT_RECHAZADA'
    assert evento.resultado == 'RECHAZADO'
    assert evento.detalle_tecnico['error_code'] == 'INCOMPATIBILIDAD_ESPECIE_SENSOR'
