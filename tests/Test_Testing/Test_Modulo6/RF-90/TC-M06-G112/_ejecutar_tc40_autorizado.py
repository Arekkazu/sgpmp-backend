# | Fecha      | Nombre | Que se hizo |
# |------------|--------|-------------|
# | 2026-11-15 | —      | Ejecución autorizada TC-M06-40: POST costo GASTO activo 2552. |
"""Ejecución autorizada TC-M06-40 / G112. Un solo POST. Sin commit/push."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE = "https://api.inmero.co/api-sgpmp-test"
ZONA = "America/Bogota"
ROOT = Path(__file__).resolve().parent
DEST = ROOT / "resultados" / "ejecucion_tc40_2026-11-15"

ACTIVO = 2552
ESPECIE = 655
PERIODO = 629
NIT = "901666216"
ASIG = 8581
DEB = "510506"
CRED = "250505"
PAYLOAD = {
    "subtipo_costo": "INVERSION_DIRECTA",
    "origen_costo": "MANO_OBRA_PROPIA",
    "monto_costo": "100000.0000",
    "fecha_costo": "2026-11-15",
    "id_activo_biologico": 2552,
    "justificacion": "TC-M06-G112 / TC-M06-40 — inversión directa llevada a gasto QA (autorizada)",
    "confirmar_capitalizacion": False,
}
SECRETOS = {"token", "access_token", "contrasena", "password", "hash_integridad", "Authorization"}


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
    if d > 12:
        return "..."
    if isinstance(v, dict):
        return {k: ({"omitido": True} if k in SECRETOS or "token" in k.lower() else limpiar(x, d + 1)) for k, x in v.items()}
    if isinstance(v, list):
        return [limpiar(x, d + 1) for x in v[:100]]
    if isinstance(v, str) and len(v) > 1000:
        return v[:1000] + "…"
    return v


def num(v):
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def ficha_activo(det):
    if not isinstance(det, dict):
        return {}
    act = det.get("activo") if isinstance(det.get("activo"), dict) else {}
    vc = det.get("valoracion_costo") if isinstance(det.get("valoracion_costo"), dict) else {}
    lineas = det.get("lineas") if isinstance(det.get("lineas"), list) else []
    return {
        "identificador": act.get("identificador"),
        "estado": act.get("estado"),
        "id_especie": act.get("id_especie"),
        "id_finca": act.get("id_finca"),
        "costos_adquisicion": str(vc.get("costos_adquisicion")) if vc.get("costos_adquisicion") is not None else None,
        "valor_contable_por_costo": str(vc.get("valor_contable_por_costo")) if vc.get("valor_contable_por_costo") is not None else None,
        "es_activa": vc.get("es_activa"),
        "lineas_count": len(lineas),
    }


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
    if "api-sgpmp-test" not in BASE:
        raise SystemExit("Ambiente no es TEST")

    st, me = pedir("GET", "/usuarios/me", token=token)
    pet.append({"fase": "perfil", "http": st, "rol": (me or {}).get("nombre_rol"), "id_usuario": (me or {}).get("id_usuario")})
    st, perm = pedir("GET", "/sesiones/me/permisos", token=token)
    acciones = sorted(
        {
            p.get("id_accion")
            for p in ((perm or {}).get("permisos") or [])
            if isinstance(p, dict) and p.get("nombre_recurso") == "costos_activos"
        }
    ) if isinstance(perm, dict) else []
    pet.append({"fase": "permisos", "http": st, "costos_activos": acciones})

    # --- Precondiciones ---
    st, det0 = pedir("GET", f"/finanzas/activos/{ACTIVO}", token=token)
    act0 = ficha_activo(det0)
    pet.append({"fase": "pre_activo", "http": st, "activo": act0})

    st, cfg = pedir("GET", "/finanzas/configuracion", token=token)
    matriz = (cfg or {}).get("matriz") if isinstance(cfg, dict) else []
    if not isinstance(matriz, list):
        matriz = []
    a8581 = next(
        (
            a
            for a in matriz
            if isinstance(a, dict)
            and (a.get("id_asignacion_cuenta_contable") or a.get("id_asignacion")) == ASIG
        ),
        None,
    )
    a8581_f = None
    if isinstance(a8581, dict):
        a8581_f = {
            "id": a8581.get("id_asignacion_cuenta_contable") or a8581.get("id_asignacion"),
            "tipo_hecho": a8581.get("tipo_hecho"),
            "sentido": a8581.get("sentido"),
            "id_especie": a8581.get("id_especie"),
            "subtipo_costo": a8581.get("subtipo_costo"),
            "cuenta_debito": a8581.get("cuenta_debito"),
            "cuenta_credito": a8581.get("cuenta_credito"),
        }
    pet.append({"fase": "pre_matriz", "http": st, "asignacion_8581": a8581_f})

    st, ps = pedir("GET", f"/finanzas/periodos?numero_id_tributaria={NIT}", token=token)
    p629 = next((p for p in (ps or []) if isinstance(p, dict) and p.get("id_periodo_contable") == PERIODO), None)
    periodo0 = {
        "estado": (p629 or {}).get("estado"),
        "fecha_inicio": (p629 or {}).get("fecha_inicio"),
        "fecha_fin": (p629 or {}).get("fecha_fin"),
        "nit": (p629 or {}).get("numero_id_tributaria"),
    }
    pet.append({"fase": "pre_periodo", "http": st, "periodo_629": periodo0})

    st, costos0 = pedir("GET", f"/finanzas/costos?id_activo_biologico={ACTIVO}", token=token)
    costos0_l = costos0 if isinstance(costos0, list) else []
    pet.append({"fase": "pre_costos", "http": st, "total": len(costos0_l)})

    checks = {
        "ambiente_test": "api-sgpmp-test" in BASE,
        "activo_activo": act0.get("estado") == "ACTIVO",
        "valor_3m": num(act0.get("costos_adquisicion")) == 3000000.0
        or num(act0.get("valor_contable_por_costo")) == 3000000.0,
        "periodo_abierto": periodo0.get("estado") == "ABIERTO"
        and periodo0.get("fecha_inicio") == "2026-11-01"
        and str(periodo0.get("nit") or "").startswith("901666216"),
        "asig_8581": bool(
            a8581_f
            and a8581_f["tipo_hecho"] == "MANO_OBRA_PROPIA"
            and a8581_f["sentido"] == "UNICO"
            and a8581_f["id_especie"] == ESPECIE
            and a8581_f["subtipo_costo"] == "INVERSION_DIRECTA"
            and a8581_f["cuenta_debito"] == DEB
            and a8581_f["cuenta_credito"] == CRED
        ),
        "permiso": len(acciones) > 0,
    }
    if not all(checks.values()):
        (DEST / "DETENIDO_precondiciones.json").write_text(
            json.dumps({"checks": checks, "act0": act0, "a8581": a8581_f, "periodo0": periodo0}, ensure_ascii=False, indent=2)
            + "\n",
            encoding="utf-8",
        )
        print(json.dumps({"detenido": True, "checks": checks}, ensure_ascii=False))
        return

    # --- POST único ---
    http, resp = pedir("POST", "/finanzas/costos", cuerpo=PAYLOAD, token=token)
    pet.append(
        {
            "fase": "post_costo",
            "metodo": "POST",
            "ruta": "/finanzas/costos",
            "http": http,
            "request": PAYLOAD,
            "respuesta": limpiar(resp),
        }
    )

    # Si timeout/incierto: consultar persistencia (aquí http conocido)
    if http is None:
        st, costos_chk = pedir("GET", f"/finanzas/costos?id_activo_biologico={ACTIVO}", token=token)
        pet.append({"fase": "post_incierto_consulta", "http": st, "costos": limpiar(costos_chk)})
        (DEST / "INCIERTO_sin_reintento.json").write_text(
            json.dumps({"peticiones": pet}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(json.dumps({"incierto": True, "sin_reintento": True}, ensure_ascii=False))
        return

    id_costo = None
    id_linea = None
    politica = None
    if isinstance(resp, dict):
        id_costo = resp.get("id_registro_costo") or resp.get("id_costo") or resp.get("id")
        id_linea = resp.get("id_linea_asiento") or resp.get("id_linea_asiento_nic41")
        politica = resp.get("politica_capitalizacion")
        # nested
        if id_linea is None and isinstance(resp.get("linea"), dict):
            id_linea = resp["linea"].get("id_linea_asiento_nic41") or resp["linea"].get("id")
        if politica is None and isinstance(resp.get("costo"), dict):
            politica = resp["costo"].get("politica_capitalizacion")
            id_costo = id_costo or resp["costo"].get("id_registro_costo")

    # --- Post verificaciones ---
    st, costos1 = pedir("GET", f"/finanzas/costos?id_activo_biologico={ACTIVO}", token=token)
    costos1_l = costos1 if isinstance(costos1, list) else []
    costo = None
    if id_costo:
        costo = next((c for c in costos1_l if isinstance(c, dict) and c.get("id_registro_costo") == id_costo), None)
    if costo is None and costos1_l:
        # match by justificacion
        costo = next(
            (
                c
                for c in costos1_l
                if isinstance(c, dict)
                and "TC-M06-40" in str(c.get("justificacion") or "")
            ),
            costos1_l[-1] if costos1_l else None,
        )
        if isinstance(costo, dict):
            id_costo = id_costo or costo.get("id_registro_costo")
    pet.append({"fase": "post_costos", "http": st, "total": len(costos1_l), "costo": limpiar(costo)})

    st, det1 = pedir("GET", f"/finanzas/activos/{ACTIVO}", token=token)
    act1 = ficha_activo(det1)
    pet.append({"fase": "post_activo", "http": st, "activo": act1})

    st, lineas = pedir("GET", f"/finanzas/lineas?id_periodo_contable={PERIODO}", token=token)
    lineas_l = lineas if isinstance(lineas, list) else []
    linea = None
    if id_linea:
        linea = next(
            (
                x
                for x in lineas_l
                if isinstance(x, dict)
                and (x.get("id_linea_asiento_nic41") or x.get("id")) == id_linea
            ),
            None,
        )
    if linea is None:
        # match by origen costo / activo / cuentas
        candidatos = [
            x
            for x in lineas_l
            if isinstance(x, dict)
            and x.get("id_activo_biologico") == ACTIVO
            and x.get("tipo_hecho") == "MANO_OBRA_PROPIA"
            and x.get("sentido") == "UNICO"
            and x.get("cuenta_debito") == DEB
        ]
        if id_costo:
            c2 = [
                x
                for x in candidatos
                if x.get("id_origen") == id_costo or x.get("tabla_origen") == "registros_costos"
            ]
            if c2:
                candidatos = c2
        linea = candidatos[-1] if candidatos else None
        if isinstance(linea, dict):
            id_linea = id_linea or linea.get("id_linea_asiento_nic41") or linea.get("id")
    pet.append({"fase": "post_lineas", "http": st, "total": len(lineas_l), "linea": limpiar(linea)})

    st, ps1 = pedir("GET", f"/finanzas/periodos?numero_id_tributaria={NIT}", token=token)
    p629b = next((p for p in (ps1 or []) if isinstance(p, dict) and p.get("id_periodo_contable") == PERIODO), None)
    periodo1 = {"estado": (p629b or {}).get("estado"), "fecha_inicio": (p629b or {}).get("fecha_inicio")}
    pet.append({"fase": "post_periodo_629", "http": st, "periodo": periodo1})

    st219, ps219 = pedir("GET", "/finanzas/periodos?numero_id_tributaria=900000002", token=token)
    p219 = next((p for p in (ps219 or []) if isinstance(p, dict) and p.get("id_periodo_contable") == 219), None)
    st220, ps220 = pedir("GET", "/finanzas/periodos?numero_id_tributaria=900000003", token=token)
    p220 = next((p for p in (ps220 or []) if isinstance(p, dict) and p.get("id_periodo_contable") == 220), None)
    pet.append(
        {
            "fase": "post_periodos_protegidos",
            "219": {"http": st219, "estado": (p219 or {}).get("estado")},
            "220": {"http": st220, "estado": (p220 or {}).get("estado")},
        }
    )

    # RF-94
    eventos = []
    for tipo in ("COSTO_REGISTRADO", "LINEA_ASIENTO_REGISTRADA", "ASIENTO_REGISTRADO"):
        for ref_key, ref_val in (("id_referencia", id_costo), ("id_referencia", id_linea)):
            if not ref_val:
                continue
            ruta = "/finanzas/auditoria?" + urllib.parse.urlencode(
                [
                    ("tipo_evento", tipo),
                    ("id_referencia", str(ref_val)),
                    ("formato", "TECNICO"),
                    ("tamano", "10"),
                    ("orden", "DESC"),
                ]
            )
            st_a, body = pedir("GET", ruta, token=token)
            items = []
            if isinstance(body, dict):
                items = body.get("eventos") or body.get("items") or body.get("registros") or []
            if not isinstance(items, list):
                items = []
            for ev in items[:5]:
                if isinstance(ev, dict):
                    eventos.append(
                        {
                            "tipo_busqueda": tipo,
                            "http": st_a,
                            "id_evento": ev.get("id_evento") or ev.get("id"),
                            "tipo_evento": ev.get("tipo_evento") or tipo,
                            "id_referencia": ev.get("id_referencia"),
                            "timestamp_evento": ev.get("timestamp_evento") or ev.get("fecha_evento"),
                            "id_usuario": ev.get("id_usuario"),
                        }
                    )
    # also recent COSTO_REGISTRADO
    ruta = "/finanzas/auditoria?" + urllib.parse.urlencode(
        [("tipo_evento", "COSTO_REGISTRADO"), ("formato", "TECNICO"), ("tamano", "10"), ("orden", "DESC")]
    )
    st_a, body = pedir("GET", ruta, token=token)
    items = []
    if isinstance(body, dict):
        items = body.get("eventos") or body.get("items") or body.get("registros") or []
    for ev in (items or [])[:10]:
        if isinstance(ev, dict) and (
            ev.get("id_referencia") == id_costo
            or (ev.get("id_activo_biologico") == ACTIVO)
        ):
            eventos.append(
                {
                    "tipo_busqueda": "COSTO_REGISTRADO_reciente",
                    "http": st_a,
                    "id_evento": ev.get("id_evento") or ev.get("id"),
                    "tipo_evento": ev.get("tipo_evento") or "COSTO_REGISTRADO",
                    "id_referencia": ev.get("id_referencia"),
                    "id_activo_biologico": ev.get("id_activo_biologico"),
                    "timestamp_evento": ev.get("timestamp_evento") or ev.get("fecha_evento"),
                    "id_usuario": ev.get("id_usuario"),
                }
            )
    # dedupe by id_evento
    seen = set()
    eventos_u = []
    for e in eventos:
        i = e.get("id_evento")
        if i in seen:
            continue
        seen.add(i)
        eventos_u.append(e)
    pet.append({"fase": "rf94", "eventos": eventos_u})

    # Criterios
    costo = costo or {}
    linea = linea or {}
    politica_final = costo.get("politica_capitalizacion") or politica
    cuentas_ok = linea.get("cuenta_debito") == DEB and linea.get("cuenta_credito") == CRED
    # Winner 8581 inferred: same accounts + species/subtipo match specific assignment (API no guarda id_asignacion en línea)
    ganadora_8581 = cuentas_ok and (
        linea.get("id_especie") == ESPECIE or act1.get("id_especie") == ESPECIE
    ) and (linea.get("subtipo_costo") == "INVERSION_DIRECTA" or costo.get("subtipo_costo") == "INVERSION_DIRECTA")

    valor_igual = (
        num(act1.get("costos_adquisicion")) == num(act0.get("costos_adquisicion"))
        and num(act1.get("valor_contable_por_costo")) == num(act0.get("valor_contable_por_costo"))
    )
    sin_cap = (
        politica_final == "GASTO"
        and PAYLOAD["confirmar_capitalizacion"] is False
        and (linea.get("sentido") == "UNICO")
        and not any(
            isinstance(x, dict)
            and x.get("id_activo_biologico") == ACTIVO
            and x.get("sentido") == "CAPITALIZACION"
            and (x.get("id_origen") == id_costo)
            for x in lineas_l
        )
    )

    matriz = [
        {"id": "40.1", "criterio": "POST HTTP éxito", "resultado": "CUMPLE" if http in (200, 201) else "NO CUMPLE", "evidencia": {"http": http}},
        {"id": "40.2", "criterio": "Línea REGISTRADA", "resultado": "CUMPLE" if linea.get("estado") == "REGISTRADA" else "NO CUMPLE", "evidencia": {"estado": linea.get("estado"), "id_linea": id_linea}},
        {"id": "40.3", "criterio": "Origen MANO_OBRA_PROPIA", "resultado": "CUMPLE" if (costo.get("origen_costo") == "MANO_OBRA_PROPIA" or linea.get("tipo_hecho") == "MANO_OBRA_PROPIA") else "NO CUMPLE", "evidencia": {"origen": costo.get("origen_costo"), "tipo_hecho": linea.get("tipo_hecho")}},
        {"id": "40.4", "criterio": "Subtipo INVERSION_DIRECTA", "resultado": "CUMPLE" if (costo.get("subtipo_costo") == "INVERSION_DIRECTA" or linea.get("subtipo_costo") == "INVERSION_DIRECTA") else "NO CUMPLE", "evidencia": {"subtipo_costo": costo.get("subtipo_costo") or linea.get("subtipo_costo")}},
        {"id": "40.5", "criterio": "Política GASTO", "resultado": "CUMPLE" if politica_final == "GASTO" else "NO CUMPLE", "evidencia": politica_final},
        {"id": "40.6", "criterio": "Débito 510506", "resultado": "CUMPLE" if linea.get("cuenta_debito") == DEB else "NO CUMPLE", "evidencia": linea.get("cuenta_debito")},
        {"id": "40.7", "criterio": "Crédito 250505", "resultado": "CUMPLE" if linea.get("cuenta_credito") == CRED else "NO CUMPLE", "evidencia": linea.get("cuenta_credito")},
        {"id": "40.8", "criterio": "Asignación ganadora 8581 (inferida por cuentas+ámbito)", "resultado": "CUMPLE" if ganadora_8581 else "NO CUMPLE", "evidencia": {"cuentas_ok": cuentas_ok, "a8581": a8581_f, "nota": "La línea no persiste id_asignacion; se infiere por D510506/C250505 + especie 655 + INVERSION_DIRECTA coincidentes con 8581"}},
        {"id": "40.9", "criterio": "Activo 2552 ACTIVO", "resultado": "CUMPLE" if act1.get("estado") == "ACTIVO" else "NO CUMPLE", "evidencia": act1.get("estado")},
        {"id": "40.10", "criterio": "Valor costo permanece 3.000.000", "resultado": "CUMPLE" if valor_igual and (num(act1.get("valor_contable_por_costo")) == 3000000.0 or num(act1.get("costos_adquisicion")) == 3000000.0) else "NO CUMPLE", "evidencia": {"antes": act0, "despues": act1}},
        {"id": "40.11", "criterio": "Capitalización no confirmada / sin asiento CAPITALIZACION indebido", "resultado": "CUMPLE" if sin_cap else "NO CUMPLE", "evidencia": {"politica": politica_final, "sentido": linea.get("sentido"), "confirmar_capitalizacion": False}},
        {"id": "40.12", "criterio": "Período 629 ABIERTO", "resultado": "CUMPLE" if periodo1.get("estado") == "ABIERTO" else "NO CUMPLE", "evidencia": periodo1},
        {"id": "40.13", "criterio": "Períodos 219/220 intactos", "resultado": "CUMPLE" if (p219 or {}).get("estado") == "CERRADO" and (p220 or {}).get("estado") == "ABIERTO" else "NO CUMPLE", "evidencia": {"219": (p219 or {}).get("estado"), "220": (p220 or {}).get("estado")}},
    ]

    # If accounts wrong, force stop messaging
    cuentas_fallo = not cuentas_ok
    tc40_ok = all(r["resultado"] == "CUMPLE" for r in matriz) and not cuentas_fallo
    dictamen = "APROBADO" if tc40_ok else "NO CUMPLE"

    hallazgo_h1 = {
        "id": "H1",
        "severidad": "MEDIA",
        "descripcion": (
            "No se declara que la asignación 34 conserve D158405/C250505. "
            "La reevaluación identificó general vigente 8898 D510506/C250505 y específica 8581 "
            "para especie 655 + INVERSION_DIRECTA. Hallazgo de configuración separado; "
            "ninguna asignación fue modificada en esta ejecución."
        ),
        "accion": "Reportar a Samuel/DBA; fuera del alcance de TC-M06-40",
    }

    resultado = {
        "caso": "TC-M06-G112",
        "subcaso": "TC-M06-40",
        "fase": "ejecucion_autorizada_2026-11-15",
        "fecha_utc": ahora(),
        "ambiente": BASE,
        "autorizacion": "Expresa — POST /finanzas/costos TC-M06-40",
        "escritura": True,
        "posts_ejecutados": 1,
        "precondiciones": checks,
        "post": {
            "http": http,
            "request": PAYLOAD,
            "respuesta": limpiar(resp),
            "id_registro_costo": id_costo,
            "id_linea_asiento": id_linea,
            "politica_capitalizacion": politica_final,
            "cuenta_debito": (linea or {}).get("cuenta_debito"),
            "cuenta_credito": (linea or {}).get("cuenta_credito"),
        },
        "activo_antes": act0,
        "activo_despues": act1,
        "costo": limpiar(costo),
        "linea": limpiar(linea),
        "periodo_629": {"antes": periodo0, "despues": periodo1},
        "periodos_protegidos": {"219": (p219 or {}).get("estado"), "220": (p220 or {}).get("estado")},
        "resolucion_matriz": {
            "asignacion_8581_pre": a8581_f,
            "cuentas_linea": {"debito": (linea or {}).get("cuenta_debito"), "credito": (linea or {}).get("cuenta_credito")},
            "inferencia_ganadora_8581": ganadora_8581,
        },
        "rf94": eventos_u,
        "hallazgo_h1": hallazgo_h1,
        "matriz": matriz,
        "dictamen_tc40": dictamen,
        "dictamen_g112_global": "NO APROBADO (grupo incompleto; solo TC-M06-40 evaluado en esta ejecución)",
        "estado_oficial_g112_no_modificado_como_aprobado_global": True,
    }

    (DEST / "solicitud_respuesta_http_TC-M06-40.json").write_text(
        json.dumps({"request": PAYLOAD, "http": http, "respuesta": limpiar(resp)}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (DEST / "peticiones_TC-M06-40.json").write_text(json.dumps({"peticiones": pet}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (DEST / "comparacion_activo_2552.json").write_text(
        json.dumps({"antes": act0, "despues": act1, "valor_sin_cambio": valor_igual}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (DEST / "linea_contable_TC-M06-40.json").write_text(json.dumps(limpiar(linea), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (DEST / "resolucion_matriz_8581.json").write_text(
        json.dumps(resultado["resolucion_matriz"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (DEST / "evidencia_rf94_TC-M06-40.json").write_text(json.dumps({"eventos": eventos_u}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (DEST / "hallazgo_H1_configuracion.json").write_text(json.dumps(hallazgo_h1, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (DEST / "matriz_criterios_TC-M06-40.json").write_text(
        json.dumps({"matriz": matriz, "aprobado": tc40_ok}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (DEST / "resultado_ejecucion_TC-M06-40.json").write_text(json.dumps(resultado, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    md = f"""# Ejecución autorizada TC-M06-40 / G112

