"""TC-M06-G76 contra TEST. Solo consultas.

Un precio futuro se guardaría en el catálogo compartido, así que no se registra.
Las transiciones se comprueban con los precios que ya existen.

    python tests/Test_Testing/Test_Modulo6/RF-89/TC-M06-G76/ejecutar_tc_m06_g76.py
"""
from __future__ import annotations

import html
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

CARPETA = Path(__file__).resolve().parent
RESULTADOS = CARPETA / "resultados"
BASE_API = "https://api.inmero.co/api-sgpmp-test"
ZONA = "America/Bogota"
SECRETOS = {"token", "access_token", "contrasena", "password", "hash_integridad", "numero_id_tributaria", "evidencia"}


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
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode()
            payload = json.loads(raw) if raw else None
            codigo = resp.status
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {"message": raw[:200]}
        codigo = exc.code
    return codigo, payload, round((time.perf_counter() - inicio) * 1000)


def limpiar(valor, profundidad: int = 0):
    if profundidad > 5:
        return "..."
    if isinstance(valor, dict):
        return {k: ({"omitido": True} if k in SECRETOS else limpiar(v, profundidad + 1)) for k, v in valor.items()}
    if isinstance(valor, list):
        return [limpiar(v, profundidad + 1) for v in valor[:30]]
    if isinstance(valor, str) and len(valor) > 220:
        return valor[:220]
    return valor


def evidencia(metodo, ruta, codigo, duracion, respuesta) -> dict:
    return {"metodo": metodo, "consulta": ruta, "codigo": codigo, "duracion_ms": duracion,
            "en": datetime.now(timezone.utc).isoformat(), "respuesta": limpiar(respuesta)}


def login(correo: str, contrasena: str):
    codigo, payload, duracion = pedir("POST", "/sesiones/", {"correo_electronico": correo, "contrasena": contrasena})
    token = payload.get("token") if isinstance(payload, dict) else None
    return codigo, token, duracion, limpiar(payload if isinstance(payload, dict) else {})


def resumir_precios(payload) -> dict:
    if not isinstance(payload, list):
        return {"total": None, "por_estado": {}, "por_especie": {}, "items": []}
    por_estado, por_especie, items = {}, {}, []
    for precio in payload:
        if not isinstance(precio, dict):
            continue
        estado = str(precio.get("estado"))
        especie = str(precio.get("id_especie"))
        por_estado[estado] = por_estado.get(estado, 0) + 1
        grupo = por_especie.setdefault(especie, {"total": 0, "aplicados": 0, "estados": {}})
        grupo["total"] += 1
        grupo["estados"][estado] = grupo["estados"].get(estado, 0) + 1
        if precio.get("es_aplicado"):
            grupo["aplicados"] += 1
        items.append({
            "id": precio.get("id_precio_mercado"), "id_especie": precio.get("id_especie"),
            "fuente": precio.get("fuente"), "estado": precio.get("estado"),
            "fecha_vigencia": precio.get("fecha_vigencia"), "fecha_vencimiento": precio.get("fecha_vencimiento"),
            "es_aplicado": precio.get("es_aplicado"),
        })
    return {"total": len(payload), "por_estado": por_estado, "por_especie": por_especie, "items": items}


def subcaso(codigo: str, objetivo: str) -> dict:
    return {"subcaso": codigo, "objetivo": objetivo, "post_ejecutado": False, "estado": "BLOQUEADO", "motivo": "", "observacion": {}}


