# | Fecha      | Nombre           | Que se hizo                                                              |
# |------------|------------------|--------------------------------------------------------------------------|
# | 2026-11-07 | Daniela Castillo | M06 RF-83: script del grupo TC-M06-G15 (pytest + sandbox, rol Contador) |
# | 2026-11-08 | Daniela Castillo | M06 RF-83: G15 alineado con la ficha y RF-94: 071 a 075 en pytest; 076 y 077 (tiempos) pasan a Newman |
"""
TC-M06-G15 - Integración con RF-86 y RF-52, auditoría, inmutabilidad, idempotencia y rendimiento de la medición.
RF-83 (CU02).   Casos: TC-M06-071 a TC-M06-077.

- Herramientas: 071 a 075 con pytest (este archivo); 076 y 077 (tiempos, responseTime) con Newman: TC-M06-G15.json
  (correr_newman.ps1 -Caso G15 -Modulo 6 -Rf RF-83). En pytest quedan omitidos con esa indicación.
- 071: la variación se registra en RF-86 (modulo6.variaciones_valor_razonable, enlazada a la medición y al evento) y sus líneas de asiento
  nacen de esa variación; ninguna línea tiene como origen la medición (RF-83 no asienta).
- 072: «RF-52» es la bitácora de M02; las mediciones de M06 se consultan por el historial del activo, por el listado del período y por
  RF-94 (auditoría). La API solo filtra por activo y período. 072a prueba esos dos filtros (el activo con mediciones en dos períodos: el
  segundo se obtiene cerrando el primero) y que el total coincide con la BD; 072b prueba los filtros por id_evento y valor_estimado que pide la
  ficha: si la API no los trae, el caso queda BLOQUEADO (funcionalidad no implementada, se reporta como hallazgo).
- 073: el vínculo con el evento se verifica con modulo6.procesamientos_eventos_m02 (el SELECT del sandbox no ve modulo2) y la auditoría con
  GET /finanzas/auditoria (técnico y legible): id_referencia = id de la medición, fecha-hora, actor, severidad y payload.
- 074: no existen operaciones PUT/PATCH/DELETE de mediciones: se intentan con Contador y Administrador y se verifica que se rechazan y que el
  SELECT no cambia. No se hace UPDATE/DELETE directo en BD.
- 075: POST /finanzas/eventos/procesar no recibe id_evento: se reprocesa la cola 3 veces y se verifica por SELECT una sola medición por id_evento.

Cómo correrlo:
    python -m pytest "tests/Test_Testing/Test_Modulo6/RF-83/TC-M06-G15/TC-M06-G15.py" -v -s -rs --noconftest --html="tests/Test_Testing/Test_Modulo6/RF-83/TC-M06-G15/reporte-TC-M06-G15.html" --self-contained-html
"""
from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from m06_lib import *  # noqa: F401,F403,E402
from m06_lib import _lista as lista_de  # noqa: E402

P = "20000.00"
HISTORICO = "2000000.00"          # por cabeza, precio histórico vencido (como en G12)


@pytest.fixture(scope="module")
def env():
    e = Entorno(("admin", "ingeniero"))
    yield e
    e.cerrar()


def _nuevo(env):
    """Un run por caso: las categorías de peso comparten la especie sembrada y sus precios, y el presupuesto de 170 s es por run."""
    if env.inicio is not None:
        env.nuevo_run()


def _filas_med(env, ida):
    return env.sql("SELECT id_medicion_posterior AS id, id_evento, origen_medicion::text AS origen, id_periodo_contable AS periodo, "
                   "valor_razonable_anterior::text AS vant, valor_razonable_actual::text AS vact, ganancia_perdida_transformacion::text AS tb, "
                   "ganancia_perdida_precio_mercado::text AS pm, variacion_total::text AS total, tiene_valor_estimado AS est "
                   f"FROM modulo6.mediciones_posteriores WHERE id_activo_biologico = {int(ida)} ORDER BY id_medicion_posterior")


def _auditoria_tecnica(env, ida):
    r = env.call("GET", "/finanzas/auditoria", "contador", params={"id_activo_biologico": ida, "tamano": 500, "formato": "TECNICO"})
    assert r.status == 200, f"GET /finanzas/auditoria (técnico) respondió {r}"
    return lista_de(r.data, "eventos")


def _payload(e):
    p = e.get("payload_evento")
    if isinstance(p, str):
        try:
            return json.loads(p)
        except ValueError:
            return {}
    return p or {}


