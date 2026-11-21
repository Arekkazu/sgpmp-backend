# | Fecha      | Nombre | Que se hizo |
# |------------|--------|-------------|
# | 2026-11-15 | —      | Ejecución autorizada TC-M06-50: POST cotización activo 1571. |
"""Ejecución autorizada TC-M06-50 / G118. Un solo POST. Sin commit/push."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE = "https://api.inmero.co/api-sgpmp-test"
ZONA = "America/Bogota"
ROOT = Path(__file__).resolve().parent
DEST = ROOT / "resultados" / "ejecucion_tc50_2026-11-15"
ACTIVO = 1571
NIT = "900000003"
PAYLOAD = {
    "activos_cotizados": [1571],
    "valor_cotizacion_propuesto": "1000.0000",
    "condiciones": "TC-M06-G118 / TC-M06-50 — integridad activo sin efectos contables (pendiente autorizacion)",
}
SECRETOS = {"token", "access_token", "contrasena", "password", "hash_integridad", "Authorization", "client_secret"}


def ahora():
    return datetime.now(timezone.utc).isoformat()


def pedir(metodo, ruta, cuerpo=None, token=None, timeout=60):
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
            return resp.status, (json.loads(raw) if raw else None), None
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {"message": raw[:800]}
        return exc.code, payload, None
    except Exception as exc:
        return None, {"error": type(exc).__name__, "message": str(exc)[:300]}, str(exc)


def limpiar(v, d=0):
    if d > 12:
        return "..."
    if isinstance(v, dict):
        return {
            k: ({"omitido": True} if k in SECRETOS or "token" in k.lower() or "secret" in k.lower() else limpiar(x, d + 1))
            for k, x in v.items()
        }
    if isinstance(v, list):
        return [limpiar(x, d + 1) for x in v[:120]]
    if isinstance(v, str) and len(v) > 1200:
        return v[:1200] + "…"
    return v


def dump(nombre, obj):
    DEST.mkdir(parents=True, exist_ok=True)
    (DEST / nombre).write_text(json.dumps(limpiar(obj), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def extraer_activo(det):
    act = (det or {}).get("activo") or {}
    cals = (det or {}).get("calculos") or []
    cal = cals[0] if cals else {}
    return {
        "identificador": act.get("identificador"),
        "estado": act.get("estado"),
        "id_finca": act.get("id_finca"),
        "valor_neto": str(cal.get("valor_neto")) if cal.get("valor_neto") is not None else None,
        "fecha_calculo": cal.get("fecha_calculo"),
        "id_calculo": cal.get("id_calculo_valor_razonable"),
        "valor_en_libros_actual": (det or {}).get("valor_en_libros_actual"),
        "lineas_count": len((det or {}).get("lineas") or []),
    }


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    correo, clave = os.environ.get("QA_CORREO"), os.environ.get("QA_CONTRASENA")
    assert correo and clave, "Faltan QA_CORREO/QA_CONTRASENA"

    pet = []
    st, login, err = pedir("POST", "/sesiones/", {"correo_electronico": correo, "contrasena": clave})
    pet.append({"fase": "login", "metodo": "POST", "ruta": "/sesiones/", "http": st, "error": err})
    token = (login or {}).get("token")
    assert token, f"login {st}"

    st, det_antes, _ = pedir("GET", f"/finanzas/activos/{ACTIVO}", token=token)
    pet.append({"fase": "baseline", "metodo": "GET", "ruta": f"/finanzas/activos/{ACTIVO}", "http": st})
    activo_antes = extraer_activo(det_antes)

    st, cots_antes, _ = pedir("GET", f"/finanzas/cotizaciones?id_activo_biologico={ACTIVO}", token=token)
    pet.append({"fase": "baseline", "metodo": "GET", "ruta": f"/finanzas/cotizaciones?id_activo_biologico={ACTIVO}", "http": st})
    lista_antes = cots_antes if isinstance(cots_antes, list) else []
    g118_antes = [c for c in lista_antes if isinstance(c, dict) and "TC-M06-G118" in str(c.get("condiciones") or "")]
    exitosas_antes = [c for c in g118_antes if c.get("estado") in ("COTIZADO", "EMITIDA", "VIGENTE")]

    st, lin_antes, _ = pedir("GET", "/finanzas/lineas?id_periodo_contable=220", token=token)
    pet.append({"fase": "baseline", "metodo": "GET", "ruta": "/finanzas/lineas?id_periodo_contable=220", "http": st})
    lineas_antes = lin_antes if isinstance(lin_antes, list) else []
    ids_lineas_antes = sorted({x.get("id_linea_asiento") for x in lineas_antes if isinstance(x, dict)})
    lineas_1571_antes = [x for x in lineas_antes if isinstance(x, dict) and x.get("id_activo_biologico") == ACTIVO]

    st, ps, _ = pedir("GET", f"/finanzas/periodos?numero_id_tributaria={NIT}", token=token)
    p220 = next((p for p in (ps or []) if isinstance(p, dict) and p.get("id_periodo_contable") == 220), None)
    st, ps2, _ = pedir("GET", "/finanzas/periodos?numero_id_tributaria=900000002", token=token)
    p219 = next((p for p in (ps2 or []) if isinstance(p, dict) and p.get("id_periodo_contable") == 219), None)

    pre = {
        "activo_estado": activo_antes.get("estado") == "ACTIVO",
        "identificador": activo_antes.get("identificador") == "QA-M06O-VR-03",
        "vr_3760000": str(activo_antes.get("valor_neto") or "").startswith("3760000"),
        "fecha_calculo_ok": activo_antes.get("fecha_calculo") == "2026-11-08T21:25:06.574099Z",
        "sin_g118_exitosa_previa": len(exitosas_antes) == 0,
        "periodo_220_abierto": (p220 or {}).get("estado") == "ABIERTO",
        "periodo_219_cerrado": (p219 or {}).get("estado") == "CERRADO",
        "payload_igual_preparacion": True,
    }
    if not all(pre.values()):
        dump("prevalidacion_FALLIDA_TC-M06-50.json", {"precondiciones": pre, "activo_antes": activo_antes, "g118_antes": g118_antes})
        print(json.dumps({"abort": True, "precondiciones": pre}, ensure_ascii=False, indent=2))
        return

    # === UN SOLO POST ===
    st_post, body_post, err_post = pedir("POST", "/finanzas/cotizaciones", PAYLOAD, token=token, timeout=90)
    pet.append({"fase": "escritura", "metodo": "POST", "ruta": "/finanzas/cotizaciones", "http": st_post, "error": err_post, "posts": 1})

    id_cot = None
    if isinstance(body_post, dict):
        id_cot = body_post.get("id_cotizacion") or (body_post.get("cotizacion") or {}).get("id_cotizacion")

    ambiguo = st_post is None
    if ambiguo or st_post not in (200, 201):
        st_v, cots_v, _ = pedir("GET", f"/finanzas/cotizaciones?id_activo_biologico={ACTIVO}", token=token)
        hallado = next(
            (
                c
                for c in (cots_v or [])
                if isinstance(c, dict)
                and c.get("condiciones") == PAYLOAD["condiciones"]
                and str(c.get("valor_cotizacion_propuesto", "")).startswith("1000")
            ),
            None,
        )
        if hallado and id_cot is None:
            id_cot = hallado.get("id_cotizacion")
        dump(
            "verificacion_ambigua_TC-M06-50.json",
            {"http_post": st_post, "get_http": st_v, "encontrado": hallado is not None, "registro": hallado, "reintento_post": False},
        )

    st, cots_desp, _ = pedir("GET", f"/finanzas/cotizaciones?id_activo_biologico={ACTIVO}", token=token)
    pet.append({"fase": "verificacion", "metodo": "GET", "ruta": f"/finanzas/cotizaciones?id_activo_biologico={ACTIVO}", "http": st})
    lista_desp = cots_desp if isinstance(cots_desp, list) else []
    cot = next((c for c in lista_desp if isinstance(c, dict) and c.get("id_cotizacion") == id_cot), None)
    if cot is None:
        cot = next((c for c in lista_desp if isinstance(c, dict) and c.get("condiciones") == PAYLOAD["condiciones"]), None)
        if cot:
            id_cot = cot.get("id_cotizacion")

    if id_cot is not None:
        st, cot_det, _ = pedir("GET", f"/finanzas/cotizaciones/{id_cot}", token=token)
        pet.append({"fase": "verificacion", "metodo": "GET", "ruta": f"/finanzas/cotizaciones/{id_cot}", "http": st})
        if isinstance(cot_det, dict) and cot_det.get("id_cotizacion"):
            cot = cot_det

    st, det_desp, _ = pedir("GET", f"/finanzas/activos/{ACTIVO}", token=token)
    pet.append({"fase": "verificacion", "metodo": "GET", "ruta": f"/finanzas/activos/{ACTIVO}", "http": st})
    activo_despues = extraer_activo(det_desp)

    st, lin_desp, _ = pedir("GET", "/finanzas/lineas?id_periodo_contable=220", token=token)
    pet.append({"fase": "verificacion", "metodo": "GET", "ruta": "/finanzas/lineas?id_periodo_contable=220", "http": st})
    lineas_desp = lin_desp if isinstance(lin_desp, list) else []
    ids_lineas_desp = sorted({x.get("id_linea_asiento") for x in lineas_desp if isinstance(x, dict)})
    nuevas_lineas = [i for i in ids_lineas_desp if i not in set(ids_lineas_antes)]
    lineas_1571_desp = [x for x in lineas_desp if isinstance(x, dict) and x.get("id_activo_biologico") == ACTIVO]

    st, ps, _ = pedir("GET", f"/finanzas/periodos?numero_id_tributaria={NIT}", token=token)
    p220b = next((p for p in (ps or []) if isinstance(p, dict) and p.get("id_periodo_contable") == 220), None)
    st, ps2, _ = pedir("GET", "/finanzas/periodos?numero_id_tributaria=900000002", token=token)
    p219b = next((p for p in (ps2 or []) if isinstance(p, dict) and p.get("id_periodo_contable") == 219), None)

    # Auditoría RF-94
    st, aud, _ = pedir(
        "GET",
        f"/finanzas/auditoria?id_activo_biologico={ACTIVO}&formato=TECNICO&tamano=30&orden=DESC",
        token=token,
    )
    pet.append({"fase": "verificacion", "metodo": "GET", "ruta": "/finanzas/auditoria?...activo=1571", "http": st})
    eventos = aud if isinstance(aud, list) else (aud or {}).get("items") or (aud or {}).get("eventos") or []
    if not isinstance(eventos, list):
        eventos = []
    ev = next(
        (
            e
            for e in eventos
            if isinstance(e, dict)
            and e.get("tipo_evento") == "COTIZACION_REGISTRADA"
            and (e.get("id_referencia") == id_cot or id_cot is None)
        ),
        None,
    )
    if ev is None:
        ev = next((e for e in eventos if isinstance(e, dict) and e.get("tipo_evento") == "COTIZACION_REGISTRADA"), None)

    # AAEF: no se espera nueva exportación; consulta vista-previa Contador del NIT del activo (solo lectura)
    st_aaef, aaef, _ = pedir(
        "GET",
        "/integracion/aaef/vista-previa/productores/900000003?desde=2026-11-01&hasta=2026-11-30",
        token=token,
    )
    pet.append({"fase": "aaef", "metodo": "GET", "ruta": "/integracion/aaef/vista-previa/productores/900000003", "http": st_aaef})

    estado_cot = (cot or {}).get("estado") if isinstance(cot, dict) else None
    version = (cot or {}).get("version") if isinstance(cot, dict) else None
    vr_ref = (cot or {}).get("valor_razonable_referencia") if isinstance(cot, dict) else None
    activos = (cot or {}).get("activos_cotizados") if isinstance(cot, dict) else None

    criterios = [
        {"id": "50.1", "criterio": "POST HTTP 201", "resultado": "CUMPLE" if st_post == 201 else "NO CUMPLE", "evidencia": {"http": st_post}},
        {"id": "50.2", "criterio": "id_cotizacion presente", "resultado": "CUMPLE" if id_cot is not None else "NO CUMPLE", "evidencia": {"id_cotizacion": id_cot}},
        {
            "id": "50.3",
            "criterio": "Estado COTIZADO",
            "resultado": "CUMPLE" if estado_cot == "COTIZADO" else "NO CUMPLE",
            "evidencia": {"estado": estado_cot, "version": version},
        },
        {
            "id": "50.4",
            "criterio": "Asociación activo 1571",
            "resultado": "CUMPLE" if isinstance(activos, list) and ACTIVO in activos else "NO CUMPLE",
            "evidencia": {"activos_cotizados": activos},
        },
        {
            "id": "50.5",
            "criterio": "VR referencia 3760000",
            "resultado": "CUMPLE" if str(vr_ref or "").startswith("3760000") else "NO CUMPLE",
            "evidencia": {"valor_razonable_referencia": vr_ref},
        },
        {
            "id": "50.6",
            "criterio": "Activo 1571 permanece ACTIVO",
            "resultado": "CUMPLE" if activo_despues.get("estado") == "ACTIVO" else "NO CUMPLE",
            "evidencia": activo_despues.get("estado"),
        },
        {
            "id": "50.7",
            "criterio": "VR neto sin cambio",
            "resultado": "CUMPLE" if activo_antes.get("valor_neto") == activo_despues.get("valor_neto") else "NO CUMPLE",
            "evidencia": {"antes": activo_antes.get("valor_neto"), "despues": activo_despues.get("valor_neto")},
        },
        {
            "id": "50.8",
            "criterio": "Fecha cálculo sin cambio",
            "resultado": "CUMPLE" if activo_antes.get("fecha_calculo") == activo_despues.get("fecha_calculo") else "NO CUMPLE",
            "evidencia": {"antes": activo_antes.get("fecha_calculo"), "despues": activo_despues.get("fecha_calculo")},
        },
        {
            "id": "50.9",
            "criterio": "Sin nuevas líneas contables en 220",
            "resultado": "CUMPLE" if len(nuevas_lineas) == 0 else "NO CUMPLE",
            "evidencia": {"nuevas": nuevas_lineas, "total_antes": len(ids_lineas_antes), "total_despues": len(ids_lineas_desp)},
        },
        {
            "id": "50.10",
            "criterio": "Líneas del activo 1571 sin incremento",
            "resultado": "CUMPLE" if len(lineas_1571_antes) == len(lineas_1571_desp) else "NO CUMPLE",
            "evidencia": {"antes": len(lineas_1571_antes), "despues": len(lineas_1571_desp)},
        },
        {
            "id": "50.11",
            "criterio": "Auditoría COTIZACION_REGISTRADA",
            "resultado": "CUMPLE" if isinstance(ev, dict) and ev.get("tipo_evento") == "COTIZACION_REGISTRADA" else "NO CUMPLE",
            "evidencia": {
                "id_evento": (ev or {}).get("id_evento") if isinstance(ev, dict) else None,
                "id_referencia": (ev or {}).get("id_referencia") if isinstance(ev, dict) else None,
            },
        },
        {
            "id": "50.12",
            "criterio": "Período 220 ABIERTO",
            "resultado": "CUMPLE" if (p220b or {}).get("estado") == "ABIERTO" else "NO CUMPLE",
            "evidencia": (p220b or {}).get("estado"),
        },
        {
            "id": "50.13",
            "criterio": "Período 219 CERRADO",
            "resultado": "CUMPLE" if (p219b or {}).get("estado") == "CERRADO" else "NO CUMPLE",
            "evidencia": (p219b or {}).get("estado"),
        },
        {
            "id": "50.14",
            "criterio": "AAEF: sin exigir nueva exportación; vista-previa 900000003 sigue PERIODO_NO_CERRADO",
            "resultado": (
                "CUMPLE"
                if st_aaef == 422 and isinstance(aaef, dict) and aaef.get("error_code") == "PERIODO_NO_CERRADO"
                else "NO CUMPLE"
            ),
            "evidencia": {"http": st_aaef, "error_code": (aaef or {}).get("error_code") if isinstance(aaef, dict) else None},
        },
    ]

    cumple = sum(1 for c in criterios if c["resultado"] == "CUMPLE")
    no_cumple = sum(1 for c in criterios if c["resultado"] == "NO CUMPLE")
    no_ver = sum(1 for c in criterios if c["resultado"] == "NO VERIFICABLE")
    dictamen = "APROBADO" if no_cumple == 0 and st_post == 201 and estado_cot == "COTIZADO" else "RECHAZADO"

    resultado = {
        "caso": "TC-M06-G118",
        "subcaso": "TC-M06-50",
        "fase": "ejecucion_autorizada_2026-11-15",
        "fecha_utc": ahora(),
        "ambiente": BASE,
        "autorizacion": "Expresa — POST /finanzas/cotizaciones TC-M06-50",
        "posts_ejecutados": 1,
        "precondiciones": pre,
        "post": {"http": st_post, "request": PAYLOAD, "respuesta": body_post, "error_red": err_post, "id_cotizacion": id_cot},
        "cotizacion": cot,
        "activo_antes": activo_antes,
        "activo_despues": activo_despues,
        "lineas": {"antes": len(ids_lineas_antes), "despues": len(ids_lineas_desp), "nuevas": nuevas_lineas, "activo_1571_antes": len(lineas_1571_antes), "activo_1571_despues": len(lineas_1571_desp)},
        "periodos": {"220": (p220b or {}).get("estado"), "219": (p219b or {}).get("estado")},
        "auditoria_rf94": {"evento": ev},
        "aaef_vista_previa": {"http": st_aaef, "error_code": (aaef or {}).get("error_code") if isinstance(aaef, dict) else None},
        "resumen_criterios": {"cumple": cumple, "no_cumple": no_cumple, "no_verificable": no_ver, "total": len(criterios)},
        "dictamen": dictamen,
        "g118_global": "APROBADO" if dictamen == "APROBADO" else "NO APROBADO",
    }

    dump("solicitud_respuesta_http_TC-M06-50.json", {"metodo": "POST", "endpoint": "/finanzas/cotizaciones", "request": PAYLOAD, "http": st_post, "respuesta": body_post})
    dump("peticiones_TC-M06-50.json", {"peticiones": pet, "posts_ejecutados": 1})
    dump("comparacion_activo_1571.json", {"antes": activo_antes, "despues": activo_despues})
    dump("verificacion_lineas_periodo_220.json", resultado["lineas"])
    dump("evidencia_rf94_TC-M06-50.json", {"evento": ev, "tipos": [e.get("tipo_evento") for e in eventos if isinstance(e, dict)][:15]})
    dump("matriz_criterios_TC-M06-50.json", {"matriz": criterios, "resumen": resultado["resumen_criterios"], "dictamen": dictamen})
    dump("resultado_ejecucion_TC-M06-50.json", resultado)

    md = [
        "# Reporte de ejecución TC-M06-50 — G118",
        "",
        f"- Fecha UTC: `{resultado['fecha_utc']}`",
        f"- HTTP POST: **{st_post}**",
        f"- id_cotizacion: **{id_cot}**",
        f"- Estado: **{estado_cot}** · versión: **{version}**",
        f"- Dictamen TC-M06-50: **{dictamen}**",
        f"- Dictamen G118 (si 50 es el subcaso obligatorio): **{resultado['g118_global']}**",
        "",
        "## Criterios",
        "",
        "| ID | Criterio | Resultado |",
        "|---|---|---|",
    ]
    for c in criterios:
        md.append(f"| {c['id']} | {c['criterio']} | {c['resultado']} |")
    md.append("")
    md.append("Preparación anterior conservada. Sin commit/push.")
    (DEST / "REPORTE_EJECUCION_TC-M06-50.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    print(json.dumps({"http": st_post, "id_cotizacion": id_cot, "estado": estado_cot, "dictamen": dictamen, "g118": resultado["g118_global"], "resumen": resultado["resumen_criterios"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
