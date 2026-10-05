"""RF-21 v2.0 / RF-22 v1.2 (RFC-011): dispositivo de visión (CAMARA).

La categoría la da el tipo del catálogo. Una cámara exige resolución, fps y área
de cobertura válidos (400); un sensor los ignora. Varias cámaras van a la misma
área (N:1) y una cámara no admite sensores escalares.
"""
from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import pytest

from src.configuration.application.use_cases.dispositivos_iot.registrar_dispositivo_iot_use_case import (
    RegistrarDispositivoIotUseCase,
)
from src.configuration.application.use_cases.dispositivos_iot.registrar_sensor_use_case import RegistrarSensorUseCase
from src.configuration.domain.entities.tipo_dispositivo_iot import TipoDispositivoIot
from src.configuration.infrastructure.dto.registrar_dispositivo_iot_dto import RegistrarDispositivoIotDTO
from src.configuration.infrastructure.dto.registrar_sensor_dto import RegistrarSensorDTO
from src.shared.errors import BusinessRuleError, ValidationError
from tests.configuration.test_rf21_gateway_edge import (
    USUARIO,
    AuditoriaFake,
    DbFake,
    InfraRepoFake,
    RepoFake,
)

SENSOR, CAMARA = 1, 5
TIPOS = {
    SENSOR: TipoDispositivoIot(SENSOR, "GENERICO", 1, 60, 1, 120),
    CAMARA: TipoDispositivoIot(CAMARA, "CAMARA_VISION", 1, 1440, 1, 1440, categoria="CAMARA"),
}
VISION = {"resolucion": "1920x1080", "fps": 25, "area_cobertura_m2": Decimal("80.5")}


class _Tipos:
    def obtener_por_id(self, id_): return TIPOS.get(id_)


def _registrar(repo, serial, tipo, **vision):
    uc = RegistrarDispositivoIotUseCase(
        db=DbFake(), dispositivo_repo=repo, infra_repo=InfraRepoFake(), tipo_repo=_Tipos(),
        auditoria_repo=AuditoriaFake(),
    )
    dto = RegistrarDispositivoIotDTO(
        serial=serial, descripcion="Nodo de vision", id_infraestructura=1, id_tipo_dispositivo=tipo, **vision,
    )
    return uc.execute(dto, USUARIO)


def test_camara_valida_persiste_sus_atributos_de_vision():
    camara = _registrar(RepoFake(), "CAM-1", CAMARA, **VISION)
    assert (camara.resolucion, camara.fps, camara.area_cobertura_m2) == ("1920x1080", 25, Decimal("80.5"))
    assert camara._snapshot()["area_cobertura_m2"] == "80.5"


def test_varias_camaras_en_la_misma_area():
    repo = RepoFake()
    a = _registrar(repo, "CAM-1", CAMARA, **VISION)
    b = _registrar(repo, "CAM-2", CAMARA, **VISION)
    assert a.id_infraestructura == b.id_infraestructura == 1


@pytest.mark.parametrize(
    "cambio, campo",
    [
        ({"resolucion": None}, "resolucion"),
        ({"resolucion": "1080p"}, "resolucion"),
        ({"fps": None}, "fps"),
        ({"fps": 0}, "fps"),
        ({"fps": 61}, "fps"),
        ({"area_cobertura_m2": None}, "area_cobertura_m2"),
        ({"area_cobertura_m2": Decimal("0")}, "area_cobertura_m2"),
    ],
)
def test_camara_con_atributos_faltantes_o_fuera_de_rango_es_400(cambio, campo):
    with pytest.raises(ValidationError) as e:
        _registrar(RepoFake(), "CAM-1", CAMARA, **{**VISION, **cambio})
    assert e.value.code == "ATRIBUTOS_VISION_INVALIDOS" and e.value.status_code == 400
    assert e.value.field == campo and f"'{campo}'" in e.value.message


def test_sensor_ignora_los_atributos_de_vision():
    sensor = _registrar(RepoFake(), "SEN-1", SENSOR, resolucion="no-importa", fps=999, area_cobertura_m2=Decimal("-1"))
    assert (sensor.resolucion, sensor.fps, sensor.area_cobertura_m2) == (None, None, None)


def test_camara_no_admite_sensores_escalares():
    camara = SimpleNamespace(id_dispositivo_iot=7, id_tipo_dispositivo=CAMARA)
    uc = RegistrarSensorUseCase(
        db=DbFake(), sensor_repo=None, dispositivo_repo=SimpleNamespace(obtener_por_id=lambda _id: camara),
        tipo_repo=_Tipos(),
    )
    with pytest.raises(BusinessRuleError) as e:
        uc.execute(7, RegistrarSensorDTO(nombre="Temperatura", categoria="TEMPERATURA"), USUARIO)
    assert e.value.code == "CAMARA_SIN_SENSORES"


def test_tipo_de_dispositivo_inexistente_es_422():
    with pytest.raises(BusinessRuleError) as e:
        _registrar(RepoFake(), "SEN-9", 999)
    assert e.value.status_code == 422 and e.value.code == "TIPO_DISPOSITIVO_NO_ENCONTRADO"
    assert e.value.message.startswith("Error de catálogo")
