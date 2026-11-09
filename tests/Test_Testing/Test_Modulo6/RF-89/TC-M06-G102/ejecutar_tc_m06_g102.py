"""TC-M06-G102 contra TEST.

Los tres registros positivos no se envían: un precio vigente es global por
especie, se confirma en base de datos y puede cambiar valoraciones compartidas.

Los tres rechazos sí se envían. El DTO o el caso de uso los detienen antes de
insertar el precio.

    python tests/Test_Testing/Test_Modulo6/RF-89/TC-M06-G102/ejecutar_tc_m06_g102.py
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
HOY = datetime.now(timezone(timedelta(hours=-5))).date().isoformat()
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
        limpio = {}
        for clave, item in valor.items():
            if clave in SECRETOS:
                limpio[clave] = {"omitido": True, "longitud": len(item) if isinstance(item, str) else None}
            else:
                limpio[clave] = limpiar(item, profundidad + 1)
        return limpio
    if isinstance(valor, list):
        return [limpiar(v, profundidad + 1) for v in valor[:40]]
    if isinstance(valor, str) and len(valor) > 240:
        return valor[:240]
    return valor


def autenticar() -> tuple[int, str | None, dict, int]:
    correo = os.environ.get("QA_CORREO")
    contrasena = os.environ.get("QA_CONTRASENA")
    if not correo or not contrasena:
        raise SystemExit("Defina QA_CORREO y QA_CONTRASENA en el entorno. No las escriba en el archivo.")
    codigo, payload, duracion = pedir("POST", "/sesiones/", {"correo_electronico": correo, "contrasena": contrasena})
    token = payload.get("token") if isinstance(payload, dict) else None
    publico = limpiar(payload if isinstance(payload, dict) else {})
    return codigo, token, publico if isinstance(publico, dict) else {}, duracion


def evidencia(metodo: str, ruta: str, codigo: int, duracion: int, cuerpo, respuesta, escritura: bool = False) -> dict:
    return {
        "metodo": metodo,
        "consulta": ruta,
        "codigo": codigo,
        "duracion_ms": duracion,
        "escritura": escritura,
        "en": datetime.now(timezone.utc).isoformat(),
        "cuerpo": limpiar(cuerpo),
        "respuesta": limpiar(respuesta),
    }


def resumir_precios(payload) -> dict:
    if not isinstance(payload, list):
        return {"total": None, "ids": []}
    por_fuente: dict[str, int] = {}
    por_especie: dict[str, int] = {}
    for precio in payload:
        if not isinstance(precio, dict):
            continue
        fuente = str(precio.get("fuente"))
        especie = str(precio.get("id_especie"))
        por_fuente[fuente] = por_fuente.get(fuente, 0) + 1
        por_especie[especie] = por_especie.get(especie, 0) + 1
    return {
        "total": len(payload),
        "ids": sorted(p.get("id_precio_mercado") for p in payload if isinstance(p, dict)),
        "por_fuente": por_fuente,
        "por_especie": por_especie,
        "aplicados": [
            {
                "id": p.get("id_precio_mercado"),
                "id_especie": p.get("id_especie"),
                "fuente": p.get("fuente"),
                "precio_unitario": p.get("precio_unitario"),
                "estado": p.get("estado"),
                "fecha_vigencia": p.get("fecha_vigencia"),
                "evidencia_presente": bool((p.get("evidencia") or "").strip()) if isinstance(p.get("evidencia"), str) else p.get("evidencia") is not None,
            }
            for p in payload if isinstance(p, dict) and p.get("es_aplicado")
        ],
    }


def contrato(openapi) -> dict:
    rutas = (openapi or {}).get("paths") if isinstance(openapi, dict) else {}
    precios = rutas.get("/finanzas/precios") if isinstance(rutas, dict) else None
    if not isinstance(precios, dict):
        return {"encontrado": False}
    post = precios.get("post") if isinstance(precios.get("post"), dict) else {}
    esquema = (((post.get("requestBody") or {}).get("content") or {}).get("application/json") or {}).get("schema") or {}
    return {
        "encontrado": True,
        "get": "get" in precios,
        "post": "post" in precios,
        "post_status": post.get("responses", {}).get("201", {}).get("description") if isinstance(post.get("responses"), dict) else None,
        "esquema": esquema.get("$ref") or esquema.get("title") or list(esquema.keys())[:8],
        "permiso_resumen": (post.get("description") or post.get("summary") or "")[:240],
    }


def subcaso(codigo: str, objetivo: str) -> dict:
    return {
        "subcaso": codigo,
        "objetivo": objetivo,
        "endpoint": "POST /finanzas/precios",
        "post_ejecutado": False,
        "peticiones": [],
        "http": [],
        "estado": "BLOQUEADO",
        "motivo": "",
    }


def render(informe: dict) -> str:
    filas = []
    for esc in informe["escenarios"]:
        filas.append(
            "<tr>"
            f"<td>{html.escape(esc['subcaso'])}</td>"
            f"<td>{'sí' if esc['post_ejecutado'] else 'no'}</td>"
            f"<td>{html.escape(', '.join(str(c) for c in esc['http']))}</td>"
            f"<td class='b'>{html.escape(esc['estado'])}</td>"
            f"<td>{html.escape(esc['motivo'])}</td>"
            "</tr>"
        )
    hallazgos = "".join(f"<li>{html.escape(h)}</li>" for h in informe["hallazgos"])
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <title>TC-M06-G102</title>
  <style>
    body {{ font-family: Segoe UI, sans-serif; margin: 2rem; line-height: 1.45; }}
    table {{ border-collapse: collapse; width: 100%; margin: 1rem 0; }}
    th, td {{ border: 1px solid #ccc; padding: .45rem .6rem; vertical-align: top; text-align: left; }}
    th {{ background: #f3f3f3; }}
    .b {{ font-weight: 700; }}
    pre {{ white-space: pre-wrap; background: #fafafa; padding: .8rem; }}
  </style>
</head>
<body>
  <h1>Módulo 6 — RF-89 — TC-M06-G102</h1>
  <p>Registro de precios según las fuentes permitidas y la evidencia documental. Fecha: {html.escape(informe['generado_en'])}. Ambiente: {html.escape(informe['ambiente'])}.</p>
  <h2>Resumen</h2>
  <table>
    <tr><th>Aprobados</th><td>{informe['aprobados']}</td></tr>
    <tr><th>Rechazados</th><td>{informe['rechazados']}</td></tr>
    <tr><th>Bloqueados</th><td>{informe['bloqueados']}</td></tr>
    <tr><th>Porcentaje</th><td class="b">{informe['porcentaje_aprobacion']} %</td></tr>
    <tr><th>Precios antes</th><td>{informe['antes']['total']}</td></tr>
    <tr><th>Precios después</th><td>{informe['despues']['total']}</td></tr>
    <tr><th>Registros nuevos</th><td>{informe['registros_nuevos']}</td></tr>
  </table>
  <h2>Contrato</h2>
  <pre>{html.escape(json.dumps(informe['contrato'], ensure_ascii=False, indent=2))}</pre>
  <h2>Subcasos</h2>
  <table>
    <tr><th>Subcaso</th><th>POST</th><th>HTTP</th><th>Estado</th><th>Motivo</th></tr>
    {''.join(filas)}
  </table>
  <h2>Precios aplicados antes</h2>
  <pre>{html.escape(json.dumps(informe['antes'].get('aplicados'), ensure_ascii=False, indent=2))}</pre>
  <h2>Hallazgos</h2>
  <ul>{hallazgos}</ul>
</body>
</html>
"""


