# | Fecha      | Nombre | Que se hizo |
# |------------|--------|-------------|
# | 2026-11-19 | usuario-git | TC-M07-G062 (RF-AE01 / RF-AE02): runner de G4.1 a G4.4 (+ variantes de G4.5 y G4.8) contra TEST y pytest local de G4.5 a G4.8. |
# | 2026-11-19 | usuario-git | TC-M07-G062: G4.8 acepta cualquier 4xx (CA-8 no exige codigo) y deja el 404 generico como observacion. |
"""TC-M07-G062 — Reglas de acceso, de periodos y de ciclo de vida del Anexo.  Responsable: Maria Jose.

Subcasos:
  G4.1 (Alta)  Cliente de canal suspendido y revocado: 403 CLIENTE_NO_AUTORIZADO con un token emitido antes.   [TEST, sandbox]
  G4.2 (Alta)  Usuario sin todas las fincas del titular: 403 ALCANCE_INSUFICIENTE; con todas: 200.            [TEST, solo lectura]
  G4.3 (Alta)  Rango no alineado (inicio o fin a mitad de periodo): 422 RANGO_NO_ALINEADO con rango sugerido. [TEST, solo lectura]
  G4.4 (Alta)  Rango que incluye un periodo abierto: 422 PERIODO_NO_CERRADO.                                  [TEST, solo lectura]
  G4.5 (Alta)  Pasar a EN_REVISION: aprobacion interna del Contador; usuario sin ese perfil rechazado.        [pytest + TEST sandbox]
  G4.6 (Alta)  Pasar a APROBADO exige evidencia de interoperabilidad (ExchangeId y ACK 100 %).                [pytest]
  G4.7 (Media) Solo BORRADOR -> EN_REVISION -> APROBADO; las demas transiciones se rechazan.                  [pytest]
  G4.8 (Alta)  Un Anexo APROBADO no se modifica; un cambio es un Anexo nuevo en BORRADOR.                     [pytest + TEST sandbox]

SEGURIDAD DE LOS DATOS DE TEST. Todo lo que escribe (suspender y revocar clientes, intentar cambiar Anexos) corre DENTRO de
un run del sandbox (cabeceras X-Test-Run-Id y X-Sandbox-Secret) y el run se cierra SIEMPRE con DELETE /test-control/runs/{id}
(rollback), aunque algo falle. Antes de escribir se comprueba que el servidor devuelva el eco X-Test-Run-Id; si no lo
devuelve, no se escribe nada. Despues del rollback se vuelve a leer el estado de los clientes y de los Anexos y se compara
con el de antes. Sin QA_SANDBOX_SECRET no se ejecuta ninguna escritura: esos subcasos quedan BLOQUEADO.

El cliente QA_M07_AAEF tiene 5 consultas por minuto. El runner hace 5 consultas que cuentan y se pausa solo para no pasar de 4
por minuto; la corrida puede tardar ~1 minuto mas.

Los secretos van por variables de entorno; NUNCA se guardan en el reporte ni en el repo:
  QA_SECRET_AAEF           (G4.2 a G4.4) client_secret de QA_M07_AAEF (D10)
  QA_CORREO_CONTADOR       default contador@gmail.com (D03: lectura en exportacion_contable y las 3 fincas de D01)
  QA_CORREO_PARCIAL        (G4.2) correo del usuario que solo tiene 2 de las 3 fincas (D04)
  QA_SANDBOX_SECRET        (G4.1, G4.5 y G4.8 en TEST) X-Sandbox-Secret
  QA_CORREO_ADMIN          default admin.rol@gmail.com;  QA_CONTRASENA_ADMIN  (G4.1) contrasena del administrador
  QA_SECRET_SUSP, QA_SECRET_REV   (G4.1) client_secret de QA_M07_SUSP y QA_M07_REV (D14); ids publicos en
                           QA_CLIENT_ID_SUSP (default qa-m07-susp) y QA_CLIENT_ID_REV (default qa-m07-rev)
  QA_CONTRASENA_CONTADOR   (G4.5, G4.8) contrasena web del contador, para leer los Anexos
  QA_CORREO_PRODUCTOR      default daniiella.vargass@gmail.com;  QA_CONTRASENA_PRODUCTOR  (G4.5) usuario sin el perfil del Contador
  QA_NIT                   default 901444215 (D01)
  QA_BASE_URL              default https://api.inmero.co/api-sgpmp-test

Lo que no se pueda ejecutar queda BLOQUEADO con el motivo; nunca se da por aprobado sin ejecutarse.

Desde la raiz de sgpmp-backend (cada secreto con read -s + export, sin pegarlo en el chat):
    .venv/bin/python tests/Test_Testing/Test_Modulo7/RF-AE01/TC-M07-G062/ejecutar_tc_m07_g62.py
"""
from __future__ import annotations

