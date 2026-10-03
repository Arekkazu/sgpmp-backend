"""RF-49 CU11 Flujo Alterno "Dispositivo IoT Fuera de Línea" (INC-M02-35-G84 v2):
sin heartbeat en los últimos 30 min, la asociación igual se crea (HTTP 201) pero
la respuesta debe incluir una advertencia informativa -- antes hardcodeada a
None sin consultar M03.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.biological_assets.application.use_cases.gestion.asociar_sensor_activo_use_case import (
    AsociarSensorActivoUseCase,
)
from src.biological_assets.domain.entities.activo_biologico import ActivoBiologico
from src.biological_assets.domain.repositories.dispositivo_iot_estado_port import EstadoDispositivoIot
from src.biological_assets.domain.repositories.infraestructura_consulta_port import InfraestructuraConsulta
from src.biological_assets.domain.repositories.sensor_consulta_port import (
    CompatibilidadSensorEspecie,
    SensorConsulta,
)
from src.biological_assets.domain.value_objects.estado_activo import EstadoActivo
from src.biological_assets.infrastructure.dto.asociar_sensor_activo_dto import AsociarSensorActivoDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual

_COMPATIBILIDAD_OK = CompatibilidadSensorEspecie(
    configurada=True, es_compatible=True,
    nombre_especie_activo='Bovino', especies_compatibles=('Bovino',),
)


class ActivoRepoFake:
    def __init__(self, activo: ActivoBiologico) -> None:
        self.activo = activo

    def obtener_por_id(self, _id: int, *, ids_fincas_permitidas=None):
        return self.activo


class SensorPortFake:
    def __init__(self, id_dispositivo_iot: int) -> None:
        self.id_dispositivo_iot = id_dispositivo_iot

    def obtener_sensor_con_contexto(self, _id: int):
        return SensorConsulta(
            id_sensor=7, nombre='Sensor', es_activo=True,
            id_dispositivo_iot=self.id_dispositivo_iot, dispositivo_es_activo=True,
            id_infraestructura_dispositivo=11, id_infraestructura_area=11,
        )

    def obtener_compatibilidad_especie(self, _sensor_id: int, _especie_id: int):
        return _COMPATIBILIDAD_OK


class InfraPortFake:
    def obtener_activa(self, id_infraestructura: int):
        return InfraestructuraConsulta(
            id_infraestructura=id_infraestructura, nombre='Infra', tipo='Galpon',
            es_activo=True, id_finca=5,
        )


class AsociacionRepoFake:
    def listar_activas_por_sensor(self, _sensor_id: int, _tipo: str):
        return []

    def listar_activas_por_activo(self, _id_activo: int, _tipo: str):
        return []

    def obtener_activa_por_sensor_y_activo(self, _sensor_id: int, _id_activo: int):
        return None

    def guardar(self, entidad):
        entidad.id_asociacion_activo_sensor = 99
        return entidad

    def registrar_auditoria(self, **kwargs):
        pass


class DbFake:
    def commit(self) -> None:
        pass

    def rollback(self) -> None:
        pass


class DispositivoEstadoPortFake:
    def __init__(self, estado: EstadoDispositivoIot | None) -> None:
        self.estado = estado

    def obtener_estado(self, _id_dispositivo_iot: int):
        return self.estado


def _activo() -> ActivoBiologico:
    return ActivoBiologico(
        id_especie=40, tipo='INDIVIDUAL', origen_financiero='PROPIO',
        id_infraestructura=11, id_estado=EstadoActivo.ACTIVO, id_usuario=1,
        id_activo_biologico=279,
    )


def _dto() -> AsociarSensorActivoDTO:
    return AsociarSensorActivoDTO(
        tipo_activo='INDIVIDUAL', tipo_asociacion='DIRECTA',
        dispositivo_iot_id=3, sensor_id=7, id_infraestructura=11,
    )


def _uc(dispositivo_estado_port):
    return AsociarSensorActivoUseCase(
        db=DbFake(),
        repo=AsociacionRepoFake(),
        activo_repo=ActivoRepoFake(_activo()),
        sensor_port=SensorPortFake(id_dispositivo_iot=3),
        infra_port=InfraPortFake(),
        dispositivo_estado_port=dispositivo_estado_port,
    )


def test_sin_puerto_configurado_no_hay_advertencia():
    resultado = _uc(dispositivo_estado_port=None).execute(279, _dto(), UsuarioActual(id_usuario=1, id_token=1, id_rol=1))
    assert resultado.advertencia is None


def test_dispositivo_con_heartbeat_reciente_no_hay_advertencia():
    estado = EstadoDispositivoIot(id_dispositivo_iot=3, fecha_ultimo_contacto=datetime.now(timezone.utc) - timedelta(minutes=5))
    resultado = _uc(DispositivoEstadoPortFake(estado)).execute(279, _dto(), UsuarioActual(id_usuario=1, id_token=1, id_rol=1))
    assert resultado.advertencia is None


def test_dispositivo_desconectado_hace_mas_de_30_min_devuelve_advertencia():
    hace_40_min = datetime.now(timezone.utc) - timedelta(minutes=40)
    estado = EstadoDispositivoIot(id_dispositivo_iot=3, fecha_ultimo_contacto=hace_40_min)

    resultado = _uc(DispositivoEstadoPortFake(estado)).execute(279, _dto(), UsuarioActual(id_usuario=1, id_token=1, id_rol=1))

    assert resultado.id_asociacion_activo_sensor == 99  # la asociación SÍ se crea (HTTP 201, no se bloquea)
    assert resultado.advertencia is not None
    assert 'dispositivo 3' in resultado.advertencia
    assert 'desconectado desde las' in resultado.advertencia
    assert hace_40_min.strftime('%H:%M:%S') in resultado.advertencia


def test_dispositivo_sin_registro_de_estado_en_m03_no_hay_advertencia():
    resultado = _uc(DispositivoEstadoPortFake(None)).execute(279, _dto(), UsuarioActual(id_usuario=1, id_token=1, id_rol=1))
    assert resultado.advertencia is None
