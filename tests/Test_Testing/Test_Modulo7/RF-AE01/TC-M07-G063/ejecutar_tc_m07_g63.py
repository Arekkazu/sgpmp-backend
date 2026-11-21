# | Fecha      | Nombre | Que se hizo |
# |------------|--------|-------------|
# | 2026-11-19 | usuario-git | TC-M07-G063 (RF-AE01 / RF-AE02): runner de G5.1 y G5.3 contra TEST (auditoria RF-102) + pytest local de G5.1 a G5.3. |
"""TC-M07-G063 — Registro en la auditoria de las consultas AAEF y del ciclo de vida del Anexo.  Responsable: Maria Jose.

Subcasos:
  G5.1 (Alta)  Una consulta exitosa y una fallida dejan su registro en RF-102 con usuario, titular, rango, version, hash y
               resultado.                                                                          [TEST, solo lectura + pytest]
  G5.2 (Media) Caida de la auditoria durante la consulta: la consulta responde 200 y la falta del registro queda a la vista.
                                                                                                   [pytest]
  G5.3 (Alta)  Ciclo de vida del Anexo: creacion, validacion automatica, aprobacion interna, evidencia y aprobacion quedan en
               la auditoria con usuario y fecha; la evidencia queda asociada a la version del Anexo.  [pytest + TEST sandbox]

G5.1 deja en la auditoria de TEST dos eventos reales (una consulta exitosa y una rechazada), como cualquier consulta normal: no
hay forma de probar que se registran sin registrarlos. Son 2 consultas que cuentan contra el limite de 5 por minuto del cliente.

G5.3 en TEST escribe (registra, pasa a revision y aprueba un Anexo de prueba), asi que corre DENTRO de un run del sandbox
(cabeceras X-Test-Run-Id y X-Sandbox-Secret) y el run se cierra SIEMPRE con DELETE /test-control/runs/{id} (rollback). Antes de
escribir se comprueba el eco X-Test-Run-Id; si no llega, no se escribe nada. Tras el rollback se compara la lista de Anexos con la
de antes. Sin QA_SANDBOX_SECRET esa parte queda BLOQUEADO.

Los secretos van por variables de entorno; NUNCA se guardan en el reporte ni en el repo:
  QA_SECRET_AAEF           (G5.1) client_secret de QA_M07_AAEF (D10)
  QA_CORREO_CONTADOR       default contador@gmail.com (D03)
  QA_CORREO_ADMIN          default admin.rol@gmail.com;  QA_CONTRASENA_ADMIN  (G5.1 y G5.3) lee la auditoria (permiso de auditoria)
  QA_SANDBOX_SECRET        (G5.3 en TEST) X-Sandbox-Secret
  QA_CONTRASENA_CONTADOR   (G5.3) contrasena web del contador; se prueba primero con el contador y, si no tiene el permiso de
                           una operacion, con el administrador
  QA_NIT                   default 901444215 (D01)
  QA_BASE_URL              default https://api.inmero.co/api-sgpmp-test

Lo que no se pueda ejecutar queda BLOQUEADO con el motivo; nunca se da por aprobado sin ejecutarse.

Desde la raiz de sgpmp-backend (cada secreto con read -s + export, sin pegarlo en el chat):
    .venv/bin/python tests/Test_Testing/Test_Modulo7/RF-AE01/TC-M07-G063/ejecutar_tc_m07_g63.py
"""
from __future__ import annotations

import html
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

CASO, RF, RESPONSABLE = "TC-M07-G063", "RF-AE01 / RF-AE02", "Maria Jose"
CARPETA = Path(__file__).resolve().parent
RAIZ = CARPETA.parents[4]  # sgpmp-backend
RESULTADO = CARPETA / "Resultado"

BASE = os.environ.get("QA_BASE_URL", "https://api.inmero.co/api-sgpmp-test").rstrip("/")
NIT = os.environ.get("QA_NIT", "901444215")
CORREO = os.environ.get("QA_CORREO_CONTADOR", "contador@gmail.com")
CORREO_ADMIN = os.environ.get("QA_CORREO_ADMIN", "admin.rol@gmail.com")
CLIENT_ID = os.environ.get("QA_CLIENT_ID_AAEF", "qa-m07-aaef")
SANDBOX = os.environ.get("QA_SANDBOX_SECRET", "")
SECRETOS: list[str] = []
ALERTAS: list[str] = []


def ahora() -> str:
    return datetime.now(timezone.utc).isoformat()


