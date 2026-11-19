# | Fecha      | Nombre | Que se hizo |
# |------------|--------|-------------|
# | 2026-11-18 | usuario-git | TC-M07-G060 (RF-AE01 / RF-AE02): runner de G2.1 a G2.5 contra TEST + pytest local de G2.6 y G2.7. |
"""TC-M07-G060 — Validacion de la consulta AAEF y del Anexo.  Responsable: Maria Jose.

Subcasos:
  G2.1 (Alta)  Sin cabecera Authorization: 401 NO_AUTENTICADO.
  G2.2 (Alta)  Token invalido, vencido y de otro canal: 401 NO_AUTENTICADO en todos.
  G2.3 (Alta)  Parametros ausentes o mal formados, desde > hasta: 400 PARAMETROS_INVALIDOS con field.
  G2.4 (Alta)  Credenciales en la URL (token, password, api_key): 400 CREDENCIALES_EN_URL y sin rastro del valor.
  G2.5 (Media) NIT inexistente: 404 TITULAR_NO_ENCONTRADO; NIT mal formado: 400 PARAMETROS_INVALIDOS.
  G2.6-G2.7    RF-AE02, via pytest (test_tc_m07_g60_validacion_anexo.py).

El cliente QA_M07_AAEF tiene 5 consultas por minuto. Casi todas las pruebas se rechazan antes de contar contra ese
limite; el runner cuenta como maximo 2 consultas que si cuentan (password en la URL y el NIT inexistente).
No escribe datos de negocio (los eventos de auditoria RF-102 son inmutables y se generan solos).

Los secretos van por variables de entorno; NUNCA se guardan en el reporte ni en el repo:
  QA_SECRET_AAEF           (obligatoria) client_secret de QA_M07_AAEF (D10), lo entrega el DBA
  QA_CORREO_CONTADOR       correo con el que se emite el token (default contador@gmail.com, D03)
  QA_CLIENT_ID_AAEF        default qa-m07-aaef
  QA_NIT                   default 901444215 (D01)
  QA_SECRET_M2M            (opcional) client_secret de QA_M07_M2M (D11): da el token de "otro canal" de G2.2
  QA_CLIENT_ID_M2M         default qa-m07-m2m
  QA_CONTRASENA_CONTADOR   (opcional) contrasena web del contador: da el token de sesion web de G2.2
  QA_CONTRASENA_ADMIN      (opcional) contrasena de admin.rol@gmail.com (QA_CORREO_ADMIN): permite comprobar en
                           GET /integracion/auditoria que la credencial de G2.4 no queda registrada
  QA_ESPERAR_TTL=SI        (opcional) espera ~6 min a que venza un token de canal (TTL 5 min + 30 s de tolerancia)
  QA_BASE_URL              default https://api.inmero.co/api-sgpmp-test

Lo que no se pueda ejecutar queda BLOQUEADO con el motivo; nunca se da por aprobado sin ejecutarse.

Desde la raiz de sgpmp-backend:
    export QA_SECRET_AAEF=...        # (tecleado en la terminal, sin pegarlo en el chat)
    .venv/bin/python tests/Test_Testing/Test_Modulo7/RF-AE01/TC-M07-G060/ejecutar_tc_m07_g60.py
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
from datetime import datetime, timezone
from pathlib import Path

CASO, RF, RESPONSABLE = "TC-M07-G060", "RF-AE01 / RF-AE02", "Maria Jose"
CARPETA = Path(__file__).resolve().parent
RAIZ = CARPETA.parents[4]  # sgpmp-backend
RESULTADO = CARPETA / "Resultado"

BASE = os.environ.get("QA_BASE_URL", "https://api.inmero.co/api-sgpmp-test").rstrip("/")
NIT = os.environ.get("QA_NIT", "901444215")
CORREO = os.environ.get("QA_CORREO_CONTADOR", "contador@gmail.com")
CORREO_ADMIN = os.environ.get("QA_CORREO_ADMIN", "admin.rol@gmail.com")
CLIENT_ID = os.environ.get("QA_CLIENT_ID_AAEF", "qa-m07-aaef")
CLIENT_ID_M2M = os.environ.get("QA_CLIENT_ID_M2M", "qa-m07-m2m")
DESDE, HASTA = "2026-09-01", "2026-10-31"          # D02: periodos 626 y 627 cerrados
MARCA = "QA-G060-" + uuid.uuid4().hex[:12]         # valor que se manda como "credencial" en la URL
MARGEN_TTL = 30 + 20                               # tolerancia del JWT (30 s) + margen
SECRETOS: list[str] = [MARCA]


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
            return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()
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


NOMBRES_API = {
    "G2.1": ("Sin cabecera Authorization", "Alta", "401 NO_AUTENTICADO"),
    "G2.2": ("Token invalido, vencido y de otro canal", "Alta", "401 NO_AUTENTICADO en los tres"),
    "G2.3": ("Parametros ausentes o mal formados; desde > hasta", "Alta", "400 PARAMETROS_INVALIDOS con field"),
    "G2.4": ("Credenciales en la URL (token, password, api_key)", "Alta",
             "400 CREDENCIALES_EN_URL; la credencial no queda registrada"),
    "G2.5": ("NIT inexistente y NIT mal formado", "Media", "404 TITULAR_NO_ENCONTRADO / 400 PARAMETROS_INVALIDOS"),
}


def bloquear_todo_api(motivo: str):
    return [escenario(k, n, p, e, "BLOQUEADO", motivo) for k, (n, p, e) in NOMBRES_API.items()]


class Variante:
    """Una peticion de un subcaso: lo esperado contra lo obtenido."""

    def __init__(self, etiqueta, http_esperado, codigo_esperado, st, crudo, con_field=False):
        cuerpo = json_o_none(crudo) or {}
        self.etiqueta, self.st = etiqueta, st
        # Cuerpo real (src/shared/error_handlers.py): {"error_code", "message", "fields": [{"field", "message"}]}.
        cuerpo = cuerpo if isinstance(cuerpo, dict) else {}
        self.codigo = cuerpo.get("error_code") or cuerpo.get("code")
        campos = cuerpo.get("fields")
        self.field = (campos[0].get("field") if isinstance(campos, list) and campos and isinstance(campos[0], dict)
                      else None) or cuerpo.get("field")
        self.ok = st == http_esperado and self.codigo == codigo_esperado and (not con_field or bool(self.field))
        self.texto = (f"{etiqueta}: HTTP {st} {self.codigo or '-'}"
                      f"{' field=' + str(self.field) if con_field else ''} (esperado {http_esperado} {codigo_esperado})"
                      f" {'OK' if self.ok else 'FALLA'}")


def token_de(client_id: str, secreto: str, correo: str):
    SECRETOS.append(secreto)
    st, _, crudo = pedir("POST", "/integraciones/agrofusion/token",
                         {"client_id": client_id, "client_secret": secreto, "email": correo})
    datos = json_o_none(crudo) or {}
    tok = datos.get("access_token") or datos.get("token")
    if tok:
        SECRETOS.append(tok)
    return st, tok, datos


def sesion_web(correo: str, clave: str):
    SECRETOS.append(clave)
    st, _, crudo = pedir("POST", "/sesiones/", {"correo_electronico": correo, "contrasena": clave})
    tok = (json_o_none(crudo) or {}).get("token")
    if tok:
        SECRETOS.append(tok)
    return st, tok


def veredicto_variantes(variantes: list[Variante], no_ejecutadas: list[str]):
    """RECHAZADO si alguna variante ejecutada falla; BLOQUEADO si todas pasan pero faltan variantes."""
    if any(not v.ok for v in variantes):
        return "RECHAZADO"
    return "BLOQUEADO" if no_ejecutadas or not variantes else "APROBADO"


def detalle(variantes, no_ejecutadas):
    partes = [v.texto for v in variantes] + [f"NO EJECUTADA: {m}" for m in no_ejecutadas]
    return "; ".join(partes)


def parte_api():
    secreto = os.environ.get("QA_SECRET_AAEF", "")
    if not secreto:
        return bloquear_todo_api("Falta la variable QA_SECRET_AAEF (client_secret de QA_M07_AAEF, lo entrega el DBA). "
                                 "No se ejecuto ninguna consulta contra TEST."), []
    peticiones = []

    def reg(nombre, metodo, ruta, st):
        peticiones.append({"paso": nombre, "metodo": metodo, "ruta": enmascarar(ruta), "http": st, "utc": ahora()})

    def consulta(nombre, ruta, token=None, extra=None):
        st, h, crudo = pedir("GET", ruta, token=token, extra=extra)
        reg(nombre, "GET", ruta, st)
        return st, h, crudo

    st, token, datos = token_de(CLIENT_ID, secreto, CORREO)
    reg("Emitir token de canal", "POST", "/integraciones/agrofusion/token", st)
    if st != 200 or not token:
        return bloquear_todo_api(f"No se pudo emitir el token de canal (HTTP {st}, {datos.get('error_code') or ''}). "
                                 "Revise secreto, client_id y correo."), peticiones
    vigencia = int(datos.get("expires_in") or 300)

    # Token que se deja vencer mientras corren los demas subcasos (solo si se pidio esperar).
    token_a_vencer, hora_a_vencer = None, 0.0
    if os.environ.get("QA_ESPERAR_TTL") == "SI":
        st2, token_a_vencer, _ = token_de(CLIENT_ID, secreto, CORREO)
        reg("Emitir token para dejar vencer", "POST", "/integraciones/agrofusion/token", st2)
        hora_a_vencer = time.monotonic() + vigencia + MARGEN_TTL

    ruta_ok = f"/integracion/aaef/productores/{NIT}?desde={DESDE}&hasta={HASTA}"
    esc = []

    # G2.1
    st, _, crudo = consulta("G2.1 sin Authorization", ruta_ok)
    v = Variante("sin Authorization", 401, "NO_AUTENTICADO", st, crudo)
    n, p, e = NOMBRES_API["G2.1"]
    esc.append(escenario("G2.1", n, p, e, "APROBADO" if v.ok else "RECHAZADO", v.texto,
                         [f"GET {ruta_ok} sin cabecera Authorization"]))

    # G2.2
    variantes, faltan = [], []
    partes = token.split(".")
    firma = partes[2]
    medio = len(firma) // 2
    alterada = ".".join(partes[:2] + [firma[:medio] + ("A" if firma[medio] != "A" else "B") + firma[medio + 1:]])
    for etiqueta, tok in (("firma alterada", alterada), ("cadena que no es un token", "no.es.untoken")):
        s, _, c = consulta(f"G2.2 {etiqueta}", ruta_ok, token=tok)
        variantes.append(Variante(etiqueta, 401, "NO_AUTENTICADO", s, c))
    clave_web = os.environ.get("QA_CONTRASENA_CONTADOR", "")
    if clave_web:
        s_web, tok_web = sesion_web(CORREO, clave_web)
        if s_web == 200 and tok_web:
            s, _, c = consulta("G2.2 token de sesion web", ruta_ok, token=tok_web)
            variantes.append(Variante("token de la sesion web (sin audiencia de canal)", 401, "NO_AUTENTICADO", s, c))
        else:
            faltan.append(f"token de sesion web: el login devolvio HTTP {s_web}")
    else:
        faltan.append("token de sesion web: falta QA_CONTRASENA_CONTADOR")
    secreto_m2m = os.environ.get("QA_SECRET_M2M", "")
    if secreto_m2m:
        s_m, tok_m, d_m = token_de(CLIENT_ID_M2M, secreto_m2m, CORREO)
        reg("Emitir token del cliente M2M", "POST", "/integraciones/agrofusion/token", s_m)
        if s_m == 200 and tok_m:
            s, _, c = consulta("G2.2 token de otro canal", ruta_ok, token=tok_m)
            variantes.append(Variante("token de otro canal (QA_M07_M2M)", 401, "NO_AUTENTICADO", s, c))
        else:
            faltan.append(f"token de otro canal: no se pudo emitir (HTTP {s_m} {d_m.get('error_code') or ''})")
    else:
        faltan.append("token de otro canal: falta QA_SECRET_M2M")
    if not token_a_vencer:
        faltan.append("token vencido: defina QA_ESPERAR_TTL=SI (la corrida tarda ~6 min mas)")

    # G2.3 (el parametro se valida antes de la autenticacion; se envia con token valido para aislar la causa)
    v23 = []
    for etiqueta, q in (("falta desde", f"hasta={HASTA}"), ("falta hasta", f"desde={DESDE}"),
                        ("fecha 2026-13-40", f"desde=2026-13-40&hasta={HASTA}"),
                        ("fecha 31/10/2026", f"desde={DESDE}&hasta=31/10/2026"),
                        ("desde posterior a hasta", f"desde={HASTA}&hasta={DESDE}")):
        s, _, c = consulta(f"G2.3 {etiqueta}", f"/integracion/aaef/productores/{NIT}?{urllib.parse.quote(q, safe='=&/')}", token=token)
        v23.append(Variante(etiqueta, 400, "PARAMETROS_INVALIDOS", s, c, con_field=True))
    n, p, e = NOMBRES_API["G2.3"]
    esc.append(escenario("G2.3", n, p, e, veredicto_variantes(v23, []), detalle(v23, []),
                         ["GET con token valido y cada parametro defectuoso"]))

    # G2.4
    v24 = []
    for etiqueta, param in (("token", "token"), ("password", "password"), ("api_key", "api_key")):
        s, _, c = consulta(f"G2.4 {etiqueta} en la URL", ruta_ok + f"&{param}={MARCA}", token=token)
        v24.append(Variante(f"{etiqueta} en la URL", 400, "CREDENCIALES_EN_URL", s, c))
    no_ej24 = []
    clave_admin = os.environ.get("QA_CONTRASENA_ADMIN", "")
    registro = ""
    if clave_admin:
        s_a, tok_a = sesion_web(CORREO_ADMIN, clave_admin)
        if s_a == 200 and tok_a:
            s, _, c = pedir("GET", "/integracion/auditoria?tipo_evento=CREDENCIALES_EN_URL&tamano=100", token=tok_a)
            reg("G2.4 consultar auditoria CREDENCIALES_EN_URL", "GET", "/integracion/auditoria?tipo_evento=CREDENCIALES_EN_URL", s)
            cuerpo = c.decode("utf-8", "replace")
            eventos = (json_o_none(c) or {}).get("total")
            if s != 200:
                no_ej24.append(f"registro: GET /integracion/auditoria devolvio HTTP {s}")
            elif MARCA in cuerpo:
                v = Variante("la credencial NO debe quedar registrada", 0, "-", 0, b"")
                v.ok, v.texto = False, "la credencial enviada aparece en el registro de auditoria: FALLA"
                v24.append(v)
            else:
                registro = f"; en la auditoria ({eventos} eventos CREDENCIALES_EN_URL) no aparece el valor enviado: OK"
        else:
            no_ej24.append(f"registro: el login del administrador devolvio HTTP {s_a}")
    else:
        no_ej24.append("registro: falta QA_CONTRASENA_ADMIN para revisar GET /integracion/auditoria")
    n, p, e = NOMBRES_API["G2.4"]
    esc.append(escenario("G2.4", n, p, e, veredicto_variantes(v24, no_ej24), detalle(v24, no_ej24) + registro,
                         ["GET con token valido y una credencial en la query", "Revisar la auditoria RF-102"]))

    # G2.5
    v25 = []
    s, _, c = consulta("G2.5 NIT inexistente", "/integracion/aaef/productores/999999990?" + f"desde={DESDE}&hasta={HASTA}", token=token)
    v25.append(Variante("NIT inexistente 999999990", 404, "TITULAR_NO_ENCONTRADO", s, c))
    for etiqueta, nit in (("NIT con letras", "12AB56"), ("NIT de 3 digitos", "123")):
        s, _, c = consulta(f"G2.5 {etiqueta}", f"/integracion/aaef/productores/{nit}?desde={DESDE}&hasta={HASTA}", token=token)
        v25.append(Variante(etiqueta, 400, "PARAMETROS_INVALIDOS", s, c))
    n, p, e = NOMBRES_API["G2.5"]
    esc.append(escenario("G2.5", n, p, e, veredicto_variantes(v25, []), detalle(v25, []),
                         ["GET con token valido y NIT inexistente / mal formado"]))

    # G2.2: el token vencido va al final para darle tiempo
    if token_a_vencer:
        falta = hora_a_vencer - time.monotonic()
        if falta > 0:
            print(f"Esperando {int(falta)} s a que venza el token de canal...", flush=True)
            time.sleep(falta)
        s, _, c = consulta("G2.2 token vencido", ruta_ok, token=token_a_vencer)
        variantes.append(Variante(f"token vencido (vigencia {vigencia} s)", 401, "NO_AUTENTICADO", s, c))
    n, p, e = NOMBRES_API["G2.2"]
    esc.insert(1, escenario("G2.2", n, p, e, veredicto_variantes(variantes, faltan), detalle(variantes, faltan),
                            ["GET con cada token defectuoso"]))
    return esc, peticiones


INFO_PYTEST = {
    "G2.6": ("Valores fijos del Anexo", "Alta", 'StandardVersion = "1.0", fechas YYYY-MM-DD, transactions = [], Status = ACTIVE'),
    "G2.7": ("Cada control del Anexo bloquea el paso a EN_REVISION", "Alta",
             "Estructura, cobertura, cuadre de documento y de summary, cuentas y formato de fecha: cada falla bloquea (FA-2)"),
}


def parte_pytest():
    RESULTADO.mkdir(exist_ok=True)
    xml_ruta = RESULTADO / "pytest_g60_validacion.xml"
    r = subprocess.run([sys.executable, "-m", "pytest", str(CARPETA / "test_tc_m07_g60_validacion_anexo.py"), "-v", "-s",
                        "-p", "no:cacheprovider", f"--junitxml={xml_ruta}"], cwd=RAIZ, capture_output=True, text=True)
    (RESULTADO / "pytest_g60_validacion.txt").write_text(r.stdout + r.stderr, encoding="utf-8")
    por_subcaso: dict[str, list[tuple[str, bool, str]]] = {}
    if xml_ruta.exists():
        for tc in ET.parse(xml_ruta).getroot().iter("testcase"):
            nombre = tc.get("name", "")
            clave = nombre[5:9].replace("_", ".").upper()
            falla = tc.find("failure") if tc.find("failure") is not None else tc.find("error")
            por_subcaso.setdefault(clave, []).append(
                (nombre.split("[")[-1].rstrip("]") if "[" in nombre else nombre, falla is None,
                 (falla.get("message", "") if falla is not None else "").replace("\n", " ")[:160]))
    esc = []
    for sid, (nombre, prio, esperado) in INFO_PYTEST.items():
        filas = por_subcaso.get(sid)
        if not filas:
            esc.append(escenario(sid, nombre, prio, esperado, "BLOQUEADO", "pytest no ejecuto este subcaso"))
            continue
        malas = [f"{n} ({m})" for n, ok, m in filas if not ok]
        obtenido = (f"pytest: {len(filas) - len(malas)}/{len(filas)} comprobaciones pasan"
                    + (f"; NO bloquean o fallan: {'; '.join(malas)}" if malas else ""))
        esc.append(escenario(sid, nombre, prio, esperado, "RECHAZADO" if malas else "APROBADO", obtenido,
                             ["pytest sobre el caso de uso del Anexo (sin BD ni red)"]))
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
    return (f"<!DOCTYPE html><html lang='es'><head><meta charset='utf-8'><title>{CASO} — {ev['estado_final']}</title>"
            "<style>body{font-family:Arial,sans-serif;margin:24px}table{border-collapse:collapse;width:100%;font-size:13px}"
            "th,td{border:1px solid #ccc;padding:6px;vertical-align:top;text-align:left}th{background:#e8eef5}</style></head><body>"
            f"<h1>{CASO} — Validaciones de la consulta AAEF y del Anexo</h1><p><b>RF:</b> {RF} · <b>Responsable:</b> {RESPONSABLE} · "
            f"<b>Entorno:</b> TEST · <b>UTC:</b> {ev['fecha_ejecucion_utc']} · <b>Estado final:</b> {ev['estado_final']}</p>"
            "<table><thead><tr><th>Subcaso</th><th>Escenario</th><th>Prioridad</th><th>Esperado</th><th>Obtenido</th>"
            f"<th>Estado</th></tr></thead><tbody>{filas}</tbody></table>"
            "<p><i>Los secretos y tokens no se guardan en este reporte.</i></p></body></html>")


def main():
    RESULTADO.mkdir(exist_ok=True)
    api, peticiones = parte_api()
    escenarios = api + parte_pytest()
    escenarios.sort(key=lambda e: e["id"])
    ev = {"caso": CASO, "requisito": RF, "responsable": RESPONSABLE, "fecha_ejecucion_utc": ahora(), "entorno": "TEST",
          "base_url": BASE, "estado_final": veredicto(escenarios), "escenarios": escenarios, "peticiones": peticiones}
    (RESULTADO / f"evidencia_ejecucion_{CASO}.json").write_text(
        enmascarar(json.dumps(ev, ensure_ascii=False, indent=2)), encoding="utf-8")
    (RESULTADO / f"resultado_{CASO}.html").write_text(enmascarar(html_reporte(ev)), encoding="utf-8")
    for e in escenarios:
        print(f"{e['id']:5} {e['estado']:10} {e['obtenido'][:140]}")
    print("ESTADO FINAL:", ev["estado_final"])


if __name__ == "__main__":
    main()
