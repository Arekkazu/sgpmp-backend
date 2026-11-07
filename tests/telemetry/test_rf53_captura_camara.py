# | Fecha      | Nombre   | Que se hizo                                                     |
# |------------|----------|-----------------------------------------------------------------|
# | 2026-11-02 | Arekkazu | RF-53/RF-66: capturas de la cámara (guardar, recortar y buscar)  |
# | 2026-11-02 | Arekkazu | RF-66 POBLACIONAL: conteo de la cámara contra el inventario      |
"""Capturas de la cámara: solo JPEG válidos, solo las más recientes, y por ventana para la inferencia."""
from __future__ import annotations

import base64
import io
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from PIL import Image

from src.prediction.application.use_cases.camara.obtener_captura_area_use_case import ObtenerCapturaAreaUseCase
from src.prediction.domain.entities.conteo_poblacional import hay_discrepancia
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


def _uc_area(camaras, registrada=15, conteos=(11, 10, 11)):
    return ObtenerCapturaAreaUseCase(SimpleNamespace(
        camaras=lambda a: camaras, cantidad_registrada=lambda a: registrada,
        conteos_recientes=lambda a, n: list(conteos)[:n]))


def test_consulta_por_area_distingue_sin_camara_y_sin_captura():
    uc = _uc_area
    with pytest.raises(NotFoundError) as exc:
        uc([]).execute(7)
    assert exc.value.code == "AREA_SIN_CAMARA"
    with pytest.raises(NotFoundError) as exc:
        uc([8]).execute(7)
    assert exc.value.code == "CAPTURA_NO_DISPONIBLE"
    guardar_captura(8, T0, 6, _jpeg())
    assert uc([8]).execute(7).captura.n_individuos == 6


def test_aviso_de_inventario_solo_si_las_ultimas_ventanas_se_alejan_mas_de_la_tolerancia():
    # Granja: la cámara ve 11 de 15 (27 % menos) → dentro de la tolerancia del 35 %.
    assert not hay_discrepancia([11, 10, 11], 15)
    # Echados: ve 3–5 de 15 en tres ventanas seguidas → aviso.
    assert hay_discrepancia([3, 5, 4], 15)
    assert not hay_discrepancia([3, 5, 11], 15)  # una ventana cerca basta para no avisar
    assert not hay_discrepancia([3, 5], 15)  # aún no hay suficientes ventanas
    assert not hay_discrepancia([3, 5, 4], None)  # el área no tiene lotes poblacionales
    assert hay_discrepancia([25, 24, 26], 15)  # más animales que los registrados también avisa


def test_la_captura_actual_trae_inventario_y_aviso_y_la_de_una_ventana_no_avisa():
    guardar_captura(8, T0, 4, _jpeg())
    actual = _uc_area([8], conteos=(4, 3, 5)).execute(7)
    assert (actual.cantidad_registrada, actual.discrepancia_inventario) == (15, True)
    vieja = _uc_area([8], conteos=(4, 3, 5)).execute(7, T0)
    assert (vieja.cantidad_registrada, vieja.discrepancia_inventario) == (15, False)