import html
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

CASO, RF, RESPONSABLE = "TC-M07-G062", "RF-AE01 / RF-AE02", "Maria Jose"
CARPETA = Path(__file__).resolve().parent
RAIZ = CARPETA.parents[4]  # sgpmp-backend
RESULTADO = CARPETA / "Resultado"

BASE = os.environ.get("QA_BASE_URL", "https://api.inmero.co/api-sgpmp-test").rstrip("/")
NIT = os.environ.get("QA_NIT", "901444215")
CORREO = os.environ.get("QA_CORREO_CONTADOR", "contador@gmail.com")
CORREO_ADMIN = os.environ.get("QA_CORREO_ADMIN", "admin.rol@gmail.com")
CORREO_PRODUCTOR = os.environ.get("QA_CORREO_PRODUCTOR", "daniiella.vargass@gmail.com")
CLIENT_ID = os.environ.get("QA_CLIENT_ID_AAEF", "qa-m07-aaef")
ID_SUSP = os.environ.get("QA_CLIENT_ID_SUSP", "qa-m07-susp")
ID_REV = os.environ.get("QA_CLIENT_ID_REV", "qa-m07-rev")
SANDBOX = os.environ.get("QA_SANDBOX_SECRET", "")
RANGO_SUGERIDO = "2026-10-01 a 2026-10-31"
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
    "G4.1": ("Cliente de canal suspendido y revocado", "Alta", "403 CLIENTE_NO_AUTORIZADO en ambos casos (token emitido antes)"),
    "G4.2": ("Usuario que no tiene todas las fincas del titular", "Alta", "Alcance parcial: 403 ALCANCE_INSUFICIENTE; con todas las fincas: 200"),
    "G4.3": ("Rango no alineado a periodos", "Alta", "422 RANGO_NO_ALINEADO con el rango valido sugerido"),
    "G4.4": ("Rango que incluye un periodo abierto", "Alta", "422 PERIODO_NO_CERRADO"),
    "G4.5": ("Pasar a EN_REVISION sin la aprobacion interna del Contador", "Alta",
             "Sin aprobacion interna se rechaza y el Anexo sigue en BORRADOR; con ella avanza a EN_REVISION"),
    "G4.6": ("Pasar a APROBADO sin evidencia de interoperabilidad", "Alta",
             "Sin ExchangeId o con ACK distinto de aceptado al 100 % se rechaza; con la evidencia avanza"),
    "G4.7": ("Transiciones de estado invalidas del Anexo", "Media",
             "Solo BORRADOR -> EN_REVISION -> APROBADO; las demas se rechazan sin cambiar el estado"),
    "G4.8": ("Modificar un Anexo APROBADO", "Alta",
             "Se rechaza y el Anexo no cambia; un cambio crea un Anexo nuevo en BORRADOR"),
}


class Variante:
    """Una peticion de TEST: lo esperado contra lo obtenido. Lee el cuerpo estandar {error_code, message, fields}."""

    def __init__(self, etiqueta, st, crudo, http, codigo, con_field=False, contiene=None):
        cuerpo = json_o_none(crudo)
        cuerpo = cuerpo if isinstance(cuerpo, dict) else {}
        campos = cuerpo.get("fields")
        self.st, self.cuerpo = st, cuerpo
        self.codigo = cuerpo.get("error_code") or cuerpo.get("code")
        self.field = campos[0].get("field") if isinstance(campos, list) and campos and isinstance(campos[0], dict) else None
        self.mensaje = str(cuerpo.get("message") or "")
        self.ok = (st == http and self.codigo == codigo and (not con_field or bool(self.field))
                   and (contiene is None or contiene in self.mensaje))
        extra = (f" field={self.field}" if con_field else "") + (
            f" texto «{contiene}» {'presente' if contiene in self.mensaje else 'AUSENTE'}" if contiene else "")
        self.texto = (f"{etiqueta}: HTTP {st} {self.codigo or '-'}{extra} (esperado {http} {codigo or 'sin error'}) "
                      f"{'OK' if self.ok else 'FALLA'}")

    @staticmethod
    def manual(texto, ok):
        v = Variante.__new__(Variante)
        v.texto, v.ok = f"{texto}: {'OK' if ok else 'FALLA'}", ok
        return v


