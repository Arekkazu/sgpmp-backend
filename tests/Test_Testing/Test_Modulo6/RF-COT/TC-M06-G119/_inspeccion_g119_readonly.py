# | Fecha      | Nombre | Que se hizo |
# |------------|--------|-------------|
# | 2026-11-13 | —      | Inspección solo-lectura G119 (TC-M06-51/52); sin POST anulación ni vencer. |
"""Inspeccion solo-lectura TC-M06-G119. Sin escritura."""
from __future__ import annotations

import json
import os
import shutil
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE = "https://api.inmero.co/api-sgpmp-test"
ZONA = "America/Bogota"
ROOT = Path(__file__).resolve().parent
RES = ROOT / "resultados"
PRIMERA = RES / "primera_evaluacion"
PREP = RES / "preparacion"
COT_51 = 6
COT_52 = 7
ACTIVO_51 = 1571
ACTIVO_52 = 1570
NIT_OPS = "900000003"
NIT_CIERRE = "900000002"
PERIODO = 220
PERIODO_219 = 219
SECRETOS = {
    "token", "access_token", "contrasena", "password", "hash_integridad",
    "numero_id_tributaria", "identificador", "finca", "correo_electronico", "nombre_usuario",
}


def pedir(metodo, ruta, cuerpo=None, token=None, timeout=30):
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
    if isinstance(v, str) and len(v) > 400:
        return v[:400]
    return v


def preservar_historico():
    PRIMERA.mkdir(parents=True, exist_ok=True)
    for name in (
        "resumen_ejecucion_TC-M06-G119.json",
        "evidencia_peticiones_TC-M06-G119.json",
        "resultado_ejecucion_TC-M06-G119.html",
        "analisis_hallazgos_TC-M06-G119.md",
    ):
        src, dst = RES / name, PRIMERA / name
        if src.exists() and not dst.exists():
            shutil.copy2(src, dst)
            src.unlink()
        elif src.exists() and dst.exists() and src.read_bytes() == dst.read_bytes():
            src.unlink()


def ficha_cotizacion(c):
    if not isinstance(c, dict):
        return None
    return {
        "id_cotizacion": c.get("id_cotizacion"),
        "estado": c.get("estado"),
        "version": c.get("version"),
        "activos_cotizados": c.get("activos_cotizados"),
        "fecha_emision": c.get("fecha_emision"),
        "fecha_vencimiento": c.get("fecha_vencimiento"),
        "motivo_anulacion": c.get("motivo_anulacion"),
        "id_periodo_contable": c.get("id_periodo_contable"),
        "estado_periodo": c.get("estado_periodo"),
        "valor_cotizacion_propuesto": str(c["valor_cotizacion_propuesto"]) if c.get("valor_cotizacion_propuesto") is not None else None,
        "valor_razonable_referencia": str(c["valor_razonable_referencia"]) if c.get("valor_razonable_referencia") is not None else None,
        "fecha_actualizacion": c.get("fecha_actualizacion"),
    }


def ultimo_calculo(calcs):
    if not isinstance(calcs, list) or not calcs:
        return None
    ordenados = sorted(
        [x for x in calcs if isinstance(x, dict)],
        key=lambda x: str(x.get("fecha_calculo") or x.get("fecha_creacion") or ""),
        reverse=True,
    )
    return ordenados[0] if ordenados else None


def tiene_permiso(permisos_payload, recurso, id_accion):
    if not isinstance(permisos_payload, dict):
        return False
    for p in permisos_payload.get("permisos") or []:
        if isinstance(p, dict) and p.get("nombre_recurso") == recurso and p.get("id_accion") == id_accion:
            return True
    return False