def enmascarar(texto: str) -> str:
    for s in SECRETOS:
        if s:
            texto = texto.replace(s, "***")
    return texto


def pedir(metodo: str, ruta: str, cuerpo=None, token: str | None = None, extra: dict | None = None):
    headers = {"Accept": "application/json", "X-Zona-Horaria": "America/Bogota", **(extra or {})}
    datos = None
    if cuerpo is not None:
        datos = json.dumps(cuerpo).encode()
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(BASE + ruta, data=datos, headers=headers, method=metodo)
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            return r.status, {k.lower(): v for k, v in r.headers.items()}, r.read()
    except urllib.error.HTTPError as e:
        return e.code, {k.lower(): v for k, v in e.headers.items()}, e.read()
    except Exception as e:  # noqa: BLE001
        return None, {}, str(e).encode()


def json_o_none(crudo: bytes):
    try:
        return json.loads(crudo.decode("utf-8", "replace"))
    except json.JSONDecodeError:
        return None


def escenario(sid, nombre, prioridad, esperado, estado, obtenido, pasos=None, **extra):
    return {"id": sid, "nombre": nombre, "prioridad": prioridad, "esperado": esperado, "estado": estado,
            "obtenido": enmascarar(obtenido), "pasos": pasos or [], **extra}


INFO = {
    "G5.1": ("Una consulta exitosa y una fallida quedan en la auditoria", "Alta",
             "Cada solicitud deja su registro con usuario, titular, rango, version, hash y resultado; la fallida, con su resultado de error"),
    "G5.2": ("Caida de la auditoria durante la consulta", "Media",
             "La consulta responde 200 con normalidad; la falta del registro no bloquea el servicio y queda a la vista"),
    "G5.3": ("Ciclo de vida del Anexo en la auditoria", "Alta",
             "Creacion, validacion automatica, aprobacion interna, evidencia y aprobacion quedan con usuario y fecha; "
             "la evidencia queda asociada a la version del Anexo"),
}


class Chequeo:
    """Una comprobacion con su detalle."""

    def __init__(self, texto, ok):
        self.texto, self.ok = f"{texto}: {'OK' if ok else 'FALLA'}", ok


def token_canal(secreto, correo):
    SECRETOS.append(secreto)
    st, _, crudo = pedir("POST", "/integraciones/agrofusion/token",
                         {"client_id": CLIENT_ID, "client_secret": secreto, "email": correo})
    datos = json_o_none(crudo) or {}
    tok = datos.get("access_token") or datos.get("token")
    if tok:
        SECRETOS.append(tok)
    return st, tok, datos


def sesion_web(correo, clave):
    SECRETOS.append(clave)
    st, _, crudo = pedir("POST", "/sesiones/", {"correo_electronico": correo, "contrasena": clave})
    tok = (json_o_none(crudo) or {}).get("token")
    if tok:
        SECRETOS.append(tok)
    return st, tok


def lista(crudo):
    j = json_o_none(crudo)
    if isinstance(j, list):
        return j
    if isinstance(j, dict):
        return j.get("items") if isinstance(j.get("items"), list) else next((v for v in j.values() if isinstance(v, list)), [])
    return []


def buscar_evento(tok, tipo, coincide, run=None, paginas=5):
    """Busca en GET /integracion/auditoria un evento del tipo dado que cumpla `coincide`. (evento|None, http)."""
    desde = (datetime.now(timezone.utc) - timedelta(days=1)).date().isoformat()
    http = None
    for pagina in range(1, paginas + 1):
        ruta = f"/integracion/auditoria?tipo_evento={tipo}&desde={desde}&tamano=100&pagina={pagina}"
        st, _, crudo = run.pedir("GET", ruta, token=tok) if run else pedir("GET", ruta, token=tok)
        http = st
        if st != 200:
            return None, st
        j = json_o_none(crudo) or {}
        for e in j.get("items", []):
            if coincide(e):
                return e, st
        if pagina * 100 >= (j.get("total") or 0):
            break
    return None, http


# --- G5.1: consulta exitosa y fallida contra TEST ---------------------------------------------------

