"""INC-M09-77-G137 (#513): ingesta de observaciones de visión (RF-53/56/62 v2.0) que
alimenta la calibración VISION de RF-24 en vez del stub vacío."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from main import app
from src.configuration.application.use_cases.sensores.calibrar_vision_use_case import CalibrarVisionUseCase
from src.configuration.domain.entities import observacion_vision as obs_m09
from src.configuration.domain.value_objects.calibracion_vision import EstadoCalibracionVision
from src.configuration.infrastructure.dto.calibrar_vision_dto import CalibrarVisionDTO
from src.shared.database import get_db_sistema
from src.shared.errors import AuthenticationError, BusinessRuleError, ValidationError
from src.telemetry.application.use_cases.ingesta.ingerir_observaciones_vision_use_case import (
    IngerirObservacionesVisionUseCase,
)
from src.telemetry.domain.entities.observacion_vision import (
    EstadoCalibracionCamara,
    calcular_indice_calidad_vision,
)
from src.telemetry.domain.entities.telemetria_calidad import ClasificacionCalidad
from src.telemetry.domain.repositories.dispositivo_port import CamaraInfo
from src.telemetry.infrastructure.dto.ingerir_observaciones_vision_dto import IngerirObservacionesVisionDTO
from src.telemetry.infrastructure.routers import telemetria_router

T0 = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)
CAMARA = CamaraInfo(id_dispositivo_iot=12, id_infraestructura=2, es_activo=True, es_camara=True, fps_nominal=25)


def _obs(i: int = 0, **extra) -> dict:
    return {
        "timestamp_captura": (T0 + timedelta(minutes=i)).isoformat(),
        "cobertura_ventana": "0.9500", "n_tracks": 19, "n_tracks_perdidos": 1,
        "fps_efectivo": "24.00", "estado_calibracion": "CALIBRADA",
        "vector": {"densidad_actividad": 10.0 + i % 3, "tasa_movimiento": 3.0 + i % 2},
        **extra,
    }


def _dto(n: int = 1, **sobre) -> IngerirObservacionesVisionDTO:
    return IngerirObservacionesVisionDTO(**{
        "device_id": 12, "access_key": "CAM-001", "area_id": 2,
        "observaciones": [_obs(i) for i in range(n)], **sobre,
    })


class _Repo:
    """Repositorio en memoria: guarda y expone lo guardado como hace M03."""

    def __init__(self, existentes=()):
        self.filas, self.existentes = [], set(existentes)

    def fechas_existentes(self, id_dispositivo_iot, fechas):
        return {f for f in fechas if f in self.existentes}

    def guardar(self, o):
        o.id_observacion_vision = len(self.filas) + 1
        self.filas.append(o)
        return o


def _uc(camara=CAMARA, repo=None):
    puerto = Mock()
    puerto.obtener_camara.return_value = camara
    db = Mock()
    return IngerirObservacionesVisionUseCase(db=db, repo=repo or _Repo(), dispositivo_port=puerto), db


@pytest.mark.parametrize("dims, esperado, clasificacion", [
    (dict(cobertura_ventana=Decimal("1"), cantidad_tracks=10, cantidad_tracks_perdidos=0,
          fps_efectivo=Decimal("25"), fps_nominal=25, estado_calibracion=EstadoCalibracionCamara.CALIBRADA),
     100, ClasificacionCalidad.APTO),
    # cobertura 60, tracks 50, fps 50, estado 50 → 52.5 → 53 (mitad hacia arriba)
    (dict(cobertura_ventana=Decimal("0.6"), cantidad_tracks=5, cantidad_tracks_perdidos=5,
          fps_efectivo=Decimal("12.5"), fps_nominal=25, estado_calibracion=EstadoCalibracionCamara.DEGRADADA),
     53, ClasificacionCalidad.APTO_CON_RESERVA),
    # sin tracks y sin detección: solo cuentan cobertura y fps
    (dict(cobertura_ventana=Decimal("0.2"), cantidad_tracks=0, cantidad_tracks_perdidos=0,
          fps_efectivo=Decimal("5"), fps_nominal=None, estado_calibracion=EstadoCalibracionCamara.SIN_DETECCION),
     30, ClasificacionCalidad.NO_APTO),
])
def test_indice_de_calidad_de_vision_y_tramos_80_40(dims, esperado, clasificacion):
    from src.telemetry.domain.entities.telemetria_calidad import clasificar_desde_indice
    indice = calcular_indice_calidad_vision(**dims)
    assert indice == esperado
    assert clasificar_desde_indice(indice) == clasificacion


def test_ingesta_guarda_con_indice_apto_y_nic41_false():
    uc, db = _uc()
    r = uc.execute(_dto(3))
    assert (r.total, r.duplicados, len(r.observaciones)) == (3, 0, 3)
    o = r.observaciones[0]
    # (cobertura 95 + tracks 95 + fps 96 + estado 100) / 4 = 96.5 → 97
    assert o.id_infraestructura == 2 and o.indice_calidad == 97 and o.es_apto_para_ia is True
    assert o.es_apto_para_nic41 is False
    db.commit.assert_called_once()


def test_reenvio_del_buffer_cuenta_como_duplicado():
    repo = _Repo(existentes={T0})
    uc, _ = _uc(repo=repo)
    dto = _dto(2)
    dto.observaciones.append(dto.observaciones[1])  # repetida dentro del mismo lote
    r = uc.execute(dto)
    assert (r.total, r.duplicados, len(repo.filas)) == (3, 2, 1)


@pytest.mark.parametrize("camara, error, codigo", [
    (None, AuthenticationError, "ERROR_AUTENTICACION"),
    (CamaraInfo(12, 2, False, True, 25), AuthenticationError, "ERROR_AUTENTICACION"),
    (CamaraInfo(12, 2, True, False, None), BusinessRuleError, "DISPOSITIVO_NO_ES_CAMARA"),
    (CamaraInfo(12, 7, True, True, 25), BusinessRuleError, "AREA_NO_COINCIDE"),
])
def test_rechazos_de_identidad_y_area_no_persisten(camara, error, codigo):
    repo = _Repo()
    uc, db = _uc(camara=camara, repo=repo)
    with pytest.raises(error) as exc:
        uc.execute(_dto())
    assert exc.value.code == codigo and repo.filas == []
    db.commit.assert_not_called()


def test_timestamp_futuro_rechaza_el_lote():
    repo = _Repo()
    uc, _ = _uc(repo=repo)
    futuro = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    with pytest.raises(ValidationError) as exc:
        uc.execute(_dto(observaciones=[_obs(0), _obs(1, timestamp_captura=futuro)]))
    assert exc.value.code == "ERROR_TIEMPO" and exc.value.field == "observaciones[1].timestamp_captura"
    assert repo.filas == []


def test_lo_ingerido_permite_publicar_la_linea_base_vision():
    """TC-M09-275/276: con observaciones aptas de M03 el cálculo VISION es EXITOSA (antes, stub vacío → 422)."""
    repo = _Repo()
    _uc(repo=repo)[0].execute(_dto(40))

    class _M03:  # lo que ObservacionVisionM03Adapter lee de modulo3.observaciones_vision
        def listar(self, ids, inicio, fin):
            return [obs_m09.ObservacionVision(
                id_dispositivo_iot=o.id_dispositivo_iot, fecha_observacion=o.fecha_observacion,
                es_apto_para_ia=o.es_apto_para_ia, cobertura_ventana=float(o.cobertura_ventana),
                n_tracks=o.cantidad_tracks, componentes=o.vector,
            ) for o in repo.filas if o.id_dispositivo_iot in ids and inicio <= o.fecha_observacion <= fin]

    area = Mock(id_infraestructura=2, id_especie=4, tipo_modelo_asignado="MODELO_AVES")
    infra, camaras, cal, lb, eventos = Mock(), Mock(), Mock(), Mock(), Mock()
    infra.obtener_por_id.return_value = area
    camaras.listar_por_area.return_value = [Mock(id_dispositivo_iot=12, es_activo=True)]
    cal.guardar.side_effect = lambda c: c
    uc = CalibrarVisionUseCase(db=Mock(), infraestructura_repo=infra, camara_repo=camaras,
                               observacion_port=_M03(), calibracion_repo=cal, linea_base_repo=lb,
                               eventos_repo=eventos)
    dto = CalibrarVisionDTO(modo_calibracion="VISION", area_id=2,
                            ventana_observacion={"inicio": T0.isoformat(), "fin": (T0 + timedelta(hours=1)).isoformat()})
    resultado = uc.execute(dto, Mock(id_usuario=7))
    assert resultado.estado == EstadoCalibracionVision.EXITOSA
    assert set(resultado.linea_base["valores"]) == {"densidad_actividad", "tasa_movimiento"}
    lb.publicar.assert_called_once()
    assert eventos.registrar.call_args.kwargs["tipo_evento"] == 30


@pytest.fixture
def cliente(monkeypatch):
    repo = _Repo()
    puerto = Mock()
    puerto.obtener_camara.return_value = CAMARA
    monkeypatch.setattr(telemetria_router, "SqlAlchemyObservacionVisionRepository", lambda db: repo)
    monkeypatch.setattr(telemetria_router, "DispositivoM09Adapter", lambda db: puerto)
    app.dependency_overrides[get_db_sistema] = lambda: Mock()
    yield TestClient(app)
    app.dependency_overrides.pop(get_db_sistema, None)


def test_http_201_publica_indice_y_aptitudes(cliente):
    r = cliente.post("/iot/telemetria/vision", json={
        "device_id": 12, "access_key": "CAM-001", "area_id": 2, "observaciones": [_obs(0)]})
    assert r.status_code == 201, r.text
    cuerpo = r.json()
    assert (cuerpo["aceptadas"], cuerpo["duplicadas"]) == (1, 0)
    assert cuerpo["observaciones"][0]["apto_para_ia"] is True
    assert cuerpo["observaciones"][0]["apto_para_nic41"] is False


@pytest.mark.parametrize("obs", [
    _obs(0, vector={}),
    _obs(0, cobertura_ventana="1.5"),
    _obs(0, estado_calibracion="OTRO"),
], ids=["vector-vacio", "cobertura-fuera-de-rango", "estado-desconocido"])
def test_http_rechaza_observacion_mal_formada(cliente, obs):
    r = cliente.post("/iot/telemetria/vision", json={
        "device_id": 12, "access_key": "CAM-001", "area_id": 2, "observaciones": [obs]})
    assert r.status_code in (400, 422), r.text


def test_http_rechaza_componente_no_finito(cliente):
    cuerpo = ('{"device_id":12,"access_key":"CAM-001","area_id":2,"observaciones":[{'
              '"timestamp_captura":"2026-10-08T12:00:00Z","cobertura_ventana":"0.9","n_tracks":1,'
              '"n_tracks_perdidos":0,"fps_efectivo":"24","estado_calibracion":"CALIBRADA",'
              '"vector":{"densidad_actividad":NaN}}]}')
    r = cliente.post("/iot/telemetria/vision", content=cuerpo, headers={"Content-Type": "application/json"})
    assert r.status_code in (400, 422), r.text
