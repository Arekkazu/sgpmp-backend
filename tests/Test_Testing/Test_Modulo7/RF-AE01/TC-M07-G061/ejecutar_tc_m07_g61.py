# | Fecha      | Nombre | Que se hizo |
# |------------|--------|-------------|
# | 2026-11-19 | usuario-git | TC-M07-G061 (RF-AE01 / RF-AE02): runner de G3.1 y G3.2 contra TEST + pytest local de G3.1 a G3.6. |
"""TC-M07-G061 — Extremos de la consulta AAEF y del Anexo (valores limite).  Responsable: Maria Jose.

Subcasos:
  G3.1 (Alta)  Rango de un dia (desde = hasta): en TEST, el dia suelto con periodos mensuales da 422 RANGO_NO_ALINEADO
               con el rango sugerido; el dia alineado a un periodo de un dia se verifica en local (TEST no tiene uno).
  G3.2 (Media) Rango cerrado sin datos: 200 con invoices [] y summary en 0. TEST solo si hay un rango sin hechos (ver abajo).
  G3.3 (Media) 20 MB exactos pasan y 20 MB + 1 byte -> 422 TAMANO_EXCEDIDO (pytest, caso de uso con datos simulados).
  G3.4 (Alta)  accounting_account con 0, 1, 2 y 3 elementos: solo 1 en tipo 02 y 2 en tipo 06 (pytest).
  G3.5 (Alta)  monto_costo con 0, 0.01 y 100.999 (pytest).
  G3.6 (Media) Value de linea del tipo 06 con 0, 0.01 y suma del par de cuentas (pytest).

El cliente QA_M07_AAEF tiene 5 consultas por minuto. Este runner hace como maximo 4 consultas que cuentan (3 de G3.1 y 1 de
G3.2). Si lo corre dos veces seguidas, espere un minuto entre corridas.

Los secretos van por variables de entorno; NUNCA se guardan en el reporte ni en el repo:
  QA_SECRET_AAEF           (obligatoria para G3.1 y G3.2 en TEST) client_secret de QA_M07_AAEF (D10), lo entrega el DBA
  QA_CORREO_CONTADOR       correo con el que se emite el token (default contador@gmail.com, D03)
  QA_CLIENT_ID_AAEF        default qa-m07-aaef
  QA_NIT                   default 901444215 (D01)
  QA_NIT_SIN_DATOS, QA_DESDE_SIN_DATOS, QA_HASTA_SIN_DATOS
                           (opcionales) un titular y rango alineado, CERRADO y sin hechos, para G3.2 en TEST (no esta en D01-D18)
  QA_BASE_URL              default https://api.inmero.co/api-sgpmp-test

Lo que no se pueda ejecutar queda BLOQUEADO con el motivo; nunca se da por aprobado sin ejecutarse.

Desde la raiz de sgpmp-backend:
    read -s QA_SECRET_AAEF; export QA_SECRET_AAEF      # tecleado en la terminal, sin pegarlo en el chat
    .venv/bin/python tests/Test_Testing/Test_Modulo7/RF-AE01/TC-M07-G061/ejecutar_tc_m07_g61.py
"""
from __future__ import annotations

import html
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

CASO, RF, RESPONSABLE = "TC-M07-G061", "RF-AE01 / RF-AE02", "Maria Jose"
CARPETA = Path(__file__).resolve().parent
RAIZ = CARPETA.parents[4]  # sgpmp-backend
RESULTADO = CARPETA / "Resultado"

BASE = os.environ.get("QA_BASE_URL", "https://api.inmero.co/api-sgpmp-test").rstrip("/")
NIT = os.environ.get("QA_NIT", "901444215")
CORREO = os.environ.get("QA_CORREO_CONTADOR", "contador@gmail.com")
CLIENT_ID = os.environ.get("QA_CLIENT_ID_AAEF", "qa-m07-aaef")
# D02: periodos cerrados 2026-09 y 2026-10. Dias de octubre: fin de periodo, inicio de periodo y mitad de periodo.
DIAS_SUELTOS = (("fin de periodo", "2026-10-31"), ("inicio de periodo", "2026-10-01"), ("mitad de periodo", "2026-10-15"))
RANGO_SUGERIDO = "2026-10-01 a 2026-10-31"
SECRETOS: list[str] = []


def ahora() -> str:
    return datetime.now(timezone.utc).isoformat()


def enmascarar(texto: str) -> str:
    for s in SECRETOS:
        if s:
            texto = texto.replace(s, "***")
    return texto


def pedir(metodo: str, ruta: str, cuerpo=None, token: str | None = None):
    headers = {"Accept": "application/json", "X-Zona-Horaria": "America/Bogota"}
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


