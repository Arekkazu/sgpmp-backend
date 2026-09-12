"""RF-32 - Mecanismo de snapshot y rollback ante fallo de persistencia.

Cubre TC-M09-G120: TC-M09-230 (snapshot previo), TC-M09-232 (rollback
automatico ante fallo de persistencia), TC-M09-233 (restauracion exacta) y
TC-M09-242 (atomicidad: sin cambios parciales).

Estas pruebas ejecutan el codigo real de `AplicarPlantillaUseCase` (no un
doble del use case en si) para verificar el mecanismo de snapshot/rollback,
siguiendo el mismo estilo de fakes en memoria que ya usa este proyecto en
`test_rf32_concurrencia_aplicar_plantilla.py` (sin PostgreSQL real).

El fallo de persistencia que se fuerza aqui NO es artificial: es el mismo
defecto real confirmado por pruebas de API en TC-M09-G118 (evidencia
`TC-M09-G118_evidencia_ejecucion.md`): un snapshot de `metricas_produccion`
creado a traves de la API publica (que no valida su estructura interna, ver
TC-M09-215) nunca trae `unidad_medida`/`tipo_medicion`/`aplica_a_tipo_activo`,
y `MetricaProduccionRepository.guardar_desde_snapshot` accede a esas claves
sin verificar que existan -> `KeyError` no controlado -> 500 en produccion.

Para poder verificar atomicidad ENTRE varios repositorios (algo que un fake
"vacio" como `RepoVacioFake` del archivo de concurrencia no puede probar,
porque no comparten estado), los fakes de este archivo comparten una unica
`TransactionalStore`: las escrituras de cada repo se acumulan en un area
"staged", separada del estado "committed", exactamente como lo hace una
sesion real de SQLAlchemy con flush()/commit()/rollback(). Solo cuando el
`DbFake` compartido recibe `commit()` se confirma `staged` en `committed`;
si recibe `rollback()`, `staged` se descarta y vuelve a ser una copia de
`committed`. Esto es necesario porque en produccion la atomicidad la
garantiza la sesion compartida, no cada repositorio por separado.
"""
from __future__ import annotations

import copy
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from src.configuration.application.use_cases.plantillas.aplicar_plantilla_use_case import (
    AplicarPlantillaUseCase,
)
from src.configuration.domain.entities.especie import Especie
from src.configuration.domain.entities.plantilla import Plantilla
from src.configuration.domain.value_objects.nombre_especie import NombreEspecie
from src.configuration.infrastructure.dto.aplicar_plantilla_dto import AplicarPlantillaDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual

