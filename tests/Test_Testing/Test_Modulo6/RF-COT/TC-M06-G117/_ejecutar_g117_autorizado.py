# | Fecha      | Nombre | Que se hizo |
# |------------|--------|-------------|
# | 2026-11-13 | —      | Ejecución autorizada 48a/48b/49a (sin 49b); evidencias en ultima_evaluacion/. |
"""Ejecucion autorizada TC-M06-G117: solo POST negativos 48a, 48b y 49a.

No ejecuta 49b. No modifica DTO/use case. Conserva expectativa matriz para 48a/48b.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

BASE = "https://api.inmero.co/api-sgpmp-test"
ZONA = "America/Bogota"
TZ = ZoneInfo(ZONA)
ROOT = Path(__file__).resolve().parent
ULTIMA = ROOT / "resultados" / "ultima_evaluacion"
ACTIVO = 1569
NIT = "900000003"
FINCA = 467
PERIODO = 220
RESERVADAS = {9, 10}
SECRETOS = {
    "token", "access_token", "contrasena", "password", "hash_integridad",
    "numero_id_tributaria", "identificador", "finca", "correo_electronico", "nombre_usuario",
}


def pedir(metodo, ruta, cuerpo=None, token=None, timeout=30):
    datos = None if cuerpo is None else json.dumps(cuerpo, default=str).encode()
    headers = {"Accept": "application/json", "X-Zona-Horaria": ZONA}
    if cuerpo is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(BASE + ruta, data=datos, headers=headers, method=metodo)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode()
            return resp.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {"message": raw[:400]}
        return exc.code, payload
    except Exception as exc:
        return None, {"error": type(exc).__name__, "message": str(exc)[:200]}


def limpiar(v, d=0):
    if d > 8:
        return "..."
    if isinstance(v, dict):
        return {k: ({"omitido": True} if k in SECRETOS else limpiar(x, d + 1)) for k, x in v.items()}
    if isinstance(v, list):
        return [limpiar(x, d + 1) for x in v[:80]]
    if isinstance(v, str) and len(v) > 500:
        return v[:500]
    return v


def ahora():
    return datetime.now(timezone.utc).isoformat()


def code_de(payload):
    if not isinstance(payload, dict):
        return None
    return payload.get("error_code") or payload.get("code")


def snapshot_cotizaciones(token, pet, nota):
    c, data = pedir("GET", "/finanzas/cotizaciones", token=token)
    lista = data if isinstance(data, list) else []
    ids = [x.get("id_cotizacion") for x in lista if isinstance(x, dict)]
    sobre = [x for x in lista if isinstance(x, dict) and ACTIVO in (x.get("activos_cotizados") or [])]
    reservadas = {
        str(i): next((limpiar(x) for x in lista if isinstance(x, dict) and x.get("id_cotizacion") == i), None)
        for i in sorted(RESERVADAS)
    }
    out = {
        "total": len(lista),
        "ids": ids,
        "sobre_1569": [x.get("id_cotizacion") for x in sobre],
        "reservadas_9_10": reservadas,
    }
    pet.append({"metodo": "GET", "ruta": "/finanzas/cotizaciones", "codigo": c, "escritura": False,
                "en": ahora(), "nota": nota, "respuesta": out})
    return out


def snapshot_auditoria(token, pet, nota):
    ruta = "/finanzas/auditoria?tipo_evento=COTIZACION_REGISTRADA&formato=TECNICO&tamano=1&orden=DESC"
    c, data = pedir("GET", ruta, token=token)
    total = (data or {}).get("total_registros") if isinstance(data, dict) else None
    out = {"total_registros": total}
    pet.append({"metodo": "GET", "ruta": ruta, "codigo": c, "escritura": False,
                "en": ahora(), "nota": nota, "respuesta": out})
    return out


def snapshot_activo(token, pet, nota):
    c, det = pedir("GET", f"/finanzas/activos/{ACTIVO}", token=token)
    act = (det or {}).get("activo") if isinstance(det, dict) else None
    recs = (det or {}).get("reconocimientos") if isinstance(det, dict) else []
    if not isinstance(recs, list):
        recs = []
    rec = next((r for r in recs if isinstance(r, dict) and r.get("estado") == "CONFIRMADO"), None)
    out = {
        "http": c,
        "estado": (act or {}).get("estado") if isinstance(act, dict) else None,
        "id_finca": (act or {}).get("id_finca") if isinstance(act, dict) else None,
        "razon_social": (act or {}).get("razon_social") if isinstance(act, dict) else None,
        "indicador_valoracion": (rec or {}).get("indicador_valoracion") if isinstance(rec, dict) else None,
    }
    pet.append({"metodo": "GET", "ruta": f"/finanzas/activos/{ACTIVO}", "codigo": c, "escritura": False,
                "en": ahora(), "nota": nota, "respuesta": out})
    return out


def snapshot_periodo(token, pet, nota):
    ruta = f"/finanzas/periodos?numero_id_tributaria={NIT}"
    c, periodos = pedir("GET", ruta, token=token)
    p220 = next((p for p in (periodos or []) if isinstance(p, dict) and p.get("id_periodo_contable") == PERIODO), None)
    out = {
        "encontrado": p220 is not None,
        "id_periodo_contable": (p220 or {}).get("id_periodo_contable"),
        "estado": (p220 or {}).get("estado"),
        "fecha_inicio": (p220 or {}).get("fecha_inicio"),
        "fecha_fin": (p220 or {}).get("fecha_fin"),
        "fecha_cierre": (p220 or {}).get("fecha_cierre"),
        "razon_social": (p220 or {}).get("razon_social"),
    }
    pet.append({"metodo": "GET", "ruta": ruta, "codigo": c, "escritura": False,
                "en": ahora(), "nota": nota, "respuesta": {"periodo_220": out}})
    return out


def evaluar(escenario, http_real, code_real, checks):
    http_ok = http_real == escenario["esperado"]["http"]
    code_ok = code_real == escenario["esperado"]["code"]
    persistencia_ok = all([
        checks["sin_cotizacion_nueva"],
        checks["sin_evento_nuevo"],
        checks["reservadas_intactas"],
        checks["activo_sin_cambio"],
        checks["periodo_220_abierto"],
    ])
    if not persistencia_ok:
        return "BLOQUEADO", "Incidente de persistencia o proteccion de datos."
    if http_ok and code_ok:
        return "APROBADO", f"HTTP {http_real} {code_real}; sin persistencia."
    return "RECHAZADO", (
        f"Esperado HTTP {escenario['esperado']['http']} {escenario['esperado']['code']}; "
        f"recibido HTTP {http_real} {code_real}."
    )


def main():
    correo, clave = os.environ.get("QA_CORREO"), os.environ.get("QA_CONTRASENA")
    if not correo or not clave:
        raise SystemExit("Defina QA_CORREO y QA_CONTRASENA")

    ULTIMA.mkdir(parents=True, exist_ok=True)
    hoy = datetime.now(TZ).date()
    ayer = hoy - timedelta(days=1)

    pet = []
    informe = {
        "caso": "TC-M06-G117",
        "subcasos": ["TC-M06-48", "TC-M06-49"],
        "fase": "ejecucion_negativa_autorizada",
        "ambiente": BASE,
        "generado_en": ahora(),
        "autorizacion": "POST negativos 48a/48b/49a; sin 49b; sin alterar periodo 220 ni cotizaciones 9/10",
        "hoy_america_bogota": str(hoy),
        "ayer_america_bogota": str(ayer),
        "49b_ejecutado": False,
        "peticiones": pet,
        "escenarios": [],
        "discrepancias": [],
        "proteccion_datos": {},
        "dictamen": {},
    }

    # Auth
    c, login = pedir("POST", "/sesiones/", {"correo_electronico": correo, "contrasena": clave})
    token = login.get("token") if isinstance(login, dict) else None
    pet.append({"metodo": "POST", "ruta": "/sesiones/", "codigo": c, "escritura": True,
                "en": ahora(), "nota": "autenticacion_contador", "respuesta": {"ok": bool(token), "tipo": (login or {}).get("tipo") if isinstance(login, dict) else None}})
    if not token:
        informe["dictamen"] = {"categoria": "BLOQUEADO", "motivo": "No se obtuvo sesion Contador"}
        _guardar(informe)
        raise SystemExit("SIN SESION")

    baseline = {
        "cotizaciones": snapshot_cotizaciones(token, pet, "baseline_cotizaciones"),
        "auditoria": snapshot_auditoria(token, pet, "baseline_auditoria"),
        "activo_1569": snapshot_activo(token, pet, "baseline_activo_1569"),
        "periodo_220": snapshot_periodo(token, pet, "baseline_periodo_220"),
    }
    informe["baseline"] = baseline

    escenarios = [
        {
            "id": "48a",
            "subcaso": "TC-M06-48",
            "nombre": "Valor propuesto cero",
            "esperado": {"http": 422, "code": "VALOR_COTIZACION_INVALIDO"},
            "cuerpo": {"activos_cotizados": [ACTIVO], "valor_cotizacion_propuesto": 0},
        },
        {
            "id": "48b",
            "subcaso": "TC-M06-48",
            "nombre": "Valor propuesto negativo",
            "esperado": {"http": 422, "code": "VALOR_COTIZACION_INVALIDO"},
            "cuerpo": {"activos_cotizados": [ACTIVO], "valor_cotizacion_propuesto": -1},
        },
        {
            "id": "49a",
            "subcaso": "TC-M06-49",
            "nombre": "Vencimiento anterior a emision",
            "esperado": {"http": 422, "code": "FECHA_VENCIMIENTO_INVALIDA"},
            "cuerpo": {
                "activos_cotizados": [ACTIVO],
                "valor_cotizacion_propuesto": "1000.0000",
                "fecha_vencimiento": str(ayer),
            },
        },
    ]

    incidente = None
    for esc in escenarios:
        pre_cots = snapshot_cotizaciones(token, pet, f"pre_{esc['id']}_cotizaciones")
        pre_aud = snapshot_auditoria(token, pet, f"pre_{esc['id']}_auditoria")
        pre_act = snapshot_activo(token, pet, f"pre_{esc['id']}_activo")
        pre_per = snapshot_periodo(token, pet, f"pre_{esc['id']}_periodo")

        http, resp = pedir("POST", "/finanzas/cotizaciones", cuerpo=esc["cuerpo"], token=token)
        code = code_de(resp)
        pet.append({
            "metodo": "POST", "ruta": "/finanzas/cotizaciones", "codigo": http, "escritura": True,
            "en": ahora(), "nota": f"post_{esc['id']}",
            "request": esc["cuerpo"],
            "respuesta": limpiar(resp),
        })

        post_cots = snapshot_cotizaciones(token, pet, f"post_{esc['id']}_cotizaciones")
        post_aud = snapshot_auditoria(token, pet, f"post_{esc['id']}_auditoria")
        post_act = snapshot_activo(token, pet, f"post_{esc['id']}_activo")
        post_per = snapshot_periodo(token, pet, f"post_{esc['id']}_periodo")

        ids_antes = set(pre_cots["ids"])
        ids_despues = set(post_cots["ids"])
        ids_nuevos = sorted(ids_despues - ids_antes)
        sin_cot = len(ids_nuevos) == 0 and pre_cots["total"] == post_cots["total"]
        sin_evt = pre_aud.get("total_registros") == post_aud.get("total_registros")
        reservadas_ok = (
            pre_cots["reservadas_9_10"] == post_cots["reservadas_9_10"]
            and set(post_cots.get("sobre_1569") or []) >= RESERVADAS
            and 9 in ids_despues and 10 in ids_despues
        )
        activo_ok = (
            pre_act.get("estado") == post_act.get("estado") == "ACTIVO"
            and pre_act.get("id_finca") == post_act.get("id_finca") == FINCA
            and pre_act.get("indicador_valoracion") == post_act.get("indicador_valoracion")
        )
        periodo_ok = post_per.get("estado") == "ABIERTO" and post_per.get("id_periodo_contable") == PERIODO

        checks = {
            "http_esperado": http == esc["esperado"]["http"],
            "code_esperado": code == esc["esperado"]["code"],
            "sin_cotizacion_nueva": sin_cot,
            "sin_evento_nuevo": sin_evt,
            "reservadas_intactas": reservadas_ok,
            "activo_sin_cambio": activo_ok,
            "periodo_220_abierto": periodo_ok,
        }
        estado, motivo = evaluar(esc, http, code, checks)

        # DISC-G117-01 confirmation for 48a/48b
        disc = None
        if esc["id"] in ("48a", "48b") and http == 400 and code == "VAL_ENTRADA":
            disc = {
                "id": "DISC-G117-01",
                "escenario": esc["id"],
                "matriz": "HTTP 422 VALOR_COTIZACION_INVALIDO",
                "real": f"HTTP {http} {code}",
                "confirmado": True,
                "nota": "DTO Field(gt=0) intercepta antes de FA-6; expectativa matriz conservada → RECHAZADO",
            }
            informe["discrepancias"].append(disc)

        resultado = {
            "escenario_id": esc["id"],
            "subcaso": esc["subcaso"],
            "nombre": esc["nombre"],
            "activo": ACTIVO,
            "esperado": esc["esperado"],
            "estado": estado,
            "motivo": motivo,
            "request": esc["cuerpo"],
            "post": {"http": http, "code": code, "respuesta": limpiar(resp), "en": ahora()},
            "verificaciones": {
                "checks": checks,
                "http": http,
                "code": code,
                "cotizaciones_antes": pre_cots["total"],
                "cotizaciones_despues": post_cots["total"],
                "ids_nuevos": ids_nuevos,
                "eventos_antes": pre_aud.get("total_registros"),
                "eventos_despues": post_aud.get("total_registros"),
                "activo_antes": pre_act,
                "activo_despues": post_act,
                "periodo_220_antes": pre_per,
                "periodo_220_despues": post_per,
                "reservadas_antes": pre_cots["reservadas_9_10"],
                "reservadas_despues": post_cots["reservadas_9_10"],
            },
            "discrepancia": disc,
        }
        informe["escenarios"].append(resultado)
        (ULTIMA / f"evidencia_escenario_{esc['id']}_TC-M06-G117.json").write_text(
            json.dumps({"caso": "TC-M06-G117", **resultado}, ensure_ascii=False, indent=2, default=str) + "\n",
            encoding="utf-8",
        )

        if not sin_cot or not sin_evt:
            incidente = {
                "escenario": esc["id"],
                "ids_nuevos": ids_nuevos,
                "eventos_antes": pre_aud.get("total_registros"),
                "eventos_despues": post_aud.get("total_registros"),
            }
            break

    final = {
        "cotizaciones": snapshot_cotizaciones(token, pet, "final_cotizaciones"),
        "auditoria": snapshot_auditoria(token, pet, "final_auditoria"),
        "activo_1569": snapshot_activo(token, pet, "final_activo_1569"),
        "periodo_220": snapshot_periodo(token, pet, "final_periodo_220"),
    }
    informe["final"] = final
    informe["incidente_persistencia"] = incidente
    informe["proteccion_datos"] = {
        "cotizaciones_inicial": baseline["cotizaciones"]["total"],
        "cotizaciones_final": final["cotizaciones"]["total"],
        "delta_cotizaciones": final["cotizaciones"]["total"] - baseline["cotizaciones"]["total"],
        "ids_inicial": baseline["cotizaciones"]["ids"],
        "ids_final": final["cotizaciones"]["ids"],
        "ids_nuevos": sorted(set(final["cotizaciones"]["ids"]) - set(baseline["cotizaciones"]["ids"])),
        "eventos_inicial": baseline["auditoria"].get("total_registros"),
        "eventos_final": final["auditoria"].get("total_registros"),
        "delta_eventos": (
            None if baseline["auditoria"].get("total_registros") is None or final["auditoria"].get("total_registros") is None
            else final["auditoria"]["total_registros"] - baseline["auditoria"]["total_registros"]
        ),
        "reservadas_9_10_intactas": baseline["cotizaciones"]["reservadas_9_10"] == final["cotizaciones"]["reservadas_9_10"],
        "periodo_220_final": final["periodo_220"],
        "activo_1569_final": final["activo_1569"],
        "49b_ejecutado": False,
    }

    estados = [e["estado"] for e in informe["escenarios"]]
    if incidente:
        categoria = "BLOQUEADO"
        motivo = f"Persistencia inesperada en {incidente['escenario']}"
    elif any(s == "BLOQUEADO" for s in estados):
        categoria = "BLOQUEADO"
        motivo = "Al menos un escenario BLOQUEADO"
    elif all(s == "APROBADO" for s in estados) and len(estados) == 3:
        categoria = "APROBADO"
        motivo = "48a/48b/49a cumplen matriz; sin persistencia"
    else:
        categoria = "RECHAZADO"
        motivo = "Uno o mas escenarios no cumplen la expectativa de la matriz (ver DISC-G117-01 si aplica)"

    informe["dictamen"] = {
        "categoria": categoria,
        "motivo": motivo,
        "conteos": {
            "aprobados": estados.count("APROBADO"),
            "rechazados": estados.count("RECHAZADO"),
            "bloqueados": estados.count("BLOQUEADO"),
            "ejecutados": len(estados),
            "autorizados": 3,
        },
        "49b_ejecutado": False,
        "escritura_positiva": False,
    }

    _guardar(informe)
    print("DICTAMEN", categoria)
    for e in informe["escenarios"]:
        print(e["escenario_id"], e["estado"], e["post"]["http"], e["post"]["code"])
    print("DELTA_COTS", informe["proteccion_datos"]["delta_cotizaciones"])
    print("DELTA_EVT", informe["proteccion_datos"]["delta_eventos"])
    print("49b", False)
    return 0 if categoria != "BLOQUEADO" else 2


def _guardar(informe: dict) -> None:
    ULTIMA.mkdir(parents=True, exist_ok=True)
    (ULTIMA / "evidencias_ejecucion_vigente_TC-M06-G117.json").write_text(
        json.dumps({"peticiones": informe.get("peticiones", [])}, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    (ULTIMA / "resumen_ejecucion_vigente_TC-M06-G117.json").write_text(
        json.dumps(informe, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8"
    )
    (ULTIMA / "analisis_hallazgos_vigente_TC-M06-G117.md").write_text(_analisis(informe), encoding="utf-8")
    (ULTIMA / "informe_cierre_TC-M06-G117.md").write_text(_cierre(informe), encoding="utf-8")
    (ULTIMA / "resultado_ejecucion_vigente_TC-M06-G117.html").write_text(_html(informe), encoding="utf-8")
    print("OK", ULTIMA)


def _analisis(inf: dict) -> str:
    lineas = [
        "# TC-M06-G117 — Analisis de hallazgos (ultima evaluacion)",
        "",
        f"- Generado: {inf.get('generado_en')}",
        f"- Dictamen: **{inf.get('dictamen', {}).get('categoria')}**",
        f"- Motivo: {inf.get('dictamen', {}).get('motivo')}",
        f"- 49b ejecutado: {inf.get('49b_ejecutado')}",
        "",
        "## Escenarios",
        "",
    ]
    for e in inf.get("escenarios", []):
        lineas += [
            f"### {e['escenario_id']} — {e['nombre']}",
            f"- Estado: **{e['estado']}**",
            f"- Esperado: HTTP {e['esperado']['http']} `{e['esperado']['code']}`",
            f"- Real: HTTP {e['post']['http']} `{e['post']['code']}`",
            f"- Motivo: {e['motivo']}",
            "",
        ]
    if inf.get("discrepancias"):
        lineas += ["## Discrepancias confirmadas", ""]
        for d in inf["discrepancias"]:
            lineas.append(f"- **{d['id']}** ({d['escenario']}): matriz `{d['matriz']}` vs real `{d['real']}`")
        lineas.append("")
    p = inf.get("proteccion_datos", {})
    lineas += [
        "## Proteccion de datos",
        "",
        f"- Delta cotizaciones: {p.get('delta_cotizaciones')} ({p.get('cotizaciones_inicial')} -> {p.get('cotizaciones_final')})",
        f"- Delta eventos COTIZACION_REGISTRADA: {p.get('delta_eventos')} ({p.get('eventos_inicial')} -> {p.get('eventos_final')})",
        f"- Reservadas 9/10 intactas: {p.get('reservadas_9_10_intactas')}",
        f"- Periodo 220: {json.dumps(p.get('periodo_220_final'), ensure_ascii=False)}",
        "",
    ]
    return "\n".join(lineas)


def _cierre(inf: dict) -> str:
    d = inf.get("dictamen", {})
    p = inf.get("proteccion_datos", {})
    lineas = [
        "# TC-M06-G117 — Informe de cierre (ejecucion autorizada)",
        "",
        f"**Dictamen: {d.get('categoria')}**",
        "",
        d.get("motivo", ""),
        "",
        f"- Conteos: {json.dumps(d.get('conteos'), ensure_ascii=False)}",
        f"- 49b ejecutado: **No**",
        f"- Escritura positiva: **No**",
        "",
        "## Resultados",
        "",
        "| Escenario | Esperado | Real | Estado |",
        "|---|---|---|---|",
    ]
    for e in inf.get("escenarios", []):
        lineas.append(
            f"| {e['escenario_id']} | {e['esperado']['http']} `{e['esperado']['code']}` | "
            f"{e['post']['http']} `{e['post']['code']}` | {e['estado']} |"
        )
    lineas += [
        "",
        "## Proteccion",
        "",
        f"- Cotizaciones: {p.get('cotizaciones_inicial')} -> {p.get('cotizaciones_final')} (delta {p.get('delta_cotizaciones')})",
        f"- Eventos COTIZACION_REGISTRADA: {p.get('eventos_inicial')} -> {p.get('eventos_final')} (delta {p.get('delta_eventos')})",
        f"- Cotizaciones 9 y 10 intactas: {p.get('reservadas_9_10_intactas')}",
        f"- Periodo 220 final: `{p.get('periodo_220_final', {}).get('estado')}`",
        "",
        "## Evidencias",
        "",
        "`tests/Test_Testing/Test_Modulo6/RF-COT/TC-M06-G117/resultados/ultima_evaluacion/`",
        "",
        "No se ejecuto commit ni push.",
        "",
    ]
    return "\n".join(lineas)


def _html(inf: dict) -> str:
    rows = "".join(
        f"<tr><td>{e['escenario_id']}</td><td>{e['esperado']['http']} {e['esperado']['code']}</td>"
        f"<td>{e['post']['http']} {e['post']['code']}</td><td>{e['estado']}</td></tr>"
        for e in inf.get("escenarios", [])
    )
    d = inf.get("dictamen", {})
    return f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8"><title>TC-M06-G117</title></head>
<body>
<h1>TC-M06-G117 — ultima evaluacion</h1>
<p><strong>Dictamen: {d.get('categoria')}</strong></p>
<p>{d.get('motivo')}</p>
<table border="1" cellpadding="4">
<tr><th>Escenario</th><th>Esperado</th><th>Real</th><th>Estado</th></tr>
{rows}
</table>
<p>49b ejecutado: No. Sin escritura positiva.</p>
</body></html>
"""


if __name__ == "__main__":
    raise SystemExit(main())