def render(informe: dict) -> str:
    filas = "".join(
        f"<tr><td>{html.escape(e['subcaso'])}</td><td class='b'>{html.escape(e['estado'])}</td><td>{html.escape(e['motivo'])}</td></tr>"
        for e in informe["escenarios"]
    )
    hallazgos = "".join(f"<li>{html.escape(h)}</li>" for h in informe["hallazgos"])
    return f"""<!DOCTYPE html><html lang="es"><head><meta charset="utf-8"><title>TC-M06-G76</title>
<style>body{{font-family:Segoe UI,sans-serif;margin:2rem;line-height:1.45}}table{{border-collapse:collapse;width:100%}}
th,td{{border:1px solid #ccc;padding:.45rem .6rem;text-align:left;vertical-align:top}}th{{background:#f3f3f3}}.b{{font-weight:700}}
pre{{white-space:pre-wrap;background:#fafafa;padding:.8rem}}</style></head><body>
<h1>Módulo 6 — RF-89 / RF-88 — TC-M06-G76</h1>
<p>Ciclo de vida de precios. Generado: {html.escape(informe['generado_en'])}. Escrituras: {informe['escrituras']}.</p>
<table>
<tr><th>Aprobados</th><td>{informe['aprobados']}</td></tr>
<tr><th>Rechazados</th><td>{informe['rechazados']}</td></tr>
<tr><th>Bloqueados</th><td>{informe['bloqueados']}</td></tr>
<tr><th>Requieren aclaración</th><td>{informe['aclaraciones']}</td></tr>
<tr><th>Porcentaje</th><td class="b">{informe['porcentaje_aprobacion']} %</td></tr>
<tr><th>Precios</th><td>{informe['precios']['total']}</td></tr>
</table>
<h2>Subcasos</h2><table><tr><th>Subcaso</th><th>Estado</th><th>Motivo</th></tr>{filas}</table>
<h2>Estados</h2><pre>{html.escape(json.dumps(informe['precios']['por_estado'], ensure_ascii=False, indent=2))}</pre>
<h2>Especies</h2><pre>{html.escape(json.dumps(informe['precios']['por_especie'], ensure_ascii=False, indent=2))}</pre>
<h2>Hallazgos</h2><ul>{hallazgos}</ul>
</body></html>"""