def parte_g51(res, peticiones):
    secreto = os.environ.get("QA_SECRET_AAEF", "")
    clave_admin = os.environ.get("QA_CONTRASENA_ADMIN", "")
    if not secreto:
        res["G5.1"][1].append("falta QA_SECRET_AAEF; no se hizo ninguna consulta a TEST")
        return
    if not clave_admin:
        res["G5.1"][1].append("falta QA_CONTRASENA_ADMIN para leer la auditoria")
        return
    s_adm, tok_adm = sesion_web(CORREO_ADMIN, clave_admin)
    if s_adm != 200 or not tok_adm:
        res["G5.1"][1].append(f"el login del administrador devolvio HTTP {s_adm}")
        return
    st, token, datos = token_canal(secreto, CORREO)
    peticiones.append({"paso": "Emitir token de canal", "http": st, "utc": ahora()})
    if st != 200 or not token:
        res["G5.1"][1].append(f"no se pudo emitir el token de canal (HTTP {st} {datos.get('error_code') or ''})")
        return
    rid_ok, rid_err = str(uuid.uuid4()), str(uuid.uuid4())
    ruta_ok = f"/integracion/aaef/productores/{NIT}?desde=2026-09-01&hasta=2026-10-31"
    ruta_err = f"/integracion/aaef/productores/{NIT}?desde=2026-10-05&hasta=2026-10-31"
    s1, h1, _ = pedir("GET", ruta_ok, token=token, extra={"X-Request-Id": rid_ok})
    s2, h2, _ = pedir("GET", ruta_err, token=token, extra={"X-Request-Id": rid_err})
    peticiones += [{"paso": "G5.1 consulta exitosa", "http": s1, "x_request_id": rid_ok, "utc": ahora()},
                   {"paso": "G5.1 consulta fallida (rango no alineado)", "http": s2, "x_request_id": rid_err, "utc": ahora()}]
    c = res["G5.1"][0]
    c.append(Chequeo(f"consulta exitosa HTTP {s1} (esperado 200); consulta fallida HTTP {s2} (esperado 422)", s1 == 200 and s2 == 422))
    if not (s1 == 200 and s2 == 422):
        return
    time.sleep(1)
    ev_ok, st_a = buscar_evento(tok_adm, "PAQUETE_AAEF_CONSULTADO", lambda e: e.get("id_solicitud") == rid_ok)
    ev_err, st_b = buscar_evento(tok_adm, "SOLICITUD_RECHAZADA", lambda e: e.get("id_solicitud") == rid_err)
    if st_a == 403 or st_b == 403:
        res["G5.1"][1].append("el administrador no tiene permiso para leer la auditoria (HTTP 403)")
        return
    if ev_ok is None:
        c.append(Chequeo(f"evento de la consulta exitosa (X-Request-Id {rid_ok}) en la auditoria", False))
    else:
        falta = [k for k in ("id_usuario", "id_cliente_externo", "numero_id_tributaria", "fecha_desde", "fecha_hasta",
                             "version_contrato", "hash_contenido", "codigo_resultado") if not ev_ok.get(k)]
        c.append(Chequeo(f"consulta exitosa registrada; campos faltantes={falta or 'ninguno'}", not falta))
        c.append(Chequeo(f"el registro coincide con la respuesta: NIT {ev_ok.get('numero_id_tributaria')}, "
                         f"rango {ev_ok.get('fecha_desde')} a {ev_ok.get('fecha_hasta')}, version {ev_ok.get('version_contrato')} "
                         f"(cabecera {h1.get('x-version-contrato-aaef')}), hash igual a X-Content-SHA256",
                         ev_ok.get("numero_id_tributaria") == NIT and ev_ok.get("fecha_desde") == "2026-09-01"
                         and ev_ok.get("fecha_hasta") == "2026-10-31"
                         and ev_ok.get("version_contrato") == h1.get("x-version-contrato-aaef")
                         and ev_ok.get("hash_contenido") == h1.get("x-content-sha256")))
        c.append(Chequeo(f"codigo_http {ev_ok.get('codigo_http')} / resultado {ev_ok.get('codigo_resultado')} / integridad "
                         f"{ev_ok.get('integridad')}", ev_ok.get("codigo_http") == 200 and ev_ok.get("integridad") == "INTEGRO"))
    if ev_err is None:
        c.append(Chequeo(f"evento de la consulta fallida (X-Request-Id {rid_err}) en la auditoria", False))
    else:
        falta = [k for k in ("id_usuario", "numero_id_tributaria", "fecha_desde", "fecha_hasta", "codigo_resultado") if not ev_err.get(k)]
        c.append(Chequeo(f"consulta fallida registrada; campos faltantes={falta or 'ninguno'}", not falta))
        c.append(Chequeo(f"resultado de error: codigo_http {ev_err.get('codigo_http')} (esperado 422), codigo_resultado "
                         f"{ev_err.get('codigo_resultado')} (esperado RANGO_NO_ALINEADO), severidad {ev_err.get('severidad')}, "
                         f"integridad {ev_err.get('integridad')}",
                         ev_err.get("codigo_http") == 422 and ev_err.get("codigo_resultado") == "RANGO_NO_ALINEADO"
                         and ev_err.get("integridad") == "INTEGRO"))