INFO = {
    "G3.1": ("Rango de un solo dia (desde = hasta)", "Alta",
             "Dia suelto no alineado: 422 RANGO_NO_ALINEADO con el rango valido sugerido; alineado a un periodo de un dia: valido"),
    "G3.2": ("Rango cerrado sin datos", "Media", "200 con invoices: [] y envelope valido, con summary en 0"),
    "G3.3": ("Respuesta de 20 MB exactos y de 20 MB + 1 byte", "Media", "Hasta 20 MB: 200; por encima: 422 TAMANO_EXCEDIDO"),
    "G3.4": ("accounting_account con 0, 1, 2 y 3 elementos", "Alta", "Valido solo con 1 elemento en tipo 02 y 2 en tipo 06"),
    "G3.5": ("monto_costo con 0, 0.01 y 100.999", "Alta", "0 no genera documento valido; 0.01 valido; 100.999 se trunca a 100.99"),
    "G3.6": ("Value de linea del tipo 06 con 0, 0.01 y suma del par", "Media", "Debe ser > 0: 0 se rechaza, 0.01 se acepta"),
}


class Variante:
    """Una peticion de TEST: lo esperado contra lo obtenido."""

    def __init__(self, etiqueta, st, crudo, http, codigo, con_field=False, contiene=None):
        cuerpo = json_o_none(crudo)
        cuerpo = cuerpo if isinstance(cuerpo, dict) else {}
        campos = cuerpo.get("fields")
        self.st = st
        self.codigo = cuerpo.get("error_code") or cuerpo.get("code")
        self.field = (campos[0].get("field") if isinstance(campos, list) and campos and isinstance(campos[0], dict) else None)
        self.mensaje = str(cuerpo.get("message") or "")
        self.cuerpo = cuerpo
        self.ok = (st == http and self.codigo == codigo and (not con_field or bool(self.field))
                   and (contiene is None or contiene in self.mensaje))
        extra = ""
        if con_field:
            extra += f" field={self.field}"
        if contiene is not None:
            extra += f" rango sugerido {'presente' if contiene in self.mensaje else 'AUSENTE'}"
        self.texto = (f"{etiqueta}: HTTP {st} {self.codigo or '-'}{extra} (esperado {http} {codigo or 'sin error'}) "
                      f"{'OK' if self.ok else 'FALLA'}")


def parte_api():
    """Devuelve ({sid: (variantes, faltan)}, peticiones)."""
    resultado = {"G3.1": ([], []), "G3.2": ([], [])}
    secreto = os.environ.get("QA_SECRET_AAEF", "")
    if not secreto:
        motivo = "falta QA_SECRET_AAEF (client_secret de QA_M07_AAEF, lo entrega el DBA); no se hizo ninguna consulta a TEST"
        for sid in resultado:
            resultado[sid][1].append(motivo)
        return resultado, []
    SECRETOS.append(secreto)
    peticiones = []

    def reg(nombre, metodo, ruta, st):
        peticiones.append({"paso": nombre, "metodo": metodo, "ruta": enmascarar(ruta), "http": st, "utc": ahora()})

    st, _, crudo = pedir("POST", "/integraciones/agrofusion/token",
                         {"client_id": CLIENT_ID, "client_secret": secreto, "email": CORREO})
    reg("Emitir token de canal", "POST", "/integraciones/agrofusion/token", st)
    datos = json_o_none(crudo) or {}
    token = datos.get("access_token") or datos.get("token")
    if st != 200 or not token:
        motivo = f"no se pudo emitir el token de canal (HTTP {st} {datos.get('error_code') or ''}); revise secreto, client_id y correo"
        for sid in resultado:
            resultado[sid][1].append(motivo)
        return resultado, peticiones
    SECRETOS.append(token)

    # G3.1: dia suelto con periodos mensuales
    for etiqueta, dia in DIAS_SUELTOS:
        ruta = f"/integracion/aaef/productores/{NIT}?desde={dia}&hasta={dia}"
        st, _, crudo = pedir("GET", ruta, token=token)
        reg(f"G3.1 {etiqueta}", "GET", ruta, st)
        resultado["G3.1"][0].append(Variante(f"{etiqueta} {dia}", st, crudo, 422, "RANGO_NO_ALINEADO",
                                             con_field=True, contiene=RANGO_SUGERIDO))

    # G3.2: rango cerrado sin hechos (solo si se dio el dato de prueba)
    nit0 = os.environ.get("QA_NIT_SIN_DATOS", NIT)
    d0, h0 = os.environ.get("QA_DESDE_SIN_DATOS", ""), os.environ.get("QA_HASTA_SIN_DATOS", "")
    if d0 and h0:
        ruta = f"/integracion/aaef/productores/{nit0}?desde={d0}&hasta={h0}"
        st, h, crudo = pedir("GET", ruta, token=token)
        reg("G3.2 rango sin hechos", "GET", ruta, st)
        v = Variante(f"rango sin hechos {d0} a {h0}", st, crudo, 200, None)
        cuerpo = v.cuerpo
        vacio = (st == 200 and cuerpo.get("invoices") == [] and cuerpo.get("transactions") == []
                 and cuerpo.get("summary", {}).get("TotalInvoices") == 0 and cuerpo.get("summary", {}).get("TotalNet") == 0
                 and sorted(cuerpo) == ["invoices", "metadata", "summary", "transactions"]
                 and bool({k.lower(): x for k, x in h.items()}.get("x-content-sha256")))
        v.ok = vacio
        v.texto = (f"rango sin hechos {d0} a {h0}: HTTP {st}; invoices={cuerpo.get('invoices')!r}; "
                   f"summary={cuerpo.get('summary')}; {'OK' if vacio else 'FALLA'}")
        resultado["G3.2"][0].append(v)
    else:
        resultado["G3.2"][1].append("TEST: falta un rango cerrado sin hechos (QA_DESDE_SIN_DATOS, QA_HASTA_SIN_DATOS; "
                                    "no esta entre los datos D01-D18 del DBA)")
    return resultado, peticiones


