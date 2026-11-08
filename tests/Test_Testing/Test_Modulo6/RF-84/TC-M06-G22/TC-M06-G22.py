# | Fecha      | Nombre           | Que se hizo                                                                                           |
# |------------|------------------|-------------------------------------------------------------------------------------------------------|
# | 2026-11-07 | Daniela Castillo | M06 RF-84: script del grupo TC-M06-G22 (pytest + sandbox, rol Contador)                               |
# | 2026-11-08 | Daniela Castillo | G22 revisado contra ficha y RF/CU: 101b (registro de los intentos), 102 con valores exactos, 103 en     |
# |            |                  | lotes de varios runs (20 cálculos), 104 con más escenarios, 105 completo con RF-85; 106 pasa a Newman |
"""
TC-M06-G22 - Autorización, auditoría, exactitud, consistencia entre módulos y tiempo de respuesta del cálculo.   RF-84.   Casos: TC-M06-101 a TC-M06-106.

- Herramientas: 101 a 105 con pytest (este archivo); 106 (tiempo, responseTime) con Newman: TC-M06-G22.json
  (correr_newman.ps1 -Caso G22 -Modulo 6 -Rf RF-84). En pytest queda omitido con esa indicación.
- Necesita las contraseñas de los cuatro roles (QA_CONTRASENA_ADMIN, _INGENIERO, _PRODUCTOR, _VETERINARIO).
- 101: confirmar el reconocimiento (única operación que valida/sobrescribe costos) con Productor, Veterinario, Ingeniero de campo (rol 4
  temporal), Administrador y sin token (401); el Contador sí puede y el Administrador configura los costos de venta. 101b: «cada intento
  rechazado queda registrado» (RNF-82-05; ya reportado como H-07 en G07 y G08).
- 102: el cálculo del caso base conserva bruto, los cuatro costos, método por componente, neto, usuario y fecha-hora, y es consultable.
- 103: 20 cálculos aleatorios (semilla fija, 4 decimales) repartidos en varios runs (cada run tiene 170 s): neto = bruto - suma de costos,
  bruto = magnitud x precio y cada costo parametrizado = bruto x porcentaje de M09, todo por SELECT.
- 104: invariante neto = bruto - suma de costos aplicados sobre TODOS los cálculos del run, tras escenarios M09, mixtos, manuales y en cero.
- 105: mismo valor neto en la consulta directa de RF-84 (simulación), RF-82 (propuesta y reconocimiento), RF-83 (medición) y RF-85 (producto
  agrícola con la misma cantidad y el mismo precio).

Cómo correrlo:
    python -m pytest "tests/Test_Testing/Test_Modulo6/RF-84/TC-M06-G22/TC-M06-G22.py" -v -s -rs --noconftest --html="tests/Test_Testing/Test_Modulo6/RF-84/TC-M06-G22/reporte-TC-M06-G22.html" --self-contained-html
    (repetición de 102 tras corregir el script: agregar  -k 102  y  reporte-TC-M06-G22-102.html)
"""
from __future__ import annotations

import pathlib
import random
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from m06_lib import *  # noqa: F401,F403,E402

JUSTIF = "Ajuste manual QA TC-M06 con soporte documental: cotización No. 987 del proveedor."
PCT = ("0.02", "0.03", "0.01")
CONSULTA_CALCULOS = (
    "SELECT id_activo_biologico, valor_razonable_bruto::text AS bruto, valor_neto::text AS neto FROM modulo6.calculos_valor_razonable "
    "WHERE {filtro} ("
    "(valor_razonable_bruto - (costo_transporte + costo_comisiones + costo_impuestos_transaccion + otros_costos_disposicion)) <> valor_neto) LIMIT 20")
CONSULTA_LOTE = (
    "SELECT id_activo_biologico, valor_razonable_bruto::text AS bruto, valor_neto::text AS neto FROM modulo6.calculos_valor_razonable "
    "WHERE id_activo_biologico IN ({ids}) AND ("
    "(valor_razonable_bruto - (costo_transporte + costo_comisiones + costo_impuestos_transaccion + otros_costos_disposicion)) <> valor_neto "
    "OR abs(valor_razonable_bruto - magnitud * precio_unitario) > 0.0001 "
    "OR abs(costo_transporte - valor_razonable_bruto * 0.02) > 0.0001 "
    "OR abs(costo_comisiones - valor_razonable_bruto * 0.03) > 0.0001 "
    "OR abs(costo_impuestos_transaccion - valor_razonable_bruto * 0.01) > 0.0001) LIMIT 20")


