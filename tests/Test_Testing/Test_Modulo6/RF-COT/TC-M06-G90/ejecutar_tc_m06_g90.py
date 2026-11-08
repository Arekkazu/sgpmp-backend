"""TC-M06-G90 contra TEST.

No registra la cotización. Una alta válida insertaría la fila y el evento
COTIZACION_REGISTRADA sobre un activo compartido.

    python tests/Test_Testing/Test_Modulo6/RF-COT/TC-M06-G90/ejecutar_tc_m06_g90.py
"""
from __future__ import annotations

import html
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path

CARPETA = Path(__file__).resolve().parent
RESULTADOS = CARPETA / "resultados"
BASE_API = "https://api.inmero.co/api-sgpmp-test"
ZONA = "America/Bogota"
OMITIR = {"token", "access_token", "contrasena", "password", "hash_integridad", "numero_id_tributaria",
          "identificador", "finca", "razon_social", "condiciones", "correo_electronico"}


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
        with urllib.request.urlopen(req, timeout=40) as resp:
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
        return [limpiar(v, profundidad + 1) for v in valor[:15]]
    if isinstance(valor, str):
        return valor.replace("QA-M06-", "activo ")[:240]
    return valor


def evidencia(metodo, ruta, codigo, duracion, respuesta, cuerpo=None) -> dict:
    return {"metodo": metodo, "consulta": ruta.split("?")[0], "codigo": codigo, "duracion_ms": duracion,
            "escritura": False, "en": datetime.now(ZoneInfo(ZONA)).isoformat(), "cuerpo": cuerpo,
            "respuesta": limpiar(respuesta)}


def ficha(activo: dict) -> dict:
    return {"id_activo_biologico": activo.get("id_activo_biologico"), "estado": activo.get("estado"),
            "especie": activo.get("especie"), "valor_razonable_neto": None if activo.get("valor_razonable_neto") is None else str(activo.get("valor_razonable_neto")),
            "fecha_calculo": activo.get("fecha_calculo"), "valorado_por_costo": activo.get("valorado_por_costo")}


def render(informe: dict) -> str:
    return f"""<!DOCTYPE html><html lang="es"><head><meta charset="utf-8"><title>TC-M06-G90</title>
<style>body{{font-family:Segoe UI,sans-serif;margin:2rem;line-height:1.45}}table{{border-collapse:collapse;width:100%}}
th,td{{border:1px solid #ccc;padding:.45rem .6rem;text-align:left;vertical-align:top}}th{{background:#f3f3f3}}
pre{{white-space:pre-wrap}}</style></head><body>
<h1>Módulo 6 — RF-COT — TC-M06-G90</h1>
<p>Generado: {html.escape(informe['generado_en'])}. No se registró la cotización.</p>
<table><tr><th>Subcaso</th><td>TC-M06-50</td></tr>
<tr><th>Estado</th><td>{html.escape(informe['estado'])}</td></tr>
<tr><th>Porcentaje</th><td>{informe['porcentaje_aprobacion']} %</td></tr></table>
<h2>Activo leído</h2><pre>{html.escape(json.dumps(informe.get('activo'), ensure_ascii=False, indent=2))}</pre>
<h2>Contrato</h2><pre>{html.escape(informe['contrato'])}</pre>
<h2>Hallazgos</h2><ul>{''.join(f'<li>{html.escape(h)}</li>' for h in informe['hallazgos'])}</ul>
</body></html>"""


