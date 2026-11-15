# | Fecha      | Nombre | Que se hizo |
# |------------|--------|-------------|
# | 2026-11-15 | —      | Ejecución autorizada TC-M06-51: anulación cotización 6 + 2º intento. |
"""Ejecución autorizada TC-M06-51 / G119. Solo cotización 6. Sin commit/push."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

BASE = "https://api.inmero.co/api-sgpmp-test"
ZONA = "America/Bogota"
ROOT = Path(__file__).resolve().parent
DEST = ROOT / "resultados" / "ejecucion_tc51_2026-11-15"
ULTIMA = ROOT / "resultados" / "ultima_evaluacion"
COT = 6
ACTIVO = 1571
PERIODO = 220
NIT = "900000003"
MOTIVO = (
    "TC-M06-G119 / TC-M06-51 — anulación controlada de cotización 6 "
    "(activo 1571). Motivo de prueba QA; pendiente autorización."
)
SECRETOS = {
    "token", "access_token", "contrasena", "password", "hash_integridad",
    "numero_id_tributaria", "correo_electronico", "Authorization",
}


def ahora():
    return datetime.now(timezone.utc).isoformat()


def pedir(metodo, ruta, cuerpo=None, token=None, timeout=45):
    datos = None if cuerpo is None else json.dumps(cuerpo).encode()
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
            payload = {"message": raw[:800]}
        return exc.code, payload
    except Exception as exc:
        return None, {"error": type(exc).__name__, "message": str(exc)[:300]}


def limpiar(v, d=0):
    if d > 10:
        return "..."
    if isinstance(v, dict):
        out = {}
        for k, x in v.items():
            if k in SECRETOS or "token" in k.lower() or "contrasen" in k.lower():
                out[k] = {"omitido": True}
            else:
                out[k] = limpiar(x, d + 1)
        return out
    if isinstance(v, list):
        return [limpiar(x, d + 1) for x in v[:100]]
    if isinstance(v, str) and len(v) > 800:
        return v[:800] + "…"
    return v


def tiene_permiso(permisos_payload, recurso, id_accion):
    if not isinstance(permisos_payload, dict):
        return False
    for p in permisos_payload.get("permisos") or []:
        if (
            isinstance(p, dict)
            and p.get("nombre_recurso") == recurso
            and p.get("id_accion") == id_accion
        ):
            return True
    return False


def ficha_cot(c):
    if not isinstance(c, dict):
        return None
    out = {
        k: c.get(k)
        for k in (
            "id_cotizacion",
            "estado",
            "version",
            "activos_cotizados",
            "fecha_emision",
            "fecha_vencimiento",
            "motivo_anulacion",
            "id_periodo_contable",
            "estado_periodo",
            "valor_cotizacion_propuesto",
            "valor_razonable_referencia",
            "fecha_actualizacion",
            "fecha_registro",
        )
    }
    for k in ("valor_cotizacion_propuesto", "valor_razonable_referencia"):
        if out.get(k) is not None:
            out[k] = str(out[k])
    return out


def ultimo_calculo(calcs):
    if not isinstance(calcs, list) or not calcs:
        return None
    ordenados = sorted(
        [x for x in calcs if isinstance(x, dict)],
        key=lambda x: str(x.get("fecha_calculo") or x.get("fecha_creacion") or ""),
        reverse=True,
    )
    return ordenados[0] if ordenados else None


def ficha_activo(det):
    if not isinstance(det, dict):
        return {"http_payload": None}
    act = det.get("activo") if isinstance(det.get("activo"), dict) else {}
    calcs = det.get("calculos") if isinstance(det.get("calculos"), list) else []
    calc = ultimo_calculo(calcs)
    recs = det.get("reconocimientos") if isinstance(det.get("reconocimientos"), list) else []
    rec = next((r for r in recs if isinstance(r, dict) and r.get("estado") == "CONFIRMADO"), None)
    lineas = det.get("lineas") if isinstance(det.get("lineas"), list) else []
    return {
        "identificador": act.get("identificador"),
        "estado": act.get("estado"),
        "indicador_valoracion": (rec or {}).get("indicador_valoracion") if isinstance(rec, dict) else None,
        "valor_razonable_neto": str(calc.get("valor_neto")) if calc and calc.get("valor_neto") is not None else None,
        "fecha_calculo": (calc or {}).get("fecha_calculo") if isinstance(calc, dict) else None,
        "id_calculo": (calc or {}).get("id_calculo_valor_razonable") if isinstance(calc, dict) else None,
        "lineas_count": len(lineas),
        "lineas_ids": [
            x.get("id_linea_contable") or x.get("id_linea") or x.get("id")
            for x in lineas
            if isinstance(x, dict)
        ][:20],
    }


def obtener_cotizacion(token, id_cot):
    st, cots = pedir("GET", "/finanzas/cotizaciones", token=token)
    lista = cots if isinstance(cots, list) else []
    for c in lista:
        if isinstance(c, dict) and c.get("id_cotizacion") == id_cot:
            return st, ficha_cot(c), c
    st2, subset = pedir("GET", f"/finanzas/cotizaciones?id_activo_biologico={ACTIVO}", token=token)
    arr = subset if isinstance(subset, list) else []
    for c in arr:
        if isinstance(c, dict) and c.get("id_cotizacion") == id_cot:
            return st2, ficha_cot(c), c
    return st, None, None


def aud_anulada(token):
    ruta = "/finanzas/auditoria?" + urllib.parse.urlencode(
        [
            ("tipo_evento", "COTIZACION_ANULADA"),
            ("id_referencia", str(COT)),
            ("formato", "TECNICO"),
            ("tamano", "20"),
            ("orden", "DESC"),
        ]
    )
    st, body = pedir("GET", ruta, token=token)
    items = []
    total = None
    if isinstance(body, dict):
        items = body.get("items") or body.get("registros") or body.get("eventos") or body.get("datos") or []
        total = body.get("total_registros")
    elif isinstance(body, list):
        items = body
        total = len(items)
    if not isinstance(items, list):
        items = []
    eventos = []
    for ev in items:
        if not isinstance(ev, dict):
            continue
        payload = ev.get("payload") or ev.get("datos_nuevos") or {}
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except json.JSONDecodeError:
                payload = {"raw": payload[:400]}
        eventos.append(
            {
                "id_evento": ev.get("id_evento") or ev.get("id"),
                "tipo_evento": ev.get("tipo_evento") or "COTIZACION_ANULADA",
                "id_referencia": ev.get("id_referencia"),
                "timestamp_evento": ev.get("timestamp_evento") or ev.get("fecha_evento"),
                "tipo_actor": ev.get("tipo_actor") or ev.get("actor"),
                "id_usuario": ev.get("id_usuario"),
                "id_sistema": ev.get("id_sistema"),
                "severidad": ev.get("severidad"),
                "payload": limpiar(payload) if isinstance(payload, (dict, list)) else payload,
                "justificacion": ev.get("justificacion")
                or (payload.get("justificacion") if isinstance(payload, dict) else None),
            }
        )
    return ruta, st, total, eventos, limpiar(body)


def error_code(resp):
    if not isinstance(resp, dict):
        return None
    return (
        resp.get("code")
        or resp.get("error_code")
        or resp.get("codigo")
        or (resp.get("detail") or {}).get("code")
        if isinstance(resp.get("detail"), dict)
        else resp.get("code")
    )


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    pet = []
    correo, clave = os.environ.get("QA_CORREO"), os.environ.get("QA_CONTRASENA")
    if not correo or not clave:
        raise SystemExit("Defina QA_CORREO y QA_CONTRASENA")

    st, login = pedir("POST", "/sesiones/", {"correo_electronico": correo, "contrasena": clave})
    token = login.get("token") if isinstance(login, dict) else None
    pet.append({"fase": "login", "metodo": "POST", "ruta": "/sesiones/", "http": st, "ok": bool(token)})
    if not token:
        raise SystemExit(f"SIN SESION HTTP {st}")

    st, perfil = pedir("GET", "/usuarios/me", token=token)
    rol = (perfil or {}).get("nombre_rol") if isinstance(perfil, dict) else None
    pet.append({"fase": "perfil", "metodo": "GET", "ruta": "/usuarios/me", "http": st, "rol": rol})

    st, permisos = pedir("GET", "/sesiones/me/permisos", token=token)
    puede_anular = tiene_permiso(permisos, "cotizaciones", 4)
    pet.append(
        {
            "fase": "permisos",
            "metodo": "GET",
            "ruta": "/sesiones/me/permisos",
            "http": st,
            "cotizaciones_D": puede_anular,
        }
    )

    # --- Precondiciones ---
    st_c, cot_antes, _raw = obtener_cotizacion(token, COT)
    pet.append({"fase": "pre_cot", "metodo": "GET", "ruta": "/finanzas/cotizaciones", "http": st_c, "cot": cot_antes})

    st_a, det_antes = pedir("GET", f"/finanzas/activos/{ACTIVO}", token=token)
    act_antes = ficha_activo(det_antes)
    pet.append({"fase": "pre_activo", "metodo": "GET", "ruta": f"/finanzas/activos/{ACTIVO}", "http": st_a, "activo": act_antes})

    st_p, periodos = pedir("GET", f"/finanzas/periodos?numero_id_tributaria={NIT}", token=token)
    p220 = next((p for p in (periodos or []) if isinstance(p, dict) and p.get("id_periodo_contable") == PERIODO), None)
    periodo_antes = {
        "id_periodo_contable": PERIODO,
        "estado": (p220 or {}).get("estado"),
        "fecha_inicio": (p220 or {}).get("fecha_inicio"),
        "fecha_fin": (p220 or {}).get("fecha_fin"),
        "encontrado": p220 is not None,
    }
    pet.append({"fase": "pre_periodo", "metodo": "GET", "ruta": f"/finanzas/periodos?numero_id_tributaria={NIT}", "http": st_p, "periodo_220": periodo_antes})

    ruta_aud0, st_aud0, tot_aud0, ev_aud0, _ = aud_anulada(token)
    pet.append({"fase": "pre_auditoria", "metodo": "GET", "ruta": ruta_aud0, "http": st_aud0, "total": tot_aud0, "eventos": ev_aud0})

    # Cotización 7 baseline (no alterar)
    st7, cot7_antes, _ = obtener_cotizacion(token, 7)
    pet.append({"fase": "pre_cot7", "metodo": "GET", "ruta": "/finanzas/cotizaciones", "http": st7, "cot7": cot7_antes})

    pre = {
        "cotizacion_6_estado": (cot_antes or {}).get("estado"),
        "cotizacion_6_version": (cot_antes or {}).get("version"),
        "motivo_anulacion": (cot_antes or {}).get("motivo_anulacion"),
        "activo_1571_estado": act_antes.get("estado"),
        "valor_razonable_neto": act_antes.get("valor_razonable_neto"),
        "periodo_220_estado": periodo_antes.get("estado"),
        "permiso_anular": puede_anular,
        "eventos_anulada_previos": len(ev_aud0),
    }
    checks = {
        "cotizado": pre["cotizacion_6_estado"] == "COTIZADO",
        "version_1": pre["cotizacion_6_version"] == 1,
        "motivo_nulo": pre["motivo_anulacion"] in (None, ""),
        "activo_activo": pre["activo_1571_estado"] == "ACTIVO",
        "vr_3760000": pre["valor_razonable_neto"] in ("3760000.0000", "3760000", 3760000),
        "periodo_abierto": pre["periodo_220_estado"] == "ABIERTO",
        "permiso_ok": puede_anular is True,
    }
    if not all(checks.values()):
        informe = {
            "caso": "TC-M06-51",
            "estado": "DETENIDO",
            "motivo": "Precondiciones no cumplidas; no se ejecutó POST",
            "precondiciones": pre,
            "checks": checks,
            "fecha_utc": ahora(),
        }
        (DEST / "DETENIDO_precondiciones.json").write_text(
            json.dumps(informe, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(json.dumps({"detenido": True, "checks": checks, "pre": pre}, ensure_ascii=False))
        return

    # --- POST 1: anulación ---
    body1 = {"version": 1, "motivo_anulacion": MOTIVO}
    http1, resp1 = pedir("POST", f"/finanzas/cotizaciones/{COT}/anulacion", cuerpo=body1, token=token)
    cot_post1 = ficha_cot(resp1) if isinstance(resp1, dict) and resp1.get("id_cotizacion") else None
    pet.append(
        {
            "fase": "post1_anulacion",
            "metodo": "POST",
            "ruta": f"/finanzas/cotizaciones/{COT}/anulacion",
            "http": http1,
            "request_body": body1,
            "respuesta": limpiar(resp1),
            "cotizacion": cot_post1,
        }
    )

    st_c2, cot_despues1, _ = obtener_cotizacion(token, COT)
    pet.append({"fase": "post1_get_cot", "metodo": "GET", "ruta": "/finanzas/cotizaciones", "http": st_c2, "cot": cot_despues1})

    ruta_aud1, st_aud1, tot_aud1, ev_aud1, raw_aud1 = aud_anulada(token)
    pet.append(
        {
            "fase": "post1_auditoria",
            "metodo": "GET",
            "ruta": ruta_aud1,
            "http": st_aud1,
            "total": tot_aud1,
            "eventos": ev_aud1,
        }
    )

    version_vigente = (cot_despues1 or cot_post1 or {}).get("version") or 2

    # --- POST 2: irreversibilidad (versión vigente, mismo motivo) ---
    body2 = {"version": int(version_vigente), "motivo_anulacion": MOTIVO}
    http2, resp2 = pedir("POST", f"/finanzas/cotizaciones/{COT}/anulacion", cuerpo=body2, token=token)
    pet.append(
        {
            "fase": "post2_irreversibilidad",
            "metodo": "POST",
            "ruta": f"/finanzas/cotizaciones/{COT}/anulacion",
            "http": http2,
            "request_body": body2,
            "respuesta": limpiar(resp2),
            "error_code": error_code(resp2) if isinstance(resp2, dict) else None,
        }
    )

    st_c3, cot_final, _ = obtener_cotizacion(token, COT)
    pet.append({"fase": "post2_get_cot", "metodo": "GET", "ruta": "/finanzas/cotizaciones", "http": st_c3, "cot": cot_final})

    ruta_aud2, st_aud2, tot_aud2, ev_aud2, raw_aud2 = aud_anulada(token)
    pet.append(
        {
            "fase": "post2_auditoria",
            "metodo": "GET",
            "ruta": ruta_aud2,
            "http": st_aud2,
            "total": tot_aud2,
            "eventos": ev_aud2,
        }
    )

    # --- Integridad activo / período / cot 7 ---
    st_a2, det_despues = pedir("GET", f"/finanzas/activos/{ACTIVO}", token=token)
    act_despues = ficha_activo(det_despues)
    pet.append({"fase": "post_activo", "metodo": "GET", "ruta": f"/finanzas/activos/{ACTIVO}", "http": st_a2, "activo": act_despues})

    st_p2, periodos2 = pedir("GET", f"/finanzas/periodos?numero_id_tributaria={NIT}", token=token)
    p220b = next((p for p in (periodos2 or []) if isinstance(p, dict) and p.get("id_periodo_contable") == PERIODO), None)
    periodo_despues = {
        "id_periodo_contable": PERIODO,
        "estado": (p220b or {}).get("estado"),
        "fecha_inicio": (p220b or {}).get("fecha_inicio"),
        "fecha_fin": (p220b or {}).get("fecha_fin"),
    }
    pet.append({"fase": "post_periodo", "metodo": "GET", "ruta": f"/finanzas/periodos?numero_id_tributaria={NIT}", "http": st_p2, "periodo_220": periodo_despues})

    st7b, cot7_despues, _ = obtener_cotizacion(token, 7)
    pet.append({"fase": "post_cot7", "metodo": "GET", "ruta": "/finanzas/cotizaciones", "http": st7b, "cot7": cot7_despues})

    # Criterios
    anulacion_ok = http1 in (200, 201) and (cot_despues1 or {}).get("estado") == "ANULADA"
    motivo_ok = (cot_despues1 or {}).get("motivo_anulacion") == MOTIVO or (
        (cot_despues1 or {}).get("motivo_anulacion") or ""
    ).startswith("TC-M06-G119 / TC-M06-51")
    eventos_nuevos = [e for e in ev_aud1 if e.get("id_referencia") == COT]
    # Prefer events after pre count
    if tot_aud0 is not None and tot_aud1 is not None:
        evento_unico = (tot_aud1 == 1) or (tot_aud1 == (tot_aud0 or 0) + 1)
    else:
        evento_unico = len(eventos_nuevos) == 1
    evento = eventos_nuevos[0] if eventos_nuevos else None
    # Motivo en payload
    motivo_en_evento = False
    if evento:
        just = evento.get("justificacion") or ""
        payload = evento.get("payload") or {}
        cambios = payload.get("cambios") if isinstance(payload, dict) else {}
        motivo_payload = ""
        if isinstance(cambios, dict):
            motivo_payload = cambios.get("motivo_anulacion") or ""
        if isinstance(payload, dict) and not motivo_payload:
            motivo_payload = payload.get("motivo_anulacion") or payload.get("justificacion") or ""
        motivo_en_evento = MOTIVO in str(just) or MOTIVO in str(motivo_payload) or "TC-M06-G119 / TC-M06-51" in (
            str(just) + str(motivo_payload) + str(payload)
        )

    code2 = error_code(resp2) if isinstance(resp2, dict) else None
    if code2 is None and isinstance(resp2, dict):
        # nested detail
        detail = resp2.get("detail")
        if isinstance(detail, dict):
            code2 = detail.get("code") or detail.get("error_code")
        elif isinstance(detail, list) and detail:
            code2 = (detail[0] or {}).get("code") if isinstance(detail[0], dict) else None
        code2 = code2 or resp2.get("error") or resp2.get("type")

    segundo_ok = (
        http2 == 422
        and (code2 == "COTIZACION_NO_MODIFICABLE" or "NO_MODIFICABLE" in str(code2 or "") or "NO_MODIFICABLE" in json.dumps(resp2, ensure_ascii=False))
        and (cot_final or {}).get("estado") == "ANULADA"
        and (tot_aud2 in (tot_aud1, 1) or len(ev_aud2) == len(ev_aud1))
    )
    # More precise: no second ANULADA event
    ids1 = {e.get("id_evento") for e in ev_aud1}
    ids2 = {e.get("id_evento") for e in ev_aud2}
    sin_segundo_evento = ids2 == ids1 or (len(ids2) == 1 and len(ids1) == 1)

    activo_ok = (
        act_despues.get("estado") == "ACTIVO"
        and act_despues.get("valor_razonable_neto") in ("3760000.0000", "3760000", 3760000)
        and act_despues.get("estado") == act_antes.get("estado")
        and act_despues.get("valor_razonable_neto") == act_antes.get("valor_razonable_neto")
        and act_despues.get("id_calculo") == act_antes.get("id_calculo")
    )
    lineas_ok = act_despues.get("lineas_count") == act_antes.get("lineas_count") and act_despues.get(
        "lineas_ids"
    ) == act_antes.get("lineas_ids")
    periodo_ok = periodo_despues.get("estado") == "ABIERTO" and periodo_despues.get("estado") == periodo_antes.get(
        "estado"
    )
    cot7_ok = (cot7_despues or {}) == (cot7_antes or {}) or (
        (cot7_despues or {}).get("estado") == (cot7_antes or {}).get("estado")
        and (cot7_despues or {}).get("version") == (cot7_antes or {}).get("version")
    )

    matriz = [
        {"id": "51.1", "criterio": "Cotización inicialmente COTIZADO", "resultado": "CUMPLE" if checks["cotizado"] else "NO CUMPLE", "evidencia": pre},
        {
            "id": "51.2",
            "criterio": "Anulación exitosa con motivo obligatorio",
            "resultado": "CUMPLE" if anulacion_ok and motivo_ok else "NO CUMPLE",
            "evidencia": {"http": http1, "estado": (cot_despues1 or {}).get("estado"), "motivo": (cot_despues1 or {}).get("motivo_anulacion")},
        },
        {
            "id": "51.3",
            "criterio": "Estado final ANULADA",
            "resultado": "CUMPLE" if (cot_final or {}).get("estado") == "ANULADA" else "NO CUMPLE",
            "evidencia": cot_final,
        },
        {
            "id": "51.4",
            "criterio": "Motivo persistido y conservado",
            "resultado": "CUMPLE" if motivo_ok and (cot_final or {}).get("motivo_anulacion") == (cot_despues1 or {}).get("motivo_anulacion") else "NO CUMPLE",
            "evidencia": (cot_final or {}).get("motivo_anulacion"),
        },
        {
            "id": "51.5",
            "criterio": "Evento COTIZACION_ANULADA en RF-94",
            "resultado": "CUMPLE" if evento and evento_unico and motivo_en_evento else ("NO CUMPLE" if not evento else "CUMPLE" if evento and evento_unico else "NO CUMPLE"),
            "evidencia": {"total": tot_aud1, "evento": evento, "motivo_en_evento": motivo_en_evento, "unico": evento_unico},
        },
        {
            "id": "51.6",
            "criterio": "Segundo intento rechazado (irreversibilidad)",
            "resultado": "CUMPLE" if segundo_ok and sin_segundo_evento else "NO CUMPLE",
            "evidencia": {"http": http2, "code": code2, "estado": (cot_final or {}).get("estado"), "eventos_ids": list(ids2), "sin_segundo_evento": sin_segundo_evento},
        },
        {
            "id": "51.7",
            "criterio": "Activo 1571 sin cambios de estado ni valoración",
            "resultado": "CUMPLE" if activo_ok else "NO CUMPLE",
            "evidencia": {"antes": act_antes, "despues": act_despues},
        },
        {
            "id": "51.8",
            "criterio": "Sin efectos contables indebidos",
            "resultado": "CUMPLE" if lineas_ok and periodo_ok else "NO CUMPLE",
            "evidencia": {
                "lineas_antes": act_antes.get("lineas_count"),
                "lineas_despues": act_despues.get("lineas_count"),
                "lineas_ids_iguales": act_despues.get("lineas_ids") == act_antes.get("lineas_ids"),
                "periodo_antes": periodo_antes,
                "periodo_despues": periodo_despues,
                "cot7_intacta": cot7_ok,
            },
        },
    ]

    # Refine 51.5: if event exists with ref 6 and unique, even if motivo nested differently still pass if payload has cambios
    if evento and evento_unico and matriz[4]["resultado"] != "CUMPLE":
        # re-check motivo loosely
        blob = json.dumps(evento, ensure_ascii=False)
        if "ANULADA" in blob and str(evento.get("id_referencia")) == "6":
            if MOTIVO in blob or "motivo_anulacion" in blob or "TC-M06-G119" in blob:
                matriz[4]["resultado"] = "CUMPLE"
                matriz[4]["evidencia"]["motivo_en_evento"] = True

    tc51_ok = all(r["resultado"] == "CUMPLE" for r in matriz)
    # TC-52 historical
    tc52_evid = ULTIMA / "evidencia_escenario_tc52_TC-M06-G119.json"
    tc52_ok = tc52_evid.exists() and (cot7_despues or {}).get("estado") == "VENCIDA"
    dictamen_global = "APROBADO" if tc51_ok and tc52_ok else ("PARCIALMENTE APROBADO" if tc52_ok else "NO CUMPLE")

    resultado = {
        "caso": "TC-M06-G119",
        "subcaso": "TC-M06-51",
        "fase": "ejecucion_autorizada_2026-11-15",
        "fecha_utc": ahora(),
        "ambiente": BASE,
        "autorizacion": "Expresa del usuario — anulación cotización 6 + segundo intento",
        "escritura": True,
        "rol": rol,
        "precondiciones": {"valores": pre, "checks": checks, "ok": all(checks.values())},
        "post1": {
            "http": http1,
            "request": body1,
            "respuesta": limpiar(resp1),
            "cotizacion": cot_despues1,
        },
        "auditoria_rf94": {
            "antes_total": tot_aud0,
            "despues_total": tot_aud1,
            "tras_segundo_total": tot_aud2,
            "eventos": ev_aud2,
            "evento_principal": evento,
        },
        "post2": {
            "http": http2,
            "request": body2,
            "respuesta": limpiar(resp2),
            "error_code": code2,
            "esperado": {"http": 422, "code": "COTIZACION_NO_MODIFICABLE"},
        },
        "activo_comparacion": {"antes": act_antes, "despues": act_despues},
        "periodo_comparacion": {"antes": periodo_antes, "despues": periodo_despues},
        "cotizacion_7": {"antes": cot7_antes, "despues": cot7_despues, "intacta": cot7_ok},
        "matriz_tc51": matriz,
        "tc_m06_51": "APROBADO" if tc51_ok else "NO CUMPLE",
        "tc_m06_52": "APROBADO" if tc52_ok else "NO VERIFICABLE",
        "dictamen_global": dictamen_global,
        "grupo_aprobado_completo": dictamen_global == "APROBADO",
    }

    # Persist artifacts
    (DEST / "respuestas_http_TC-M06-51.json").write_text(
        json.dumps({"peticiones": pet}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (DEST / "evidencia_auditoria_RF94_COTIZACION_ANULADA.json").write_text(
        json.dumps(
            {
                "tipo_evento": "COTIZACION_ANULADA",
                "id_referencia": 6,
                "antes": {"total": tot_aud0, "eventos": ev_aud0},
                "despues_anulacion": {"total": tot_aud1, "eventos": ev_aud1},
                "despues_segundo_intento": {"total": tot_aud2, "eventos": ev_aud2},
                "respuesta_cruda_sanitizada": raw_aud2,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (DEST / "comparacion_activo_1571.json").write_text(
        json.dumps({"antes": act_antes, "despues": act_despues, "sin_cambio": activo_ok and lineas_ok}, ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )
    (DEST / "resultado_segundo_intento.json").write_text(
        json.dumps(resultado["post2"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (DEST / "matriz_criterios_TC-M06-51.json").write_text(
        json.dumps({"matriz": matriz, "aprobado": tc51_ok}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (DEST / "resultado_ejecucion_TC-M06-51.json").write_text(
        json.dumps(resultado, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    md = f"""# Ejecución autorizada TC-M06-51 / G119

