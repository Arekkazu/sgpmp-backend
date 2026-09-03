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

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from src.configuration.application.use_cases.plantillas.registrar_plantilla_use_case import (
    RegistrarPlantillaUseCase,
)
from src.configuration.domain.esquema_plantilla import (
    CAMPOS_REQUERIDOS,
    CLAVES_FUERA_DE_ALCANCE,
    claves_fuera_de_alcance,
    CATEGORIAS,
    CHANGELOG,
    SCHEMA_VERSION_ACTUAL,
    es_compatible,
    validar_snapshot,
    versiones_compatibles,
)
from src.configuration.domain.value_objects.aplica_tipo_activo import AplicaTipoActivo
from src.configuration.domain.value_objects.nivel_alerta import NivelAlerta
from src.configuration.domain.value_objects.tipo_medicion import TipoMedicion
from src.configuration.infrastructure.dto.registrar_plantilla_dto import RegistrarPlantillaDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.error_handlers import register_error_handlers
from src.shared.errors import BusinessRuleError

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


def test_claves_fuera_de_alcance_se_detectan_y_se_nombran():
    """FA 'Scope Creep' del RF-30. Va aparte de validar_snapshot porque el RF
    le asigna 422, y el DTO solo puede producir 400."""
    assert claves_fuera_de_alcance({**SNAPSHOT_VALIDO, "dispositivos_iot": [{"id": 1}]}) == [
        "dispositivos_iot"
    ]
    assert claves_fuera_de_alcance(SNAPSHOT_VALIDO) == []


def test_validar_snapshot_calla_si_el_fallo_es_de_alcance():
    """Si callara a medias, el 400 de 'plantilla vacía' se adelantaría al 422."""
    assert validar_snapshot({"dispositivos_iot": [{"id": 1}]}) == []


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


# ── RF-31 — tipos de los campos obligatorios ─────────────────────────────────
# Cada uno de estos casos pasaba la creación (solo se comprobaba presencia),
# quedaba guardado en una plantilla inmutable y reventaba después al aplicarla
# en RF-32: `int('muchos')` y `Decimal('abc')` salen como 500, y los enums como
# un 400 de la base de datos que no dice qué campo estaba mal.

def test_duracion_dias_no_numerica_es_rechazada():
    errores = validar_snapshot({"ciclos_biologicos": [{"nombre": "Alevín", "duracion_dias": "muchos"}]})
    assert errores == [
        "ciclos_biologicos[0].duracion_dias debe ser entero positivo; llegó 'muchos'."
    ]


@pytest.mark.parametrize("duracion", [0, -5, 12.5, True])
def test_duracion_dias_debe_ser_entero_positivo(duracion):
    """`True` entra aparte: en Python `bool` es subclase de `int`."""
    errores = validar_snapshot({"ciclos_biologicos": [{"nombre": "Alevín", "duracion_dias": duracion}]})
    assert any("duracion_dias debe ser entero positivo" in e for e in errores)


def test_nombre_en_blanco_no_cuenta_como_nombre():
    errores = validar_snapshot({"ciclos_biologicos": [{"nombre": "   ", "duracion_dias": 30}]})
    assert any("nombre debe ser texto no vacío" in e for e in errores)


def test_valor_no_decimal_del_umbral_es_rechazado():
    errores = validar_snapshot({
        "umbrales_ambientales": [{
            "id_variable_ambiental": 1, "unidad_medida": "°C",
            "valor_min": "abc", "valor_max": 30,
        }],
    })
    assert errores == ["umbrales_ambientales[0].valor_min debe ser número; llegó 'abc'."]


def test_valor_del_umbral_acepta_numero_y_string_numerico():
    """El backend serializa los decimales como string; ambos deben pasar."""
    assert validar_snapshot({
        "umbrales_ambientales": [{
            "id_variable_ambiental": 1, "unidad_medida": "°C",
            "valor_min": "22.0", "valor_max": 30,
        }],
    }) == []


def test_infinito_no_es_un_valor_valido():
    errores = validar_snapshot({
        "umbrales_ambientales": [{
            "id_variable_ambiental": 1, "unidad_medida": "°C",
            "valor_min": "-Infinity", "valor_max": "NaN",
        }],
    })
    assert len(errores) == 2


def test_enums_de_metrica_se_validan_contra_los_value_objects():
    errores = validar_snapshot({
        "metricas_produccion": [{
            "nombre": "Peso promedio", "unidad_medida": "kg",
            "tipo_medicion": "INVENTADO", "aplica_a_tipo_activo": "ANIMAL",
        }],
    })
    assert len(errores) == 2
    assert all(m.value in errores[0] for m in TipoMedicion)
    assert all(a.value in errores[1] for a in AplicaTipoActivo)


