# | Fecha      | Nombre    | Que se hizo |
# |------------|-----------|-------------|
# | 2026-11-18 | HulkyZeus | TC-M07-G059 (RF-AE01 / RF-AE02): runner de G1.1 a G1.4 contra TEST + pytest local de G1.5 a G1.8. |
# | 2026-11-18 | HulkyZeus | TC-M07-G059: G1.2 resuelve la version ACTIVA real en /integracion/contratos (antes fija en 2.1). |
"""TC-M07-G059 — Funcional: consulta AAEF y generacion del Anexo.  Responsable: Maria Jose.

Subcasos:
  G1.1 (Alta)  Consulta valida: 200, tres headers y envelope con metadata/summary/invoices/transactions.
  G1.2 (Media) Sin Accept-Version: X-Version-Contrato-AAEF informa la version ACTIVA.
  G1.3 (Alta)  Dos consultas identicas: mismo X-Content-SHA256 y cuerpo equivalente.
  G1.4 (Media) Nunca 206 ni metadatos de paginacion.
  G1.5-G1.8    RF-AE02, via pytest (test_tc_m07_g59_mapeo.py).

Solo hace 2 consultas AAEF (el cliente tiene 5 por minuto) mas la emision del token. No escribe datos de
negocio (los eventos de auditoria RF-102 son inmutables y se generan solos).

Los secretos van por variables de entorno; NUNCA se guardan en el reporte ni en el repo:
  QA_SECRET_AAEF           (obligatoria) client_secret de QA_M07_AAEF (D10), lo entrega el DBA
  QA_CORREO_CONTADOR       correo con el que se emite el token (default contador@gmail.com, D03)
  QA_CLIENT_ID_AAEF        default qa-m07-aaef
  QA_NIT                   default 901444215 (D01)
  QA_CONTRASENA_CONTADOR   contrasena web del contador (opcional): permite consultar la version ACTIVA real
                           en GET /integracion/contratos (cambia con las pruebas de RF-98)
  QA_VERSION_ACTIVA        solo si no hay contrasena: version que se espera como ACTIVA (sin verificarla)
  QA_BASE_URL              default https://api.inmero.co/api-sgpmp-test

Desde la raiz de sgpmp-backend:
    export QA_SECRET_AAEF=...        # (tecleado en la terminal, sin pegarlo en el chat)
    .venv/bin/python tests/Test_Testing/Test_Modulo7/RF-AE01/TC-M07-G059/ejecutar_tc_m07_g59.py
"""
from __future__ import annotations

import html
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
import uuid
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

CASO, RF, RESPONSABLE = "TC-M07-G059", "RF-AE01 / RF-AE02", "Maria Jose"
CARPETA = Path(__file__).resolve().parent
RAIZ = CARPETA.parents[4]  # sgpmp-backend
RESULTADO = CARPETA / "Resultado"

BASE = os.environ.get("QA_BASE_URL", "https://api.inmero.co/api-sgpmp-test").rstrip("/")
NIT = os.environ.get("QA_NIT", "901444215")
CORREO = os.environ.get("QA_CORREO_CONTADOR", "contador@gmail.com")
CLIENT_ID = os.environ.get("QA_CLIENT_ID_AAEF", "qa-m07-aaef")
VERSION_ACTIVA = os.environ.get("QA_VERSION_ACTIVA", "")
DESDE, HASTA = "2026-09-01", "2026-10-31"          # D02: 626 y 627 cerrados, 5 facturas, $1.420.000
FACTURAS_ESPERADAS, NETO_ESPERADO = 5, 1420000.00
SECRETOS: list[str] = []                           # todo lo que se enmascara en lo que se guarda


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


def bloquear_todo_api(motivo: str):
    nombres = {"G1.1": "Consulta valida", "G1.2": "Sin Accept-Version", "G1.3": "Dos consultas identicas",
               "G1.4": "Nunca 206 ni paginacion"}
    return [escenario(k, v, "-", "-", "BLOQUEADO", motivo) for k, v in nombres.items()]


