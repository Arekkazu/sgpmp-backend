"""TC-M06-G89 contra TEST.

El cero y el negativo fallan en el DTO. La fecha anterior a hoy falla antes
de consultar activos. Omitir el vencimiento solo se envía con un activo que
no tiene valor razonable, para no crear una cotización.

    python tests/Test_Testing/Test_Modulo6/RF-COT/TC-M06-G89/ejecutar_tc_m06_g89.py
"""
from __future__ import annotations

import html
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path

CARPETA = Path(__file__).resolve().parent
RESULTADOS = CARPETA / "resultados"
BASE_API = "https://api.inmero.co/api-sgpmp-test"
ZONA = "America/Bogota"
OMITIR = {"token", "access_token", "contrasena", "password", "hash_integridad", "numero_id_tributaria",
          "identificador", "finca", "condiciones"}


def pedir(metodo: str, ruta: str, cuerpo: dict | None = None, token: str | None = None):
    datos = None if cuerpo is None else json.dumps(cuerpo).encode()
    headers = {"Accept": "application/json", "X-Zona-Horaria": ZONA}
    if cuerpo is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(BASE_API + ruta, data=datos, headers=headers, method=metodo)
    inicio = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            raw = resp.read().decode()
            payload = json.loads(raw) if raw else None
            codigo = resp.status
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {"message": raw[:240]}
        codigo = exc.code
    except (TimeoutError, urllib.error.URLError) as exc:
        return None, {"message": type(exc).__name__}, round((time.perf_counter() - inicio) * 1000)
    return codigo, payload, round((time.perf_counter() - inicio) * 1000)


def limpiar(valor, profundidad: int = 0):
    if profundidad > 4:
        return "..."
    if isinstance(valor, dict):
        return {k: ({"omitido": True} if k in OMITIR else limpiar(v, profundidad + 1)) for k, v in valor.items()}
    if isinstance(valor, list):
        return [limpiar(v, profundidad + 1) for v in valor[:20]]
    if isinstance(valor, str):
        return valor.replace("QA-M06-", "activo ")[:240]
    return valor


def evidencia(metodo, ruta, codigo, duracion, respuesta, cuerpo=None) -> dict:
    return {"metodo": metodo, "consulta": ruta.split("?")[0], "codigo": codigo, "duracion_ms": duracion,
            "escritura": False, "en": datetime.now(ZoneInfo(ZONA)).isoformat(), "cuerpo": cuerpo,
            "respuesta": limpiar(respuesta)}


def negocio(payload) -> str | None:
    return payload.get("error_code") or payload.get("code") if isinstance(payload, dict) else None


def campos(payload) -> list:
    if not isinstance(payload, dict):
        return []
    return [f.get("field") for f in payload.get("fields") or [] if isinstance(f, dict)]


def ficha_cotizacion(item: dict) -> dict:
    return {"id_cotizacion": item.get("id_cotizacion"), "estado": item.get("estado"),
            "fecha_emision": item.get("fecha_emision"), "fecha_vencimiento": item.get("fecha_vencimiento"),
            "valor_cotizacion_propuesto": None if item.get("valor_cotizacion_propuesto") is None else str(item.get("valor_cotizacion_propuesto"))}


def subir(estados: list[str]) -> str:
    if estados and all(e == "APROBADO" for e in estados):
        return "APROBADO"
    if any(e == "RECHAZADO" for e in estados):
        return "RECHAZADO"
    if any(e == "REQUIERE ACLARACION" for e in estados):
        return "REQUIERE ACLARACION"
    return "BLOQUEADO"