@pytest.fixture(scope="module")
def env():
    e = Entorno(("admin", "ingeniero", "productor", "veterinario"))
    yield e
    e.cerrar()


def _contar_auditoria(env) -> int:
    return int(uno(env.sql("SELECT count(*) AS n FROM modulo6.auditorias_financieras")) or 0)


def test_TC_M06_101_solo_el_contador_valida_y_sobrescribe(env):
    env.nuevo_run()
    env.presupuesto(80)
    esc = env.escenario(categoria="POR_CABEZA", precio="10000000.00")
    ida = env.activo(esc, origen="nacimiento", costo=None, soporte=None)
    cuerpo = {"costos_manuales": {"comisiones": "250000"}, "justificacion": JUSTIF}
    ruta = f"/finanzas/reconocimientos/{ida}"
    sin = env.call("POST", ruta, None, json=cuerpo)
    assert sin.status == 401, f"sin token debía responder 401: {sin}"
    for rol in ("productor", "veterinario", "admin"):
        r = env.call("POST", ruta, rol, json=cuerpo)
        assert r.status == 403, f"{rol} no debe validar ni sobrescribir (403) y respondió {r}"
    env.set_rol(ROL_INGENIERO)
    try:
        r = env.call("POST", ruta, "ingeniero", json=cuerpo)
        assert r.status == 403, f"Ingeniero de campo no debe validar ni sobrescribir (403) y respondió {r}"
    finally:
        env.contador()
    assert env.calculo(ida) is None, "ningún intento rechazado debe haber creado un cálculo"
    ok = env.confirmar(ida, "contador", cuerpo)
    assert ok.status in (200, 201), f"el Contador sí debe poder validar y sobrescribir: {ok}"
    cfg = env.call("PUT", f"/finanzas/configuracion/costos-venta/{esc.id_especie}", "admin",
                   json={"pct_transporte": "0.02", "pct_comisiones": "0.03", "pct_impuestos": "0.01"})
    assert cfg.status in (200, 201), f"el Administrador debe poder configurar los costos de venta (M09) y respondió {cfg}"


def test_TC_M06_101b_cada_intento_rechazado_queda_registrado(env):
    env.nuevo_run()
    env.presupuesto(60)
    esc = env.escenario(categoria="POR_CABEZA", precio="10000000.00")
    ida = env.activo(esc, origen="nacimiento", costo=None, soporte=None)
    cuerpo = {"costos_manuales": {"comisiones": "250000"}, "justificacion": JUSTIF}
    ruta = f"/finanzas/reconocimientos/{ida}"
    sin_registro = []
    for rol in ("productor", "veterinario", "admin"):
        antes = _contar_auditoria(env)
        r = env.call("POST", ruta, rol, json=cuerpo)
        assert r.status == 403, f"{rol}: {r}"
        despues = _contar_auditoria(env)
        if despues <= antes:
            sin_registro.append(f"{rol} ({antes}->{despues})")
    env.set_rol(ROL_INGENIERO)
    try:
        antes = _contar_auditoria(env)
        r = env.call("POST", ruta, "ingeniero", json=cuerpo)
        assert r.status == 403, f"ingeniero: {r}"
        despues = _contar_auditoria(env)
        if despues <= antes:
            sin_registro.append(f"ingeniero de campo ({antes}->{despues})")
    finally:
        env.contador()
    assert not sin_registro, ("el intento rechazado debe quedar registrado en el log de auditoría (RNF-82-05, ficha 101) y no cambió el "
                              f"conteo de auditorias_financieras con: {', '.join(sin_registro)}")


