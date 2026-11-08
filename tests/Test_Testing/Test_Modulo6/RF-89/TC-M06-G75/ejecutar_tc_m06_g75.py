"""TC-M06-G75 contra TEST.

TC-M06-22 y TC-M06-24 se rechazan en la validación, antes de insertar.
TC-M06-23 con 365 días supera esa validación y el caso de uso guardaría el
precio, así que no se envía.

    python tests/Test_Testing/Test_Modulo6/RF-89/TC-M06-G75/ejecutar_tc_m06_g75.py
"""
from __future__ import annotations

import html
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

CARPETA = Path(__file__).resolve().parent
RESULTADOS = CARPETA / "resultados"
BASE_API = "https://api.inmero.co/api-sgpmp-test"
ZONA = "America/Bogota"
HOY = datetime.now(timezone(timedelta(hours=-5))).date()
SECRETOS = {"token", "access_token", "contrasena", "password", "hash_integridad", "numero_id_tributaria", "evidencia", "hash_evidencia"}


def pedir(metodo: str, ruta: str, cuerpo: dict | None = None, token: str | None = None):
    datos = None if cuerpo is None else json.dumps(cuerpo).encode("utf-8")
    headers = {"Accept": "application/json", "X-Zona-Horaria": ZONA}
    if cuerpo is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(BASE_API + ruta, data=datos, headers=headers, method=metodo)
    inicio = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode("utf-8")
            payload = json.loads(raw) if raw else None
            codigo = resp.status
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {"message": raw[:240]}
        codigo = exc.code
    return codigo, payload, round((time.perf_counter() - inicio) * 1000)


def limpiar(valor, profundidad: int = 0):
    if profundidad > 5:
        return "..."
    if isinstance(valor, dict):
        return {
            clave: ({"omitido": True, "longitud": len(item)} if isinstance(item, str) else {"omitido": True})
            if clave in SECRETOS else limpiar(item, profundidad + 1)
            for clave, item in valor.items()
        }
    if isinstance(valor, list):
        return [limpiar(v, profundidad + 1) for v in valor[:40]]
    if isinstance(valor, str) and len(valor) > 240:
        return valor[:240]
    return valor


def evidencia(metodo: str, ruta: str, codigo: int, duracion: int, cuerpo, respuesta, escritura: bool = False) -> dict:
    return {
        "metodo": metodo, "consulta": ruta, "codigo": codigo, "duracion_ms": duracion,
        "escritura": escritura, "en": datetime.now(timezone.utc).isoformat(),
        "cuerpo": limpiar(cuerpo), "respuesta": limpiar(respuesta),
    }


def resumir(payload) -> dict:
    if not isinstance(payload, list):
        return {"total": None, "ids": [], "muestra": []}
    muestra = []
    for precio in payload:
        if not isinstance(precio, dict):
            continue
        muestra.append({
            "id": precio.get("id_precio_mercado"),
            "id_especie": precio.get("id_especie"),
            "fuente": precio.get("fuente"),
            "estado": precio.get("estado"),
            "fecha_vigencia": precio.get("fecha_vigencia"),
            "fecha_vencimiento": precio.get("fecha_vencimiento"),
            "es_aplicado": precio.get("es_aplicado"),
        })
    return {
        "total": len(payload),
        "ids": sorted(p.get("id_precio_mercado") for p in payload if isinstance(p, dict)),
        "muestra": muestra,
    }


def subcaso(codigo: str, objetivo: str) -> dict:
    return {"subcaso": codigo, "objetivo": objetivo, "endpoint": "POST /finanzas/precios", "post_ejecutado": False, "http": None, "codigo_negocio": None, "mensaje": None, "estado": "BLOQUEADO", "motivo": ""}


def render(informe: dict) -> str:
    filas = "".join(
        "<tr>"
        f"<td>{html.escape(e['subcaso'])}</td><td>{'sí' if e['post_ejecutado'] else 'no'}</td>"
        f"<td>{html.escape(str(e.get('http')))}</td><td>{html.escape(str(e.get('codigo_negocio') or ''))}</td>"
        f"<td class='b'>{html.escape(e['estado'])}</td><td>{html.escape(e['motivo'])}</td></tr>"
        for e in informe["escenarios"]
    )
    hallazgos = "".join(f"<li>{html.escape(h)}</li>" for h in informe["hallazgos"])
    return f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8"><title>TC-M06-G75</title>