# --- G5.3: ciclo de vida del Anexo en el sandbox ----------------------------------------------------

class Run:
    def __init__(self, secreto):
        self.id, self.secreto, self.cerrado, self.cierre_http = str(uuid.uuid4()), secreto, False, None
        SECRETOS.append(secreto)

    def cab(self):
        return {"X-Test-Run-Id": self.id, "X-Sandbox-Secret": self.secreto}

    def pedir(self, metodo, ruta, cuerpo=None, token=None):
        st, h, crudo = pedir(metodo, ruta, cuerpo, token, self.cab())
        return st, h.get("x-test-run-id") == self.id, crudo

    def cerrar(self):
        if self.cerrado:
            return
        st, _, _ = pedir("DELETE", f"/test-control/runs/{self.id}", extra={"X-Sandbox-Secret": self.secreto})
        self.cierre_http, self.cerrado = st, st in (200, 404)
        if st not in (200, 404):
            ALERTAS.append(f"ATENCION: no se pudo cerrar el run {self.id} (HTTP {st}). Avisar al DBA para liberar la sesion.")


def parte_g53(res, peticiones):
    faltan = res["G5.3"][1]
    if not SANDBOX:
        faltan.append("TEST: falta QA_SANDBOX_SECRET; el ciclo del Anexo escribe (con rollback) y no se ejecuta")
        return
    clave_admin, clave_contador = os.environ.get("QA_CONTRASENA_ADMIN", ""), os.environ.get("QA_CONTRASENA_CONTADOR", "")
    sesiones = []   # (nombre, token) en el orden en que se intentaran las operaciones
    if clave_contador:
        s, t = sesion_web(CORREO, clave_contador)
        if s == 200 and t:
            sesiones.append(("Contador", t))
    tok_admin = None
    if clave_admin:
        s, tok_admin = sesion_web(CORREO_ADMIN, clave_admin)
        if s == 200 and tok_admin:
            sesiones.append(("Administrador", tok_admin))
        else:
            tok_admin = None
    if not sesiones:
        faltan.append("TEST: faltan QA_CONTRASENA_CONTADOR o QA_CONTRASENA_ADMIN (o los logins fallaron)")
        return
    if not tok_admin:
        faltan.append("TEST: falta QA_CONTRASENA_ADMIN para leer la auditoria")
        return
    st, _, crudo = pedir("GET", "/integracion/anexos", token=sesiones[0][1])
    anexos_antes = lista(crudo) if st == 200 else None
    if anexos_antes is None:
        faltan.append(f"TEST: no se pudo leer GET /integracion/anexos (HTTP {st})")
        return
    codigo = f"QA-G063-{uuid.uuid4().hex[:8]}"
    version = "9.63"
    sha = (codigo.encode().hex() * 4)[:64]
    exchange = f"AF-SIGAB-2026-10-{uuid.uuid4().int % 10**7:07d}"
    run = Run(SANDBOX)
    c = res["G5.3"][0]
    try:
        st, eco, _ = run.pedir("GET", "/integracion/anexos", token=sesiones[0][1])
        peticiones.append({"paso": "Comprobar el eco del run", "http": st, "eco": eco, "utc": ahora()})
        if not eco:
            faltan.append("TEST: el sandbox no devolvio el eco X-Test-Run-Id; no se escribio nada")
            return

        def operar(nombre, metodo, ruta, cuerpo):
            """Prueba la operacion con cada sesion hasta que una tenga el permiso. (http, actor, crudo)."""
            for actor, tok in sesiones:
                s, e, crudo = run.pedir(metodo, ruta, cuerpo, tok)
                peticiones.append({"paso": f"G5.3 {nombre} ({actor})", "http": s, "eco": e, "utc": ahora()})
                if not e:
                    return s, actor, crudo
                if s != 403:
                    return s, actor, crudo
            return 403, None, crudo

        s, actor_reg, crudo = operar("registrar el Anexo", "POST", "/integracion/anexos",
                                     {"codigo_anexo": codigo, "version_anexo": version, "ruta_documento": "docs/qa/g063.md",
                                      "sha256_documento": sha})
        if s != 201:
            faltan.append(f"TEST: no se pudo registrar el Anexo de prueba (HTTP {s}; sin permiso con ninguna sesion si es 403)")
            return
        ida = (json_o_none(crudo) or {}).get("id_mapeo_anexo_aaef")
        tipos = ["ANEXO_REGISTRADO"]
        s, actor_rev, crudo = operar("pasar a revision", "POST", f"/integracion/anexos/{ida}/revision",
                                      {"justificacion": "TC-M07-G063: aprobacion interna dentro del sandbox, se revierte."})
        if s != 200:
            faltan.append(f"TEST: no se pudo pasar el Anexo a revision (HTTP {s}, {(json_o_none(crudo) or {}).get('error_code')})")
        else:
            tipos.append("ANEXO_EN_REVISION")
            s, actor_apr, crudo = operar("aprobar con evidencia", "POST", f"/integracion/anexos/{ida}/aprobar",
                                         {"id_intercambio": exchange, "ack_aceptado": True,
                                          "observaciones": "TC-M07-G063 dentro del sandbox, se revierte"})
            if s != 200:
                faltan.append(f"TEST: no se pudo aprobar el Anexo (HTTP {s}, {(json_o_none(crudo) or {}).get('error_code')})")
            else:
                tipos.append("ANEXO_APROBADO")
        # Lectura de la auditoria dentro del run (los eventos del Anexo van en la misma transaccion).
        def propio(e):
            return (e.get("json_detalle") or {}).get("codigo_anexo") == codigo
        for tipo in tipos:
            ev, hs = buscar_evento(tok_admin, tipo, propio, run=run)
            if hs == 403:
                faltan.append("TEST: el administrador no tiene permiso para leer la auditoria (HTTP 403)")
                break
            if ev is None:
                c.append(Chequeo(f"evento {tipo} del Anexo {codigo} en la auditoria", False))
                continue
            det = ev.get("json_detalle") or {}
            ok_base = bool(ev.get("id_usuario")) and bool(ev.get("fecha_evento")) and det.get("version_anexo") == version
            extra = ""
            if tipo == "ANEXO_REGISTRADO":
                extra, ok_extra = " (creacion)", det.get("sha256_documento") == sha
            elif tipo == "ANEXO_EN_REVISION":
                extra, ok_extra = " (validacion automatica y aprobacion interna)", det.get("validacion_automatica") == "OK"
            else:
                evi = det.get("evidencia") or {}
                extra, ok_extra = " (evidencia y aprobacion)", evi.get("id_intercambio") == exchange and evi.get("ack_aceptado") is True
            c.append(Chequeo(f"{tipo}{extra}: usuario {ev.get('id_usuario')}, fecha {ev.get('fecha_evento')}, "
                             f"version_anexo {det.get('version_anexo')}", ok_base and ok_extra))
    finally:
        run.cerrar()
        peticiones.append({"paso": "Cerrar el run (rollback)", "http": run.cierre_http, "utc": ahora()})
    st, _, crudo = pedir("GET", "/integracion/anexos", token=sesiones[0][1])
    if st != 200 or lista(crudo) != anexos_antes:
        ALERTAS.append("ATENCION: la lista de Anexos despues del rollback no coincide con la de antes. Avisar al DBA.")