def test_TC_M06_102_el_calculo_persiste_componentes_metodo_usuario_y_fecha(env):
    env.nuevo_run()
    env.presupuesto(40)
    esc = env.escenario(categoria="POR_CABEZA", precio="10000000.00", costos=("0.015", "0.02", "0.005"))
    ida, r = env.confirmar_manual(esc, {"otros": "100000"}, JUSTIF)
    assert r.status in (200, 201), r
    c = env.calculo(ida)
    for campo in ("valor_razonable_bruto", "costo_transporte", "costo_comisiones", "costo_impuestos_transaccion", "otros_costos_disposicion",
                  "valor_neto", "metodo_costo", "json_metodo_costo", "id_usuario", "fecha_calculo"):
        assert c.get(campo) is not None, f"el cálculo no conserva «{campo}»: {c}"
    assert dec(c["valor_razonable_bruto"]) == dec("10000000"), c
    assert (dec(c["costo_transporte"]), dec(c["costo_comisiones"]), dec(c["costo_impuestos_transaccion"]), dec(c["otros_costos_disposicion"])) == (
        dec("150000"), dec("200000"), dec("50000"), dec("100000")), c
    assert dec(c["valor_neto"]) == dec("9500000"), c
    metodos = c["json_metodo_costo"]
    assert (metodos.get("transporte"), metodos.get("comisiones"), metodos.get("impuestos"), metodos.get("otros")) == (
        "PARAMETRIZADO", "PARAMETRIZADO", "PARAMETRIZADO", "MANUAL"), f"método por componente: {c}"
    assert c["metodo_costo"] == "MIXTO", c
    eventos = [e for e in env.auditoria(ida) if e.get("tipo_evento") == "RECONOCIMIENTO_INICIAL"]
    assert eventos and (eventos[-1].get("actor") or eventos[-1].get("id_usuario")), f"el evento de auditoría debe identificar al usuario: {env.auditoria(ida)}"
    assert any("fecha" in k for k in eventos[-1]), f"el evento de auditoría no trae fecha-hora: {eventos[-1]}"
    obs("El cálculo guarda usuario (id_usuario) y fecha (fecha_calculo); el evento RECONOCIMIENTO_INICIAL de RF-94 guarda usuario y fecha-hora, "
        "pero no los componentes del cálculo (estos viven en el registro del cálculo). El evento identifica al usuario en el campo «actor».")


def _lote(env, azar, objetivo: int) -> int:
    """Un run: escenario con precio aleatorio y hasta `objetivo` activos con peso aleatorio; verifica por SELECT dentro del mismo run."""
    env.nuevo_run()
    env.presupuesto(60)
    precio = f"{azar.randint(5000, 20000)}.{azar.randint(1, 99):02d}"
    esc = env.escenario(categoria="PESO_KG", precio=precio, costos=PCT)
    ids = []
    while len(ids) < objetivo and env.restante() > 25:
        kg = f"{azar.randint(100, 900)}.{azar.randint(0, 99):02d}"
        ida, _r = env.reconocer(esc, origen="nacimiento", costo=None, soporte=None, peso_kg=kg)
        ids.append(ida)
    if not ids:
        return 0
    lista = ",".join(str(i) for i in ids)
    n = int(uno(env.sql(f"SELECT count(*) AS n FROM modulo6.calculos_valor_razonable WHERE id_activo_biologico IN ({lista})")) or 0)
    assert n == len(ids), f"cada activo debe tener su cálculo: {len(ids)} activos y {n} cálculos (precio {precio})"
    filas = env.sql(CONSULTA_LOTE.format(ids=lista))
    assert not filas, f"cálculos cuyo neto, bruto o costos difieren de la recomputación (precio {precio}): {filas}"
    return len(ids)


def test_TC_M06_103_neto_persistido_igual_a_la_recomputacion_de_20_calculos(env):
    azar = random.Random(20261107)
    total, corridas = 0, 0
    while total < 20 and corridas < 4:
        total += _lote(env, azar, 20 - total)
        corridas += 1
    if total < 20:
        no_concluyente(f"solo se verificaron {total} cálculos en {corridas} runs.")
    obs(f"{total} cálculos verificados en {corridas} runs (neto = bruto - costos, bruto = magnitud x precio, costos = bruto x porcentaje).")


