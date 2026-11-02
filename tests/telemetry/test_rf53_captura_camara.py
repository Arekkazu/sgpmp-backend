# | Fecha      | Nombre   | Que se hizo                                                     |
# |------------|----------|-----------------------------------------------------------------|
# | 2026-11-02 | Arekkazu | RF-53/RF-66: capturas de la cámara (guardar, recortar y buscar)  |
"""Capturas de la cámara: solo JPEG válidos, solo las más recientes, y por ventana para la inferencia."""
from __future__ import annotations

import base64
import io
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from PIL import Image

from src.prediction.application.use_cases.camara.obtener_captura_area_use_case import ObtenerCapturaAreaUseCase
from src.shared import almacen_capturas
from src.shared.almacen_capturas import buscar_captura, guardar_captura
from src.shared.errors import AuthenticationError, BusinessRuleError, NotFoundError, ValidationError
from src.telemetry.application.use_cases.ingesta.ingerir_captura_vision_use_case import IngerirCapturaVisionUseCase
from src.telemetry.infrastructure.dto.captura_vision_dto import CapturaVisionDTO

T0 = datetime(2026, 11, 2, 14, 8, 36, 659000, tzinfo=timezone.utc)


def _jpeg(ancho=64, alto=36, formato="JPEG") -> bytes:
    salida = io.BytesIO()
    Image.new("RGB", (ancho, alto), (200, 120, 0)).save(salida, formato)
    return salida.getvalue()


@pytest.fixture(autouse=True)
def directorio(tmp_path, monkeypatch):
    monkeypatch.setattr(almacen_capturas, "DIRECTORIO", tmp_path)
    return tmp_path


def test_guarda_solo_las_mas_recientes_y_busca_la_ultima_o_la_de_una_ventana(directorio):
    for i in range(18):
        guardar_captura(8, T0 + timedelta(seconds=20 * i), i, _jpeg())
    assert len(list((directorio / "8").glob("*.jpg"))) == almacen_capturas.MAX_POR_CAMARA
    ultima = buscar_captura([8])
    assert (ultima.fecha, ultima.n_individuos) == (T0 + timedelta(seconds=340), 17)
    assert ultima.jpeg[:3] == b"\xff\xd8\xff"
    # La de una ventana, con la precisión de la BD (microsegundos) frente a la del nodo (ms).
    assert buscar_captura([8], T0 + timedelta(seconds=200, microseconds=412)).n_individuos == 10
    assert buscar_captura([8], T0) is None  # ya se descartó
    assert buscar_captura([99]) is None


@pytest.mark.parametrize("contenido", [b"no es imagen", _jpeg(formato="PNG"), _jpeg(ancho=2000)])
def test_rechaza_lo_que_no_es_un_jpeg_razonable(contenido):
    with pytest.raises(ValidationError) as exc:
        guardar_captura(8, T0, 1, contenido)
    assert exc.value.code == "CAPTURA_INVALIDA"


def _ingerir(camara, **cambios):
    datos = {"serial": "CAM-PORC-001", "area_id": 7, "ventana_fin": T0, "n_individuos_observados": 6,
             "imagen_jpeg_base64": base64.b64encode(_jpeg()).decode(), **cambios}
    dto = CapturaVisionDTO(**datos)
    return IngerirCapturaVisionUseCase(SimpleNamespace(obtener_camara_por_serial=lambda s: camara)).execute(dto)


def _camara(**cambios):
    return SimpleNamespace(**{"id_dispositivo_iot": 8, "id_infraestructura": 7, "es_activo": True,
                              "es_camara": True, **cambios})


def test_ingesta_valida_la_camara_como_el_sobre_d4():
    assert _ingerir(_camara()) == 8 and buscar_captura([8]).n_individuos == 6
    with pytest.raises(AuthenticationError):
        _ingerir(None)
    with pytest.raises(AuthenticationError):
        _ingerir(_camara(es_activo=False))
    with pytest.raises(BusinessRuleError, match="no es una cámara"):
        _ingerir(_camara(es_camara=False))
    with pytest.raises(BusinessRuleError, match="no está asociada"):
        _ingerir(_camara(id_infraestructura=3))
    with pytest.raises(ValidationError):
        _ingerir(_camara(), imagen_jpeg_base64="@@no es base64@@")


def test_consulta_por_area_distingue_sin_camara_y_sin_captura():
    uc = lambda camaras: ObtenerCapturaAreaUseCase(SimpleNamespace(camaras=lambda a: camaras))  # noqa: E731
    with pytest.raises(NotFoundError) as exc:
        uc([]).execute(7)
    assert exc.value.code == "AREA_SIN_CAMARA"
    with pytest.raises(NotFoundError) as exc:
        uc([8]).execute(7)
    assert exc.value.code == "CAPTURA_NO_DISPONIBLE"
    guardar_captura(8, T0, 6, _jpeg())
    assert uc([8]).execute(7).n_individuos == 6