def render(informe: dict) -> str:
    filas = "".join(
        "<tr>" + "".join(f"<td>{html.escape(str(e.get(k, '')))}</td>" for k in (
            "escenario", "subcaso", "http", "code", "esperado", "estado")) + "</tr>"
        for e in informe["escenarios"]
    )
    return f"""<!DOCTYPE html><html lang="es"><head><meta charset="utf-8"><title>TC-M06-G89</title>
<style>body{{font-family:Segoe UI,sans-serif;margin:2rem;line-height:1.45}}table{{border-collapse:collapse;width:100%}}
th,td{{border:1px solid #ccc;padding:.45rem .6rem;text-align:left;vertical-align:top}}th{{background:#f3f3f3}}</style></head><body>
<h1>Módulo 6 — RF-COT — TC-M06-G89</h1>
<p>Generado: {html.escape(informe['generado_en'])}. Aprobación: {informe['porcentaje_aprobacion']} %.</p>
<table><tr><th>Escenario</th><th>Subcaso</th><th>HTTP</th><th>Código</th><th>Esperado por el diseño</th><th>Estado</th></tr>{filas}</table>
<h2>Contrato</h2><pre>{html.escape(informe['contrato'])}</pre>
<h2>Hallazgos</h2><ul>{''.join(f'<li>{html.escape(h)}</li>' for h in informe['hallazgos'])}</ul>
</body></html>"""


