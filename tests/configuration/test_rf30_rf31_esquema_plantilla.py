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

from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from src.configuration.application.use_cases.plantillas.registrar_plantilla_use_case import (
    RegistrarPlantillaUseCase,
)
from src.configuration.application.use_cases.plantillas.versionar_plantilla_use_case import (
    VersionarPlantillaUseCase,
)
from src.configuration.domain.entities.plantilla import Plantilla
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
from src.configuration.infrastructure.dto.versionar_plantilla_dto import VersionarPlantillaDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.error_handlers import register_error_handlers
from src.shared.errors import BusinessRuleError, ConflictError, NotFoundError

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
        self.activa = True

    def obtener_por_id(self, _id_especie):
        self.consultada = True
        return SimpleNamespace(id_especie=1, es_activo=self.activa)


class _PlantillaRepoFake:
    """Emula el trigger `trg_fn_plantilla_version_incremental`: la BD, no la
    app, fija el número de versión al insertar, comparando el nombre
    normalizado."""

    def __init__(self, existentes: list | None = None) -> None:
        self.guardadas: list = list(existentes or [])

    def _familia(self, template_name: str) -> list:
        clave = template_name.strip().lower()
        return [p for p in self.guardadas if p.template_name.strip().lower() == clave]

    def existe_nombre(self, template_name: str) -> bool:
        return bool(self._familia(template_name))

    def obtener_por_id(self, id_plantilla):
        return next((p for p in self.guardadas if p.id_plantilla == id_plantilla), None)

    def guardar(self, plantilla):
        familia = self._familia(plantilla.template_name)
        plantilla.version = max((p.version for p in familia), default=0) + 1
        plantilla.id_plantilla = len(self.guardadas) + 1
        self.guardadas.append(plantilla)
        return plantilla


class _AuditoriaRepoFake:
    def __init__(self) -> None:
        self.registros = 0
        self.ultimo: dict = {}

    def registrar(self, **kwargs) -> None:
        self.registros += 1
        self.ultimo = kwargs


class _VariableRepoFake:
    """Variable de rango físico [15.0, 30.0], igual que 'Temperatura del agua'."""

    def obtener_por_id(self, id_variable_ambiental):
        if id_variable_ambiental is None:
            return None
        return SimpleNamespace(
            id_variable_ambiental=id_variable_ambiental,
            nombre="Temperatura del agua",
            unidad="°C",
            valor_fisico_min=Decimal("15.0"),
            valor_fisico_max=Decimal("30.0"),
            es_activo=True,
        )