def main():
    correo, clave = os.environ.get("QA_CORREO"), os.environ.get("QA_CONTRASENA")
    if not correo or not clave:
        raise SystemExit("Defina QA_CORREO y QA_CONTRASENA")

    preservar_historico()
    PREP.mkdir(parents=True, exist_ok=True)
    pet = []
    informe = {
        "caso": "TC-M06-G119",
        "subcasos": ["TC-M06-51", "TC-M06-52"],
        "issue": "#1022 / INC-M06-335-G91",
        "fase": "inspeccion_preparacion_solo_lectura",
        "ambiente": BASE,
        "generado_en": datetime.now(timezone.utc).isoformat(),
        "restricciones": "Sin POST/PUT/PATCH/DELETE; sin vencer manual; sin SQL",
        "peticiones": pet,
        "escritura_ejecutada": False,
    }

    def reg(metodo, ruta, codigo, payload, nota=None):
        pet.append({
            "metodo": metodo, "ruta": ruta, "codigo": codigo,
            "escritura": metodo != "GET",
            "en": datetime.now(timezone.utc).isoformat(),
            "nota": nota,
            "respuesta": limpiar(payload),
        })

    c, health = pedir("GET", "/health")
    reg("GET", "/health", c, health, "health")
    c, login = pedir("POST", "/sesiones/", {"correo_electronico": correo, "contrasena": clave})
    token = login.get("token") if isinstance(login, dict) else None
    reg("POST", "/sesiones/", c, {"ok": bool(token), "tipo": (login or {}).get("tipo") if isinstance(login, dict) else None}, "login")
    if not token:
        informe["dictamen_preparacion"] = {"categoria": "BLOQUEADO", "motivo": "Sin sesion Contador"}
        _guardar(informe)
        raise SystemExit("SIN SESION")

    c, perfil = pedir("GET", "/usuarios/me", token=token)
    rol = (perfil or {}).get("nombre_rol") if isinstance(perfil, dict) else None
    reg("GET", "/usuarios/me", c, {"nombre_rol": rol}, "perfil")

    c, permisos = pedir("GET", "/sesiones/me/permisos", token=token)
    informe["permisos"] = {
        "rol": rol,
        "cotizaciones_R": tiene_permiso(permisos, "cotizaciones", 2),
        "cotizaciones_D": tiene_permiso(permisos, "cotizaciones", 4),  # desactivar/anular
        "auditoria_financiera_R": tiene_permiso(permisos, "auditoria_financiera", 2),
        "valoracion_activos_R": tiene_permiso(permisos, "valoracion_activos", 2),
    }
    # Also check accion ids present for cotizaciones
    acciones_cot = sorted({
        p.get("id_accion") for p in (permisos.get("permisos") or [])
        if isinstance(p, dict) and p.get("nombre_recurso") == "cotizaciones"
    }) if isinstance(permisos, dict) else []
    informe["permisos"]["cotizaciones_acciones"] = acciones_cot
    reg("GET", "/sesiones/me/permisos", c, informe["permisos"], "permisos")

    # List cotizaciones and pick 6 / 7
    c, cots = pedir("GET", "/finanzas/cotizaciones", token=token)
    lista = cots if isinstance(cots, list) else []
    por_id = {x.get("id_cotizacion"): x for x in lista if isinstance(x, dict)}
    cot6 = ficha_cotizacion(por_id.get(COT_51))
    cot7 = ficha_cotizacion(por_id.get(COT_52))
    informe["cotizacion_6"] = cot6
    informe["cotizacion_7"] = cot7
    reg("GET", "/finanzas/cotizaciones", c, {
        "total": len(lista),
        "ids": [x.get("id_cotizacion") for x in lista if isinstance(x, dict)],
        "cotizacion_6": cot6,
        "cotizacion_7": cot7,
    }, "cotizaciones")

    # Filter by activo as extra confirmation
    for activo, nota in ((ACTIVO_51, "cots_activo_1571"), (ACTIVO_52, "cots_activo_1570")):
        ruta = f"/finanzas/cotizaciones?id_activo_biologico={activo}"
        c, subset = pedir("GET", ruta, token=token)
        reg("GET", ruta, c, {
            "total": len(subset) if isinstance(subset, list) else None,
            "ids": [x.get("id_cotizacion") for x in (subset or []) if isinstance(x, dict)],
            "estados": [
                {"id": x.get("id_cotizacion"), "estado": x.get("estado"), "version": x.get("version")}
                for x in (subset or []) if isinstance(x, dict)
            ],
        }, nota)

    # Activo 1570 (TC-52) and 1571 (dependency G118 / cot 6)
    for activo_id, key in ((ACTIVO_52, "activo_1570"), (ACTIVO_51, "activo_1571")):
        c, det = pedir("GET", f"/finanzas/activos/{activo_id}", token=token)
        act = (det or {}).get("activo") if isinstance(det, dict) else None
        recs = (det or {}).get("reconocimientos") if isinstance(det, dict) else []
        calcs = (det or {}).get("calculos") if isinstance(det, dict) else []
        if not isinstance(recs, list):
            recs = []
        if not isinstance(calcs, list):
            calcs = []
        rec = next((r for r in recs if isinstance(r, dict) and r.get("estado") == "CONFIRMADO"), None)
        calc = ultimo_calculo(calcs)
        out = {
            "http": c,
            "identificador": (act or {}).get("identificador") if isinstance(act, dict) else None,
            "estado": (act or {}).get("estado") if isinstance(act, dict) else None,
            "id_finca": (act or {}).get("id_finca") if isinstance(act, dict) else None,
            "razon_social": (act or {}).get("razon_social") if isinstance(act, dict) else None,
            "indicador_valoracion": (rec or {}).get("indicador_valoracion") if isinstance(rec, dict) else None,
            "valor_razonable_neto": str(calc.get("valor_neto")) if calc and calc.get("valor_neto") is not None else None,
            "fecha_calculo": (calc or {}).get("fecha_calculo") if isinstance(calc, dict) else None,
        }
        informe[key] = out
        reg("GET", f"/finanzas/activos/{activo_id}", c, out, key)

    # Periodos
    c, p_ops = pedir("GET", f"/finanzas/periodos?numero_id_tributaria={NIT_OPS}", token=token)
    p220 = next((p for p in (p_ops or []) if isinstance(p, dict) and p.get("id_periodo_contable") == PERIODO), None)
    informe["periodo_220"] = {
        "encontrado": p220 is not None,
        "estado": (p220 or {}).get("estado"),
        "fecha_inicio": (p220 or {}).get("fecha_inicio"),
        "fecha_fin": (p220 or {}).get("fecha_fin"),
        "razon_social": (p220 or {}).get("razon_social"),
    }
    reg("GET", f"/finanzas/periodos?numero_id_tributaria={NIT_OPS}", c, {"periodo_220": informe["periodo_220"]}, "periodo_220")

    c, p_cie = pedir("GET", f"/finanzas/periodos?numero_id_tributaria={NIT_CIERRE}", token=token)
    p219 = next((p for p in (p_cie or []) if isinstance(p, dict) and p.get("id_periodo_contable") == PERIODO_219), None)
    informe["periodo_219"] = {
        "encontrado": p219 is not None,
        "estado": (p219 or {}).get("estado"),
        "fecha_inicio": (p219 or {}).get("fecha_inicio"),
        "fecha_fin": (p219 or {}).get("fecha_fin"),
        "razon_social": (p219 or {}).get("razon_social"),
    }
    reg("GET", f"/finanzas/periodos?numero_id_tributaria={NIT_CIERRE}", c, {"periodo_219": informe["periodo_219"]}, "periodo_219")

    # Auditoria
    aud = {}
    if informe["permisos"]["auditoria_financiera_R"]:
        for tipo in ("COTIZACION_ANULADA", "COTIZACION_VENCIDA", "COTIZACION_REGISTRADA"):
            ruta = "/finanzas/auditoria?" + urllib.parse.urlencode([
                ("tipo_evento", tipo), ("formato", "TECNICO"), ("tamano", "20"), ("orden", "DESC"),
            ])
            c, data = pedir("GET", ruta, token=token)
            total = (data or {}).get("total_registros") if isinstance(data, dict) else None
            items = (data or {}).get("items") or (data or {}).get("registros") or (data or {}).get("eventos") or []
            if not isinstance(items, list):
                items = []
            muestra = []
            for ev in items[:20]:
                if not isinstance(ev, dict):
                    continue
                muestra.append({
                    "id_evento": ev.get("id_evento") or ev.get("id"),
                    "id_referencia": ev.get("id_referencia"),
                    "timestamp_evento": ev.get("timestamp_evento") or ev.get("fecha_evento"),
                    "tipo_actor": ev.get("tipo_actor") or ev.get("actor"),
                    "id_sistema": ev.get("id_sistema"),
                    "tipo_evento": ev.get("tipo_evento") or tipo,
                })
            # Also filter by id_referencia 6/7 if present in any structure
            aud[tipo] = {"http": c, "total_registros": total, "muestra": muestra}
            # Dedicated filter by referencia if API supports id_referencia
            for ref in (COT_51, COT_52):
                ruta_ref = "/finanzas/auditoria?" + urllib.parse.urlencode([
                    ("tipo_evento", tipo), ("id_referencia", str(ref)),
                    ("formato", "TECNICO"), ("tamano", "10"), ("orden", "DESC"),
                ])
                c2, data2 = pedir("GET", ruta_ref, token=token)
                total2 = (data2 or {}).get("total_registros") if isinstance(data2, dict) else None
                items2 = (data2 or {}).get("items") or (data2 or {}).get("registros") or (data2 or {}).get("eventos") or []
                if not isinstance(items2, list):
                    items2 = []
                aud[tipo][f"id_referencia_{ref}"] = {
                    "http": c2,
                    "total_registros": total2,
                    "muestra": [
                        {
                            "id_evento": ev.get("id_evento") or ev.get("id"),
                            "id_referencia": ev.get("id_referencia"),
                            "timestamp_evento": ev.get("timestamp_evento") or ev.get("fecha_evento"),
                            "tipo_actor": ev.get("tipo_actor") or ev.get("actor"),
                            "id_sistema": ev.get("id_sistema"),
                        }
                        for ev in items2[:10] if isinstance(ev, dict)
                    ],
                }
                reg("GET", ruta_ref, c2, aud[tipo][f"id_referencia_{ref}"], f"aud_{tipo}_{ref}")
            reg("GET", ruta, c, {"total_registros": total, "muestra": muestra}, f"aud_{tipo}")
    else:
        aud["consultado"] = False
        aud["motivo"] = "Sin permiso auditoria_financiera R"
    informe["auditoria"] = aud

    # Evaluacion TC-51 / TC-52
    apta_51 = (
        cot6 is not None
        and cot6.get("estado") == "COTIZADO"
        and cot6.get("motivo_anulacion") in (None, "")
        and ACTIVO_51 in (cot6.get("activos_cotizados") or [])
        and cot6.get("estado_periodo") != "CERRADO"
        and isinstance(cot6.get("version"), int)
    )
    transicion_52 = None
    if cot7 is None:
        transicion_52 = "NO_ENCONTRADA"
    elif cot7.get("estado") == "VENCIDA":
        transicion_52 = "YA_OCURRIO"
    elif cot7.get("estado") == "COTIZADO":
        transicion_52 = "PENDIENTE_PROCESO_AUTOMATICO"
    else:
        transicion_52 = f"ESTADO_INESPERADO_{cot7.get('estado')}"

    evento_vencida_7 = (aud.get("COTIZACION_VENCIDA") or {}).get("id_referencia_7") or {}
    evidencia_52_suficiente = (
        transicion_52 == "YA_OCURRIO"
        and (evento_vencida_7.get("total_registros") or 0) >= 1
    )

    informe["evaluacion"] = {
        "tc51_cotizacion_6": {
            "apta_para_anulacion": apta_51,
            "estado": (cot6 or {}).get("estado"),
            "version": (cot6 or {}).get("version"),
            "activo_ok": ACTIVO_51 in ((cot6 or {}).get("activos_cotizados") or []),
            "sin_vencimiento": (cot6 or {}).get("fecha_vencimiento") is None,
        },
        "tc52_cotizacion_7": {
            "transicion_automatica": transicion_52,
            "estado": (cot7 or {}).get("estado"),
            "fecha_vencimiento": (cot7 or {}).get("fecha_vencimiento"),
            "version": (cot7 or {}).get("version"),
            "activo_ok": ACTIVO_52 in ((cot7 or {}).get("activos_cotizados") or []),
            "evento_COTIZACION_VENCIDA_ref_7": evento_vencida_7,
            "evidencia_automatica_suficiente": evidencia_52_suficiente,
            "accion": (
                "No reprocesar; verificar activo 1570 y dictaminar con evidencia de estado+evento"
                if transicion_52 == "YA_OCURRIO"
                else "No forzar; investigar documentalmente el proceso de fondo"
            ),
        },
    }

    motivo = (
        "TC-M06-G119 / TC-M06-51 — anulación controlada de cotización 6 "
        "(activo 1571). Motivo de prueba QA; pendiente autorización."
    )
    assert len(motivo) >= 20
    solicitud_51 = {
        "endpoint": f"POST /finanzas/cotizaciones/{COT_51}/anulacion",
        "headers": {
            "Authorization": "Bearer <token Contador>",
            "Content-Type": "application/json",
            "X-Zona-Horaria": ZONA,
        },
        "usuario_rol": f"{rol or 'Contador'} (permiso cotizaciones desactivar)",
        "body": {
            "version": (cot6 or {}).get("version"),
            "motivo_anulacion": motivo,
        },
        "segundo_intento": {
            "endpoint": f"POST /finanzas/cotizaciones/{COT_51}/anulacion",
            "body": {
                "version": ((cot6 or {}).get("version") or 0) + 1,
                "motivo_anulacion": motivo + " segundo intento",
            },
            "esperado": {"http": 422, "code": "COTIZACION_NO_MODIFICABLE"},
            "nota": "Usar version actualizada tras primera anulación; no ejecutar sin autorización",
        },
        "consultas_posteriores": [
            "GET /finanzas/cotizaciones (filtrar id 6)",
            "GET /finanzas/auditoria?tipo_evento=COTIZACION_ANULADA&id_referencia=6",
            "GET /finanzas/activos/1571",
        ],
        "ejecutado": False,
    }
    informe["solicitud_anulacion_preparada"] = solicitud_51

    informe["implementacion"] = {
        "anulacion": {
            "router": "POST /finanzas/cotizaciones/{id}/anulacion",
            "permiso": "cotizaciones D (desactivar)",
            "dto": "AnularCotizacionDTO: version>=1, motivo_anulacion min_length=20",
            "reglas": "Solo estado COTIZADO y periodo no CERRADO; pasa a ANULADA; evento COTIZACION_ANULADA; sin ruta de reactivación",
            "segundo_intento": "422 COTIZACION_NO_MODIFICABLE si estado != COTIZADO",
            "fuentes": [
                "m06_router.py anular_cotizacion",
                "m06_dto.py AnularCotizacionDTO",
                "modificar_cotizacion_use_case.py anular/_vigente",
            ],
        },
        "vencimiento_automatico": {
            "endpoint_publico": None,
            "proceso": "main.py _procesar_m06_periodicamente: ciclo 60s; una vez por día calendario UTC llama m06.modificar_cotizacion().vencer()",
            "criterio_sql": "estado=COTIZADO AND fecha_vencimiento < hoy AND periodo <> CERRADO",
            "evento": "COTIZACION_VENCIDA con id_sistema=M06_VENCIMIENTO_COTIZACIONES",
            "hoy": "hoy_usuario() en el caso de uso",
            "fuentes": [
                "main.py:_procesar_m06_periodicamente",
                "modificar_cotizacion_use_case.py:vencer",
                "cotizacion_repository.py:vencer",
            ],
            "no_ejecutar_manual": True,
        },
    }

    informe["dependencia_g118"] = {
        "descripcion": (
            "Cotización 6 / activo 1571 es el mismo activo aislado preparado para G118 (TC-M06-50). "
            "G118 sigue pendiente de autorización de POST de registro. Anular la cotización 6 "
            "alteraría el baseline comercial de 1571 y debe coordinarse: no ejecutar TC-M06-51 "
            "sin decisión expresa respecto a G118."
        ),
        "impacto_si_se_anula_6": "1571 perdería la cotización COTIZADO id 6; G118 podría necesitar otra cotización o reordenar ejecución",
        "g118_post_ejecutado": False,
    }

    riesgos = []
    if not apta_51:
        riesgos.append("TC-51: cotización 6 no apta para anulación en el estado actual")
    if transicion_52 == "PENDIENTE_PROCESO_AUTOMATICO":
        riesgos.append(
            "TC-52: cotización 7 sigue COTIZADO pese a fecha_vencimiento 2026-11-08 < hoy; "
            "posible fallo/retraso del proceso diario de fondo o timezone — no forzar"
        )
    if transicion_52 == "YA_OCURRIO" and not evidencia_52_suficiente:
        riesgos.append("TC-52: estado VENCIDA pero falta evento COTIZACION_VENCIDA con id_referencia=7")
    riesgos.append("Dependencia G118: no anular cotización 6 sin autorización coordinada")
    riesgos.append("No alterar cotizaciones 4/5 ni periodos 219/220")
    informe["riesgos"] = riesgos

    listo_51 = apta_51 and informe["permisos"].get("cotizaciones_D") or (4 in acciones_cot)
    # Fix boolean: Contador historically has D for cotizaciones
    listo_51 = bool(apta_51 and (informe["permisos"].get("cotizaciones_D") or 4 in acciones_cot))
    listo_52 = transicion_52 in ("YA_OCURRIO", "PENDIENTE_PROCESO_AUTOMATICO")

    informe["dictamen_preparacion"] = {
        "categoria": "PREPARADO_PENDIENTE_AUTORIZACION" if (cot6 or cot7) else "BLOQUEADO",
        "tc51_listo_para_anulacion": listo_51,
        "tc52_estado": transicion_52,
        "tc52_evidencia_automatica_suficiente": evidencia_52_suficiente,
        "escritura_ejecutada": False,
        "motivo": (
            "Baseline de solo lectura listo. Anulación 51 preparada (no enviada). "
            f"Vencimiento 52: {transicion_52}. Coordinar dependencia G118 antes de anular cotización 6."
        ),
        "requiere_autorizacion_expresa": [
            "POST anulación cotización 6 (TC-M06-51) — coordinar con G118",
            "Segundo intento de anulación (irreversibilidad)",
            "No ejecutar vencer() manual para TC-M06-52",
        ],
    }

    _guardar(informe)
    print("DICTAMEN", informe["dictamen_preparacion"]["categoria"])
    print("COT6", cot6)
    print("COT7", cot7)
    print("TC52", transicion_52, "evidencia", evidencia_52_suficiente)
    print("A1570", informe["activo_1570"])
    print("P220", informe["periodo_220"])
    print("P219", informe["periodo_219"])
    return 0


