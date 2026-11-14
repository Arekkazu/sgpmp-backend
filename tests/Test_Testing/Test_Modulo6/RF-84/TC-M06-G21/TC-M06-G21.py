# | Fecha      | Nombre           | Que se hizo                                                                                          |
# |------------|------------------|------------------------------------------------------------------------------------------------------|
# | 2026-11-07 | Daniela Castillo | M06 RF-84: script del grupo TC-M06-G21 (pytest + sandbox, rol Contador)                              |
# | 2026-11-08 | Daniela Castillo | G21 revisado contra ficha y RF/CU: rechazos por su motivo, método MANUAL por componente, 099b con      |
# | 2026-11-12 | Daniela Castillo | M06 reprueba V2.0 (RF-83 v1.2, RF-84 v1.1, RF-85 v1.2, RF-88 v2.0): el reporte HTML pasa a llamarse reporte-TC-M06-G21-V2.0.html |
# |            |                  | costos manuales, versión de parámetros comprobada en BD y 100b (el Administrador cambia la comisión)  |
# | 2026-11-13 | Daniela Castillo | M06 V2.0 (2.ª pasada): la base de datos pasa a ser la fuente de verdad (SQL ya funciona), expectativas alineadas con las correcciones de Desarrollo (notas de la versión 1.4.0) y las precondiciones que fallan ya no se omiten: quedan en rojo con diagnóstico |
"""
TC-M06-G21 - Parámetros de M09 y precio de mercado: ingreso manual, bloqueo sin precio y vigencia sin afectar el histórico.
RF-84 (FA-1, FA-4).   Casos: TC-M06-098 a TC-M06-100.

- 098: especie sin costos de venta en M09 -> la propuesta queda bloqueada con COSTOS_VENTA_REQUERIDOS y la confirmación sin costos se rechaza POR ESO
  (sin cálculo con ceros implícitos); con costos manuales y justificación se calcula con método MANUAL en todos los componentes.
- 099: especie sin precio RF-89 (y sin costo) -> la simulación devuelve SIN_PRECIO y la confirmación se rechaza con un mensaje que habla de la falta
  de precio/mercado; 099b: con costos manuales y justificación también se bloquea (RF-84 FA-4 no depende de los costos).
- 100: cambio de comisión 2 % -> 3 % (el RF/ficha lo hacen en M09; aquí el parámetro vive en modulo6.parametros_costos_venta): el cálculo previo no
  cambia, el nuevo usa el 3 % y cada cálculo conserva su versión de parámetros (id_parametro_costo_venta -> fila con su porcentaje; la anterior
  queda inactiva). 100b: la ficha dice que el Administrador cambia la comisión: se prueba que puede hacerlo.
- «Región»: la API solo maneja una región general (no hay entrada de región): se documenta.

Cómo correrlo:
    python -m pytest "tests/Test_Testing/Test_Modulo6/RF-84/TC-M06-G21/TC-M06-G21.py" -v -s -rs --noconftest --html="tests/Test_Testing/Test_Modulo6/RF-84/TC-M06-G21/reporte-TC-M06-G21-V2.0.html" --self-contained-html
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from m06_lib import *  # noqa: F401,F403,E402

JUSTIF = "Costos manuales QA TC-M06 con soporte documental: cotización No. 654 del proveedor."
MANUALES = {"transporte": "100000", "comisiones": "150000", "impuestos": "50000", "otros": "0"}


@pytest.fixture(scope="module")
def env():
    e = Entorno(("admin", "ingeniero"))
    yield e
    e.cerrar()


def _parametros(env, id_especie):
    return env.sql("SELECT id_parametro_costo_venta, pct_comisiones::text AS pct_comisiones, es_activo "
                   f"FROM modulo6.parametros_costos_venta WHERE id_especie = {int(id_especie)} ORDER BY id_parametro_costo_venta")


def test_TC_M06_098_sin_parametros_de_m09_se_exige_ingreso_manual(env):
    env.nuevo_run()
    env.presupuesto(40)
    esc = env.escenario(categoria="POR_CABEZA", precio="10000000.00", costos=None)
    ida = env.activo(esc, origen="nacimiento", costo=None, soporte=None)
    p = env.propuesta(ida)
    assert p.status == 200 and "COSTOS_VENTA_REQUERIDOS" in codigos(p) and p.get("requiere_costos_manuales") is True, p
    sin = env.confirmar(ida)
    assert 400 <= sin.status < 500 and "COSTOS_VENTA_REQUERIDOS" in (sin.text or ""), \
        f"sin costos debía rechazarse pidiendo el ingreso manual (COSTOS_VENTA_REQUERIDOS): {sin}"
    assert env.calculo(ida) is None and env.contar("calculos_valor_razonable", ida) == 0, "sin costos no debe haber cálculo con ceros implícitos (API ni base)"
    con = env.confirmar(ida, cuerpo={"costos_manuales": MANUALES, "justificacion": JUSTIF})
    assert con.status in (200, 201), con
    c = env.calculo(ida)
    assert c["metodo_costo"] == "MANUAL" and dec(c["valor_neto"]) == dec("9700000.0000"), c
    metodos = c.get("json_metodo_costo") or {}
    assert all(metodos.get(k) == "MANUAL" for k in ("transporte", "comisiones", "impuestos", "otros")), f"cada componente debe quedar MANUAL: {c}"
    assert c.get("id_parametro_costo_venta") is None, f"sin parámetros de M09 no debe referenciarse ninguno: {c}"
    bd = env.comparar_calculo_bd(ida, c)
    assert bd.get("id_parametro_costo_venta") is None and dec(bd["valor_neto"]) == dec("9700000.0000"), f"base de datos: {bd}"
    obs("El aviso al Contador (RF-84 FA-1) no es verificable en el sandbox (se emite tras el commit); lo observable es la propuesta bloqueada. "
        "La API solo maneja una región general (no hay entrada de región).")


def test_TC_M06_099_sin_precio_el_calculo_se_bloquea(env):
    env.nuevo_run()
    env.presupuesto(30)
    esc = env.escenario(categoria="POR_CABEZA", precio=None)
    ida = env.activo(esc, origen="nacimiento", costo=None, soporte=None)
    s = env.simulacion(ida)
    assert s.status == 200 and s.get("es_valido") is False and s.get("motivo") == "SIN_PRECIO" and s.get("calculo") is None, s
    assert "precio" in (s.get("mensaje") or "").lower(), s
    c = env.confirmar(ida)
    assert 400 <= c.status < 500 and any(p in (c.text or "").lower() for p in ("precio", "mercado")), \
        f"la confirmación debía bloquearse con un mensaje que indique la falta de precio/mercado: {c}"
    assert env.calculo(ida) is None and env.contar("calculos_valor_razonable", ida) == 0, "no debe generarse valor neto (API ni base)"


def test_TC_M06_099b_sin_precio_tampoco_se_calcula_con_costos_manuales(env):
    env.nuevo_run()
    env.presupuesto(30)
    esc = env.escenario(categoria="POR_CABEZA", precio=None, costos=None)
    ida = env.activo(esc, origen="nacimiento", costo=None, soporte=None)
    c = env.confirmar(ida, cuerpo={"costos_manuales": MANUALES, "justificacion": JUSTIF})
    assert 400 <= c.status < 500 and any(p in (c.text or "").lower() for p in ("precio", "mercado", "valor")), \
        f"sin precio de mercado el cálculo debía bloquearse aunque haya costos manuales: {c}"
    assert env.calculo(ida) is None and env.contar("calculos_valor_razonable", ida) == 0, "no debe generarse valor neto sin precio (API ni base)"


def test_TC_M06_100_actualizar_parametros_no_altera_el_historico(env):
    env.nuevo_run()
    env.presupuesto(60)
    esc = env.escenario(categoria="POR_CABEZA", precio="10000000.00", costos=("0.02", "0.02", "0.01"))
    a, r = env.reconocer(esc, origen="nacimiento", costo=None, soporte=None)
    previo = env.calculo(a)
    assert dec(previo["valor_neto"]) == dec("9500000.0000"), previo
    env.prep(env.call("PUT", f"/finanzas/configuracion/costos-venta/{esc.id_especie}", "contador",
                      json={"pct_transporte": "0.02", "pct_comisiones": "0.03", "pct_impuestos": "0.01"}), (200, 201), "comisión 3 %")
    b, rb = env.reconocer(esc, origen="nacimiento", costo=None, soporte=None)
    nuevo = env.calculo(b)
    assert dec(nuevo["costo_comisiones"]) == dec("300000.0000") and dec(nuevo["valor_neto"]) == dec("9400000.0000"), nuevo
    despues = env.calculo(a)
    assert despues == previo, "el cálculo previo debe conservar su valor exacto"
    bd_prev, bd_nuevo = env.comparar_calculo_bd(a, previo), env.comparar_calculo_bd(b, nuevo)
    assert dec(bd_prev["valor_neto"]) == dec("9500000.0000") and dec(bd_nuevo["valor_neto"]) == dec("9400000.0000"), (
        f"base de datos: el previo debe conservar 9.500.000 y el nuevo 9.400.000: {bd_prev.get('valor_neto')} / {bd_nuevo.get('valor_neto')}")
    assert previo["id_parametro_costo_venta"] != nuevo["id_parametro_costo_venta"], "cada cálculo debe conservar la versión de parámetros aplicada"
    filas = {f["id_parametro_costo_venta"]: f for f in _parametros(env, esc.id_especie)}
    vieja, nueva = filas.get(previo["id_parametro_costo_venta"]), filas.get(nuevo["id_parametro_costo_venta"])
    assert vieja and nueva, f"las dos versiones de parámetros deben seguir en BD: {filas}"
    assert dec(vieja["pct_comisiones"]) == dec("0.02") and vieja["es_activo"] is False, f"la versión del cálculo previo debe conservar 2 % e inactiva: {vieja}"
    assert dec(nueva["pct_comisiones"]) == dec("0.03") and nueva["es_activo"] is True, f"la versión nueva debe tener 3 % y estar activa: {nueva}"


def test_TC_M06_100b_el_administrador_puede_cambiar_la_comision(env):
    env.nuevo_run()
    env.presupuesto(30)
    esc = env.escenario(categoria="POR_CABEZA", precio="10000000.00", costos=("0.02", "0.02", "0.01"))
    r = env.call("PUT", f"/finanzas/configuracion/costos-venta/{esc.id_especie}", "admin",
                 json={"pct_transporte": "0.02", "pct_comisiones": "0.03", "pct_impuestos": "0.01"})
    assert r.status in (200, 201), (
        "la ficha 100 y el RF-84 (Actores y Precondición 3) hacen que el Administrador configure los costos de venta y respondió "
        f"{r}. Desde el 13-nov el Administrador tiene todos los permisos de M06 (INC-M06-328 corregido por Desarrollo).")
