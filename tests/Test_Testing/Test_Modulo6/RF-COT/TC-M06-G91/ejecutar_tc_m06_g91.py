"""TC-M06-G91 contra TEST.

No anula cotizaciones ni dispara el vencimiento. Solo lee el listado y la auditoría.

    python tests/Test_Testing/Test_Modulo6/RF-COT/TC-M06-G91/ejecutar_tc_m06_g91.py
"""
from __future__ import annotations

import html
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path

CARPETA = Path(__file__).resolve().parent
RESULTADOS = CARPETA / "resultados"
BASE_API = "https://api.inmero.co/api-sgpmp-test"
ZONA = "America/Bogota"
OMITIR = {"token", "access_token", "contrasena", "password", "hash_integridad", "numero_id_tributaria",
          "identificador", "finca", "condiciones", "correo_electronico", "justificacion"}


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
        salida = {}
        for k, v in valor.items():
            if k in OMITIR or k == "motivo_anulacion":
                salida[k] = {"omitido": True, "longitud": len(v)} if isinstance(v, str) else {"omitido": True}
            else:
                salida[k] = limpiar(v, profundidad + 1)
        return salida
    if isinstance(valor, list):
        return [limpiar(v, profundidad + 1) for v in valor[:20]]
    if isinstance(valor, str):
        return valor.replace("QA-M06-", "activo ")[:240]
    return valor


def evidencia(metodo, ruta, codigo, duracion, respuesta) -> dict:
    return {"metodo": metodo, "consulta": ruta.split("?")[0], "codigo": codigo, "duracion_ms": duracion,
            "escritura": False, "en": datetime.now(ZoneInfo(ZONA)).isoformat(), "respuesta": limpiar(respuesta)}


def ficha(item: dict) -> dict:
    motivo = item.get("motivo_anulacion")
    return {"id_cotizacion": item.get("id_cotizacion"), "estado": item.get("estado"),
            "fecha_emision": item.get("fecha_emision"), "fecha_vencimiento": item.get("fecha_vencimiento"),
            "id_periodo_contable": item.get("id_periodo_contable"), "estado_periodo": item.get("estado_periodo"),
            "activos_cotizados": item.get("activos_cotizados"), "version": item.get("version"),
            "valor_razonable_referencia": None if item.get("valor_razonable_referencia") is None else str(item.get("valor_razonable_referencia")),
            "tiene_motivo": bool(motivo)}


def render(informe: dict) -> str:
    filas = "".join(
        f"<tr><td>{html.escape(s['subcaso'])}</td><td>{html.escape(s['estado'])}</td><td>{html.escape(s['motivo'])}</td></tr>"
        for s in informe["subcasos"]
    )
    return f"""<!DOCTYPE html><html lang="es"><head><meta charset="utf-8"><title>TC-M06-G91</title>
<style>body{{font-family:Segoe UI,sans-serif;margin:2rem;line-height:1.45}}table{{border-collapse:collapse;width:100%}}
th,td{{border:1px solid #ccc;padding:.45rem .6rem;text-align:left;vertical-align:top}}th{{background:#f3f3f3}}
pre{{white-space:pre-wrap}}</style></head><body>
<h1>Módulo 6 — RF-COT — TC-M06-G91</h1>
<p>Generado: {html.escape(informe['generado_en'])}. No se anuló ni se venció ninguna cotización.</p>
<p>Aprobación: {informe['porcentaje_aprobacion']} %.</p>
<table><tr><th>Subcaso</th><th>Estado</th><th>Motivo</th></tr>{filas}</table>
<h2>Contrato</h2><pre>{html.escape(informe['contrato'])}</pre>
<h2>Cotizaciones leídas</h2><pre>{html.escape(json.dumps(informe.get('cotizaciones'), ensure_ascii=False, indent=2))}</pre>
</body></html>"""