def _evento_procesado(env, ide):
    filas = env.sql(f"SELECT resultado::text AS resultado FROM modulo6.procesamientos_eventos_m02 WHERE id_evento = {int(ide)}")
    assert filas, f"el id_evento {ide} de la medición no figura como procesado en M06 (procesamientos_eventos_m02)"
    assert filas[0]["resultado"] == "PROCESADO", f"id_evento {ide}: {filas[0]}"


# ------------------------------------------------------------------------------------------------------------------- 071
def test_TC_M06_071_la_variacion_se_envia_a_rf86_y_rf83_no_asienta(env):
    _nuevo(env)
    env.presupuesto(60)
    esc = env.escenario(categoria="PESO_KG", precio=P)
    ida = env.base_medible(esc, "400")
    assert env.medir(esc, ida, "21000.00", "450").status == 200
    ms = _filas_med(env, ida)
    if not ms:
        no_verificable("no se generó medición.")
    m = ms[-1]
    # RF-86 registra una fila por tipo de variación (transformación biológica y precio de mercado): se suman las filas de la medición
    var = env.sql("SELECT id_variacion_valor_razonable AS id, tipo::text AS tipo, id_evento, variacion_transformacion::text AS tb, "
                  "variacion_precio_mercado::text AS pm FROM modulo6.variaciones_valor_razonable "
                  f"WHERE id_activo_biologico = {int(ida)} AND id_medicion_posterior = {int(m['id'])} ORDER BY 1")
    assert var, "RF-86 debe recibir la variación de la medición (modulo6.variaciones_valor_razonable enlazada a la medición)"
    assert all(v["id_evento"] == m["id_evento"] for v in var), f"las variaciones deben llevar el id_evento de la medición: {var} / {m}"
    suma_tb = sum((dec(v["tb"]) for v in var), Decimal("0"))
    suma_pm = sum((dec(v["pm"]) for v in var), Decimal("0"))
    assert abs(suma_tb - dec(m["tb"])) <= dec("0.01") and abs(suma_pm - dec(m["pm"])) <= dec("0.01"), (
        f"RF-86 debe recibir los dos componentes de la medición (transformación {m['tb']}, precio {m['pm']}); recibió {var}")
    obs(f"RF-86 recibió {len(var)} variación(es) de la medición {m['id']}: {[(v['tipo'], v['tb'], v['pm']) for v in var]} "
        f"(la medición guarda 4 decimales; la variación de RF-86, 2).")
    ids = ", ".join(str(int(v["id"])) for v in var)
    lineas = env.sql("SELECT tipo_hecho::text AS tipo_hecho, valor::text AS valor FROM modulo6.lineas_asiento_nic41 "
                     f"WHERE id_activo_biologico = {int(ida)} AND NOT es_reverso AND tabla_origen = 'variaciones_valor_razonable' "
                     f"AND id_origen IN ({ids})")
    por_tipo = {ln["tipo_hecho"]: dec(ln["valor"]) for ln in lineas}
    assert "VARIACION_VR_PM" in por_tipo and "VARIACION_VR_TB" in por_tipo, f"RF-86 debe generar las dos líneas de la variación: {lineas}"
    assert abs(por_tipo["VARIACION_VR_PM"] - trunc2(abs(dec(m["pm"])))) <= dec("0.01"), (por_tipo, m)
    assert abs(por_tipo["VARIACION_VR_TB"] - trunc2(abs(dec(m["tb"])))) <= dec("0.01"), (por_tipo, m)
    propias = env.sql("SELECT count(*) AS n FROM modulo6.lineas_asiento_nic41 WHERE tabla_origen = 'mediciones_posteriores' "
                      f"AND id_activo_biologico = {int(ida)}")
    assert int(uno(propias)) == 0, "RF-83 no debe generar asientos propios (las líneas las genera RF-86)"