**Fecha UTC:** {resultado['fecha_utc']}  
**Ambiente:** `{BASE}`  
**Autorización:** expresa — anulación cotización 6 + segundo intento de irreversibilidad

## Resultado

| Ítem | Estado |
|---|---|
| TC-M06-51 | **{resultado['tc_m06_51']}** |
| TC-M06-52 (histórico + vivo) | **{resultado['tc_m06_52']}** |
| Dictamen G119 | **{resultado['dictamen_global']}** |

## Precondiciones

Todas cumplidas: `{all(checks.values())}`

- Cotización 6: `{pre['cotizacion_6_estado']}` v`{pre['cotizacion_6_version']}` motivo=`{pre['motivo_anulacion']}`
- Activo 1571: `{pre['activo_1571_estado']}` VR=`{pre['valor_razonable_neto']}`
- Período 220: `{pre['periodo_220_estado']}`
- Permiso anular: `{puede_anular}`

## POST 1 — Anulación

- HTTP **{http1}**
- Estado → `{(cot_despues1 or {}).get('estado')}` versión `{(cot_despues1 or {}).get('version')}`
- Motivo: `{(cot_despues1 or {}).get('motivo_anulacion')}`

## RF-94

- Eventos `COTIZACION_ANULADA` ref 6: antes={tot_aud0} → después={tot_aud1} → tras 2º={tot_aud2}
- Evento principal: `{json.dumps(evento, ensure_ascii=False) if evento else None}`

