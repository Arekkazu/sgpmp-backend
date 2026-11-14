# | Fecha      | Nombre                   | Que se hizo                                                            |
# |------------|--------------------------|------------------------------------------------------------------------|
# | 2026-11-11 | Juan Sebastian Gutierrez | Script de observacion Fase 1 TC-M05-G37 (INC-M05-275-G37 / RF-80 v2.0) |
"""Observacion controlada en TEST para Fase 1 de reevaluacion de TC-M05-G37 (RF-80 v2.0).

Ejecuta unicamente lecturas y acciones de observacion dentro de corridas sandbox
estrictamente secuenciales (inobase -> main -> inofin), con cierre garantizado
por DELETE /test-control/runs/{run_id} incluso ante fallos.
No imprime ni persiste credenciales ni tokens JWT.
"""
from __future__ import annotations

import json
import os
import re
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests
from dotenv import dotenv_values

ZONA_USUARIO = timezone(timedelta(hours=-5))
NOMBRE_ZONA = "America/Bogota"
TIMEOUT_S = 30
ACTIVOS_PROHIBIDOS = {930, 900, 901, 825}


def _repo_root() -> Path:
    cur = Path(__file__).resolve().parent
    while cur != cur.parent:
        if (cur / ".env.test").exists():
            return cur
        cur = cur.parent
    raise FileNotFoundError("No se encontro .env.test")


def _cargar_env(repo: Path) -> dict[str, str]:
    env_path = repo / ".env.test"
    raw = dotenv_values(env_path)
    return {k: str(v) for k, v in raw.items() if v is not None}


def _secretos(env: dict[str, str]) -> list[str]:
    vals: list[str] = []
    for k, v in env.items():
        ku = k.upper()
        if any(p in ku for p in ("PASS", "CLAVE", "SECRET", "EMAIL")) and v:
            vals.append(v)
            if len(v) >= 20:
                vals.append(v[-20:])
    return vals