def guardar(informe: dict) -> None:
    RESULTADOS.mkdir(parents=True, exist_ok=True)
    (RESULTADOS / "resultado_ejecucion_TC-M06-G90.html").write_text(render(informe), encoding="utf-8")
    (RESULTADOS / "resumen_ejecucion_TC-M06-G90.json").write_text(
        json.dumps({k: v for k, v in informe.items() if k != "analisis"}, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    (RESULTADOS / "evidencia_peticiones_TC-M06-G90.json").write_text(json.dumps({
        "caso": "TC-M06-G90", "generado_en": informe["generado_en"], "peticiones": informe["peticiones"],
        "registro_ejecutado": False, "sql_local": False,
    }, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    (RESULTADOS / "analisis_hallazgos_TC-M06-G90.md").write_text(informe["analisis"], encoding="utf-8")


def main() -> int:
    inicio = time.perf_counter()
    peticiones = []
    contrato = (
        "POST /finanzas/cotizaciones responde 201 con estado COTIZADO. No llama al contabilizador de asientos "
        "ni a M07. Inserta la cotización y el evento COTIZACION_REGISTRADA. El valor razonable se lee y se copia "
        "como referencia; no se actualiza. periodo_para puede crear un período si no hay uno abierto posterior. "
        "GET /integracion/auditoria, usado sin permiso, escribe ACCESO_AUDITORIA_DENEGADO, así que no se consultó. "
        "La vista AAEF del productor exige el NIT y un token de canal. No se llamó."
    )
    informe = {
        "caso": "TC-M06-G90", "subcaso": "TC-M06-50", "ambiente": BASE_API,
        "generado_en": datetime.now(ZoneInfo(ZONA)).isoformat(), "contrato": contrato,
        "registro_ejecutado": False, "estado": "BLOQUEADO", "porcentaje_aprobacion": 0,
        "activo": None, "conteos": {}, "peticiones": peticiones, "hallazgos": [], "newman_ejecutado": False,
    }
    correo, contrasena = os.environ.get("QA_CORREO"), os.environ.get("QA_CONTRASENA")
    if not correo or not contrasena:
        raise SystemExit("Defina QA_CORREO y QA_CONTRASENA.")
    codigo, login, duracion = pedir("POST", "/sesiones/", {"correo_electronico": correo, "contrasena": contrasena})
    token = login.get("token") if isinstance(login, dict) else None
    peticiones.append(evidencia("POST", "/sesiones/", codigo, duracion, limpiar(login if isinstance(login, dict) else {})))
    if not token:
        informe["hallazgos"] = ["BLOQUEO DE PRUEBA: TEST no completó el inicio de sesión."]
        informe["analisis"] = "# TC-M06-G90\n\nNo se registró la cotización. No hubo sesión.\n"
        guardar(informe)
        print("SIN SESION")
        return 2
    codigo, perfil, duracion = pedir("GET", "/usuarios/me", token=token)
    informe["rol"] = perfil.get("nombre_rol") if isinstance(perfil, dict) else None
    peticiones.append(evidencia("GET", "/usuarios/me", codigo, duracion, {"nombre_rol": informe["rol"]}))
    codigo, permisos, duracion = pedir("GET", "/sesiones/me/permisos", token=token)
    acciones = sorted(p.get("id_accion") for p in (permisos.get("permisos") or [])
                      if isinstance(p, dict) and p.get("nombre_recurso") == "cotizaciones") if isinstance(permisos, dict) else []
    informe["puede_crear"] = 1 in acciones
    peticiones.append(evidencia("GET", "/sesiones/me/permisos", codigo, duracion, {"cotizaciones_puede_crear": informe["puede_crear"]}))
    codigo, activos, duracion = pedir("GET", "/finanzas/activos", token=token)
    candidatos = [ficha(a) for a in activos if isinstance(a, dict) and str(a.get("estado", "")).upper() == "ACTIVO" and a.get("valor_razonable_neto") is not None] if isinstance(activos, list) else []
    informe["activo"] = candidatos[0] if candidatos else None
    peticiones.append(evidencia("GET", "/finanzas/activos", codigo, duracion, {"con_valor_razonable": len(candidatos), "elegido": informe["activo"]}))
    if informe["activo"]:
        activo_id = informe["activo"]["id_activo_biologico"]
        codigo, historia, duracion = pedir("GET", f"/finanzas/activos/{activo_id}", token=token)
        lineas = historia.get("lineas") if isinstance(historia, dict) else None
        calculos = historia.get("calculos") if isinstance(historia, dict) else None
        informe["historial"] = {"http": codigo, "lineas": len(lineas) if isinstance(lineas, list) else None,
                                 "calculos": len(calculos) if isinstance(calculos, list) else None}
        peticiones.append(evidencia("GET", f"/finanzas/activos/{activo_id}", codigo, duracion, informe["historial"]))
        codigo, biologico, duracion = pedir("GET", f"/activos-biologicos/{activo_id}", token=token)
        informe["biologico"] = {"http": codigo, "nombre_estado": biologico.get("nombre_estado") if isinstance(biologico, dict) else None}
        peticiones.append(evidencia("GET", f"/activos-biologicos/{activo_id}", codigo, duracion, informe["biologico"]))
    codigo, lineas_periodo, duracion = pedir("GET", "/finanzas/lineas?id_periodo_contable=8", token=token)
    informe["lineas_periodo_8"] = len(lineas_periodo) if isinstance(lineas_periodo, list) else None
    peticiones.append(evidencia("GET", "/finanzas/lineas", codigo, duracion, {"periodo": 8, "total": informe["lineas_periodo_8"]}))
    codigo, cotizaciones, duracion = pedir("GET", "/finanzas/cotizaciones", token=token)
    informe["cotizaciones"] = len(cotizaciones) if isinstance(cotizaciones, list) else None
    peticiones.append(evidencia("GET", "/finanzas/cotizaciones", codigo, duracion, {"total": informe["cotizaciones"]}))
    ruta_aud = "/finanzas/auditoria?" + urllib.parse.urlencode([
        ("tipo_evento", "COTIZACION_REGISTRADA"), ("formato", "TECNICO"), ("tamano", "1")])
    codigo, auditoria, duracion = pedir("GET", ruta_aud, token=token)
    informe["eventos_cotizacion"] = auditoria.get("total_registros") if isinstance(auditoria, dict) else None
    peticiones.append(evidencia("GET", ruta_aud, codigo, duracion, {"total_registros": informe["eventos_cotizacion"]}))
    informe["conteos"] = {
        "cotizaciones": informe["cotizaciones"], "eventos_cotizacion_registrada": informe["eventos_cotizacion"],
        "lineas_periodo_abierto_diciembre": informe["lineas_periodo_8"],
        "lineas_del_activo": (informe.get("historial") or {}).get("lineas"),
        "aaef_consultado": False,
    }
    informe["hallazgos"] = [
        "BLOQUEO DE PRUEBA: el activo con valor razonable pertenece al catálogo compartido. Registrar la cotización insertaría la fila y el evento de auditoría.",
        "La ausencia de asientos y de exportaciones AAEF se ve en el código del caso de uso. No se comprobó con un alta real.",
    ]
    informe["analisis"] = (
        "# TC-M06-G90\n\nNo se usó SQL local. No se consultó la auditoría de M07 porque una consulta sin permiso escribe un evento.\n\n"
        "POST /finanzas/cotizaciones no llama a asientos ni a AAEF. Sí guarda la cotización y COTIZACION_REGISTRADA.\n"
        f"Activo leído: {informe['activo']}. Cotizaciones existentes: {informe['cotizaciones']}. "
        f"Eventos COTIZACION_REGISTRADA: {informe['eventos_cotizacion']}. Líneas del período 8: {informe['lineas_periodo_8']}.\n"
        "TC-M06-50: BLOQUEADO. No hubo comparación posterior porque no hubo registro.\n"
    )
    informe["duracion_ms"] = round((time.perf_counter() - inicio) * 1000)
    guardar(informe)
    print("TC-M06-50 BLOQUEADO", informe["activo"], "lineas8", informe["lineas_periodo_8"], "cotizaciones", informe["cotizaciones"])
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
