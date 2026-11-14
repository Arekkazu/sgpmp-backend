# | Fecha      | Nombre           | Que se hizo                                                              |
# |------------|------------------|--------------------------------------------------------------------------|
# | 2026-11-07 | Daniela Castillo | M06 RF-82: script del grupo TC-M06-G07 (pytest + sandbox, rol Contador) |
# | 2026-11-08 | Daniela Castillo | M06 RF-82: G07 alineado con la ficha (bandeja, revisión, mensajes, REVERTIDO, registro de intentos no autorizados) |
# | 2026-11-12 | Daniela Castillo | M06 reprueba V2.0 (RF-83 v1.2, RF-84 v1.1, RF-85 v1.2, RF-88 v2.0): el reporte HTML pasa a llamarse reporte-TC-M06-G07-V2.0.html |
# | 2026-11-13 | Daniela Castillo | M06 RF-82: 036 con Administrador con todos los permisos (líder y Análisis, 13-nov) y rol Auditor nuevo: se retira el Administrador de los roles no autorizados, se agrega el Auditor y 036 administrador revierte
# | 2026-11-13 | Daniela Castillo | M06 RF-82: 031c nuevo: el Auditor ve el reconocimiento original y la reversión (Postcondiciones 6 b)
"""
TC-M06-G07 - Reversión del reconocimiento inicial: asiento espejo, motivo, bloqueos por dependencias y autorización.
RF-82 (CU01).   Casos: TC-M06-031 a TC-M06-038.

Operación: POST /finanzas/reconocimientos/{id_activo}/reversion {"motivo_reversion": "..."} (reconocimiento_inicial·Desactivar:
solo Contador). Dependencias: medición posterior y variación (RF-83/RF-86) se crean dentro del run con un precio nuevo + un evento de
crecimiento de M02 + POST /finanzas/eventos/procesar; el período cerrado (RF-87) con POST /finanzas/periodos/{id}/cierre (si el cierre
no puede completarse en el sandbox el caso 035 queda BLOQUEADO con el motivo).

V2.0 (13-nov): el Administrador tiene todos los permisos (líder y Análisis): puede revertir (036 administrador); 036 por rol no autorizado ahora cubre Productor, Veterinario,
Auditor (rol nuevo) y sin token.

Motivo: el DTO exige min_length=20 (400 si es menor); 20 espacios pasan el DTO y el caso de uso los rechaza al recortar (los espacios NO cuentan).

Cómo correrlo (necesita también QA_CONTRASENA_PRODUCTOR, QA_CONTRASENA_VETERINARIO y QA_CONTRASENA_AUDITOR):
    python -m pytest "tests/Test_Testing/Test_Modulo6/RF-82/TC-M06-G07/TC-M06-G07.py" -v -rs --noconftest -s --html="tests/Test_Testing/Test_Modulo6/RF-82/TC-M06-G07/reporte-TC-M06-G07-V2.0.html" --self-contained-html
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

import requests

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from m06_lib import *  # noqa: F401,F403,E402

MOTIVO = "Error en la captura del origen del activo, se corrige"          # > 20 caracteres


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


def _rechazo(r):
    """La ficha dice «rechazo» sin código exacto: vale cualquier 4xx (el 400 VAL_ENTRADA equivale al 422)."""
    return 400 <= r.status < 500


def _n(env, ida, estado):
    return env.contar("reconocimientos_iniciales", ida, f"AND estado = '{estado}'")


def _accesos_no_autorizados(env) -> list[dict]:
    """Eventos ACCESO_NO_AUTORIZADO del log de auditoría de M06 (API, Contador, los 500 más recientes). El 403 de RBAC guarda el id del activo
    en el payload y no en la columna id_activo_biologico (la envía alguien sin permiso y puede no existir), por eso no se filtra por activo."""
    r = env.call("GET", "/finanzas/auditoria", "contador", params={"tipo_evento": "ACCESO_NO_AUTORIZADO", "tamano": 500, "orden": "DESC"})
    assert r.status == 200, f"GET /finanzas/auditoria respondió {r}"
    return lista_de(r.data, "eventos")


def _id_activo_del_evento(ev: dict):
    p = ev.get("resumen_payload")
    if isinstance(p, str):
        try:
            p = json.loads(p)
        except ValueError:
            m = re.search(r'"?id_activo_biologico"?\W+(\d+)', p)
            return int(m.group(1)) if m else None
    return p.get("id_activo_biologico") if isinstance(p, dict) else None


def _en_bandeja(env, ida) -> bool:
    b = env.call("GET", "/finanzas/reconocimientos/propuestas", "contador")
    assert b.status == 200, b
    return ida in {x.get("id_activo_biologico") for x in lista_de(b.data, "propuestas")}


def _reconocido(env, esc, **kw):
    kw.setdefault("origen", "compra")
    if kw["origen"] in ("compra", "donacion"):
        kw.setdefault("costo", "2500000.0000")
        kw.setdefault("soporte", "Factura QA-M06-G07")
    else:
        kw.setdefault("costo", None)
        kw.setdefault("soporte", None)
    return env.reconocer(esc, **kw)


def test_TC_M06_031_reversion_sin_dependencias_asiento_espejo(env, esc):
    env.presupuesto(40)
    ida, conf = _reconocido(env, esc)
    original = lineas_de(env.historial(ida))
    r = env.revertir(ida, "x" * 40)
    assert r.status in (200, 201), r
    assert r.get("id_reconocimiento_revertido") == conf.get("id_reconocimiento_inicial"), "debe apuntar al reconocimiento original"
    assert r.get("lineas_espejo"), "falta el asiento espejo"
    lineas = lineas_de(env.historial(ida))
    espejos = [l for l in lineas if l.get("es_reverso")]
    originales = [l for l in lineas if not l.get("es_reverso")]
    assert len(originales) == len(original) and len(espejos) == len(original), f"líneas: {lineas}"
    for o, e in zip(originales, espejos):
        assert dec(o["valor"]) == dec(e["valor"]), (o, e)
        if o.get("estado") == "REGISTRADA":
            assert (e["cuenta_debito"], e["cuenta_credito"]) == (o["cuenta_credito"], o["cuenta_debito"]), "el espejo debe invertir el par"
    # El activo vuelve a PENDIENTE_RECONOCIMIENTO: vuelve a tener propuesta confirmable y no hay reconocimiento vigente.
    assert env.propuesta(ida).get("es_confirmable") is True
    assert _n(env, ida, "CONFIRMADO") == 0 and _n(env, ida, "REVERTIDO") == 1
    # id_reconocimiento_revertido apunta al original en el registro de la reversión, por el mismo monto del reconocimiento.
    # (La tabla revisiones_reconocimiento tiene RLS y el SQL del sandbox no la ve: se comprueba por la API.)
    orig = [x for x in (env.historial(ida).get("reconocimientos") or []) if x.get("id_reconocimiento_inicial") == conf.get("id_reconocimiento_inicial")]
    assert len(orig) == 1 and orig[0].get("estado") == "REVERTIDO", f"el reconocimiento original debe quedar REVERTIDO: {orig}"
    assert (orig[0].get("justificacion_reversion") or "").strip() and orig[0].get("fecha_reversion"), f"falta el motivo o la fecha de la reversión: {orig}"
    # El monto de la reversión (revisiones_reconocimiento.monto_revision) se lee del evento RECONOCIMIENTO_REVERTIDO del log (monto_afectado):
    # debe ser el valor reconocido (el asiento solo lleva la diferencia sobre el costo, por eso no se compara con el espejo).
    ev = env.auditoria(ida, "RECONOCIMIENTO_REVERTIDO")
    assert len(ev) == 1, f"debe existir un evento RECONOCIMIENTO_REVERTIDO en el log: {ev}"
    assert dec(ev[0].get("monto_afectado")) == dec(conf.get("valor_inicial")), f"monto de la reversión {ev[0].get('monto_afectado')} != valor reconocido {conf.get('valor_inicial')}"
    assert sum(dec(e["valor"]) for e in espejos) == sum(dec(o["valor"]) for o in originales), "el asiento espejo debe ser por el mismo monto"
    # PENDIENTE_RECONOCIMIENTO: el activo vuelve a la bandeja de propuestas (igual que antes de confirmar).
    assert _en_bandeja(env, ida), "tras la reversión el activo debe volver a PENDIENTE_RECONOCIMIENTO (bandeja de propuestas)"
    # El original sigue visible junto al espejo (CA-13): el historial conserva ambos asientos.
    assert len(lineas_de(env.historial(ida))) == 2 * len(original)


@pytest.mark.parametrize("motivo,acepta", [
    ("", False), (" " * 20, False), ("a" * 19, False), ("b" * 20, True), ("c" * 21, True)],
    ids=["vacio", "20_espacios", "19_caracteres", "20_caracteres", "21_caracteres"])
def test_TC_M06_032_limites_del_motivo(env, esc, motivo, acepta):
    env.presupuesto(30)
    ida, _ = _reconocido(env, esc)
    r = env.revertir(ida, motivo)
    if acepta:
        assert r.status in (200, 201), r
        assert _n(env, ida, "REVERTIDO") == 1 and _n(env, ida, "CONFIRMADO") == 0, "la reversión aceptada debe dejar el reconocimiento REVERTIDO"
    else:
        assert _rechazo(r), f"el motivo {motivo!r} debía rechazarse: {r}"
        assert "20" in r.text, f"el rechazo debe indicar el mínimo exigido (20 caracteres): {r.text[:300]}"
        assert _n(env, ida, "CONFIRMADO") == 1 and _n(env, ida, "REVERTIDO") == 0, "el rechazo no debe alterar el reconocimiento"
        assert not [l for l in lineas_de(env.historial(ida)) if l.get("es_reverso")], "el rechazo no debe generar asiento espejo"


def _reconocimiento_con_medicion(env):
    """Un pesaje (RF-83) exige que el activo tenga una fase activa de un ciclo productivo (M02 responde SIN_FASE_ACTIVA si no):
    por eso se usa la especie productiva sembrada de TEST (con ciclo y categoría PESO_KG), se asigna la fase y se mide con un
    segundo pesaje mayor."""
    esc = env.escenario_producto(precio_activo="20000.00")
    r = env.prep(env.activo_r(esc, origen="compra", costo="2500000.0000", soporte="Factura QA-M06-G07"), (200, 201), "registrar activo RF-33")
    ida = r.get("id_activo_biologico")
    f = env.call("POST", f"/activos-biologicos/{ida}/fases", "admin", json={"id_ciclo_productiva": ID_CICLO_PRODUCTIVO})
    obs(f"asignar fase del ciclo {ID_CICLO_PRODUCTIVO} al activo: HTTP {f.status} {f.err or ''}")
    env.pesaje(ida, "400")
    env.prep(env.confirmar(ida), (200, 201), "confirmar el reconocimiento inicial")
    env.procesar_eventos()                                   # vacía la cola: los eventos previos al reconocimiento no miden nada
    pr = env.medir(esc, ida, None, kg="450")                 # segundo pesaje (450 kg) y procesamiento
    assert pr.status == 200, pr
    if not env.contar("mediciones_posteriores", ida):
        no_verificable(f"no se generó la medición posterior dentro del run (procesar eventos: {pr.data}); depende del procesamiento de M02 en el sandbox.")
    return ida


@pytest.mark.parametrize("dependencia", ["medicion_posterior_RF83", "variacion_RF86"])
def test_TC_M06_033_034_reversion_bloqueada_por_dependencias(env, dependencia):
    _asegurar(env, 120)
    env.presupuesto(70)
    ida = _reconocimiento_con_medicion(env)
    if dependencia == "variacion_RF86":
        h = env.historial(ida)
        variaciones = env.variaciones(ida)
        lineas_var = [ln for ln in lineas_de(h) if ln.get("tabla_origen") == "variaciones_valor_razonable"]
        # Si la medición no produjo variación, el caso no puede probar la dependencia: queda ROJO con el detalle (no se omite).
        assert variaciones or lineas_var, ("la medición posterior no generó ninguna variación RF-86 (ni por la API de variaciones del período ni "
                                          f"líneas de asiento de origen variaciones_valor_razonable); mediciones del activo: {h.get('mediciones')}")
    r = env.revertir(ida, MOTIVO)
    assert _rechazo(r), f"la reversión debía rechazarse: {r}"
    assert r.err == "REVERSION_BLOQUEADA", f"el código de error debía ser REVERSION_BLOQUEADA: {r}"
    termino = "medición" if dependencia == "medicion_posterior_RF83" else "variación"
    assert termino in r.text.lower() and "dependientes" in r.text.lower(), \
        f"el mensaje debe indicar la dependencia ({termino}): {r.text[:300]}"
    assert _n(env, ida, "CONFIRMADO") == 1 and _n(env, ida, "REVERTIDO") == 0, "el reconocimiento debe seguir vigente"
    assert not [l for l in lineas_de(env.historial(ida)) if l.get("es_reverso")], "no debe haber asiento espejo"
    ev = env.auditoria(ida, "REVERSION_BLOQUEADA")
    assert ev, "RF-94 debe registrar REVERSION_BLOQUEADA"
    assert str(ev[0].get("severidad")).upper() == "WARNING", f"RF-94 debe registrar REVERSION_BLOQUEADA con severidad WARNING: {ev[0]}"
    tipo = "MEDICION_POSTERIOR" if dependencia == "medicion_posterior_RF83" else "VARIACION"
    assert tipo in str(ev[0]), f"el evento de RF-94 debe indicar la dependencia ({tipo}): {ev[0]}"


def test_TC_M06_035_reversion_bloqueada_por_periodo_cerrado(env):
    _asegurar(env, 130)
    env.presupuesto(80)
    esc = env.escenario(categoria="POR_CABEZA", precio="8000000.00")
    ida, conf = _reconocido(env, esc)
    id_periodo = conf.get("id_periodo_contable")
    try:
        cierre = env.call("POST", f"/finanzas/periodos/{id_periodo}/cierre", "contador",
                          json={"autorizar_exclusiones": True, "incluir_activos_sin_precio": True})
    except requests.exceptions.RequestException as exc:
        no_concluyente(f"el cierre del período no respondió a tiempo dentro del sandbox: {exc}")
    if cierre.status not in (200, 201, 202):
        bloqueado(f"no se pudo cerrar el período {id_periodo} dentro del run: {cierre}")
    r = env.revertir(ida, MOTIVO)
    assert _rechazo(r) and r.err == "REVERSION_BLOQUEADA", f"período cerrado: la reversión debía rechazarse con REVERSION_BLOQUEADA: {r}"
    assert "cierre" in r.text.lower(), f"el mensaje debe indicar el cierre del período como dependencia: {r.text[:300]}"
    assert _n(env, ida, "CONFIRMADO") == 1 and _n(env, ida, "REVERTIDO") == 0, "el reconocimiento debe quedar sin cambios"
    ev = env.auditoria(ida, "REVERSION_BLOQUEADA")
    assert ev, "RF-94 debe registrar REVERSION_BLOQUEADA"
    assert str(ev[0].get("severidad")).upper() == "WARNING", f"la severidad debe ser WARNING: {ev[0]}"


@pytest.mark.parametrize("rol", ["productor", "veterinario", "auditor", "sin_token"])
def test_TC_M06_036_reversion_por_rol_no_autorizado(env, esc, rol):
    env.presupuesto(30)
    ida, _ = _reconocido(env, esc)
    r = env.call("POST", f"/finanzas/reconocimientos/{ida}/reversion", None if rol == "sin_token" else rol, json={"motivo_reversion": MOTIVO})
    assert r.status == (401 if rol == "sin_token" else 403), f"[{rol}] {r}"
    assert _n(env, ida, "CONFIRMADO") == 1 and _n(env, ida, "REVERTIDO") == 0, "el reconocimiento no debe cambiar"
    assert not [l for l in lineas_de(env.historial(ida)) if l.get("es_reverso")], "no debe haber asiento espejo"


@pytest.mark.parametrize("rol", ["productor", "veterinario", "auditor", "sin_token"])
def test_TC_M06_036_cada_intento_no_autorizado_queda_registrado(env, esc, rol):
    """Ficha 036: «cada intento queda registrado». RNF-82-05 pide lo mismo para cualquier rol no autorizado.
    Sin token (401) NO aplica a M06 (criterio de Daniela, 8-nov): lo rechaza la autenticación de M01 antes de llegar al módulo."""
    if rol == "sin_token":
        pytest.skip("NO APLICA: sin token la petición no pasa la autenticación de M01 y no llega a M06 (no es «otro rol»); el 401 se verifica en la prueba de códigos.")
    env.presupuesto(30)
    ida, _ = _reconocido(env, esc)
    antes = _accesos_no_autorizados(env)
    r = env.call("POST", f"/finanzas/reconocimientos/{ida}/reversion", None if rol == "sin_token" else rol, json={"motivo_reversion": MOTIVO})
    assert r.status == (401 if rol == "sin_token" else 403), f"[{rol}] {r}"
    despues = _accesos_no_autorizados(env)
    nuevos = [e for e in despues if e not in antes]
    del_activo = [e for e in nuevos if _id_activo_del_evento(e) == ida]
    assert del_activo, (f"[{rol}] el intento de reversión no autorizado (HTTP {r.status}) no dejó ningún evento ACCESO_NO_AUTORIZADO del activo {ida} "
                        f"en el log de auditoría de M06 (eventos ACCESO_NO_AUTORIZADO antes {len(antes)}, después {len(despues)}, nuevos {len(nuevos)}: {nuevos[:3]})")


def test_TC_M06_037_reversion_de_reconocimiento_ya_revertido_o_inexistente(env, esc):
    env.presupuesto(40)
    ida, _ = _reconocido(env, esc)
    assert env.revertir(ida, MOTIVO).status in (200, 201)
    n = len(lineas_de(env.historial(ida)))
    r2 = env.revertir(ida, MOTIVO)
    assert _rechazo(r2), f"segundo intento: debía rechazarse: {r2}"
    assert "reconocimiento" in r2.text.lower() and "vigente" in r2.text.lower(), f"mensaje poco claro (sin reconocimiento vigente): {r2.text[:300]}"
    nunca = env.activo(esc, origen="compra", costo="2500000.0000", soporte="Factura QA-M06-037")
    r3 = env.revertir(nunca, MOTIVO)
    assert _rechazo(r3), f"activo sin reconocimiento: debía rechazarse: {r3}"
    assert "reconocimiento" in r3.text.lower() and "vigente" in r3.text.lower(), f"mensaje poco claro (sin reconocimiento vigente): {r3.text[:300]}"
    obs(f"códigos obtenidos: ya revertido {r2.status} {r2.err}; sin reconocimiento {r3.status} {r3.err}")
    assert len(lineas_de(env.historial(ida))) == n, "no deben crearse asientos adicionales"


def test_TC_M06_038_nuevo_reconocimiento_tras_la_reversion(env, esc):
    env.presupuesto(40)
    ida, primero = _reconocido(env, esc)
    assert env.revertir(ida, MOTIVO).status in (200, 201)
    p = env.propuesta(ida)
    assert p.get("es_confirmable") is True and str(p.get("fecha_reconocimiento"))[:10] == str(hoy()), p.data
    segundo = env.confirmar(ida)
    assert segundo.status == 201, segundo
    assert segundo.get("id_reconocimiento_inicial") != primero.get("id_reconocimiento_inicial")
    assert str(segundo.get("fecha_reconocimiento"))[:10] == str(hoy()), f"el nuevo reconocimiento debe quedar a la fecha del día: {segundo.data}"
    assert dec(segundo.get("valor_inicial")) == dec(primero.get("valor_inicial")), "mismo precio vigente: el valor debe ser el de hoy (igual al primero)"
    assert _n(env, ida, "CONFIRMADO") == 1, "solo un reconocimiento vigente"
    assert _n(env, ida, "REVERTIDO") == 1, "el original debe seguir consultable como revertido"
    assert env.contar("reconocimientos_iniciales", ida) == 2


def test_TC_M06_036_administrador_si_puede_revertir(env, esc):
    """V2.0 (13-nov): el líder y Análisis definieron que el Administrador tiene todos los permisos del módulo: la reversión se acepta."""
    env.presupuesto(30)
    ida, _ = _reconocido(env, esc)
    r = env.call("POST", f"/finanzas/reconocimientos/{ida}/reversion", "admin", json={"motivo_reversion": MOTIVO})
    assert r.status in (200, 201), f"[admin] la reversión debía aceptarse (todos los permisos): {r}"
    assert _n(env, ida, "REVERTIDO") == 1 and _n(env, ida, "CONFIRMADO") == 0, "la reversión aceptada debe dejar el reconocimiento REVERTIDO"


def test_TC_M06_031c_el_auditor_ve_el_original_y_la_reversion(env, esc):
    """RF-82 Postcondiciones 6 b: tras la reversión, el reconocimiento original y su reversión son visibles para el Contador y el Auditor
    (CU01 FA-08: «ambos registros permanecen visibles en el historial del activo»). Rol Auditor nuevo (13-nov).
    Se exige lo que dice el RF: el reconocimiento original (REVERTIDO, con motivo y fecha) visible para el Auditor. Las líneas del asiento NO se
    exigen: la RLS de `lineas_asiento_nic41` (rls_modulo_06) deja a los lectores ver solo períodos cerrados; se anota lo que ve el Auditor frente al
    Contador. Si Análisis define que el Auditor ve los asientos de períodos abiertos, este caso pasa a exigirlas."""
    env.presupuesto(40)
    ida, conf = _reconocido(env, esc)
    r = env.revertir(ida, MOTIVO)
    assert r.status in (200, 201), f"precondición: la reversión del Contador debía aceptarse: {r}"
    h = env.call("GET", f"/finanzas/activos/{ida}", "auditor")
    assert h.status == 200, f"[auditor] consultar el historial del activo: esperado 200 (RF-82 Postcondiciones 6 b), recibido {h}"
    recs = (h.data or {}).get("reconocimientos") or []
    assert recs, f"[auditor] el reconocimiento original (revertido) debe seguir visible en el historial: {h.data}"
    orig = [x for x in recs if x.get("id_reconocimiento_inicial") == conf.get("id_reconocimiento_inicial")] or recs
    assert orig[0].get("estado") == "REVERTIDO", f"[auditor] el original debe verse como REVERTIDO: {orig[0]}"
    assert orig[0].get("justificacion_reversion") and orig[0].get("fecha_reversion"), f"[auditor] el original debe mostrar motivo y fecha de la reversión: {orig[0]}"
    l_aud = lineas_de(h.data or {})
    l_con = lineas_de(env.historial(ida))
    obs(f"líneas del asiento visibles en el historial: Auditor {len(l_aud)}, Contador {len(l_con)} "
        f"(la RLS de lineas_asiento_nic41 solo muestra a los lectores las de períodos cerrados).")
