#!/usr/bin/env python3
"""
Generador de artefactos oficiales (JSON + HTML) para TC-M05-G43.

HISTORIAL DE CAMBIOS:
| Fecha      | Autor                    | Cambio |
|------------|--------------------------|--------|
| 2026-11-07 | Equipo QA                | Version inicial de generacion de artefactos JSON y HTML. |
| 12/11/2026 | Juan Sebastian Gutierrez | Reintento 1: soporte --reintento, metricas reales desde trazas_http.jsonl/contexto_g43.json y PENDIENTE_DIAGNOSTICO. |
| 12/11/2026 | Juan Sebastian Gutierrez | C3: nombres reales de paso, fuente literal en checkpoints, NO_ENCONTRADO:<paso> y observaciones completas. |
| 13/11/2026 | Juan Sebastian Gutierrez | reintento INC-M05-358-G43 |
"""

from __future__ import annotations

import argparse
import html
import json
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path


def _cargar_trazas(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out: list[dict] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            pass
    return out


def _cargar_contexto(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _cargar_junit(xml_path: Path) -> dict[str, dict]:
    if not xml_path.exists():
        return {}
    tree = ET.parse(xml_path)
    root = tree.getroot()
    casos: dict[str, dict] = {}
    for tc in root.findall(".//testcase"):
        name = tc.attrib.get("name", "")
        time_s = float(tc.attrib.get("time", "0") or 0)
        failure = tc.find("failure")
        error = tc.find("error")
        skipped = tc.find("skipped")
        if failure is not None:
            estado = "FALLA"
            msg = (failure.attrib.get("message", "") or failure.text or "").strip()
        elif error is not None:
            estado = "FALLA"
            msg = (error.attrib.get("message", "") or error.text or "").strip()
        elif skipped is not None:
            estado = "FALLA"
            msg = f"SKIPPED: {(skipped.attrib.get('message', '') or '').strip()}"
        else:
            estado = "OK"
            msg = ""
        casos[name] = {
            "name": name,
            "time_s": round(time_s, 3),
            "estado": estado,
            "mensaje": msg,
        }
    return casos


def _trazas_por_paso(trazas: list[dict]) -> dict[str, list[dict]]:
    res: dict[str, list[dict]] = {}
    for t in trazas:
        paso = t.get("paso") or ""
        if paso:
            res.setdefault(paso, []).append(t)
    return res


def _buscar_traza(por_paso: dict[str, list[dict]], paso: str) -> dict | None:
    arr = por_paso.get(paso) or []
    return arr[-1] if arr else None


def _buscar_trazas_prefijo(por_paso: dict[str, list[dict]], prefijo: str) -> list[dict]:
    encontradas: list[dict] = []
    for k, arr in por_paso.items():
        if k.startswith(prefijo):
            encontradas.extend(arr)
    return encontradas


def _val_o_no_encontrado(val, paso: str) -> str:
    if val is None or val == "":
        return f"NO_ENCONTRADO:{paso}"
    return str(val)


def _extraer_eventos_nuevos_traza(por_paso: dict[str, list[dict]], prefijo_antes: str, prefijo_despues: str) -> list[dict]:
    t_antes = _buscar_traza(por_paso, prefijo_antes)
    max_antes = 0
    if t_antes and isinstance(t_antes.get("response_body"), dict):
        items_a = t_antes["response_body"].get("items") or []
        if items_a:
            max_antes = max(e.get("id_auditoria_suministro", 0) for e in items_a)
    desp_trazas = _buscar_trazas_prefijo(por_paso, prefijo_despues)
    vistos: dict[int, dict] = {}
    for t in desp_trazas:
        rb = t.get("response_body")
        if isinstance(rb, dict):
            for e in rb.get("items") or []:
                eid = e.get("id_auditoria_suministro")
                if eid is not None and eid > max_antes:
                    vistos[eid] = e
    return [vistos[k] for k in sorted(vistos.keys())]


def _valores_reales_paso(paso_id: str, por_paso: dict[str, list[dict]], ctx: dict) -> str:
    if paso_id == "T00":
        t_ini = _buscar_traza(por_paso, "T00_auditoria_inicial")
        t_me = _buscar_traza(por_paso, "T00_usuarios_me")
        t_act = _buscar_traza(por_paso, "T00_crear_activo_c")
        st_ini = t_ini.get("status_code") if t_ini else "NO_ENCONTRADO:T00_auditoria_inicial"
        st_me = t_me.get("status_code") if t_me else "NO_ENCONTRADO:T00_usuarios_me"
        st_act = t_act.get("status_code") if t_act else "NO_ENCONTRADO:T00_crear_activo_c"
        xreq = (t_act or {}).get("x_request_id") or "NO_ENCONTRADO:T00_crear_activo_c.x_request_id"
        return (
            f"T00_auditoria_inicial HTTP {st_ini} (total={_val_o_no_encontrado(ctx.get('auditoria_inicial_total'), 'contexto.auditoria_inicial_total')}, "
            f"ultimo_id={_val_o_no_encontrado(ctx.get('auditoria_inicial_ultimo_id'), 'contexto.auditoria_inicial_ultimo_id')}); "
            f"T00_usuarios_me HTTP {st_me} (id_usuario={_val_o_no_encontrado(ctx.get('id_usuario_ref'), 'contexto.id_usuario_ref')}); "
            f"T00_crear_activo_c HTTP {st_act} (id_activo_biologico={_val_o_no_encontrado(ctx.get('id_activo_c'), 'contexto.id_activo_c')}, "
            f"id_ciclo={_val_o_no_encontrado(ctx.get('id_ciclo_c'), 'contexto.id_ciclo_c')}, X-Request-Id={xreq})"
        )

    if paso_id == "B01":
        t_c = _buscar_traza(por_paso, "B01_consultar_historial")
        t_d = _buscar_trazas_prefijo(por_paso, "B01_auditoria_despues_p")
        st_c = t_c.get("status_code") if t_c else "NO_ENCONTRADO:B01_consultar_historial"
        st_d = t_d[-1].get("status_code") if t_d else "NO_ENCONTRADO:B01_auditoria_despues_p*"
        n_reg = len((t_c or {}).get("response_body", {}).get("items", [])) if (t_c and isinstance(t_c.get("response_body"), dict)) else "NO_ENCONTRADO:B01_consultar_historial.items"
        xreq = (t_c or {}).get("x_request_id") or "NO_ENCONTRADO:B01_consultar_historial.x_request_id"
        evs = _extraer_eventos_nuevos_traza(por_paso, "B01_auditoria_antes", "B01_auditoria_despues_p")
        ev_info = ", ".join(f"{e.get('id_auditoria_suministro')}:{e.get('tipo_operacion')}:{e.get('resultado')}" for e in evs) or "NO_ENCONTRADO:B01_eventos"
        lit = ((ctx.get("observaciones") or {}).get("datos_nuevos_literales") or {}).get("B01")
        if not lit and evs:
            lit = evs[-1].get("datos_nuevos")
        filtros_lit = json.dumps((lit or {}).get("filtros_aplicados"), ensure_ascii=False) if isinstance(lit, dict) else "NO_ENCONTRADO:B01.filtros_aplicados"
        tot_ret = (lit or {}).get("total_registros_retornados") if isinstance(lit, dict) else "NO_ENCONTRADO:B01.total_registros_retornados"
        return (
            f"B01_consultar_historial HTTP {st_c} (registros={n_reg}, X-Request-Id={xreq}); "
            f"B01_auditoria_despues_p* HTTP {st_d} (eventos=[{ev_info}], "
            f"total_registros_retornados={tot_ret}, filtros_aplicados={filtros_lit})"
        )

    if paso_id == "B02":
        t_c = _buscar_traza(por_paso, "B02_consulta_vacia")
        t_d = _buscar_trazas_prefijo(por_paso, "B02_auditoria_despues_p")
        st_c = t_c.get("status_code") if t_c else "NO_ENCONTRADO:B02_consulta_vacia"
        st_d = t_d[-1].get("status_code") if t_d else "NO_ENCONTRADO:B02_auditoria_despues_p*"
        n_reg = len((t_c or {}).get("response_body", {}).get("items", [])) if (t_c and isinstance(t_c.get("response_body"), dict)) else "NO_ENCONTRADO:B02_consulta_vacia.items"
        xreq = (t_c or {}).get("x_request_id") or "NO_ENCONTRADO:B02_consulta_vacia.x_request_id"
        evs = _extraer_eventos_nuevos_traza(por_paso, "B02_auditoria_antes", "B02_auditoria_despues_p")
        ev_info = ", ".join(f"{e.get('id_auditoria_suministro')}:{e.get('tipo_operacion')}:{e.get('resultado')}" for e in evs) or "NO_ENCONTRADO:B02_eventos"
        lit = ((ctx.get("observaciones") or {}).get("datos_nuevos_literales") or {}).get("B02")
        if not lit and evs:
            lit = evs[-1].get("datos_nuevos")
        filtros_lit = json.dumps((lit or {}).get("filtros_aplicados"), ensure_ascii=False) if isinstance(lit, dict) else "NO_ENCONTRADO:B02.filtros_aplicados"
        tot_ret = (lit or {}).get("total_registros_retornados") if isinstance(lit, dict) else "NO_ENCONTRADO:B02.total_registros_retornados"
        return (
            f"B02_consulta_vacia HTTP {st_c} (registros={n_reg}, X-Request-Id={xreq}); "
            f"B02_auditoria_despues_p* HTTP {st_d} (eventos=[{ev_info}], "
            f"total_registros_retornados={tot_ret}, filtros_aplicados={filtros_lit})"
        )

    if paso_id == "B03":
        partes = []
        for fmt, paso_exp in (("PDF", "B03_exportar_pdf"), ("EXCEL", "B03_exportar_excel")):
            t_exp = _buscar_traza(por_paso, paso_exp)
            t_aud = _buscar_trazas_prefijo(por_paso, f"B03_{fmt}_auditoria_despues_p")
            st_exp = t_exp.get("status_code") if t_exp else f"NO_ENCONTRADO:{paso_exp}"
            st_aud = t_aud[-1].get("status_code") if t_aud else f"NO_ENCONTRADO:B03_{fmt}_auditoria_despues_p*"
            xreq = (t_exp or {}).get("x_request_id") or f"NO_ENCONTRADO:{paso_exp}.x_request_id"
            evs = _extraer_eventos_nuevos_traza(por_paso, f"B03_{fmt}_auditoria_antes", f"B03_{fmt}_auditoria_despues_p")
            ev_info = ", ".join(f"{e.get('id_auditoria_suministro')}:{e.get('tipo_operacion')}:{e.get('resultado')}" for e in evs) or f"NO_ENCONTRADO:B03_{fmt}_eventos"
            lit = ((ctx.get("observaciones") or {}).get("datos_nuevos_literales") or {}).get(f"B03_{fmt}")
            if not lit and evs:
                lit = evs[-1].get("datos_nuevos")
            tot_ret = (lit or {}).get("total_registros_retornados") if isinstance(lit, dict) else f"NO_ENCONTRADO:B03_{fmt}.total_registros_retornados"
            filtros_lit = json.dumps((lit or {}).get("filtros_aplicados"), ensure_ascii=False) if isinstance(lit, dict) else f"NO_ENCONTRADO:B03_{fmt}.filtros_aplicados"
            partes.append(
                f"{paso_exp} HTTP {st_exp} (X-Request-Id={xreq}); audit HTTP {st_aud} "
                f"(eventos=[{ev_info}], total_registros_retornados={tot_ret}, filtros_aplicados={filtros_lit})"
            )
        return " | ".join(partes)

    if paso_id == "B04":
        p_post = (_buscar_traza(por_paso, "B04_post_intento") or {}).get("status_code", "NO_ENCONTRADO:B04_post_intento")
        p_put = (_buscar_traza(por_paso, "B04_put_intento") or {}).get("status_code", "NO_ENCONTRADO:B04_put_intento")
        p_patch = (_buscar_traza(por_paso, "B04_patch_intento") or {}).get("status_code", "NO_ENCONTRADO:B04_patch_intento")
        p_del = (_buscar_traza(por_paso, "B04_del_intento") or {}).get("status_code", "NO_ENCONTRADO:B04_del_intento")
        t_desp = _buscar_traza(por_paso, "B04_despues")
        n_desp = len((t_desp or {}).get("response_body", {}).get("items", [])) if (t_desp and isinstance(t_desp.get("response_body"), dict)) else "NO_ENCONTRADO:B04_despues.items"
        return f"POST={p_post}, PUT={p_put}, PATCH={p_patch}, DELETE={p_del} sobre /suministros/historial; B04_despues items={n_desp}"

    if paso_id == "A01":
        t_ok = _buscar_traza(por_paso, "A01_gestor_su_finca")
        t_put = _buscar_traza(por_paso, "A01_gestor_put")
        st_ok = t_ok.get("status_code") if t_ok else "NO_ENCONTRADO:A01_gestor_su_finca"
        st_put = t_put.get("status_code") if t_put else "NO_ENCONTRADO:A01_gestor_put"
        n_items = len((t_ok or {}).get("response_body", {}).get("items", [])) if (t_ok and isinstance(t_ok.get("response_body"), dict)) else "NO_ENCONTRADO:A01_gestor_su_finca.items"
        xreq = (t_ok or {}).get("x_request_id") or "NO_ENCONTRADO:A01_gestor_su_finca.x_request_id"
        return f"A01_gestor_su_finca HTTP {st_ok} (items={n_items}, X-Request-Id={xreq}); A01_gestor_put HTTP {st_put}"

    if paso_id == "A02":
        t_a2 = _buscar_traza(por_paso, "A02_gestor_finca_ajena")
        st = t_a2.get("status_code") if t_a2 else "NO_ENCONTRADO:A02_gestor_finca_ajena"
        err = t_a2.get("error_code") if t_a2 else "NO_ENCONTRADO:A02_gestor_finca_ajena.error_code"
        xreq = (t_a2 or {}).get("x_request_id") or "NO_ENCONTRADO:A02_gestor_finca_ajena.x_request_id"
        rb = (t_a2 or {}).get("response_body")
        keys = list(rb.keys()) if isinstance(rb, dict) else []
        msg = rb.get("message", "") if isinstance(rb, dict) else str(rb)
        return f"A02_gestor_finca_ajena HTTP {st} (error_code={err}, mensaje={msg!r}, claves={keys}, X-Request-Id={xreq})"

    if paso_id == "A02b":
        t_a2b = _buscar_traza(por_paso, "A02b_gestor_export_ajena")
        st = t_a2b.get("status_code") if t_a2b else "NO_ENCONTRADO:A02b_gestor_export_ajena"
        err = t_a2b.get("error_code") if t_a2b else "NO_ENCONTRADO:A02b_gestor_export_ajena.error_code"
        xreq = (t_a2b or {}).get("x_request_id") or "NO_ENCONTRADO:A02b_gestor_export_ajena.x_request_id"
        rb = (t_a2b or {}).get("response_body")
        keys = list(rb.keys()) if isinstance(rb, dict) else []
        msg = rb.get("message", "") if isinstance(rb, dict) else str(rb)
        return f"A02b_gestor_export_ajena HTTP {st} (error_code={err}, mensaje={msg!r}, claves={keys}, X-Request-Id={xreq})"

    if paso_id == "A03":
        a03_ctx = ctx.get("a03") or {}
        t_int = _buscar_traza(por_paso, "A03_intento_rechazado")
        st_int = a03_ctx.get("intento_http") or ((t_int or {}).get("status_code")) or "NO_ENCONTRADO:A03_intento_rechazado"
        err_int = a03_ctx.get("intento_error_code") or ((t_int or {}).get("error_code")) or "NO_ENCONTRADO:A03_intento_rechazado.error_code"
        xreq = a03_ctx.get("x_request_id") or ((t_int or {}).get("x_request_id")) or "NO_ENCONTRADO:A03_intento_rechazado.x_request_id"
        t_antes = _buscar_traza(por_paso, "A03_antes_audit_max_id")
        id_base_traza = None
        if t_antes and isinstance(t_antes.get("response_body"), dict):
            items_a = t_antes["response_body"].get("items") or []
            if items_a:
                id_base_traza = max(e.get("id_auditoria_suministro", 0) for e in items_a)
        id_base = a03_ctx.get("id_base") if "id_base" in a03_ctx else (id_base_traza if id_base_traza is not None else "NO_ENCONTRADO:A03_antes_audit_max_id")
        evs_ctx = a03_ctx.get("eventos_nuevos")
        if isinstance(evs_ctx, list):
            evs_det = ", ".join(f"{e.get('id')}:{e.get('accion')}:{e.get('resultado')}" for e in evs_ctx) or "[]"
            n_evs = len(evs_ctx)
        else:
            evs_tr = _extraer_eventos_nuevos_traza(por_paso, "A03_antes_audit_max_id", "A03_despues_audit_p")
            evs_det = ", ".join(f"{e.get('id_auditoria_suministro')}:{e.get('tipo_operacion')}:{e.get('resultado')}" for e in evs_tr) or "[]"
            n_evs = len(evs_tr) if _buscar_trazas_prefijo(por_paso, "A03_despues_audit_p") else "NO_ENCONTRADO:A03_despues_audit_p*"
        t_cierre = _buscar_traza(por_paso, "teardown_a03_admin")
        st_cierre = t_cierre.get("status_code") if t_cierre else "NO_ENCONTRADO:teardown_a03_admin"
        return (
            f"A03_intento_rechazado HTTP {st_int} (error_code={err_int}, X-Request-Id={xreq}); "
            f"id_base={id_base}, eventos_nuevos={n_evs} ({evs_det}), teardown_a03_admin HTTP {st_cierre}"
        )

    if paso_id == "A04":
        t_pre = _buscar_traza(por_paso, "A04_productor_precondicion_activo")
        t_p = _buscar_traza(por_paso, "A04_productor_su_finca")
        st_pre = t_pre.get("status_code") if t_pre else "NO_ENCONTRADO:A04_productor_precondicion_activo"
        st = t_p.get("status_code") if t_p else "NO_ENCONTRADO:A04_productor_su_finca"
        n_items = len((t_p or {}).get("response_body", {}).get("items", [])) if (t_p and isinstance(t_p.get("response_body"), dict)) else "NO_ENCONTRADO:A04_productor_su_finca.items"
        xreq = (t_p or {}).get("x_request_id") or "NO_ENCONTRADO:A04_productor_su_finca.x_request_id"
        return f"A04_productor_precondicion_activo HTTP {st_pre}; A04_productor_su_finca HTTP {st} (items={n_items}, X-Request-Id={xreq})"

    if paso_id == "T98":
        cerradas = ctx.get("corridas_cerradas") or {}
        if not cerradas:
            return "NO_ENCONTRADO:contexto.corridas_cerradas"
        resumen = ", ".join(f"{k}:{v.get('status_code')}" for k, v in cerradas.items())
        return f"Corridas cerradas con DELETE 200 Rollback exitoso ({resumen})"

    if paso_id == "T99":
        t_aud = _buscar_traza(por_paso, "T99_audit_inocuidad")
        t_act = _buscar_traza(por_paso, "T99_activo_c_404")
        t_his = _buscar_traza(por_paso, "T99_historial_c_404")
        t_td = _buscar_traza(por_paso, "teardown_t99")
        st_aud = t_aud.get("status_code") if t_aud else "NO_ENCONTRADO:T99_audit_inocuidad"
        st_act = t_act.get("status_code") if t_act else "NO_ENCONTRADO:T99_activo_c_404"
        st_his = t_his.get("status_code") if t_his else "NO_ENCONTRADO:T99_historial_c_404"
        st_td = t_td.get("status_code") if t_td else "NO_ENCONTRADO:teardown_t99"
        rb_t99 = (t_aud or {}).get("response_body") or {}
        tot_t99 = rb_t99.get("total", "NO_ENCONTRADO:T99_audit_inocuidad.total")
        items_t99 = rb_t99.get("items") or []
        max_id_t99 = max((e.get("id_auditoria_suministro", 0) for e in items_t99), default="NO_ENCONTRADO:T99_audit_inocuidad.max_id")
        max_id_t00 = ctx.get("auditoria_inicial_ultimo_id")
        if max_id_t00 is None:
            max_id_t00 = "NO_ENCONTRADO:contexto.auditoria_inicial_ultimo_id"
        return (
            f"T99_audit_inocuidad HTTP {st_aud} (total={tot_t99}, max_id={max_id_t99} vs T00={max_id_t00}), "
            f"T99_activo_c_404 HTTP {st_act}, T99_historial_c_404 HTTP {st_his}, teardown_t99 HTTP {st_td}"
        )

    return "NO_ENCONTRADO:paso"


def _resumen_obtenido(paso_id: str, junit_item: dict, por_paso: dict[str, list[dict]], ctx: dict) -> str:
    reales = _valores_reales_paso(paso_id, por_paso, ctx)
    msg = junit_item.get("mensaje", "")
    if junit_item.get("estado") == "FALLA":
        msg_1 = msg.splitlines()[0][:240] if msg else "Falla sin mensaje"
        return f"PENDIENTE_DIAGNOSTICO | {msg_1} | {reales}"
    return reales


def construir_json(
    ev_dir: Path,
    junit_path: Path,
    trazas_path: Path,
    reintento: int,
) -> dict:
    casos = _cargar_junit(junit_path)
    trazas = _cargar_trazas(trazas_path)
    por_paso = _trazas_por_paso(trazas)
    ctx = _cargar_contexto(ev_dir / "contexto_g43.json")

    definicion = [
        (
            "T00",
            "T00 Setup de activo C y línea base (Admin)",
            "test_00_setup_linea_base_y_activo_c",
            "Linea base de auditoria en T00, usuario autenticado y creacion de activo C + fase + 3 suministros en sandbox (HTTP 201)",
            "Testing Harness / Setup de linea base",
            False,
        ),
        (
            "B01",
            "B01 Auditoría de consulta con resultados (105 / 040)",
            "test_b01_consulta_con_resultados_auditoria",
            "HTTP 200 con 3 registros; exactamente 1 CONSULTA_HISTORIAL_EJECUTADA nuevo con id_usuario = /usuarios/me, id_activo_biologico = activo C, fecha_emision no nula, datos_nuevos.filtros_aplicados con cada filtro enviado y datos_nuevos.total_registros_retornados = 3",
            "RF-81 Fase 7, CA-8, Postcondicion 2",
            False,
        ),
        (
            "B02",
            "B02 Auditoría de consulta sin resultados (105 / 040, CU04 FA-01)",
            "test_b02_consulta_sin_resultados_auditoria",
            "HTTP 200 con 0 registros; exactamente 1 CONSULTA_HISTORIAL_EJECUTADA nuevo con las mismas verificaciones de B01 y datos_nuevos.total_registros_retornados = 0",
            "RF-81 Fase 7, CA-8, E1; caso TC-M05-105/040",
            False,
        ),
        (
            "B03",
            "B03 Auditoría de exportación síncrona PDF y Excel (105 / 040)",
            "test_b03_exportacion_sincrona_auditoria",
            "PDF y EXCEL: HTTP 200; por cada formato exactamente 1 EXPORTACION_HISTORIAL_GENERADA nuevo con id_usuario = /usuarios/me, id_activo_biologico = activo C, fecha_emision no nula, filtros_aplicados con cada filtro enviado y total_registros_retornados = 3",
            "RF-81 Fase 6 a, Fase 7, CA-8, Postcondicion 2",
            False,
        ),
        (
            "B04",
            "B04 Naturaleza de solo lectura e inmutabilidad (102 / 037)",
            "test_b04_solo_lectura_restr_4",
            "POST, PUT, PATCH, DELETE sobre /suministros/historial rechazados con 405 Method Not Allowed; historial inalterado",
            "RF-81 Restr. 4 / TC-M05-102 (037)",
            False,
        ),
        (
            "A01",
            "A01 Gestor de Granja consulta activo de su unidad (102 / 037)",
            "test_a01_gestor_granja_consulta_su_unidad",
            "HTTP 200 con items y resumen para activo 1042 en finca 464 asignada; PUT/DELETE rechazados (405)",
            "RF-81 Restr. 1 / CA-3 / TC-M05-102 (037)",
            False,
        ),
        (
            "A02",
            "A02 Rechazo a usuario sin la unidad del activo (102 / 037)",
            "test_a02_gestor_granja_rechazo_sin_unidad",
            "HTTP 403 con mensaje de E2 ('No tiene permisos para consultar el historial del activo 957. Verifique su rol y unidades productivas asignadas.') y sin registros ni resumen",
            "RF-81 Fase 1, E2, Restriccion 1, CA-3",
            False,
        ),
        (
            "A02b",
            "A02b Rechazo a exportación sin la unidad del activo (RF-81)",
            "test_a02b_gestor_granja_rechazo_exportacion_sin_unidad",
            "HTTP 403 con mensaje de E2 completo, sin generar archivo ni id_exportacion",
            "RF-81 Fase 1, E2, Restriccion 1",
            False,
        ),
        (
            "A04",
            "A04 [OBSERVACION] Productor consulta activo de su unidad",
            "test_a04_observacion_productor_consulta_su_unidad",
            "Productor consulta activo 957 de su unidad -> HTTP 200 con precondicion de visibilidad (HTTP 200)",
            "Observacion de interoperabilidad (fuera de spec RF-81)",
            True,
        ),
        (
            "T98",
            "T98 Cierre estricto de todas las corridas sandbox",
            "test_98_cierre_corridas",
            "Todas las corridas previas (t00, admin, gestor, productor) cerradas con DELETE /test-control/runs/{run_id} -> HTTP 200 ('Rollback exitoso')",
            "Testing Harness / Sandbox Protocol",
            False,
        ),
        (
            "T99",
            "T99 Inocuidad final en sandbox",
            "test_99_inocuidad_final",
            "Inocuidad en sandbox: total y max id de auditoria restaurados a T00; activo C y su historial retornan 404 y run t99 cierra con 200 Rollback exitoso",
            "Testing Harness / Sandbox Protocol",
            False,
        ),
    ]

    checkpoints: list[dict] = []
    ok_cnt = 0
    falla_cnt = 0
    total_eval = 0

    for paso_id, paso_label, fn_name, esperado, fuente, es_obs in definicion:
        item = casos.get(fn_name, {"estado": "FALLA", "mensaje": f"Test {fn_name} no encontrado en junitxml", "time_s": 0.0})
        estado = item["estado"]
        if not es_obs:
            total_eval += 1
            if estado == "OK":
                ok_cnt += 1
            else:
                falla_cnt += 1

        cp = {
            "paso": paso_label,
            "test_fn": fn_name,
            "esperado": esperado,
            "fuente": fuente,
            "obtenido": _resumen_obtenido(paso_id, item, por_paso, ctx),
            "estado": estado,
            "tiempo_s": item.get("time_s", 0.0),
        }
        if estado == "FALLA":
            cp["diagnostico"] = "PENDIENTE_DIAGNOSTICO"
        checkpoints.append(cp)

    veredicto = "APROBADO" if falla_cnt == 0 and total_eval == 10 else "RECHAZADO"
    repro_cmd = (
        f"powershell -ExecutionPolicy Bypass -File "
        f"\"tests/Test_Testing/Test_Modulo5/RF-81/TC-M05-G43/ejecutar_tc_m05_g43.ps1\""
        + (f" -Reintento {reintento}" if reintento > 0 else "")
    )

    obs_ctx = ctx.get("observaciones") or {}
    observaciones = {
        "obs_inexistente": obs_ctx.get("obs_inexistente"),
        "obs_auditoria_tras_403": obs_ctx.get("obs_auditoria_tras_403"),
        "obs_distincion_403_404": obs_ctx.get("obs_distincion_403_404"),
        "obs_pag": obs_ctx.get("obs_pag"),
        "obs_r8": obs_ctx.get("obs_r8") or [],
        "obs_hash": obs_ctx.get("obs_hash") or [],
        "obs_otros": obs_ctx.get("obs_otros") or [],
        "datos_nuevos_literales": obs_ctx.get("datos_nuevos_literales") or {},
    }

    return {
        "tc": "TC-M05-G43",
        "titulo": "RF-81 / RF-80 - Auditoria de consultas y exportaciones de historial de suministros",
        "reintento": reintento,
        "fecha_utc": datetime.now(timezone.utc).isoformat(),
        "staging": str(ev_dir).replace("\\", "/"),
        "repro": repro_cmd,
        "summary": {
            "total": total_eval,
            "ok": ok_cnt,
            "falla": falla_cnt,
            "veredicto": veredicto,
        },
        "checkpoints": checkpoints,
        "observaciones": observaciones,
        "runs_orden": ctx.get("runs_orden") or [],
        "corridas_cerradas": ctx.get("corridas_cerradas") or {},
        "a03": ctx.get("a03") or {},
        "total_trazas_http": len(trazas),
    }


def construir_html(payload: dict) -> str:
    summary = payload["summary"]
    json_blob = json.dumps(payload, ensure_ascii=False)
    json_blob_attr = html.escape(json_blob, quote=True)

    filas = []
    for cp in payload["checkpoints"]:
        badge_cls = "ok" if cp["estado"] == "OK" else "fail"
        filas.append(
            "<tr>"
            f"<td><strong>{html.escape(cp['paso'])}</strong></td>"
            f"<td><span class='badge {badge_cls}'>{html.escape(cp['estado'])}</span></td>"
            f"<td>{html.escape(cp['esperado'])}<br/><small><em>Fuente: {html.escape(cp['fuente'])}</em></small></td>"
            f"<td>{html.escape(cp['obtenido'])}</td>"
            f"<td>{cp['tiempo_s']}s</td>"
            "</tr>"
        )

    obs_pretty = html.escape(json.dumps(payload.get("observaciones") or {}, ensure_ascii=False, indent=2))

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8" />
  <title>{html.escape(payload['tc'])} - Reporte Ejecucion</title>
  <style>
    body {{ font-family: system-ui, -apple-system, sans-serif; margin: 24px; color: #1f2937; }}
    .meta {{ background: #f3f4f6; padding: 12px 16px; border-radius: 8px; margin-bottom: 16px; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 12px; }}
    th, td {{ border: 1px solid #d1d5db; padding: 8px 10px; text-align: left; vertical-align: top; font-size: 13px; }}
    th {{ background: #f9fafb; }}
    .badge {{ padding: 2px 8px; border-radius: 12px; font-weight: 600; font-size: 12px; }}
    .ok {{ background: #dcfce7; color: #166534; }}
    .fail {{ background: #fee2e2; color: #991b1b; }}
    .obs {{ background: #fef3c7; color: #92400e; }}
    pre {{ background: #f9fafb; padding: 12px; border: 1px solid #e5e7eb; border-radius: 6px; font-size: 12px; overflow-x: auto; }}
  </style>
</head>
<body>
  <div id="json-root" data-jsonblob="{json_blob_attr}"></div>
  <h1>{html.escape(payload['tc'])} - {html.escape(payload['titulo'])}</h1>
  <div class="meta">
    <div><strong>Veredicto:</strong> {html.escape(summary['veredicto'])} ({summary['ok']}/{summary['total']} OK, {summary['falla']} FALLA)</div>
    <div><strong>Reintento:</strong> {payload['reintento']} | <strong>Fecha UTC:</strong> {html.escape(payload['fecha_utc'])}</div>
    <div><strong>Repro:</strong> <code>{html.escape(payload['repro'])}</code></div>
  </div>
  <table>
    <thead>
      <tr><th>Paso</th><th>Estado</th><th>Esperado / Fuente</th><th>Obtenido</th><th>Tiempo</th></tr>
    </thead>
    <tbody>
      {''.join(filas)}
    </tbody>
  </table>
  <h2>Observaciones</h2>
  <pre>{obs_pretty}</pre>
  <script id="data-jsonblob" type="application/json">{json_blob}</script>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Genera JSON y HTML de resultados para TC-M05-G43.")
    parser.add_argument("--evidence-dir", required=True, help="Directorio de evidencias del run")
    parser.add_argument("--junit", default=None, help="Ruta opcional al XML de pytest")
    parser.add_argument("--trazas", default=None, help="Ruta opcional a trazas_http.jsonl")
    parser.add_argument("--reintento", type=int, default=0, help="Numero de reintento (0 = corrida inicial)")
    args = parser.parse_args()

    ev_dir = Path(args.evidence_dir).resolve()
    suf = f"_reintento{args.reintento}" if args.reintento > 0 else ""

    junit_path = Path(args.junit) if args.junit else (ev_dir / f"pytest_TC-M05-G43{suf}.xml")
    trazas_path = Path(args.trazas) if args.trazas else (ev_dir / "trazas_http.jsonl")

    payload = construir_json(ev_dir, junit_path, trazas_path, args.reintento)

    json_out = ev_dir / f"resultado_TC-M05-G43{suf}.json"
    html_out = ev_dir / f"resultado_TC-M05-G43{suf}.html"

    json_out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    html_out.write_text(construir_html(payload), encoding="utf-8")

    print(f"Artefactos generados en {ev_dir}: {json_out.name}, {html_out.name} | Veredicto: {payload['summary']['veredicto']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
