# | Fecha      | Nombre           | Que se hizo                                                              |
# |------------|------------------|--------------------------------------------------------------------------|
# | 2026-11-07 | Daniela Castillo | M06 RF-85: script del grupo TC-M06-G29 (pytest + sandbox, rol Contador) |
# | 2026-11-08 | Daniela Castillo | G29: 128 toma el id del evento de la respuesta de M02 (el SELECT del sandbox no ve modulo2) |
# | 2026-11-08 | Daniela Castillo | G29 revisado: cada caso abre su run; 128 verifica la restricción NOT NULL del vínculo y que no hay operación con id del cliente; 130 verifica el hecho completo hacia RF-86 (periódico y consumo); 131 compara contra el cálculo RF-84 del activo |
# | 2026-11-12 | Daniela Castillo | M06 reprueba V2.0 (RF-83 v1.2, RF-84 v1.1, RF-85 v1.2, RF-88 v2.0): el reporte HTML pasa a llamarse reporte-TC-M06-G29-V2.0.html |
# | 2026-11-13 | Daniela Castillo | M06 V2.0 (2.ª pasada): la base de datos pasa a ser la fuente de verdad (SQL ya funciona), expectativas alineadas con las correcciones de Desarrollo (notas de la versión 1.4.0) y las precondiciones que fallan ya no se omiten: quedan en rojo con diagnóstico |
"""
TC-M06-G29 - Integración del reconocimiento del producto con RF-43, RF-109, RF-86 y RF-84.   RF-85.   Casos: TC-M06-128 a TC-M06-131.

Precondición común (RF-43): el evento productivo de M02 exige una fase activa de un ciclo de M09; se usa la especie productiva sembrada de TEST (Cachama, métrica
PESO en kg) y la fase se asigna con POST /activos-biologicos/{id}/fases. Si M02 responde 5xx o rechaza, el caso queda BLOQUEADO. Un producto no se registra dos veces
el mismo día para un activo (409): cada cosecha usa un activo propio. Costos de venta de M09: 2 %+3 %+1 %.
- 128: el producto queda ligado al id del evento productivo de M02 y se reconoce al procesar la cola (<= 3 s). El reconocimiento no recibe un id_evento del cliente: «evento inexistente» no es reproducible.
- 129: las cuentas del asiento salen de la matriz de la especie (RF-109), para producto periódico y de consumo (se comparan con las cuentas cargadas en el run).
- 130: el hecho PRODUCTO_AGRICOLA llega a RF-86 como una línea con origen en el reconocimiento (tabla reconocimientos_productos_agricolas, id del producto), el activo, el valor_producto y, en consumo, el valor_reduccion; con cuentas de la matriz y estado REGISTRADA.
- 131: 150 kg a 4.000,00 = 600.000,0000; costos 6 % -> valor 564.000,0000 (la ficha usa costos de 15.000 -> 585.000: los valores del RF son ejemplos). RF-84 no recibe el bruto como entrada (sale de magnitud por precio de RF-89, ver G18):
  se compara el valor_producto con el cálculo RF-84 del activo de 150 kg con el mismo precio de 4.000,00 por kg y los mismos costos, idéntico al 4.º decimal.
- Newman: no se usa en este grupo. La única medida de tiempo es 128 (<= 3 s, RNF-85-01) y, como en G30, todos los casos dependen de la fase activa del activo (RF-37) y del evento productivo (RF-43), que no se arman con una colección sin el escenario del run; el tiempo se mide con el responseTime de POST /finanzas/eventos/procesar en pytest.

Cómo correrlo:
    python -m pytest "tests/Test_Testing/Test_Modulo6/RF-85/TC-M06-G29/TC-M06-G29.py" -v -s -rs --noconftest --html="tests/Test_Testing/Test_Modulo6/RF-85/TC-M06-G29/reporte-TC-M06-G29-V2.0.html" --self-contained-html
"""
from __future__ import annotations

import pathlib
import random
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from m06_lib import *  # noqa: F401,F403,E402

@pytest.fixture(scope="module")
def env():
    e = Entorno(("admin", "ingeniero"))
    yield e
    e.cerrar()

def _rutas_api(env, *palabras):
    """Rutas del OpenAPI de TEST que contienen alguna de las palabras. None si no se puede leer."""
    r = env.call("GET", "/openapi.json", sandbox=False)
    if r.status != 200 or not isinstance(r.data, dict):
        return None
    return sorted(f"{m.upper()} {ruta}" for ruta, ops in (r.data.get("paths") or {}).items() for m in ops
                  if any(p in ruta.lower() for p in palabras))


def _periodico(env, kg="150", precio="4000.00", kg_activo="1000", precio_activo="20000.00"):
    esc = env.escenario_producto("PRODUCCION", precio_activo, precio)
    ida = env.activo_productivo(esc, kg_activo)
    base = env.calculo(ida)
    r = env.cosechar(ida, kg)
    assert r.status == 200, r
    return esc, ida, r, base


