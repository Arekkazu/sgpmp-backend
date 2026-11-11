"""Preparación de TC-M06-G102, subcasos 16, 17 y 18. Solo lectura por defecto.

No abre conexión a base de datos. Un POST /finanzas/precios sale únicamente si
TC_AUTORIZAR_POST es 17 o 18, o si es 16 y además TC_G108_EJECUTADO es 424.
Cada invocación autorizada envía un solo POST y no lo reintenta.

    python tests/Test_Testing/Test_Modulo6/RF-89/TC-M06-G102/preparar_tc_m06_g102.py
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from decimal import Decimal

BASE_API = "https://api.inmero.co/api-sgpmp-test"
ZONA = "America/Bogota"
ESPECIE = 424
TIMEOUT = 90
HOY = datetime.now(timezone(timedelta(hours=-5))).date().isoformat()
JUSTIFICACION_18 = (
    "No existe una transacción observada que permita usar MERCADO_ACTIVO para esta estimación. "
    "No se toma el boletín UPRA como fuente de este valor. "
    "Los comparables son referencias internas de ovinos de QA para la especie 424."
)

CUERPOS = {
    "16": {
        "id_especie": ESPECIE,
        "categoria": "POR_CABEZA",
        "precio_unitario": "5000000.00",
        "fecha_vigencia": HOY,
        "fuente": "MERCADO_ACTIVO",
        "evidencia_documental": "Acta de feria QA TC-M06-16, mercado de referencia de Ovino Qa Precios.",
        "confirmar_desviacion": False,
    },
    "17": {
        "id_especie": ESPECIE,
        "categoria": "POR_CABEZA",
        "precio_unitario": "4800000.00",
        "fecha_vigencia": HOY,
        "fuente": "UPRA",
        "evidencia_documental": "Boletín UPRA QA TC-M06-17, referencia de precio de Ovino Qa Precios.",
        "confirmar_desviacion": False,
    },
    "18": {
        "id_especie": ESPECIE,
        "categoria": "POR_CABEZA",
        "precio_unitario": "4500000.00",
        "fecha_vigencia": HOY,
        "fuente": "ESTIMADA",
        "evidencia_documental": "Descripción del mercado de referencia QA TC-M06-18 para Ovino Qa Precios.",
        "justificacion_estimacion": JUSTIFICACION_18,
        "confirmar_desviacion": False,
    },
}


def pedir(metodo: str, ruta: str, cuerpo: dict | None = None, token: str | None = None):
    if metodo != "GET" and ruta != "/sesiones/" and not (metodo == "POST" and ruta == "/finanzas/precios"):
        raise RuntimeError("Ruta no permitida")
    if metodo == "POST" and ruta == "/finanzas/precios":
        if not isinstance(cuerpo, dict) or cuerpo.get("id_especie") != ESPECIE:
            raise RuntimeError("El POST solo puede usar la especie 424")
        if "cierre" in ruta:
            raise RuntimeError("Este caso no cierra períodos")
    datos = None if cuerpo is None else json.dumps(cuerpo).encode("utf-8")
    headers = {"Accept": "application/json", "X-Zona-Horaria": ZONA}
    if cuerpo is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(BASE_API + ruta, data=datos, headers=headers, method=metodo)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {"message": raw[:240]}
        return exc.code, payload


def login() -> str:
    correo, contrasena = os.environ.get("QA_CORREO"), os.environ.get("QA_CONTRASENA")
    if not correo or not contrasena:
        raise SystemExit("Defina QA_CORREO y QA_CONTRASENA. No las escriba en el archivo.")
    codigo, payload = pedir("POST", "/sesiones/", {"correo_electronico": correo, "contrasena": contrasena})
    token = payload.get("token") if isinstance(payload, dict) else None
    if codigo != 200 or not token:
        raise SystemExit("No fue posible autenticar al Contador.")
    codigo_me, perfil = pedir("GET", "/usuarios/me", token=token)
    rol = perfil.get("rol") if isinstance(perfil, dict) else None
    if isinstance(rol, dict):
        rol = rol.get("nombre") or rol.get("nombre_rol")
    elif isinstance(perfil, dict):
        rol = perfil.get("nombre_rol") or rol
    if codigo_me != 200 or "contad" not in str(rol or "").lower():
        raise SystemExit("La sesión no corresponde al Contador.")
    return token


def precios_especie(token: str) -> list[dict]:
    codigo, payload = pedir("GET", f"/finanzas/precios?id_especie={ESPECIE}", token=token)
    if codigo != 200 or not isinstance(payload, list):
        raise SystemExit("No se pudo leer el catálogo de la especie 424.")
    return [p for p in payload if isinstance(p, dict)]


def ya_registrado(lista: list[dict], cuerpo: dict) -> bool:
    for precio in lista:
        if precio.get("fuente") == cuerpo["fuente"] and Decimal(str(precio.get("precio_unitario"))) == Decimal(cuerpo["precio_unitario"]):
            return True
    return False


def main() -> int:
    if len(JUSTIFICACION_18.strip()) < 50:
        raise SystemExit("La justificación del subcaso 18 no llega a 50 caracteres.")
    for cuerpo in CUERPOS.values():
        evidencia = cuerpo["evidencia_documental"].strip()
        if not 1 <= len(evidencia) <= 500 or cuerpo["categoria"] != "POR_CABEZA":
            raise SystemExit("Un cuerpo preparado no cumple el DTO.")
    token = login()
    lista = precios_especie(token)
    autorizacion = os.environ.get("TC_AUTORIZAR_POST")
    if autorizacion not in {"16", "17", "18"}:
        print(f"LECTURA especie 424 precios {len(lista)} post False")
        return 0
    if autorizacion == "16" and os.environ.get("TC_G108_EJECUTADO") != str(ESPECIE):
        print("BLOQUEADO subcaso 16: TC-M06-32 y TC-M06-33 no están confirmados. No se envió el POST.")
        return 3
    cuerpo = CUERPOS[autorizacion]
    lista = precios_especie(token)
    if ya_registrado(lista, cuerpo):
        print("BLOQUEADO: ese precio ya existe. No se envió el POST.")
        return 3
    try:
        codigo, _respuesta = pedir("POST", "/finanzas/precios", cuerpo, token)
    except (TimeoutError, urllib.error.URLError) as exc:
        print(f"POST incierto: {type(exc).__name__}. No se reintenta. Consulte GET /finanzas/precios?id_especie=424.")
        return 4
    print(f"POST {codigo} subcaso {autorizacion}")
    return 0 if codigo == 201 else 2


if __name__ == "__main__":
    raise SystemExit(main())
