# | Fecha      | Nombre           | Que se hizo                                                              |
# |------------|------------------|--------------------------------------------------------------------------|
# | 2026-11-07 | Daniela Castillo | M06 RF-83: script del grupo TC-M06-G14 (pytest + sandbox, rol Contador) |
# | 2026-11-08 | Daniela Castillo | M06 RF-83: G14 reescrito según ficha y CU02 (FA-04, FA-06, FA-07): auditoría del intento, estados, estimación, invariante propio |
# | 2026-11-08 | Daniela Castillo | M06 RF-83: G14 corregido: VARIACION_REGISTRADA no cuenta como auditoría del intento/exclusión; 070 con rol Contador antes de las peticiones inválidas |
# | 2026-11-11 | Daniela Castillo | M06 RF-83 v1.2: 067a revisado: sin precio, sin histórico ni costo queda MEDICION_PENDIENTE (no se estima con el costo) |
# | 2026-11-12 | Daniela Castillo | M06 reprueba V2.0 (RF-83 v1.2, RF-84 v1.1, RF-85 v1.2, RF-88 v2.0): el reporte HTML pasa a llamarse reporte-TC-M06-G14-V2.0.html |
# | 2026-11-13 | Daniela Castillo | M06 V2.0 (2.ª pasada): la base de datos pasa a ser la fuente de verdad (SQL ya funciona), expectativas alineadas con las correcciones de Desarrollo (notas de la versión 1.4.0) y las precondiciones que fallan ya no se omiten: quedan en rojo con diagnóstico |
"""
TC-M06-G14 - Restricciones y validación de la medición: período cerrado, estados no elegibles, recuperación, invariante e inválidos.
RF-83 (FA-04, FA-06, FA-07; restricciones 2 y 5).   Casos: TC-M06-065 a TC-M06-070.

Adaptaciones al backend (se documentan en la evidencia):
- Los eventos llevan la fecha de hoy: «último día del período cerrado / primer día del período abierto» (065) no se puede construir. Se prueba el
  evento de hoy después de cerrar el período (RF-83 restricción 2 y CU02 FA-04: bloquear, alerta, intento en auditoría).
- M06 no recibe eventos por API (POST /finanzas/eventos/procesar toma la cola de M02 y no recibe parámetros): los datos inválidos del 069 se envían
  al evento de crecimiento de M02, que es el que alimenta la medición. «id_evento ausente» no tiene equivalente en M06 y se registra como observación.
- 066: M02 no admite eventos sobre un activo que ya no está ACTIVO. INACTIVO y PENDIENTE_RECONOCIMIENTO se prueban con el pesaje ya registrado
  (INACTIVO: el activo cambia de estado antes de procesar la cola). BAJA: el pesaje anterior a la baja se mide legítimamente (el activo estaba ACTIVO
  al ocurrir el evento), así que se prueba que, ya dada la baja, un nuevo evento y el cierre del período no miden el activo (RF-83 restricción 5).
- 067 (RF-83 v1.2): «sin precio, sin histórico ni costo»: el activo a valor razonable cuya especie nunca tuvo precio en la categoría vigente queda
  MEDICION_PENDIENTE (sin medición parcial, sin pasar a costo); al cargar el precio el reintento crea una sola medición (067a). 067b reproduce el
  bloqueo real con costos de venta = 100 % (VALOR_NETO_NO_POSITIVO) y su recuperación.
- 068: se construyen en el run mediciones por evento, por estimación y por cierre (los escenarios de G09 a G13 corren en otros runs y se deshacen).
  FA-06 (alerta de inconsistencia) no se puede provocar desde QA: se cubre con este invariante.

Cómo correrlo:
    python -m pytest "tests/Test_Testing/Test_Modulo6/RF-83/TC-M06-G14/TC-M06-G14.py" -v -s -rs --noconftest --html="tests/Test_Testing/Test_Modulo6/RF-83/TC-M06-G14/reporte-TC-M06-G14-V2.0.html" --self-contained-html
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from m06_lib import *  # noqa: F401,F403,E402

P = "20000.00"
HISTORICO = "2000000.00"          # por cabeza, precio histórico vencido (como en G12)
COSTOS_OK = {"pct_transporte": "0.02", "pct_comisiones": "0.03", "pct_impuestos": "0.01"}
# Eventos de auditoría que son parte de una medición normal (no son el registro de un bloqueo ni de una exclusión)
TIPOS_MEDICION_PROPIOS = ("MEDICION_POSTERIOR", "MEDICION_CON_ESTIMACION", "MEDICION_SIN_VARIACION", "VARIACION_REGISTRADA")


@pytest.fixture(scope="module")
def env():
    e = Entorno(("admin", "ingeniero"))
    yield e
    e.cerrar()


def _nuevo(env):
    """Un run por caso: las categorías de peso comparten la especie sembrada y sus precios, y el presupuesto de 170 s es por run."""
    if env.inicio is not None:
        env.nuevo_run()


def _n(env, ida):
    return env.contar("mediciones_posteriores", ida)


def _estado_periodo(env, periodo):
    return uno(env.sql(f"SELECT estado::text FROM modulo6.periodos_contables WHERE id_periodo_contable = {int(periodo)}"))


def _ultimo_procesado(env) -> int:
    return int(uno(env.sql("SELECT coalesce(max(id_evento), 0) FROM modulo6.procesamientos_eventos_m02")) or 0)


def _procesamientos(env, desde: int = 0):
    """Registro de procesamiento de eventos de M06 posteriores a `desde` (el más reciente primero): [] si el evento no dejó registro."""
    return env.sql("SELECT id_evento, resultado::text AS resultado, detalle FROM modulo6.procesamientos_eventos_m02 "
                   f"WHERE id_evento > {int(desde)} ORDER BY id_evento DESC LIMIT 5")


def _dejar_sin_precio_vigente(env, esc):
    """Igual que G12: precio POR_CABEZA ya vencido (histórico) y la especie pasa a esa categoría: sin precio vigente, con último conocido."""
    env.procesar_eventos()
    env.precio(esc, HISTORICO, desde=hoy() - timedelta(days=3), hasta=hoy() - timedelta(days=1), categoria="POR_CABEZA")
    env.prep(env.call("PUT", f"/finanzas/configuracion/especies/{esc.id_especie}", "contador", json={
        "clasificacion": "PRODUCCION", "categoria_precio": "POR_CABEZA", "vida_util_meses": 60}), (200, 201), "especie con precio solo histórico")


# ------------------------------------------------------------------------------------------------------------------- 065
def test_TC_M06_065a_periodo_cerrado_no_admite_mediciones_retroactivas(env):
    _nuevo(env)
    env.presupuesto(90)
    esc = env.escenario(categoria="PESO_KG", precio=P)
    ida = env.base_medible(esc, "400")
    periodo = env.periodo(ida)
    r = env.cierre(periodo)
    if r.status not in (200, 201, 202):
        bloqueado(f"no se pudo cerrar el período {periodo} dentro del run: {r}")
    estado = _estado_periodo(env, periodo)
    if estado != "CERRADO":
        no_concluyente(f"el período {periodo} quedó en estado {estado}: no está cerrado, no se puede validar el bloqueo.")
    antes = _n(env, ida)
    en_periodo_antes = int(uno(env.sql(f"SELECT count(*) FROM modulo6.mediciones_posteriores WHERE id_periodo_contable = {int(periodo)} "
                                       f"AND id_activo_biologico = {int(ida)}")) or 0)
    desde = _ultimo_procesado(env)
    env.pesaje(ida, "450")                                              # evento de hoy, que cae en el período ya cerrado
    p = env.procesar_eventos()
    assert p.status < 500, p
    despues = _n(env, ida)
    nuevas = env.sql("SELECT id_periodo_contable AS periodo, origen_medicion::text AS origen FROM modulo6.mediciones_posteriores "
                     f"WHERE id_activo_biologico = {int(ida)} ORDER BY id_medicion_posterior DESC LIMIT {max(despues - antes, 1)}")
    obs(f"Período {periodo} CERRADO. Mediciones del activo antes/después del evento: {antes}/{despues}. "
        f"Mediciones nuevas (período, origen): {nuevas if despues > antes else 'ninguna'}. Procesamiento: {_procesamientos(env, desde)[:1] or 'sin registro'}")
    en_periodo = int(uno(env.sql(f"SELECT count(*) FROM modulo6.mediciones_posteriores WHERE id_periodo_contable = {int(periodo)} "
                                 f"AND id_activo_biologico = {int(ida)}")) or 0)
    assert en_periodo == en_periodo_antes, "no deben registrarse mediciones retroactivas en el período cerrado"
    assert despues == antes, ("el evento de un período cerrado debe bloquearse y no generar medición (RF-83 restricción 2, CU02 FA-04, ficha 065); "
                              f"se generaron {despues - antes} medición(es) nueva(s): {nuevas}")
    # INC-M06-312 (corregido por Desarrollo, #999): el evento en período cerrado queda MEDICION_PENDIENTE y genera alerta.
    pr = _procesamientos(env, desde)
    tipos = env.tipos_auditoria(ida)
    assert "MEDICION_PENDIENTE" in tipos or any("PENDIENTE" in str(x["resultado"]).upper() for x in pr), (
        f"INC-M06-312: el evento de un período cerrado debe quedar MEDICION_PENDIENTE; procesamiento {pr[:1]}, auditoría {tipos}")
    obs("El evento 'del período abierto' no se prueba: los eventos llevan la fecha de hoy y no se pueden fechar en otro período.")


def test_TC_M06_065b_el_intento_en_periodo_cerrado_queda_en_auditoria(env):
    """CU02 FA-04: el sistema bloquea, genera alerta y registra el intento en auditoría."""
    _nuevo(env)
    env.presupuesto(90)
    esc = env.escenario(categoria="PESO_KG", precio=P)
    ida = env.base_medible(esc, "400")
    periodo = env.periodo(ida)
    r = env.cierre(periodo)
    if r.status not in (200, 201, 202) or _estado_periodo(env, periodo) != "CERRADO":
        bloqueado(f"no se pudo cerrar el período {periodo} dentro del run: {r}")
    antes = env.tipos_auditoria(ida)
    env.pesaje(ida, "450")
    assert env.procesar_eventos().status < 500
    despues = env.tipos_auditoria(ida)
    nuevos = list(despues)
    for t in antes:
        if t in nuevos:
            nuevos.remove(t)
    obs(f"Eventos de auditoría nuevos tras el intento: {nuevos or 'ninguno'}")
    assert [t for t in nuevos if t not in TIPOS_MEDICION_PROPIOS], (
        "CU02 FA-04: el intento de medición sobre un período cerrado debe quedar registrado en auditoría (con alerta); "
        f"los eventos nuevos del activo fueron: {nuevos or 'ninguno'}")
    # INC-M06-312 (#999): la alerta es MEDICION_PENDIENTE.
    assert "MEDICION_PENDIENTE" in nuevos, f"INC-M06-312: el intento debe dejar la alerta MEDICION_PENDIENTE; eventos nuevos: {nuevos}"
    db = env.sql("SELECT count(*) AS n FROM modulo6.auditorias_financieras WHERE tipo_evento::text = 'MEDICION_PENDIENTE' "
                 f"AND id_activo_biologico = {int(ida)}")
    assert int(uno(db)) >= 1, f"base de datos: debe existir el evento MEDICION_PENDIENTE del activo {ida}: {db}"


# ------------------------------------------------------------------------------------------------------------------- 066
def _atender_estado(env, estado):
    """Prepara el activo en el estado pedido con un pesaje pendiente de procesar. Devuelve (escenario, id_activo)."""
    esc = env.escenario(categoria="PESO_KG", precio=P)
    if estado == "PENDIENTE_RECONOCIMIENTO":
        ida = env.activo(esc, origen="nacimiento", costo=None, soporte=None, peso_kg="400")      # registrado y sin confirmar
        env.pesaje(ida, "450")
        return esc, ida
    ida = env.base_medible(esc, "400")
    if estado == "ACTIVO":
        env.pesaje(ida, "450")
    elif estado == "INACTIVO":
        env.pesaje(ida, "450")                                      # M02 solo admite el evento mientras el activo está ACTIVO
        r = env.estado_activo(ida, "INACTIVO")
        assert r.status in (200, 201), f"precondición: M02 debe permitir pasar el activo a INACTIVO y respondió {r}"
    return esc, ida


@pytest.mark.parametrize("estado", ["INACTIVO", "PENDIENTE_RECONOCIMIENTO"])
def test_TC_M06_066_estado_no_elegible_no_se_mide(env, estado):
    _nuevo(env)
    env.presupuesto(70)
    esc, ida = _atender_estado(env, estado)
    antes_med, antes_aud = _n(env, ida), env.tipos_auditoria(ida)
    desde = _ultimo_procesado(env)
    assert env.procesar_eventos().status == 200
    despues_med, despues_aud = _n(env, ida), env.tipos_auditoria(ida)
    nuevos = list(despues_aud)
    for t in antes_aud:
        if t in nuevos:
            nuevos.remove(t)
    proc = _procesamientos(env, desde)[:1] or 'sin registro de procesamiento'
    obs(f"{estado}: mediciones {antes_med}->{despues_med}; auditoría nueva: {nuevos or 'ninguna'}; procesamiento: {proc}")
    fallos = []
    if despues_med != antes_med:
        fallos.append(f"un activo en estado {estado} no debe medirse y se generaron {despues_med - antes_med} medición(es)")
    if estado == "PENDIENTE_RECONOCIMIENTO":
        # Decisión de Daniela (13-nov): es una PREGUNTA para Análisis/líder, no un error. Un evento de un activo sin reconocimiento confirmado
        # no se excluye: M06 solo procesa activos con reconocimiento CONFIRMADO, así que el evento espera en la cola; lo que dice el RF-83 FA-07
        # y la ficha 066 (registrar la exclusión) no parece aplicar a este estado. Lo que sí se exige: que no se mida y que no haya error.
        obs("PREGUNTA (no es error): el evento de un activo PENDIENTE_RECONOCIMIENTO no deja registro de exclusión ni de procesamiento; "
            "se asume que espera en la cola hasta que se confirme el reconocimiento. RF-83 FA-07 y la ficha 066 piden registrar la exclusión: "
            "confirmar con Análisis/líder cuál es el comportamiento correcto.")
        assert not fallos, " | ".join(fallos)
        return
    # INC-M06-313 (corregido por Desarrollo, #1000): la exclusión se registra como MEDICION_EXCLUIDA.
    if "MEDICION_EXCLUIDA" not in nuevos:
        fallos.append("INC-M06-313: la exclusión debe quedar registrada como MEDICION_EXCLUIDA con su motivo en auditoría (RF-83 FA-07 / ficha 066) "
                      f"(eventos nuevos: {nuevos or 'ninguno'})")
    else:
        db = env.sql("SELECT count(*) AS n FROM modulo6.auditorias_financieras WHERE tipo_evento::text = 'MEDICION_EXCLUIDA' "
                     f"AND id_activo_biologico = {int(ida)}")
        if int(uno(db)) < 1:
            fallos.append(f"base de datos: no existe el evento MEDICION_EXCLUIDA del activo {ida}")
    assert not fallos, " | ".join(fallos)


def test_TC_M06_066_baja_ya_dada_no_se_mide_por_evento_ni_por_cierre(env):
    _nuevo(env)
    env.presupuesto(90)
    esc = env.escenario(categoria="PESO_KG", precio=P)
    ida = env.base_medible(esc, "400")
    env.prep(env.baja(ida, "perdida"), (200, 201), "baja del activo")
    assert env.procesar_eventos().status == 200
    base = _n(env, ida)                                              # lo que haya quedado al procesar la propia baja
    evento = env.call("POST", f"/activos-biologicos/{ida}/eventos/crecimiento", "admin", json={
        "tipo_medicion": "PESO", "valor_medicion": "450", "unidad_medida": "kg"})
    obs(f"Evento de crecimiento sobre un activo dado de baja (M02): HTTP {evento.status}")
    assert evento.status < 500, evento
    assert env.procesar_eventos().status == 200
    env.precio(esc, "21000.00", desde=hoy())
    periodo = env.periodo(ida)
    assert periodo, "no se pudo determinar el período contable del activo"
    cierre = env.cierre(periodo)
    obs(f"Cierre del período {periodo} con el activo dado de baja: HTTP {cierre.status}")
    assert _n(env, ida) == base, "el activo dado de baja no debe medirse ni por evento ni por cierre (RF-83 restricción 5, ficha 066)"


def test_TC_M06_066_control_activo_si_se_mide(env):
    _nuevo(env)
    env.presupuesto(60)
    esc, ida = _atender_estado(env, "ACTIVO")
    assert env.procesar_eventos().status == 200
    assert _n(env, ida) == 1, "el activo ACTIVO debe medirse (control del caso 066)"


# ------------------------------------------------------------------------------------------------------------------- 067
def test_TC_M06_067a_sin_precio_ni_historico_queda_pendiente_y_al_cargar_precio_el_reintento_crea_una_sola(env):
    _nuevo(env)
    env.presupuesto(90)
    esc = env.escenario(categoria="PESO_KG", precio=P)
    ida = env.base_medible(esc, "400")
    calculos = env.contar("calculos_valor_razonable", ida)
    valor_previo = dec(env.calculo(ida)["valor_neto"])
    # La especie pasa a una categoría en la que nunca tuvo precio (no se registra ninguno): sin precio vigente ni histórico y sin usar el costo.
    env.prep(env.call("PUT", f"/finanzas/configuracion/especies/{esc.id_especie}", "contador", json={
        "clasificacion": "PRODUCCION", "categoria_precio": "POR_CABEZA", "vida_util_meses": 60}), (200, 201), "especie sin precio en la categoría vigente")
    env.pesaje(ida, "450")
    assert env.procesar_eventos().status == 200
    n1 = _n(env, ida)
    if n1 and env.mediciones(ida)[-1]["tiene_valor_estimado"] is True:
        no_concluyente("el backend tomó el precio por kg anterior como histórico, así que la especie no queda sin ningún precio; "
                       f"no se pudo preparar el escenario «sin precio ni histórico»: {env.mediciones(ida)[-1]}")
    assert n1 == 0, f"RF-83 v1.2: sin precio ni histórico no debe crearse medición (tampoco con el costo): {env.mediciones(ida)}"
    assert env.contar("calculos_valor_razonable", ida) == calculos, "no debe quedar cálculo parcial"
    assert dec(env.calculo(ida)["valor_neto"]) == valor_previo, "el valor del activo no debe cambiar mientras la medición está bloqueada"
    assert "MEDICION_PENDIENTE" in env.tipos_auditoria(ida), env.tipos_auditoria(ida)
    env.precio(esc, "2100000.00", desde=hoy(), categoria="POR_CABEZA")             # el Administrador/Contador carga el precio
    assert env.procesar_eventos().status == 200
    if _n(env, ida) == n1:
        env.pesaje(ida, "460")
        assert env.procesar_eventos().status == 200
    n2 = _n(env, ida)
    assert n2 == n1 + 1, f"tras cargar el precio el reintento debe crear una sola medición (antes {n1}, después {n2})"
    assert env.mediciones(ida)[-1]["tiene_valor_estimado"] is False, "con precio vigente la medición no debe ir marcada como estimada"


def test_TC_M06_067b_sin_valor_utilizable_no_deja_medicion_parcial_y_se_recupera(env):
    _nuevo(env)
    env.presupuesto(80)
    esc = env.escenario(categoria="PESO_KG", precio=P)
    ida = env.base_medible(esc, "400")
    calculos = env.contar("calculos_valor_razonable", ida)
    env.prep(env.call("PUT", f"/finanzas/configuracion/costos-venta/{esc.id_especie}", "contador",
                      json={"pct_transporte": "0.5", "pct_comisiones": "0.4", "pct_impuestos": "0.1"}), (200, 201), "costos de venta al 100 %")
    env.pesaje(ida, "450")
    assert env.procesar_eventos().status == 200
    assert _n(env, ida) == 0 and env.contar("calculos_valor_razonable", ida) == calculos, "no debe quedar medición ni cálculo parcial"
    assert "MEDICION_PENDIENTE" in env.tipos_auditoria(ida), env.tipos_auditoria(ida)
    env.prep(env.call("PUT", f"/finanzas/configuracion/costos-venta/{esc.id_especie}", "contador", json=COSTOS_OK), (200, 201), "restaurar costos")
    assert env.procesar_eventos().status == 200
    if _n(env, ida) == 0:
        env.pesaje(ida, "460")
        assert env.procesar_eventos().status == 200
    assert _n(env, ida) == 1, f"tras corregir, el reintento debe crear una sola medición (hay {_n(env, ida)})"


# ------------------------------------------------------------------------------------------------------------------- 068
def test_TC_M06_068_invariante_de_suma_en_las_mediciones_del_run(env):
    _nuevo(env)
    env.presupuesto(120)
    esc = env.escenario(categoria="PESO_KG", precio=P)
    a = env.base_medible(esc, "400")
    c = env.base_medible(esc, "400")
    env.medir(esc, a, "21000.00", "450")                              # por evento (precio y transformación)
    env.medir(esc, a, "19000.00", "430")                              # por evento (baja de precio y de peso)
    _dejar_sin_precio_vigente(env, esc)                               # estimación (último precio histórico)
    env.pesaje(c, "380")
    env.procesar_eventos()
    periodo = env.periodo(a)
    r = env.cierre(periodo) if periodo else None                      # por cierre de período (RF-87)
    ids = f"{int(a)}, {int(c)}"
    filas = env.sql("SELECT id_medicion_posterior AS id, id_activo_biologico AS ida, origen_medicion::text AS origen, "
                    "tiene_valor_estimado AS est, (ganancia_perdida_transformacion + ganancia_perdida_precio_mercado "
                    "- (valor_razonable_actual - valor_razonable_anterior))::text AS dif_componentes, "
                    "(variacion_total - (valor_razonable_actual - valor_razonable_anterior))::text AS dif_total "
                    f"FROM modulo6.mediciones_posteriores WHERE id_activo_biologico IN ({ids}) ORDER BY id_medicion_posterior")
    origenes = sorted({f["origen"] for f in filas})
    obs(f"Mediciones del run: {len(filas)} (orígenes {origenes}; estimadas {sum(1 for f in filas if f['est'])}); cierre: HTTP {r.status if r else 'no se ejecutó'}.")
    assert len(filas) >= 3, f"no se crearon mediciones suficientes en el run ({len(filas)}); orígenes {origenes}"
    malas = [f for f in filas if dec(f["dif_componentes"]) != 0 or dec(f["dif_total"]) != 0]
    assert not malas, f"mediciones cuya suma de efectos no es igual a actual - anterior (diferencia debe ser 0,0000): {malas}"


# ------------------------------------------------------------------------------------------------------------------- 069
def test_TC_M06_069_eventos_invalidos_se_rechazan_sin_5xx_ni_mediciones(env):
    _nuevo(env)
    env.presupuesto(60)
    esc = env.escenario(categoria="PESO_KG", precio=P)
    ida = env.base_medible(esc, "400")
    base = f"/activos-biologicos/{ida}/eventos/crecimiento"
    valido = {"tipo_medicion": "PESO", "valor_medicion": "450", "unidad_medida": "kg"}
    peticiones = {
        "tipo de evento fuera de catálogo (ENFERMEDAD)": (base, {**valido, "tipo_medicion": "ENFERMEDAD"}),
        "tipo en minúscula (crecimiento)": (base, {**valido, "tipo_medicion": "crecimiento"}),
        "dato obligatorio ausente (sin valor_medicion)": (base, {k: v for k, v in valido.items() if k != "valor_medicion"}),
        "activo inexistente (999999999)": ("/activos-biologicos/999999999/eventos/crecimiento", valido),
        "id de activo 'abc'": ("/activos-biologicos/abc/eventos/crecimiento", valido),
    }
    fallos = []
    for nombre, (ruta, cuerpo) in peticiones.items():
        r = env.call("POST", ruta, "admin", json=cuerpo)
        obs(f"{nombre}: HTTP {r.status} {str(r.text)[:140]}")
        if r.status >= 500:
            fallos.append(f"{nombre}: error 5xx ({r.status})")
        elif not 400 <= r.status < 500:
            fallos.append(f"{nombre}: se esperaba un rechazo 4xx y respondió {r.status}")
    p = env.call("POST", "/finanzas/eventos/procesar", "contador", json={"tipo_evento": "ENFERMEDAD"})
    obs(f"POST /finanzas/eventos/procesar con un cuerpo con tipo_evento 'ENFERMEDAD' (M06 no recibe eventos por API; 'id_evento ausente' no aplica): HTTP {p.status}")
    if p.status >= 500:
        fallos.append(f"procesar eventos con cuerpo inesperado: error 5xx ({p.status})")
    assert env.procesar_eventos().status == 200
    if _n(env, ida) != 0:
        fallos.append(f"se creó una medición ({_n(env, ida)}) a partir de peticiones inválidas")
    assert not fallos, " | ".join(fallos)


# ------------------------------------------------------------------------------------------------------------------- 070
def test_TC_M06_070_cierre_inexistente_malformado_o_repetido_se_rechaza(env):
    _nuevo(env)
    env.presupuesto(90)
    env.contador()                                                    # las peticiones inválidas deben ir con el rol Contador (si no, el 403 es de permisos)
    cuerpo = {"autorizar_exclusiones": True, "incluir_activos_sin_precio": True}
    inexistente = env.call("POST", "/finanzas/periodos/999999999/cierre", "contador", json=cuerpo)
    malformado = env.call("POST", "/finanzas/periodos/abc/cierre", "contador", json=cuerpo)
    obs(f"período inexistente: HTTP {inexistente.status}; 'abc': HTTP {malformado.status}")
    fallos = []
    for nombre, r in (("período inexistente", inexistente), ("período 'abc'", malformado)):
        if not 400 <= r.status < 500:
            fallos.append(f"{nombre}: se esperaba un rechazo 4xx y respondió {r.status}")
    esc = env.escenario(categoria="PESO_KG", precio=P)
    ida = env.base_medible(esc, "400")
    env.precio(esc, "21000.00", desde=hoy())
    periodo = env.periodo(ida)
    primero = env.cierre(periodo)
    if primero.status not in (200, 201, 202):
        bloqueado(f"no se pudo cerrar el período {periodo} dentro del run: {primero}")
    total = f"SELECT count(*) FROM modulo6.mediciones_posteriores WHERE id_periodo_contable = {int(periodo)}"
    n1 = int(uno(env.sql(total)) or 0)
    segundo = env.cierre(periodo)
    n2 = int(uno(env.sql(total)) or 0)
    obs(f"Primer cierre: HTTP {primero.status} ({n1} mediciones en el período). Segundo cierre del mismo período: HTTP {segundo.status} ({n2}).")
    if not 400 <= segundo.status < 500:
        fallos.append(f"período ya procesado: se esperaba un rechazo 4xx (RF-87: 409 PERIODO_CERRADO) y respondió {segundo.status}")
    if n2 != n1:
        fallos.append(f"el período repetido generó mediciones duplicadas ({n1} -> {n2})")
    assert not fallos, " | ".join(fallos)
