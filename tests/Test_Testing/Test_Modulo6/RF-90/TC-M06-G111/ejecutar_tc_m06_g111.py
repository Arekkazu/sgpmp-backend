"""TC-M06-G111 contra TEST.

El registro con fecha dentro de un período cerrado se envía solo cuando ya existe
un período abierto posterior: así la validación rechaza antes de crear nada.
El cierre no se ejecuta.

    python tests/Test_Testing/Test_Modulo6/RF-90/TC-M06-G111/ejecutar_tc_m06_g111.py
"""
from __future__ import annotations

import html
import json
import os
import time
import urllib.error
import urllib.request
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path

CARPETA = Path(__file__).resolve().parent
RESULTADOS = CARPETA / "resultados"
BASE_API = "https://api.inmero.co/api-sgpmp-test"
ZONA = "America/Bogota"
HOY = date(2026, 11, 8)
ACTIVO = 951
SECRETOS = {"token", "access_token", "contrasena", "password", "hash_integridad", "numero_id_tributaria",
            "tercero_nit", "tercero_razon_social", "identificador", "finca"}


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
        with urllib.request.urlopen(req, timeout=90) as resp:
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
    return codigo, payload, round((time.perf_counter() - inicio) * 1000)


def limpiar(valor, profundidad: int = 0):
    if profundidad > 4:
        return "..."
    if isinstance(valor, dict):
        return {k: ({"omitido": True} if k in SECRETOS else limpiar(v, profundidad + 1)) for k, v in valor.items()}
    if isinstance(valor, list):
        return [limpiar(v, profundidad + 1) for v in valor[:15]]
    if isinstance(valor, str) and len(valor) > 240:
        return valor[:240]
    return valor


def evidencia(metodo, ruta, codigo, duracion, respuesta, cuerpo=None) -> dict:
    return {"metodo": metodo, "consulta": ruta, "codigo": codigo, "duracion_ms": duracion, "escritura": False,
            "en": datetime.now(timezone.utc).isoformat(), "cuerpo": cuerpo, "respuesta": limpiar(respuesta)}


def negocio(payload) -> str | None:
    if isinstance(payload, dict):
        return payload.get("error_code") or payload.get("code")
    return None


def dia(valor: str | None) -> date | None:
    if not valor:
        return None
    return date.fromisoformat(str(valor)[:10])


def ficha_periodo(p: dict) -> dict:
    return {"id": p.get("id_periodo_contable"), "estado": p.get("estado"),
            "inicio": str(p.get("fecha_inicio") or "")[:10], "fin": str(p.get("fecha_fin") or "")[:10]}


def resumir_costos(lista) -> dict:
    if not isinstance(lista, list):
        return {"total": None}
    return {"total": len(lista),
            "estados": dict(Counter(c.get("estado") for c in lista if isinstance(c, dict))),
            "subtipos": dict(Counter(c.get("subtipo_costo") for c in lista if isinstance(c, dict))),
            "otro_pendiente": sum(1 for c in lista if isinstance(c, dict) and c.get("subtipo_costo") == "OTRO"
                                  and c.get("estado") == "PENDIENTE_CLASIFICACION")}


def prevalidacion_publica(payload) -> dict:
    if not isinstance(payload, dict):
        return {"http_payload": limpiar(payload)}
    bloqueos = payload.get("bloqueos") if isinstance(payload.get("bloqueos"), list) else []
    return {"puede_cerrar": payload.get("puede_cerrar"),
            "codigos": [b.get("codigo") for b in bloqueos if isinstance(b, dict)],
            "activos_sin_precio": len(payload.get("activos_sin_precio") or []),
            "lineas_sin_trazabilidad": len(payload.get("lineas_sin_trazabilidad") or [])}