def parte_pytest():
    """Devuelve {sid: [(nombre, ok, mensaje)]} segun el XML de pytest."""
    RESULTADO.mkdir(exist_ok=True)
    xml_ruta = RESULTADO / "pytest_g61_limites.xml"
    r = subprocess.run([sys.executable, "-m", "pytest", str(CARPETA / "test_tc_m07_g61_limites.py"), "-v", "-s",
                        "-p", "no:cacheprovider", f"--junitxml={xml_ruta}"], cwd=RAIZ, capture_output=True, text=True)
    (RESULTADO / "pytest_g61_limites.txt").write_text(r.stdout + r.stderr, encoding="utf-8")
    por_subcaso: dict[str, list] = {}
    if xml_ruta.exists():
        for tc in ET.parse(xml_ruta).getroot().iter("testcase"):
            nombre = tc.get("name", "")
            clave = nombre[5:9].replace("_", ".").upper()
            falla = tc.find("failure") if tc.find("failure") is not None else tc.find("error")
            por_subcaso.setdefault(clave, []).append(
                (nombre[10:], falla is None, (falla.get("message", "") if falla is not None else "").replace("\n", " ")[:180]))
    return por_subcaso


def armar_escenarios(api, locales):
    esc = []
    for sid, (nombre, prio, esperado) in INFO.items():
        variantes, faltan = api.get(sid, ([], []))
        filas = locales.get(sid)
        partes = [v.texto for v in variantes] + [f"NO EJECUTADA EN TEST: {m}" for m in faltan]
        malas_local = []
        if filas:
            malas_local = [f"{n} ({m})" for n, ok, m in filas if not ok]
            partes.append(f"pytest: {len(filas) - len(malas_local)}/{len(filas)} comprobaciones pasan"
                          + (f"; FALLAN: {'; '.join(malas_local)}" if malas_local else ""))
        else:
            partes.append("pytest no ejecuto este subcaso")
        if malas_local or any(not v.ok for v in variantes):
            estado = "RECHAZADO"
        elif not filas or faltan:
            estado = "BLOQUEADO"
        else:
            estado = "APROBADO"
        esc.append(escenario(sid, nombre, prio, esperado, estado, "; ".join(partes),
                             ["GET en TEST con token de canal" if variantes else "", "pytest sobre el nucleo AAEF (sin BD ni red)"]))
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
            f"<h1>{CASO} — Extremos de la consulta AAEF y del Anexo</h1><p><b>RF:</b> {RF} · <b>Responsable:</b> {RESPONSABLE} · "
            f"<b>Entorno:</b> TEST y local · <b>UTC:</b> {ev['fecha_ejecucion_utc']} · <b>Estado final:</b> {ev['estado_final']}</p>"
            "<table><thead><tr><th>Subcaso</th><th>Escenario</th><th>Prioridad</th><th>Esperado</th><th>Obtenido</th>"
            f"<th>Estado</th></tr></thead><tbody>{filas}</tbody></table>"
            "<p><i>Los secretos y tokens no se guardan en este reporte.</i></p></body></html>")


def main():
    RESULTADO.mkdir(exist_ok=True)
    api, peticiones = parte_api()
    escenarios = armar_escenarios(api, parte_pytest())
    ev = {"caso": CASO, "requisito": RF, "responsable": RESPONSABLE, "fecha_ejecucion_utc": ahora(), "entorno": "TEST y local",
          "base_url": BASE, "estado_final": veredicto(escenarios), "escenarios": escenarios, "peticiones": peticiones}
    (RESULTADO / f"evidencia_ejecucion_{CASO}.json").write_text(
        enmascarar(json.dumps(ev, ensure_ascii=False, indent=2)), encoding="utf-8")
    (RESULTADO / f"resultado_{CASO}.html").write_text(enmascarar(html_reporte(ev)), encoding="utf-8")
    for e in escenarios:
        print(f"{e['id']:5} {e['estado']:10} {e['obtenido'][:150]}")
    print("ESTADO FINAL:", ev["estado_final"])


if __name__ == "__main__":
    main()
