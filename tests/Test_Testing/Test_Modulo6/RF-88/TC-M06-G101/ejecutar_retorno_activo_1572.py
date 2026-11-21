"""Lectura y, solo con autorización explícita, retorno a valor razonable de TC-M06-G101.

Usa únicamente el activo 1572. No cierra períodos, no usa el 1573 y no usa el 951.

    python tests/Test_Testing/Test_Modulo6/RF-88/TC-M06-G101/ejecutar_retorno_activo_1572.py

El POST no forma parte de la ejecución por defecto. Solo se envía si el entorno
define TC_AUTORIZAR_POST=1572 y todas las lecturas coinciden con el escenario.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

CARPETA = Path(__file__).resolve().parent
SALIDA = CARPETA / "resultados" / "ultima_evaluacion" / "preparacion_activo_1572.json"
BASE_API = "https://api.inmero.co/api-sgpmp-test"
ZONA = "America/Bogota"
ACTIVO = 1572
CODIGO = "QA-M06O-COSTO-01"
NIT = "900000003"
FINCA = 467
ESPECIE = 423
PERIODO = 220
PROHIBIDOS = {951, 1569, 1570, 1571, 1573, 1574}
PRECIO_ESPERADO = Decimal("4300000")
VALOR_COSTO_ESPERADO = Decimal("4200000")
NETO_ESPERADO = Decimal("4042000")
DIFERENCIA_ESPERADA = Decimal("-158000")


def exigir_activo(id_activo: int) -> None:
    if id_activo in PROHIBIDOS or id_activo != ACTIVO:
        raise SystemExit(f"Operación rechazada: solo se admite el activo {ACTIVO}.")


def pedir(metodo: str, ruta: str, cuerpo: dict | None = None, token: str | None = None):
    if metodo != "GET" and ("cierre" in ruta or f"/{PERIODO}/" in ruta or ruta.endswith(f"/{PERIODO}")):
        raise SystemExit("Este ejecutor no cierra períodos.")
    if metodo != "GET" and any(f"/{prohibido}" in ruta or ruta.endswith(str(prohibido)) for prohibido in PROHIBIDOS):
        raise SystemExit("La ruta de escritura apunta a un activo fuera del caso.")
    datos = None if cuerpo is None else json.dumps(cuerpo).encode("utf-8")
    headers = {"Accept": "application/json", "X-Zona-Horaria": ZONA}
    if cuerpo is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(BASE_API + ruta, data=datos, headers=headers, method=metodo)
    inicio = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            raw = resp.read().decode("utf-8")
            payload = json.loads(raw) if raw else None
            codigo = resp.status
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {"message": raw[:400]}
        codigo = exc.code
    except TimeoutError as exc:
        return 0, {"error": "timeout", "detalle": str(exc)}, round((time.perf_counter() - inicio) * 1000)
    return codigo, payload, round((time.perf_counter() - inicio) * 1000)


def decimal(valor) -> Decimal | None:
    if valor is None:
        return None
    return Decimal(str(valor).split(".")[0] + (("." + str(valor).split(".")[1][:2]) if "." in str(valor) else ""))


def main() -> int:
    exigir_activo(ACTIVO)
    correo, contrasena = os.environ.get("QA_CORREO"), os.environ.get("QA_CONTRASENA")
    if not correo or not contrasena:
        raise SystemExit("Defina QA_CORREO y QA_CONTRASENA. No las escriba en el archivo.")
    codigo, login, _ = pedir("POST", "/sesiones/", {"correo_electronico": correo, "contrasena": contrasena})
    token = login.get("token") if isinstance(login, dict) else None
    if codigo != 200 or not token:
        print(f"SIN_SESION http={codigo}")
        return 2
    codigo_me, perfil, _ = pedir("GET", "/usuarios/me", token=token)
    rol = perfil.get("rol") if isinstance(perfil, dict) else None
    if isinstance(rol, dict):
        rol = rol.get("nombre")
    elif isinstance(perfil, dict):
        rol = perfil.get("nombre_rol") or rol
    if codigo_me != 200 or "contad" not in str(rol or "").lower():
        print("ROL_NO_CONTADOR")
        return 2

    codigo_a, historial, _ = pedir("GET", f"/finanzas/activos/{ACTIVO}", token=token)
    activo = (historial or {}).get("activo") if isinstance(historial, dict) else {}
    costo = (historial or {}).get("valoracion_costo") if isinstance(historial, dict) else None
    codigo_s, simulacion, _ = pedir("GET", f"/finanzas/activos/{ACTIVO}/simulacion", token=token)
    codigo_p, precios, _ = pedir("GET", f"/finanzas/precios?id_especie={ESPECIE}", token=token)
    codigo_per, periodos, _ = pedir("GET", f"/finanzas/periodos?numero_id_tributaria={NIT}", token=token)
    codigo_cfg, config, _ = pedir("GET", "/finanzas/configuracion", token=token)
    codigo_aud, auditoria, _ = pedir(
        "GET",
        f"/finanzas/auditoria?id_activo_biologico={ACTIVO}&tipo_evento=METODO_VALORACION_CAMBIADO&formato=TECNICO&tamano=20",
        token=token,
    )
    protegido_c, protegido, _ = pedir("GET", "/finanzas/activos/1573", token=token)

    periodo = next((p for p in periodos if isinstance(p, dict) and p.get("id_periodo_contable") == PERIODO), None) if isinstance(periodos, list) else None
    costos = [c for c in ((config or {}).get("costos_venta") or []) if isinstance(c, dict) and c.get("id_especie") == ESPECIE] if isinstance(config, dict) else []
    calculo = (simulacion or {}).get("calculo") if isinstance(simulacion, dict) else None
    precio = (simulacion or {}).get("precio") if isinstance(simulacion, dict) else None
    diferencias = []
    if codigo_a != 200:
        diferencias.append(f"historial http {codigo_a}")
    if activo.get("identificador") != CODIGO or activo.get("estado") != "ACTIVO":
        diferencias.append("identificador o estado distinto")
    if activo.get("id_finca") != FINCA or activo.get("numero_id_tributaria") != NIT or activo.get("id_especie") != ESPECIE:
        diferencias.append("finca, titular o especie distintos")
    if not isinstance(costo, dict) or costo.get("es_activa") is not True:
        diferencias.append("no hay valoración por costo activa")
    if decimal(costo.get("valor_contable_por_costo") if isinstance(costo, dict) else None) != VALOR_COSTO_ESPERADO:
        diferencias.append("valor contable distinto de 4200000")
    if codigo_s != 200 or not isinstance(simulacion, dict) or simulacion.get("es_valido") is not True:
        diferencias.append("la simulación no es válida")
    if not isinstance(precio, dict) or precio.get("fuente") != "MERCADO_ACTIVO" or decimal(precio.get("precio_unitario")) != PRECIO_ESPERADO:
        diferencias.append("el precio simulado no es 4300000 MERCADO_ACTIVO")
    if not isinstance(calculo, dict) or decimal(calculo.get("valor_neto")) != NETO_ESPERADO:
        diferencias.append("el valor neto simulado no es 4042000")
    vigente = next((c for c in costos if c.get("es_activo") is True and c.get("region") == "GENERAL"), None)
    if not vigente or (Decimal(str(vigente.get("pct_transporte"))), Decimal(str(vigente.get("pct_comisiones"))), Decimal(str(vigente.get("pct_impuestos")))) != (Decimal("0.02"), Decimal("0.03"), Decimal("0.01")):
        diferencias.append("los costos de venta GENERAL no son 2, 3 y 1 por ciento")
    if not periodo or periodo.get("estado") != "ABIERTO" or periodo.get("numero_id_tributaria") != NIT:
        diferencias.append("el período 220 no está abierto para el titular aislado")
    if protegido_c == 200 and isinstance(protegido, dict):
        otro = protegido.get("valoracion_costo") or {}
        if otro.get("es_activa") is not True:
            diferencias.append("el activo 1573 ya no está al costo; no se continúa")
    informe = {
        "caso": "TC-M06-G101",
        "activo": ACTIVO,
        "post_enviado": False,
        "rol": rol,
        "diferencias": diferencias,
        "periodo_220": None if not periodo else {"estado": periodo.get("estado"), "inicio": periodo.get("fecha_inicio"), "fin": periodo.get("fecha_fin")},
        "simulacion_http": codigo_s,
        "precios_http": codigo_p,
        "costos_venta_especie_423": costos,
        "eventos_cambio_metodo": auditoria.get("total_registros") if isinstance(auditoria, dict) else None,
        "valor_neto": None if not isinstance(calculo, dict) else calculo.get("valor_neto"),
        "valor_costo": None if not isinstance(costo, dict) else costo.get("valor_contable_por_costo"),
    }
    if diferencias or os.environ.get("TC_AUTORIZAR_POST") != str(ACTIVO):
        SALIDA.parent.mkdir(parents=True, exist_ok=True)
        SALIDA.write_text(json.dumps(informe, ensure_ascii=False, indent=2), encoding="utf-8")
        print("LECTURA", "diferencias", len(diferencias), "post", False)
        return 0 if not diferencias else 3

    codigo_post, respuesta, _ = pedir("POST", f"/finanzas/activos/{ACTIVO}/valor-razonable", token=token)
    informe["post_enviado"] = True
    informe["post_http"] = codigo_post
    informe["post_respuesta"] = {k: respuesta.get(k) for k in ("id_activo_biologico", "valor_razonable", "valor_por_costo", "diferencia", "error_code", "message")} if isinstance(respuesta, dict) else {"tipo": type(respuesta).__name__}
    SALIDA.write_text(json.dumps(informe, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print("POST", codigo_post)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