def _linea_completa(env, ida):
    """Línea del hecho PRODUCTO_AGRICOLA con su origen; None si la columna de origen no se puede consultar."""
    return env.sql("SELECT tabla_origen, id_origen, id_activo_biologico, estado::text AS estado, sentido::text AS sentido, valor, cuenta_debito, cuenta_credito "
                   f"FROM modulo6.lineas_asiento_nic41 WHERE id_activo_biologico = {int(ida)} AND NOT es_reverso AND tipo_hecho::text = 'PRODUCTO_AGRICOLA' ORDER BY 1")


def test_TC_M06_128_el_producto_queda_ligado_al_evento_productivo(env):
    env.nuevo_run()
    env.presupuesto(70)
    esc = env.escenario_producto("PRODUCCION", "20000.00", "4000.00")
    ida = env.activo_productivo(esc, "1000")
    ev = env.prep(env.cosecha(ida, "150"), (200, 201), "evento productivo RF-43")
    id_evento = ev.get("id_eventos")      # el SELECT del sandbox no ve modulo2: el id sale de la respuesta de M02
    assert id_evento is not None, f"M02 no devolvió el id del evento productivo: {ev}"
    r = env.procesar_eventos()
    assert r.status == 200, r
    filas = env.producto_sql(ida)
    if not filas:
        no_verificable(f"no se reconoció el producto (eventos: {env.tipos_auditoria(ida)}).")
    assert int(filas[-1]["id_evento_productivo"]) == int(id_evento), f"el producto debía quedar ligado al evento {id_evento}: {filas[-1]}"
    assert r.ms <= 3000, f"el procesamiento tardó {r.ms:.0f} ms (> 3000)"
    obs(f"Producto ligado al evento productivo {id_evento}; tiempo del procesamiento: {r.ms:.0f} ms (límite 3000 ms, RNF-85-01).")


def test_TC_M06_128b_sin_evento_productivo_no_hay_reconocimiento(env):
    """RNF-85-03: ningún producto puede reconocerse sin un evento productivo que lo sustente."""
    env.nuevo_run()
    env.presupuesto(30)
    nulo = env.sql("SELECT is_nullable FROM information_schema.columns WHERE table_schema = 'modulo6' "
                   "AND table_name = 'reconocimientos_productos_agricolas' AND column_name = 'id_evento_productivo'")
    assert nulo, "no se encontró la columna id_evento_productivo en reconocimientos_productos_agricolas"
    assert nulo[0]["is_nullable"] == "NO", "id_evento_productivo admite nulos: se podría reconocer un producto sin evento productivo"
    rutas = _rutas_api(env, "producto")
    if rutas is None:
        no_verificable("no se pudo leer /openapi.json de TEST.")
    # Desarrollo (#1010, PR #1060) agregó POST /finanzas/productos/pendientes/{id_evento}/reconocimiento: retoma un evento pendiente que YA existe
    # (costos de venta manuales, RF-85 FA-2). No crea productos sin evento: se comprueba con un id_evento inexistente (ficha 128, segundo paso).
    permitida = "POST /finanzas/productos/pendientes/{id_evento}/reconocimiento"
    escritura = [x for x in rutas if not x.startswith("GET ") and x != permitida]
    assert not escritura, f"hay operaciones para crear o cambiar productos desde el cliente: {escritura}"
    antes = uno(env.sql("SELECT count(*) FROM modulo6.reconocimientos_productos_agricolas"))
    if permitida in rutas:
        cuerpo = {"costos_manuales": {"transporte": "1000", "comisiones": "1000", "impuestos": "1000", "otros": "0"},
                  "justificacion": "Costos de venta manuales QA TC-M06 con soporte documental: cotización No. 888."}
        r = env.call("POST", "/finanzas/productos/pendientes/999999999/reconocimiento", "admin", json=cuerpo)
        obs(f"Reconocer con un id_evento inexistente (999999999): HTTP {r.status} {(r.text or '')[:300]}")
        assert r.status not in (401, 403), f"la llamada no llegó a evaluarse por permisos/token (HTTP {r.status}): no prueba el id inexistente. {r}"
        assert 400 <= r.status < 500, f"un id_evento inexistente debía rechazarse con 4xx y respondió {r}"
        despues = uno(env.sql("SELECT count(*) FROM modulo6.reconocimientos_productos_agricolas"))
        assert despues == antes, f"con un id_evento inexistente no debía quedar ningún reconocimiento (antes {antes}, después {despues})"
    obs(f"Operaciones de producto del cliente: {rutas}. El único camino de escritura retoma un evento pendiente existente; «evento inexistente» se rechaza y la restricción "
        "NOT NULL garantiza el vínculo con el evento productivo.")


def test_TC_M06_129_cuentas_del_asiento_salen_de_la_matriz_periodico(env):
    env.nuevo_run()
    env.presupuesto(70)
    esc, ida, _, _ = _periodico(env)
    lineas = env.lineas_producto(ida)
    esperado = esc.cuentas.get(("PRODUCTO_AGRICOLA", "UNICO"))
    if not lineas or not esperado:
        no_verificable(f"sin línea o sin cuentas propias de la matriz (líneas: {len(lineas)}, matriz propia: {bool(esperado)}).")
    assert (lineas[-1]["cuenta_debito"], lineas[-1]["cuenta_credito"]) == esperado, lineas[-1]