class Ritmo:
    """Mantiene como maximo 4 consultas AAEF contadas por minuto (el limite del cliente es 5)."""

    def __init__(self):
        self.marcas: list[float] = []

    def esperar(self):
        ahora_ = time.monotonic()
        self.marcas = [m for m in self.marcas if ahora_ - m < 61]
        if len(self.marcas) >= 4:
            pausa = 61 - (ahora_ - self.marcas[0])
            print(f"  (pausa de {int(pausa) + 1} s para respetar el limite de consultas por minuto)", flush=True)
            time.sleep(pausa + 1)
            self.marcas = [m for m in self.marcas if time.monotonic() - m < 61]
        self.marcas.append(time.monotonic())


def token_canal(client_id, secreto, correo):
    SECRETOS.append(secreto)
    st, _, crudo = pedir("POST", "/integraciones/agrofusion/token",
                         {"client_id": client_id, "client_secret": secreto, "email": correo})
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
    return j if isinstance(j, list) else next((v for v in (j or {}).values() if isinstance(v, list)), []) if isinstance(j, dict) else []


# --- Parte A: consulta AAEF de solo lectura (G4.2, G4.3, G4.4) ---------------------------------------

def parte_aaef(res, peticiones):
    secreto = os.environ.get("QA_SECRET_AAEF", "")
    if not secreto:
        for sid in ("G4.2", "G4.3", "G4.4"):
            res[sid][1].append("falta QA_SECRET_AAEF; no se hizo ninguna consulta AAEF a TEST")
        return
    st, token, datos = token_canal(CLIENT_ID, secreto, CORREO)
    peticiones.append({"paso": "Emitir token de canal (contador)", "http": st, "utc": ahora()})
    if st != 200 or not token:
        for sid in ("G4.2", "G4.3", "G4.4"):
            res[sid][1].append(f"no se pudo emitir el token de canal (HTTP {st} {datos.get('error_code') or ''})")
        return
    ritmo = Ritmo()

    def consulta(nombre, desde, hasta, tok):
        ritmo.esperar()
        ruta = f"/integracion/aaef/productores/{NIT}?desde={desde}&hasta={hasta}"
        st_, _, crudo = pedir("GET", ruta, token=tok)
        peticiones.append({"paso": nombre, "metodo": "GET", "ruta": enmascarar(ruta), "http": st_, "utc": ahora()})
        return st_, crudo

    # G4.3
    for etiqueta, d, h in (("inicio a mitad de periodo", "2026-10-05", "2026-10-31"),
                           ("fin a mitad de periodo", "2026-10-01", "2026-10-20")):
        s, c = consulta(f"G4.3 {etiqueta}", d, h, token)
        res["G4.3"][0].append(Variante(f"{etiqueta} ({d} a {h})", s, c, 422, "RANGO_NO_ALINEADO",
                                       con_field=True, contiene=RANGO_SUGERIDO))
    # G4.4: octubre cerrado + noviembre abierto (D01: periodos 627 y 628)
    s, c = consulta("G4.4 cerrado + abierto", "2026-10-01", "2026-11-30", token)
    res["G4.4"][0].append(Variante("un periodo cerrado seguido de uno abierto (2026-10-01 a 2026-11-30)", s, c, 422,
                                   "PERIODO_NO_CERRADO"))
    # G4.2: usuario con todas las fincas (200) y usuario con una parte (403)
    s, c = consulta("G4.2 todas las fincas", "2026-09-01", "2026-10-31", token)
    cuerpo = json_o_none(c)
    todas = s == 200 and isinstance(cuerpo, dict) and sorted(cuerpo) == ["invoices", "metadata", "summary", "transactions"]
    res["G4.2"][0].append(Variante.manual(f"usuario con todas las fincas: HTTP {s} (esperado 200 con el envelope)", todas))
    correo_parcial = os.environ.get("QA_CORREO_PARCIAL", "")
    if not correo_parcial:
        res["G4.2"][1].append("falta QA_CORREO_PARCIAL (correo del usuario D04 con solo 2 de las 3 fincas)")
        return
    s2, tok2, d2 = token_canal(CLIENT_ID, secreto, correo_parcial)
    peticiones.append({"paso": "Emitir token de canal (usuario parcial)", "http": s2, "utc": ahora()})
    if s2 != 200 or not tok2:
        res["G4.2"][1].append(f"no se pudo emitir el token del usuario parcial (HTTP {s2} {d2.get('error_code') or ''})")
        return
    s, c = consulta("G4.2 alcance parcial", "2026-09-01", "2026-10-31", tok2)
    res["G4.2"][0].append(Variante("usuario con solo una parte de las fincas", s, c, 403, "ALCANCE_INSUFICIENTE"))