# ------------------------------------------------------------------------------------------------------------------- 072
def _esc072(env):
    """Activo A con mediciones en dos períodos (el primero se cierra) y activo B con una medición estimada. Un solo run para 072a y 072b."""
    c = getattr(env, "_g15_072", None)
    if c and c["run"] == env.run_id and env.inicio is not None:
        return c
    _nuevo(env)
    env.presupuesto(130)
    esc = env.escenario(categoria="PESO_KG", precio=P)
    a = env.base_medible(esc, "400")
    b = env.base_medible(esc, "400")
    env.medir(esc, a, "21000.00", "450")
    env.medir(esc, a, None, "470")
    p1 = env.periodo(a)
    r = env.cierre(p1)
    if r.status not in (200, 201, 202):
        bloqueado(f"no se pudo cerrar el período {p1} dentro del run (se necesita para tener mediciones en dos períodos): {r}")
    env.pesaje(a, "480")                                  # tras el cierre el evento se mide en el período siguiente (ver H-13)
    env.procesar_eventos()
    env.procesar_eventos()
    env.precio(esc, HISTORICO, desde=hoy() - timedelta(days=3), hasta=hoy() - timedelta(days=1), categoria="POR_CABEZA")
    env.prep(env.call("PUT", f"/finanzas/configuracion/especies/{esc.id_especie}", "contador", json={
        "clasificacion": "PRODUCCION", "categoria_precio": "POR_CABEZA", "vida_util_meses": 60}), (200, 201), "especie con precio solo histórico")
    env.pesaje(b, "450")
    env.procesar_eventos()
    env._g15_072 = {"run": env.run_id, "esc": esc, "a": a, "b": b}
    return env._g15_072


def test_TC_M06_072a_mediciones_consultables_por_activo_y_periodo_con_total_en_bd(env):
    c = _esc072(env)
    a, b = c["a"], c["b"]
    ma, mb = env.mediciones(a), env.mediciones(b)
    if not ma or not mb:
        no_verificable(f"mediciones generadas: activo A {len(ma)}, activo B {len(mb)}.")
    periodos = sorted({m["id_periodo_contable"] for m in ma})
    if len(periodos) < 2:
        no_verificable(f"el activo A quedó con mediciones en un solo período ({periodos}): no se obtuvo el caso «períodos distintos».")
    campos = {"id_medicion_posterior", "id_evento", "id_periodo_contable", "fecha_medicion", "valor_razonable_anterior", "valor_razonable_actual",
              "ganancia_perdida_transformacion", "ganancia_perdida_precio_mercado", "variacion_total", "tiene_valor_estimado", "origen_medicion"}
    assert all(campos <= set(m) for m in ma + mb), "las mediciones del historial deben traer todos sus campos"
    # por activo
    bd_a = {f["id"] for f in _filas_med(env, a)}
    assert {m["id_medicion_posterior"] for m in ma} == bd_a, "el historial del activo debe traer exactamente sus mediciones de la BD"
    # por período
    for p in periodos:
        r = env.call("GET", f"/finanzas/periodos/{p}/mediciones", "contador")
        assert r.status == 200, r
        listado = lista_de(r.data, "mediciones")
        bd = env.sql("SELECT id_medicion_posterior AS id, id_activo_biologico AS ida FROM modulo6.mediciones_posteriores "
                     f"WHERE id_periodo_contable = {int(p)}")
        assert len(listado) == len(bd), f"el listado del período {p} trae {len(listado)} y la BD tiene {len(bd)}"
        assert {f["id_medicion_posterior"] for f in listado} == {f["id"] for f in bd}, f"período {p}: el listado no coincide con la BD"
        faltan = {"id_medicion_posterior", "id_activo_biologico", "valor_razonable_anterior", "valor_razonable_actual",
                  "ganancia_perdida_transformacion", "ganancia_perdida_precio_mercado", "variacion_total", "tiene_valor_estimado"}
        assert all(faltan <= set(f) for f in listado), "el listado del período debe traer los campos de cada medición"
    # valor estimado: se distingue en las filas (B estimada, A con precio)
    assert mb[-1]["tiene_valor_estimado"] is True and all(m["tiene_valor_estimado"] is False for m in ma)
    obs(f"Activo A con mediciones en los períodos {periodos}; el listado del período no trae id_evento (sí el historial del activo).")


