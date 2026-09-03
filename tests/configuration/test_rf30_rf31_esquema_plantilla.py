"""RF-30 / RF-31 — esquema versionado del `params_snapshot` y plantilla vacía.

Trazabilidad de los gaps que corrigen estas pruebas (auditoría
`anotaciones/modulo_9/estado_M09.md`):

- RF-30: "no hay un changelog o tabla de versiones de esquema consultable" — la
  versión vivía como constante `_SCHEMA_VERSION_ACTUAL = 1` duplicada en dos
  casos de uso. Ahora hay una sola fuente (`domain/esquema_plantilla.py`) con
  changelog, y `GET /configuracion/plantillas/esquema` la publica.
- RF-31: "no se verificó si existe la validación de al menos un parámetro
  seleccionado (rechazar plantilla vacía con 400)". Existía en el DTO; estas
  pruebas la fijan como regresión y comprueban que el handler global la traduce
  a `400`, no a `422`.
- RF-31: "no se confirmó si el mensaje interpola la lista específica de claves
  rechazadas". Se comprueba que el mensaje nombra cada parámetro inválido.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from src.configuration.domain.esquema_plantilla import (
    CAMPOS_REQUERIDOS,
    CATEGORIAS,
    CHANGELOG,
    SCHEMA_VERSION_ACTUAL,
    es_compatible,
    validar_snapshot,
    versiones_compatibles,
)
from src.configuration.infrastructure.dto.registrar_plantilla_dto import RegistrarPlantillaDTO
from src.shared.error_handlers import register_error_handlers

SNAPSHOT_VALIDO = {
    "ciclos_biologicos": [
        {"nombre": "Engorde", "duracion_dias": 45, "descripcion": None},
    ],
}


# ── RF-30 — changelog de versiones de esquema ────────────────────────────────

def test_changelog_documenta_la_version_vigente():
    """El changelog no puede quedarse atrás de SCHEMA_VERSION_ACTUAL."""
    assert CHANGELOG[0]["version"] == SCHEMA_VERSION_ACTUAL


def test_changelog_esta_ordenado_de_la_mas_reciente_a_la_mas_antigua():
    versiones = [e["version"] for e in CHANGELOG]
    assert versiones == sorted(versiones, reverse=True)


def test_cada_entrada_del_changelog_documenta_que_cambio():
    for entrada in CHANGELOG:
        assert entrada["fecha"], f"la versión {entrada['version']} no tiene fecha"
        assert entrada["cambios"], f"la versión {entrada['version']} no documenta cambios"
        assert entrada["compatible_con"], (
            f"la versión {entrada['version']} no declara compatibilidad"
        )


def test_la_version_vigente_es_compatible_consigo_misma():
    assert es_compatible(SCHEMA_VERSION_ACTUAL) is True
    assert SCHEMA_VERSION_ACTUAL in versiones_compatibles()


def test_una_version_no_declarada_es_incompatible():
    """Base del FA 'Legacy Template' del RF-30: 412 al aplicar."""
    assert es_compatible(0) is False
    assert es_compatible(SCHEMA_VERSION_ACTUAL + 1) is False


# ── RF-31 — plantilla vacía y estructura del snapshot ────────────────────────

def test_snapshot_sin_parametros_es_rechazado():
    errores = validar_snapshot({})
    assert any("Plantilla vacía" in e for e in errores)


def test_snapshot_con_categorias_vacias_tambien_es_plantilla_vacia():
    errores = validar_snapshot({k: [] for k in CATEGORIAS})
    assert any("Plantilla vacía" in e for e in errores)


def test_snapshot_con_un_solo_parametro_es_valido():
    assert validar_snapshot(SNAPSHOT_VALIDO) == []


def test_snapshot_fuera_de_alcance_nombra_las_claves_invalidas():
    errores = validar_snapshot({**SNAPSHOT_VALIDO, "dispositivos_iot": [{"id": 1}]})
    assert any("dispositivos_iot" in e and "fuera de alcance" in e for e in errores)


def test_snapshot_con_clave_desconocida_la_nombra():
    errores = validar_snapshot({**SNAPSHOT_VALIDO, "ciclos": True})
    assert any("ciclos" in e and "no reconocidas" in e for e in errores)


def test_item_sin_campos_obligatorios_los_enumera():
    """Sin esta validación el fallo aparecía en RF-32 como KeyError → 500."""
    errores = validar_snapshot({"ciclos_biologicos": [{"descripcion": "sin nombre"}]})
    assert len(errores) == 1
    assert "ciclos_biologicos[0]" in errores[0]
    for campo in CAMPOS_REQUERIDOS["ciclos_biologicos"]:
        assert campo in errores[0]


def test_categoria_que_no_es_lista_es_rechazada():
    errores = validar_snapshot({"umbrales_ambientales": {"valor_min": 1}})
    assert any("debe ser una lista" in e for e in errores)


def test_dto_acepta_snapshot_valido():
    dto = RegistrarPlantillaDTO(
        template_name="Config estándar",
        id_especie=1,
        params_snapshot=SNAPSHOT_VALIDO,
    )
    assert dto.params_snapshot == SNAPSHOT_VALIDO


def test_dto_rechaza_plantilla_vacia():
    with pytest.raises(ValidationError) as exc_info:
        RegistrarPlantillaDTO(template_name="Vacía", id_especie=1, params_snapshot={})
    assert "Plantilla vacía" in str(exc_info.value)


# ── RF-31 — la plantilla vacía sale como 400, no como 422 ────────────────────

@pytest.fixture(name="cliente")
def _cliente() -> TestClient:
    """App mínima con el DTO y los handlers globales: sin BD ni RBAC."""
    app = FastAPI()
    register_error_handlers(app)

    @app.post("/plantillas")
    def _crear(dto: RegistrarPlantillaDTO) -> dict:  # pragma: no cover - trivial
        return {"ok": True}

    return TestClient(app, raise_server_exceptions=False)


def test_plantilla_vacia_responde_400_con_el_detalle(cliente: TestClient):
    respuesta = cliente.post(
        "/plantillas",
        json={"template_name": "Vacía", "id_especie": 1, "params_snapshot": {}},
    )

    assert respuesta.status_code == 400
    cuerpo = respuesta.json()
    assert cuerpo["error_code"] == "VAL_ENTRADA"
    detalle = " ".join(f["message"] for f in cuerpo["fields"])
    assert "Plantilla vacía" in detalle
    assert "params_snapshot" in cuerpo["fields"][0]["field"]


def test_snapshot_valido_pasa_la_validacion_de_entrada(cliente: TestClient):
    respuesta = cliente.post(
        "/plantillas",
        json={
            "template_name": "Config estándar",
            "id_especie": 1,
            "params_snapshot": SNAPSHOT_VALIDO,
        },
    )
    assert respuesta.status_code == 200
