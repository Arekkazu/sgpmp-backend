# | Fecha      | Nombre           | Que se hizo                                                              |
# |------------|------------------|--------------------------------------------------------------------------|
# | 2026-11-07 | Daniela Castillo | M06 RF-82: script del grupo TC-M06-G08 (pytest + sandbox, rol Contador) |
# | 2026-11-08 | Daniela Castillo | M06 RF-82: G08 alineado con la ficha (041 completo, 043 a/b, 044 sin 409 exacto; 045 pasa a Newman) |
# | 2026-11-12 | Daniela Castillo | M06 reprueba V2.0 (RF-83 v1.2, RF-84 v1.1, RF-85 v1.2, RF-88 v2.0): el reporte HTML pasa a llamarse reporte-TC-M06-G08-V2.0.html |
# | 2026-11-13 | Daniela Castillo | M06 RF-82: 041c con Administrador con todos los permisos (líder y Análisis, 13-nov) y rol Auditor nuevo: se retira el Administrador, se agrega el Auditor y 041d administrador confirma
"""
TC-M06-G08 - Auditoría, inmutabilidad, integridad contable y rendimiento del reconocimiento inicial.   RF-82 (CU01).
Casos: TC-M06-039 a TC-M06-045.

- Herramientas: 039 a 044 con pytest (este archivo); 045 (tiempo de respuesta, responseTime) con Newman: TC-M06-G08.json
  (correr_newman.ps1 -Caso G08 -Modulo 6 -Rf RF-82). En pytest el 045 queda omitido con esa indicación.
- Auditoría (RF-94): GET /finanzas/auditoria?id_activo_biologico=... ; tipos reales: RECONOCIMIENTO_INICIAL, RECONOCIMIENTO_REVERTIDO,
  RECONOCIMIENTO_BLOQUEADO_SIN_VALOR, REVERSION_BLOQUEADA. El RF-82 no nombra el tipo del reconocimiento confirmado: se registra el observado.
- 041: propuesta, confirmación, bloqueo sin valor y reversión se verifican en RF-94; el rechazo (FA-4) no existe como operación (H-05:
  BLOQUEADO, funcionalidad no implementada); el intento de confirmar con otro rol (Productor, Veterinario, Auditor; el Administrador ya tiene todos los permisos, 13-nov) debe quedar
  registrado (RNF-82-05, H-07). Sin token no aplica a M06 (lo rechaza la autenticación de M01).
- 042: no existen rutas PUT/PATCH/DELETE sobre el reconocimiento (405/404) y el SELECT no cambia. No se hace UPDATE/DELETE directo en BD.
- 043: se verifica por separado (a) asiento cuadrado, espejo exacto y neto cero, y (b) lo que pide la ficha: el valor de la línea es el valor
  reconocido con 4 decimales exactos (1.234.444,4332). Corrida del 8-nov: ambos cumplen (la línea conserva los 4 decimales).
- Cada run del sandbox dura 170 s como máximo: los casos abren un run nuevo cuando ya no alcanza el tiempo.

Cómo correrlo (necesita también QA_CONTRASENA_PRODUCTOR, QA_CONTRASENA_VETERINARIO y QA_CONTRASENA_AUDITOR):
    python -m pytest "tests/Test_Testing/Test_Modulo6/RF-82/TC-M06-G08/TC-M06-G08.py" -v -s -rs --noconftest --html="tests/Test_Testing/Test_Modulo6/RF-82/TC-M06-G08/reporte-TC-M06-G08-V2.0.html" --self-contained-html
"""
from __future__ import annotations

import pathlib
import sys
from collections import defaultdict
from decimal import ROUND_DOWN

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from m06_lib import *  # noqa: F401,F403,E402

MOTIVO = "Reversión de prueba QA TC-M06-G08, valor mal capturado"


@pytest.fixture(scope="module")
def env():
    e = Entorno(("admin", "ingeniero", "productor", "veterinario", "auditor"))
    yield e
    e.cerrar()


def _asegurar(env, segundos):
    """Cada run del sandbox dura 170 s como máximo: si ya no alcanza para el caso, se cierra y se abre uno nuevo."""
    if env.inicio is not None and env.restante() < segundos:
        env.nuevo_run()


_ESC = {}


@pytest.fixture
def esc(env):
    _asegurar(env, 75)
    if env.run_id not in _ESC:
        _ESC[env.run_id] = env.escenario(categoria="POR_CABEZA", precio="8000000.00")
    return _ESC[env.run_id]