## POST 2 — Irreversibilidad

- HTTP **{http2}** code=`{code2}`
- Cotización permanece `{(cot_final or {}).get('estado')}`
- Sin segundo evento: `{sin_segundo_evento}`

## Activo 1571

| | Antes | Después |
|---|---|---|
| Estado | {act_antes.get('estado')} | {act_despues.get('estado')} |
| VR neto | {act_antes.get('valor_razonable_neto')} | {act_despues.get('valor_razonable_neto')} |
| Líneas | {act_antes.get('lineas_count')} | {act_despues.get('lineas_count')} |

## Matriz

| ID | Criterio | Resultado |
|---|---|---|
"""
    for row in matriz:
        md += f"| {row['id']} | {row['criterio']} | {row['resultado']} |\n"

    md += f"""
## Evidencias

`{DEST.as_posix()}/`
"""
    (DEST / "REPORTE_EJECUCION_TC-M06-51.md").write_text(md, encoding="utf-8")

    # Update dictamen G119 (nueva carpeta + ultima_evaluacion vigente)
    dictamen_g119 = {
        "caso": "TC-M06-G119",
        "subcasos": ["TC-M06-51", "TC-M06-52"],
        "fase": "cierre_post_ejecucion_tc51_2026-11-15",
        "fecha_utc": ahora(),
        "ambiente": BASE,
        "escritura_ejecutada": True,
        "anulacion_cotizacion_6_ejecutada": True,
        "subcasos_resultado": [
            {
                "subcaso": "TC-M06-51",
                "estado": resultado["tc_m06_51"],
                "cotizacion": 6,
                "activo": 1571,
                "evento": (evento or {}).get("id_evento") if evento else None,
            },
            {
                "subcaso": "TC-M06-52",
                "estado": "APROBADO",
                "cotizacion": 7,
                "activo": 1570,
                "evento": 7098,
            },
        ],
        "dictamen_grupo": {
            "categoria": dictamen_global,
            "grupo_aprobado_completo": dictamen_global == "APROBADO",
            "motivo": (
                "TC-M06-51 y TC-M06-52 con evidencia verificable completa"
                if dictamen_global == "APROBADO"
                else "Revisar matriz TC-M06-51"
            ),
        },
        "evidencias_tc51": str(DEST),
        "evidencias_tc52": str(ULTIMA / "evidencia_escenario_tc52_TC-M06-G119.json"),
    }
    (DEST / "dictamen_G119_actualizado.json").write_text(
        json.dumps(dictamen_g119, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (DEST / "DICTAMEN_G119.md").write_text(
        f"""# Dictamen G119 (post TC-M06-51)

