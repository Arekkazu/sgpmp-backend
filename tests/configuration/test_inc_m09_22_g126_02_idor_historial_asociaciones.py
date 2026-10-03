"""INC-M09-22-G126-02 — IDOR en GET /configuracion/sensores/{id}/asociaciones.

Un usuario con rol Productor sin relación con ninguna finca podía consultar
el historial completo de asociaciones de un sensor de una finca ajena,
cambiando el ID en la URL: `ConsultarAsociacionesUseCase.listar_por_sensor()`
no recibía el usuario autenticado, así que no había forma de filtrar por
finca. Verifica, con fakes (sin BD), el mismo patrón de alcance por fincas
permitidas que ya usa `ConsultarFincasUseCase.obtener()` (INC-M02-61-G52: las
fincas permitidas salen de `modulo9.usuarios_fincas`, ya no del dueño).
"""
from __future__ import annotations

import pytest

from src.configuration.application.use_cases.sensores.asociar_sensor_area_use_case import ConsultarAsociacionesUseCase
from src.configuration.domain.entities.dispositivo_iot import DispositivoIot
from src.configuration.domain.entities.infraestructura import Infraestructura
from src.configuration.domain.entities.sensor import Sensor
from src.configuration.domain.value_objects.nombre_infraestructura import NombreInfraestructura
from src.configuration.domain.value_objects.serial_dispositivo import SerialDispositivo
from src.configuration.domain.value_objects.superficie import Superficie
from src.shared.errors import NotFoundError

ID_SENSOR = 1
ID_DISPOSITIVO = 5
ID_AREA = 10
ID_FINCA = 7
ID_FINCA_AJENA = 8


class SensorRepoFake:
    def __init__(self, sensor) -> None:
        self._s = sensor

    def obtener_por_id(self, _id):
        return self._s


class DispositivoRepoFake:
    def __init__(self, dispositivo) -> None:
        self._d = dispositivo

    def obtener_por_id(self, _id):
        return self._d


class InfraRepoFake:
    def __init__(self, area) -> None:
        self._a = area

    def obtener_por_id(self, _id):
        return self._a


class SensorAreaRepoFake:
    def __init__(self) -> None:
        self.listar_llamado_con: list[int] = []

    def listar_por_sensor(self, id_sensor: int):
        self.listar_llamado_con.append(id_sensor)
        return ["asociacion-1", "asociacion-2"]


def _sensor() -> Sensor:
    s = Sensor.crear(nombre="Sensor pH", id_dispositivo_iot=ID_DISPOSITIVO)
    s.id_sensores = ID_SENSOR
    return s


def _dispositivo() -> DispositivoIot:
    d = DispositivoIot.crear(
        serial=SerialDispositivo("SN-IDOR-1"),
        descripcion="Dispositivo de prueba",
        id_infraestructura=ID_AREA,
        id_tipo_dispositivo=1,
    )
    d.id_dispositivo_iot = ID_DISPOSITIVO
    return d


def _area() -> Infraestructura:
    a = Infraestructura.crear(
        nombre=NombreInfraestructura("Estanque de prueba"),
        tipo="Estanque",
        superficie=Superficie(10),
        id_finca=ID_FINCA,
    )
    a.id_infraestructura = ID_AREA
    return a


def _use_case() -> tuple[ConsultarAsociacionesUseCase, SensorAreaRepoFake]:
    sensor_area_repo = SensorAreaRepoFake()
    uc = ConsultarAsociacionesUseCase(
        db=None,
        sensor_area_repo=sensor_area_repo,
        sensor_repo=SensorRepoFake(_sensor()),
        dispositivo_repo=DispositivoRepoFake(_dispositivo()),
        infra_repo=InfraRepoFake(_area()),
    )
    return uc, sensor_area_repo


def test_usuario_con_acceso_a_la_finca_puede_consultar() -> None:
    uc, repo = _use_case()

    resultado = uc.listar_por_sensor(ID_SENSOR, ids_fincas_permitidas=[ID_FINCA])

    assert resultado == ["asociacion-1", "asociacion-2"]
    assert repo.listar_llamado_con == [ID_SENSOR]


def test_usuario_sin_acceso_a_la_finca_recibe_404_no_200() -> None:
    uc, repo = _use_case()

    with pytest.raises(NotFoundError) as exc:
        uc.listar_por_sensor(ID_SENSOR, ids_fincas_permitidas=[ID_FINCA_AJENA])

    assert exc.value.code == "SENSOR_NO_ENCONTRADO"
    assert exc.value.status_code == 404
    assert repo.listar_llamado_con == []  # nunca llega a leer el historial


def test_admin_sin_filtro_ve_cualquier_sensor() -> None:
    uc, repo = _use_case()

    resultado = uc.listar_por_sensor(ID_SENSOR, ids_fincas_permitidas=None)

    assert resultado == ["asociacion-1", "asociacion-2"]
    assert repo.listar_llamado_con == [ID_SENSOR]


if __name__ == "__main__":
    test_usuario_con_acceso_a_la_finca_puede_consultar()
    test_usuario_sin_acceso_a_la_finca_recibe_404_no_200()
    test_admin_sin_filtro_ve_cualquier_sensor()
    print("OK")