def test_TC_M06_039_auditoria_del_reconocimiento(env, esc):
    env.presupuesto()
    ida, conf = env.reconocer(esc, origen="compra", costo="2500000.0000", soporte="Factura QA-M06-039")
    ev = env.auditoria(ida, "RECONOCIMIENTO_INICIAL")
    assert len(ev) == 1, f"debe haber un evento por la confirmación: {ev}"
    e = ev[0]
    assert e.get("fecha_hora") and e.get("actor") and e.get("actor") != "Sistema automático", f"falta fecha-hora o usuario: {e}"
    assert e.get("activo"), e
    payload = e.get("resumen_payload") or {}
    for campo in ("origen_financiero", "indicador_valoracion", "valor_inicial", "lineas"):
        assert campo in payload, f"el payload no trae {campo}: {payload}"
    assert dec(e.get("monto_afectado")) == dec(conf.get("valor_inicial")), e
    obs(f"tipo_evento observado de la confirmación: {e.get('tipo_evento')}")


def test_TC_M06_040_auditoria_de_la_reversion(env, esc):
    env.presupuesto()
    ida, conf = env.reconocer(esc, origen="compra", costo="2500000.0000", soporte="Factura QA-M06-040")
    assert env.revertir(ida, MOTIVO).status in (200, 201)
    ev = env.auditoria(ida, "RECONOCIMIENTO_REVERTIDO")
    assert len(ev) == 1, ev
    payload = ev[0].get("resumen_payload") or {}
    assert payload.get("motivo_reversion") == MOTIVO, payload
    assert payload.get("id_reconocimiento_revertido") == conf.get("id_reconocimiento_inicial"), payload
    assert ev[0].get("actor") and ev[0].get("fecha_hora") and ev[0].get("activo"), f"falta usuario, fecha-hora o activo: {ev[0]}"
    assert env.contar("reconocimientos_iniciales", ida) == 1, "el original debe permanecer consultable"


def test_TC_M06_041a_completitud_de_la_auditoria(env, esc):
    """Ficha 041: cada acción deja su evento con usuario, fecha-hora y resultado; sin acciones sin evento ni eventos huérfanos."""
    env.presupuesto(60)
    sin_precio = env.escenario(categoria="POR_CABEZA", precio=None)
    a = env.activo(esc, origen="compra", costo="2500000.0000", soporte="Factura QA-M06-041")      # propuesta + confirmación + reversión
    assert env.propuesta(a).status == 200
    assert env.confirmar(a).status == 201
    assert env.revertir(a, MOTIVO).status in (200, 201)
    b = env.activo(sin_precio, origen="nacimiento", costo=None, soporte=None)                       # bloqueo sin valor
    assert 400 <= env.confirmar(b).status < 500
    eventos_a = env.auditoria(a)
    tipos_a = [e.get("tipo_evento") for e in eventos_a]
    obs(f"eventos del activo con propuesta, confirmación y reversión: {tipos_a}")
    assert tipos_a.count("RECONOCIMIENTO_INICIAL") == 1 and tipos_a.count("RECONOCIMIENTO_REVERTIDO") == 1, tipos_a
    ev_b = env.auditoria(b, "RECONOCIMIENTO_BLOQUEADO_SIN_VALOR")
    assert len(ev_b) == 1, f"el bloqueo sin valor debe tener su evento: {ev_b}"
    for e in [x for x in eventos_a if x.get("tipo_evento") in ("RECONOCIMIENTO_INICIAL", "RECONOCIMIENTO_REVERTIDO")] + ev_b:
        assert e.get("actor") and e.get("fecha_hora") and e.get("severidad"), f"el evento debe traer usuario, fecha-hora y resultado/severidad: {e}"
    for t in tipos_a:
        assert t in ("RECONOCIMIENTO_INICIAL", "RECONOCIMIENTO_REVERTIDO", "LINEA_ASIENTO_REGISTRADA",
                     "LINEA_ASIENTO_PENDIENTE_CUENTA", "CALCULO_VALOR_RAZONABLE"), f"evento inesperado u huérfano: {t}"
    if "CALCULO_VALOR_RAZONABLE" not in tipos_a:
        obs("la propuesta (GET) no deja evento propio: se calcula al vuelo y no persiste nada (RF-82 no pide registrarla).")


def test_TC_M06_041b_rechazo_de_la_propuesta_queda_registrado(env, esc):
    pytest.skip("NO APLICA: INC-M06-305 se cerró como NO-ES-ERROR (Desarrollo y Análisis, V2.0): RF-82 FA-4 no pide una acción de rechazar la "
                "propuesta, así que no hay evento de rechazo que verificar. Queda como observación (la propuesta se descarta al no confirmarla).")


