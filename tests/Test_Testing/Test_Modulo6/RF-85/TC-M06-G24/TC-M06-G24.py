# | Fecha      | Nombre           | Que se hizo                                                              |
# |------------|------------------|--------------------------------------------------------------------------|
# | 2026-11-07 | Daniela Castillo | M06 RF-85: script del grupo TC-M06-G24 (pytest + sandbox, rol Contador) |
# | 2026-11-08 | Daniela Castillo | M06 RF-85 G24: el estado del activo en M02 viene en nombre_estado (110c y 110d lo leían de «estado» y quedaba vacío) |
# | 2026-11-08 | Daniela Castillo | M06 RF-85 G24: se separan los casos por lo que exige la ficha (valor_producto por RF-84 con el precio del producto, activo en 0, estado COSECHADO_COMPLETAMENTE, baja RF-45, asiento) y cada caso abre su propio run |
"""
TC-M06-G24 - Reconocimiento de PRODUCTO_DE_CONSUMO: reducción proporcional, cosecha total y asiento.   RF-85 (CU04, FA-4).   Casos: TC-M06-109 a TC-M06-111.

Precondición común (RF-43): el evento productivo de M02 exige una fase activa de un ciclo de M09. QA no puede crear ciclos, por lo que se usa la
especie productiva sembrada de TEST (Cachama: métrica PESO en kg, ciclo 4; variables QA_ID_ESPECIE_PRODUCTIVA / _METRICA_ / _CICLO_) y se asigna la fase con
POST /activos-biologicos/{id}/fases. Si M02 responde 5xx o rechaza (defecto previo de RF-37), el caso queda BLOQUEADO. Un producto no puede registrarse
dos veces el mismo día para un activo (409): cada caso usa un activo propio. Valores con costos de venta de M09 del 2 %+3 %+1 % (6 %).
Consumo = especie clasificada CONSUMO con categoría PESO_KG: el backend vuelve a medir el activo, calcula proporción = cosechado / magnitud actual y reduce el activo
por valor_reduccion = valor neto x proporción (truncado a 2 decimales, RF-86); el asiento es PRODUCTO_AGRICOLA/TRASLADO. Escala: activo de 1.000 kg a 20.000,00 ->
18.800.000,0000; cosecha de 250 kg (25 %) -> reducción 4.700.000,00 y activo en 14.100.000,0000 con 750 kg. En 110 el RF pide estado COSECHADO_COMPLETAMENTE e iniciar la
baja de RF-45; el backend solo avisa al Contador (MEDICION_PENDIENTE): se verifican el valor del activo, el estado y la baja por separado.
La ficha pide valor_producto = cantidad x precio del producto (RF-89) - costos de venta, calculado por RF-84 (RF-85 paso 5 y CA-5); el backend en consumo traslada a inventario
por el valor en libros reducido (valor_producto = valor_reduccion) para que el asiento cuadre (RF-85 paso 7): se verifica el valor del producto aparte (109b y 111b).
Se usa un precio de producto distinto al del activo (12.000,00 por kg frente a 20.000,00): 250 kg x 12.000,00 = 3.000.000,00 menos 6 % = 2.820.000,00 frente a la reducción 4.700.000,00.

Cómo correrlo:
    python -m pytest "tests/Test_Testing/Test_Modulo6/RF-85/TC-M06-G24/TC-M06-G24.py" -v -s -rs --noconftest --html="tests/Test_Testing/Test_Modulo6/RF-85/TC-M06-G24/reporte-TC-M06-G24.html" --self-contained-html
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

P_ACT, P_PROD = "20000.00", "12000.00"
NETO_ACTIVO = vn(1000, P_ACT)                            # 18.800.000,0000
REDUCCION_25 = trunc2(NETO_ACTIVO * dec("0.25"))         # 4.700.000,00
NETO_PRODUCTO_250 = vn(250, P_PROD)                      # 2.820.000,0000 (cantidad x precio del producto - 6 %)


def _consumo(env, kg):
    esc = env.escenario_producto("CONSUMO", P_ACT, P_PROD)
    ida = env.activo_productivo(esc, "1000")
    antes = env.calculo(ida)
    assert dec(antes["magnitud"]) == 1000 and dec(antes["valor_neto"]) == NETO_ACTIVO, f"activo antes de la cosecha: {antes}"
    assert env.cosechar(ida, kg).status == 200
    return esc, ida


def _producto(env, ida):
    filas = env.producto_sql(ida)
    if not filas:
        no_verificable(f"no se reconoció el producto (eventos: {env.tipos_auditoria(ida)}).")
    return filas[-1]


def _estado_m02(env, ida):
    r = env.call("GET", f"/activos-biologicos/{ida}", "admin")
    d = r.data if isinstance(r.data, dict) else {}
    return str(d.get("nombre_estado") or d.get("estado") or "").upper(), r


@pytest.fixture(scope="module")
def total(env):
    """Cosecha del 100 % (1.000 kg de 1.000 kg): un solo run para los casos 110, 110b, 110c y 110d."""
    env.nuevo_run()
    env.presupuesto(80)
    esc, ida = _consumo(env, "1000")
    return esc, ida


def test_TC_M06_109_consumo_parcial_reduce_el_activo_proporcionalmente(env):
    env.nuevo_run()
    env.presupuesto(70)
    esc, ida = _consumo(env, "250")
    p = _producto(env, ida)
    assert p["tipo"] == "PRODUCTO_DE_CONSUMO" and dec(p["proporcion_cosechada"]) == dec("0.25"), p
    assert dec(p["valor_reduccion_activo"]) == REDUCCION_25, f"valor_reduccion esperado {REDUCCION_25} (18.800.000 x 0,25): {p}"
    c = env.calculo(ida)
    assert dec(c["magnitud"]) == 750 and dec(c["valor_neto"]) == vn(750, P_ACT), f"el activo debía quedar en 750 kg y {vn(750, P_ACT)}: {c}"


def test_TC_M06_109b_valor_del_producto_de_consumo_por_rf84_con_el_precio_del_producto(env):
    """Ficha 109: valor_producto calculado por RF-84 con la cantidad y el precio informados (RF-85 paso 5 y CA-5)."""
    env.nuevo_run()
    env.presupuesto(70)
    esc, ida = _consumo(env, "250")
    p = _producto(env, ida)
    obs(f"valor_producto {p['valor_producto']}, precio_mercado_producto {p['precio_mercado_producto']}, valor_reduccion {p['valor_reduccion_activo']} "
        f"(esperado por la ficha: 250 x {P_PROD} - 6 % = {trunc2(NETO_PRODUCTO_250)})")
    assert dec(p["valor_producto"]) == trunc2(NETO_PRODUCTO_250), (
        f"valor_producto esperado {trunc2(NETO_PRODUCTO_250)} (250 kg x {P_PROD} - costos de venta, RF-84): {p}")
    assert dec(p["precio_mercado_producto"]) == dec(P_PROD), f"el precio del producto debe ser el de RF-89 ({P_PROD}): {p}"


def test_TC_M06_110_consumo_total_reduce_el_valor_total_del_activo(env, total):
    esc, ida = total
    p = _producto(env, ida)
    assert p["tipo"] == "PRODUCTO_DE_CONSUMO" and dec(p["proporcion_cosechada"]) == 1, p
    assert dec(p["valor_reduccion_activo"]) == trunc2(NETO_ACTIVO), f"valor_reduccion = valor total del activo {trunc2(NETO_ACTIVO)}: {p}"
    avisos = [e for e in env.auditoria(ida) if e.get("tipo_evento") == "MEDICION_PENDIENTE"]
    obs(f"alerta al Contador por cosecha completa (MEDICION_PENDIENTE): {len(avisos)}")


def test_TC_M06_110b_consumo_total_deja_el_activo_en_cero(env, total):
    esc, ida = total
    _producto(env, ida)
    c = env.calculo(ida)
    assert dec(c["valor_neto"]) == 0, f"el activo debe quedar en 0,0000 tras la cosecha total (valor vigente {c['valor_neto']}, magnitud {c['magnitud']})"


def test_TC_M06_110c_consumo_total_marca_cosechado_completamente(env, total):
    esc, ida = total
    _producto(env, ida)
    estado, r = _estado_m02(env, ida)
    if estado != "COSECHADO_COMPLETAMENTE":
        bloqueado(f"funcionalidad no implementada: el RF-85 FA-4 pide marcar el activo COSECHADO_COMPLETAMENTE y en M02 queda {estado!r} ({r}).")


def test_TC_M06_110d_consumo_total_inicia_la_baja_de_rf45(env, total):
    esc, ida = total
    _producto(env, ida)
    estado, r = _estado_m02(env, ida)
    tipos = env.tipos_auditoria(ida)
    if estado != "BAJA" and "BAJA_ACTIVO_REGISTRADA" not in tipos:
        bloqueado(f"funcionalidad no implementada: el RF-85 FA-4 pide iniciar la baja del activo en RF-45; el estado en M02 es {estado!r}, "
                  f"no hay baja registrada y los eventos son {tipos}.")


def test_TC_M06_111_asiento_de_consumo_inventario_contra_activo(env):
    env.nuevo_run()
    env.presupuesto(70)
    esc, ida = _consumo(env, "250")
    lineas = env.lineas_producto(ida)
    if not lineas:
        no_verificable(f"no hay línea PRODUCTO_AGRICOLA (eventos: {env.tipos_auditoria(ida)}).")
    assert len(lineas) == 1 and lineas[0]["sentido"] == "TRASLADO", lineas
    ln = lineas[0]
    p = env.producto_sql(ida)[-1]
    assert dec(ln["valor"]) == dec(p["valor_reduccion_activo"]) == REDUCCION_25, f"el crédito al activo biológico debe ser el valor_reduccion {REDUCCION_25}: {ln} / {p}"
    assert ln["estado"] != "PENDIENTE_CUENTA" and ln["cuenta_debito"] and ln["cuenta_credito"] and ln["cuenta_debito"] != ln["cuenta_credito"], ln
    esperado = esc.cuentas.get(("PRODUCTO_AGRICOLA", "TRASLADO"))
    assert esperado, "la matriz RF-109 del escenario debe tener PRODUCTO_AGRICOLA/TRASLADO"
    assert (ln["cuenta_debito"], ln["cuenta_credito"]) == esperado, f"las cuentas deben salir de la matriz RF-109: {ln}"
    obs(f"Asiento: débito {ln['cuenta_debito']} (inventario) / crédito {ln['cuenta_credito']} (activo biológico) por {ln['valor']}: una sola línea, cuadra.")


def test_TC_M06_111b_debito_por_valor_del_producto_y_diferencia_segun_la_matriz(env):
    """Ficha 111: débito a inventario por valor_producto (RF-84), crédito al activo por valor_reduccion y la diferencia según la matriz RF-109."""
    env.nuevo_run()
    env.presupuesto(70)
    esc, ida = _consumo(env, "250")
    lineas = env.lineas_producto(ida)
    if not lineas:
        no_verificable(f"no hay línea PRODUCTO_AGRICOLA (eventos: {env.tipos_auditoria(ida)}).")
    valores = sorted(dec(l["valor"]) for l in lineas)
    assert trunc2(NETO_PRODUCTO_250) in valores, (
        f"debe haber un débito a inventario por valor_producto {trunc2(NETO_PRODUCTO_250)} (250 kg x {P_PROD} - 6 %) y la diferencia con la reducción "
        f"{REDUCCION_25} registrada según la matriz; líneas del asiento: {valores}")