def version_activa_real():
    """Version ACTIVA segun GET /integracion/contratos (sesion web del contador). (version|None, nota)."""
    clave = os.environ.get("QA_CONTRASENA_CONTADOR", "")
    if not clave:
        return None, "sin QA_CONTRASENA_CONTADOR"
    SECRETOS.append(clave)
    st, _, crudo = pedir("POST", "/sesiones/", {"correo_electronico": CORREO, "contrasena": clave})
    tok = (json_o_none(crudo) or {}).get("token")
    if st != 200 or not tok:
        return None, f"no se pudo iniciar la sesion web (HTTP {st})"
    SECRETOS.append(tok)
    st, _, crudo = pedir("GET", "/integracion/contratos", token=tok)
    j = json_o_none(crudo)
    lista = j if isinstance(j, list) else next((v for v in (j or {}).values() if isinstance(v, list)), [])
    activa = [x.get("contrato_version") for x in lista if x.get("estado") == "ACTIVO"]
    if st != 200 or len(activa) != 1:
        return None, f"GET /integracion/contratos HTTP {st}; versiones ACTIVO encontradas: {activa}"
    return activa[0], f"GET /integracion/contratos (estados: {[(x.get('contrato_version'), x.get('estado')) for x in lista]})"


def parte_api():
    secreto = os.environ.get("QA_SECRET_AAEF", "")
    if not secreto:
        return bloquear_todo_api("Falta la variable QA_SECRET_AAEF (client_secret de QA_M07_AAEF, lo entrega el DBA). "
                                 "No se ejecuto ninguna consulta contra TEST."), []
    SECRETOS.append(secreto)
    peticiones = []

    def reg(nombre, metodo, ruta, status, headers):
        peticiones.append({"paso": nombre, "metodo": metodo, "ruta": ruta, "http": status, "utc": ahora(),
                           "x_request_id": headers.get("X-Request-Id")})

    st, _, crudo = pedir("POST", "/integraciones/agrofusion/token",
                         {"client_id": CLIENT_ID, "client_secret": secreto, "email": CORREO})
    reg("Emitir token de canal", "POST", "/integraciones/agrofusion/token", st, {})
    datos = json_o_none(crudo) or {}
    token = datos.get("access_token") or datos.get("token")
    if st != 200 or not token:
        return bloquear_todo_api(f"No se pudo emitir el token de canal (HTTP {st}, "
                                 f"{(datos.get('code') or datos.get('error_code') or '')}). Revise secreto, client_id y correo."), peticiones
    SECRETOS.append(token)

    activa_antes, nota_ver = version_activa_real()
    ruta = f"/integracion/aaef/productores/{NIT}?desde={DESDE}&hasta={HASTA}"
    rid = str(uuid.uuid4())
    a_st, a_h, a_crudo = pedir("GET", ruta, token=token, extra={"X-Request-Id": rid})
    reg("Consulta A (sin Accept-Version)", "GET", ruta, a_st, a_h)
    b_st, b_h, b_crudo = pedir("GET", ruta, token=token)
    reg("Consulta B (identica a A)", "GET", ruta, b_st, b_h)
    a, b = json_o_none(a_crudo), json_o_none(b_crudo)
    h = {k.lower(): v for k, v in a_h.items()}
    hb = {k.lower(): v for k, v in b_h.items()}
    esc = []

    # G1.1
    faltan = [k for k in ("x-request-id", "x-version-contrato-aaef", "x-content-sha256") if not h.get(k)]
    claves = sorted(a) if isinstance(a, dict) else []
    resumen = (a or {}).get("summary", {}) if isinstance(a, dict) else {}
    ok11 = a_st == 200 and not faltan and claves == ["invoices", "metadata", "summary", "transactions"]
    datos_ok = (resumen.get("TotalInvoices") == FACTURAS_ESPERADAS and abs(float(resumen.get("TotalNet", 0)) - NETO_ESPERADO) < 0.005)
    esc.append(escenario(
        "G1.1", "Consulta valida: token de canal, rango alineado, periodos cerrados", "Alta",
        "200; headers X-Request-Id, X-Version-Contrato-AAEF y X-Content-SHA256; envelope con metadata, summary, invoices, transactions",
        "APROBADO" if ok11 else "RECHAZADO",
        f"HTTP {a_st}; headers faltantes={faltan or 'ninguno'}; claves={claves}; X-Request-Id enviado "
        f"{'conservado' if h.get('x-request-id') == rid else 'NO conservado'}; "
        f"TotalInvoices={resumen.get('TotalInvoices')}, TotalNet={resumen.get('TotalNet')} "
        f"({'coincide' if datos_ok else 'NO coincide'} con D02: {FACTURAS_ESPERADAS} facturas / ${NETO_ESPERADO:,.2f})",
        ["Emitir token de canal QA_M07_AAEF", f"GET {ruta}"], headers_recibidos=sorted(h)))

    # G1.2
    version = h.get("x-version-contrato-aaef")
    activa_despues, _ = version_activa_real()
    if activa_antes is not None:
        estable = activa_antes == activa_despues
        estado12 = "APROBADO" if a_st == 200 and estable and version == activa_antes else "RECHAZADO"
        detalle12 = (f"HTTP {a_st}; X-Version-Contrato-AAEF={version}; version ACTIVA en el sistema antes={activa_antes}, "
                     f"despues={activa_despues}; {nota_ver}")
        if not estable:
            estado12, detalle12 = "BLOQUEADO", detalle12 + " (la version ACTIVA cambio durante la prueba: repetir)"
    elif VERSION_ACTIVA:
        estado12 = "APROBADO" if a_st == 200 and version == VERSION_ACTIVA else "RECHAZADO"
        detalle12 = (f"HTTP {a_st}; X-Version-Contrato-AAEF={version}; esperada {VERSION_ACTIVA} (QA_VERSION_ACTIVA, "
                     f"no verificada en el sistema: {nota_ver})")
    else:
        estado12 = "BLOQUEADO"
        detalle12 = (f"HTTP {a_st}; X-Version-Contrato-AAEF={version}. No se pudo verificar cual es la version ACTIVA "
                     f"({nota_ver}); defina QA_CONTRASENA_CONTADOR.")
    esc.append(escenario(
        "G1.2", "Consulta sin Accept-Version usa la version ACTIVA", "Media",
        "X-Version-Contrato-AAEF = version ACTIVA segun GET /integracion/contratos", estado12, detalle12,
        ["Misma consulta A, sin Accept-Version", "GET /integracion/contratos (sesion web del contador)"]))

    # G1.3
    def sin_volatiles(e):
        e = json.loads(json.dumps(e))
        if isinstance(e, dict):
            e.get("metadata", {}).pop("ExchangeId", None)
            e.get("metadata", {}).pop("GeneratedAt", None)
        return e
    mismo_hash = bool(h.get("x-content-sha256")) and h.get("x-content-sha256") == hb.get("x-content-sha256")
    mismo_cuerpo = a is not None and b is not None and sin_volatiles(a) == sin_volatiles(b)
    ok13 = a_st == 200 and b_st == 200 and mismo_hash and mismo_cuerpo
    esc.append(escenario(
        "G1.3", "Dos consultas identicas dan el mismo X-Content-SHA256 y cuerpo equivalente", "Alta",
        "Ambas 200; X-Content-SHA256 identico; cuerpo equivalente (ExchangeId y GeneratedAt cambian por diseno)",
        "APROBADO" if ok13 else "RECHAZADO",
        f"HTTP {a_st}/{b_st}; hash identico={mismo_hash}; cuerpo equivalente={mismo_cuerpo}; "
        f"ExchangeId distinto={((a or {}).get('metadata', {}).get('ExchangeId') != (b or {}).get('metadata', {}).get('ExchangeId'))}",
        ["Consulta A", "Consulta B (identica)"]))

    # G1.4
    paginacion_body = [k for k in ("page", "pagina", "next", "next_page", "total_pages", "links", "offset", "limit", "cursor")
                       if isinstance(a, dict) and (k in a or k in a.get("summary", {}) or k in a.get("metadata", {}))]
    paginacion_hdr = [k for k in ("link", "content-range", "x-total-count", "x-next-page", "x-page") if k in h]
    ok14 = a_st == 200 and not paginacion_body and not paginacion_hdr
    esc.append(escenario(
        "G1.4", "Nunca 206 y sin metadatos de paginacion", "Media",
        "HTTP 200 (no 206); sin Link/Content-Range ni campos de paginacion en el cuerpo",
        "APROBADO" if ok14 else "RECHAZADO",
        f"HTTP {a_st}; campos de paginacion en cuerpo={paginacion_body or 'ninguno'}; en headers={paginacion_hdr or 'ninguno'}",
        ["Inspeccionar la respuesta de la consulta A"]))
    return esc, peticiones