def _use_case_registro():
    return RegistrarPlantillaUseCase(
        db=_DbFake(),
        plantilla_repo=_PlantillaRepoFake(),
        especie_repo=_EspecieRepoFake(),
        auditoria_repo=_AuditoriaRepoFake(),
        variable_repo=_VariableRepoFake(),
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


# ── RF-31 (#126) — rango físico de umbrales ambientales ──────────────────────
# `_VariableRepoFake` simula una variable con rango físico real [15.0, 30.0].
# Antes de este fix, un umbral fuera de ese rango pasaba sin ningún control: el
# DTO solo valida tipo (número), no rango, porque no conoce la BD.

_UMBRAL_FUERA_DE_RANGO = {
    "id_variable_ambiental": 1, "unidad_medida": "°C",
    "valor_min": "-999", "valor_max": "999",
}
_UMBRAL_DENTRO_DE_RANGO = {
    "id_variable_ambiental": 1, "unidad_medida": "°C",
    "valor_min": "18.0", "valor_max": "25.0",
}


def test_crear_con_umbral_fuera_de_rango_fisico_responde_422():
    use_case = _use_case_registro()
    dto = _dto_con({"umbrales_ambientales": [_UMBRAL_FUERA_DE_RANGO]})

    with pytest.raises(BusinessRuleError) as exc_info:
        use_case.execute(dto, USUARIO)

    error = exc_info.value
    assert error.status_code == 422
    assert error.code == "RANGO_FISICO_INVALIDO"
    assert error.field == "params_snapshot"
    assert use_case.plantilla_repo.guardadas == []
    assert use_case.db.commits == 0


def test_crear_con_umbral_dentro_de_rango_fisico_no_dispara_422():
    use_case = _use_case_registro()
    dto = _dto_con({"umbrales_ambientales": [_UMBRAL_DENTRO_DE_RANGO]})

    plantilla = use_case.execute(dto, USUARIO)

    assert use_case.db.commits == 1
    assert plantilla.params_snapshot["umbrales_ambientales"] == [_UMBRAL_DENTRO_DE_RANGO]


# ── RF-30 / RF-31 — nombre único al crear, versionado explícito ──────────────
# Los dos RF piden como criterio de aceptación que el sistema "rechace la
# creación de una plantilla con un nombre ya existente", y a la vez que "una
# actualización genere una nueva versión". Antes el POST hacía lo segundo en
# silencio, así que el primero no se cumplía: repetir un nombre devolvía 201
# con v2 y el usuario creía haber creado una plantilla distinta.

def _plantilla_existente(nombre: str = "Config estándar", version: int = 1) -> Plantilla:
    p = Plantilla.crear(
        id_especie=1, id_usuario=7, template_name=nombre,
        params_snapshot={**SNAPSHOT_VALIDO, "schema_version": SCHEMA_VERSION_ACTUAL},
        version=version, fecha_creacion=datetime(2026, 5, 1, tzinfo=timezone.utc),
    )
    p.id_plantilla = version
    return p


def test_crear_con_nombre_repetido_responde_409():
    use_case = _use_case_registro()
    use_case.plantilla_repo.guardadas.append(_plantilla_existente())

    with pytest.raises(ConflictError) as exc_info:
        use_case.execute(_dto_con(SNAPSHOT_VALIDO), USUARIO)

    error = exc_info.value
    assert error.status_code == 409
    assert error.code == "NOMBRE_PLANTILLA_DUPLICADO"
    assert "Config estándar" in error.message
    assert error.field == "template_name"
    assert use_case.db.commits == 0
    assert len(use_case.plantilla_repo.guardadas) == 1  # no se creó una v2


@pytest.mark.parametrize("variante", ["config estándar", "CONFIG ESTÁNDAR", "  Config estándar  "])
def test_el_nombre_duplicado_se_detecta_como_lo_hace_la_base(variante):
    """El trigger compara `LOWER(TRIM(...))`. Si la app comparara exacto, estas
    variantes pasarían el 409 y la BD las uniría a la misma familia sin avisar."""
    use_case = _use_case_registro()
    use_case.plantilla_repo.guardadas.append(_plantilla_existente())
    dto = RegistrarPlantillaDTO(
        template_name=variante, id_especie=1, params_snapshot=SNAPSHOT_VALIDO
    )

    with pytest.raises(ConflictError):
        use_case.execute(dto, USUARIO)


def test_crear_con_nombre_libre_asigna_version_1():
    use_case = _use_case_registro()

    plantilla = use_case.execute(_dto_con(SNAPSHOT_VALIDO), USUARIO)

    assert plantilla.version == 1
    assert use_case.db.commits == 1


def _use_case_versionado(existentes):
    return VersionarPlantillaUseCase(
        db=_DbFake(),
        plantilla_repo=_PlantillaRepoFake(existentes),
        especie_repo=_EspecieRepoFake(),
        auditoria_repo=_AuditoriaRepoFake(),
        variable_repo=_VariableRepoFake(),
    )


def _dto_version(snapshot: dict | None = None) -> VersionarPlantillaDTO:
    return VersionarPlantillaDTO(params_snapshot=snapshot or SNAPSHOT_VALIDO)


def test_versionar_crea_la_siguiente_version_conservando_nombre_y_especie():
    base = _plantilla_existente()
    use_case = _use_case_versionado([base])

    nueva = use_case.execute(1, _dto_version(), USUARIO)

    assert nueva.version == 2
    assert nueva.template_name == base.template_name
    assert nueva.id_especie == base.id_especie
    assert nueva.id_usuario == USUARIO.id_usuario  # autoría de esta versión
    assert use_case.db.commits == 1


def test_versionar_no_sobreescribe_la_version_anterior():
    """Criterio de aceptación: 'una actualización genera nueva versión, no
    sobreescribe la original'."""
    base = _plantilla_existente()
    use_case = _use_case_versionado([base])

    use_case.execute(1, _dto_version({"patologias": [{"nombre": "Otra"}]}), USUARIO)

    guardadas = use_case.plantilla_repo.guardadas
    assert [p.version for p in guardadas] == [1, 2]
    assert guardadas[0].params_snapshot == base.params_snapshot


def test_versionar_encadena_v2_v3():
    use_case = _use_case_versionado([_plantilla_existente()])

    use_case.execute(1, _dto_version(), USUARIO)
    tercera = use_case.execute(1, _dto_version(), USUARIO)

    assert tercera.version == 3


def test_versionar_registra_auditoria_con_el_estado_anterior():
    """El RF pide trazar la actualización; sin el before no hay con qué comparar."""
    use_case = _use_case_versionado([_plantilla_existente()])

    use_case.execute(1, _dto_version(), USUARIO)

    assert use_case.auditoria_repo.registros == 1
    registro = use_case.auditoria_repo.ultimo
    assert registro["tipo_operacion"] == "CREATE"
    assert registro["valores_anteriores"]["version"] == 1
    assert registro["valores_nuevos"]["version"] == 2


def test_versionar_una_plantilla_inexistente_responde_404():
    use_case = _use_case_versionado([])

    with pytest.raises(NotFoundError) as exc_info:
        use_case.execute(99, _dto_version(), USUARIO)

    assert exc_info.value.code == "PLANTILLA_NO_ENCONTRADA"
    assert use_case.db.commits == 0


def test_versionar_con_especie_desactivada_responde_422():
    use_case = _use_case_versionado([_plantilla_existente()])
    use_case.especie_repo.activa = False

    with pytest.raises(BusinessRuleError) as exc_info:
        use_case.execute(1, _dto_version(), USUARIO)

    assert exc_info.value.status_code == 422
    assert exc_info.value.code == "ESPECIE_INACTIVA"
    assert use_case.db.commits == 0


def test_versionar_tambien_rechaza_el_scope_creep_con_422():
    use_case = _use_case_versionado([_plantilla_existente()])
    dto = _dto_version({**SNAPSHOT_VALIDO, "dashboard": [{"id": 1}]})

    with pytest.raises(BusinessRuleError) as exc_info:
        use_case.execute(1, dto, USUARIO)

    assert exc_info.value.code == "ALCANCE_NO_PERMITIDO"


def test_versionar_tambien_rechaza_umbral_fuera_de_rango_fisico():
    """Mismo gap que en creación: versionar persiste un snapshot nuevo e
    inmutable, así que también debe validar el rango físico (#126)."""
    use_case = _use_case_versionado([_plantilla_existente()])
    dto = _dto_version({"umbrales_ambientales": [_UMBRAL_FUERA_DE_RANGO]})

    with pytest.raises(BusinessRuleError) as exc_info:
        use_case.execute(1, dto, USUARIO)

    assert exc_info.value.code == "RANGO_FISICO_INVALIDO"
    assert use_case.db.commits == 0