def render(informe: dict) -> str:
    filas = "".join(
        f"<tr><td>{html.escape(e['subcaso'])}</td><td>{html.escape(e['estado'])}</td><td>{html.escape(e['motivo'])}</td></tr>"
        for e in informe["escenarios"])
    return f"""<!DOCTYPE html><html lang="es"><head><meta charset="utf-8"><title>TC-M06-G111</title>
<style>body{{font-family:Segoe UI,sans-serif;margin:2rem;line-height:1.45}}table{{border-collapse:collapse;width:100%}}
th,td{{border:1px solid #ccc;padding:.45rem .6rem;text-align:left;vertical-align:top}}th{{background:#f3f3f3}}</style></head><body>
<h1>Módulo 6 — RF-90 / RF-87 — TC-M06-G111</h1>
<p>Generado: {html.escape(informe['generado_en'])}. Cierre de período: no ejecutado.</p>
<table><tr><th>Porcentaje</th><td>{informe['porcentaje_aprobacion']} %</td></tr>
<tr><th>Aprobados / rechazados / bloqueados</th><td>{informe['aprobados']} / {informe['rechazados']} / {informe['bloqueados']}</td></tr></table>
<h2>Subcasos</h2><table><tr><th>Subcaso</th><th>Estado</th><th>Motivo</th></tr>{filas}</table>
<h2>Contrato</h2><pre>{html.escape(informe['contrato'])}</pre>
<h2>Períodos</h2><pre>{html.escape(json.dumps(informe['periodos'], ensure_ascii=False, indent=2))}</pre>
<h2>Prevalidaciones</h2><pre>{html.escape(json.dumps(informe['prevalidaciones'], ensure_ascii=False, indent=2))}</pre>
<h2>Hallazgos</h2><ul>{''.join(f'<li>{html.escape(h)}</li>' for h in informe['hallazgos'])}</ul>
</body></html>"""