# --- Parte B: sandbox (G4.1, y las variantes de TEST de G4.5 y G4.8) --------------------------------

class Run:
    """Un run del sandbox: cabeceras en cada peticion, eco comprobado y DELETE final garantizado."""

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
        self.cierre_http, self.cerrado = st, st in (200, 404)  # 404: nunca se abrio / ya cerrado
        if st not in (200, 404):
            ALERTAS.append(f"ATENCION: no se pudo cerrar el run {self.id} (HTTP {st}). Avisar al DBA para liberar la sesion.")


def parte_sandbox(res, peticiones):
    if not SANDBOX:
        for sid in ("G4.1", "G4.5", "G4.8"):
            res[sid][1].append("TEST: falta QA_SANDBOX_SECRET; las pruebas que escriben (aunque con rollback) no se ejecutan")
        return
    # Sesiones y datos previos, FUERA del run (el login no va en el run).
    clave_admin = os.environ.get("QA_CONTRASENA_ADMIN", "")
    clave_contador = os.environ.get("QA_CONTRASENA_CONTADOR", "")
    clave_prod = os.environ.get("QA_CONTRASENA_PRODUCTOR", "")
    tok_admin = tok_contador = tok_prod = None
    if clave_admin:
        s, tok_admin = sesion_web(CORREO_ADMIN, clave_admin)
        if s != 200:
            res["G4.1"][1].append(f"el login del administrador devolvio HTTP {s}")
            tok_admin = None
    else:
        res["G4.1"][1].append("falta QA_CONTRASENA_ADMIN")
    if clave_contador:
        s, tok_contador = sesion_web(CORREO, clave_contador)
        if s != 200:
            tok_contador = None
    for sid in ("G4.5", "G4.8"):
        if not tok_contador:
            res[sid][1].append("TEST: falta QA_CONTRASENA_CONTADOR (o el login fallo) para leer los Anexos")
    if clave_prod:
        s, tok_prod = sesion_web(CORREO_PRODUCTOR, clave_prod)
        if s != 200:
            tok_prod = None
    if not tok_prod:
        res["G4.5"][1].append("TEST: falta QA_CONTRASENA_PRODUCTOR (usuario sin el perfil del Contador) o el login fallo")

    # Datos previos de G4.1: clientes ACTIVO y sus tokens (emitidos antes de suspender/revocar).
    susp = rev = tok_susp = tok_rev = None
    secreto_susp, secreto_rev = os.environ.get("QA_SECRET_SUSP", ""), os.environ.get("QA_SECRET_REV", "")
    estados_antes: dict = {}
    if tok_admin:
        st, _, crudo = pedir("GET", "/integracion/clientes", token=tok_admin)
        clientes = lista(crudo) if st == 200 else []
        estados_antes = {c.get("identificador_publico"): c.get("estado") for c in clientes}
        susp = next((c for c in clientes if c.get("identificador_publico") == ID_SUSP), None)
        rev = next((c for c in clientes if c.get("identificador_publico") == ID_REV), None)
        if not susp or not rev:
            res["G4.1"][1].append(f"no se encontraron los clientes {ID_SUSP} y {ID_REV} en GET /integracion/clientes")
            susp = rev = None
        elif susp.get("estado") != "ACTIVO" or rev.get("estado") != "ACTIVO":
            res["G4.1"][1].append(f"los clientes no estan ACTIVO antes de la prueba ({susp.get('estado')} / {rev.get('estado')})")
            susp = rev = None
        elif not secreto_susp or not secreto_rev:
            res["G4.1"][1].append("falta QA_SECRET_SUSP o QA_SECRET_REV")
            susp = rev = None
        else:
            s1, tok_susp, d1 = token_canal(ID_SUSP, secreto_susp, CORREO)
            s2, tok_rev, d2 = token_canal(ID_REV, secreto_rev, CORREO)
            peticiones.append({"paso": "Emitir tokens de los clientes desechables", "http": f"{s1}/{s2}", "utc": ahora()})
            if not tok_susp or not tok_rev:
                res["G4.1"][1].append(f"no se pudieron emitir los tokens (HTTP {s1}/{s2} {d1.get('error_code') or ''} {d2.get('error_code') or ''})")
                susp = rev = None

    # Anexos previos de G4.5 y G4.8 (lectura).
    borrador = aprobado = None
    anexos_antes = []
    if tok_contador:
        st, _, crudo = pedir("GET", "/integracion/anexos", token=tok_contador)
        anexos_antes = lista(crudo) if st == 200 else []
        borrador = max((a for a in anexos_antes if a.get("estado") == "BORRADOR"), key=lambda a: a["id_mapeo_anexo_aaef"], default=None)
        aprobado = max((a for a in anexos_antes if a.get("estado") == "APROBADO"), key=lambda a: a["id_mapeo_anexo_aaef"], default=None)
        if not borrador:
            res["G4.5"][1].append("TEST: no hay ningun Anexo en BORRADOR para probar el rechazo")
        if not aprobado:
            res["G4.8"][1].append("TEST: no hay ningun Anexo APROBADO para probar la modificacion")

    hay_algo = (susp and rev) or (tok_prod and borrador) or (tok_contador and aprobado)
    if not hay_algo:
        return
    run = Run(SANDBOX)
    try:
        # Comprobacion de seguridad: el servidor debe devolver el eco del run antes de escribir.
        st, eco, _ = run.pedir("GET", "/integracion/clientes", token=tok_admin or tok_contador)
        peticiones.append({"paso": "Comprobar el eco del run", "http": st, "eco": eco, "utc": ahora()})
        if not eco:
            for sid in ("G4.1", "G4.5", "G4.8"):
                res[sid][1].append("TEST: el sandbox no devolvio el eco X-Test-Run-Id; no se escribio nada")
            return

        if susp and rev:   # G4.1
            for etiqueta, accion, cliente, tok in (("suspendido", "suspender", susp, tok_susp), ("revocado", "revocar", rev, tok_rev)):
                s, eco, c = run.pedir("POST", f"/integracion/clientes/{cliente['id_cliente_externo']}/{accion}",
                                      {"motivo": "TC-M07-G062: prueba dentro del sandbox, se revierte"}, tok_admin)
                peticiones.append({"paso": f"G4.1 {accion}", "http": s, "eco": eco, "utc": ahora()})
                if s != 200 or not eco:
                    res["G4.1"][0].append(Variante.manual(f"no se pudo {accion} el cliente (HTTP {s}, eco={eco})", False))
                    break
                ruta = f"/integracion/aaef/productores/{NIT}?desde=2026-09-01&hasta=2026-10-31"
                s, eco, c = run.pedir("GET", ruta, token=tok)
                peticiones.append({"paso": f"G4.1 consulta con el token del cliente {etiqueta}", "http": s, "eco": eco, "utc": ahora()})
                res["G4.1"][0].append(Variante(f"cliente {etiqueta}, token emitido antes", s, c, 403, "CLIENTE_NO_AUTORIZADO"))

        if tok_prod and borrador:   # G4.5: usuario sin el perfil intenta la aprobacion interna
            ida = borrador["id_mapeo_anexo_aaef"]
            s, eco, c = run.pedir("POST", f"/integracion/anexos/{ida}/revision", None, tok_prod)
            peticiones.append({"paso": "G4.5 revision sin el perfil", "http": s, "eco": eco, "utc": ahora()})
            v = Variante("usuario sin el perfil del Contador intenta pasar el Anexo a revision", s, c, 403, "ACCESO_DENEGADO")
            s2, _, c2 = run.pedir("GET", "/integracion/anexos", token=tok_contador)
            sigue = next((a for a in lista(c2) if a.get("id_mapeo_anexo_aaef") == ida), {}).get("estado") == "BORRADOR"
            res["G4.5"][0].extend([v, Variante.manual(f"el Anexo {ida} sigue en BORRADOR", sigue)])

        if tok_contador and aprobado:   # G4.8: intentar modificar un Anexo APROBADO
            ida = aprobado["id_mapeo_anexo_aaef"]
            for metodo in ("PATCH", "PUT"):
                s, eco, c = run.pedir(metodo, f"/integracion/anexos/{ida}", {"ruta_documento": "docs/qa-modificado.md"}, tok_contador)
                peticiones.append({"paso": f"G4.8 {metodo} sobre un Anexo APROBADO", "http": s, "eco": eco, "utc": ahora()})
                cuerpo = json_o_none(c) if isinstance(json_o_none(c), dict) else {}
                codigo = cuerpo.get("error_code")
                # TC-M07-290 / RF-AE02 CA-8 pide que se rechace y que el Anexo no cambie; no exige un codigo de error
                # (a diferencia de RF-98 con MODIFICACION_NO_PERMITIDA en contratos). Basta un 4xx.
                ok = s is not None and 400 <= s < 500
                res["G4.8"][0].append(Variante.manual(
                    f"{metodo} sobre el Anexo APROBADO {ida}: HTTP {s} rechazado"
                    + ("" if codigo else f" [observacion: respuesta generica {str(cuerpo)[:40]} sin error_code estandar; RF-AE02 no exige un codigo]"), ok))
            s, _, c = run.pedir("GET", "/integracion/anexos", token=tok_contador)
            igual = next((a for a in lista(c) if a.get("id_mapeo_anexo_aaef") == ida), None) == aprobado
            res["G4.8"][0].append(Variante.manual(f"el Anexo APROBADO {ida} no cambio", igual))
    finally:
        run.cerrar()
        peticiones.append({"paso": "Cerrar el run (rollback)", "http": run.cierre_http, "utc": ahora()})
    # Verificacion del rollback: los clientes y los Anexos vuelven a su estado previo.
    if tok_admin and estados_antes:
        st, _, crudo = pedir("GET", "/integracion/clientes", token=tok_admin)
        despues = {c.get("identificador_publico"): c.get("estado") for c in lista(crudo)} if st == 200 else None
        if despues != estados_antes:
            ALERTAS.append("ATENCION: el estado de los clientes despues del rollback no coincide con el de antes. Avisar al DBA.")
    if tok_contador and anexos_antes:
        st, _, crudo = pedir("GET", "/integracion/anexos", token=tok_contador)
        if st != 200 or lista(crudo) != anexos_antes:
            ALERTAS.append("ATENCION: la lista de Anexos despues del rollback no coincide con la de antes. Avisar al DBA.")


