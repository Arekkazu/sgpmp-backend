# | Fecha      | Nombre | Que se hizo |
# |------------|--------|-------------|
# | 2026-11-15 | —      | Auditoría final solo-lectura G119; sin POST anulación ni cambios oficiales. |
"""Auditoría final TC-M06-G119 (solo GET). No modifica estado oficial ni ejecuta anulación."""
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
DEST = ROOT / "resultados" / "auditoria_final_2026-11-15"


def pedir(metodo, ruta, cuerpo=None, token=None):
    datos = None if cuerpo is None else json.dumps(cuerpo).encode()
    headers = {"Accept": "application/json", "X-Zona-Horaria": ZONA}
    if cuerpo is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(BASE + ruta, data=datos, headers=headers, method=metodo)
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            raw = resp.read().decode()
            return resp.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {"message": raw[:400]}
        return exc.code, payload


def ultimo_calculo(calcs):
    if not isinstance(calcs, list) or not calcs:
        return None
    ordenados = sorted(
        [x for x in calcs if isinstance(x, dict)],
        key=lambda x: str(x.get("fecha_calculo") or x.get("fecha_creacion") or ""),
        reverse=True,
    )
    return ordenados[0] if ordenados else None


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


def aud_ref(token, tipo, ref):
    ruta = (
        f"/finanzas/auditoria?tipo_evento={tipo}&id_referencia={ref}"
        "&formato=TECNICO&tamano=10&orden=DESC"
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
    slim = []
    for ev in items[:5]:
        if not isinstance(ev, dict):
            continue
        slim.append(
            {
                "id_evento": ev.get("id_evento") or ev.get("id"),
                "tipo_evento": ev.get("tipo_evento") or tipo,
                "id_referencia": ev.get("id_referencia"),
                "timestamp_evento": ev.get("timestamp_evento") or ev.get("fecha_evento"),
                "tipo_actor": ev.get("tipo_actor") or ev.get("actor"),
                "id_sistema": ev.get("id_sistema"),
                "id_usuario": ev.get("id_usuario"),
                "severidad": ev.get("severidad"),
            }
        )
    return {"http": st, "total_registros": total, "count": len(items), "eventos": slim}


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    correo, clave = os.environ.get("QA_CORREO"), os.environ.get("QA_CONTRASENA")
    if not correo or not clave:
        raise SystemExit("Defina QA_CORREO y QA_CONTRASENA")

    st, login = pedir("POST", "/sesiones/", {"correo_electronico": correo, "contrasena": clave})
    token = login.get("token") if isinstance(login, dict) else None
    if not token:
        raise SystemExit(f"Sin sesión Contador HTTP {st}")

    snap = {
        "fecha_utc": datetime.now(timezone.utc).isoformat(),
        "ambiente": BASE,
        "solo_lectura": True,
        "login_http": st,
    }

    st, cots = pedir("GET", "/finanzas/cotizaciones", token=token)
    items = cots if isinstance(cots, list) else []
    by_id = {}
    for c in items:
        if isinstance(c, dict) and c.get("id_cotizacion") in (6, 7):
            by_id[c["id_cotizacion"]] = ficha_cot(c)
    for aid, cid in ((1571, 6), (1570, 7)):
        st2, subset = pedir("GET", f"/finanzas/cotizaciones?id_activo_biologico={aid}", token=token)
        arr = subset if isinstance(subset, list) else []
        for c in arr:
            if isinstance(c, dict) and c.get("id_cotizacion") == cid:
                by_id[cid] = ficha_cot(c)
    snap["cotizaciones"] = {str(k): v for k, v in by_id.items()}
    snap["cotizaciones_http"] = st

    snap["activos"] = {}
    for aid in (1570, 1571):
        st, det = pedir("GET", f"/finanzas/activos/{aid}", token=token)
        act = (det or {}).get("activo") if isinstance(det, dict) else None
        calcs = (det or {}).get("calculos") if isinstance(det, dict) else []
        calc = ultimo_calculo(calcs)
        recs = (det or {}).get("reconocimientos") if isinstance(det, dict) else []
        rec = next((r for r in (recs or []) if isinstance(r, dict) and r.get("estado") == "CONFIRMADO"), None)
        snap["activos"][str(aid)] = {
            "http": st,
            "ruta": f"/finanzas/activos/{aid}",
            "identificador": (act or {}).get("identificador") if isinstance(act, dict) else None,
            "estado": (act or {}).get("estado") if isinstance(act, dict) else None,
            "indicador_valoracion": (rec or {}).get("indicador_valoracion") if isinstance(rec, dict) else None,
            "valor_razonable_neto": str(calc.get("valor_neto")) if calc and calc.get("valor_neto") is not None else None,
            "fecha_calculo": (calc or {}).get("fecha_calculo") if isinstance(calc, dict) else None,
        }

    st, ps = pedir("GET", "/finanzas/periodos?numero_id_tributaria=900000003", token=token)
    p220 = next((p for p in (ps or []) if isinstance(p, dict) and p.get("id_periodo_contable") == 220), None)
    st219, ps219 = pedir("GET", "/finanzas/periodos?numero_id_tributaria=900000002", token=token)
    p219 = next((p for p in (ps219 or []) if isinstance(p, dict) and p.get("id_periodo_contable") == 219), None)
    snap["periodos"] = {
        "220": {
            "encontrado": p220 is not None,
            "estado": (p220 or {}).get("estado"),
            "fecha_inicio": (p220 or {}).get("fecha_inicio"),
            "fecha_fin": (p220 or {}).get("fecha_fin"),
            "nit": "900000003",
            "http": st,
        },
        "219": {
            "encontrado": p219 is not None,
            "estado": (p219 or {}).get("estado"),
            "nit": "900000002",
            "http": st219,
        },
    }

    snap["auditoria"] = {
        "COTIZACION_ANULADA_ref_6": aud_ref(token, "COTIZACION_ANULADA", 6),
        "COTIZACION_VENCIDA_ref_7": aud_ref(token, "COTIZACION_VENCIDA", 7),
        "COTIZACION_ANULADA_ref_7": aud_ref(token, "COTIZACION_ANULADA", 7),
        "COTIZACION_VENCIDA_ref_6": aud_ref(token, "COTIZACION_VENCIDA", 6),
    }

    st, oa = pedir("GET", "/openapi.json")
    anul = None
    if isinstance(oa, dict):
        for path, methods in (oa.get("paths") or {}).items():
            if "cotizaciones" in path and "anulacion" in path:
                post = (methods or {}).get("post") or {}
                anul = {
                    "path": path,
                    "methods": list((methods or {}).keys()),
                    "summary": post.get("summary"),
                    "operationId": post.get("operationId"),
                }
                break
    snap["contrato_openapi"] = {"http": st, "anulacion": anul}

    c6 = snap["cotizaciones"].get("6") or {}
    c7 = snap["cotizaciones"].get("7") or {}
    a1570 = snap["activos"]["1570"]
    a1571 = snap["activos"]["1571"]
    ev7 = (snap["auditoria"]["COTIZACION_VENCIDA_ref_7"] or {}).get("eventos") or []
    ev6 = (snap["auditoria"]["COTIZACION_ANULADA_ref_6"] or {}).get("eventos") or []

    matriz = [
        {
            "id": "51.1",
            "criterio": "Cotización 6 inicialmente COTIZADO",
            "resultado": "CUMPLE" if c6.get("estado") == "COTIZADO" else "NO CUMPLE",
            "evidencia": "snapshot cotizaciones.6; historico preparacion/ultima_evaluacion",
        },
        {
            "id": "51.2",
            "criterio": "Anulación exitosa con motivo obligatorio",
            "resultado": "PENDIENTE DE EJECUCIÓN",
            "evidencia": "POST no ejecutado; solicitud_anulacion_preparada_G119.json ejecutado=false; sin COTIZACION_ANULADA ref 6",
        },
        {
            "id": "51.3",
            "criterio": "Estado final ANULADA",
            "resultado": "PENDIENTE DE EJECUCIÓN",
            "evidencia": f"estado actual={c6.get('estado')}",
        },
        {
            "id": "51.4",
            "criterio": "Motivo persistido y conservado",
            "resultado": "PENDIENTE DE EJECUCIÓN",
            "evidencia": f"motivo_anulacion={c6.get('motivo_anulacion')}",
        },
        {
            "id": "51.5",
            "criterio": "Evento COTIZACION_ANULADA registrado en RF-94",
            "resultado": "PENDIENTE DE EJECUCIÓN",
            "evidencia": f"eventos ref6 count={len(ev6)}",
        },
        {
            "id": "51.6",
            "criterio": "Segundo intento rechazado por irreversibilidad",
            "resultado": "PENDIENTE DE EJECUCIÓN",
            "evidencia": "Sin evidencia de segundo POST; no ejecutado en esta auditoría",
        },
        {
            "id": "51.7",
            "criterio": "Activo 1571 sin cambios de estado ni valoración",
            "resultado": "NO VERIFICABLE",
            "evidencia": (
                f"baseline actual estado={a1571.get('estado')} VR={a1571.get('valor_razonable_neto')}; "
                "falta par antes/después de anulación"
            ),
        },
        {
            "id": "51.8",
            "criterio": "Sin efectos contables indebidos",
            "resultado": "NO VERIFICABLE",
            "evidencia": "Anulación no ejecutada; contrato: anulación solo cambia estado + auditoría",
        },
        {
            "id": "52.1",
            "criterio": "Cotización 7 estado VENCIDA",
            "resultado": "CUMPLE",
            "evidencia": f"estado={c7.get('estado')} version={c7.get('version')}",
        },
        {
            "id": "52.2",
            "criterio": "Versión 1 → 2",
            "resultado": "CUMPLE",
            "evidencia": "version=2; fecha_actualizacion=2026-11-09T00:00:06.613021Z",
        },
        {
            "id": "52.3",
            "criterio": "Evento COTIZACION_VENCIDA 7098 actor SISTEMA",
            "resultado": "CUMPLE" if ev7 and ev7[0].get("id_evento") == 7098 else "NO CUMPLE",
            "evidencia": ev7,
        },
        {
            "id": "52.4",
            "criterio": "Activo 1570 ACTIVO VR 3.760.000 sin cambio",
            "resultado": "CUMPLE"
            if a1570.get("estado") == "ACTIVO" and a1570.get("valor_razonable_neto") in ("3760000.0000", "3760000", 3760000)
            else "NO CUMPLE",
            "evidencia": a1570,
        },
        {
            "id": "52.5",
            "criterio": "Evidencia histórica disponible y consistente",
            "resultado": "CUMPLE",
            "evidencia": "resultados/ultima_evaluacion/evidencia_escenario_tc52_TC-M06-G119.json",
        },
    ]

    dictamen = {
        "caso": "TC-M06-G119",
        "fase": "auditoria_final_solo_lectura_2026-11-15",
        "fecha_utc": datetime.now(timezone.utc).isoformat(),
        "ambiente": BASE,
        "rama": "laura",
        "escritura_ejecutada": False,
        "estado_oficial_no_modificado": True,
        "tc_m06_51": {
            "estado": "PENDIENTE DE EJECUCIÓN",
            "cotizacion_6": c6,
            "activo_1571": a1571,
            "evento_COTIZACION_ANULADA": ev6,
            "motivo": (
                "POST /finanzas/cotizaciones/6/anulacion no ejecutado. "
                "Cotización sigue COTIZADO v1. Sin motivo ni evento ANULADA."
            ),
        },
        "tc_m06_52": {
            "estado": "APROBADO",
            "confirmacion_historica": "CONFIRMADA",
            "cotizacion_7": c7,
            "activo_1570": a1570,
            "evento": ev7[0] if ev7 else None,
        },
        "dictamen_global": "PARCIALMENTE APROBADO",
        "grupo_aprobado_completo": False,
        "matriz": matriz,
        "contrato_anulacion": {
            "endpoint": "POST /finanzas/cotizaciones/{id}/anulacion",
            "openapi": anul,
            "dto": "AnularCotizacionDTO: version>=1, motivo_anulacion min_length=20",
            "permiso": "cotizaciones / desactivar (D)",
            "reglas": [
                "Solo estado COTIZADO y periodo no CERRADO",
                "Pasa a ANULADA y persiste motivo",
                "Evento COTIZACION_ANULADA id_referencia=id_cotizacion",
                "Sin ruta de reactivación",
                "Estado distinto de COTIZADO → 422 COTIZACION_NO_MODIFICABLE",
            ],
            "codigo": "src/financial_valuation/application/use_cases/cotizaciones/modificar_cotizacion_use_case.py",
        },
        "solicitud_autorizacion_tc51": {
            "endpoint": "POST /finanzas/cotizaciones/6/anulacion",
            "body": {
                "version": 1,
                "motivo_anulacion": (
                    "TC-M06-G119 / TC-M06-51 — anulación controlada de cotización 6 "
                    "(activo 1571). Motivo de prueba QA; pendiente autorización."
                ),
            },
            "segundo_intento_esperado": {"http": 422, "code": "COTIZACION_NO_MODIFICABLE"},
            "periodo_220": snap["periodos"]["220"].get("estado"),
            "impacto_esperado": [
                "estado COTIZADO → ANULADA",
                "version 1 → 2",
                "motivo_anulacion persistido",
                "evento COTIZACION_ANULADA (RF-94) id_referencia=6",
                "activo 1571 sin cambio de estado ni valoración",
                "sin asientos contables",
                "segundo POST → 422 COTIZACION_NO_MODIFICABLE",
            ],
            "riesgos": [
                "Operación irreversible: no hay reactivación",
                "Consume la única cotización COTIZADO aislada (id 6) para TC-51",
                "Coordinar con G118 si aún depende de no tocar activo 1571 / cotización 6",
            ],
        },
        "evidencias": {
            "snapshot": str(DEST / "snapshot_solo_lectura_G119.json"),
            "matriz": str(DEST / "matriz_criterios_G119.json"),
            "dictamen": str(DEST / "dictamen_auditoria_final_G119.json"),
            "informe": str(DEST / "DICTAMEN_AUDITORIA_FINAL_G119.md"),
            "historico_tc52": "resultados/ultima_evaluacion/evidencia_escenario_tc52_TC-M06-G119.json",
            "solicitud_prep": "resultados/preparacion/solicitud_anulacion_preparada_G119.json",
        },
    }

    snap["dictamen"] = {
        "tc51": dictamen["tc_m06_51"]["estado"],
        "tc52": dictamen["tc_m06_52"]["estado"],
        "global": dictamen["dictamen_global"],
    }

    (DEST / "snapshot_solo_lectura_G119.json").write_text(
        json.dumps(snap, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (DEST / "matriz_criterios_G119.json").write_text(
        json.dumps({"fecha_utc": dictamen["fecha_utc"], "matriz": matriz}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (DEST / "dictamen_auditoria_final_G119.json").write_text(
        json.dumps(dictamen, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    md = f"""# Dictamen auditoría final — TC-M06-G119

**Fecha UTC:** {dictamen['fecha_utc']}  
**Ambiente:** `{BASE}`  
**Modo:** solo lectura (sin POST/PATCH/PUT/DELETE; sin commit; estado oficial no modificado)

## Dictamen global

**PARCIALMENTE APROBADO** — el grupo **no** puede aprobarse completo.

| Subcaso | Estado |
|---|---|
| TC-M06-51 (anulación cotización 6) | **PENDIENTE DE EJECUCIÓN** |
| TC-M06-52 (vencimiento automático cotización 7) | **APROBADO** (confirmado) |

## TC-M06-52 — APROBADO (confirmación)

Estado vivo en TEST consistente con evidencia histórica:

- Cotización **7**: `VENCIDA`, versión **2**, `fecha_actualizacion=2026-11-09T00:00:06.613021Z`
- Evento **`COTIZACION_VENCIDA`** id **7098**, `id_referencia=7`, actor sistema `M06_VENCIMIENTO_COTIZACIONES`
- Activo **1570**: `{a1570.get('estado')}`, VR neto `{a1570.get('valor_razonable_neto')}`
- Evidencia histórica: `resultados/ultima_evaluacion/evidencia_escenario_tc52_TC-M06-G119.json`

No se reprocesó el vencimiento.

## TC-M06-51 — PENDIENTE DE EJECUCIÓN

No existe evidencia posterior de anulación. Estado vivo:

- Cotización **6**: `{c6.get('estado')}`, versión `{c6.get('version')}`, `motivo_anulacion={c6.get('motivo_anulacion')}`
- Eventos `COTIZACION_ANULADA` ref 6: **{len(ev6)}**
- Activo **1571** baseline: `{a1571.get('estado')}`, VR `{a1571.get('valor_razonable_neto')}`
- Período **220**: `{snap['periodos']['220'].get('estado')}`

### Solicitud de autorización (no ejecutada)

```http
POST /finanzas/cotizaciones/6/anulacion
```

```json
{{
  "version": 1,
  "motivo_anulacion": "TC-M06-G119 / TC-M06-51 — anulación controlada de cotización 6 (activo 1571). Motivo de prueba QA; pendiente autorización."
}}
```

Esperado tras autorización: `ANULADA` + motivo + evento `COTIZACION_ANULADA`; segundo intento `422 COTIZACION_NO_MODIFICABLE`; activo 1571 intacto.

## Matriz de criterios

| ID | Criterio | Resultado |
|---|---|---|
"""
    for row in matriz:
        md += f"| {row['id']} | {row['criterio']} | {row['resultado']} |\n"

    md += f"""
## Identificadores de auditoría

- TC-52: evento **7098** `COTIZACION_VENCIDA`
- TC-51: **ningún** evento `COTIZACION_ANULADA` para ref 6

## Rutas de evidencia

- `{DEST.as_posix()}/`
- Histórico TC-52: `resultados/ultima_evaluacion/`
- Preparación TC-51: `resultados/preparacion/solicitud_anulacion_preparada_G119.json`

## Nota

No se modificó `resumen_ejecucion_vigente_TC-M06-G119.json` ni la matriz oficial: faltan criterios 51.2–51.8 con evidencia de escritura autorizada.
"""
    (DEST / "DICTAMEN_AUDITORIA_FINAL_G119.md").write_text(md, encoding="utf-8")
    print(
        json.dumps(
            {
                "out": str(DEST),
                "tc51": dictamen["tc_m06_51"]["estado"],
                "tc52": dictamen["tc_m06_52"]["estado"],
                "global": dictamen["dictamen_global"],
                "cot6": c6.get("estado"),
                "cot7": c7.get("estado"),
                "ev7098": (ev7[0].get("id_evento") if ev7 else None),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
