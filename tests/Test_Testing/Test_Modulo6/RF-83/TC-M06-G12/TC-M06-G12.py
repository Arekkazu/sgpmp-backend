# | Fecha      | Nombre           | Que se hizo                                                              |
# |------------|------------------|--------------------------------------------------------------------------|
# | 2026-11-07 | Daniela Castillo | M06 RF-83: script del grupo TC-M06-G12 (pytest + sandbox, rol Contador) |
# | 2026-11-08 | Daniela Castillo | M06 RF-83: G12 con precio histórico real (vencido), alerta MEDICION_PENDIENTE, costo y motivo en auditoría |
"""
TC-M06-G12 - Medición sin precio de mercado: precio histórico, costo y marca de estimación.   RF-83 (FA-1, CA-5, CA-7).   Casos: TC-M06-058 a TC-M06-060.

«Sin precio vigente pero con histórico»: no se puede vencer un precio ya registrado ni registrar uno vencido que sea el más reciente (manda el de
mayor fecha de vigencia). Se logra así, dentro del run y por la API: el activo se reconoce con precio por kg vigente; luego se registra un precio
POR_CABEZA con vigencia hoy-3 y vencimiento hoy-1 (histórico vencido) y se cambia la categoría de precio de la especie a POR_CABEZA (M09). La
especie queda sin precio vigente y con ese precio como último conocido. Un evento de crecimiento (pesaje) dispara la medición.

- 058a: la medición se registra con tiene_valor_estimado=true usando el último precio histórico, no se bloquea y queda MEDICION_CON_ESTIMACION.
- 058b: la ficha pide además la alerta MEDICION_PENDIENTE (RF-83 FA-1 «se notifica al Contador», CA-7). Se verifica en el registro de auditoría.
- 059: «sin precio vigente ni histórico, activo reconocido por costo»: el RF/ficha esperan medir con el costo y marcar valor_estimado=true. Se prepara el
  escenario real (especie sin precio, reconocimiento por costo, pesaje); si no se genera medición, el caso queda BLOQUEADO (funcionalidad no implementada).
- 060a: un activo medido con precio (valor_estimado=false) y otro estimado (true), visibles en historial, listado del período y auditoría.
- 060b: «el motivo de estimación queda en el registro de auditoría».

Cómo correrlo:
    python -m pytest "tests/Test_Testing/Test_Modulo6/RF-83/TC-M06-G12/TC-M06-G12.py" -v -s -rs --noconftest --html="tests/Test_Testing/Test_Modulo6/RF-83/TC-M06-G12/reporte-TC-M06-G12.html" --self-contained-html
"""
from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from m06_lib import *  # noqa: F401,F403,E402
from m06_lib import _lista as lista_de  # noqa: E402

P = "20000.00"
HISTORICO = "2000000.00"          # por cabeza; con costos 2/3/1 % el neto es 1.880.000,0000


@pytest.fixture(scope="module")
def env():
    e = Entorno(("admin", "ingeniero"))
    yield e
    e.cerrar()


def _nuevo(env):
    """Un run por caso: las categorías de peso comparten la especie sembrada y sus precios."""
    if env.inicio is not None:
        env.nuevo_run()


def _dejar_sin_precio_vigente(env, esc):
    """Precio POR_CABEZA ya vencido (histórico) y la especie pasa a usar esa categoría: sin precio vigente, con último conocido."""
    env.procesar_eventos()
    env.precio(esc, HISTORICO, desde=hoy() - timedelta(days=3), hasta=hoy() - timedelta(days=1), categoria="POR_CABEZA")
    env.prep(env.call("PUT", f"/finanzas/configuracion/especies/{esc.id_especie}", "contador", json={
        "clasificacion": "PRODUCCION", "categoria_precio": "POR_CABEZA", "vida_util_meses": 60}), (200, 201), "especie con precio solo histórico")


def _estimada(env, esc, ida, kg="450"):
    _dejar_sin_precio_vigente(env, esc)
    env.pesaje(ida, kg)
    return env.procesar_eventos()


def test_TC_M06_058a_sin_precio_vigente_usa_el_ultimo_historico_y_marca_estimacion(env):
    _nuevo(env)
    env.presupuesto(60)
    esc = env.escenario(categoria="PESO_KG", precio=P)
    ida = env.base_medible(esc, "400")
    r = _estimada(env, esc, ida)
    assert r.status == 200, f"el proceso no debe bloquearse: {r}"
    ms = env.mediciones(ida)
    assert ms, "con precio solo histórico la medición NO debe bloquearse: debía usar el último precio conocido"
    m = ms[-1]
    assert m["tiene_valor_estimado"] is True, m
    assert dec(m["valor_razonable_actual"]) == vn(1, HISTORICO), f"debía usar el último precio histórico ({HISTORICO} por cabeza): {m}"
    assert "MEDICION_CON_ESTIMACION" in env.tipos_auditoria(ida), env.tipos_auditoria(ida)


