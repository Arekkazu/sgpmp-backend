"""RF-22 / #1671 — Reasignación real de sensores entre áreas productivas.

`AsociarSensorAreaUseCase` bloqueaba con 422 `SENSOR_INFRAESTRUCTURA_FIJA`
cualquier intento de asociar un sensor a un área distinta de la primera que
tuvo, contradiciendo el propio docstring del módulo ("termina la anterior y
crea la nueva") y el flujo alterno del RF ("¿Desea reasignarlo? Esta acción
finalizará la asociación anterior automáticamente"). `SensorArea.terminar()`
y `SensorAreaRepository.actualizar()` ya existían para esto — el caso de uso
simplemente no los usaba.

Verifica con fakes (sin BD):
- sin asociación previa → crea la primera;
- misma área activa → 409 ASOCIACION_DUPLICADA;
- área distinta sin confirmar → 409 REASIGNACION_REQUIERE_CONFIRMACION, sin tocar nada;
- área distinta con confirmar=True → termina la anterior y crea la nueva.
"""
from __future__ import annotations

import pytest

from src.configuration.application.use_cases.sensores.asociar_sensor_area_use_case import AsociarSensorAreaUseCase
from src.configuration.domain.entities.infraestructura import Infraestructura
from src.configuration.domain.entities.sensor import Sensor
from src.configuration.domain.entities.sensor_area import SensorArea
from src.configuration.domain.value_objects.nombre_infraestructura import NombreInfraestructura
from src.configuration.domain.value_objects.punto_instalacion import PuntoInstalacion
from src.configuration.domain.value_objects.superficie import Superficie
from src.configuration.infrastructure.dto.asociar_sensor_area_dto import AsociarSensorAreaDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import ConflictError

USUARIO = UsuarioActual(id_usuario=1, id_token=1, id_rol=1)

ID_DISPOSITIVO = 3
ID_AREA_1 = 10
ID_AREA_2 = 20


class DbFake:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


class SensorRepoFake:
    def __init__(self, sensor: Sensor) -> None:
        self._s = sensor

    def obtener_por_id(self, _id):
        return self._s


class InfraRepoFake:
    def __init__(self, *areas: Infraestructura) -> None:
        self._por_id = {a.id_infraestructura: a for a in areas}

    def obtener_por_id(self, id_infraestructura):
        return self._por_id.get(id_infraestructura)


class SensorAreaRepoFake:
    """Sostiene, a lo sumo, una asociación activa — la que el escenario precargue."""

    def __init__(self, activa: SensorArea | None = None) -> None:
        self._activa = activa
        self.guardadas: list[SensorArea] = []
        self.actualizadas: list[SensorArea] = []

    def obtener_asociacion_activa(self, _id_sensor):
        return self._activa

    def guardar(self, sensor_area: SensorArea) -> SensorArea:
        sensor_area.id_sensores_area_asociada = len(self.guardadas) + 100
        self.guardadas.append(sensor_area)
        return sensor_area

    def actualizar(self, sensor_area: SensorArea) -> SensorArea:
        self.actualizadas.append(sensor_area)
        return sensor_area

    def listar_por_sensor(self, _id_sensor):
        return self.guardadas + self.actualizadas


class AuditoriaRepoFake:
    def __init__(self) -> None:
        self.registros: list[dict] = []

    def registrar(self, **kwargs):
        self.registros.append(kwargs)


def _sensor() -> Sensor:
    s = Sensor.crear(nombre="Sensor pH", id_dispositivo_iot=ID_DISPOSITIVO)
    s.id_sensores = 1
    return s


def _area(id_infraestructura: int, nombre: str, activo: bool = True) -> Infraestructura:
    a = Infraestructura.crear(
        nombre=NombreInfraestructura(nombre),
        tipo="Estanque",
        superficie=Superficie(10),
        id_finca=1,
    )
    a.id_infraestructura = id_infraestructura
    a.es_activo = activo
    return a


def _asociacion_activa(id_infraestructura: int) -> SensorArea:
    a = SensorArea.crear(
        id_sensor=1,
        id_dispositivo_iot=ID_DISPOSITIVO,
        id_infraestructura=id_infraestructura,
        punto_instalacion=PuntoInstalacion("Punto original"),
        id_usuario=1,
    )
    a.id_sensores_area_asociada = 999
    return a