<style>
 body {{ font-family: Segoe UI, sans-serif; margin: 2rem; line-height: 1.45; }}
 table {{ border-collapse: collapse; width: 100%; }}
 th, td {{ border: 1px solid #ccc; padding: .45rem .6rem; text-align: left; vertical-align: top; }}
 th {{ background: #f3f3f3; }} .b {{ font-weight: 700; }}
 pre {{ white-space: pre-wrap; background: #fafafa; padding: .8rem; }}
</style></head><body>
<h1>Módulo 6 — RF-89 — TC-M06-G75</h1>
<p>Fechas de vigencia y vencimiento. Referencia usada por el script: {html.escape(informe['fecha_referencia'])} ({html.escape(ZONA)}). Generado: {html.escape(informe['generado_en'])}.</p>
<table>
 <tr><th>Aprobados</th><td>{informe['aprobados']}</td></tr>
 <tr><th>Rechazados</th><td>{informe['rechazados']}</td></tr>
 <tr><th>Bloqueados</th><td>{informe['bloqueados']}</td></tr>
 <tr><th>Porcentaje</th><td class="b">{informe['porcentaje_aprobacion']} %</td></tr>
 <tr><th>Precios antes / después</th><td>{informe['antes']['total']} / {informe['despues']['total']}</td></tr>
 <tr><th>Registros nuevos</th><td>{informe['registros_nuevos']}</td></tr>
 <tr><th>Auditoría PRECIO_REGISTRADO antes / después</th><td>{informe['auditoria_antes']} / {informe['auditoria_despues']}</td></tr>
</table>
<h2>Subcasos</h2>
<table><tr><th>Subcaso</th><th>POST</th><th>HTTP</th><th>Código</th><th>Estado</th><th>Motivo</th></tr>{filas}</table>
<h2>Reglas observadas en el código</h2>
<pre>{html.escape(informe['reglas'])}</pre>
<h2>Hallazgos</h2><ul>{hallazgos}</ul>
</body></html>"""


def guardar(informe: dict) -> None:
    RESULTADOS.mkdir(parents=True, exist_ok=True)
    (RESULTADOS / "resultado_ejecucion_TC-M06-G75.html").write_text(render(informe), encoding="utf-8")
    (RESULTADOS / "resumen_ejecucion_TC-M06-G75.json").write_text(json.dumps(informe, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    (RESULTADOS / "evidencia_peticiones_TC-M06-G75.json").write_text(json.dumps({
        "caso": "TC-M06-G75", "generado_en": informe["generado_en"], "peticiones": informe["peticiones"],
    }, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def main() -> int:
    inicio = time.perf_counter()
    peticiones = []
    reglas = (
        "La antigüedad se calcula como (hoy_usuario - fecha_vigencia).days > 365. "
        "hoy_usuario es el día calendario de la zona enviada en X-Zona-Horaria; sin esa cabecera, el día es UTC. "
        "Exactamente 365 días no entra en la condición y la validación continúa. "
        "fecha_vencimiento es opcional. Si viene informada, debe ser posterior a fecha_vigencia: igual o anterior responde FECHA_VENCIMIENTO_INVALIDA. "
        "Ambas reglas lanzan ValidationError HTTP 400 dentro de _validar, antes del INSERT y del commit. "
        "Un rechazo de estas reglas no registra PRECIO_REGISTRADO."
    )
    escenarios = [
        subcaso("TC-M06-22", "Rechazar vigencia de 366 días antes de hoy."),
        subcaso("TC-M06-23", "Aceptar vigencia de exactamente 365 días antes de hoy."),
        subcaso("TC-M06-24", "Rechazar vencimiento anterior a la vigencia."),
    ]
    hallazgos = [
        "QUESTION-M06-G75-01: el código también rechaza una fecha de vencimiento igual a la vigencia. El subcaso 24 solo pide el caso anterior.",
        "No hay una prueba unitaria del límite de 365 días en el repositorio. La aceptación de ese límite no se comprobó contra el API porque el POST guardaría el precio.",
    ]
    informe = {
        "caso": "TC-M06-G75", "rf": "RF-89", "ambiente": BASE_API,
        "generado_en": datetime.now(timezone.utc).isoformat(),
        "fecha_referencia": HOY.isoformat(), "reglas": reglas,
        "antes": {"total": None, "ids": []}, "despues": {"total": None, "ids": []},
        "auditoria_antes": None, "auditoria_despues": None, "registros_nuevos": None,
        "escenarios": escenarios, "peticiones": peticiones, "hallazgos": hallazgos,
        "aprobados": 0, "rechazados": 0, "bloqueados": 3, "porcentaje_aprobacion": 0, "duracion_ms": 0,
    }
    escenarios[1]["motivo"] = (
        "No se envió el POST. Una vigencia de exactamente 365 días supera la validación de antigüedad. "
        "Con el resto del cuerpo válido, el caso de uso inserta el precio, confirma la transacción y puede dejarlo ACTIVO en el catálogo compartido. "
        "Hace falta un catálogo aislado o autorización expresa para comprobar la aceptación."
    )

    correo = os.environ.get("QA_CORREO")
    contrasena = os.environ.get("QA_CONTRASENA")
    if not correo or not contrasena:
        raise SystemExit("Defina QA_CORREO y QA_CONTRASENA en el entorno.")
    codigo, login, duracion = pedir("POST", "/sesiones/", {"correo_electronico": correo, "contrasena": contrasena})
    token = login.get("token") if isinstance(login, dict) else None
    peticiones.append(evidencia("POST", "/sesiones/", codigo, duracion, {"correo_electronico": "omitido"}, limpiar(login), True))
    if codigo != 200 or not token:
        for esc in escenarios:
            esc["motivo"] = "No fue posible autenticar al Contador."
        informe["duracion_ms"] = round((time.perf_counter() - inicio) * 1000)
        guardar(informe)
        print("BLOQUEADO 0")
        return 2

    codigo, permisos, duracion = pedir("GET", "/sesiones/me/permisos", token=token)
    pares = permisos.get("permisos") if isinstance(permisos, dict) else []
    puede = any(isinstance(p, dict) and p.get("nombre_recurso") == "precios_mercado" and p.get("id_accion") == 1 for p in (pares or []))
    peticiones.append(evidencia("GET", "/sesiones/me/permisos", codigo, duracion, None, {"puede_registrar": puede}))
    codigo, precios, duracion = pedir("GET", "/finanzas/precios", token=token)
    antes = resumir(precios)
    informe["antes"] = antes
    peticiones.append(evidencia("GET", "/finanzas/precios", codigo, duracion, None, {"total": antes["total"], "ids": antes["ids"]}))
    codigo_aud, auditoria, duracion = pedir("GET", "/finanzas/auditoria?tipo_evento=PRECIO_REGISTRADO&formato=TECNICO&tamano=1", token=token)
    informe["auditoria_antes"] = auditoria.get("total_registros") if isinstance(auditoria, dict) else None
    peticiones.append(evidencia("GET", "/finanzas/auditoria?tipo_evento=PRECIO_REGISTRADO&formato=TECNICO&tamano=1", codigo_aud, duracion, None, {"total_registros": informe["auditoria_antes"]}))

    if codigo != 200 or not puede or not antes["ids"]:
        for esc in (escenarios[0], escenarios[2]):
            esc["motivo"] = "No hay permiso de registro o no se pudo leer un precio existente para usar una especie real."
        informe["despues"] = antes
        informe["duracion_ms"] = round((time.perf_counter() - inicio) * 1000)
        guardar(informe)
        print("BLOQUEADO 0")
        return 2

    especie = next(item["id_especie"] for item in antes["muestra"] if item.get("id_especie"))
    base = {
        "id_especie": especie,
        "categoria": "PESO_KG",
        "precio_unitario": "100.00",
        "fuente": "MERCADO_ACTIVO",
        "evidencia_documental": "texto de validacion de fechas no persistido",
    }
    envios = {
        "TC-M06-22": ({**base, "fecha_vigencia": (HOY - timedelta(days=366)).isoformat()}, "FECHA_VIGENCIA_FUERA_DE_RANGO"),
        "TC-M06-24": ({**base, "fecha_vigencia": HOY.isoformat(), "fecha_vencimiento": (HOY - timedelta(days=1)).isoformat()}, "FECHA_VENCIMIENTO_INVALIDA"),
    }
    for esc in (escenarios[0], escenarios[2]):
        cuerpo, esperado = envios[esc["subcaso"]]
        codigo_post, respuesta, duracion_post = pedir("POST", "/finanzas/precios", cuerpo, token)
        peticiones.append(evidencia("POST", "/finanzas/precios", codigo_post, duracion_post, cuerpo, respuesta, True))
        esc["post_ejecutado"] = True
        esc["http"] = codigo_post
        esc["codigo_negocio"] = respuesta.get("error_code") if isinstance(respuesta, dict) else None
        esc["mensaje"] = respuesta.get("message") if isinstance(respuesta, dict) else None
        esc["campo"] = (respuesta.get("fields") or [{}])[0].get("field") if isinstance(respuesta, dict) else None
        if codigo_post == 400 and esc["codigo_negocio"] == esperado:
            esc["estado"] = "APROBADO"
            esc["motivo"] = "El backend rechazó la fecha antes de crear un precio."
        else:
            esc["estado"] = "RECHAZADO"
            esc["motivo"] = f"Se esperaba HTTP 400 {esperado}."

    codigo, precios, duracion = pedir("GET", "/finanzas/precios", token=token)
    despues = resumir(precios)
    informe["despues"] = {"total": despues["total"], "ids": despues["ids"]}
    peticiones.append(evidencia("GET", "/finanzas/precios", codigo, duracion, None, informe["despues"]))
    codigo_aud, auditoria, duracion = pedir("GET", "/finanzas/auditoria?tipo_evento=PRECIO_REGISTRADO&formato=TECNICO&tamano=1", token=token)
    informe["auditoria_despues"] = auditoria.get("total_registros") if isinstance(auditoria, dict) else None
    peticiones.append(evidencia("GET", "/finanzas/auditoria?tipo_evento=PRECIO_REGISTRADO&formato=TECNICO&tamano=1", codigo_aud, duracion, None, {"total_registros": informe["auditoria_despues"]}))
    informe["registros_nuevos"] = sorted(set(despues["ids"]) - set(antes["ids"]))
    if informe["registros_nuevos"] or informe["auditoria_antes"] != informe["auditoria_despues"]:
        for esc in escenarios:
            if esc["post_ejecutado"] and esc["estado"] == "APROBADO":
                esc["estado"] = "RECHAZADO"
                esc["motivo"] = "El rechazo dejó un precio o un evento PRECIO_REGISTRADO nuevo."
        hallazgos.append("BUG-M06-G75-01: una validación de fechas modificó el catálogo o la auditoría.")

    informe["aprobados"] = sum(e["estado"] == "APROBADO" for e in escenarios)
    informe["rechazados"] = sum(e["estado"] == "RECHAZADO" for e in escenarios)
    informe["bloqueados"] = sum(e["estado"] == "BLOQUEADO" for e in escenarios)
    informe["porcentaje_aprobacion"] = round(informe["aprobados"] / 3 * 100)
    informe["duracion_ms"] = round((time.perf_counter() - inicio) * 1000)
    informe["antes"] = {"total": antes["total"], "ids": antes["ids"], "muestra": antes["muestra"]}
    guardar(informe)
    print(" ".join(f"{e['subcaso']} {e['estado']} {e.get('http')} {e.get('codigo_negocio')}" for e in escenarios) + f" | PCT {informe['porcentaje_aprobacion']} NUEVOS {informe['registros_nuevos']}")
    return 0 if informe["aprobados"] == 3 else 2


if __name__ == "__main__":
    raise SystemExit(main())