**Fecha UTC:** {resultado['fecha_utc']}  
**Ambiente:** `{BASE}`  
**Dictamen TC-M06-40:** **{dictamen}**  
**Dictamen G112 global:** no aprobado (grupo incompleto)

## POST

- HTTP **{http}**
- id_registro_costo: `{id_costo}`
- id_linea: `{id_linea}`
- política: `{politica_final}`
- cuentas: D`{(linea or {}).get('cuenta_debito')}` / C`{(linea or {}).get('cuenta_credito')}`

## Matriz

| ID | Criterio | Resultado |
|---|---|---|
"""
    for row in matriz:
        md += f"| {row['id']} | {row['criterio']} | {row['resultado']} |\n"
    md += f"""
## Hallazgo H1

{hallazgo_h1['descripcion']}

## Evidencias

`{DEST.as_posix()}/`
"""
    (DEST / "REPORTE_EJECUCION_TC-M06-40.md").write_text(md, encoding="utf-8")

    print(
        json.dumps(
            {
                "out": str(DEST),
                "http": http,
                "id_costo": id_costo,
                "id_linea": id_linea,
                "politica": politica_final,
                "debito": (linea or {}).get("cuenta_debito"),
                "credito": (linea or {}).get("cuenta_credito"),
                "dictamen_tc40": dictamen,
                "matriz": {r["id"]: r["resultado"] for r in matriz},
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