def sanitizar(obj: Any, extra: tuple[str, ...], secrets: list[str]) -> Any:
    if isinstance(obj, dict):
        return {
            k: (
                "***REDACTED***"
                if k.lower() in ("contrasena", "password", "token", "access_token", "authorization")
                else sanitizar(v, extra, secrets)
            )
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [sanitizar(x, extra, secrets) for x in obj]
    if isinstance(obj, str):
        txt = obj
        for s in [*secrets, *extra]:
            if s and len(s) > 3:
                txt = txt.replace(s, "***REDACTED***")
        jwt_prefix = "ey" + "J"
        if jwt_prefix in txt:
            txt = re.sub(jwt_prefix + r"[a-zA-Z0-9_\-\.]+", "***REDACTED_JWT***", txt)
        return txt
    return obj


class SandboxClient:
    def __init__(self, prefix: str, env: dict[str, str]) -> None:
        self.run_id = f"{prefix}-{uuid.uuid4().hex[:8]}"
        self.base_url = env["TEST_BASE_URL"].rstrip("/")
        self.sandbox_secret = env["TEST_SANDBOX_SECRET"]
        self.secrets = _secretos(env)
        self.token: str | None = None
        self.logged_in = False
        self.closed = False
        self.session = requests.Session()
        self.session.headers.update({
            "X-Test-Run-Id": self.run_id,
            "X-Sandbox-Secret": self.sandbox_secret,
            "X-Zona-Horaria": NOMBRE_ZONA,
        })

    def _safe(self, obj: Any) -> Any:
        extra = (self.token,) if self.token else ()
        return sanitizar(obj, extra, self.secrets)

    def req(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: Any = None,
        with_auth: bool = True,
    ) -> dict[str, Any]:
        headers: dict[str, str] = {}
        if with_auth and self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        t0 = time.perf_counter()
        resp = self.session.request(
            method,
            f"{self.base_url}{path}",
            params=params,
            json=json_body,
            headers=headers,
            timeout=TIMEOUT_S,
        )
        elapsed = round(time.perf_counter() - t0, 3)
        try:
            body = resp.json()
        except Exception:
            body = resp.text[:400]
        return {
            "method": method,
            "path": path,
            "status_code": resp.status_code,
            "x_request_id": resp.headers.get("X-Request-Id"),
            "elapsed_s": elapsed,
            "body": self._safe(body),
            "raw_body": body if resp.status_code < 300 and path != "/sesiones/" else None,
        }

    def login_admin(self, env: dict[str, str]) -> dict[str, Any]:
        assert not self.logged_in, "Solo un login por run_id"
        self.logged_in = True
        r = self.session.post(
            f"{self.base_url}/sesiones/",
            json={
                "correo_electronico": env["TEST_ADMIN_EMAIL"],
                "contrasena": env["TEST_ADMIN_PASSWORD"],
            },
            timeout=TIMEOUT_S,
        )
        data = r.json()
        assert r.status_code == 200, f"Login fallo: HTTP {r.status_code}"
        tok = data.get("token") or data.get("access_token")
        assert tok, "Login sin token"
        self.token = tok
        return {
            "status_code": r.status_code,
            "x_request_id": r.headers.get("X-Request-Id"),
        }

    def close(self) -> dict[str, Any]:
        if self.closed:
            return {"already_closed": True}
        self.closed = True
        try:
            r = self.session.delete(
                f"{self.base_url}/test-control/runs/{self.run_id}",
                timeout=TIMEOUT_S,
            )
            try:
                body = self._safe(r.json())
            except Exception:
                body = self._safe(r.text[:300])
            return {
                "run_id": self.run_id,
                "status_code": r.status_code,
                "x_request_id": r.headers.get("X-Request-Id"),
                "body": body,
            }
        finally:
            self.session.close()


def snap_auditoria(cli: SandboxClient) -> dict[str, Any]:
    r1 = cli.req("GET", "/suministros/auditoria", params={"pagina": 1, "registros_por_pagina": 1})
    r5 = cli.req("GET", "/suministros/auditoria", params={"pagina": 1, "registros_por_pagina": 5})
    assert r1["status_code"] == 200 and r5["status_code"] == 200, f"Error snapshot: {r1}"
    b1 = r1["raw_body"]
    b5 = r5["raw_body"]
    items1 = b1.get("items") or []
    ultimo_id = items1[0]["id_auditoria_suministro"] if items1 else 0
    return {
        "total": b1["total"],
        "total_rpp5": b5["total"],
        "rpp5_len": len(b5.get("items") or []),
        "ultimo_id": ultimo_id,
        "x_request_id": r1["x_request_id"],
    }


def eventos_nuevos(cli: SandboxClient, ultimo_id_previo: int, limite: int = 20) -> list[dict[str, Any]]:
    r = cli.req("GET", "/suministros/auditoria", params={"pagina": 1, "registros_por_pagina": limite})
    assert r["status_code"] == 200, f"Error listando auditoria: {r}"
    items = r["raw_body"].get("items") or []
    nuevos = [it for it in items if int(it["id_auditoria_suministro"]) > ultimo_id_previo]
    nuevos.sort(key=lambda x: x["id_auditoria_suministro"])
    return nuevos


def run_inobase(env: dict[str, str]) -> dict[str, Any]:
    cli = SandboxClient("tc-m05-g37-inobase", env)
    try:
        login = cli.login_admin(env)
        health = cli.req("GET", "/health")
        snap = snap_auditoria(cli)
    finally:
        teardown = cli.close()
    assert teardown["status_code"] == 200, f"Rollback base fallo: {teardown}"
    return {"run_id": cli.run_id, "login": login, "health": health, "snapshot": snap, "teardown": teardown}


def run_principal(env: dict[str, str]) -> dict[str, Any]:
    cli = SandboxClient("tc-m05-g37-f1-main", env)
    out: dict[str, Any] = {"run_id": cli.run_id}
    try:
        out["login"] = cli.login_admin(env)
        hoy = datetime.now(ZONA_USUARIO).date()
        hoy_str = hoy.isoformat()
        fecha_ciclo = (hoy - timedelta(days=15)).isoformat()

        # Crear activo POBLACIONAL sin fase abierta
        r_act = cli.req(
            "POST",
            "/activos-biologicos",
            json_body={
                "tipo_activo": "POBLACIONAL",
                "id_especie": 1,
                "id_infraestructura": 2,
                "identificador_unico": f"QA-G37-F1-{uuid.uuid4().hex[:8]}",
                "cantidad_inicial": 60,
                "fecha_ingreso": fecha_ciclo,
                "fecha_inicio_ciclo": fecha_ciclo,
                "origen_financiero": "nacimiento",
                "peso_actual": 22.0,
            },
        )
        assert r_act["status_code"] == 201, f"Fallo crear activo: {r_act}"
        id_activo = r_act["raw_body"]["id_activo_biologico"]
        assert id_activo not in ACTIVOS_PROHIBIDOS, f"Activo prohibido generado: {id_activo}"
        out["activo_creado"] = {
            "id_activo_biologico": id_activo,
            "status_code": r_act["status_code"],
            "x_request_id": r_act["x_request_id"],
        }

        # 3a) Rechazo sin fase abierta
        snap_before_3a = snap_auditoria(cli)
        uuid_3a = str(uuid.uuid4())
        payload_3a = {
            "id_activo_biologico": id_activo,
            "tipo_suministro": "SERVICIO_VETERINARIO",
            "cantidad": 1.0,
            "unidad_medida": "servicio",
            "precio_unitario": 40000.0,
            "fecha_aplicacion": hoy_str,
            "justificacion_precio": "Tarifa estandar vigente para validacion de rechazo",
            "id_idempotencia": uuid_3a,
        }
        t0 = time.perf_counter()
        r_3a = cli.req("POST", "/suministros/costeo-directo", json_body=payload_3a)

        # 3b) Poll 0, 1, 2 s y capturar eventos
        poll_samples = []
        evs_3a: list[dict[str, Any]] = []
        for idx in range(3):
            if idx > 0:
                time.sleep(1.0)
            lat = round(time.perf_counter() - t0, 3)
            r_list = cli.req("GET", "/suministros/auditoria", params={"pagina": 1, "registros_por_pagina": 20})
            items_list = (r_list["raw_body"] or {}).get("items") or []
            nuevos = [it for it in items_list if int(it["id_auditoria_suministro"]) > snap_before_3a["ultimo_id"]]
            nuevos.sort(key=lambda x: x["id_auditoria_suministro"])
            poll_samples.append({
                "segundo": idx,
                "latencia_cliente_s": lat,
                "total": (r_list["raw_body"] or {}).get("total"),
                "nuevos_ids": [x["id_auditoria_suministro"] for x in nuevos],
                "x_request_id": r_list["x_request_id"],
            })
            if idx == 0 or not evs_3a:
                evs_3a = nuevos

        snap_after_3a = snap_auditoria(cli)
        out["paso_3a"] = {
            "snap_before": snap_before_3a,
            "uuid_solicitud": uuid_3a,
            "response": {
                "status_code": r_3a["status_code"],
                "x_request_id": r_3a["x_request_id"],
                "elapsed_s": r_3a["elapsed_s"],
                "body": r_3a["body"],
            },
            "snap_after": snap_after_3a,
        }
        out["paso_3b"] = {
            "polls": poll_samples,
            "eventos_nuevos": cli._safe(evs_3a),
        }

        evs_rechazo = [e for e in evs_3a if e.get("resultado") in ("RECHAZADO", "FALLIDO")]
        if not evs_rechazo:
            out["gate_ok"] = False
            out["gate_msg"] = (
                f"corrección no desplegada en TEST (total_antes={snap_before_3a['total']}, "
                f"total_despues={snap_after_3a['total']}, X-Request-Id_3a={r_3a['x_request_id']})"
            )
            return out

        out["gate_ok"] = True
        ev_r = evs_rechazo[0]
        id_ev = ev_r["id_auditoria_suministro"]

        # 3c) Detalle /{id} vs lista, filtros y /test-control/query
        r_det = cli.req("GET", f"/suministros/auditoria/{id_ev}")
        det_body = r_det["raw_body"] or {}
        diffs_det = {
            k: {"lista": ev_r.get(k), "detalle": det_body.get(k)}
            for k in set(ev_r.keys()) | set(det_body.keys())
            if ev_r.get(k) != det_body.get(k)
        }

        now_utc = datetime.now(timezone.utc)
        fecha_desde = (now_utc - timedelta(minutes=10)).isoformat()
        fecha_hasta = (now_utc + timedelta(minutes=10)).isoformat()
        filtros_tests = {
            "por_activo": {"id_activo_biologico": id_activo},
            "por_tipo": {"tipo_operacion": ev_r["tipo_operacion"]},
            "por_resultado": {"resultado": ev_r["resultado"]},
            "por_clasificacion": {"clasificacion_registro": ev_r["clasificacion_registro"]},
            "por_fechas": {"fecha_desde": fecha_desde, "fecha_hasta": fecha_hasta},
            "combinado": {
                "id_activo_biologico": id_activo,
                "tipo_operacion": ev_r["tipo_operacion"],
                "resultado": ev_r["resultado"],
                "fecha_desde": fecha_desde,
                "fecha_hasta": fecha_hasta,
            },
        }
        filtros_res = {}
        for fname, fparams in filtros_tests.items():
            rf = cli.req("GET", "/suministros/auditoria", params={**fparams, "registros_por_pagina": 20})
            ids_f = [x["id_auditoria_suministro"] for x in ((rf["raw_body"] or {}).get("items") or [])]
            filtros_res[fname] = {
                "status_code": rf["status_code"],
                "x_request_id": rf["x_request_id"],
                "total": (rf["raw_body"] or {}).get("total"),
                "encontrado": id_ev in ids_f,
            }

        sql_q = (
            "SELECT id_auditoria_suministro, tipo_operacion, resultado, "
            "clasificacion_registro, retencion_aplicable, registro_incompleto "
            f"FROM modulo5.auditorias_suministros WHERE id_auditoria_suministro = {id_ev}"
        )
        r_tcq = cli.req("POST", "/test-control/query", json_body={"query": sql_q})
        out["paso_3c"] = {
            "detalle": {
                "status_code": r_det["status_code"],
                "x_request_id": r_det["x_request_id"],
                "diffs_lista_vs_detalle": cli._safe(diffs_det),
            },
            "filtros": filtros_res,
            "test_control_query": {
                "sql": sql_q,
                "status_code": r_tcq["status_code"],
                "x_request_id": r_tcq["x_request_id"],
                "body": r_tcq["body"],
            },
        }

        # 3d) Sin efectos parciales tras el rechazo
        r_acum_3d = cli.req("GET", f"/suministros/costeo-directo/acumulado/activo/{id_activo}")
        snap_before_hist_3d = snap_auditoria(cli)
        r_hist_3d = cli.req("GET", "/suministros/historial", params={"id_activo_biologico": id_activo})
        snap_after_hist_3d = snap_auditoria(cli)
        out["paso_3d"] = {
            "acumulado_activo": {
                "status_code": r_acum_3d["status_code"],
                "x_request_id": r_acum_3d["x_request_id"],
                "body": r_acum_3d["body"],
            },
            "historial_activo": {
                "status_code": r_hist_3d["status_code"],
                "x_request_id": r_hist_3d["x_request_id"],
                "items_count": len((r_hist_3d["raw_body"] or {}).get("items") or []),
                "resumen": (r_hist_3d["raw_body"] or {}).get("resumen"),
            },
            "auditoria_por_consulta_3d": {
                "before": snap_before_hist_3d,
                "after": snap_after_hist_3d,
            },
            "outbox": "no observable por la API",
        }

        # 3e) Repetir exactamente el mismo rechazo con nuevo id_idempotencia
        snap_before_3e = snap_auditoria(cli)
        uuid_3e = str(uuid.uuid4())
        payload_3e = {**payload_3a, "id_idempotencia": uuid_3e}
        r_3e = cli.req("POST", "/suministros/costeo-directo", json_body=payload_3e)
        evs_3e = eventos_nuevos(cli, snap_before_3e["ultimo_id"])
        snap_after_3e = snap_auditoria(cli)
        out["paso_3e"] = {
            "uuid_solicitud": uuid_3e,
            "snap_before": snap_before_3e,
            "response": {
                "status_code": r_3e["status_code"],
                "x_request_id": r_3e["x_request_id"],
                "body": r_3e["body"],
            },
            "nuevos_eventos_count": len(evs_3e),
            "nuevos_eventos": cli._safe(evs_3e),
            "snap_after": snap_after_3e,
        }

        # 3f Part 1) Abrir fase, registro valido RF-78 y consulta historial RF-81
        r_fase = cli.req(
            "POST",
            f"/activos-biologicos/{id_activo}/fases",
            json_body={"id_ciclo_productiva": 1, "motivo_cambio": "Apertura fase QA G37 F1"},
        )
        assert r_fase["status_code"] in (200, 201), f"Fallo apertura fase: {r_fase}"
        id_fase = r_fase["raw_body"]["id_gestion_fases"]

        snap_before_rf78 = snap_auditoria(cli)
        r_rf78 = cli.req(
            "POST",
            "/suministros/costeo-directo",
            json_body={**payload_3a, "id_idempotencia": str(uuid.uuid4())},
        )
        assert r_rf78["status_code"] == 200, f"Fallo RF-78 positivo: {r_rf78}"
        evs_rf78 = eventos_nuevos(cli, snap_before_rf78["ultimo_id"])
        snap_after_rf78 = snap_auditoria(cli)

        snap_before_rf81 = snap_auditoria(cli)
        r_rf81 = cli.req("GET", "/suministros/historial", params={"id_activo_biologico": id_activo})
        assert r_rf81["status_code"] == 200, f"Fallo RF-81 positivo: {r_rf81}"
        evs_rf81 = eventos_nuevos(cli, snap_before_rf81["ultimo_id"])
        snap_after_rf81 = snap_auditoria(cli)

        # 3g) Payload invalido (422 negocio y 400/422 esquema) antes de cerrar ciclo
        snap_before_3g1 = snap_auditoria(cli)
        r_3g_neg = cli.req(
            "POST",
            "/suministros/costeo-directo",
            json_body={**payload_3a, "cantidad": -1, "id_idempotencia": str(uuid.uuid4())},
        )
        evs_3g_neg = eventos_nuevos(cli, snap_before_3g1["ultimo_id"])
        snap_after_3g1 = snap_auditoria(cli)

        snap_before_3g2 = snap_auditoria(cli)
        r_3g_pyd = cli.req(
            "POST",
            "/suministros/costeo-directo",
            json_body={"id_activo_biologico": id_activo, "tipo_suministro": "", "id_idempotencia": "no-uuid"},
        )
        evs_3g_pyd = eventos_nuevos(cli, snap_before_3g2["ultimo_id"])
        snap_after_3g2 = snap_auditoria(cli)

        out["paso_3g"] = {
            "negocio_cantidad_negativa": {
                "snap_before": snap_before_3g1,
                "status_code": r_3g_neg["status_code"],
                "x_request_id": r_3g_neg["x_request_id"],
                "body": r_3g_neg["body"],
                "nuevos_eventos_count": len(evs_3g_neg),
                "nuevos_eventos": cli._safe(evs_3g_neg),
                "snap_after": snap_after_3g1,
            },
            "esquema_invalido": {
                "snap_before": snap_before_3g2,
                "status_code": r_3g_pyd["status_code"],
                "x_request_id": r_3g_pyd["x_request_id"],
                "body": r_3g_pyd["body"],
                "nuevos_eventos_count": len(evs_3g_pyd),
                "nuevos_eventos": cli._safe(evs_3g_pyd),
                "snap_after": snap_after_3g2,
            },
        }

        # 3h Part 1) Rechazos de negocio RF-81 y RF-79 (ciclo activo)
        snap_b_rf81_f = snap_auditoria(cli)
        r_rf81_filtros = cli.req(
            "GET",
            "/suministros/historial",
            params={
                "id_activo_biologico": id_activo,
                "fecha_inicio_filtro": hoy_str,
                "fecha_fin_filtro": (hoy - timedelta(days=5)).isoformat(),
            },
        )
        evs_rf81_f = eventos_nuevos(cli, snap_b_rf81_f["ultimo_id"])

        snap_b_rf81_404 = snap_auditoria(cli)
        r_rf81_404 = cli.req("GET", "/suministros/historial", params={"id_activo_biologico": 999999999})
        evs_rf81_404 = eventos_nuevos(cli, snap_b_rf81_404["ultimo_id"])

        snap_b_rf79_act = snap_auditoria(cli)
        r_rf79_act = cli.req("POST", f"/suministros/nic41/ciclo/{id_fase}/consolidar")
        evs_rf79_act = eventos_nuevos(cli, snap_b_rf79_act["ultimo_id"])

        # 3f Part 2) Cierre de ciclo (RF-79 consolidacion) y consulta versiones
        snap_before_cierre = snap_auditoria(cli)
        r_cierre = cli.req(
            "POST",
            f"/activos-biologicos/{id_activo}/cierre",
            json_body={
                "fecha_cierre": hoy_str,
                "motivo_cierre": "finalizacion_lote",
                "descripcion_cierre": "Cierre QA G37 F1 para observar consolidacion NIC41",
            },
        )
        assert r_cierre["status_code"] == 200, f"Fallo cierre activo: {r_cierre}"
        evs_cierre = eventos_nuevos(cli, snap_before_cierre["ultimo_id"])
        snap_after_cierre = snap_auditoria(cli)

        r_vers = cli.req("GET", f"/suministros/nic41/ciclo/{id_fase}/versiones")
        versiones = (r_vers["raw_body"] or {}).get("versiones") or []
        id_provision = versiones[-1]["id_provision"] if versiones else None

        # 3h Part 2) Rechazo RF-79 provision inexistente
        snap_b_rf79_404 = snap_auditoria(cli)
        r_rf79_404 = cli.req(
            "POST",
            "/suministros/nic41/999999999/correccion",
            json_body={"motivo_correccion": "Motivo QA de rechazo por provision inexistente"},
        )
        evs_rf79_404 = eventos_nuevos(cli, snap_b_rf79_404["ultimo_id"])

        def _resumen_evs(lista: list[dict[str, Any]]) -> list[dict[str, Any]]:
            return [
                {
                    "id_auditoria_suministro": e.get("id_auditoria_suministro"),
                    "tipo_operacion": e.get("tipo_operacion"),
                    "resultado": e.get("resultado"),
                    "clasificacion_registro": e.get("clasificacion_registro"),
                    "retencion_aplicable": e.get("retencion_aplicable"),
                    "registro_incompleto": e.get("registro_incompleto"),
                    "detalle_causa": e.get("detalle_causa"),
                }
                for e in lista
            ]

        out["paso_3f"] = {
            "id_gestion_fases": id_fase,
            "id_registro_suministro": (r_rf78["raw_body"] or {}).get("registro", {}).get("id_registro_suministro"),
            "id_provision": id_provision,
            "rf78_positivo": {
                "status_code": r_rf78["status_code"],
                "x_request_id": r_rf78["x_request_id"],
                "snap_before": snap_before_rf78,
                "snap_after": snap_after_rf78,
                "eventos": _resumen_evs(evs_rf78),
            },
            "rf81_positivo": {
                "status_code": r_rf81["status_code"],
                "x_request_id": r_rf81["x_request_id"],
                "snap_before": snap_before_rf81,
                "snap_after": snap_after_rf81,
                "eventos": _resumen_evs(evs_rf81),
            },
            "rf79_cierre": {
                "status_code": r_cierre["status_code"],
                "x_request_id": r_cierre["x_request_id"],
                "snap_before": snap_before_cierre,
                "snap_after": snap_after_cierre,
                "eventos": _resumen_evs(evs_cierre),
            },
        }
        out["paso_3h"] = {
            "rf81_filtros_invalidos": {
                "status_code": r_rf81_filtros["status_code"],
                "x_request_id": r_rf81_filtros["x_request_id"],
                "body": r_rf81_filtros["body"],
                "nuevos_eventos_count": len(evs_rf81_f),
            },
            "rf81_activo_inexistente": {
                "status_code": r_rf81_404["status_code"],
                "x_request_id": r_rf81_404["x_request_id"],
                "body": r_rf81_404["body"],
                "nuevos_eventos_count": len(evs_rf81_404),
            },
            "rf79_ciclo_activo": {
                "status_code": r_rf79_act["status_code"],
                "x_request_id": r_rf79_act["x_request_id"],
                "body": r_rf79_act["body"],
                "nuevos_eventos_count": len(evs_rf79_act),
            },
            "rf79_provision_inexistente": {
                "status_code": r_rf79_404["status_code"],
                "x_request_id": r_rf79_404["x_request_id"],
                "body": r_rf79_404["body"],
                "nuevos_eventos_count": len(evs_rf79_404),
            },
        }
        return out
    finally:
        out["teardown"] = cli.close()


def run_inofin(env: dict[str, str], id_activo: int, id_provision: int | None) -> dict[str, Any]:
    cli = SandboxClient("tc-m05-g37-inofin", env)
    try:
        login = cli.login_admin(env)
        snap = snap_auditoria(cli)
        r_act = cli.req("GET", f"/activos-biologicos/{id_activo}")
        r_acum = cli.req("GET", f"/suministros/costeo-directo/acumulado/activo/{id_activo}")
        r_hist = cli.req("GET", "/suministros/historial", params={"id_activo_biologico": id_activo})
        r_prov = cli.req("GET", f"/suministros/nic41/{id_provision}") if id_provision else None
    finally:
        teardown = cli.close()
    assert teardown["status_code"] == 200, f"Rollback final fallo: {teardown}"
    return {
        "run_id": cli.run_id,
        "login": login,
        "snapshot": snap,
        "checks_404": {
            "activo": {"status_code": r_act["status_code"], "x_request_id": r_act["x_request_id"]},
            "acumulado": {"status_code": r_acum["status_code"], "x_request_id": r_acum["x_request_id"]},
            "historial": {"status_code": r_hist["status_code"], "x_request_id": r_hist["x_request_id"]},
            "provision": (
                {"status_code": r_prov["status_code"], "x_request_id": r_prov["x_request_id"]}
                if r_prov is not None
                else None
            ),
        },
        "teardown": teardown,
    }


def main() -> None:
    repo = _repo_root()
    env = _cargar_env(repo)

    res: dict[str, Any] = {}
    res["inobase"] = run_inobase(env)
    res["principal"] = run_principal(env)
    assert res["principal"].get("teardown", {}).get("status_code") == 200, (
        f"Teardown principal fallo: {res['principal'].get('teardown')}"
    )

    id_activo = (res["principal"].get("activo_creado") or {}).get("id_activo_biologico")
    id_prov = (res["principal"].get("paso_3f") or {}).get("id_provision")
    if id_activo is not None:
        res["inofin"] = run_inofin(env, id_activo, id_prov)

    out_dir = Path(__file__).resolve().parent
    (out_dir / "obs_resultado.json").write_text(
        json.dumps(res, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(json.dumps(res, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