def test_TC_M06_072b_filtros_por_evento_y_valor_estimado(env):
    c = _esc072(env)
    a, b = c["a"], c["b"]
    ma, mb = env.mediciones(a), env.mediciones(b)
    if not ma or not mb:
        no_verificable("no se generaron las mediciones del escenario.")
    periodo = mb[-1]["id_periodo_contable"]

    def listar(**params):
        r = env.call("GET", f"/finanzas/periodos/{periodo}/mediciones", "contador", params=params or None)
        assert r.status == 200, r
        return lista_de(r.data, "mediciones")

    sin = listar()
    if len({f["tiene_valor_estimado"] for f in sin}) < 2 or len(sin) < 2:
        no_verificable(f"el período {periodo} no tiene mediciones estimadas y no estimadas a la vez ({len(sin)} filas).")
    faltan = []
    if not any((lambda f: 0 < len(f) < len(sin) and all(x["tiene_valor_estimado"] for x in f))(listar(**{k: "true"}))
               for k in ("tiene_valor_estimado", "valor_estimado")):
        faltan.append("valor_estimado")
    ev = next((m["id_evento"] for m in ma if m.get("id_evento")), None)
    if ev is None or not (lambda f: 0 < len(f) < len(sin))(listar(id_evento=ev)):
        faltan.append("id_evento")
    if faltan:
        bloqueado("funcionalidad no implementada: la ficha pide consultar las mediciones con filtros por id_evento y valor_estimado y la API solo "
                  f"filtra por activo (historial) y por período (listado); sin filtro en el servidor: {', '.join(faltan)}. "
                  f"El listado del período {periodo} devuelve las {len(sin)} mediciones aunque se pase el parámetro.")


# ------------------------------------------------------------------------------------------------------------------- 073
def _verificar_auditoria_medicion(env, ida, m, origen):
    tec = [e for e in _auditoria_tecnica(env, ida) if e.get("tipo_evento") in ("MEDICION_POSTERIOR", "MEDICION_CON_ESTIMACION")
           and str(e.get("id_referencia")) == str(m["id"])]
    assert tec, f"no hay evento de auditoría de la medición {m['id']} (id_referencia): {[e.get('tipo_evento') for e in _auditoria_tecnica(env, ida)]}"
    t = tec[-1]
    assert t.get("id_usuario") is not None or t.get("id_sistema") is not None, f"el evento debe conservar el usuario o proceso de origen: {t}"
    assert t.get("timestamp_evento"), f"el evento debe traer fecha-hora: {t}"
    assert t.get("severidad_evento"), f"el evento debe traer el resultado (severidad): {t}"
    pl = _payload(t)
    assert pl.get("origen") and pl.get("valor_actual") is not None, f"el payload debe traer el origen y los valores: {pl}"
    obs(f"Auditoría de la medición {m['id']} ({origen}): origen del payload {pl.get('origen')}, actor {'usuario ' + str(t.get('id_usuario')) if t.get('id_usuario') else 'sistema'}, severidad {t.get('severidad_evento')}.")
    leg = [e for e in env.auditoria(ida) if e.get("tipo_evento") == t["tipo_evento"] and e.get("fecha_hora")]
    assert leg and leg[-1].get("actor") and leg[-1].get("severidad"), f"la vista legible debe mostrar fecha-hora, actor y resultado: {leg[-1:]}"
    return t


def test_TC_M06_073a_trazabilidad_de_la_medicion_por_evento(env):
    _nuevo(env)
    env.presupuesto(60)
    esc = env.escenario(categoria="PESO_KG", precio=P)
    ida = env.base_medible(esc, "400")
    assert env.medir(esc, ida, None, "450").status == 200
    ms = _filas_med(env, ida)
    if not ms:
        no_verificable("no se generó medición.")
    m = ms[-1]
    assert m["origen"] == "EVENTO" and m["id_evento"] is not None, f"la medición por evento debe tener id_evento: {m}"
    _evento_procesado(env, m["id_evento"])
    assert m["periodo"] is not None, f"la medición debe tener id_periodo_contable: {m}"
    _verificar_auditoria_medicion(env, ida, m, "EVENTO")
    var = [e for e in _auditoria_tecnica(env, ida) if e.get("tipo_evento") == "VARIACION_REGISTRADA"]
    assert var and _payload(var[-1]).get("id_evento") == m["id_evento"], "la variación registrada debe quedar ligada al mismo id_evento"


def test_TC_M06_073b_trazabilidad_de_la_medicion_por_cierre(env):
    _nuevo(env)
    env.presupuesto(90)
    esc = env.escenario(categoria="PESO_KG", precio=P)
    ida = env.base_medible(esc, "400")
    env.precio(esc, "21000.00", desde=hoy())
    r = env.cierre(env.periodo(ida))
    if r.status not in (200, 201, 202):
        bloqueado(f"el cierre no se pudo ejecutar dentro del run: {r}")
    ms = [m for m in _filas_med(env, ida) if m["origen"] == "CIERRE_PERIODO"]
    if not ms:
        no_verificable("el cierre no creó medición para el activo.")
    m = ms[-1]
    assert m["periodo"] is not None and m["id_evento"] is None, f"la medición por cierre debe tener id_periodo_contable y no id_evento: {m}"
    _verificar_auditoria_medicion(env, ida, m, "CIERRE_PERIODO")
    var = [e for e in _auditoria_tecnica(env, ida) if e.get("tipo_evento") == "VARIACION_REGISTRADA"]
    assert var and _payload(var[-1]).get("id_cierre") is not None, "la variación por cierre debe quedar ligada al cierre del período"


