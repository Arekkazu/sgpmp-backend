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

from decimal import Decimal, InvalidOperation
from typing import Any, Callable

from src.configuration.domain.value_objects.aplica_tipo_activo import AplicaTipoActivo
from src.configuration.domain.value_objects.nivel_alerta import NivelAlerta
from src.configuration.domain.value_objects.tipo_medicion import TipoMedicion

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

# ── Reglas de tipo ───────────────────────────────────────────────────────────
# Una regla es (descripción para el usuario, predicado). La descripción viaja en
# el mensaje de error y en `GET /configuracion/plantillas/esquema`, así que el
# cliente sabe qué se espera antes de enviar y por qué se le rechazó.

Regla = tuple[str, Callable[[Any], bool]]


def _es_texto(valor: Any) -> bool:
    return isinstance(valor, str) and valor.strip() != ""


def _es_entero_positivo(valor: Any) -> bool:
    # bool es subclase de int en Python: `True` no es una duración válida.
    return isinstance(valor, int) and not isinstance(valor, bool) and valor > 0


def _es_numero(valor: Any) -> bool:
    """Acepta lo que `Decimal(...)` del repositorio convierte sin reventar."""
    if isinstance(valor, bool):
        return False
    if isinstance(valor, int):
        return True
    try:
        return Decimal(str(valor)).is_finite()
    except (InvalidOperation, ValueError, TypeError):
        return False


def _uno_de(*opciones: str) -> Regla:
    return (f"uno de {list(opciones)}", lambda valor: valor in opciones)


TEXTO: Regla = ("texto no vacío", _es_texto)
ENTERO_POSITIVO: Regla = ("entero positivo", _es_entero_positivo)
NUMERO: Regla = ("número", _es_numero)

#: Campos obligatorios de cada ítem, con su tipo. Son los que
#: `*_desde_snapshot` de los repositorios lee sin `.get()` y convierte con
#: `int()`/`Decimal()`: si faltan o traen basura, RF-32 revienta al aplicar, y
#: para entonces la plantilla ya está guardada y es inmutable.
CAMPOS_REQUERIDOS: dict[str, dict[str, Regla]] = {
    "ciclos_biologicos": {
        "nombre": TEXTO,
        "duracion_dias": ENTERO_POSITIVO,
    },
    "patologias": {
        "nombre": TEXTO,
    },
    "metricas_produccion": {
        "nombre": TEXTO,
        "unidad_medida": TEXTO,
        "tipo_medicion": _uno_de(*(m.value for m in TipoMedicion)),
        "aplica_a_tipo_activo": _uno_de(*(a.value for a in AplicaTipoActivo)),
    },
    "umbrales_ambientales": {
        "id_variable_ambiental": ENTERO_POSITIVO,
        "unidad_medida": TEXTO,
        "valor_min": NUMERO,
        "valor_max": NUMERO,
    },
}

#: Forma de cada elemento de `umbrales_ambientales[].niveles`. La clave
#: `niveles` es opcional (el repositorio usa `.get('niveles', [])`), pero si
#: viene, sus elementos se leen por índice y se convierten a `Decimal`.
CAMPOS_NIVEL_ALERTA: dict[str, Regla] = {
    "nivel": _uno_de(*(n.value for n in NivelAlerta)),
    "limite_inferior": NUMERO,
    "limite_superior": NUMERO,
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
            "Cada campo obligatorio declara su tipo: los textos no pueden ir "
            "vacíos, duracion_dias e id_variable_ambiental son enteros "
            "positivos, los límites y valores son números, y tipo_medicion, "
            "aplica_a_tipo_activo y nivel se validan contra sus enums.",
        ),
    },
)


def versiones_compatibles() -> tuple[int, ...]:
    """Versiones de snapshot que esta versión del sistema puede aplicar."""
    return tuple(CHANGELOG[0]["compatible_con"])


def es_compatible(schema_version: Any) -> bool:
    """Indica si un snapshot guardado bajo `schema_version` se puede aplicar."""
    return schema_version in versiones_compatibles()


def _validar_item(item: dict[str, Any], reglas: dict[str, Regla], ubicacion: str) -> list[str]:
    """Comprueba que el ítem traiga sus campos obligatorios y con el tipo debido."""
    errores: list[str] = []

    faltantes = [campo for campo in reglas if item.get(campo) is None]
    if faltantes:
        errores.append(f"{ubicacion}: faltan los campos {faltantes}.")

    for campo, (descripcion, es_valido) in reglas.items():
        valor = item.get(campo)
        if valor is not None and not es_valido(valor):
            errores.append(f"{ubicacion}.{campo} debe ser {descripcion}; llegó {valor!r}.")

    return errores


def _validar_niveles(umbral: dict[str, Any], ubicacion: str) -> list[str]:
    """Valida `niveles` del umbral. La clave es opcional; su contenido no."""
    niveles = umbral.get("niveles")
    if niveles is None:
        return []
    if not isinstance(niveles, list):
        return [f"{ubicacion}.niveles debe ser una lista de niveles de alerta."]

    errores: list[str] = []
    for posicion, nivel in enumerate(niveles):
        sub_ubicacion = f"{ubicacion}.niveles[{posicion}]"
        if not isinstance(nivel, dict):
            errores.append(f"{sub_ubicacion} debe ser un objeto.")
            continue
        errores.extend(_validar_item(nivel, CAMPOS_NIVEL_ALERTA, sub_ubicacion))
    return errores


def claves_fuera_de_alcance(snapshot: dict[str, Any]) -> list[str]:
    """Devuelve las claves de otros módulos que el RF-30 excluye del alcance.

    Va aparte de `validar_snapshot` porque el RF le asigna a este caso su
    propio código: el FA "Intento de inclusión de parámetros fuera de alcance"
    responde `422`, mientras que un fallo de esquema responde `400`. El use
    case lo consulta antes de nada para poder lanzar el 422.

    Args:
        snapshot: Contenido de `params_snapshot` tal como llega del cliente.

    Returns:
        Claves fuera de alcance encontradas, ordenadas. Vacía si no hay.
    """
    return sorted(set(snapshot) & CLAVES_FUERA_DE_ALCANCE)


def validar_snapshot(snapshot: dict[str, Any]) -> list[str]:
    """Valida la estructura de un `params_snapshot` contra el esquema vigente.

    No reporta las claves fuera de alcance: el RF-30 las castiga con `422` y
    esta función alimenta al DTO, que solo puede producir `400`. Si el snapshot
    trae alguna, esta función calla del todo para que el 422 del use case sea
    el que llegue al cliente, y no un 400 de "plantilla vacía" disparado por
    unas categorías que además no correspondían.

    Args:
        snapshot: Contenido de `params_snapshot` tal como llega del cliente.

    Returns:
        Lista de problemas encontrados, en lenguaje de usuario. Vacía si el
        snapshot cumple el esquema, o si su fallo es de alcance.
    """
    if claves_fuera_de_alcance(snapshot):
        return []

    errores: list[str] = []

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
            ubicacion = f"{categoria}[{posicion}]"
            if not isinstance(item, dict):
                errores.append(f"{ubicacion} debe ser un objeto.")
                continue
            errores.extend(_validar_item(item, CAMPOS_REQUERIDOS[categoria], ubicacion))
            if categoria == "umbrales_ambientales":
                errores.extend(_validar_niveles(item, ubicacion))

    if total_items == 0:
        errores.append(
            "Plantilla vacía: debe seleccionar al menos un parámetro "
            f"({', '.join(CATEGORIAS)}) para generar una plantilla válida."
        )

    return errores