def parte_pytest():
    RESULTADO.mkdir(exist_ok=True)
    xml_ruta = RESULTADO / "pytest_g59_mapeo.xml"
    txt = RESULTADO / "pytest_g59_mapeo.txt"
    r = subprocess.run([sys.executable, "-m", "pytest", str(CARPETA / "test_tc_m07_g59_mapeo.py"), "-v", "-s",
                        "-p", "no:cacheprovider", f"--junitxml={xml_ruta}"], cwd=RAIZ, capture_output=True, text=True)
    txt.write_text(r.stdout + r.stderr, encoding="utf-8")
    info = {"G1.5": ("Todo campo del esquema de Agrofusion esta mapeado y en el Anexo", "Alta",
                     "100 % de los campos requeridos de metadata, summary, invoices y transactions mapeados y descritos en el Anexo"),
            "G1.6": ("Documento 02 desde COMPRA_PROVEEDOR y SERVICIO_TERCERO", "Alta",
                     "Type 02; DocumentId COS-{id}-{fecha}; IVA/retenciones/descuentos 0; una sola linea"),
            "G1.7": ("Documento 06 desde el comprobante NIC 41", "Alta",
                     "Type 06; DocumentId NIC-{NIT}-{AAAAMM}-{TIPO_HECHO}-{ESPECIE}; fechas = ultimo dia del periodo"),
            "G1.8": ("Hash SHA-256 del Anexo reproducible", "Media",
                     "hash_documento_anexo reproducible y con el formato que acepta RF-98")}
    resultados = {}
    if xml_ruta.exists():
        for tc in ET.parse(xml_ruta).getroot().iter("testcase"):
            clave = tc.get("name", "")[5:9].replace("_", ".").upper()
            falla = tc.find("failure") if tc.find("failure") is not None else tc.find("error")
            resultados[clave] = (falla is None, (falla.get("message", "") if falla is not None else "")[:300])
    esc = []
    for sid, (nombre, prio, esperado) in info.items():
        ok, msg = resultados.get(sid, (None, "no se ejecuto"))
        esc.append(escenario(sid, nombre, prio, esperado, "APROBADO" if ok else "RECHAZADO",
                             "pytest: PASSED" if ok else f"pytest: {msg}", ["pytest sobre el nucleo AAEF (sin BD ni red)"]))
    for e in esc:
        if e["id"] == "G1.8" and e["estado"] == "APROBADO":
            e["nota"] = ("La coincidencia con el hash registrado en RF-98 (GET /integracion/anexos) NO se compara aqui: "
                         "en TEST solo esta el anexo 2 (ANEXO-AAEF-V2.0) y el 3 (2.2, BORRADOR); no hay registro del v3.0.")
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
            f"<h1>{CASO} — Consulta AAEF y generacion del Anexo</h1><p><b>RF:</b> {RF} · <b>Responsable:</b> {RESPONSABLE} · "
            f"<b>Entorno:</b> TEST · <b>UTC:</b> {ev['fecha_ejecucion_utc']} · <b>Estado final:</b> {ev['estado_final']}</p>"
            "<table><thead><tr><th>Subcaso</th><th>Escenario</th><th>Prioridad</th><th>Esperado</th><th>Obtenido</th>"
            f"<th>Estado</th></tr></thead><tbody>{filas}</tbody></table>"
            "<p><i>Los secretos y tokens no se guardan en este reporte.</i></p></body></html>")


def main():
    RESULTADO.mkdir(exist_ok=True)
    api, peticiones = parte_api()
    escenarios = api + parte_pytest()
    ev = {"caso": CASO, "requisito": RF, "responsable": RESPONSABLE, "fecha_ejecucion_utc": ahora(), "entorno": "TEST",
          "base_url": BASE, "estado_final": veredicto(escenarios), "escenarios": escenarios, "peticiones": peticiones,
          "limitaciones": ["Subcasos opcionales de interoperabilidad con Agrofusion/SIGCON no ejecutados."]}
    (RESULTADO / f"evidencia_ejecucion_{CASO}.json").write_text(
        enmascarar(json.dumps(ev, ensure_ascii=False, indent=2)), encoding="utf-8")
    (RESULTADO / f"resultado_{CASO}.html").write_text(enmascarar(html_reporte(ev)), encoding="utf-8")
    for e in escenarios:
        print(f"{e['id']:5} {e['estado']:10} {e['obtenido'][:110]}")
    print("ESTADO FINAL:", ev["estado_final"])


if __name__ == "__main__":
    main()