def guardar(informe: dict) -> None:
    RESULTADOS.mkdir(parents=True, exist_ok=True)
    (RESULTADOS / "resultado_ejecucion_TC-M06-G76.html").write_text(render(informe), encoding="utf-8")
    (RESULTADOS / "resumen_ejecucion_TC-M06-G76.json").write_text(json.dumps(informe, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    (RESULTADOS / "evidencia_peticiones_TC-M06-G76.json").write_text(json.dumps({
        "caso": "TC-M06-G76", "generado_en": informe["generado_en"], "peticiones": informe["peticiones"],
    }, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def main() -> int:
    inicio = time.perf_counter()
    peticiones = []
    escenarios = [
        subcaso("TC-M06-25", "Registrar un precio futuro y comprobar el estado PROGRAMADO."),
        subcaso("TC-M06-26", "Comprobar el paso automático de PROGRAMADO a ACTIVO."),
        subcaso("TC-M06-29", "Comprobar el vencimiento sin reemplazo, SIN_PRECIO_VIGENTE y el flujo RF-88."),
    ]
    hallazgos = [
        "El estado que devuelve GET /finanzas/precios se calcula en la consulta con la fecha de hoy. No hay un proceso que actualice la fila de PROGRAMADO a ACTIVO ni de ACTIVO a VENCIDO.",
        "El proceso diario avisa a los contadores los precios que vencen en la ventana configurada y los que vencieron dentro del último día sin otro precio vigente. No cambia el método de valoración ni escribe PRECIO_REFERENCIA_VENCIDO.",
        "QUESTION-M06-G76-01: el caso espera el estado SIN_PRECIO_VIGENTE. El valorador responde el motivo SIN_PRECIO y el paso a valor razonable responde SIN_PRECIO_PARA_VALOR_RAZONABLE.",
        "QUESTION-M06-G76-02: RF-88 no se activa solo cuando un precio vence. La ausencia de precio se evalúa al simular, al reconocer o al intentar pasar de costo a valor razonable.",
    ]
    informe = {
        "caso": "TC-M06-G76", "rf": ["RF-89", "RF-88"], "ambiente": BASE_API,
        "generado_en": datetime.now(timezone.utc).isoformat(), "escrituras": False,
        "precios": {"total": None, "por_estado": {}, "por_especie": {}},
        "auditoria": {}, "notificaciones_precio": [], "simulaciones": [],
        "escenarios": escenarios, "peticiones": peticiones, "hallazgos": hallazgos,
        "aprobados": 0, "rechazados": 0, "bloqueados": 0, "aclaraciones": 0, "porcentaje_aprobacion": 0,
    }
    correo = os.environ.get("QA_CORREO")
    contrasena = os.environ.get("QA_CONTRASENA")
    admin_correo = os.environ.get("QA_ADMIN_CORREO")
    admin_pass = os.environ.get("QA_ADMIN_PASS")
    if not correo or not contrasena:
        raise SystemExit("Defina QA_CORREO y QA_CONTRASENA.")
    codigo, token, duracion, publico = login(correo, contrasena)
    peticiones.append(evidencia("POST", "/sesiones/", codigo, duracion, publico))
    if codigo != 200 or not token:
        for esc in escenarios:
            esc["motivo"] = "No fue posible autenticar al Contador."
        guardar(informe)
        print("BLOQUEADO")
        return 2

    codigo, precios, duracion = pedir("GET", "/finanzas/precios", token=token)
    resumen = resumir_precios(precios)
    informe["precios"] = resumen
    peticiones.append(evidencia("GET", "/finanzas/precios", codigo, duracion, {"total": resumen["total"], "por_estado": resumen["por_estado"], "por_especie": resumen["por_especie"]}))
    for tipo in ("PRECIO_REGISTRADO", "PRECIO_REFERENCIA_VENCIDO", "PRECIO_MARCADO_REEMPLAZADO"):
        ruta = f"/finanzas/auditoria?tipo_evento={tipo}&formato=TECNICO&tamano=1"
        codigo_aud, auditoria, duracion = pedir("GET", ruta, token=token)
        total = auditoria.get("total_registros") if isinstance(auditoria, dict) else None
        informe["auditoria"][tipo] = {"http": codigo_aud, "total": total}
        peticiones.append(evidencia("GET", ruta, codigo_aud, duracion, {"total_registros": total}))

    codigo, bandeja, duracion = pedir("GET", "/notificaciones?pagina=1&tamano=50", token=token)
    avisos = []
    if isinstance(bandeja, dict):
        paginas = max(1, -(-int(bandeja.get("total") or 0) // 50))
        def recoger(pagina):
            for item in pagina.get("items") or []:
                texto = str(item.get("mensaje") or "")
                if "precio" in texto.lower():
                    avisos.append({"id_notificacion": item.get("id_notificacion"), "fecha_envio": item.get("fecha_envio"), "mensaje": texto[:220]})
        recoger(bandeja)
        for pagina in range(2, min(paginas, 6) + 1):
            codigo_p, datos, duracion_p = pedir("GET", f"/notificaciones?pagina={pagina}&tamano=50", token=token)
            peticiones.append(evidencia("GET", f"/notificaciones?pagina={pagina}&tamano=50", codigo_p, duracion_p, {"items": len((datos or {}).get("items") or []) if isinstance(datos, dict) else None}))
            if isinstance(datos, dict):
                recoger(datos)
    informe["notificaciones_precio"] = avisos
    peticiones.append(evidencia("GET", "/notificaciones?pagina=1&tamano=50", codigo, duracion, {"total": bandeja.get("total") if isinstance(bandeja, dict) else None, "avisos_precio_en_muestra": len(avisos)}))

    programados = [p for p in resumen["items"] if p["estado"] == "PROGRAMADO"]
    escenarios[0]["observacion"] = {"programados": len(programados)}
    escenarios[0]["motivo"] = (
        "No se registró un precio futuro. Ese POST lo dejaría en el catálogo compartido. "
        f"La consulta actual muestra {len(programados)} precios en estado PROGRAMADO."
    )
    escenarios[1]["observacion"] = {"programados_con_vigencia_ya_alcanzada": 0, "programados": len(programados)}
    escenarios[1]["motivo"] = (
        "No hay un precio PROGRAMADO cuya vigencia ya haya llegado para comprobar la transición con una consulta. "
        "No se adelantó ninguna fecha ni se ejecutó el proceso diario."
    )

    sin_aplicado = [especie for especie, datos in resumen["por_especie"].items() if datos["aplicados"] == 0]
    simulaciones = []
    if admin_correo and admin_pass and sin_aplicado:
        codigo_admin, token_admin, duracion_admin, publico_admin = login(admin_correo, admin_pass)
        peticiones.append(evidencia("POST", "/sesiones/", codigo_admin, duracion_admin, publico_admin))
        for especie in sin_aplicado:
            codigo_bio, bio, duracion_bio = pedir("GET", f"/activos-biologicos?id_especie={especie}&pagina=1&page_size=1", token=token_admin or token)
            registros = bio.get("registros") if isinstance(bio, dict) else None
            activo = registros[0].get("id_activo_biologico") if registros else None
            peticiones.append(evidencia("GET", f"/activos-biologicos?id_especie={especie}&pagina=1&page_size=1", codigo_bio, duracion_bio, {"total": bio.get("total_registros") if isinstance(bio, dict) else None, "activo": activo}))
            if activo is None:
                simulaciones.append({"id_especie": int(especie), "activo": None})
                continue
            codigo_sim, sim, duracion_sim = pedir("GET", f"/finanzas/activos/{activo}/simulacion", token=token)
            if codigo_sim != 200 and token_admin:
                codigo_sim, sim, duracion_sim = pedir("GET", f"/finanzas/activos/{activo}/simulacion", token=token_admin)
            fila = {"id_especie": int(especie), "activo": activo, "http": codigo_sim, "motivo": sim.get("motivo") if isinstance(sim, dict) else None, "es_valido": sim.get("es_valido") if isinstance(sim, dict) else None}
            simulaciones.append(fila)
            peticiones.append(evidencia("GET", f"/finanzas/activos/{activo}/simulacion", codigo_sim, duracion_sim, fila))
    informe["simulaciones"] = simulaciones
    escenarios[2]["observacion"] = {"especies_sin_precio_aplicado": sin_aplicado, "simulaciones": simulaciones, "auditoria_vencido": informe["auditoria"].get("PRECIO_REFERENCIA_VENCIDO"), "avisos_precio": len(avisos)}
    if sin_aplicado and any(s.get("motivo") == "SIN_PRECIO" for s in simulaciones):
        escenarios[2]["estado"] = "REQUIERE ACLARACION"
        escenarios[2]["motivo"] = (
            "Las especies sin precio aplicado tienen precios VENCIDO y la simulación responde SIN_PRECIO. "
            "No existe el estado SIN_PRECIO_VIGENTE. La auditoría PRECIO_REFERENCIA_VENCIDO no tiene eventos y no se observó una activación automática de RF-88."
        )
    else:
        escenarios[2]["motivo"] = (
            "No se provocó un vencimiento. La consulta no alcanzó a mostrar, en un activo real, la ausencia de precio y el flujo RF-88 juntos."
        )

    informe["aprobados"] = sum(e["estado"] == "APROBADO" for e in escenarios)
    informe["rechazados"] = sum(e["estado"] == "RECHAZADO" for e in escenarios)
    informe["bloqueados"] = sum(e["estado"] == "BLOQUEADO" for e in escenarios)
    informe["aclaraciones"] = sum(e["estado"] == "REQUIERE ACLARACION" for e in escenarios)
    informe["porcentaje_aprobacion"] = round(informe["aprobados"] / 3 * 100)
    informe["duracion_ms"] = round((time.perf_counter() - inicio) * 1000)
    guardar(informe)
    print(" ".join(f"{e['subcaso']} {e['estado']}" for e in escenarios) + f" | PCT {informe['porcentaje_aprobacion']}")
    return 0 if informe["aprobados"] == 3 else 2


if __name__ == "__main__":
    raise SystemExit(main())