def guardar(informe: dict) -> None:
    RESULTADOS.mkdir(parents=True, exist_ok=True)
    (RESULTADOS / "resultado_ejecucion_TC-M06-G91.html").write_text(render(informe), encoding="utf-8")
    (RESULTADOS / "resumen_ejecucion_TC-M06-G91.json").write_text(
        json.dumps({k: v for k, v in informe.items() if k != "analisis"}, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    (RESULTADOS / "evidencia_peticiones_TC-M06-G91.json").write_text(json.dumps({
        "caso": "TC-M06-G91", "generado_en": informe["generado_en"], "peticiones": informe["peticiones"],
        "anulacion_ejecutada": False, "vencimiento_ejecutado": False,
    }, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    (RESULTADOS / "analisis_hallazgos_TC-M06-G91.md").write_text(informe["analisis"], encoding="utf-8")


def main() -> int:
    inicio = time.perf_counter()
    peticiones = []
    hoy = datetime.now(ZoneInfo(ZONA)).date().isoformat()
    contrato = (
        "La anulación es POST /finanzas/cotizaciones/{id}/anulacion. Exige version y motivo_anulacion de al menos 20 caracteres. "
        "El permiso es cotizaciones con la acción desactivar. Solo procede si el estado es COTIZADO y el período no está cerrado. "
        "Pasa a ANULADA, guarda el motivo y escribe COTIZACION_ANULADA con id_referencia igual al id de la cotización. "
        "No hay ruta para reactivarla. Un estado distinto de COTIZADO responde 422 COTIZACION_NO_MODIFICABLE. "
        "El vencimiento no tiene endpoint. El proceso de fondo de main.py lo llama una vez por día UTC, dentro de un ciclo de 60 segundos. "
        "vencer actualiza a VENCIDA las cotizaciones COTIZADO con fecha de vencimiento anterior a hoy y período no cerrado, "
        "y escribe COTIZACION_VENCIDA con actor de sistema. Una fecha de vencimiento nula no entra en esa condición. "
        "Ese proceso también incorpora provisiones y eventos, así que no se disparó."
    )
    informe = {
        "caso": "TC-M06-G91", "ambiente": BASE_API, "generado_en": datetime.now(ZoneInfo(ZONA)).isoformat(),
        "hoy": hoy, "contrato": contrato, "cotizaciones": [], "auditoria": {}, "peticiones": peticiones,
        "anulacion_ejecutada": False, "vencimiento_ejecutado": False,
    }
    correo, contrasena = os.environ.get("QA_CORREO"), os.environ.get("QA_CONTRASENA")
    if not correo or not contrasena:
        raise SystemExit("Defina QA_CORREO y QA_CONTRASENA.")
    codigo, login, duracion = pedir("POST", "/sesiones/", {"correo_electronico": correo, "contrasena": contrasena})
    token = login.get("token") if isinstance(login, dict) else None
    peticiones.append(evidencia("POST", "/sesiones/", codigo, duracion, limpiar(login if isinstance(login, dict) else {})))
    if not token:
        informe["subcasos"] = [
            {"subcaso": "TC-M06-51", "estado": "BLOQUEADO", "motivo": "TEST no completó el inicio de sesión."},
            {"subcaso": "TC-M06-52", "estado": "BLOQUEADO", "motivo": "TEST no completó el inicio de sesión."},
        ]
        informe.update({"aprobados": 0, "rechazados": 0, "bloqueados": 2, "requiere_aclaracion": 0, "porcentaje_aprobacion": 0,
                        "analisis": "# TC-M06-G91\n\nNo hubo sesión.\n"})
        guardar(informe)
        print("SIN SESION")
        return 2
    codigo, perfil, duracion = pedir("GET", "/usuarios/me", token=token)
    informe["rol"] = perfil.get("nombre_rol") if isinstance(perfil, dict) else None
    peticiones.append(evidencia("GET", "/usuarios/me", codigo, duracion, {"nombre_rol": informe["rol"]}))
    codigo, permisos, duracion = pedir("GET", "/sesiones/me/permisos", token=token)
    acciones = [p.get("id_accion") for p in (permisos.get("permisos") or []) if isinstance(p, dict) and p.get("nombre_recurso") == "cotizaciones"] if isinstance(permisos, dict) else []
    informe["puede_anular"] = 4 in acciones
    peticiones.append(evidencia("GET", "/sesiones/me/permisos", codigo, duracion, {"puede_anular": informe["puede_anular"]}))
    codigo, cotizaciones, duracion = pedir("GET", "/finanzas/cotizaciones", token=token)
    fichas = [ficha(c) for c in cotizaciones] if isinstance(cotizaciones, list) else []
    informe["cotizaciones"] = fichas
    informe["estados"] = dict(Counter(c["estado"] for c in fichas))
    peticiones.append(evidencia("GET", "/finanzas/cotizaciones", codigo, duracion, {"total": len(fichas), "estados": informe["estados"], "cotizaciones": fichas}))
    for tipo in ("COTIZACION_ANULADA", "COTIZACION_VENCIDA"):
        ruta = "/finanzas/auditoria?" + urllib.parse.urlencode([
            ("tipo_evento", tipo), ("formato", "TECNICO"), ("tamano", "5"), ("orden", "DESC")])
        codigo, auditoria, duracion = pedir("GET", ruta, token=token)
        eventos = []
        if isinstance(auditoria, dict):
            for evento in auditoria.get("eventos") or []:
                eventos.append({"id_evento": evento.get("id_evento"), "id_referencia": evento.get("id_referencia"),
                                 "timestamp_evento": evento.get("timestamp_evento"), "tipo_actor": evento.get("tipo_actor")})
        informe["auditoria"][tipo] = {"total": auditoria.get("total_registros") if isinstance(auditoria, dict) else None, "muestra": eventos}
        peticiones.append(evidencia("GET", ruta, codigo, duracion, informe["auditoria"][tipo]))
    cotizadas = [c for c in fichas if c["estado"] == "COTIZADO"]
    informe["subcasos"] = [
        {"subcaso": "TC-M06-51", "estado": "BLOQUEADO",
         "motivo": "No hay una cotización COTIZADO aislada y autorizada. Anular una existente sería irreversible."},
        {"subcaso": "TC-M06-52", "estado": "BLOQUEADO",
         "motivo": "No hay una cotización COTIZADO aislada con vencimiento pasado, y el proceso de fondo no se ejecutó porque también escribe provisiones y eventos."},
    ]
    if cotizadas:
        informe["subcasos"][0]["motivo"] = "Hay cotizaciones COTIZADO, pero son compartidas. No se anularon."
        informe["subcasos"][1]["motivo"] = "Hay cotizaciones COTIZADO compartidas. No se disparó el vencimiento."
    informe["aprobados"] = 0
    informe["rechazados"] = 0
    informe["bloqueados"] = 2
    informe["requiere_aclaracion"] = 0
    informe["porcentaje_aprobacion"] = 0
    informe["hallazgos"] = [
        "BLOQUEO DE PRUEBA: la anulación y el vencimiento cambian cotizaciones compartidas. No se ejecutaron.",
    ]
    informe["analisis"] = (
        "# TC-M06-G91\n\nNo se usó SQL local. No se anuló ni se venció ninguna cotización.\n\n"
        f"Leídas: {len(fichas)}. Estados: {informe['estados']}. Puede anular: {informe['puede_anular']}.\n"
        f"COTIZACION_ANULADA: {informe['auditoria']['COTIZACION_ANULADA']['total']}. "
        f"COTIZACION_VENCIDA: {informe['auditoria']['COTIZACION_VENCIDA']['total']}.\n"
        "TC-M06-51 y TC-M06-52: BLOQUEADO.\n"
    )
    informe["duracion_ms"] = round((time.perf_counter() - inicio) * 1000)
    guardar(informe)
    print("TC-M06-51 BLOQUEADO TC-M06-52 BLOQUEADO", informe["estados"], "anular", informe["puede_anular"])
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