def guardar(informe: dict) -> None:
    RESULTADOS.mkdir(parents=True, exist_ok=True)
    (RESULTADOS / "resultado_ejecucion_TC-M06-G102.html").write_text(render(informe), encoding="utf-8")
    (RESULTADOS / "resumen_ejecucion_TC-M06-G102.json").write_text(json.dumps(informe, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    (RESULTADOS / "evidencia_peticiones_TC-M06-G102.json").write_text(json.dumps({
        "caso": informe["caso"], "generado_en": informe["generado_en"], "peticiones": informe["peticiones"],
    }, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def rechazado(esc: dict, respuestas: list[dict], antes_ids: list, despues_ids: list, auditoria_igual: bool) -> None:
    codigos = [r["codigo"] for r in respuestas]
    errores = [r["respuesta"].get("error_code") if isinstance(r["respuesta"], dict) else None for r in respuestas]
    persistio = antes_ids != despues_ids or not auditoria_igual
    esc["http"] = codigos
    esc["codigos_negocio"] = errores
    esc["post_ejecutado"] = True
    if persistio:
        esc["estado"] = "RECHAZADO"
        esc["motivo"] = "Algún rechazo dejó un precio o un evento de auditoría nuevo."
        return
    if all(codigo in (400, 422) for codigo in codigos):
        esc["estado"] = "APROBADO"
        esc["motivo"] = "El backend rechazó la solicitud y el listado de precios quedó igual."
        return
    esc["estado"] = "RECHAZADO"
    esc["motivo"] = "La respuesta no fue un rechazo de validación."


def main() -> int:
    inicio = time.perf_counter()
    peticiones: list[dict] = []
    hallazgos = [
        "QUESTION-M06-G74-01: el caso pide evidencia documental adjunta. El contrato implementado guarda un texto evidencia_documental de 1 a 500 caracteres, no un archivo.",
        "QUESTION-M06-G74-02: ESTIMADA exige, además de la evidencia, una justificacion_estimacion de al menos 50 caracteres. El subcaso 18 no contempla ese campo.",
        "El catálogo de precios es global por especie. Un precio ACTIVO nuevo se confirma, puede avisar a los contadores y cambia el precio aplicado de las valoraciones de esa especie.",
    ]
    escenarios = [
        subcaso("TC-M06-16", "Registrar MERCADO_ACTIVO por 5000000 con evidencia y conservar la procedencia."),
        subcaso("TC-M06-17", "Registrar UPRA por 4800000 con evidencia y conservar la procedencia."),
        subcaso("TC-M06-18", "Registrar ESTIMADA por 4500000 con evidencia y conservar la procedencia."),
        subcaso("TC-M06-19", "Rechazar un precio igual a cero o negativo."),
        subcaso("TC-M06-20", "Rechazar un precio sin evidencia documental obligatoria."),
        subcaso("TC-M06-21", "Rechazar una fuente que no sea MERCADO_ACTIVO, UPRA ni ESTIMADA."),
    ]
    informe = {
        "caso": "TC-M06-G102",
        "rf": "RF-89",
        "ambiente": BASE_API,
        "generado_en": datetime.now(timezone.utc).isoformat(),
        "contrato": {},
        "puede_registrar": False,
        "antes": {"total": None},
        "despues": {"total": None},
        "registros_nuevos": None,
        "escenarios": escenarios,
        "peticiones": peticiones,
        "hallazgos": hallazgos,
        "aprobados": 0,
        "rechazados": 0,
        "bloqueados": 6,
        "porcentaje_aprobacion": 0,
        "duracion_ms": 0,
    }
    bloqueo_positivo = (
        "No se envió el POST. El precio quedaría vigente para toda la especie en el catálogo compartido, "
        "se confirmaría en base de datos y podría cambiar simulaciones y valoraciones, incluido el activo 951 del TC-M06-G101. "
        "No hay un catálogo aislado ni autorización para registrarlo."
    )
    for esc in escenarios[:3]:
        esc["motivo"] = bloqueo_positivo

    codigo_api, openapi, duracion = pedir("GET", "/openapi.json")
    informe["contrato"] = {"http": codigo_api, **contrato(openapi if codigo_api == 200 else {})}
    peticiones.append(evidencia("GET", "/openapi.json", codigo_api, duracion, None, informe["contrato"]))

    codigo, token, publico, duracion_login = autenticar()
    informe["login_http"] = codigo
    peticiones.append(evidencia("POST", "/sesiones/", codigo, duracion_login, {"correo_electronico": "omitido"}, publico, True))
    if codigo != 200 or not token:
        for esc in escenarios:
            esc["motivo"] = "No fue posible autenticar al Contador."
        informe["duracion_ms"] = round((time.perf_counter() - inicio) * 1000)
        guardar(informe)
        print("BLOQUEADO 0")
        return 2

    codigo, permisos, duracion = pedir("GET", "/sesiones/me/permisos", token=token)
    pares = permisos.get("permisos") if isinstance(permisos, dict) else []
    informe["puede_registrar"] = any(
        isinstance(p, dict) and p.get("nombre_recurso") == "precios_mercado" and p.get("id_accion") == 1
        for p in (pares or [])
    )
    peticiones.append(evidencia("GET", "/sesiones/me/permisos", codigo, duracion, None, {"puede_registrar_precios": informe["puede_registrar"]}))

    codigo, precios, duracion = pedir("GET", "/finanzas/precios", token=token)
    antes = resumir_precios(precios)
    informe["antes"] = antes
    peticiones.append(evidencia("GET", "/finanzas/precios", codigo, duracion, None, antes))
    codigo_aud, auditoria, duracion = pedir("GET", "/finanzas/auditoria?tipo_evento=PRECIO_REGISTRADO&formato=TECNICO&tamano=1", token=token)
    auditoria_antes = auditoria.get("total_registros") if isinstance(auditoria, dict) else None
    peticiones.append(evidencia("GET", "/finanzas/auditoria?tipo_evento=PRECIO_REGISTRADO&formato=TECNICO&tamano=1", codigo_aud, duracion, None, {"total_registros": auditoria_antes}))

    if codigo != 200 or not informe["puede_registrar"]:
        for esc in escenarios[3:]:
            esc["motivo"] = "La cuenta no puede registrar precios, así que el rechazo de validación no se alcanzaría."
        informe["duracion_ms"] = round((time.perf_counter() - inicio) * 1000)
        guardar(informe)
        print("BLOQUEADO 0")
        return 2

    especie = antes["aplicados"][0]["id_especie"] if antes["aplicados"] else 1
    base = {
        "id_especie": especie,
        "categoria": "PESO_KG",
        "fecha_vigencia": HOY,
        "fuente": "MERCADO_ACTIVO",
        "evidencia_documental": "texto de validacion no persistido",
    }
    pruebas = {
        "TC-M06-19": [ {**base, "precio_unitario": "0"}, {**base, "precio_unitario": "-1"} ],
        "TC-M06-20": [ {k: v for k, v in {**base, "precio_unitario": "100"}.items() if k != "evidencia_documental"}, {**base, "precio_unitario": "100", "evidencia_documental": ""}, {**base, "precio_unitario": "100", "evidencia_documental": "   "} ],
        "TC-M06-21": [ {**base, "precio_unitario": "100", "fuente": "OTRA"} ],
    }
    for esc in escenarios[3:]:
        respuestas = []
        for cuerpo in pruebas[esc["subcaso"]]:
            codigo_post, respuesta, duracion_post = pedir("POST", "/finanzas/precios", cuerpo, token)
            item = evidencia("POST", "/finanzas/precios", codigo_post, duracion_post, cuerpo, respuesta, True)
            peticiones.append(item)
            respuestas.append(item)
            esc["peticiones"].append({"http": codigo_post, "codigo": respuesta.get("error_code") if isinstance(respuesta, dict) else None, "mensaje": respuesta.get("message") if isinstance(respuesta, dict) else None})
        codigo_despues, precios_despues, duracion_despues = pedir("GET", "/finanzas/precios", token=token)
        despues = resumir_precios(precios_despues)
        peticiones.append(evidencia("GET", "/finanzas/precios", codigo_despues, duracion_despues, None, {"total": despues["total"]}))
        codigo_aud2, auditoria2, duracion_aud = pedir("GET", "/finanzas/auditoria?tipo_evento=PRECIO_REGISTRADO&formato=TECNICO&tamano=1", token=token)
        auditoria_despues = auditoria2.get("total_registros") if isinstance(auditoria2, dict) else None
        peticiones.append(evidencia("GET", "/finanzas/auditoria?tipo_evento=PRECIO_REGISTRADO&formato=TECNICO&tamano=1", codigo_aud2, duracion_aud, None, {"total_registros": auditoria_despues}))
        rechazado(esc, respuestas, antes["ids"], despues["ids"], auditoria_antes == auditoria_despues)
        informe["despues"] = despues

    informe["registros_nuevos"] = None if informe["despues"].get("ids") is None else sorted(set(informe["despues"]["ids"]) - set(antes["ids"]))
    informe["aprobados"] = sum(1 for e in escenarios if e["estado"] == "APROBADO")
    informe["rechazados"] = sum(1 for e in escenarios if e["estado"] == "RECHAZADO")
    informe["bloqueados"] = sum(1 for e in escenarios if e["estado"] == "BLOQUEADO")
    informe["porcentaje_aprobacion"] = round(informe["aprobados"] / 6 * 100)
    informe["duracion_ms"] = round((time.perf_counter() - inicio) * 1000)
    if any(e["estado"] == "RECHAZADO" for e in escenarios[3:]):
        hallazgos.append("BUG-M06-G74-01: un rechazo de validación no cumplió el contrato o dejó un registro.")
    guardar(informe)
    print(
        " ".join(f"{e['subcaso']} {e['estado']}" for e in escenarios)
        + f" | APROBADOS {informe['aprobados']} RECHAZADOS {informe['rechazados']} BLOQUEADOS {informe['bloqueados']} PCT {informe['porcentaje_aprobacion']}"
    )
    return 0 if informe["aprobados"] == 6 else 2


if __name__ == "__main__":
    raise SystemExit(main())