# ------------------------------------------------------------------------------------------------------------------- 074
def test_TC_M06_074_las_mediciones_son_inmutables_por_api(env):
    _nuevo(env)
    env.presupuesto(60)
    esc = env.escenario(categoria="PESO_KG", precio=P)
    ida = env.base_medible(esc, "400")
    env.medir(esc, ida, None, "450")
    antes = _filas_med(env, ida)
    if not antes:
        no_verificable("no se generó medición.")
    idm = antes[-1]["id"]
    periodo = antes[-1]["periodo"]
    rutas = (f"/finanzas/mediciones/{idm}", f"/finanzas/periodos/{periodo}/mediciones/{idm}", f"/finanzas/activos/{ida}/mediciones/{idm}")
    for rol in ("contador", "admin"):
        for ruta in rutas:
            for metodo, cuerpo in (("PATCH", {"valor_razonable_actual": "1.0000"}), ("PUT", {"valor_razonable_actual": "1.0000"}), ("DELETE", None)):
                r = env.call(metodo, ruta, rol, json=cuerpo)
                assert not (200 <= r.status < 300), f"{metodo} {ruta} como {rol} no debe aceptarse: {r}"
                assert r.status < 500, f"{metodo} {ruta} como {rol} produjo un error de servidor: {r}"
    assert _filas_med(env, ida) == antes, "los valores de la medición deben permanecer intactos"
    obs("No existen operaciones de modificación ni eliminación de mediciones (404/405); la corrección es una nueva medición por evento o cierre.")


# ------------------------------------------------------------------------------------------------------------------- 075
def test_TC_M06_075_un_evento_una_medicion(env):
    _nuevo(env)
    env.presupuesto(60)
    esc = env.escenario(categoria="PESO_KG", precio=P)
    ida = env.base_medible(esc, "400")
    env.medir(esc, ida, None, "450")
    base = _filas_med(env, ida)
    if len(base) != 1:
        no_verificable(f"se esperaba 1 medición por el evento y hay {len(base)}.")
    ide = base[0]["id_evento"]
    for i in range(3):                                   # reprocesos de la cola (la operación no recibe id_evento)
        r = env.call("POST", "/finanzas/eventos/procesar", "contador", json={"id_evento": ide} if i == 2 else None)
        assert r.status == 200, r
    despues = _filas_med(env, ida)
    assert len(despues) == 1 and despues == base, "reprocesar no debe crear una segunda medición"
    por_evento = int(uno(env.sql(f"SELECT count(*) AS n FROM modulo6.mediciones_posteriores WHERE id_evento = {int(ide)}")))
    assert por_evento == 1, f"el id_evento {ide} debe tener una sola medición y tiene {por_evento}"
    procesados = int(uno(env.sql(f"SELECT count(*) AS n FROM modulo6.procesamientos_eventos_m02 WHERE id_evento = {int(ide)}")))
    assert procesados == 1, f"el id_evento {ide} debe figurar procesado una sola vez y figura {procesados}"
    obs("POST /finanzas/eventos/procesar no acepta id_evento (un cuerpo con id_evento se ignora): se reprocesó la cola 3 veces.")


# ------------------------------------------------------------------------------------------------------------------- 076 y 077
def test_TC_M06_076_tiempo_de_medicion_por_evento():
    pytest.skip("OMITIDO: el tiempo de respuesta se mide con Newman (responseTime): correr_newman.ps1 -Caso G15 -Modulo 6 -Rf RF-83 "
                "(desde tests\\Test_Testing). Mide 20 eventos secuenciales, cada uno <= 3000 ms.")


def test_TC_M06_077_cierre_de_un_lote_acotado_tiempo_por_activo():
    pytest.skip("OMITIDO: el tiempo de la medición por cierre se mide con Newman (responseTime): correr_newman.ps1 -Caso G15 -Modulo 6 -Rf RF-83 "
                "(desde tests\\Test_Testing). Lote de 20 a 25 activos; tiempo por activo <= 0,18 s.")
