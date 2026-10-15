"""RF-32 - Mecanismo de snapshot y rollback ante fallo de persistencia (v2.0).

v2.0 (2026-10): actualizado al codigo vigente de `AplicarPlantillaUseCase`
(rc.48 y rc.50). Que cambio respecto de la v1:
  * El constructor ahora exige `auditoria_repo` y `variable_repo`.
  * `execute()` envuelve el flujo y, ante cualquier excepcion, hace
    `db.rollback()` y despues registra el intento FALLIDO en la auditoria con
    su PROPIO commit. La v1 afirmaba `commits == 0`, que ya no es cierto: hay
    exactamente 1 commit, pero es el de la auditoria y ocurre DESPUES del
    rollback. Lo que realmente importa (y se verifica ahora) es que ese commit
    no deje filtrar ningun cambio parcial.
  * Se rechaza una version superada de la plantilla (`obtener_ultima_version`).
  * `_capturar_estado` lee tambien `tipo_dato` y `es_obligatorio` de las metricas.
  * Se agrega el orden de eventos de la sesion (`DbFake.events`) para verificar
    "rollback primero, commit solo de auditoria despues".

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
                    "tipo_dato": "NUMERICO",
                    "es_obligatorio": False,
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
        # Tabla de auditoria (auditoria_plantillas): participa de la misma
        # logica staged/committed que el resto de las tablas.
        "auditoria": [],
    }


def _solo_datos(estado: dict) -> dict:
    """Estado de configuracion sin la tabla de auditoria (para comparar
    "la configuracion de la especie" antes/despues)."""
    return {k: v for k, v in estado.items() if k != "auditoria"}


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
        self.events: list[str] = []  # orden real: "rollback" / "commit"

    def commit(self) -> None:
        self.commits += 1
        self.events.append("commit")
        self.store.commit()

    def rollback(self) -> None:
        self.rollbacks += 1
        self.events.append("rollback")
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


def _inferir_tipo_dato(_tipo_medicion: str) -> str:
    return "NUMERICO"


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
        # El repo real hace: datos.get('tipo_dato') or inferir(datos['tipo_medicion'])
        # -> si falta tipo_medicion tambien lanza KeyError.
        tipo_dato = datos.get("tipo_dato") or _inferir_tipo_dato(datos["tipo_medicion"])
        nueva = {
            "nombre": datos["nombre"],
            "unidad_medida": datos["unidad_medida"],
            "tipo_medicion": datos["tipo_medicion"],
            "aplica_a_tipo_activo": datos["aplica_a_tipo_activo"],
            "tipo_dato": tipo_dato,
            "es_obligatorio": datos.get("es_obligatorio", False),
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
                tipo_dato=_ValueAttr(m["tipo_dato"]),
                es_obligatorio=m["es_obligatorio"],
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


class AuditoriaRepoFake:
    """Sustituye a SqlAlchemyAuditoriaPlantillaRepository.registrar: hace
    "flush" (escribe en staged); solo el commit de la sesion lo confirma."""

    def __init__(self, store: TransactionalStore) -> None:
        self.store = store

    def registrar(
        self,
        *,
        id_usuario,
        tipo_operacion,
        valores_nuevos,
        id_plantilla=None,
        resultado="EXITOSO",
        valores_anteriores=None,
    ) -> None:
        self.store.staged["auditoria"].append(
            {
                "id_plantilla": id_plantilla,
                "id_usuario": id_usuario,
                "tipo_operacion": tipo_operacion,
                "resultado": resultado,
                "valores_nuevos": valores_nuevos,
            }
        )


class VariableRepoFake:
    """Todas las variables ambientales existen y estan activas (este archivo
    no prueba referencias huerfanas)."""

    def obtener_por_id(self, id_variable):
        return SimpleNamespace(id_variable_ambiental=id_variable, es_activo=True)


class PlantillaRepoFake:
    def __init__(self, snapshot: dict) -> None:
        self._snapshot = snapshot

    def _plantilla(self):
        return Plantilla.crear(
            id_especie=ID_ESPECIE,
            id_usuario=1,
            template_name="plantilla-test-atomicidad",
            params_snapshot=self._snapshot,
            version=1,
            fecha_creacion=datetime.now(timezone.utc),
        )

    def obtener_por_id(self, _id_plantilla):
        return self._plantilla()

    def obtener_ultima_version(self, _template_name):
        # La version 1 es la vigente (no hay una posterior).
        return self._plantilla()


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
        auditoria_repo=AuditoriaRepoFake(store),
        variable_repo=VariableRepoFake(),
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
    assert estado["metricas_produccion"][0]["tipo_dato"] == "NUMERICO"
    assert estado["umbrales_ambientales"][0]["id_variable_ambiental"] == 1
    assert estado["patologias"][0]["nombre"] == "Hongos"
    # Nada se escribio todavia: staged == committed.
    assert store.staged == store.committed
    assert dbfake.commits == 0
    assert dbfake.rollbacks == 0


# ---------------------------------------------------------------------------
# TC-M09-232 / TC-M09-233 / TC-M09-242: fallo real a mitad de camino
# ---------------------------------------------------------------------------

# Snapshot con DOS categorias: ciclos (valido, se procesa primero y SI se
# alcanza a insertar) y metricas_produccion (con el defecto real confirmado en
# TC-M09-G118: falta unidad_medida/tipo_medicion/aplica_a_tipo_activo). El
# fallo ocurre A MITAD del proceso: cuando sucede, ya se desactivaron TODAS las
# categorias de la especie (ciclos, metricas, umbrales, patologias) y ya se
# inserto el nuevo ciclo "Engorde".
SNAPSHOT_CON_METRICA_MALFORMADA = {
    "schema_version": 1,
    "ciclos_biologicos": [{"nombre": "Engorde", "duracion_dias": 60, "descripcion": "Etapa final"}],
    "metricas_produccion": [{"nombre": "peso_promedio_kg", "valor": 1.5}],
}


def _ejecutar_con_fallo():
    store = TransactionalStore(_estado_con_datos_previos())
    dbfake = DbFake(store)
    aplicacion_repo = AplicacionRepoFake()
    use_case = _armar_use_case(
        store, dbfake, snapshot=SNAPSHOT_CON_METRICA_MALFORMADA, aplicacion_repo=aplicacion_repo
    )
    estado_antes = use_case._capturar_estado(ID_ESPECIE)
    datos_antes = _solo_datos(store.committed)

    with pytest.raises(KeyError):
        use_case.execute(1, _dto(), _usuario())

    return store, dbfake, aplicacion_repo, use_case, estado_antes, datos_antes


def test_TC232_233_242_fallo_de_persistencia_revierte_todo_sin_dejar_cambios_parciales():
    store, dbfake, aplicacion_repo, use_case, estado_antes, datos_antes = _ejecutar_con_fallo()

    # TC-M09-232: ante el fallo de persistencia se hizo rollback, y el rollback
    # fue lo PRIMERO que toco la sesion (antes de cualquier commit).
    assert dbfake.rollbacks == 1
    assert dbfake.events[0] == "rollback"

    # TC-M09-233: la configuracion final es identica, campo por campo, a la
    # que existia antes de intentar aplicar.
    estado_despues = use_case._capturar_estado(ID_ESPECIE)
    assert estado_despues == estado_antes

    # TC-M09-242: aunque el ciclo "Engorde" SI llego a insertarse y todas las
    # categorias ya habian sido desactivadas/eliminadas antes del punto de
    # falla, nada de eso sobrevive. Se comprueba sobre lo CONFIRMADO en BD
    # (committed) -- incluido el commit posterior de la auditoria: ese commit
    # NO debe dejar filtrar ningun cambio parcial.
    assert _solo_datos(store.committed) == datos_antes
    ciclos_finales = store.committed["ciclos"][ID_ESPECIE]
    assert not any(c["nombre"] == "Engorde" for c in ciclos_finales)
    assert all(c["es_activo"] for c in ciclos_finales if c["nombre"] == "Alevinaje")
    metricas_finales = store.committed["metricas"][ID_ESPECIE]
    assert all(m["es_activo"] for m in metricas_finales if m["nombre"] == "peso_promedio_kg")
    umbrales_finales = store.committed["umbrales"][ID_ESPECIE]
    assert all(u["es_activo"] for u in umbrales_finales)
    patologias_finales = store.committed["patologias"][ID_ESPECIE]
    assert len(patologias_finales) == 1 and patologias_finales[0]["nombre"] == "Hongos"

    # Tampoco debe quedar un registro de historial de aplicacion exitosa.
    assert aplicacion_repo.guardada is None


def test_TC232_complemento_el_intento_fallido_queda_auditado_en_transaccion_propia():
    """Complemento v2.0 (cambio de codigo rc.48, INC-M09-04-124): el intento
    fallido se audita DESPUES del rollback y en su propio commit. El RF-32 no
    exige auditar los fallos; esto verifica que el mecanismo agregado no rompa
    la atomicidad (el orden rollback -> commit-de-auditoria es el que garantiza
    que el commit solo confirma la fila de auditoria)."""
    store, dbfake, _aplicacion_repo, _uc, _antes, _datos = _ejecutar_con_fallo()

    assert dbfake.events == ["rollback", "commit"]
    assert len(store.committed["auditoria"]) == 1
    registro = store.committed["auditoria"][0]
    assert registro["tipo_operacion"] == "APPLY"
    assert registro["resultado"] == "FALLIDO"
    assert registro["id_plantilla"] == 1
    assert registro["id_usuario"] == 1
    assert registro["valores_nuevos"]["id_especie_destino"] == ID_ESPECIE


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
    assert dbfake.events == ["commit"]
    assert resultado.id_aplicacion_plantilla == 1

    metricas_finales = store.committed["metricas"][ID_ESPECIE]
    nuevas = [m for m in metricas_finales if m["nombre"] == "talla_cm"]
    assert nuevas and nuevas[0]["es_activo"] is True
    anteriores = [m for m in metricas_finales if m["nombre"] == "peso_promedio_kg"]
    assert anteriores and anteriores[0]["es_activo"] is False