def guardar(informe: dict) -> None:
    RESULTADOS.mkdir(parents=True, exist_ok=True)
    (RESULTADOS / "resultado_ejecucion_TC-M06-G111.html").write_text(render(informe), encoding="utf-8")
    (RESULTADOS / "resumen_ejecucion_TC-M06-G111.json").write_text(json.dumps(informe, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    (RESULTADOS / "evidencia_peticiones_TC-M06-G111.json").write_text(json.dumps({
        "caso": "TC-M06-G111", "generado_en": informe["generado_en"], "peticiones": informe["peticiones"],
    }, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    (RESULTADOS / "analisis_hallazgos_TC-M06-G111.md").write_text(informe["analisis"], encoding="utf-8")


def main() -> int:
    inicio = time.perf_counter()
    peticiones = []
    contrato = (
        "POST /finanzas/costos y POST /finanzas/periodos/{id}/cierre están publicados. "
        "El Contador registra y clasifica costos y puede ejecutar el cierre. El Administrador y el Revisor Fiscal consultan el cierre. "
        "Una fecha que cae en un período CERRADO no se guarda allí: el sistema busca el primer período ABIERTO posterior y, "
        "como esa fecha no le pertenece, responde 422 PERIODO_CONTABLE_CERRADO antes del INSERT. "
        "Si no hubiera un período abierto posterior, la búsqueda podría crear uno; por eso este script no envía el costo en ese caso. "
        "Un subtipo OTRO sin naturaleza queda PENDIENTE_CLASIFICACION. "
        "GET /finanzas/periodos/{id}/prevalidacion informa COSTOS_PENDIENTE_CLASIFICACION. "
        "El POST de cierre, si hay bloqueos, responde 422 CIERRE_BLOQUEADO antes de pasar el período a EN_CIERRE. "
        "Si no hay bloqueos, el cierre sí cambia el período. Esa operación no se envía. "
        "La clasificación es POST /finanzas/costos/{id}/clasificacion y tampoco se envía."
    )
    informe = {
        "caso": "TC-M06-G111", "rf": ["RF-90", "RF-87"], "ambiente": BASE_API,
        "generado_en": datetime.now(timezone.utc).isoformat(), "contrato": contrato,
        "periodos": [], "costos": {}, "prevalidaciones": [], "escenarios": [], "peticiones": peticiones,
        "hallazgos": ["BLOQUEO DE PRUEBA: no hay un período aislado con un costo OTRO pendiente, y el cierre de un período compartido puede dejarlo EN_CIERRE."],
        "aprobados": 0, "rechazados": 0, "bloqueados": 0, "porcentaje_aprobacion": 0,
    }
    correo, contrasena = os.environ.get("QA_CORREO"), os.environ.get("QA_CONTRASENA")
    if not correo or not contrasena:
        raise SystemExit("Defina QA_CORREO y QA_CONTRASENA.")
    codigo, login, duracion = pedir("POST", "/sesiones/", {"correo_electronico": correo, "contrasena": contrasena})
    token = login.get("token") if isinstance(login, dict) else None
    peticiones.append(evidencia("POST", "/sesiones/", codigo, duracion, limpiar(login if isinstance(login, dict) else {})))
    if codigo != 200 or not token:
        guardar(informe)
        print("SIN SESION")
        return 2

    codigo, openapi, duracion = pedir("GET", "/openapi.json")
    caminos = (openapi or {}).get("paths") or {} if codigo == 200 and isinstance(openapi, dict) else {}
    informe["rutas"] = {
        "/finanzas/costos": sorted(k for k in (caminos.get("/finanzas/costos") or {}) if k in {"get", "post", "put", "patch", "delete"}),
        "/finanzas/periodos/{id_periodo_contable}/cierre": sorted(k for k in (caminos.get("/finanzas/periodos/{id_periodo_contable}/cierre") or {}) if k in {"get", "post", "put", "patch", "delete"}),
        "/finanzas/periodos/{id_periodo_contable}/prevalidacion": "get" in (caminos.get("/finanzas/periodos/{id_periodo_contable}/prevalidacion") or {}),
    }
    peticiones.append(evidencia("GET", "/openapi.json", codigo, duracion, informe["rutas"]))

    codigo, periodos, duracion = pedir("GET", "/finanzas/periodos", token=token)
    fichas = [ficha_periodo(p) for p in periodos if isinstance(p, dict)] if isinstance(periodos, list) else []
    informe["periodos"] = fichas
    peticiones.append(evidencia("GET", "/finanzas/periodos", codigo, duracion, {"total": len(fichas), "estados": dict(Counter(p["estado"] for p in fichas))}))
    codigo, costos, duracion = pedir("GET", "/finanzas/costos", token=token)
    informe["costos"] = resumir_costos(costos)
    peticiones.append(evidencia("GET", "/finanzas/costos", codigo, duracion, informe["costos"]))
    for ruta in ("/finanzas/costos?subtipo_costo=OTRO", "/finanzas/costos?estado=PENDIENTE_CLASIFICACION"):
        codigo_c, lista, duracion = pedir("GET", ruta, token=token)
        peticiones.append(evidencia("GET", ruta, codigo_c, duracion, resumir_costos(lista)))
    ruta_aud = "/finanzas/auditoria?tipo_evento=COSTO_REGISTRADO&formato=TECNICO&tamano=1"
    codigo, auditoria, duracion = pedir("GET", ruta_aud, token=token)
    auditoria_antes = auditoria.get("total_registros") if isinstance(auditoria, dict) else None
    peticiones.append(evidencia("GET", ruta_aud, codigo, duracion, {"total_registros": auditoria_antes}))
    codigo, historial, duracion = pedir("GET", f"/finanzas/activos/{ACTIVO}", token=token)
    costo_val = (historial or {}).get("valoracion_costo") if isinstance(historial, dict) else None
    libros_antes = costo_val.get("valor_contable_por_costo") if isinstance(costo_val, dict) else None
    peticiones.append(evidencia("GET", f"/finanzas/activos/{ACTIVO}", codigo, duracion, {"valor_contable_por_costo": libros_antes}))

    abiertos = [p for p in fichas if p["estado"] == "ABIERTO"]
    for periodo in abiertos:
        ruta = f"/finanzas/periodos/{periodo['id']}/prevalidacion"
        codigo_v, previa, duracion = pedir("GET", ruta, token=token)
        publica = prevalidacion_publica(previa)
        publica["id_periodo"] = periodo["id"]
        informe["prevalidaciones"].append(publica)
        peticiones.append(evidencia("GET", ruta, codigo_v, duracion, publica))

    cerrados = [p for p in fichas if p["estado"] == "CERRADO" and dia(p["inicio"]) and dia(p["inicio"]) <= HOY]
    candidato = None
    for cerrado in sorted(cerrados, key=lambda p: p["inicio"], reverse=True):
        if any(p["estado"] == "ABIERTO" and dia(p["inicio"]) and dia(cerrado["fin"]) and dia(p["inicio"]) > dia(cerrado["fin"]) for p in fichas):
            candidato = cerrado
            break
    post_37 = None
    if candidato:
        cuerpo = {"subtipo_costo": "ALIMENTO", "origen_costo": "MANO_OBRA_PROPIA", "monto_costo": 100,
                  "fecha_costo": candidato["inicio"], "id_activo_biologico": ACTIVO}
        codigo_r, respuesta, duracion = pedir("POST", "/finanzas/costos", cuerpo, token)
        post_37 = {"http": codigo_r, "code": negocio(respuesta), "periodo": candidato["id"], "fecha": candidato["inicio"]}
        peticiones.append(evidencia("POST", "/finanzas/costos", codigo_r, duracion, respuesta, cuerpo))
    codigo, costos_despues, duracion = pedir("GET", "/finanzas/costos", token=token)
    despues = resumir_costos(costos_despues)
    peticiones.append(evidencia("GET", "/finanzas/costos", codigo, duracion, despues))
    codigo, auditoria, duracion = pedir("GET", ruta_aud, token=token)
    auditoria_despues = auditoria.get("total_registros") if isinstance(auditoria, dict) else None
    peticiones.append(evidencia("GET", ruta_aud, codigo, duracion, {"total_registros": auditoria_despues}))
    codigo, historial, duracion = pedir("GET", f"/finanzas/activos/{ACTIVO}", token=token)
    costo_val = (historial or {}).get("valoracion_costo") if isinstance(historial, dict) else None
    libros_despues = costo_val.get("valor_contable_por_costo") if isinstance(costo_val, dict) else None
    peticiones.append(evidencia("GET", f"/finanzas/activos/{ACTIVO}", codigo, duracion, {"valor_contable_por_costo": libros_despues}))
    intacto = informe["costos"].get("total") == despues.get("total") and auditoria_antes == auditoria_despues and libros_antes == libros_despues

    if post_37 and post_37["http"] == 422 and post_37["code"] == "PERIODO_CONTABLE_CERRADO" and intacto:
        estado_37, motivo_37 = "APROBADO", (
            f"La fecha {post_37['fecha']} pertenece al período cerrado {post_37['periodo']}. "
            "El registro respondió 422 PERIODO_CONTABLE_CERRADO. Los costos, la auditoría y el valor en libros quedaron iguales.")
    elif post_37:
        estado_37, motivo_37 = "RECHAZADO", f"La respuesta fue {post_37['http']} {post_37['code']} y la comparación de persistencia dio intacto={intacto}."
    else:
        estado_37, motivo_37 = "BLOQUEADO", "No hay un período cerrado con un período abierto posterior. Enviar el costo podría crear un período nuevo."
    informe["escenarios"].append({"subcaso": "TC-M06-37", "estado": estado_37, "motivo": motivo_37, "post": post_37, "sin_persistencia": intacto})
    pendientes = informe["costos"].get("otro_pendiente")
    informe["escenarios"].append({
        "subcaso": "TC-M06-41", "estado": "BLOQUEADO", "cierre_ejecutado": False, "otro_pendiente": pendientes,
        "motivo": "No se envió el cierre. No existe un costo OTRO pendiente en un período aislado. La prevalidación de los períodos abiertos se consultó sin modificarlos.",
    })
    estados = [e["estado"] for e in informe["escenarios"]]
    informe["aprobados"] = estados.count("APROBADO")
    informe["rechazados"] = estados.count("RECHAZADO")
    informe["bloqueados"] = estados.count("BLOQUEADO")
    informe["porcentaje_aprobacion"] = round(informe["aprobados"] / 2 * 100)
    informe["analisis"] = (
        "# TC-M06-G111\n\nNo se usó SQL local.\n\n"
        f"- TC-M06-37: {estado_37}. {motivo_37}\n"
        f"- TC-M06-41: BLOQUEADO. Costos OTRO pendientes leídos: {pendientes}. El cierre no se ejecutó.\n"
    )
    informe["duracion_ms"] = round((time.perf_counter() - inicio) * 1000)
    guardar(informe)
    print(f"TC-M06-37 {estado_37} TC-M06-41 BLOQUEADO | {informe['porcentaje_aprobacion']}%")
    return 0 if informe["bloqueados"] == 0 and informe["rechazados"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