def _guardar(informe: dict) -> None:
    PREP.mkdir(parents=True, exist_ok=True)
    (PREP / "inspeccion_preparacion_G119.json").write_text(
        json.dumps(informe, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8"
    )
    (PREP / "solicitud_anulacion_preparada_G119.json").write_text(
        json.dumps(informe.get("solicitud_anulacion_preparada"), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (PREP / "informe_inspeccion_preparacion_G119.md").write_text(_md(informe), encoding="utf-8")
    (PREP / "plan_ejecucion_G119.md").write_text(_plan(informe), encoding="utf-8")
    (PREP / "analisis_hallazgos_preparacion_G119.md").write_text(_analisis(informe), encoding="utf-8")
    (PREP / "dependencias_y_bloqueos_G119.md").write_text(_deps(informe), encoding="utf-8")
    print("OK", PREP)


def _md(inf: dict) -> str:
    d = inf.get("dictamen_preparacion") or {}
    return "\n".join([
        "# TC-M06-G119 — Informe de inspección de preparación",
        "",
        f"- Antecedente: {inf.get('issue')}",
        f"- Generado: {inf.get('generado_en')}",
        f"- Dictamen: **{d.get('categoria')}**",
        f"- Escritura: **No**",
        "",
        d.get("motivo", ""),
        "",
        "## Cotización 6 (TC-M06-51)",
        f"```json\n{json.dumps(inf.get('cotizacion_6'), ensure_ascii=False, indent=2)}\n```",
        "",
        "## Cotización 7 (TC-M06-52)",
        f"```json\n{json.dumps(inf.get('cotizacion_7'), ensure_ascii=False, indent=2)}\n```",
        "",
        "## Evaluación",
        f"```json\n{json.dumps(inf.get('evaluacion'), ensure_ascii=False, indent=2)}\n```",
        "",
        "## Activo 1570",
        f"```json\n{json.dumps(inf.get('activo_1570'), ensure_ascii=False, indent=2)}\n```",
        "",
        "## Periodos",
        f"```json\n{json.dumps({'220': inf.get('periodo_220'), '219': inf.get('periodo_219')}, ensure_ascii=False, indent=2)}\n```",
        "",
        "## Auditoría (resumen)",
        f"```json\n{json.dumps({k: {'total': (v or {}).get('total_registros'), 'ref6': (v or {}).get('id_referencia_6'), 'ref7': (v or {}).get('id_referencia_7')} for k, v in (inf.get('auditoria') or {}).items() if isinstance(v, dict)}, ensure_ascii=False, indent=2)}\n```",
        "",
        "## Solicitud de anulación (NO enviada)",
        f"```json\n{json.dumps(inf.get('solicitud_anulacion_preparada'), ensure_ascii=False, indent=2)}\n```",
        "",
        "## Confirmación",
        "",
        "Sin POST de anulación. Sin ejecución manual de vencer(). Solo health, login y GET.",
        "",
    ]) + "\n"


def _plan(inf: dict) -> str:
    ev = inf.get("evaluacion") or {}
    return f"""# TC-M06-G119 — Plan de ejecución (pendiente de autorización)

## TC-M06-51 — Anulación (cotización 6)

1. Confirmar coordinación con G118 (activo 1571 / cotización 6).
2. Tras autorización expresa: `POST /finanzas/cotizaciones/6/anulacion` con body preparado.
3. Verificar estado `ANULADA`, motivo almacenado, evento `COTIZACION_ANULADA`.
4. Segundo intento (misma u otra version): esperar 422 `COTIZACION_NO_MODIFICABLE`.
5. Verificar activo 1571 sin cambio de estado/VR.

Estado preparación: apta={ev.get('tc51_cotizacion_6', {}).get('apta_para_anulacion')}

## TC-M06-52 — Vencimiento automático (cotización 7)

1. **No** llamar `vencer()` ni endpoints de proceso de fondo.
2. Transición observada: `{ev.get('tc52_cotizacion_7', {}).get('transicion_automatica')}`.
3. Si ya `VENCIDA`: dictaminar con estado + evento `COTIZACION_VENCIDA` + activo 1570 intacto.
4. Si sigue `COTIZADO`: documentar causa probable (proceso diario UTC en `main.py`) y esperar al proceso o decisión del responsable; no forzar.

## Restricciones

- No alterar cotizaciones 4/5.
- No cerrar 220 / no reabrir 219.
- No SQL. No modificar backend.
"""


def _analisis(inf: dict) -> str:
    return "\n".join([
        "# TC-M06-G119 — Análisis de hallazgos (preparación)",
        "",
        f"- Cotización 6: {json.dumps(inf.get('cotizacion_6'), ensure_ascii=False)}",
        f"- Cotización 7: {json.dumps(inf.get('cotizacion_7'), ensure_ascii=False)}",
        f"- Evaluación: {json.dumps(inf.get('evaluacion'), ensure_ascii=False)}",
        f"- Riesgos: {json.dumps(inf.get('riesgos'), ensure_ascii=False)}",
        "",
        "Implementación: anulación por POST con version+motivo; vencimiento solo por proceso de fondo diario en main.py.",
        "",
    ])


def _deps(inf: dict) -> str:
    return "\n".join([
        "# TC-M06-G119 — Dependencias y bloqueos",
        "",
        "## Dependencia G118",
        "",
        json.dumps(inf.get("dependencia_g118"), ensure_ascii=False, indent=2),
        "",
        "## Riesgos / bloqueos",
        "",
        *[f"- {r}" for r in (inf.get("riesgos") or [])],
        "",
        "## Dictamen",
        "",
        json.dumps(inf.get("dictamen_preparacion"), ensure_ascii=False, indent=2),
        "",
    ])


if __name__ == "__main__":
    raise SystemExit(main())