def test_TC_M06_058b_alerta_medicion_pendiente_en_la_medicion_estimada(env):
    _nuevo(env)
    env.presupuesto(60)
    esc = env.escenario(categoria="PESO_KG", precio=P)
    ida = env.base_medible(esc, "400")
    _estimada(env, esc, ida)
    if not env.mediciones(ida):
        no_verificable("no se generó la medición estimada.")
    tipos = env.tipos_auditoria(ida)
    obs(f"eventos de auditoría del activo: {tipos}")
    assert "MEDICION_PENDIENTE" in tipos, ("la ficha y RF-83 (FA-1, salida 4, CA-7) piden la alerta MEDICION_PENDIENTE al Contador en la "
                                           f"medición con estimación; solo quedó {sorted(set(tipos))} (M06 no notifica al Contador por este motivo)")


def test_TC_M06_059_sin_precio_ni_historico_usa_el_costo(env):
    _nuevo(env)
    env.presupuesto(70)
    esc = env.escenario(categoria="PESO_KG", precio=None)                     # especie sin ningún precio RF-89
    ida = env.activo(esc, origen="compra", costo="2500000.0000", soporte="Factura QA-M06-059")
    r = env.prep(env.confirmar(ida), (200, 201), "reconocimiento por costo")
    assert r.get("indicador_valoracion") == "VALORACION_POR_COSTO", f"precondición: activo reconocido por costo: {r}"
    env.procesar_eventos()
    env.pesaje(ida, "450")                                                    # evento CRECIMIENTO
    assert env.procesar_eventos().status == 200
    ms = env.mediciones(ida)
    pr = env.sql("SELECT resultado::text AS resultado, detalle FROM modulo6.procesamientos_eventos_m02 "
                 "ORDER BY fecha_procesamiento DESC, id_evento DESC LIMIT 1")
    if not ms:
        bloqueado("funcionalidad no implementada: RF-83 FA-1 (sin precio vigente ni histórico se usa el costo y se marca valor_estimado=true) "
                  f"no se cumple; el evento CRECIMIENTO sobre el activo reconocido por costo quedó {pr[0] if pr else 'sin procesar'} "
                  "y no se generó medición.")
    m = ms[-1]
    assert m["tiene_valor_estimado"] is True, m
    assert "MEDICION_CON_ESTIMACION" in env.tipos_auditoria(ida)


def test_TC_M06_060a_la_estimacion_no_se_oculta(env):
    _nuevo(env)
    env.presupuesto(100)
    esc = env.escenario(categoria="PESO_KG", precio=P)
    a = env.base_medible(esc, "400")
    b = env.base_medible(esc, "400")
    assert env.medir(esc, a, "21000.00", "450").status == 200               # A: con precio vigente
    assert _estimada(env, esc, b).status == 200                             # B: sin precio vigente, con histórico
    ma, mb = env.mediciones(a), env.mediciones(b)
    if not ma or not mb:
        no_verificable(f"no se generaron ambas mediciones (precio vigente: {len(ma)}, estimada: {len(mb)}).")
    assert ma[-1]["tiene_valor_estimado"] is False and mb[-1]["tiene_valor_estimado"] is True, (ma[-1], mb[-1])
    assert "MEDICION_POSTERIOR" in env.tipos_auditoria(a) and "MEDICION_CON_ESTIMACION" in env.tipos_auditoria(b)
    eventos_b = [e for e in env.auditoria(b) if e.get("tipo_evento") == "MEDICION_CON_ESTIMACION"]
    assert eventos_b and eventos_b[-1].get("severidad") in ("WARNING", "ADVERTENCIA"), eventos_b
    periodo = mb[-1]["id_periodo_contable"]
    listado = env.call("GET", f"/finanzas/periodos/{periodo}/mediciones", "contador")
    assert listado.status == 200, listado
    filas = {f["id_medicion_posterior"]: f for f in lista_de(listado.data, "mediciones")}
    assert filas[mb[-1]["id_medicion_posterior"]]["tiene_valor_estimado"] is True, "el listado del período debe mostrar la marca de estimación"
    assert filas[ma[-1]["id_medicion_posterior"]]["tiene_valor_estimado"] is False


def test_TC_M06_060b_el_motivo_de_la_estimacion_queda_en_auditoria(env):
    _nuevo(env)
    env.presupuesto(70)
    esc = env.escenario(categoria="PESO_KG", precio=P)
    ida = env.base_medible(esc, "400")
    _estimada(env, esc, ida)
    if not env.mediciones(ida):
        no_verificable("no se generó la medición estimada.")
    # La API de consulta de auditoría no devolvió el contenido del evento (payload vacío): se lee la columna directamente por SELECT.
    filas = env.sql("SELECT datos_nuevos::text AS carga, severidad::text AS severidad FROM modulo6.auditorias_financieras "
                    f"WHERE tipo_evento::text = 'MEDICION_CON_ESTIMACION' AND id_activo_biologico = {int(ida)} ORDER BY 1")
    assert filas, "debe existir el evento MEDICION_CON_ESTIMACION"
    texto = filas[-1]["carga"] or "{}"
    carga = json.loads(texto)
    obs(f"contenido del evento MEDICION_CON_ESTIMACION ({filas[-1]['severidad']}): {texto}")
    claves = {str(k).lower() for k in carga.keys()}
    motivo = [k for k in claves if any(t in k for t in ("motivo", "razon", "causa", "fuente", "precio_unitario", "id_precio", "estimacion"))]
    assert motivo, ("la ficha espera que el motivo de la estimación (sin precio vigente, último precio usado) quede en la auditoría; "
                    f"el evento solo trae {sorted(claves)}")