def guardar(informe: dict) -> None:
    RESULTADOS.mkdir(parents=True, exist_ok=True)
    (RESULTADOS / "resultado_ejecucion_TC-M06-G89.html").write_text(render(informe), encoding="utf-8")
    (RESULTADOS / "resumen_ejecucion_TC-M06-G89.json").write_text(
        json.dumps({k: v for k, v in informe.items() if k != "analisis"}, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    (RESULTADOS / "evidencia_peticiones_TC-M06-G89.json").write_text(json.dumps({
        "caso": "TC-M06-G89", "generado_en": informe["generado_en"], "peticiones": informe["peticiones"],
        "newman_ejecutado": False,
    }, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    (RESULTADOS / "analisis_hallazgos_TC-M06-G89.md").write_text(informe["analisis"], encoding="utf-8")


def main() -> int:
    inicio = time.perf_counter()
    peticiones = []
    hoy = datetime.now(ZoneInfo(ZONA)).date()
    ayer = (hoy - timedelta(days=1)).isoformat()
    contrato = (
        "POST /finanzas/cotizaciones. valor_cotizacion_propuesto es Decimal, mayor que cero, con hasta 18 dígitos y 4 decimales. "
        "El cero y el negativo los rechaza el DTO con 400 VAL_ENTRADA, antes del caso de uso. "
        "El caso de uso también tiene 422 VALOR_COTIZACION_INVALIDO, pero esa línea no se alcanza por la API. "
        "fecha_emision no se envía: es la fecha de hoy en America/Bogota. fecha_vencimiento es opcional. "
        "Si viene y es anterior a hoy, responde 422 FECHA_VENCIMIENTO_INVALIDA antes de consultar activos y antes de insertar. "
        "Omitirla o enviarla nula no se rechaza por fecha. La columna admite nulo y exige, si hay fecha, que no sea anterior a la emisión. "
        "No hay un documento RF-COT v1.1 en el repositorio. La nota del caso de uso lo cita."
    )
    informe = {
        "caso": "TC-M06-G89", "ambiente": BASE_API, "generado_en": datetime.now(ZoneInfo(ZONA)).isoformat(),
        "hoy": hoy.isoformat(), "contrato": contrato, "especificacion_rfcot": "No está en el repositorio. Se usó el DTO, el caso de uso y la tabla modulo6.cotizaciones.",
        "escenarios": [], "peticiones": peticiones, "hallazgos": [], "newman_ejecutado": False,
    }
    correo, contrasena = os.environ.get("QA_CORREO"), os.environ.get("QA_CONTRASENA")
    if not correo or not contrasena:
        raise SystemExit("Defina QA_CORREO y QA_CONTRASENA.")
    codigo, login, duracion = pedir("POST", "/sesiones/", {"correo_electronico": correo, "contrasena": contrasena})
    token = login.get("token") if isinstance(login, dict) else None
    peticiones.append(evidencia("POST", "/sesiones/", codigo, duracion, limpiar(login if isinstance(login, dict) else {})))
    if not token:
        informe["escenarios"] = [
            {"escenario": "A valor cero", "subcaso": "TC-M06-48", "http": None, "code": None, "estado": "BLOQUEADO",
             "esperado": "HTTP 422 VALOR_COTIZACION_INVALIDO", "motivo": "TEST no respondió al inicio de sesión."},
            {"escenario": "B valor negativo", "subcaso": "TC-M06-48", "http": None, "code": None, "estado": "BLOQUEADO",
             "esperado": "HTTP 422 VALOR_COTIZACION_INVALIDO", "motivo": "TEST no respondió al inicio de sesión."},
            {"escenario": "C vencimiento anterior", "subcaso": "TC-M06-49", "http": None, "code": None, "estado": "BLOQUEADO",
             "esperado": "HTTP 422 FECHA_VENCIMIENTO_INVALIDA", "motivo": "TEST no respondió al inicio de sesión."},
            {"escenario": "D vencimiento omitido y nulo", "subcaso": "TC-M06-49", "http": None, "code": None, "estado": "BLOQUEADO",
             "esperado": "Confirmar si el vencimiento es obligatorio", "motivo": "TEST no respondió al inicio de sesión."},
        ]
        informe["subcasos"] = [{"subcaso": "TC-M06-48", "estado": "BLOQUEADO"}, {"subcaso": "TC-M06-49", "estado": "BLOQUEADO"}]
        informe.update({"aprobados": 0, "rechazados": 0, "bloqueados": 2, "requiere_aclaracion": 0, "porcentaje_aprobacion": 0,
                        "conteos": {}, "hallazgos": ["BLOQUEO DE PRUEBA: la API de TEST aceptó la conexión y no devolvió respuesta."]})
        informe["analisis"] = (
            "# TC-M06-G89\n\nNo se envió ninguna cotización. El inicio de sesión no obtuvo respuesta HTTP.\n\n"
            "El contrato inspeccionado queda pendiente de ejecución.\n"
        )
        guardar(informe)
        print("SIN SESION")
        return 2
    codigo, perfil, duracion = pedir("GET", "/usuarios/me", token=token)
    informe["rol"] = perfil.get("nombre_rol") if isinstance(perfil, dict) else None
    peticiones.append(evidencia("GET", "/usuarios/me", codigo, duracion, {"nombre_rol": informe["rol"]}))
    codigo, activos, duracion = pedir("GET", "/finanzas/activos", token=token)
    sin_valor = next((a for a in activos if isinstance(a, dict) and str(a.get("estado", "")).upper() == "ACTIVO"
                      and a.get("valor_razonable_neto") is None), None) if isinstance(activos, list) else None
    informe["activo_sin_valor"] = None if sin_valor is None else sin_valor.get("id_activo_biologico")
    peticiones.append(evidencia("GET", "/finanzas/activos", codigo, duracion, {
        "total": len(activos) if isinstance(activos, list) else None, "activo_sin_valor": informe["activo_sin_valor"]}))
    codigo, cotizaciones, duracion = pedir("GET", "/finanzas/cotizaciones", token=token)
    antes = [ficha_cotizacion(c) for c in cotizaciones] if isinstance(cotizaciones, list) else []
    peticiones.append(evidencia("GET", "/finanzas/cotizaciones", codigo, duracion, {"total": len(antes), "cotizaciones": antes}))
    ruta_aud = "/finanzas/auditoria?" + urllib.parse.urlencode([
        ("tipo_evento", "COTIZACION_REGISTRADA"), ("formato", "TECNICO"), ("tamano", "1")])
    codigo, auditoria, duracion = pedir("GET", ruta_aud, token=token)
    eventos_antes = auditoria.get("total_registros") if isinstance(auditoria, dict) else None
    peticiones.append(evidencia("GET", ruta_aud, codigo, duracion, {"total_registros": eventos_antes}))

    activo = informe["activo_sin_valor"] or 951
    base = {"activos_cotizados": [activo]}
    for nombre, valor in (("A valor cero", 0), ("B valor negativo", -1)):
        cuerpo = {**base, "valor_cotizacion_propuesto": valor}
        codigo_r, respuesta, duracion = pedir("POST", "/finanzas/cotizaciones", cuerpo, token)
        peticiones.append(evidencia("POST", "/finanzas/cotizaciones", codigo_r, duracion, respuesta, cuerpo))
        dto = codigo_r == 400 and negocio(respuesta) == "VAL_ENTRADA" and "valor_cotizacion_propuesto" in campos(respuesta)
        informe["escenarios"].append({
            "escenario": nombre, "subcaso": "TC-M06-48", "http": codigo_r, "code": negocio(respuesta),
            "campos": campos(respuesta), "esperado": "HTTP 422 VALOR_COTIZACION_INVALIDO",
            "estado": "REQUIERE ACLARACION" if dto else ("RECHAZADO" if codigo_r == 201 else "REQUIERE ACLARACION"),
            "motivo": "El DTO exige un valor mayor que cero y responde 400 VAL_ENTRADA. El 422 del caso de uso no se alcanza.",
        })
        if codigo_r == 201:
            informe["alta_inesperada"] = True
            break

    if not informe.get("alta_inesperada"):
        cuerpo = {**base, "valor_cotizacion_propuesto": "1000.0000", "fecha_vencimiento": ayer}
        codigo_r, respuesta, duracion = pedir("POST", "/finanzas/cotizaciones", cuerpo, token)
        peticiones.append(evidencia("POST", "/finanzas/cotizaciones", codigo_r, duracion, respuesta, cuerpo))
        correcto = codigo_r == 422 and negocio(respuesta) == "FECHA_VENCIMIENTO_INVALIDA"
        informe["escenarios"].append({
            "escenario": "C vencimiento anterior", "subcaso": "TC-M06-49", "fecha_vencimiento": ayer,
            "http": codigo_r, "code": negocio(respuesta), "esperado": "HTTP 422 FECHA_VENCIMIENTO_INVALIDA",
            "estado": "APROBADO" if correcto else ("RECHAZADO" if codigo_r == 201 else "REQUIERE ACLARACION"),
            "motivo": "La fecha es anterior a la emisión y el caso de uso la rechaza antes de consultar el activo.",
        })
        if codigo_r == 201:
            informe["alta_inesperada"] = True

    if sin_valor and not informe.get("alta_inesperada"):
        resultados_d = []
        for nombre, extra in (("omitida", {}), ("nula", {"fecha_vencimiento": None})):
            cuerpo = {**base, "valor_cotizacion_propuesto": "1000.0000", **extra}
            codigo_r, respuesta, duracion = pedir("POST", "/finanzas/cotizaciones", cuerpo, token)
            peticiones.append(evidencia("POST", "/finanzas/cotizaciones", codigo_r, duracion, respuesta, cuerpo))
            resultados_d.append({"variante": nombre, "http": codigo_r, "code": negocio(respuesta)})
            if codigo_r == 201:
                informe["alta_inesperada"] = True
                break
        opcionales = all(r["http"] == 422 and r["code"] == "VALOR_RAZONABLE_NO_DISPONIBLE" for r in resultados_d) and len(resultados_d) == 2
        informe["escenarios"].append({
            "escenario": "D vencimiento omitido y nulo", "subcaso": "TC-M06-49", "variantes": resultados_d,
            "http": resultados_d[-1]["http"] if resultados_d else None, "code": resultados_d[-1]["code"] if resultados_d else None,
            "esperado": "Confirmar si el vencimiento es obligatorio",
            "estado": "APROBADO" if opcionales else ("RECHAZADO" if informe.get("alta_inesperada") else "REQUIERE ACLARACION"),
            "motivo": "Ni la omisión ni el nulo se rechazan por fecha. La solicitud sigue y falla porque el activo no tiene valor razonable.",
        })
    else:
        informe["escenarios"].append({
            "escenario": "D vencimiento omitido y nulo", "subcaso": "TC-M06-49", "http": None, "code": None,
            "esperado": "Confirmar si el vencimiento es obligatorio", "estado": "BLOQUEADO",
            "motivo": "Sin un activo ACTIVO carente de valor razonable, omitir la fecha podría crear la cotización.",
        })

    codigo, cotizaciones, duracion = pedir("GET", "/finanzas/cotizaciones", token=token)
    despues = [ficha_cotizacion(c) for c in cotizaciones] if isinstance(cotizaciones, list) else []
    peticiones.append(evidencia("GET", "/finanzas/cotizaciones", codigo, duracion, {"total": len(despues), "cotizaciones": despues}))
    codigo, auditoria, duracion = pedir("GET", ruta_aud, token=token)
    eventos_despues = auditoria.get("total_registros") if isinstance(auditoria, dict) else None
    peticiones.append(evidencia("GET", ruta_aud, codigo, duracion, {"total_registros": eventos_despues}))
    informe["conteos"] = {
        "cotizaciones_antes": antes, "cotizaciones_despues": despues, "sin_cambio": antes == despues,
        "eventos_antes": eventos_antes, "eventos_despues": eventos_despues, "sin_evento_nuevo": eventos_antes == eventos_despues,
    }
    if not (informe["conteos"]["sin_cambio"] and informe["conteos"]["sin_evento_nuevo"]):
        for escenario in informe["escenarios"]:
            if escenario["estado"] == "APROBADO":
                escenario["estado"] = "RECHAZADO"
    subcasos = []
    for codigo_sub in ("TC-M06-48", "TC-M06-49"):
        propios = [e["estado"] for e in informe["escenarios"] if e["subcaso"] == codigo_sub]
        subcasos.append({"subcaso": codigo_sub, "estado": subir(propios)})
    informe["subcasos"] = subcasos
    aprobados = sum(s["estado"] == "APROBADO" for s in subcasos)
    informe["aprobados"] = aprobados
    informe["rechazados"] = sum(s["estado"] == "RECHAZADO" for s in subcasos)
    informe["bloqueados"] = sum(s["estado"] == "BLOQUEADO" for s in subcasos)
    informe["requiere_aclaracion"] = sum(s["estado"] == "REQUIERE ACLARACION" for s in subcasos)
    informe["porcentaje_aprobacion"] = round(aprobados / 2 * 100)
    informe["hallazgos"] = [
        "QUESTION-M06-G89-01: el cero y el negativo responden 400 VAL_ENTRADA en el campo valor_cotizacion_propuesto. "
        "El diseño esperaba 422 VALOR_COTIZACION_INVALIDO. Ese código está en el caso de uso, después del DTO, y la API no lo alcanza.",
        "El vencimiento es opcional en el DTO, en el caso de uso y en la columna fecha_vencimiento. "
        "No se creó una cotización para demostrarlo con un alta exitosa.",
    ]
    informe["analisis"] = (
        "# TC-M06-G89\n\nNo se usó SQL local ni Newman. No hay un archivo de RF-COT v1.1 en el repositorio.\n\n"
        f"Hoy en America/Bogota: {hoy.isoformat()}. Vencimiento probado: {ayer}.\n"
        f"Cotizaciones sin cambio: {informe['conteos']['sin_cambio']}. Eventos sin cambio: {informe['conteos']['sin_evento_nuevo']}.\n"
        + "\n".join(f"- {s['subcaso']}: {s['estado']}" for s in subcasos) + "\n"
    )
    informe["duracion_ms"] = round((time.perf_counter() - inicio) * 1000)
    guardar(informe)
    print(" ".join(f"{s['subcaso']} {s['estado']}" for s in subcasos))
    for e in informe["escenarios"]:
        print(e["escenario"], e["estado"], e.get("http"), e.get("code"))
    return 0 if aprobados == 2 else 2


if __name__ == "__main__":
    raise SystemExit(main())