def test_niveles_del_umbral_se_validan_aunque_la_clave_sea_opcional():
    base = {
        "id_variable_ambiental": 1, "unidad_medida": "°C",
        "valor_min": "22.0", "valor_max": "30.0",
    }
    assert validar_snapshot({"umbrales_ambientales": [base]}) == []

    errores = validar_snapshot({
        "umbrales_ambientales": [{**base, "niveles": [{"nivel": "azul", "limite_inferior": "x"}]}],
    })
    assert any("niveles[0]: faltan los campos ['limite_superior']" in e for e in errores)
    assert any("niveles[0].nivel debe ser uno de" in e for e in errores)
    assert any("niveles[0].limite_inferior debe ser número" in e for e in errores)


def test_nivel_valido_pasa():
    assert validar_snapshot({
        "umbrales_ambientales": [{
            "id_variable_ambiental": 1, "unidad_medida": "°C",
            "valor_min": "22.0", "valor_max": "30.0",
            "niveles": [
                {"nivel": n.value, "limite_inferior": "20", "limite_superior": "32"}
                for n in NivelAlerta
            ],
        }],
    }) == []


def test_tipo_invalido_responde_400_nombrando_el_campo(cliente: TestClient):
    respuesta = cliente.post(
        "/plantillas",
        json={
            "template_name": "Ciclo corrupto",
            "id_especie": 1,
            "params_snapshot": {"ciclos_biologicos": [{"nombre": "Alevín", "duracion_dias": "muchos"}]},
        },
    )

    assert respuesta.status_code == 400
    detalle = " ".join(f["message"] for f in respuesta.json()["fields"])
    assert "duracion_dias" in detalle and "entero positivo" in detalle


# ── RF-30 — FA "Scope Creep": 422, no 400 ────────────────────────────────────
# El RF le da a este caso su propio código, distinto del 400 con que se rechaza
# un fallo de esquema. El chequeo vive en el use case porque un validador de
# Pydantic solo puede terminar en el 400 del handler global.

class _DbFake:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


class _EspecieRepoFake:
    """Si el 422 no se adelanta, la ejecución llega hasta aquí y se nota."""

    def __init__(self) -> None:
        self.consultada = False

    def obtener_por_id(self, _id_especie):
        self.consultada = True
        return SimpleNamespace(id_especie=1, es_activo=True)


class _PlantillaRepoFake:
    def __init__(self) -> None:
        self.guardadas: list = []

    def obtener_version_maxima(self, _template_name):
        return None

    def guardar(self, plantilla):
        self.guardadas.append(plantilla)
        plantilla.id_plantilla = 1
        return plantilla


class _AuditoriaRepoFake:
    def __init__(self) -> None:
        self.registros = 0

    def registrar(self, **_kwargs) -> None:
        self.registros += 1


def _use_case_registro():
    return RegistrarPlantillaUseCase(
        db=_DbFake(),
        plantilla_repo=_PlantillaRepoFake(),
        especie_repo=_EspecieRepoFake(),
        auditoria_repo=_AuditoriaRepoFake(),
    )


def _dto_con(snapshot: dict) -> RegistrarPlantillaDTO:
    return RegistrarPlantillaDTO(
        template_name="Config estándar", id_especie=1, params_snapshot=snapshot
    )


USUARIO = UsuarioActual(id_usuario=7, id_token=1, id_rol=1)


def test_scope_creep_lanza_422_y_no_toca_la_base():
    use_case = _use_case_registro()
    dto = _dto_con({**SNAPSHOT_VALIDO, "dispositivos_iot": [{"id": 1}]})

    with pytest.raises(BusinessRuleError) as exc_info:
        use_case.execute(dto, USUARIO)

    error = exc_info.value
    assert error.status_code == 422
    assert error.code == "ALCANCE_NO_PERMITIDO"
    assert "dispositivos_iot" in error.message
    assert error.field == "params_snapshot"
    # Se corta antes de consultar la especie, guardar o auditar.
    assert use_case.especie_repo.consultada is False
    assert use_case.plantilla_repo.guardadas == []
    assert use_case.auditoria_repo.registros == 0
    assert use_case.db.commits == 0


@pytest.mark.parametrize("clave", sorted(CLAVES_FUERA_DE_ALCANCE))
def test_todas_las_categorias_excluidas_por_el_rf_dan_422(clave):
    """Dispositivos IoT, infraestructura, dashboard e identidad visual, más las
    que el RF-30 excluye por depender del contexto de cada unidad productiva."""
    use_case = _use_case_registro()

    with pytest.raises(BusinessRuleError):
        use_case.execute(_dto_con({**SNAPSHOT_VALIDO, clave: [{"id": 1}]}), USUARIO)


def test_snapshot_dentro_del_alcance_no_dispara_el_422():
    use_case = _use_case_registro()

    plantilla = use_case.execute(_dto_con(SNAPSHOT_VALIDO), USUARIO)

    assert plantilla.version == 1
    assert plantilla.params_snapshot["schema_version"] == SCHEMA_VERSION_ACTUAL
    assert use_case.db.commits == 1
