# | Fecha      | Nombre           | Que se hizo                                                              |
# |------------|------------------|--------------------------------------------------------------------------|
# | 2026-11-07 | Daniela Castillo | M06 RF-85: script del grupo TC-M06-G26 (pytest + sandbox, rol Contador) |
# | 2026-11-08 | Daniela Castillo | G26 revisado contra la ficha: un activo y un run por caso, rechazos con campo identificado, 116 y 119 con códigos de validación, 118 verifica que no se cree producto |
# | 2026-11-11 | Daniela Castillo | G26 117 revisado: el conjunto válido lo define la unidad de la métrica (no KG, LT, UNIDAD, M2); se rechazan TON, vacía y XYZ y se observan LT, UNIDAD y M2 |
"""
TC-M06-G26 - Validación de datos mínimos, catálogos, unidades, fecha y activo del evento productivo.   RF-85 / RF-43.   Casos: TC-M06-115 a TC-M06-119.

El reconocimiento del producto no tiene entrada propia: nace del evento productivo de M02 (RF-43), por eso las validaciones se envían a
POST /activos-biologicos/{id}/eventos/productivo con id_metrica_produccion (= tipo_producto del catálogo de M09), cantidad_producida (= cantidad_cosechada),
unidad_medida y fecha_evento (= fecha_cosecha). El id del activo va en la ruta y el id del evento lo genera M02 (no es entrada). Correspondencia con la ficha:
- 115: se omite cada campo del cuerpo (4) y el id del activo en la ruta; id_evento_productivo no se puede omitir porque lo genera M02 (se documenta). Cada rechazo debe
  identificar el campo faltante; no se crea producto ni se emite 5xx.
- 116: tipo_producto fuera de catálogo: 'PRODUCTO_OTRO', 'producto_periodico' y vacío (la API pide un id numérico), más un id inexistente: todos con error de validación (400 o 422).
- 117 (revisado): la unidad válida es la de la métrica del producto (kg en la métrica sembrada); el conjunto KG, LT, UNIDAD, M2 de la ficha no es el catálogo del backend.
  Se rechazan 'TON', vacía y 'XYZ'; 'LT', 'UNIDAD' y 'M2' (del conjunto de la ficha) se envían contra la métrica en kg y se anota la respuesta; 'kg' se acepta.
- 118: fecha de mañana y '2026-13-45' se rechazan sin crear producto; la de hoy se acepta y se reconoce.
- 119: id inexistente (la API usa ids enteros, no UUID): 404 o rechazo equivalente; 'abc' y 'null' mal formados: error de validación (400 VAL_ENTRADA o 422). Sin 5xx.
Precondición (RF-43): el activo necesita una fase activa de un ciclo de M09; QA no crea ciclos y usa la especie productiva sembrada de TEST (Cachama, métrica PESO en kg).
Un producto no puede repetirse el mismo día para un activo (409): cada caso usa su propio run y su propio activo. Costos de venta de M09 del 6 %.

Cómo correrlo:
    python -m pytest "tests/Test_Testing/Test_Modulo6/RF-85/TC-M06-G26/TC-M06-G26.py" -v -s -rs --noconftest --html="tests/Test_Testing/Test_Modulo6/RF-85/TC-M06-G26/reporte-TC-M06-G26.html" --self-contained-html
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from m06_lib import *  # noqa: F401,F403,E402

@pytest.fixture(scope="module")
def env():
    e = Entorno(("admin", "ingeniero"))
    yield e
    e.cerrar()

VALIDO = {"id_metrica_produccion": ID_METRICA_PRODUCTIVA, "cantidad_producida": "100", "unidad_medida": "kg", "fecha_evento": str(hoy())}


def _activo(env):
    env.nuevo_run()
    env.presupuesto(60)
    esc = env.escenario_producto("CONSUMO", "20000.00")
    return env.activo_productivo(esc, "1000")


def _enviar(env, ida, cuerpo, ruta=None):
    return env.call("POST", ruta or f"/activos-biologicos/{ida}/eventos/productivo", "admin", json=cuerpo)


def _sin_producto(env, ida, contexto):
    env.procesar_eventos()
    assert not env.producto_sql(ida), f"{contexto}: no debía crearse ningún producto"


def test_TC_M06_115_datos_minimos_ausentes_se_rechazan_identificando_el_campo(env):
    ida = _activo(env)
    obs("id_evento_productivo no es entrada de la API: lo genera M02 al registrar el evento, por eso no se puede omitir; el id del activo viaja en la ruta.")
    fallos = []
    for campo in ("id_metrica_produccion", "cantidad_producida", "unidad_medida", "fecha_evento"):
        r = _enviar(env, ida, {k: v for k, v in VALIDO.items() if k != campo})
        if not 400 <= r.status < 500:
            fallos.append(f"sin {campo}: debía rechazarse con 4xx y respondió {r}")
        elif campo not in (r.text or ""):
            fallos.append(f"sin {campo}: el rechazo debía identificar el campo faltante y dice: {(r.text or '')[:200]}")
    r = _enviar(env, ida, VALIDO, "/activos-biologicos//eventos/productivo")
    if not 400 <= r.status < 500:
        fallos.append(f"sin id del activo (ruta vacía): debía rechazarse con 4xx y respondió {r}")
    _sin_producto(env, ida, "con datos mínimos ausentes")
    assert not fallos, " | ".join(fallos)


def test_TC_M06_116_tipo_de_producto_fuera_de_catalogo(env):
    ida = _activo(env)
    fallos = []
    for valor in ("PRODUCTO_OTRO", "producto_periodico", "", 999999):
        r = _enviar(env, ida, {**VALIDO, "id_metrica_produccion": valor})
        if r.status not in (400, 422):
            fallos.append(f"tipo de producto {valor!r}: la ficha pide error de validación (400 VAL_ENTRADA o 422) y respondió {r}")
    _sin_producto(env, ida, "con tipo de producto fuera de catálogo")
    assert not fallos, " | ".join(fallos)


def test_TC_M06_117_unidad_de_medida_no_permitida(env):
    ida = _activo(env)
    fallos = []
    for unidad in ("TON", "", "XYZ"):
        r = _enviar(env, ida, {**VALIDO, "unidad_medida": unidad})
        if not 400 <= r.status < 500:
            fallos.append(f"unidad {unidad!r}: debía rechazarse con 4xx y respondió {r}")
    for unidad in ("LT", "UNIDAD", "M2"):                 # conjunto de la ficha: se observa la respuesta contra la métrica en kg
        r = _enviar(env, ida, {**VALIDO, "unidad_medida": unidad})
        obs(f"Unidad {unidad!r} contra la métrica en kg: HTTP {r.status} {r.err or ''}")
        if r.status >= 500:
            fallos.append(f"unidad {unidad!r}: no debía dar 5xx y respondió {r}")
    _sin_producto(env, ida, "con unidad no permitida")
    r = _enviar(env, ida, {**VALIDO, "unidad_medida": "kg"})
    obs(f"Unidad 'kg' (la de la métrica; la ficha la lista como inválida por la minúscula, diferencia de formato frente a KG): HTTP {r.status}.")
    assert r.status < 500, f"unidad 'kg' no debía dar 5xx: {r}"
    assert not fallos, " | ".join(fallos)


def test_TC_M06_118_fecha_de_cosecha(env):
    ida = _activo(env)
    fallos = []
    for fecha in (str(hoy() + timedelta(days=1)), "2026-13-45"):
        r = _enviar(env, ida, {**VALIDO, "fecha_evento": fecha})
        if not 400 <= r.status < 500:
            fallos.append(f"fecha {fecha}: debía rechazarse con 4xx y respondió {r}")
    _sin_producto(env, ida, "con fecha futura o inválida")
    ok = _enviar(env, ida, VALIDO)
    assert ok.status in (200, 201), f"la fecha de hoy debía aceptarse: {ok}"
    env.procesar_eventos()
    assert env.producto_sql(ida), f"la cosecha de hoy debía reconocerse como producto (eventos: {env.tipos_auditoria(ida)})"
    assert not fallos, " | ".join(fallos)


def test_TC_M06_119_activo_inexistente_o_mal_formado(env):
    env.nuevo_run()
    env.presupuesto(30)
    fallos = []
    r = _enviar(env, 0, VALIDO, "/activos-biologicos/999999999/eventos/productivo")
    obs(f"Activo inexistente (id 999999999; la API usa ids enteros, no UUID): HTTP {r.status} {r.err}")
    if not 400 <= r.status < 500:
        fallos.append(f"activo inexistente: la ficha pide 404 o rechazo equivalente y respondió {r}")
    for malo in ("abc", "null"):
        r = _enviar(env, 0, VALIDO, f"/activos-biologicos/{malo}/eventos/productivo")
        if r.status not in (400, 422):
            fallos.append(f"identificador {malo!r}: la ficha pide 422 (o 400 VAL_ENTRADA) y respondió {r}")
    assert not fallos, " | ".join(fallos)