ID_ESPECIE = 5
FECHA_ACTUALIZACION_DB = datetime(2026, 5, 10, 8, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Infraestructura fake: sesion transaccional compartida
# ---------------------------------------------------------------------------


class _ValorAttr:
    """Simula un value object con atributo `.valor` (NombreX, DuracionDias)."""

    def __init__(self, valor):
        self.valor = valor


class _ValueAttr:
    """Simula un Enum con atributo `.value` (TipoMedicion, AplicaTipoActivo, NivelAlerta)."""

    def __init__(self, value):
        self.value = value


def _estado_con_datos_previos() -> dict:
    """Configuracion 'antes' de una especie: un registro activo por categoria."""
    return {
        "ciclos": {
            ID_ESPECIE: [
                {"nombre": "Alevinaje", "duracion_dias": 30, "descripcion": "Etapa inicial", "es_activo": True},
            ]
        },
        "metricas": {
            ID_ESPECIE: [
                {
                    "nombre": "peso_promedio_kg",
                    "unidad_medida": "kg",
                    "tipo_medicion": "PESO",
                    "aplica_a_tipo_activo": "AMBOS",
                    "es_activo": True,
                },
            ]
        },
        "umbrales": {
            ID_ESPECIE: [
                {
                    "id_variable_ambiental": 1,
                    "unidad_medida": "°C",
                    "valor_min": "20.0",
                    "valor_max": "28.0",
                    "es_activo": True,
                    "niveles": [
                        {"nivel": "ALERTA", "limite_inferior": "18.0", "limite_superior": "30.0"},
                    ],
                },
            ]
        },
        "patologias": {
            ID_ESPECIE: [
                {"nombre": "Hongos", "descripcion": "Infeccion fungica", "es_activo": True},
            ]
        },
    }


class TransactionalStore:
    """Simula la atomicidad de una unica sesion de BD compartida entre repos."""

    def __init__(self, estado_inicial: dict) -> None:
        self.committed = copy.deepcopy(estado_inicial)
        self.staged = copy.deepcopy(estado_inicial)

    def commit(self) -> None:
        self.committed = copy.deepcopy(self.staged)

    def rollback(self) -> None:
        self.staged = copy.deepcopy(self.committed)


class DbFake:
    """Sustituye a la Session de SQLAlchemy: cuenta commits/rollbacks reales
    y los propaga al TransactionalStore compartido por todos los repos fake."""

    def __init__(self, store: TransactionalStore) -> None:
        self.store = store
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1
        self.store.commit()

    def rollback(self) -> None:
        self.rollbacks += 1
        self.store.rollback()


class CicloRepoFake:
    def __init__(self, store: TransactionalStore) -> None:
        self.store = store

    def desactivar_todos_por_especie(self, id_especie: int) -> None:
        for c in self.store.staged["ciclos"].get(id_especie, []):
            c["es_activo"] = False

    def guardar_desde_snapshot(self, datos: dict, id_especie: int) -> None:
        self.store.staged["ciclos"].setdefault(id_especie, []).append(
            {
                "nombre": datos["nombre"],
                "duracion_dias": int(datos["duracion_dias"]),
                "descripcion": datos.get("descripcion"),
                "es_activo": True,
            }
        )

    def listar_por_especie(self, id_especie: int, solo_activas: bool = False):
        items = self.store.staged["ciclos"].get(id_especie, [])
        if solo_activas:
            items = [c for c in items if c["es_activo"]]
        return [
            SimpleNamespace(
                nombre=_ValorAttr(c["nombre"]),
                duracion_dias=_ValorAttr(c["duracion_dias"]),
                descripcion=c["descripcion"],
            )
            for c in items
        ]


class MetricaRepoFake:
    def __init__(self, store: TransactionalStore) -> None:
        self.store = store

    def desactivar_todas_por_especie(self, id_especie: int) -> None:
        for m in self.store.staged["metricas"].get(id_especie, []):
            m["es_activo"] = False

    def guardar_desde_snapshot(self, datos: dict, id_especie: int, id_usuario: int) -> None:
        # OJO: acceso directo por clave, igual que el repositorio real -- si
        # `datos` no trae estas claves (como ocurre con cualquier plantilla
        # creada por la API publica), esto lanza KeyError sin controlar,
        # reproduciendo el defecto real de TC-M09-G118.
        nueva = {
            "nombre": datos["nombre"],
            "unidad_medida": datos["unidad_medida"],
            "tipo_medicion": datos["tipo_medicion"],
            "aplica_a_tipo_activo": datos["aplica_a_tipo_activo"],
            "es_activo": True,
        }
        self.store.staged["metricas"].setdefault(id_especie, []).append(nueva)

    def listar_por_especie(self, id_especie: int, solo_activas: bool = False):
        items = self.store.staged["metricas"].get(id_especie, [])
        if solo_activas:
            items = [m for m in items if m["es_activo"]]
        return [
            SimpleNamespace(
                nombre=_ValorAttr(m["nombre"]),
                unidad_medida=m["unidad_medida"],
                tipo_medicion=_ValueAttr(m["tipo_medicion"]),
                aplica_a_tipo_activo=_ValueAttr(m["aplica_a_tipo_activo"]),
            )
            for m in items
        ]


class UmbralRepoFake:
    def __init__(self, store: TransactionalStore) -> None:
        self.store = store

    def desactivar_todos_por_especie(self, id_especie: int) -> None:
        for u in self.store.staged["umbrales"].get(id_especie, []):
            u["es_activo"] = False

    def guardar_desde_snapshot(self, datos: dict, id_especie: int, id_usuario: int) -> None:
        nuevo = {
            "id_variable_ambiental": int(datos["id_variable_ambiental"]),
            "unidad_medida": datos["unidad_medida"],
            "valor_min": datos["valor_min"],
            "valor_max": datos["valor_max"],
            "es_activo": True,
            "niveles": [
                {
                    "nivel": n["nivel"],
                    "limite_inferior": n["limite_inferior"],
                    "limite_superior": n["limite_superior"],
                }
                for n in datos.get("niveles", [])
            ],
        }
        self.store.staged["umbrales"].setdefault(id_especie, []).append(nuevo)

    def listar_por_especie(self, id_especie: int, solo_activas: bool = False):
        items = self.store.staged["umbrales"].get(id_especie, [])
        if solo_activas:
            items = [u for u in items if u["es_activo"]]
        return [
            SimpleNamespace(
                id_variable_ambiental=u["id_variable_ambiental"],
                unidad_medida=u["unidad_medida"],
                valor_min=u["valor_min"],
                valor_max=u["valor_max"],
                niveles=[
                    SimpleNamespace(
                        nivel=_ValueAttr(n["nivel"]),
                        limite_inferior=n["limite_inferior"],
                        limite_superior=n["limite_superior"],
                    )
                    for n in u["niveles"]
                ],
            )
            for u in items
        ]


class PatologiaRepoFake:
    def __init__(self, store: TransactionalStore) -> None:
        self.store = store

    def eliminar_todas_de_especie(self, id_especie: int) -> None:
        self.store.staged["patologias"][id_especie] = []

    def vincular_desde_snapshot(self, id_especie: int, datos: dict) -> None:
        self.store.staged["patologias"].setdefault(id_especie, []).append(
            {
                "nombre": datos["nombre"],
                "descripcion": datos.get("descripcion"),
                "es_activo": datos.get("es_activo", True),
            }
        )

    def listar_por_especie(self, id_especie: int):
        return [
            SimpleNamespace(nombre=_ValorAttr(p["nombre"]), descripcion=p["descripcion"], es_activo=p["es_activo"])
            for p in self.store.staged["patologias"].get(id_especie, [])
        ]


class AplicacionRepoFake:
    def __init__(self) -> None:
        self.guardada = None

    def guardar(self, aplicacion):
        self.guardada = aplicacion
        aplicacion.id_aplicacion_plantilla = 1
        return aplicacion


class PlantillaRepoFake:
    def __init__(self, snapshot: dict) -> None:
        self._snapshot = snapshot

    def obtener_por_id(self, _id_plantilla):
        return Plantilla.crear(
            id_especie=ID_ESPECIE,
            id_usuario=1,
            template_name="plantilla-test-atomicidad",
            params_snapshot=self._snapshot,
            version=1,
            fecha_creacion=datetime.now(timezone.utc),
        )


class EspecieRepoFake:
    def obtener_por_id(self, _id_especie):
        especie = Especie.crear(
            nombre=NombreEspecie("EspecieAtomicidad"),
            descripcion=None,
            fecha_creacion=datetime(2020, 1, 1, tzinfo=timezone.utc),
        )
        especie.id_especie = ID_ESPECIE
        especie.fecha_actualizacion = FECHA_ACTUALIZACION_DB
        return especie


def _armar_use_case(store: TransactionalStore, dbfake: DbFake, snapshot: dict, aplicacion_repo=None):
    return AplicarPlantillaUseCase(
        db=dbfake,
        plantilla_repo=PlantillaRepoFake(snapshot),
        especie_repo=EspecieRepoFake(),
        ciclo_repo=CicloRepoFake(store),
        metrica_repo=MetricaRepoFake(store),
        umbral_repo=UmbralRepoFake(store),
        patologia_repo=PatologiaRepoFake(store),
        aplicacion_repo=aplicacion_repo or AplicacionRepoFake(),
    )


def _dto() -> AplicarPlantillaDTO:
    return AplicarPlantillaDTO(
        id_especie_destino=ID_ESPECIE,
        fecha_actualizacion_especie_destino=FECHA_ACTUALIZACION_DB,
    )


def _usuario() -> UsuarioActual:
    return UsuarioActual(id_usuario=1, id_token=1, id_rol=1)


# ---------------------------------------------------------------------------
# TC-M09-230: snapshot previo
# ---------------------------------------------------------------------------


def test_TC230_captura_estado_anterior_antes_de_escribir_nada():
    store = TransactionalStore(_estado_con_datos_previos())
    dbfake = DbFake(store)
    use_case = _armar_use_case(store, dbfake, snapshot={"schema_version": 1})

    estado = use_case._capturar_estado(ID_ESPECIE)

    assert estado["ciclos_biologicos"] == [
        {"nombre": "Alevinaje", "duracion_dias": 30, "descripcion": "Etapa inicial"}
    ]
    assert estado["metricas_produccion"][0]["nombre"] == "peso_promedio_kg"
    assert estado["umbrales_ambientales"][0]["id_variable_ambiental"] == 1
    assert estado["patologias"][0]["nombre"] == "Hongos"
    # Nada se escribio todavia: staged == committed.
    assert store.staged == store.committed
    assert dbfake.commits == 0
    assert dbfake.rollbacks == 0


# ---------------------------------------------------------------------------
# TC-M09-232 / TC-M09-233 / TC-M09-242: fallo real a mitad de camino
# ---------------------------------------------------------------------------


def test_TC232_233_242_fallo_de_persistencia_revierte_todo_sin_dejar_cambios_parciales():
    store = TransactionalStore(_estado_con_datos_previos())
    dbfake = DbFake(store)
    aplicacion_repo = AplicacionRepoFake()

    # Snapshot con DOS categorias: ciclos (valido, se procesa primero y SI se
    # alcanza a insertar) y metricas_produccion (con el mismo defecto real
    # confirmado en TC-M09-G118: falta unidad_medida/tipo_medicion/
    # aplica_a_tipo_activo). El fallo ocurre A MITAD del proceso: cuando
    # sucede, ya se desactivaron TODAS las categorias anteriores (ciclos,
    # metricas, umbrales, patologias) y ya se inserto el nuevo ciclo.
    snapshot_con_metrica_malformada = {
        "schema_version": 1,
        "ciclos_biologicos": [{"nombre": "Engorde", "duracion_dias": 60, "descripcion": "Etapa final"}],
        "metricas_produccion": [{"nombre": "peso_promedio_kg", "valor": 1.5}],
    }

    use_case = _armar_use_case(
        store, dbfake, snapshot=snapshot_con_metrica_malformada, aplicacion_repo=aplicacion_repo
    )

    estado_antes = use_case._capturar_estado(ID_ESPECIE)

    with pytest.raises(KeyError):
        use_case.execute(1, _dto(), _usuario())

    # TC-M09-232: ante el fallo de persistencia, se hizo rollback (nunca commit).
    assert dbfake.rollbacks == 1
    assert dbfake.commits == 0

    # TC-M09-233: la configuracion final es identica, campo por campo, a la
    # que existia antes de intentar aplicar.
    estado_despues = use_case._capturar_estado(ID_ESPECIE)
    assert estado_despues == estado_antes

    # TC-M09-242: aunque el ciclo "Engorde" SI llego a insertarse y todas las
    # categorias ya habian sido desactivadas/eliminadas antes del punto de
    # falla, nada de eso sobrevive al rollback.
    assert store.committed == store.staged
    ciclos_finales = store.committed["ciclos"][ID_ESPECIE]
    assert not any(c["nombre"] == "Engorde" for c in ciclos_finales)
    assert all(c["es_activo"] for c in ciclos_finales if c["nombre"] == "Alevinaje")
    metricas_finales = store.committed["metricas"][ID_ESPECIE]
    assert all(m["es_activo"] for m in metricas_finales if m["nombre"] == "peso_promedio_kg")
    umbrales_finales = store.committed["umbrales"][ID_ESPECIE]
    assert all(u["es_activo"] for u in umbrales_finales)
    patologias_finales = store.committed["patologias"][ID_ESPECIE]
    assert len(patologias_finales) == 1 and patologias_finales[0]["nombre"] == "Hongos"

    # Tampoco debe quedar un registro de historial para este intento fallido.
    assert aplicacion_repo.guardada is None


# ---------------------------------------------------------------------------
# Control positivo: confirma que el arnes de pruebas SI distingue exito de
# fallo (no esta sesgado a fallar siempre).
# ---------------------------------------------------------------------------


def test_control_aplicacion_exitosa_hace_commit_una_sola_vez_y_actualiza_estado():
    store = TransactionalStore(_estado_con_datos_previos())
    dbfake = DbFake(store)
    snapshot_valido = {
        "schema_version": 1,
        "metricas_produccion": [
            {
                "nombre": "talla_cm",
                "unidad_medida": "cm",
                "tipo_medicion": "LONGITUD",
                "aplica_a_tipo_activo": "AMBOS",
            }
        ],
    }
    use_case = _armar_use_case(store, dbfake, snapshot=snapshot_valido)

    resultado = use_case.execute(1, _dto(), _usuario())

    assert dbfake.commits == 1
    assert dbfake.rollbacks == 0
    assert resultado.id_aplicacion_plantilla == 1

    metricas_finales = store.committed["metricas"][ID_ESPECIE]
    nuevas = [m for m in metricas_finales if m["nombre"] == "talla_cm"]
    assert nuevas and nuevas[0]["es_activo"] is True
    anteriores = [m for m in metricas_finales if m["nombre"] == "peso_promedio_kg"]
    assert anteriores and anteriores[0]["es_activo"] is False