def _use_case(sensor_area_repo: SensorAreaRepoFake, *areas: Infraestructura) -> tuple[AsociarSensorAreaUseCase, DbFake]:
    db = DbFake()
    uc = AsociarSensorAreaUseCase(
        db=db,
        sensor_repo=SensorRepoFake(_sensor()),
        sensor_area_repo=sensor_area_repo,
        infra_repo=InfraRepoFake(*areas),
        auditoria_repo=AuditoriaRepoFake(),
    )
    return uc, db


def test_sin_asociacion_previa_crea_la_primera():
    area = _area(ID_AREA_1, "Estanque Norte")
    uc, db = _use_case(SensorAreaRepoFake(activa=None), area)
    dto = AsociarSensorAreaDTO(id_dispositivo_iot=ID_DISPOSITIVO, id_infraestructura=ID_AREA_1, punto_instalacion="Esquina norte")

    resultado = uc.execute(1, dto, USUARIO)

    assert resultado.id_infraestructura == ID_AREA_1
    assert db.commits == 1
    assert db.rollbacks == 0


def test_misma_area_activa_409_asociacion_duplicada():
    area = _area(ID_AREA_1, "Estanque Norte")
    activa = _asociacion_activa(ID_AREA_1)
    uc, _db = _use_case(SensorAreaRepoFake(activa=activa), area)
    dto = AsociarSensorAreaDTO(id_dispositivo_iot=ID_DISPOSITIVO, id_infraestructura=ID_AREA_1, punto_instalacion="Otro punto")

    with pytest.raises(ConflictError) as exc:
        uc.execute(1, dto, USUARIO)

    assert exc.value.code == "ASOCIACION_DUPLICADA"
    assert exc.value.status_code == 409


def test_area_distinta_sin_confirmar_409_pide_confirmacion_sin_tocar_nada():
    area_1 = _area(ID_AREA_1, "Estanque Norte")
    area_2 = _area(ID_AREA_2, "Estanque Sur")
    activa = _asociacion_activa(ID_AREA_1)
    repo = SensorAreaRepoFake(activa=activa)
    uc, db = _use_case(repo, area_1, area_2)
    dto = AsociarSensorAreaDTO(id_dispositivo_iot=ID_DISPOSITIVO, id_infraestructura=ID_AREA_2, punto_instalacion="Esquina sur")

    with pytest.raises(ConflictError) as exc:
        uc.execute(1, dto, USUARIO)

    assert exc.value.code == "REASIGNACION_REQUIERE_CONFIRMACION"
    assert exc.value.status_code == 409
    assert "Estanque Norte" in exc.value.message
    assert repo.actualizadas == []
    assert repo.guardadas == []
    assert db.commits == 0


def test_area_distinta_confirmada_termina_la_anterior_y_crea_la_nueva():
    area_1 = _area(ID_AREA_1, "Estanque Norte")
    area_2 = _area(ID_AREA_2, "Estanque Sur")
    activa = _asociacion_activa(ID_AREA_1)
    repo = SensorAreaRepoFake(activa=activa)
    uc, db = _use_case(repo, area_1, area_2)
    dto = AsociarSensorAreaDTO(
        id_dispositivo_iot=ID_DISPOSITIVO, id_infraestructura=ID_AREA_2, punto_instalacion="Esquina sur", confirmar=True
    )

    resultado = uc.execute(1, dto, USUARIO)

    assert resultado.id_infraestructura == ID_AREA_2
    assert len(repo.actualizadas) == 1
    assert repo.actualizadas[0].tiene_estado is False
    assert repo.actualizadas[0].fecha_finalizacion is not None
    assert len(repo.guardadas) == 1
    assert db.commits == 1
    assert db.rollbacks == 0


def test_area_inactiva_no_permite_asociar():
    from src.shared.errors import BusinessRuleError

    area_inactiva = _area(ID_AREA_1, "Estanque Norte", activo=False)
    uc, _db = _use_case(SensorAreaRepoFake(activa=None), area_inactiva)
    dto = AsociarSensorAreaDTO(id_dispositivo_iot=ID_DISPOSITIVO, id_infraestructura=ID_AREA_1, punto_instalacion="Punto")

    with pytest.raises(BusinessRuleError) as exc:
        uc.execute(1, dto, USUARIO)

    assert exc.value.code == "AREA_NO_DISPONIBLE"
