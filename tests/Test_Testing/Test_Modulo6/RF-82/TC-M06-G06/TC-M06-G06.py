# | Fecha      | Nombre           | Que se hizo                                                              |
# |------------|------------------|--------------------------------------------------------------------------|
# | 2026-11-07 | Daniela Castillo | M06 RF-82: script del grupo TC-M06-G06 (pytest + sandbox, rol Contador) |
# | 2026-11-08 | Daniela Castillo | M06 RF-82: G06 alineado con la ficha (026 donación, 027 estricto, 029 bruto 8000, 030 diferencia 0) |
# | 2026-11-12 | Daniela Castillo | M06 reprueba V2.0 (RF-83 v1.2, RF-84 v1.1, RF-85 v1.2, RF-88 v2.0): el reporte HTML pasa a llamarse reporte-TC-M06-G06-V2.0.html |
# | 2026-11-12 | Daniela Castillo | M06 INC-302: 026 donación espera el hecho RECONOCIMIENTO_DONACION/UNICO con su par de la matriz; 027 retira ese par; 030 anota el hecho observado |
# | 2026-11-12 | Daniela Castillo | M06 reprueba V2.0: 025 muestra las líneas del activo si falla el conteo; 028 y 029 envían referencia_documental (INC-M06-316)
# | 2026-11-13 | Daniela Castillo | M06 RF-82: 024 exige que el Administrador pueda cargar el precio RF-89 (Administrador con todos los permisos en el sistema)
"""
TC-M06-G06 - Integración del reconocimiento con RF-33, RF-89, RF-84, M09 (costos y matriz contable RF-109) y RF-86.
RF-82 (CU01).   Casos: TC-M06-023 a TC-M06-030.

Notas de ejecución:
- 024: el Administrador tiene todos los permisos del sistema (líder y Análisis, 13-nov): carga el precio RF-89 y el caso exige que pueda. Si recibe 403,
  el caso sigue con el Contador para comprobar el resto del flujo y falla al final por el permiso del Administrador.
- 026: para DONACION el crédito debe ser «Ingreso por donación» (RF-82 CA-7 y CA-10), distinto del de nacimiento; si coincide con el
  de nacimiento falla (hallazgo H-01, igual que TC-M06-003 y TC-M06-007).
- 027: la matriz RF-109 de la especie se edita por la API de M09 dentro del run (se retira también la asignación general del hecho,
  que el backend usa como respaldo). La ficha esperaba PENDIENTE_CONFIRMACION, pero RF-86 v2.0 FA-5 y CA-21 mandan: no se crea la
  línea de asiento, el hecho queda PENDIENTE_CUENTA, alerta al Contador, el período no cierra y al completar la matriz se generan las
  líneas. Se prueba lo que dice RF-86 (la ficha difiere: se documenta como diferencia de la ficha).
- 028: sin costos de venta parametrizados RF-82 FA-3 bloquea; RF-84 admite ingreso manual con justificación: se prueban ambos.
- 029: bruto 8000,0000 como dice la ficha (precio por cabeza 8000 con un animal).
- 030: RFC-018. Los valores se obtienen con una especie de costos de venta 0 % y precio por cabeza 500.000 (POBLACIONAL con 19, 17, 18
  y 8 cabezas = 9,5 M, 8,5 M, 9 M y 4 M). Diferencia 0: RF-86 CA-22 prohíbe líneas de valor <= 0, así que no se asienta línea
  (la ficha pedía el hecho con 0,0000; diferencia de la ficha, se documenta).

Cómo correrlo:
    python -m pytest "tests/Test_Testing/Test_Modulo6/RF-82/TC-M06-G06/TC-M06-G06.py" -v -rs --noconftest --html="tests/Test_Testing/Test_Modulo6/RF-82/TC-M06-G06/reporte-TC-M06-G06-V2.0.html" --self-contained-html
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from datetime import timedelta
from m06_lib import *  # noqa: F401,F403,E402

PRECIO = "8000000.00"
NETO = neto_esperado(PRECIO)


@pytest.fixture(scope="module")
def env():
    e = Entorno(("admin", "ingeniero"))
    yield e
    e.cerrar()


@pytest.fixture(scope="module")
def esc(env):
    return env.escenario(categoria="POR_CABEZA", precio=PRECIO)


def test_TC_M06_023_la_propuesta_toma_origen_costo_y_soporte_de_rf33(env, esc):
    env.presupuesto()
    ida = env.activo(esc, origen="compra", costo="2500000.0000", soporte="Factura QA-M06-023")
    p = env.propuesta(ida)             # sin enviar origen, costo ni soporte
    assert p.status == 200, p
    assert str(p.get("origen_financiero")).lower() == "compra", p.data
    assert dec(p.get("costo_adquisicion")) == dec("2500000.0000"), p.data
    assert p.get("soporte_documental") == "Factura QA-M06-023", p.data
    assert p.ms <= 5000, f"RNF-82-01: la propuesta tardó {p.ms:.0f} ms (límite 5000)"


def test_TC_M06_024_recuperacion_tras_bloqueo_por_precio_ausente(env):
    env.presupuesto(40)
    esc = env.escenario(categoria="POR_CABEZA", precio=None)           # especie sin precio
    ida = env.activo(esc, origen="nacimiento", costo=None, soporte=None)
    p = env.propuesta(ida)
    assert p.get("es_confirmable") is False and "RECONOCIMIENTO_BLOQUEADO_SIN_VALOR" in codigos(p), p.data
    assert env.confirmar(ida).status in (400, 409, 422)
    assert not env.historial(ida).get("reconocimientos") and not lineas_de(env.historial(ida))
    # La ficha: el Administrador carga el precio RF-89. Si el RBAC no se lo permite, se documenta y lo carga el Contador.
    cuerpo_precio = {"id_especie": esc.id_especie, "categoria": esc.categoria, "precio_unitario": PRECIO,
                     "fecha_vigencia": str(hoy() - timedelta(days=1)), "fuente": "MERCADO_ACTIVO",
                     "evidencia_documental": "Boletín de precios QA TC-M06", "confirmar_desviacion": True}
    r_adm = env.call("POST", "/finanzas/precios", "admin", json=cuerpo_precio)
    admin_pudo = r_adm.status in (200, 201)
    if admin_pudo:
        esc.precio, esc.id_precio = dec(PRECIO), r_adm.get("id_precio_mercado")
    else:
        obs(f"el Administrador no pudo cargar el precio RF-89 (HTTP {r_adm.status} {r_adm.err}); se sigue el caso con el Contador y se exige al final.")
        env.precio(esc, PRECIO)
    p2 = env.propuesta(ida)
    assert p2.get("es_confirmable") is True and p2.get("indicador_valoracion") == "VALOR_RAZONABLE", p2.data
    assert env.confirmar(ida).status == 201
    assert env.contar("reconocimientos_iniciales", ida, "AND estado = 'CONFIRMADO'") == 1, "debe haber un solo reconocimiento"
    assert admin_pudo, (f"el Administrador tiene todos los permisos (líder y Análisis, 13-nov) y debía poder cargar el precio RF-89 como dice la ficha: "
                        f"HTTP {r_adm.status} {r_adm.err}")


def test_TC_M06_025_repeticiones_secuenciales_no_duplican(env, esc):
    env.presupuesto(40)
    ida = env.activo(esc, origen="compra", costo="2500000.0000", soporte="Factura QA-M06-025")
    valores = {str(env.propuesta(ida).get("valor_inicial")) for _ in range(3)}
    assert len(valores) == 1, f"las repeticiones cambiaron el valor: {valores}"
    assert env.contar("reconocimientos_iniciales", ida) == 0, "consultar la propuesta no debe persistir nada"
    assert env.confirmar(ida).status == 201
    assert env.confirmar(ida).status == 409
    assert env.contar("reconocimientos_iniciales", ida, "AND estado = 'CONFIRMADO'") == 1
    hist = lineas_de(env.historial(ida))
    del_hist = [ln for ln in hist if ln.get("tabla_origen") == "reconocimientos_iniciales"]
    assert len(del_hist) == 1, f"el historial debe mostrar un solo asiento del reconocimiento: {hist}"
    id_origen = int(del_hist[0]["id_origen"])
    ln = del_hist[0]
    assert ln.get("estado") == "REGISTRADA" and not ln.get("es_reverso"), f"el asiento del reconocimiento no quedó REGISTRADO: {ln}"
    assert ln.get("cuenta_debito") and ln.get("cuenta_credito") and ln["cuenta_debito"] != ln["cuenta_credito"], f"cuentas del asiento: {ln}"
    # El SQL del sandbox (/test-control/query) ya lleva identidad de sistema (13-nov): la base debe mostrar la misma línea que el historial.
    cols = "id_linea_asiento_nic41 AS id, id_activo_biologico, tabla_origen, id_origen, estado::text AS estado, es_reverso, valor"
    por_origen = env.sql(f"SELECT {cols} FROM modulo6.lineas_asiento_nic41 WHERE tabla_origen = 'reconocimientos_iniciales' AND id_origen = {id_origen} ORDER BY 1")
    assert len(por_origen) == 1, (f"la base debe tener una sola línea del reconocimiento {id_origen}: devolvió {len(por_origen)} "
                                  f"(el historial de la API muestra 1, línea {ln.get('id_linea_asiento_nic41')})")
    por_activo = env.sql(f"SELECT {cols} FROM modulo6.lineas_asiento_nic41 WHERE id_activo_biologico = {ida} AND tabla_origen = 'reconocimientos_iniciales' ORDER BY 1")
    assert len(por_activo) == 1, f"la base debe tener un solo asiento del reconocimiento para el activo {ida}: {len(por_activo)}"


@pytest.mark.parametrize("origen,costo,soporte,clave", [
    ("compra", "2500000.0000", "Factura", ("RECONOCIMIENTO_DIFERENCIA", "GANANCIA")),
    ("nacimiento", None, None, ("RECONOCIMIENTO_NACIMIENTO", "UNICO")),
    ("donacion", "1200000.0000", "Acta", ("RECONOCIMIENTO_DONACION", "UNICO")),
    ("transferencia_interna", None, None, ("RECONOCIMIENTO_NACIMIENTO", "TRASLADO")),
])
def test_TC_M06_026_cuentas_del_asiento_salen_de_la_matriz(env, esc, origen, costo, soporte, clave):
    env.presupuesto(30)
    if clave not in esc.cuentas:
        bloqueado("la matriz RF-109 no se pudo cargar por la API de M09 para esta especie.")
    ida = env.activo(esc, origen=origen, costo=costo, soporte=soporte)
    r = env.prep(env.confirmar(ida), (201,), f"confirmar {origen}")
    assert r.get("lineas"), f"la confirmación no devolvió líneas de asiento: {r}"
    ln = r.get("lineas")[0]
    assert (ln["tipo_hecho"], ln["sentido"]) == clave, ln
    assert ln["estado"] == "REGISTRADA", ln
    assert (ln["cuenta_debito"], ln["cuenta_credito"]) == esc.cuentas[clave], \
        f"las cuentas debían ser las de la matriz {esc.cuentas[clave]}, no un valor fijo: {ln}"
    if origen == "donacion":
        nac = esc.cuentas[("RECONOCIMIENTO_NACIMIENTO", "UNICO")]
        assert ln["cuenta_credito"] != nac[1], (f"la donación se acredita a {ln['cuenta_credito']}, la misma cuenta del nacimiento "
                                                "(ingreso por transformación biológica); la ficha exige «Ingreso por donación» (H-01)")


def test_TC_M06_027_matriz_sin_cuenta_de_contrapartida(env, esc):
    env.presupuesto(50)
    clave = ("RECONOCIMIENTO_DONACION", "UNICO")      # la donación tiene hecho propio (INC-302): se retira su par de cuentas
    id_asig = esc.asignaciones.get(clave)
    if not id_asig:
        bloqueado("M09 no expuso la asignación de la matriz para retirarla (id_asignacion_cuenta_contable).")
    env.prep(env.call("DELETE", f"/finanzas/configuracion/matriz/{id_asig}", "contador"), (200, 204), "desactivar la asignación")
    # Si existe una asignación general (sin especie) para el mismo hecho, el backend la usa como respaldo y la matriz no queda
    # incompleta: se retira también (dentro del run; el rollback la restaura).
    cfg = env.prep(env.call("GET", "/finanzas/configuracion", "contador"), (200,), "consultar la configuración contable")
    for a in (cfg.get("matriz") or []):
        if a.get("tipo_hecho") == clave[0] and a.get("sentido") == clave[1] and a.get("id_especie") is None:
            env.prep(env.call("DELETE", f"/finanzas/configuracion/matriz/{a['id_asignacion_cuenta_contable']}", "contador"),
                     (200, 204), "desactivar la asignación general del hecho")
    ida = env.activo(esc, origen="donacion", costo="1200000.0000", soporte="Acta QA-M06-027")
    r = env.confirmar(ida)
    assert r.status == 201, f"el reconocimiento debía confirmarse y dejar el hecho pendiente de cuenta (RF-86 FA-5): {r}"
    lineas = lineas_de(env.historial(ida))
    assert not any(l.get("estado") == "REGISTRADA" for l in lineas), f"con la matriz incompleta no debe haber línea registrada: {lineas}"
    assert lineas and all(l.get("estado") == "PENDIENTE_CUENTA" for l in lineas), f"el hecho debía quedar PENDIENTE_CUENTA: {lineas}"
    assert "LINEA_ASIENTO_PENDIENTE_CUENTA" in env.tipos_auditoria(ida), "falta la alerta de línea pendiente de cuenta"
    obs("matriz incompleta: el hecho quedó PENDIENTE_CUENTA con alerta (RF-86 FA-5); el período no podrá cerrarse.")
    # Al completar la matriz, el sistema genera las líneas pendientes.
    deb, cre = esc.cuentas[clave]
    env.prep(env.call("POST", "/finanzas/configuracion/matriz", "contador", json={
        "tipo_hecho": clave[0], "sentido": clave[1], "id_especie": esc.id_especie, "cuenta_debito": deb, "cuenta_credito": cre}),
        (200, 201), "restaurar la matriz")
    assert all(l.get("estado") == "REGISTRADA" for l in lineas_de(env.historial(ida))), "la línea debía resolverse al restaurar la matriz"


def test_TC_M06_028_sin_costos_de_venta_en_m09(env):
    env.presupuesto(50)
    esc = env.escenario(categoria="POR_CABEZA", precio=PRECIO, costos=None)    # sin costos de venta parametrizados
    ida = env.activo(esc, origen="compra", costo="2500000.0000", soporte="Factura QA-M06-028")
    p = env.propuesta(ida)
    assert p.get("es_confirmable") is False and "COSTOS_VENTA_REQUERIDOS" in codigos(p), p.data
    assert p.get("requiere_costos_manuales") is True
    c = env.confirmar(ida)
    assert 400 <= c.status < 500 and c.err == "COSTOS_VENTA_REQUERIDOS", c
    assert not env.historial(ida).get("reconocimientos") and not lineas_de(env.historial(ida))
    # Alternativa de RF-84: ingreso manual de costos con justificación y soporte.
    m = env.confirmar(ida, cuerpo={"costos_manuales": {"transporte": "100000", "comisiones": "50000", "impuestos": "10000"},
                                   "justificacion": "Costos de venta cotizados con el comprador, soporte QA-M06-028."})
    assert m.status == 201, f"con costos manuales y justificación debía confirmarse: {m}"
    assert dec(m.get("valor_inicial")) == q4(PRECIO) - dec("160000"), m


def test_TC_M06_029_consistencia_con_rf84(env):
    env.presupuesto(40)
    NETO = neto_esperado("8000.0000")                                     # ficha: precio bruto 8000,0000
    esc = env.escenario(categoria="POR_CABEZA", precio="8000.0000")
    ida = env.activo(esc, origen="nacimiento", costo=None, soporte=None)
    sim = env.simulacion(ida)                                             # solicitud directa de RF-84
    assert sim.status == 200 and sim.get("es_valido") is True, sim
    calculo = sim.get("calculo") or {}
    assert dec(calculo.get("valor_neto")) == NETO, f"RF-84 directo: {calculo}"
    assert dec(env.propuesta(ida).get("valor_inicial")) == dec(calculo.get("valor_neto")), "el reconocimiento no coincide con RF-84"
    bruto = dec(calculo.get("valor_razonable_bruto"))
    total = sum(dec(calculo.get(k) or 0) for k in ("costo_transporte", "costo_comisiones", "costo_impuestos_transaccion", "otros_costos_disposicion"))
    assert bruto - total == dec(calculo.get("valor_neto")), "neto != bruto - costos (4 decimales)"
    # Con un componente manual «otros»: valor = bruto - (parametrizados + otros).
    ida2 = env.activo(esc, origen="nacimiento", costo=None, soporte=None)
    c = env.confirmar(ida2, cuerpo={"costos_manuales": {"otros": "50"}, "justificacion": "Otros costos de disposición con soporte QA-M06-029."})
    assert c.status == 201, c
    assert dec(c.get("valor_inicial")) == NETO - dec("50"), c


def test_TC_M06_030_hechos_enviados_a_rf86(env):
    env.nuevo_run()                    # run propio: este caso necesita más de 80 s y los anteriores ya gastaron el presupuesto
    env.presupuesto(80)
    esc = env.escenario(categoria="POR_CABEZA", precio="500000.00", costos=("0", "0", "0"))
    compras = [(19, "GANANCIA", "500000"), (17, "PERDIDA", "500000"), (18, None, None)]
    for cabezas, sentido, valor in compras:
        ida = env.activo(esc, tipo="POBLACIONAL", cantidad=cabezas, origen="compra", costo="9000000.0000", soporte="Factura QA-M06-030")
        hechos_pre = hechos(env.propuesta(ida))                       # hechos que se enviarán a RF-86
        r = env.prep(env.confirmar(ida), (201,), f"confirmar compra de {cabezas} cabezas")
        lineas = r.get("lineas") or []
        if sentido is None:
            # RF-86 CA-22: ninguna línea de asiento puede tener valor <= 0; con diferencia 0 no se asienta línea.
            assert not lineas, f"diferencia 0: no debe asentarse línea de valor 0 (RF-86 CA-22): {lineas}"
            obs(f"diferencia 0,0000: sin línea de asiento (RF-86 CA-22). Hechos enviados: {hechos_pre}")
        else:
            assert len(lineas) == 1 and (lineas[0]["tipo_hecho"], lineas[0]["sentido"]) == ("RECONOCIMIENTO_DIFERENCIA", sentido), lineas
            assert dec(lineas[0]["valor"]) == dec(valor), lineas
    ida = env.activo(esc, tipo="POBLACIONAL", cantidad=8, origen="nacimiento", costo=None, soporte=None)
    r = env.prep(env.confirmar(ida), (201,), "confirmar nacimiento de 8 cabezas")
    ln = (r.get("lineas") or [{}])[0]
    assert (ln.get("tipo_hecho"), ln.get("sentido")) == ("RECONOCIMIENTO_NACIMIENTO", "UNICO"), ln
    assert dec(ln.get("valor")) == dec("4000000"), "RECONOCIMIENTO_NACIMIENTO debe ir por el valor razonable completo"
    for origen, costo, soporte in (("donacion", "1200000.0000", "Acta"), ("transferencia_interna", None, None)):
        ida = env.activo(esc, tipo="POBLACIONAL", cantidad=8, origen=origen, costo=costo, soporte=soporte)
        ln = (env.prep(env.confirmar(ida), (201,), f"confirmar {origen}").get("lineas") or [{}])[0]
        obs(f"{origen}: hecho observado {ln.get('tipo_hecho')}/{ln.get('sentido')} por {ln.get('valor')} (RFC-018 no lo define; la donación usa RECONOCIMIENTO_DONACION desde INC-302).")
