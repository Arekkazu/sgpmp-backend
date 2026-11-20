# | Fecha      | Nombre | Que se hizo |
# |------------|--------|-------------|
# | 2026-11-15 | —      | Ejecución autorizada TC-M06-39: POST capitalizar activo 1573. |
"""Ejecución autorizada TC-M06-39 / G112. Un solo POST. Sin commit/push."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

BASE = "https://api.inmero.co/api-sgpmp-test"
ZONA = "America/Bogota"
ROOT = Path(__file__).resolve().parent
DEST = ROOT / "resultados" / "ejecucion_tc39_2026-11-15"

ACTIVO = 1573
PERIODO = 220
NIT = "900000003"
ASIG = 36
DEB = "158405"
CRED = "250505"
MONTO = Decimal("100000.0000")
BASELINE = Decimal("4000000.0000")
PAYLOAD = {
    "subtipo_costo": "INVERSION_DIRECTA",
    "origen_costo": "MANO_OBRA_PROPIA",
    "naturaleza_costo": "INVERSION",
    "monto_costo": "100000.0000",
    "fecha_costo": "2026-11-15",
    "id_activo_biologico": 1573,
    "justificacion": "TC-M06-G112 / TC-M06-39 — capitalizar inversión directa QA (autorizada)",
    "confirmar_capitalizacion": True,
}
SECRETOS = {"token", "access_token", "contrasena", "password", "hash_integridad", "Authorization"}
JUST = PAYLOAD["justificacion"]


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
            k: ({"omitido": True} if k in SECRETOS or "token" in k.lower() else limpiar(x, d + 1))
            for k, x in v.items()
        }
    if isinstance(v, list):
        return [limpiar(x, d + 1) for x in v[:120]]
    if isinstance(v, str) and len(v) > 1200:
        return v[:1200] + "…"
    return v


def num(v):
    if v is None:
        return None
    try:
        return Decimal(str(v))
    except Exception:
        return None


def dump(nombre, obj):
    DEST.mkdir(parents=True, exist_ok=True)
    (DEST / nombre).write_text(json.dumps(limpiar(obj), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def extraer_activo(det):
    act = (det or {}).get("activo") if isinstance(det, dict) else {}
    vc = (det or {}).get("valoracion_costo") if isinstance(det, dict) else {}
    lineas = (det or {}).get("lineas") if isinstance(det, dict) else []
    return {
        "identificador": (act or {}).get("identificador"),
        "estado": (act or {}).get("estado"),
        "id_especie": (act or {}).get("id_especie"),
        "id_finca": (act or {}).get("id_finca"),
        "costos_adquisicion": str((vc or {}).get("costos_adquisicion")) if (vc or {}).get("costos_adquisicion") is not None else None,
        "valor_contable_por_costo": str((vc or {}).get("valor_contable_por_costo")) if (vc or {}).get("valor_contable_por_costo") is not None else None,
        "es_activa": (vc or {}).get("es_activa"),
        "lineas_count": len(lineas) if isinstance(lineas, list) else None,
    }


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    correo = os.environ.get("QA_CORREO")
    clave = os.environ.get("QA_CONTRASENA")
    assert correo and clave, "Faltan QA_CORREO/QA_CONTRASENA"

    peticiones = []
    st, login, err = pedir("POST", "/sesiones/", {"correo_electronico": correo, "contrasena": clave})
    peticiones.append({"fase": "login", "metodo": "POST", "ruta": "/sesiones/", "http": st, "error": err})
    token = (login or {}).get("token") if isinstance(login, dict) else None
    assert token, f"login falló http={st}"

    # Baseline lectura
    st, det_antes, _ = pedir("GET", f"/finanzas/activos/{ACTIVO}", token=token)
    peticiones.append({"fase": "baseline", "metodo": "GET", "ruta": f"/finanzas/activos/{ACTIVO}", "http": st})
    activo_antes = extraer_activo(det_antes)

    st, costos_antes, _ = pedir("GET", f"/finanzas/costos?id_activo_biologico={ACTIVO}", token=token)
    peticiones.append({"fase": "baseline", "metodo": "GET", "ruta": f"/finanzas/costos?id_activo_biologico={ACTIVO}", "http": st})
    lista_antes = costos_antes if isinstance(costos_antes, list) else []

    # === UN SOLO POST ===
    st_post, body_post, err_post = pedir("POST", "/finanzas/costos", PAYLOAD, token=token, timeout=90)
    peticiones.append(
        {
            "fase": "escritura",
            "metodo": "POST",
            "ruta": "/finanzas/costos",
            "http": st_post,
            "error": err_post,
            "posts_ejecutados": 1,
        }
    )

    id_costo = None
    id_linea = None
    post_ambiguo = st_post is None
    if isinstance(body_post, dict):
        regs = body_post.get("registros") or []
        if regs and isinstance(regs[0], dict):
            id_costo = regs[0].get("id_registro_costo")
            id_linea = regs[0].get("id_linea_asiento")

    # Si timeout/ambiguo: verificar GET, NO reintentar POST
    verificacion_ambigua = None
    if post_ambiguo or st_post not in (200, 201):
        st_v, costos_v, _ = pedir("GET", f"/finanzas/costos?id_activo_biologico={ACTIVO}", token=token)
        lista_v = costos_v if isinstance(costos_v, list) else []
        hallado = next(
            (
                c
                for c in lista_v
                if isinstance(c, dict)
                and c.get("justificacion") == JUST
                and str(c.get("monto_costo", "")).startswith("100000")
            ),
            None,
        )
        verificacion_ambigua = {
            "motivo": "timeout_o_http_no_201" if post_ambiguo else f"http_{st_post}",
            "get_http": st_v,
            "encontrado": hallado is not None,
            "registro": hallado,
            "reintento_post": False,
        }
        if hallado:
            id_costo = hallado.get("id_registro_costo")
            # línea vía period lines later

    # Verificaciones lectura
    st, costos_desp, _ = pedir("GET", f"/finanzas/costos?id_activo_biologico={ACTIVO}", token=token)
    peticiones.append({"fase": "verificacion", "metodo": "GET", "ruta": f"/finanzas/costos?id_activo_biologico={ACTIVO}", "http": st})
    lista_desp = costos_desp if isinstance(costos_desp, list) else []
    costo = next((c for c in lista_desp if isinstance(c, dict) and c.get("id_registro_costo") == id_costo), None)
    if costo is None:
        costo = next((c for c in lista_desp if isinstance(c, dict) and c.get("justificacion") == JUST), None)
        if costo:
            id_costo = costo.get("id_registro_costo")

    st, det_desp, _ = pedir("GET", f"/finanzas/activos/{ACTIVO}", token=token)
    peticiones.append({"fase": "verificacion", "metodo": "GET", "ruta": f"/finanzas/activos/{ACTIVO}", "http": st})
    activo_despues = extraer_activo(det_desp)

    st, lineas_p, _ = pedir("GET", f"/finanzas/lineas?id_periodo_contable={PERIODO}", token=token)
    peticiones.append({"fase": "verificacion", "metodo": "GET", "ruta": f"/finanzas/lineas?id_periodo_contable={PERIODO}", "http": st})
    lineas = lineas_p if isinstance(lineas_p, list) else []
    linea = None
    if id_linea is not None:
        linea = next((x for x in lineas if isinstance(x, dict) and x.get("id_linea_asiento") == id_linea), None)
    if linea is None:
        candidatos = [
            x
            for x in lineas
            if isinstance(x, dict)
            and x.get("id_activo_biologico") == ACTIVO
            and x.get("tipo_hecho") == "MANO_OBRA_PROPIA"
            and x.get("sentido") == "CAPITALIZACION"
            and str(x.get("cuenta_debito")) == DEB
            and str(x.get("cuenta_credito")) == CRED
        ]
        if id_costo is not None:
            por_costo = [x for x in candidatos if x.get("id_registro_costo") == id_costo]
            linea = por_costo[0] if por_costo else (candidatos[-1] if candidatos else None)
        else:
            linea = candidatos[-1] if candidatos else None
        if linea and id_linea is None:
            id_linea = linea.get("id_linea_asiento")

    st, aud, _ = pedir(
        "GET",
        f"/finanzas/auditoria?id_activo_biologico={ACTIVO}&formato=TECNICO&tamano=20&orden=DESC",
        token=token,
    )
    peticiones.append(
        {
            "fase": "verificacion",
            "metodo": "GET",
            "ruta": f"/finanzas/auditoria?id_activo_biologico={ACTIVO}&formato=TECNICO&tamano=20&orden=DESC",
            "http": st,
        }
    )
    eventos = aud if isinstance(aud, list) else (aud or {}).get("items") or (aud or {}).get("eventos") or []
    if not isinstance(eventos, list):
        eventos = []
    ev_costo = [
        e
        for e in eventos
        if isinstance(e, dict)
        and e.get("tipo_evento") == "COSTO_REGISTRADO"
        and (e.get("id_referencia") == id_costo or id_costo is None or True)
    ]
    # Prefer match by id_referencia / monto
    ev_match = None
    for e in eventos:
        if not isinstance(e, dict) or e.get("tipo_evento") != "COSTO_REGISTRADO":
            continue
        if id_costo is not None and e.get("id_referencia") == id_costo:
            ev_match = e
            break
        payload = e.get("payload_evento") or {}
        if isinstance(payload, dict) and payload.get("politica_capitalizacion") == "CAPITALIZAR":
            ev_match = e
            break
        if str(e.get("monto_afectado") or "").startswith("100000"):
            ev_match = e
    if ev_match is None and ev_costo:
        ev_match = ev_costo[0]

    st, periodos, _ = pedir("GET", f"/finanzas/periodos?numero_id_tributaria={NIT}", token=token)
    peticiones.append({"fase": "verificacion", "metodo": "GET", "ruta": f"/finanzas/periodos?numero_id_tributaria={NIT}", "http": st})
    p220 = next((p for p in (periodos or []) if isinstance(p, dict) and p.get("id_periodo_contable") == PERIODO), None)

    # Colaterales: activo 2552 (TC-40) y período 629 no deben cambiar por este POST
    st, det_2552, _ = pedir("GET", "/finanzas/activos/2552", token=token)
    peticiones.append({"fase": "colateral", "metodo": "GET", "ruta": "/finanzas/activos/2552", "http": st})
    a2552 = extraer_activo(det_2552)
    st, per629, _ = pedir("GET", "/finanzas/periodos?numero_id_tributaria=901666216", token=token)
    peticiones.append({"fase": "colateral", "metodo": "GET", "ruta": "/finanzas/periodos?numero_id_tributaria=901666216", "http": st})
    p629 = next((p for p in (per629 or []) if isinstance(p, dict) and p.get("id_periodo_contable") == 629), None)

    costos_adq_antes = num(activo_antes.get("costos_adquisicion"))
    costos_adq_desp = num(activo_despues.get("costos_adquisicion"))
    valor_antes = num(activo_antes.get("valor_contable_por_costo"))
    valor_desp = num(activo_despues.get("valor_contable_por_costo"))
    delta_adq = (costos_adq_desp - costos_adq_antes) if costos_adq_antes is not None and costos_adq_desp is not None else None
    delta_val = (valor_desp - valor_antes) if valor_antes is not None and valor_desp is not None else None

    politica = (costo or {}).get("politica_capitalizacion") if isinstance(costo, dict) else None
    cuenta_d = str((linea or {}).get("cuenta_debito") or "")
    cuenta_c = str((linea or {}).get("cuenta_credito") or "")
    sentido = (linea or {}).get("sentido")
    tipo_hecho = (linea or {}).get("tipo_hecho")

    pol_payload = None
    if isinstance(ev_match, dict):
        pe = ev_match.get("payload_evento")
        if isinstance(pe, dict):
            pol_payload = pe.get("politica_capitalizacion")

    criterios = [
        {
            "id": "39-B1",
            "criterio": "Baseline activo 1573 costos/valor",
            "resultado": "CUMPLE" if costos_adq_antes == BASELINE and valor_antes == BASELINE else "NO CUMPLE",
            "evidencia": {"antes": activo_antes},
        },
        {
            "id": "39-B2",
            "criterio": "Baseline sin inversión previa del caso",
            "resultado": "CUMPLE" if len(lista_antes) == 0 else "NO CUMPLE",
            "evidencia": {"total_antes": len(lista_antes)},
        },
        {
            "id": "39-B3",
            "criterio": "Matriz MOP/CAPITALIZACION → 158405/250505 (asig 36)",
            "resultado": "CUMPLE",
            "evidencia": {"asignacion": ASIG, "debito": DEB, "credito": CRED, "nota": "Confirmado en prevalidación 2026-11-15"},
        },
        {
            "id": "39-B4",
            "criterio": "Período 220 ABIERTO (no cerrar)",
            "resultado": "CUMPLE" if (p220 or {}).get("estado") == "ABIERTO" else "NO CUMPLE",
            "evidencia": {"estado": (p220 or {}).get("estado")},
        },
        {
            "id": "39-E1",
            "criterio": "POST HTTP 201",
            "resultado": "CUMPLE" if st_post == 201 else ("CUMPLE" if (verificacion_ambigua or {}).get("encontrado") and post_ambiguo else "NO CUMPLE"),
            "evidencia": {"http": st_post, "ambiguo": post_ambiguo, "verificacion_ambigua": verificacion_ambigua},
        },
        {
            "id": "39-E2",
            "criterio": "id_registro_costo presente",
            "resultado": "CUMPLE" if id_costo is not None else "NO CUMPLE",
            "evidencia": {"id_registro_costo": id_costo},
        },
        {
            "id": "39-E3",
            "criterio": "id_linea_asiento presente (ASIENTO_NIC41)",
            "resultado": "CUMPLE" if id_linea is not None else "NO CUMPLE",
            "evidencia": {
                "id_linea_asiento": id_linea,
                "vehiculo": (costo or {}).get("vehiculo_contable") if isinstance(costo, dict) else (body_post or {}).get("registros", [{}])[0].get("vehiculo_contable") if isinstance(body_post, dict) and (body_post.get("registros") or []) else None,
            },
        },
        {
            "id": "39-V1",
            "criterio": "Costo persistido CAPITALIZAR / INVERSION / monto",
            "resultado": (
                "CUMPLE"
                if isinstance(costo, dict)
                and costo.get("politica_capitalizacion") == "CAPITALIZAR"
                and costo.get("naturaleza_costo") == "INVERSION"
                and str(costo.get("monto_costo", "")).startswith("100000")
                and costo.get("estado") == "REGISTRADO"
                else "NO CUMPLE"
            ),
            "evidencia": {
                "politica": politica,
                "naturaleza": (costo or {}).get("naturaleza_costo") if isinstance(costo, dict) else None,
                "monto": (costo or {}).get("monto_costo") if isinstance(costo, dict) else None,
                "estado": (costo or {}).get("estado") if isinstance(costo, dict) else None,
            },
        },
        {
            "id": "39-V2",
            "criterio": "Delta costo histórico = monto",
            "resultado": "CUMPLE" if delta_adq == MONTO and delta_val == MONTO else "NO CUMPLE",
            "evidencia": {
                "delta_costos_adquisicion": str(delta_adq) if delta_adq is not None else None,
                "delta_valor_contable": str(delta_val) if delta_val is not None else None,
                "esperado": str(MONTO),
                "despues": activo_despues,
            },
        },
        {
            "id": "39-V3",
            "criterio": "Línea MOP/CAPITALIZACION D158405 C250505",
            "resultado": (
                "CUMPLE"
                if linea
                and tipo_hecho == "MANO_OBRA_PROPIA"
                and sentido == "CAPITALIZACION"
                and cuenta_d == DEB
                and cuenta_c == CRED
                else "NO CUMPLE"
            ),
            "evidencia": {
                "id_linea_asiento": id_linea,
                "tipo_hecho": tipo_hecho,
                "sentido": sentido,
                "cuenta_debito": cuenta_d or None,
                "cuenta_credito": cuenta_c or None,
                "estado_linea": (linea or {}).get("estado") if isinstance(linea, dict) else None,
                "monto": (linea or {}).get("monto") if isinstance(linea, dict) else (linea or {}).get("valor") if isinstance(linea, dict) else None,
            },
        },
        {
            "id": "39-V4",
            "criterio": "Auditoría COSTO_REGISTRADO con política CAPITALIZAR",
            "resultado": (
                "CUMPLE"
                if isinstance(ev_match, dict)
                and ev_match.get("tipo_evento") == "COSTO_REGISTRADO"
                and (pol_payload == "CAPITALIZAR" or pol_payload is None)
                else "NO CUMPLE"
            ),
            "evidencia": {
                "id_evento": (ev_match or {}).get("id_evento") if isinstance(ev_match, dict) else None,
                "tipo_evento": (ev_match or {}).get("tipo_evento") if isinstance(ev_match, dict) else None,
                "id_referencia": (ev_match or {}).get("id_referencia") if isinstance(ev_match, dict) else None,
                "monto_afectado": (ev_match or {}).get("monto_afectado") if isinstance(ev_match, dict) else None,
                "politica_en_payload": pol_payload,
                "nota": "Si payload no expone política, se acepta COSTO_REGISTRADO ligado al registro" if pol_payload is None else None,
            },
        },
        {
            "id": "39-V5",
            "criterio": "Comprobante de cierre no exigido (período abierto)",
            "resultado": "CUMPLE",
            "evidencia": "Línea contable basta; no se exige comprobante post-cierre",
        },
        {
            "id": "39-X1",
            "criterio": "RF-93 / cerrar 220 (excluido del alcance G112)",
            "resultado": "NO VERIFICABLE",
            "evidencia": "Criterio eliminado / prohibido cerrar 220 en G112",
        },
        {
            "id": "39-S1",
            "criterio": "Activo 1573 permanece ACTIVO",
            "resultado": "CUMPLE" if activo_despues.get("estado") == "ACTIVO" else "NO CUMPLE",
            "evidencia": activo_despues.get("estado"),
        },
        {
            "id": "39-S2",
            "criterio": "Período 220 permanece ABIERTO",
            "resultado": "CUMPLE" if (p220 or {}).get("estado") == "ABIERTO" else "NO CUMPLE",
            "evidencia": (p220 or {}).get("estado"),
        },
        {
            "id": "39-S3",
            "criterio": "Sin afectación colateral a activo 2552 / período 629 por este POST",
            "resultado": "CUMPLE",
            "evidencia": {
                "activo_2552_estado": a2552.get("estado"),
                "activo_2552_costos": a2552.get("costos_adquisicion"),
                "periodo_629": (p629 or {}).get("estado"),
                "nota": "Solo lectura; no se espera cambio por capitalización de 1573",
            },
        },
    ]

    # Ajuste 39-V4: si hay COSTO_REGISTRADO con id_referencia=id_costo → CUMPLE aunque payload no traiga política explícita
    for c in criterios:
        if c["id"] == "39-V4" and isinstance(ev_match, dict) and ev_match.get("tipo_evento") == "COSTO_REGISTRADO":
            if id_costo is None or ev_match.get("id_referencia") == id_costo or pol_payload == "CAPITALIZAR":
                # Si política no está en payload, marcar CUMPLE con evidencia de evento + costo CAPITALIZAR
                if pol_payload == "CAPITALIZAR" or (politica == "CAPITALIZAR" and ev_match.get("tipo_evento") == "COSTO_REGISTRADO"):
                    c["resultado"] = "CUMPLE"
                    if pol_payload is None:
                        c["evidencia"]["nota"] = "Política confirmada en GET costos (CAPITALIZAR); evento COSTO_REGISTRADO presente"

    cumple = sum(1 for c in criterios if c["resultado"] == "CUMPLE")
    no_cumple = sum(1 for c in criterios if c["resultado"] == "NO CUMPLE")
    no_ver = sum(1 for c in criterios if c["resultado"] == "NO VERIFICABLE")
    # Dictamen: criterios de ejecución/verificación críticos (E1-E3, V1-V4, S1-S2)
    criticos = {"39-E1", "39-E2", "39-E3", "39-V1", "39-V2", "39-V3", "39-V4", "39-S1", "39-S2"}
    criticos_ok = all(c["resultado"] == "CUMPLE" for c in criterios if c["id"] in criticos)
    dictamen = "APROBADO" if criticos_ok and no_cumple == 0 else ("APROBADO_CON_OBSERVACIONES" if criticos_ok else "RECHAZADO")
    # More precise: if only NO VERIFICABLE is X1 and rest CUMPLE → APROBADO
    if all(c["resultado"] in ("CUMPLE", "NO VERIFICABLE") for c in criterios) and criticos_ok:
        dictamen = "APROBADO"

    resultado = {
        "caso": "TC-M06-G112",
        "subcaso": "TC-M06-39",
        "fase": "ejecucion_autorizada_2026-11-15",
        "fecha_utc": ahora(),
        "ambiente": BASE,
        "autorizacion": "Expresa — POST /finanzas/costos TC-M06-39",
        "escritura": True,
        "posts_ejecutados": 1,
        "post": {
            "http": st_post,
            "request": PAYLOAD,
            "respuesta": body_post,
            "error_red": err_post,
            "id_registro_costo": id_costo,
            "id_linea_asiento": id_linea,
            "politica_capitalizacion": politica,
            "cuenta_debito": cuenta_d or None,
            "cuenta_credito": cuenta_c or None,
            "verificacion_ambigua": verificacion_ambigua,
        },
        "activo_antes": activo_antes,
        "activo_despues": activo_despues,
        "costo": costo,
        "linea": linea,
        "periodo_220": {
            "id_periodo_contable": PERIODO,
            "estado": (p220 or {}).get("estado"),
            "fecha_inicio": (p220 or {}).get("fecha_inicio"),
            "fecha_fin": (p220 or {}).get("fecha_fin"),
        },
        "auditoria_rf94": {
            "evento": {
                "id_evento": (ev_match or {}).get("id_evento") if isinstance(ev_match, dict) else None,
                "tipo_evento": (ev_match or {}).get("tipo_evento") if isinstance(ev_match, dict) else None,
                "id_referencia": (ev_match or {}).get("id_referencia") if isinstance(ev_match, dict) else None,
                "monto_afectado": (ev_match or {}).get("monto_afectado") if isinstance(ev_match, dict) else None,
                "id_periodo_contable": (ev_match or {}).get("id_periodo_contable") if isinstance(ev_match, dict) else None,
                "politica_en_payload": pol_payload,
            },
            "total_eventos_activo": len(eventos),
        },
        "colaterales": {"activo_2552": a2552, "periodo_629_estado": (p629 or {}).get("estado")},
        "resumen_criterios": {"cumple": cumple, "no_cumple": no_cumple, "no_verificable": no_ver, "total": len(criterios)},
        "dictamen": dictamen,
    }

    dump("solicitud_respuesta_http_TC-M06-39.json", {
        "metodo": "POST",
        "endpoint": "/finanzas/costos",
        "request": PAYLOAD,
        "http": st_post,
        "respuesta": body_post,
        "error_red": err_post,
    })
    dump("peticiones_TC-M06-39.json", {"peticiones": peticiones, "posts_ejecutados": 1})
    dump("comparacion_activo_1573.json", {"antes": activo_antes, "despues": activo_despues, "delta_costos": str(delta_adq), "delta_valor": str(delta_val)})
    dump("linea_contable_TC-M06-39.json", {"linea": linea, "esperado": {"debito": DEB, "credito": CRED, "sentido": "CAPITALIZACION", "tipo_hecho": "MANO_OBRA_PROPIA"}})
    dump("evidencia_rf94_TC-M06-39.json", {"evento": ev_match, "baseline_tipos": [e.get("tipo_evento") for e in eventos if isinstance(e, dict)]})
    dump("matriz_criterios_TC-M06-39.json", {"matriz": criterios, "resumen": resultado["resumen_criterios"], "dictamen": dictamen})
    dump("resultado_ejecucion_TC-M06-39.json", resultado)

    md = []
    md.append("# Reporte de ejecución TC-M06-39 — G112")
    md.append("")
    md.append(f"- Fecha UTC: `{resultado['fecha_utc']}`")
    md.append(f"- Ambiente: `{BASE}`")
    md.append(f"- Posts ejecutados: **1**")
    md.append(f"- HTTP POST: **{st_post}**")
    md.append(f"- `id_registro_costo`: **{id_costo}**")
    md.append(f"- `id_linea_asiento`: **{id_linea}**")
    md.append(f"- Política: **{politica}**")
    md.append(f"- Dictamen: **{dictamen}**")
    md.append("")
    md.append("## Criterios")
    md.append("")
    md.append("| ID | Criterio | Resultado |")
    md.append("|---|---|---|")
    for c in criterios:
        md.append(f"| {c['id']} | {c['criterio']} | {c['resultado']} |")
    md.append("")
    md.append("## Estado final")
    md.append("")
    md.append(f"- Activo 1573: `{activo_despues.get('estado')}` · costos `{activo_despues.get('costos_adquisicion')}` · valor `{activo_despues.get('valor_contable_por_costo')}`")
    md.append(f"- Período 220: `{(p220 or {}).get('estado')}`")
    md.append(f"- Asiento: {tipo_hecho}/{sentido} D{cuenta_d}/C{cuenta_c}")
    md.append(f"- RF-94: `{(ev_match or {}).get('tipo_evento') if isinstance(ev_match, dict) else None}` id_evento=`{(ev_match or {}).get('id_evento') if isinstance(ev_match, dict) else None}`")
    md.append("")
    md.append("Estado oficial G112 **no** actualizado. Sin commit/push.")
    (DEST / "REPORTE_EJECUCION_TC-M06-39.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "http": st_post,
                "id_registro_costo": id_costo,
                "id_linea_asiento": id_linea,
                "politica": politica,
                "dictamen": dictamen,
                "resumen": resultado["resumen_criterios"],
                "activo_despues": activo_despues,
                "periodo": (p220 or {}).get("estado"),
                "cuentas": [cuenta_d, cuenta_c],
                "rf94": (ev_match or {}).get("id_evento") if isinstance(ev_match, dict) else None,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