def test_TC_M06_129b_cuentas_del_asiento_salen_de_la_matriz_consumo(env):
    env.nuevo_run()
    env.presupuesto(70)
    esc = env.escenario_producto("CONSUMO", "20000.00")
    ida = env.activo_productivo(esc, "1000")
    assert env.cosechar(ida, "250").status == 200
    lineas = env.lineas_producto(ida)
    esperado = esc.cuentas.get(("PRODUCTO_AGRICOLA", "TRASLADO"))
    if not lineas or not esperado:
        no_verificable(f"sin línea o sin cuentas propias de la matriz (líneas: {len(lineas)}, matriz propia: {bool(esperado)}).")
    assert (lineas[-1]["cuenta_debito"], lineas[-1]["cuenta_credito"]) == esperado, lineas[-1]


def test_TC_M06_130_se_emite_el_hecho_producto_agricola_hacia_rf86(env):
    env.nuevo_run()
    env.presupuesto(70)
    esc, ida, _, _ = _periodico(env)
    filas = env.producto_sql(ida)
    lineas = env.lineas_producto(ida)
    if not filas:
        no_verificable(f"no se reconoció el producto (eventos: {env.tipos_auditoria(ida)}).")
    assert len(lineas) == 1 and lineas[0]["id_origen"] == filas[-1]["id"], f"la línea debe nacer del reconocimiento del producto: {lineas}"
    assert dec(lineas[0]["valor"]) == dec(filas[-1]["valor_producto"]), (lineas[0], filas[-1])
    completa = _linea_completa(env, ida)
    assert completa, f"la base de datos debe tener la línea PRODUCTO_AGRICOLA del activo {ida}"
    c = completa[-1]
    assert c["tabla_origen"] == "reconocimientos_productos_agricolas", f"la línea debe referir al reconocimiento del producto: {c}"
    assert int(c["id_activo_biologico"]) == int(ida) and int(c["id_origen"]) == int(filas[-1]["id"]), c
    assert c["estado"] == "REGISTRADA" and c["cuenta_debito"] and c["cuenta_credito"], f"la línea debe quedar registrada con cuentas: {c}"


def test_TC_M06_130b_hecho_de_consumo_lleva_el_valor_de_la_reduccion(env):
    env.nuevo_run()
    env.presupuesto(70)
    esc = env.escenario_producto("CONSUMO", "20000.00")
    ida = env.activo_productivo(esc, "1000")
    assert env.cosechar(ida, "250").status == 200
    filas, lineas = env.producto_sql(ida), env.lineas_producto(ida)
    if not filas:
        no_verificable(f"no se reconoció el producto (eventos: {env.tipos_auditoria(ida)}).")
    p = filas[-1]
    assert len(lineas) == 1 and lineas[0]["id_origen"] == p["id"], f"la línea debe nacer del reconocimiento del producto: {lineas}"
    assert lineas[0]["sentido"] == "TRASLADO", lineas[0]
    assert dec(lineas[0]["valor"]) == dec(p["valor_producto"]) == dec(p["valor_reduccion_activo"]), (lineas[0], p)
    db = _linea_completa(env, ida)
    assert db and db[-1]["tabla_origen"] == "reconocimientos_productos_agricolas" and int(db[-1]["id_origen"]) == int(p["id"]), f"base de datos: origen de la línea de consumo: {db}"


def test_TC_M06_131_valor_del_producto_coincide_con_la_formula_de_rf84(env):
    env.nuevo_run()
    env.presupuesto(90)
    # Activo de 150 kg con el mismo precio de 4.000,00 por kg: su cálculo RF-84 es el de referencia (bruto 600.000,0000)
    esc, ida, _, base = _periodico(env, "150", "4000.00", kg_activo="150", precio_activo="4000.00")
    filas = env.producto_sql(ida)
    if not filas:
        no_verificable(f"no se reconoció el producto (eventos: {env.tipos_auditoria(ida)}).")
    p = filas[-1]
    if base is None:
        no_verificable("el activo no tiene un cálculo RF-84 previo a la cosecha con el cual comparar.")
    assert dec(base["valor_razonable_bruto"]) == dec("600000.0000"), f"el cálculo RF-84 de referencia debía partir del bruto 600.000,0000: {base}"
    assert dec(p["valor_producto"]) == dec(base["valor_neto"]), f"valor_producto {p['valor_producto']} vs neto RF-84 {base['valor_neto']}"
    assert dec(p["valor_producto"]) == trunc2(vn(150, "4000.00")), p
    costos = (dec(p["costo_venta_producto"]) * 150)
    assert cerca(costos, dec("600000") - dec(base["valor_neto"]), "0.05"), f"costos de venta del producto: {p}"