# --- pytest local y armado --------------------------------------------------------------------------

def parte_pytest():
    RESULTADO.mkdir(exist_ok=True)
    xml_ruta = RESULTADO / "pytest_g63_auditoria.xml"
    r = subprocess.run([sys.executable, "-m", "pytest", str(CARPETA / "test_tc_m07_g63_auditoria.py"), "-v", "-s",
                        "-p", "no:cacheprovider", f"--junitxml={xml_ruta}"], cwd=RAIZ, capture_output=True, text=True)
    (RESULTADO / "pytest_g63_auditoria.txt").write_text(r.stdout + r.stderr, encoding="utf-8")
    por: dict[str, list] = {}
    if xml_ruta.exists():
        for tc in ET.parse(xml_ruta).getroot().iter("testcase"):
            nombre = tc.get("name", "")
            falla = tc.find("failure") if tc.find("failure") is not None else tc.find("error")
            por.setdefault(nombre[5:9].replace("_", ".").upper(), []).append(
                (nombre[10:], falla is None, (falla.get("message", "") if falla is not None else "").replace("\n", " ")[:180]))
    return por


REQUIERE_TEST = ("G5.1", "G5.3")


def armar(res, locales):
    esc = []
    for sid, (nombre, prio, esperado) in INFO.items():
        chequeos, faltan = res[sid]
        partes = [c.texto for c in chequeos] + [f"NO EJECUTADA EN TEST: {m}" for m in faltan]
        filas = locales.get(sid)
        malas = []
        if filas:
            malas = [f"{n} ({m})" for n, ok, m in filas if not ok]
            partes.append(f"pytest: {len(filas) - len(malas)}/{len(filas)} comprobaciones pasan"
                          + (f"; FALLAN: {'; '.join(malas)}" if malas else ""))
        else:
            partes.append("pytest no ejecuto este subcaso")
        if malas or any(not c.ok for c in chequeos):
            estado = "RECHAZADO"
        elif faltan or not filas or (sid in REQUIERE_TEST and not chequeos):
            estado = "BLOQUEADO"
        else:
            estado = "APROBADO"
        esc.append(escenario(sid, nombre, prio, esperado, estado, "; ".join(partes)))
    return esc