def test_TC_M06_104_invariante_neto_igual_bruto_menos_costos_en_todos_los_calculos(env):
    env.nuevo_run()
    env.presupuesto(100)
    esc = env.escenario(categoria="POR_CABEZA", precio="10000000.00", costos=("0.015", "0.02", "0.005"))
    env.reconocer(esc, origen="nacimiento", costo=None, soporte=None)                                         # solo M09
    env.confirmar_manual(esc, {"otros": "100000"}, JUSTIF)                                                    # mixto
    env.confirmar_manual(esc, {"comisiones": "250000", "otros": "60000"}, JUSTIF)                             # mixto
    env.confirmar_manual(esc, {"transporte": "1", "comisiones": "2", "impuestos": "3", "otros": "4"}, JUSTIF)    # todo manual
    env.confirmar_manual(esc, {"transporte": "0", "comisiones": "0", "impuestos": "0", "otros": "0"}, JUSTIF)    # costos en cero
    total = int(uno(env.sql("SELECT count(*) AS n FROM modulo6.calculos_valor_razonable")) or 0)
    filas = env.sql(CONSULTA_CALCULOS.format(filtro=""))
    assert not filas, f"cálculos con neto distinto de bruto - suma de costos aplicados: {filas}"
    obs(f"{total} cálculos revisados en el run (incluye los 5 del caso y los que ya existían en TEST).")


def test_TC_M06_105_mismo_valor_en_rf82_rf83_rf85_y_la_consulta_directa(env):
    env.nuevo_run()
    env.presupuesto(100)
    esc = env.escenario_producto(clasificacion="PRODUCCION", precio_activo="20000.00", precio_producto="20000.00")
    ida = env.activo(esc, origen="nacimiento", costo=None, soporte=None, peso_kg="400")
    esperado = vn(400, "20000.00")
    s = env.simulacion(ida)
    assert dec(s.get("calculo")["valor_neto"]) == esperado, f"consulta directa de RF-84: {s}"
    p = env.propuesta(ida)
    assert dec(p.get("valor_inicial")) == esperado, f"la propuesta (RF-82) debe usar el mismo cálculo: {p}"
    c = env.confirmar(ida)
    assert c.status in (200, 201) and dec(c.get("valor_inicial")) == esperado, f"reconocimiento (RF-82): {c}"
    assert dec(env.calculo(ida)["valor_neto"]) == esperado, "el cálculo persistido debe ser el mismo"
    env.procesar_eventos()
    assert env.medir(esc, ida, None, "450").status == 200
    ms = env.mediciones(ida)
    if not ms:
        no_verificable("no se generó la medición de RF-83.")
    s2 = env.simulacion(ida)
    esperado2 = vn(450, "20000.00")
    assert dec(s2.get("calculo")["valor_neto"]) == esperado2, f"consulta directa tras la medición: {s2}"
    assert dec(ms[-1]["valor_razonable_actual"]) == esperado2, f"medición (RF-83): {ms[-1]}"
    env.cosechar(ida, "450", "kg")
    productos = env.productos(ida)
    if not productos:
        no_verificable("no se generó el reconocimiento del producto agrícola (RF-85).")
    calc_producto = [k for k in (env.historial(ida).get("calculos") or []) if (k.get("json_metodo_costo") or {}).get("es_producto")]
    assert calc_producto, "RF-85 debe dejar el cálculo del producto"
    assert dec(calc_producto[-1]["valor_neto"]) == esperado2, f"cálculo del producto (RF-85): {calc_producto[-1]}"
    assert dec(productos[-1]["valor_producto"]) == trunc2(esperado2), f"valor del producto (RF-85): {productos[-1]}"
    obs("RF-85 obtiene el neto con las mismas funciones de dominio (costos_venta y valor_neto) que RF-84, pero con su propio orquestador (no pasa por el "
        "servicio Valorador de RF-84); RF-82 y RF-83 sí lo usan. Con la misma cantidad y el mismo precio los cuatro netos coinciden.")


def test_TC_M06_106_tiempo_de_calculo_30_invocaciones(env):
    pytest.skip("TC-M06-106 (tiempo de cálculo, responseTime) se ejecuta con Newman: "
                "correr_newman.ps1 -Caso G22 -Modulo 6 -Rf RF-84 (TC-M06-G22.json).")
