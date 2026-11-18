# | Fecha      | Nombre   | Que se hizo                                                      |
# |------------|----------|------------------------------------------------------------------|
# | 2026-11-14 | Arekkazu | M08 RF-103: catálogo de widgets con opciones y regla del semáforo |
"""Catálogo de widgets del dashboard (RF-103): qué muestra cada uno y qué se puede configurar.

La fila de ``modulo9.widgets`` dice quién ve el widget (su recurso RBAC) y dónde se coloca; esta
definición dice cómo se dibuja (``visual``), de dónde salen sus datos (``fuente``) y qué opciones
elige el usuario en Personalización. Cada opción tiene valor por defecto: un widget sin configurar
funciona igual.

Los nombres de opción, de visual y los valores de las listas son claves que el front traduce; aquí
no hay textos para el usuario salvo los mensajes de "sin datos".
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Optional

from src.shared.errors import ValidationError

# Tipos de opción. Las de áreas, especies y sensores ofrecen los de la finca activa.
AREAS = "areas"
AREA = "area"
ESPECIES = "especies"
SENSORES = "sensores"
LISTA = "lista"

_MAX_ELEGIDOS = 50


@dataclass(frozen=True)
class Opcion:
    """Lo que el usuario puede elegir en un widget."""
    nombre: str
    tipo: str
    valores: tuple = ()
    defecto: Any = None


@dataclass(frozen=True)
class DefinicionWidget:
    """Cómo se dibuja un widget, de dónde salen sus datos y qué se configura.

    ``fijos`` son parámetros que el usuario no elige (ej. la variable de «Temperatura»).
    ``requiere_finca`` en False: el widget funciona sin finca activa (widgets contables, cuyo
    alcance es el del Contador en Finanzas). ``reacciona_a_alertas``: el front lo pide de nuevo
    apenas llega un push de alerta, sin esperar el ciclo de refresco.
    """
    clave: str
    visual: str
    fuente: str
    opciones: tuple[Opcion, ...] = ()
    fijos: Mapping[str, Any] = field(default_factory=dict)
    requiere_finca: bool = True
    reacciona_a_alertas: bool = False


_O_AREAS = Opcion("areas", AREAS, defecto=[])
_O_AREA = Opcion("area", AREA)
_O_ESPECIES = Opcion("especies", ESPECIES, defecto=[])
_O_SENSORES = Opcion("sensores", SENSORES, defecto=[])
_O_RANGO = Opcion("rango", LISTA, ("6h", "24h", "7d"), "24h")


def _lecturas(clave: str, variable: str) -> DefinicionWidget:
    return DefinicionWidget(clave, "lecturas", "lecturas", (_O_AREA,), {"variable": variable},
                            reacciona_a_alertas=True)


def _historico(clave: str, variable: str) -> DefinicionWidget:
    return DefinicionWidget(clave, "linea", "historico", (_O_AREA, _O_RANGO), {"variable": variable})


DEFINICIONES: dict[str, DefinicionWidget] = {d.clave: d for d in (
    # Productor
    DefinicionWidget("semaforo_areas", "semaforo", "semaforo", (_O_AREAS,), reacciona_a_alertas=True),
    _lecturas("temp_galpon", "temperatura"),
    _lecturas("hum_galpon", "humedad"),
    _lecturas("ph_estanque", "ph"),
    _lecturas("co2_galpon", "co2"),
    DefinicionWidget("inventario_especies", "barras", "inventario", (_O_ESPECIES,)),
    DefinicionWidget("valor_inventario", "cifra", "valor_inventario",
                     (Opcion("vista", LISTA, ("TOTAL", "POR_METODO"), "TOTAL"),), requiere_finca=False),
    DefinicionWidget("ultimos_eventos", "lista", "eventos", (Opcion("cantidad", LISTA, (5, 10), 5),)),
    DefinicionWidget("conversion_alimenticia", "conversion", "conversion", (_O_ESPECIES,)),
    DefinicionWidget("alertas", "lista", "alertas_activas", (_O_AREAS,), reacciona_a_alertas=True),
    DefinicionWidget("alertas_crit", "lista", "alertas_activas", (_O_AREAS,), {"solo_criticas": True},
                     reacciona_a_alertas=True),
    _historico("hist_temp", "temperatura"),
    _historico("hist_hum", "humedad"),
    # Veterinario
    DefinicionWidget("riesgo_sanitario_alto", "lista", "riesgo_alto", (_O_ESPECIES,)),
    DefinicionWidget("distribucion_riesgo", "barras", "distribucion_riesgo",
                     (_O_ESPECIES, Opcion("periodo", LISTA, ("24h", "7d", "30d"), "7d"))),
    DefinicionWidget("retroalimentacion_pendiente", "lista", "retroalimentacion_pendiente"),
    DefinicionWidget("alertas_sanitarias", "barras", "alertas_sanitarias", reacciona_a_alertas=True),
    # Contador
    DefinicionWidget("periodos_abiertos", "lista", "periodos", requiere_finca=False),
    DefinicionWidget("reconocimientos_pendientes", "lista", "reconocimientos", requiere_finca=False),
    DefinicionWidget("integraciones_fallidas", "lista", "integraciones",
                     (Opcion("dias", LISTA, (7, 30), 7),), requiere_finca=False),
    DefinicionWidget("precios_por_vencer", "lista", "precios",
                     (Opcion("dias", LISTA, (7, 15, 30), 15),), requiere_finca=False),
    # Ingeniero de Campo
    DefinicionWidget("estado_iot", "estados", "estado_dispositivos", (_O_AREAS,)),
    DefinicionWidget("dispositivos_sin_senal", "lista", "sin_senal", (_O_AREAS,)),
    DefinicionWidget("lecturas_area", "lecturas", "lecturas", (_O_AREA, _O_SENSORES), reacciona_a_alertas=True),
    DefinicionWidget("cal_sensores", "lista", "calibraciones", (_O_AREAS,)),
    DefinicionWidget("cfg_pendiente", "lista", "configuracion_pendiente", (_O_AREAS,)),
    DefinicionWidget("fincas_estado", "lista", "estado_fincas", requiere_finca=False),
)}


# Variables que muestra cada widget de lectura: (texto, cómo se busca en el nombre de la variable).
# Por nombre y no por id: los ids de ``modulo9.variables_ambientales`` no son los mismos en todas las bases.
VARIABLES = {
    "temperatura": ("temperatura", "inicio"),
    "humedad": ("humedad", "inicio"),
    "ph": ("ph", "inicio"),
    "co2": ("co2", "contiene"),
}


def coincide_variable(variable: Optional[str], nombre: Optional[str], categoria: Optional[str]) -> bool:
    """Si la variable de una lectura es la que pide el widget. La temperatura corporal no es ambiental."""
    if variable is None:
        return True
    if not nombre or (categoria or "").upper() == "ANIMAL":
        return False
    texto, modo = VARIABLES[variable]
    nombre = nombre.lower()
    return nombre.startswith(texto) if modo == "inicio" else texto in nombre


def patron_variable(variable: str) -> str:
    """El mismo criterio de :func:`coincide_variable` como patrón ``LIKE``."""
    texto, modo = VARIABLES[variable]
    return f"{texto}%" if modo == "inicio" else f"%{texto}%"


def _error_opcion() -> ValidationError:
    return ValidationError(
        code="VAL_ENTRADA",
        message="La configuración del widget no es válida. Recarga la página y vuelve a elegir sus opciones.",
        field="parametros",
    )


def _ids(valor: Any) -> list[int]:
    if not isinstance(valor, list) or len(valor) > _MAX_ELEGIDOS:
        raise _error_opcion()
    if any(isinstance(v, bool) or not isinstance(v, int) or v <= 0 for v in valor):
        raise _error_opcion()
    return list(dict.fromkeys(valor))


def validar_parametros(definicion: DefinicionWidget, parametros: Any) -> dict[str, Any]:
    """Opciones elegidas por el usuario, validadas contra el catálogo del widget.

    Nombre de opción desconocido o valor fuera de su tipo o de su lista → 400. No comprueba que
    las áreas o sensores sean de una finca del usuario: al leer, el widget solo usa los de la finca
    activa (ya validada), así que un id ajeno guardado no muestra nada ajeno.
    """
    if parametros is None:
        return {}
    if not isinstance(parametros, dict):
        raise _error_opcion()
    opciones = {o.nombre: o for o in definicion.opciones}
    limpios: dict[str, Any] = {}
    for nombre, valor in parametros.items():
        opcion = opciones.get(nombre)
        if opcion is None:
            raise _error_opcion()
        if valor is None:
            continue
        if opcion.tipo in (AREAS, ESPECIES, SENSORES):
            limpios[nombre] = _ids(valor)
        elif opcion.tipo == AREA:
            if isinstance(valor, bool) or not isinstance(valor, int) or valor <= 0:
                raise _error_opcion()
            limpios[nombre] = valor
        elif valor in opcion.valores and type(valor) is type(opcion.defecto):
            limpios[nombre] = valor
        else:
            raise _error_opcion()
    return limpios


def resolver_parametros(definicion: DefinicionWidget, guardados: Any) -> dict[str, Any]:
    """Parámetros con que se consulta el widget: defecto, lo guardado y lo fijo, en ese orden.

    Lo guardado se validó al guardar; si el catálogo cambió después y ya no es válido, se usan los
    valores por defecto en vez de romper el widget.
    """
    base = {o.nombre: o.defecto for o in definicion.opciones}
    try:
        base.update(validar_parametros(definicion, guardados))
    except ValidationError:
        pass
    base.update(definicion.fijos)
    return base


# Estados del semáforo (RF-103 R5). SIN_DATOS: el área no tiene de dónde medir (sin sensores o todos
# caídos por fallas técnicas) y tampoco predicciones; las alertas técnicas no pintan rojo ni amarillo.
VERDE, AMARILLO, ROJO, SIN_DATOS = "VERDE", "AMARILLO", "ROJO", "SIN_DATOS"


def estado_semaforo(criticas: int, advertencias: int, sin_datos: bool) -> str:
    """Una crítica de cualquier fuente → ROJO; solo advertencias → AMARILLO; nada → VERDE."""
    if criticas:
        return ROJO
    if advertencias:
        return AMARILLO
    return SIN_DATOS if sin_datos else VERDE


MENSAJE_ERROR = "No pudimos traer estos datos. Se intentará de nuevo en la próxima actualización."

# Un widget vacío por falta de datos (no por buenas noticias: sin alertas o sin pendientes es OK).
MENSAJES_SIN_DATOS = {
    "semaforo": "Esta finca no tiene áreas activas para mostrar.",
    "lecturas": "No hay sensores con lecturas en el área elegida.",
    "historico": "No hay lecturas en el período elegido.",
    "inventario": "Esta finca todavía no tiene animales registrados.",
    "valor_inventario": "Todavía no hay animales con valor reconocido.",
    "eventos": "Todavía no hay eventos registrados en esta finca.",
    "conversion": "Todavía no hay cálculos de conversión alimenticia en esta finca.",
    "distribucion_riesgo": "No hay predicciones de salud en el período elegido.",
    "estado_dispositivos": "Esta finca no tiene dispositivos registrados.",
    "calibraciones": "Esta finca no tiene dispositivos registrados.",
    "estado_fincas": "No tienes fincas asignadas.",
}