@pytest.mark.parametrize("rol", ["productor", "veterinario", "auditor"])
def test_TC_M06_041c_confirmacion_por_rol_no_autorizado_queda_registrada(env, esc, rol):
    """Ficha 041: «el intento de otro rol queda registrado como rechazado». RNF-82-05: rechazado y registrado en el log de auditoría."""
    env.presupuesto(30)
    ida = env.activo(esc, origen="compra", costo="2500000.0000", soporte="Factura QA-M06-041c")
    antes = int(uno(env.sql("SELECT count(*) AS n FROM modulo6.auditorias_financieras")) or 0)
    r = env.confirmar(ida, rol)
    assert r.status == 403, f"[{rol}] la confirmación debía rechazarse con 403: {r}"
    despues = int(uno(env.sql("SELECT count(*) AS n FROM modulo6.auditorias_financieras")) or 0)
    assert despues > antes, (f"[{rol}] el intento de confirmar (HTTP 403) no dejó ningún registro en el log de auditoría de M06 "
                             f"(eventos antes {antes}, después {despues}); RNF-82-05 lo exige")
    assert env.contar("reconocimientos_iniciales", ida) == 0, "el rechazo no debe crear el reconocimiento"


@pytest.mark.parametrize("metodo", ["PUT", "PATCH", "DELETE"])
@pytest.mark.parametrize("rol", ["contador", "admin"])
def test_TC_M06_042_inmutabilidad_del_reconocimiento(env, esc, metodo, rol):
    env.presupuesto(30)
    ida, conf = env.reconocer(esc, origen="compra", costo="2500000.0000", soporte="Factura QA-M06-042")
    # El SQL del sandbox no ve modulo6 (RLS): el estado del reconocimiento se lee del historial del activo por la API (Contador).
    campos = ("id_reconocimiento_inicial", "valor_razonable_neto_inicial", "origen_financiero", "fecha_reconocimiento", "estado")
    def _estado():
        return [{k: x.get(k) for k in campos} for x in (env.historial(ida).get("reconocimientos") or [])]
    sql_rec = (f"SELECT valor_razonable_neto_inicial, origen_financiero, fecha_reconocimiento, estado::text AS estado FROM modulo6.reconocimientos_iniciales "
               f"WHERE id_activo_biologico = {ida}")
    antes = _estado()
    assert len(antes) == 1 and antes[0]["estado"] == "CONFIRMADO", antes
    antes_sql = env.sql(sql_rec)
    assert len(antes_sql) == 1, f"la base debía mostrar el reconocimiento confirmado (devolvió {len(antes_sql)}): el SQL del sandbox no lo ve"
    idr = conf.get("id_reconocimiento_inicial")
    cuerpo = {"valor_razonable_neto_inicial": "1.00", "origen_financiero": "donacion", "fecha_reconocimiento": str(hoy())}
    for ruta in (f"/finanzas/reconocimientos/{ida}", f"/finanzas/reconocimientos/{idr}"):
        r = env.call(metodo, ruta, rol, json=None if metodo == "DELETE" else cuerpo)
        assert r.status < 500 and r.status in (401, 403, 404, 405), f"{metodo} {ruta} como {rol}: debía rechazarse (405/403/404) y respondió {r}"
    despues = _estado()
    assert antes == despues, f"el reconocimiento cambió: {antes} -> {despues}"
    assert env.sql(sql_rec) == antes_sql, f"el reconocimiento cambió en la base: {antes_sql} -> {env.sql(sql_rec)}"



_C043 = {}


def _datos_043(env):
    """Reconocimiento con valor de 4 decimales: precio por cabeza 1.234.567,89 con transporte 0,01 % -> neto 1.234.444,4332."""
    if env.run_id not in _C043:
        _asegurar(env, 60)
        esc = env.escenario(categoria="POR_CABEZA", precio="1234567.89", costos=("0.0001", "0", "0"))
        ida = env.activo(esc, origen="nacimiento", costo=None, soporte=None)
        conf = env.prep(env.confirmar(ida), (201,), "confirmar el reconocimiento")
        esperado4 = neto_esperado("1234567.89", ("0.0001", "0", "0"))
        guardado = dec((env.historial(ida).get("reconocimientos") or [{}])[0].get("valor_razonable_neto_inicial"))
        _C043.clear()
        _C043[env.run_id] = (ida, conf, esperado4, guardado)
    return _C043[env.run_id]


def test_TC_M06_043a_asiento_cuadrado_espejo_exacto_y_neto_cero(env):
    env.presupuesto(30)
    ida, conf, esperado4, guardado = _datos_043(env)
    assert guardado == esperado4, f"el valor reconocido guardado debía ser {esperado4} (4 decimales): {guardado}"
    originales = conf.get("lineas")
    verificar_asiento(originales)
    assert env.revertir(ida, MOTIVO).status in (200, 201)
    lineas = [l for l in lineas_de(env.historial(ida)) if l.get("estado") == "REGISTRADA"]
    espejos = [l for l in lineas if l.get("es_reverso")]
    base = [l for l in lineas if not l.get("es_reverso")]
    assert len(espejos) == len(base) == len(originales), lineas
    for o, e in zip(base, espejos):                              # el espejo invierte exactamente débito y crédito, con el mismo valor
        assert (e["cuenta_debito"], e["cuenta_credito"]) == (o["cuenta_credito"], o["cuenta_debito"]), (o, e)
        assert dec(e["valor"]) == dec(o["valor"]), (o, e)
    saldo: dict = defaultdict(Decimal)
    for l in lineas:
        saldo[l["cuenta_debito"]] += dec(l["valor"])
        saldo[l["cuenta_credito"]] -= dec(l["valor"])
    assert saldo and all(v == 0 for v in saldo.values()), f"el original y el espejo deben netear 0,0000 por cuenta: {dict(saldo)}"