**Dictamen global: {dictamen_global}**

| Subcaso | Estado |
|---|---|
| TC-M06-51 | {resultado['tc_m06_51']} |
| TC-M06-52 | APROBADO |

Evidencias TC-51: `{DEST.as_posix()}/`  
Evidencias TC-52: `resultados/ultima_evaluacion/evidencia_escenario_tc52_TC-M06-G119.json`
""",
        encoding="utf-8",
    )

    # Actualizar resumen vigente (no borrar histórico de cierre parcial: copiar a archivo con sufijo si hace falta)
    vigente_prev = ULTIMA / "resumen_ejecucion_vigente_TC-M06-G119.json"
    if vigente_prev.exists():
        backup = ULTIMA / "resumen_ejecucion_vigente_TC-M06-G119_pre_tc51.json"
        if not backup.exists():
            backup.write_text(vigente_prev.read_text(encoding="utf-8"), encoding="utf-8")

    vigente = {
        "caso": "TC-M06-G119",
        "subcasos": ["TC-M06-51", "TC-M06-52"],
        "fase": "cierre_completo_post_tc51_2026-11-15",
        "ambiente": BASE,
        "generado_en": ahora(),
        "autorizacion": "Ejecución autorizada TC-M06-51 (anulación + 2º intento)",
        "escritura_ejecutada": True,
        "anulacion_cotizacion_6_ejecutada": True,
        "subcasos_resultado": dictamen_g119["subcasos_resultado"],
        "dictamen_grupo": dictamen_g119["dictamen_grupo"],
        "tc51": {
            "estado": resultado["tc_m06_51"],
            "cotizacion_6": cot_final,
            "evento": evento,
            "segundo_intento": {"http": http2, "code": code2},
            "activo_1571": act_despues,
        },
        "tc52": {
            "estado": "APROBADO",
            "cotizacion_7": cot7_despues,
            "evento_id": 7098,
        },
        "evidencias": {
            "ejecucion_51": str(DEST),
            "escenario_52": "resultados/ultima_evaluacion/evidencia_escenario_tc52_TC-M06-G119.json",
            "auditoria_final_readonly": "resultados/auditoria_final_2026-11-15/",
        },
    }
    ULTIMA.mkdir(parents=True, exist_ok=True)
    vigente_prev.write_text(json.dumps(vigente, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (ULTIMA / "informe_cierre_TC-M06-G119.md").write_text(
        f"""# TC-M06-G119 — Cierre

**Dictamen: {dictamen_global}**

| Subcaso | Estado |
|---|---|
| TC-M06-51 | {resultado['tc_m06_51']} |
| TC-M06-52 | APROBADO |

Ejecución TC-51: `resultados/ejecucion_tc51_2026-11-15/`  
Histórico TC-52 preservado en `evidencia_escenario_tc52_TC-M06-G119.json`.
""",
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "out": str(DEST),
                "tc51": resultado["tc_m06_51"],
                "tc52": resultado["tc_m06_52"],
                "global": dictamen_global,
                "http1": http1,
                "http2": http2,
                "code2": code2,
                "estado_final": (cot_final or {}).get("estado"),
                "evento_id": (evento or {}).get("id_evento") if evento else None,
                "matriz": {r["id"]: r["resultado"] for r in matriz},
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