def veredicto(escenarios):
    estados = [e["estado"] for e in escenarios]
    if "RECHAZADO" in estados:
        return "RECHAZADO"
    return "APROBADO" if all(s == "APROBADO" for s in estados) else "BLOQUEADO"


def html_reporte(ev):
    color = {"APROBADO": "#1b7a3d", "RECHAZADO": "#b3261e", "BLOQUEADO": "#9a6b00"}
    filas = "".join(
        f"<tr><td>{html.escape(e['id'])}</td><td>{html.escape(e['nombre'])}</td><td>{e['prioridad']}</td>"
        f"<td>{html.escape(e['esperado'])}</td><td>{html.escape(e['obtenido'])}</td>"
        f"<td style='color:#fff;background:{color.get(e['estado'], '#555')};font-weight:600'>{e['estado']}</td></tr>"
        for e in ev["escenarios"])
    alertas = "".join(f"<p style='color:#b3261e'><b>{html.escape(a)}</b></p>" for a in ev.get("alertas", []))
    return (f"<!DOCTYPE html><html lang='es'><head><meta charset='utf-8'><title>{CASO} — {ev['estado_final']}</title>"
            "<style>body{font-family:Arial,sans-serif;margin:24px}table{border-collapse:collapse;width:100%;font-size:13px}"
            "th,td{border:1px solid #ccc;padding:6px;vertical-align:top;text-align:left}th{background:#e8eef5}</style></head><body>"
            f"<h1>{CASO} — Auditoria de las consultas AAEF y del ciclo de vida del Anexo</h1><p><b>RF:</b> {RF} · "
            f"<b>Responsable:</b> {RESPONSABLE} · <b>Entorno:</b> TEST y local · <b>UTC:</b> {ev['fecha_ejecucion_utc']} · "
            f"<b>Estado final:</b> {ev['estado_final']}</p>{alertas}"
            "<table><thead><tr><th>Subcaso</th><th>Escenario</th><th>Prioridad</th><th>Esperado</th><th>Obtenido</th>"
            f"<th>Estado</th></tr></thead><tbody>{filas}</tbody></table>"
            "<p><i>Los secretos y tokens no se guardan en este reporte.</i></p></body></html>")


def main():
    RESULTADO.mkdir(exist_ok=True)
    res = {sid: ([], []) for sid in INFO}
    peticiones: list = []
    try:
        parte_g51(res, peticiones)
        parte_g53(res, peticiones)
    finally:
        escenarios = armar(res, parte_pytest())
        ev = {"caso": CASO, "requisito": RF, "responsable": RESPONSABLE, "fecha_ejecucion_utc": ahora(), "entorno": "TEST y local",
              "base_url": BASE, "estado_final": veredicto(escenarios), "alertas": ALERTAS, "escenarios": escenarios,
              "peticiones": peticiones}
        (RESULTADO / f"evidencia_ejecucion_{CASO}.json").write_text(
            enmascarar(json.dumps(ev, ensure_ascii=False, indent=2)), encoding="utf-8")
        (RESULTADO / f"resultado_{CASO}.html").write_text(enmascarar(html_reporte(ev)), encoding="utf-8")
        for e in escenarios:
            print(f"{e['id']:5} {e['estado']:10} {e['obtenido'][:150]}")
        for a in ALERTAS:
            print(a)
        print("ESTADO FINAL:", ev["estado_final"])


if __name__ == "__main__":
    main()
