"""Esquema versionado del `params_snapshot` de plantillas (RF-30, RF-31).

El RNF de mantenibilidad del RF-30 exige que el esquema JSON del snapshot se
gestione con *schema versioning* y que "cualquier actualización del esquema debe
documentarse con el número de versión correspondiente". Este módulo es esa
documentación: versión vigente, forma que debe tener cada categoría y changelog
de cambios estructurales, en un solo sitio y expuesto por
`GET /configuracion/plantillas/esquema` para que sea consultable sin leer código.

Cómo se actualiza el esquema:

1. subir `SCHEMA_VERSION_ACTUAL`;
2. agregar la entrada correspondiente al inicio de `CHANGELOG`, con qué cambió y
   con qué versiones anteriores sigue siendo estructuralmente compatible;
3. dejar fuera de `compatible_con` las versiones que ya no se pueden aplicar:
   `AplicarPlantillaUseCase` las rechaza con `412` (FA "Legacy Template" del
   RF-30) en vez de aplicar un snapshot que ya no entiende.

Las plantillas son inmutables, así que un snapshot guardado conserva para
siempre el `schema_version` con el que se creó; la compatibilidad se resuelve al
aplicar, nunca migrando la fila.
"""
from __future__ import annotations

from typing import Any

SCHEMA_VERSION_ACTUAL = 1

#: Categorías que el RF-30 autoriza dentro de una plantilla.
CATEGORIAS: tuple[str, ...] = (
    "ciclos_biologicos",
    "patologias",
    "metricas_produccion",
    "umbrales_ambientales",
)

CLAVES_PERMITIDAS: frozenset[str] = frozenset({"schema_version", *CATEGORIAS})

#: Claves de otros módulos que el RF-30 excluye explícitamente del alcance.
CLAVES_FUERA_DE_ALCANCE: frozenset[str] = frozenset({
    "dispositivos_iot", "infraestructuras", "dashboard", "identidad_visual",
    "fincas", "sensores", "configuraciones_globales",
})

#: Campos obligatorios de cada ítem. Son los que `*_desde_snapshot` de los
#: repositorios lee sin `.get()`: si faltan, RF-32 reventaría al aplicar.
CAMPOS_REQUERIDOS: dict[str, tuple[str, ...]] = {
    "ciclos_biologicos": ("nombre", "duracion_dias"),
    "patologias": ("nombre",),
    "metricas_produccion": ("nombre", "unidad_medida", "tipo_medicion", "aplica_a_tipo_activo"),
    "umbrales_ambientales": ("id_variable_ambiental", "unidad_medida", "valor_min", "valor_max"),
}

#: Changelog consultable de versiones del esquema, de la más reciente a la más
#: antigua. `compatible_con` lista los `schema_version` que esta versión del
#: sistema todavía sabe aplicar.
CHANGELOG: tuple[dict[str, Any], ...] = (
    {
        "version": 1,
        "fecha": "2026-06-21",
        "compatible_con": (1,),
        "cambios": (
            "Versión inicial del esquema de params_snapshot.",
            "Categorías admitidas: ciclos_biologicos, patologias, "
            "metricas_produccion, umbrales_ambientales.",
            "ciclos_biologicos: nombre, duracion_dias, descripcion (opcional).",
            "patologias: nombre, descripcion (opcional), es_activo (opcional).",
            "metricas_produccion: nombre, unidad_medida, tipo_medicion, "
            "aplica_a_tipo_activo.",
            "umbrales_ambientales: id_variable_ambiental, unidad_medida, "
            "valor_min, valor_max y niveles[] con nivel, limite_inferior y "
            "limite_superior.",
        ),
    },
)


def versiones_compatibles() -> tuple[int, ...]:
    """Versiones de snapshot que esta versión del sistema puede aplicar."""
    return tuple(CHANGELOG[0]["compatible_con"])


def es_compatible(schema_version: Any) -> bool:
    """Indica si un snapshot guardado bajo `schema_version` se puede aplicar."""
    return schema_version in versiones_compatibles()


def validar_snapshot(snapshot: dict[str, Any]) -> list[str]:
    """Valida la estructura de un `params_snapshot` contra el esquema vigente.

    Args:
        snapshot: Contenido de `params_snapshot` tal como llega del cliente.

    Returns:
        Lista de problemas encontrados, en lenguaje de usuario. Vacía si el
        snapshot cumple el esquema.
    """
    errores: list[str] = []

    fuera_de_alcance = sorted(set(snapshot) & CLAVES_FUERA_DE_ALCANCE)
    if fuera_de_alcance:
        errores.append(
            f"Parámetros fuera de alcance: {fuera_de_alcance}. Las plantillas solo "
            "pueden contener parámetros productivos y umbrales ambientales."
        )

    desconocidas = sorted(set(snapshot) - CLAVES_PERMITIDAS - CLAVES_FUERA_DE_ALCANCE)
    if desconocidas:
        errores.append(f"Claves no reconocidas en params_snapshot: {desconocidas}.")

    total_items = 0
    for categoria in CATEGORIAS:
        items = snapshot.get(categoria)
        if items is None:
            continue
        if not isinstance(items, list):
            errores.append(f"'{categoria}' debe ser una lista de parámetros.")
            continue
        total_items += len(items)
        for posicion, item in enumerate(items):
            if not isinstance(item, dict):
                errores.append(f"{categoria}[{posicion}] debe ser un objeto.")
                continue
            faltantes = [c for c in CAMPOS_REQUERIDOS[categoria] if item.get(c) is None]
            if faltantes:
                errores.append(f"{categoria}[{posicion}]: faltan los campos {faltantes}.")

    if total_items == 0:
        errores.append(
            "Plantilla vacía: debe seleccionar al menos un parámetro "
            f"({', '.join(CATEGORIAS)}) para generar una plantilla válida."
        )

    return errores
