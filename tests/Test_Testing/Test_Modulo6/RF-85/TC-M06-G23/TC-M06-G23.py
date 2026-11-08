# | Fecha      | Nombre           | Que se hizo                                                              |
# |------------|------------------|--------------------------------------------------------------------------|
# | 2026-11-07 | Daniela Castillo | M06 RF-85: script del grupo TC-M06-G23 (pytest + sandbox, rol Contador) |
# | 2026-11-08 | Daniela Castillo | M06 RF-85 G23: el valor del activo se lee de sus propios cálculos (no del del producto); se agregan los costos del producto, el cálculo RF-84 y el estado de la línea |
# | 2026-11-08 | Daniela Castillo | M06 RF-85 G23: costo_venta_producto se guarda por unidad (210 por kg); la prueba compara el total (costo por unidad x cantidad) |
"""
TC-M06-G23 - Reconocimiento de PRODUCTO_PERIODICO: valor del producto, activo sin reducción y asiento.   RF-85 (CU04).   Casos: TC-M06-107 y TC-M06-108.

Precondición común (RF-43): el evento productivo de M02 exige una fase activa de un ciclo de M09. QA no puede crear ciclos, por lo que se usa la
especie productiva sembrada de TEST (Cachama: métrica PESO en kg, ciclo 4; variables QA_ID_ESPECIE_PRODUCTIVA / _METRICA_ / _CICLO_) y se asigna la fase con
POST /activos-biologicos/{id}/fases. Si M02 responde 5xx o rechaza (defecto previo de RF-37), el caso queda BLOQUEADO. Un producto no puede registrarse
dos veces el mismo día para un activo (409): cada caso usa un activo propio. Valores con costos de venta de M09 del 2 %+3 %+1 % (6 %).
Escala: 200 kg a 3.500,00 por kg = 700.000,0000 menos 6 % = 658.000,0000 (la ficha usa 200 LT y costos de 20.000). El activo de 1.000 kg a 20.000,00
queda en 18.800.000,0000. El asiento esperado: inventario de productos agrícolas / resultado por medición a valor razonable (matriz RF-109).

Cómo correrlo:
    python -m pytest "tests/Test_Testing/Test_Modulo6/RF-85/TC-M06-G23/TC-M06-G23.py" -v -s -rs --noconftest --html="tests/Test_Testing/Test_Modulo6/RF-85/TC-M06-G23/reporte-TC-M06-G23.html" --self-contained-html
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

P_PROD, KG, P_ACT = "3500.00", "200", "20000.00"
KG_ACTIVO = "1000"
NETO_PRODUCTO = vn(200, "3500.00")                 # 700.000,0000 - 6 % = 658.000,0000
BRUTO = dec("700000")
VALOR_ACTIVO = vn(1000, P_ACT)                       # 18.800.000,0000


def _calculos_activo(env, ida):
    """Cálculos RF-84 del activo (magnitud 1.000 kg); los del producto agrícola llevan la magnitud cosechada."""
    return [c for c in env.historial(ida)["calculos"] if dec(c["magnitud"]) == dec(KG_ACTIVO)]


def _foto(env, ida):
    h = env.historial(ida)
    ca = _calculos_activo(env, ida)
    return {"mediciones": len(env.mediciones(ida)), "calculos_activo": len(ca),
            "valor": dec(max(ca, key=lambda c: c["id_calculo_valor_razonable"])["valor_neto"]) if ca else None,
            "hechos": sorted(f"{t}/{s}" for t, s in {(l["tipo_hecho"], l["sentido"]) for l in lineas_de(h)})}


def _periodico(env):
    esc = env.escenario_producto("PRODUCCION", P_ACT, P_PROD)
    ida = env.activo_productivo(esc, KG_ACTIVO)
    antes = _foto(env, ida)
    assert antes["valor"] == VALOR_ACTIVO, f"valor del activo antes de la cosecha: {antes}"
    assert env.cosechar(ida, KG).status == 200
    return esc, ida, antes


def test_TC_M06_107_valor_del_producto_periodico_por_rf84(env):
    """Ficha 107: valor_producto = cantidad x precio - costos, calculado por RF-84. Escala: 200 kg a 3.500,00 y costos de M09 del 6 %."""
    env.presupuesto(70)
    esc, ida, antes = _periodico(env)
    filas = env.producto_sql(ida)
    if not filas:
        no_verificable(f"no se reconoció el producto (eventos: {env.tipos_auditoria(ida)}).")
    assert len(filas) == 1, filas
    p = filas[0]
    assert p["tipo"] == "PRODUCTO_PERIODICO", p
    assert dec(p["cantidad_cosechada"]) == dec(KG) and dec(p["precio_mercado_producto"]) == dec(P_PROD), p
    # La columna guarda el costo de venta POR UNIDAD (la tabla exige valor_producto = (precio - costo) x cantidad): 42.000 / 200 kg = 210 por kg.
    assert dec(p["costo_venta_producto"]) * dec(KG) == BRUTO - NETO_PRODUCTO, f"costos de venta esperados {BRUTO - NETO_PRODUCTO} en total (2 % + 3 % + 1 %): {p}"
    assert dec(p["valor_producto"]) == trunc2(NETO_PRODUCTO), f"valor_producto esperado {trunc2(NETO_PRODUCTO)} (RF-84: cantidad x precio - costos): {p}"
    cp = [c for c in env.historial(ida)["calculos"] if (c.get("json_metodo_costo") or {}).get("es_producto")]
    assert cp, "el valor del producto debe quedar calculado con la lógica de RF-84 (cálculo del producto)"
    c = cp[-1]
    assert dec(c["valor_neto"]) == NETO_PRODUCTO, f"cálculo del producto: {c}"
    assert (dec(c["costo_transporte"]), dec(c["costo_comisiones"]), dec(c["costo_impuestos_transaccion"])) == (dec("14000"), dec("21000"), dec("7000")), c
    obs("RF-85 usa las mismas funciones de dominio de RF-84 (costos_venta, valor_neto) con su propio orquestador; el neto coincide con el de RF-84.")


def test_TC_M06_107b_el_activo_no_se_reduce(env):
    """Ficha 107: el valor del activo permanece y valor_reduccion no aplica (RF-85 Restricción 3, CA-3, CA-9, RNF-85-02)."""
    env.presupuesto(70)
    esc, ida, antes = _periodico(env)
    filas = env.producto_sql(ida)
    if not filas:
        no_verificable(f"no se reconoció el producto (eventos: {env.tipos_auditoria(ida)}).")
    p = filas[-1]
    assert not p["valor_reduccion_activo"] or dec(p["valor_reduccion_activo"]) == 0, f"el producto periódico no reduce el activo: {p}"
    despues = _foto(env, ida)
    assert despues["valor"] == VALOR_ACTIVO, f"el valor del activo debe permanecer en {VALOR_ACTIVO}: {antes} -> {despues}"
    assert despues["calculos_activo"] == antes["calculos_activo"] and despues["mediciones"] == antes["mediciones"], (
        f"la cosecha periódica no debe medir ni recalcular el activo: {antes} -> {despues}")
    nuevos = [h for h in despues["hechos"] if h not in antes["hechos"]]
    assert nuevos == ["PRODUCTO_AGRICOLA/UNICO"], f"el único asiento nuevo debe ser el del producto (sin reducción del activo): {antes['hechos']} -> {despues['hechos']}"
    assert dec(env.simulacion(ida).get("calculo")["valor_neto"]) == VALOR_ACTIVO, "consulta directa del activo tras la cosecha"


def test_TC_M06_108_asiento_del_producto_periodico(env):
    """Ficha 108: Débito Inventario de Productos Agrícolas / Crédito a resultado por medición a valor razonable (CA-7), por 658.000,0000."""
    env.presupuesto(70)
    esc, ida, antes = _periodico(env)
    lineas = env.lineas_producto(ida)
    if not lineas:
        no_verificable(f"no hay línea PRODUCTO_AGRICOLA (eventos: {env.tipos_auditoria(ida)}).")
    assert len(lineas) == 1 and lineas[0]["sentido"] == "UNICO", lineas
    ln = lineas[0]
    assert dec(ln["valor"]) == trunc2(NETO_PRODUCTO), ln
    assert ln["estado"] != "PENDIENTE_CUENTA", f"con la matriz completa la línea debe generarse con sus cuentas: {ln}"
    assert ln["cuenta_debito"] and ln["cuenta_credito"] and ln["cuenta_debito"] != ln["cuenta_credito"], ln
    esperado = esc.cuentas.get(("PRODUCTO_AGRICOLA", "UNICO"))
    assert esperado, "la matriz RF-109 del escenario debe tener PRODUCTO_AGRICOLA/UNICO"
    assert (ln["cuenta_debito"], ln["cuenta_credito"]) == esperado, f"las cuentas deben salir de la matriz RF-109 (no fijas en código): {ln}"
    prod = env.producto_sql(ida)
    obs(f"Cuentas aplicadas: débito {ln['cuenta_debito']} (inventario de productos agrícolas, matriz del run) / crédito {ln['cuenta_credito']} "
        f"(cuenta de resultado de la matriz del run); valor {ln['valor']}; id_origen de la línea {ln['id_origen']} (producto {prod[0]['id'] if prod else None}). "
        "CA-7 habla de resultado por medición a valor razonable; RFC-018 de ingreso por producto agrícola: las cuentas las define la matriz de M09, no el código.")