def test_TC_M06_043b_valor_de_la_linea_con_cuatro_decimales_exactos(env):
    """Valor reconocido con 4 decimales y línea del asiento a 2 decimales (corrección de Desarrollo, lanzamiento backend 1.4.0, INC-M06-307: «componentes
    menores a 0,01 se registran sin línea de valor 0»; lineas_asiento_nic41.valor es NUMERIC(18,2)). La ficha 043 pedía 4 decimales en el asiento; manda la
    actualización de Desarrollo. Se exige: valor reconocido exacto a 4 decimales (RNF-84-01); línea del asiento igual a ese valor a 2 decimales; suma de
    las líneas igual a la línea. El modo de redondeo (mitad hacia arriba o truncado) no está definido: se aceptan ambos y se anota."""
    env.presupuesto(30)
    ida, conf, esperado4, guardado = _datos_043(env)
    assert guardado == esperado4, f"el valor reconocido debía conservar 4 decimales ({esperado4}): {guardado}"
    lineas = conf.get("lineas")
    ln = lineas[0]
    arriba = esperado4.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    truncado = esperado4.quantize(Decimal("0.01"), rounding=ROUND_DOWN)
    valor = dec(ln["valor"])
    obs(f"valor reconocido {guardado} (4 decimales) / línea del asiento {ln['valor']} (2 decimales por diseño, corrección de Desarrollo); "
        f"mitad hacia arriba {arriba}, truncado {truncado}.")
    assert valor in (arriba, truncado), f"la línea del asiento vale {ln['valor']}; el valor reconocido {esperado4} a 2 decimales es {arriba} (o {truncado} truncado)"
    assert sum(dec(l["valor"]) for l in lineas) == valor, f"la suma de las líneas debía ser {valor}: {[l['valor'] for l in lineas]}"


def test_TC_M06_044_doble_confirmacion_inmediata(env, esc):
    env.presupuesto(30)
    ida = env.activo(esc, origen="compra", costo="2500000.0000", soporte="Factura QA-M06-044")
    r1, r2 = env.confirmar(ida), env.confirmar(ida)
    assert r1.status == 201, r1
    assert 400 <= r2.status < 500, f"la segunda confirmación debía rechazarse de forma controlada (sin 5xx): {r2}"
    obs(f"segunda confirmación: HTTP {r2.status} {r2.err}")
    assert env.contar("reconocimientos_iniciales", ida, "AND estado = 'CONFIRMADO'") == 1
    propias = [ln for ln in lineas_de(env.historial(ida)) if ln.get("tabla_origen") == "reconocimientos_iniciales"]
    assert len(propias) == 1, f"debe haber un solo asiento del reconocimiento (historial de la API): {propias}"
    assert int(uno(env.sql(f"SELECT count(*) AS n FROM modulo6.lineas_asiento_nic41 WHERE id_activo_biologico = {ida} "
                           f"AND tabla_origen = 'reconocimientos_iniciales'")) or 0) == 1, "la base debe tener un solo asiento del reconocimiento"


def test_TC_M06_045_tiempo_de_respuesta_del_reconocimiento(env):
    pytest.skip("SE PRUEBA CON NEWMAN (responseTime): Test_Modulo6/RF-82/TC-M06-G08/TC-M06-G08.json -> "
                ".\\correr_newman.ps1 -Caso G08 -Modulo 6 -Rf RF-82 (desde tests\\Test_Testing).")


def test_TC_M06_041d_el_administrador_confirma(env, esc):
    """V2.0 (13-nov): el Administrador tiene todos los permisos: su confirmación se acepta y no es un intento no autorizado."""
    env.presupuesto(30)
    ida = env.activo(esc, origen="compra", costo="2500000.0000", soporte="Factura QA-M06-041d")
    r = env.confirmar(ida, "admin")
    assert r.status == 201, f"[admin] la confirmación debía aceptarse (todos los permisos): {r}"
    assert env.contar("reconocimientos_iniciales", ida, "AND estado = 'CONFIRMADO'") == 1, "debe quedar un reconocimiento confirmado"