# --- pytest local y armado ---------------------------------------------------------------------------

def parte_pytest():
    RESULTADO.mkdir(exist_ok=True)
    xml_ruta = RESULTADO / "pytest_g62_anexo.xml"
    r = subprocess.run([sys.executable, "-m", "pytest", str(CARPETA / "test_tc_m07_g62_anexo.py"), "-v", "-s",
                        "-p", "no:cacheprovider", f"--junitxml={xml_ruta}"], cwd=RAIZ, capture_output=True, text=True)
    (RESULTADO / "pytest_g62_anexo.txt").write_text(r.stdout + r.stderr, encoding="utf-8")
    por: dict[str, list] = {}
    if xml_ruta.exists():
        for tc in ET.parse(xml_ruta).getroot().iter("testcase"):
            nombre = tc.get("name", "")
            falla = tc.find("failure") if tc.find("failure") is not None else tc.find("error")
            por.setdefault(nombre[5:9].replace("_", ".").upper(), []).append(
                (nombre[10:], falla is None, (falla.get("message", "") if falla is not None else "").replace("\n", " ")[:180]))
    return por


LOCALES = ("G4.5", "G4.6", "G4.7", "G4.8")


def armar(res, locales):
    esc = []
    for sid, (nombre, prio, esperado) in INFO.items():
        variantes, faltan = res[sid]
        partes = [v.texto for v in variantes] + [f"NO EJECUTADA EN TEST: {m}" for m in faltan]
        filas = locales.get(sid)
        malas = []
        if sid in LOCALES:
            if filas:
                malas = [f"{n} ({m})" for n, ok, m in filas if not ok]
                partes.append(f"pytest: {len(filas) - len(malas)}/{len(filas)} comprobaciones pasan"
                              + (f"; FALLAN: {'; '.join(malas)}" if malas else ""))
            else:
                partes.append("pytest no ejecuto este subcaso")
        if malas or any(not v.ok for v in variantes):
            estado = "RECHAZADO"
        elif faltan or (sid in LOCALES and not filas) or (sid not in LOCALES and not variantes):
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
            f"<h1>{CASO} — Reglas de acceso, de periodos y del ciclo de vida del Anexo</h1><p><b>RF:</b> {RF} · "
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
        parte_aaef(res, peticiones)
        parte_sandbox(res, peticiones)
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
