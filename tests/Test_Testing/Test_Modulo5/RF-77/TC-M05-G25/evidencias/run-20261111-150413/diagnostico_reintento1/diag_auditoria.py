# | Fecha      | Nombre                   | Que se hizo                                                            |
# |------------|--------------------------|------------------------------------------------------------------------|
# | 2026-11-11 | Juan Sebastian Gutierrez | Diagnostico reintento 1 TC-M05-G25 (RF-77 auditoria E01-E07 e inocuidad) |
"""Diagnostico aislado para TC-M05-G25 (RF-77 / TC-M05-025) en TEST.

Cobertura:
- E01: Generacion de reporte de gastos -> evento INSERT / accion GENERACION en <= 2 s.
- E02: Exportacion CSV -> evento INSERT / accion EXPORTACION (CSV) en <= 2 s + descarga.
- E03: Exportacion PDF -> evento INSERT / accion EXPORTACION (PDF) en <= 2 s + descarga.
- E04: Regeneracion de reporte -> evento SELECT / accion REGENERACION en <= 2 s y snapshot intacto.
- E05: Consulta normal (historial / detalle) -> sin incremento en auditoria.
- E06: Error controlado en exportacion (formato invalido 422, reporte inexistente 404; analisis E6a).
- E07: Factibilidad IDOR bajo DEF-04 (evidencia post-rollback y verificacion read-only de ajenos si existen).
- Inocuidad completa: total base == total final de auditoria y 404 para todos los IDs creados.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
import requests
from dotenv import dotenv_values

_ZONA_HORARIA = "America/Bogota"
_TIMEOUT_S = 25
_RAIZ_REPO = Path(__file__).resolve().parents[7]
if not (_RAIZ_REPO / ".env.test").exists():
    _RAIZ_REPO = Path.cwd()
_ENV_TEST = dotenv_values(_RAIZ_REPO / ".env.test") if (_RAIZ_REPO / ".env.test").exists() else {}
_SALIDA_DIR = Path(__file__).resolve().parent


def _env(nombre: str) -> str:
    val = os.environ.get(nombre) or _ENV_TEST.get(nombre) or ""
    assert val, f"Falta variable obligatoria en .env.test: {nombre}"
    return val


def _req_id(resp: requests.Response) -> str:
    return resp.headers.get("X-Request-Id") or resp.headers.get("x-request-id") or ""


class SandboxCliente:
    """Cliente sandbox secuencial (DEF-04: un solo POST /sesiones/ por run_id)."""

    def __init__(self, sufijo: str, email_var: str, pass_var: str) -> None:
        self.run_id = f"tc-m05-g25-diag-{sufijo}-{uuid.uuid4().hex[:8]}"
        self.email_var = email_var
        self.pass_var = pass_var
        self.base = _env("TEST_BASE_URL").rstrip("/")
        self.secret = _env("TEST_SANDBOX_SECRET")
        self._ya_autenticado = False
        self.cerrada = False
        self.http = requests.Session()
        self.http.headers.update({
            "X-Test-Run-Id": self.run_id,
            "X-Sandbox-Secret": self.secret,
            "X-Zona-Horaria": _ZONA_HORARIA,
        })

    def login(self) -> dict[str, Any]:
        assert not self._ya_autenticado, "DEF-04: solo un POST /sesiones/ por run_id"
        self._ya_autenticado = True
        r = self.http.post(
            f"{self.base}/sesiones/",
            json={"correo_electronico": _env(self.email_var), "contrasena": _env(self.pass_var)},
            timeout=_TIMEOUT_S,
        )
        assert r.status_code == 200, f"Login {self.email_var} fallo: HTTP {r.status_code}"
        body = r.json()
        token = body.get("token") or body.get("access_token")
        assert token, f"Login {self.email_var} sin credencial de sesion"
        self.http.headers["Authorization"] = f"Bearer {token}"
        return {"status": r.status_code, "x_request_id": _req_id(r)}

    def get(self, ruta: str, params: dict[str, Any] | None = None) -> requests.Response:
        return self.http.get(f"{self.base}{ruta}", params=params, timeout=_TIMEOUT_S)

    def post(self, ruta: str, payload: dict[str, Any]) -> requests.Response:
        return self.http.post(f"{self.base}{ruta}", json=payload, timeout=_TIMEOUT_S)

    def cerrar(self) -> dict[str, Any]:
        if self.cerrada:
            return {"status": None, "ya_cerrada": True}
        self.cerrada = True
        try:
            r = self.http.delete(f"{self.base}/test-control/runs/{self.run_id}", timeout=_TIMEOUT_S)
            info = {"run_id": self.run_id, "status": r.status_code, "x_request_id": _req_id(r), "body": r.text[:200]}
            assert r.status_code == 200 and "Rollback exitoso" in r.text, (
                f"Teardown invalido para {self.run_id}: {info}"
            )
            return info
        finally:
            self.http.close()


def _resumen_evento(ev: dict[str, Any]) -> dict[str, Any]:
    return {
        "id_auditoria_suministro": ev.get("id_auditoria_suministro"),
        "entidad_afectada": ev.get("entidad_afectada"),
        "tipo_operacion": ev.get("tipo_operacion"),
        "id_usuario": ev.get("id_usuario"),
        "resultado": ev.get("resultado"),
        "fecha_evento": ev.get("fecha_evento"),
        "fecha_emision": ev.get("fecha_emision"),
        "id_activo_biologico": ev.get("id_activo_biologico"),
        "hash_integridad_presente": bool(ev.get("hash_integridad")),
        "detalle_causa": ev.get("detalle_causa"),
        "datos_nuevos": ev.get("datos_nuevos"),
    }


def _esperar_evento_auditoria(
    adm: SandboxCliente,
    top_id_previo: int,
    t_accion_fin: float,
    predicado,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]], float]:
    """Consulta /suministros/auditoria en 0 s, 1 s y 2 s hasta encontrar el evento."""
    pausas = [0.0, 1.0, 1.0]
    ultimo_poll_nuevos: list[dict[str, Any]] = []
    for pausa in pausas:
        if pausa > 0:
            time.sleep(pausa)
        r = adm.get("/suministros/auditoria", params={"registros_por_pagina": 20})
        elapsed_s = round(time.perf_counter() - t_accion_fin, 3)
        assert r.status_code == 200, f"GET /suministros/auditoria fallo: HTTP {r.status_code}"
        items = r.json().get("items", [])
        nuevos = [it for it in items if (it.get("id_auditoria_suministro") or 0) > top_id_previo]
        ultimo_poll_nuevos = [_resumen_evento(x) for x in nuevos]
        for ev in nuevos:
            if predicado(ev):
                return _resumen_evento(ev), ultimo_poll_nuevos, elapsed_s
    return None, ultimo_poll_nuevos, round(time.perf_counter() - t_accion_fin, 3)


def _snapshot_auditoria(adm: SandboxCliente) -> tuple[int, int, str]:
    r = adm.get("/suministros/auditoria", params={"registros_por_pagina": 20})
    assert r.status_code == 200, f"Error consultando auditoria: HTTP {r.status_code}"
    j = r.json()
    items = j.get("items", [])
    top_id = (items[0].get("id_auditoria_suministro") if items else 0) or 0
    return int(j.get("total", 0)), int(top_id), _req_id(r)


_ESTADO: dict[str, Any] = {
    "base_auditoria": {},
    "prod_e07": {},
    "main": {},
    "final_inocuidad": {},
    "ids_creados": {
        "activos": [],
        "reportes": [],
        "archivos": [],
    },
}


@pytest.fixture(scope="module")
def guardar_resultado_diag():
    yield
    destino = _SALIDA_DIR / "diag_resultados.json"
    destino.write_text(json.dumps(_ESTADO, indent=2, ensure_ascii=False), encoding="utf-8")


def test_01_linea_base_auditoria_admin(guardar_resultado_diag):
    """Run 1 (Admin, solo lectura): captura total y top_id base reales antes de crear recursos."""
    adm = SandboxCliente("base", "TEST_ADMIN_EMAIL", "TEST_ADMIN_PASSWORD")
    try:
        login_info = adm.login()
        total, top_id, xid = _snapshot_auditoria(adm)
        _ESTADO["base_auditoria"] = {
            "run_id": adm.run_id,
            "login": login_info,
            "total": total,
            "top_id": top_id,
            "x_request_id": xid,
        }
        assert total >= 0
    finally:
        _ESTADO["base_auditoria"]["teardown"] = adm.cerrar()


def test_02_e07_productor_exportacion_y_rollback(guardar_resultado_diag):
    """Run 2 (Productor): genera/exporta archivo ajeno en sandbox y cierra run antes del Run 3."""
    prod = SandboxCliente("prod-e07", "TEST_PRODUCER_EMAIL", "TEST_PRODUCER_PASSWORD")
    try:
        login_info = prod.login()
        r_rep = prod.post(
            "/suministros/reportes-gastos",
            {
                "id_infraestructura": 2,
                "fecha_inicio_reporte": "2026-06-01",
                "fecha_fin_reporte": "2026-11-01",
                "tipo_periodo": "MENSUAL",
            },
        )
        assert r_rep.status_code == 200, f"Productor generar reporte fallo: HTTP {r_rep.status_code}"
        id_rep = r_rep.json().get("id_reporte_gasto_acumulado")
        assert id_rep is not None
        _ESTADO["ids_creados"]["reportes"].append(id_rep)

        r_exp = prod.post(f"/suministros/reportes-gastos/{id_rep}/exportacion", {"formato_exportacion": "CSV"})
        assert r_exp.status_code == 201, f"Productor exportar CSV fallo: HTTP {r_exp.status_code}"
        uuid_prod = r_exp.json().get("id_archivo") or r_exp.json().get("id_archivo_exportacion")
        assert uuid_prod
        _ESTADO["ids_creados"]["archivos"].append(uuid_prod)

        r_dl = prod.get(f"/suministros/reportes-gastos/exportaciones/{uuid_prod}")
        assert r_dl.status_code == 200

        _ESTADO["prod_e07"] = {
            "run_id": prod.run_id,
            "login": login_info,
            "id_reporte_prod": id_rep,
            "uuid_archivo_prod": uuid_prod,
            "descarga_propia_status": r_dl.status_code,
        }
    finally:
        _ESTADO["prod_e07"]["teardown"] = prod.cerrar()


def test_03_admin_e01_a_e07_auditoria(guardar_resultado_diag):
    """Run 3 (Admin): valida E01..E07 en sandbox unico y registra latencias/campos exactos."""
    adm = SandboxCliente("main", "TEST_ADMIN_EMAIL", "TEST_ADMIN_PASSWORD")
    det: dict[str, Any] = {"run_id": adm.run_id}
    try:
        det["login"] = adm.login()

        # Setup dentro del sandbox: activo INDIVIDUAL + fase + consumo inicial (10.000 COP)
        r_act = adm.post(
            "/activos-biologicos",
            {
                "tipo_activo": "INDIVIDUAL",
                "id_especie": 5,
                "id_infraestructura": 389,
                "identificador": f"QA-G25-DIAG-{uuid.uuid4().hex[:6]}",
                "raza": "Holstein",
                "sexo": "Hembra",
                "fecha_inicio_ciclo": "2026-07-01",
                "origen_financiero": "nacimiento",
            },
        )
        assert r_act.status_code == 201, f"Crear activo fallo: HTTP {r_act.status_code}: {r_act.text[:200]}"
        id_act = r_act.json()["id_activo_biologico"]
        _ESTADO["ids_creados"]["activos"].append(id_act)

        r_fase = adm.post(
            f"/activos-biologicos/{id_act}/fases",
            {
                "id_ciclo_productiva": 5,
                "motivo_cambio": "Diagnostico G25",
                "fecha_inicio": "2026-07-01T05:00:00Z",
            },
        )
        assert r_fase.status_code in (200, 201), f"Abrir fase fallo: HTTP {r_fase.status_code}"

        r_con1 = adm.post(
            "/suministros/consumo-alimentos",
            {
                "id_activo_biologico": id_act,
                "id_tipo_alimento": 1,
                "fecha_consumo": "2026-08-10",
                "hora_suministro": "08:00:00",
                "cantidad_alimento": 10,
                "costo_unitario": 1000,
            },
        )
        assert r_con1.status_code == 201, f"Consumo 1 fallo: HTTP {r_con1.status_code}"

        tot_pre, top_pre, _ = _snapshot_auditoria(adm)
        det["setup"] = {"id_activo": id_act, "auditoria_total_pre": tot_pre, "auditoria_top_pre": top_pre}

        # --- E01: Generacion exitosa de reporte ---
        r_rep = adm.post(
            "/suministros/reportes-gastos",
            {
                "activo_biologico_id": id_act,
                "fecha_inicio_reporte": "2026-08-01",
                "fecha_fin_reporte": "2026-08-31",
                "tipo_periodo": "MENSUAL",
            },
        )
        t_gen = time.perf_counter()
        assert r_rep.status_code == 200, f"E01 generacion fallo: HTTP {r_rep.status_code}: {r_rep.text[:200]}"
        id_rep = r_rep.json()["id_reporte_gasto_acumulado"]
        _ESTADO["ids_creados"]["reportes"].append(id_rep)

        ev_e01, _, lat_e01 = _esperar_evento_auditoria(
            adm,
            top_pre,
            t_gen,
            lambda e: (
                e.get("entidad_afectada") == "reporte_gastos_acumulados"
                and (e.get("datos_nuevos") or {}).get("accion") == "GENERACION"
                and (e.get("datos_nuevos") or {}).get("id_reporte_gasto_acumulado") == id_rep
            ),
        )
        assert ev_e01 is not None, "E01: no aparecio evento GENERACION en auditoria en <= 2 s"
        assert lat_e01 <= 2.0, f"E01 latencia fuera de SLA (<=2s): {lat_e01}s"
        assert ev_e01["resultado"] == "EXITOSO"
        assert ev_e01["id_usuario"] is not None
        assert ev_e01["fecha_evento"] is not None
        id_actor = ev_e01["id_usuario"]
        det["E01"] = {
            "status": r_rep.status_code,
            "x_request_id": _req_id(r_rep),
            "id_reporte": id_rep,
            "latencia_s": lat_e01,
            "evento": ev_e01,
        }

        tot_post_e01, top_post_e01, _ = _snapshot_auditoria(adm)

        # --- E02: Exportacion exitosa CSV + Descarga ---
        r_csv = adm.post(f"/suministros/reportes-gastos/{id_rep}/exportacion", {"formato_exportacion": "CSV"})
        t_csv = time.perf_counter()
        assert r_csv.status_code == 201, f"E02 exportacion CSV fallo: HTTP {r_csv.status_code}"
        uuid_csv = r_csv.json()["id_archivo"]
        _ESTADO["ids_creados"]["archivos"].append(uuid_csv)

        ev_e02, _, lat_e02 = _esperar_evento_auditoria(
            adm,
            top_post_e01,
            t_csv,
            lambda e: (
                (e.get("datos_nuevos") or {}).get("accion") == "EXPORTACION"
                and (e.get("datos_nuevos") or {}).get("id_archivo") == uuid_csv
            ),
        )
        assert ev_e02 is not None, "E02: no aparecio evento EXPORTACION CSV en auditoria en <= 2 s"
        assert lat_e02 <= 2.0, f"E02 latencia fuera de SLA (<=2s): {lat_e02}s"
        assert ev_e02["id_usuario"] == id_actor
        assert (ev_e02["datos_nuevos"] or {}).get("formato") == "CSV"

        tot_pre_dl_csv, top_pre_dl_csv, _ = _snapshot_auditoria(adm)
        r_dl_csv = adm.get(f"/suministros/reportes-gastos/exportaciones/{uuid_csv}")
        assert r_dl_csv.status_code == 200
        tot_post_dl_csv, top_post_dl_csv, _ = _snapshot_auditoria(adm)

        det["E02"] = {
            "status": r_csv.status_code,
            "x_request_id": _req_id(r_csv),
            "id_archivo_csv": uuid_csv,
            "latencia_s": lat_e02,
            "evento": ev_e02,
            "descarga_status": r_dl_csv.status_code,
            "descarga_delta_auditoria": tot_post_dl_csv - tot_pre_dl_csv,
        }

        # --- E03: Exportacion exitosa PDF + Descarga ---
        r_pdf = adm.post(f"/suministros/reportes-gastos/{id_rep}/exportacion", {"formato_exportacion": "PDF"})
        t_pdf = time.perf_counter()
        assert r_pdf.status_code == 201, f"E03 exportacion PDF fallo: HTTP {r_pdf.status_code}"
        uuid_pdf = r_pdf.json()["id_archivo"]
        _ESTADO["ids_creados"]["archivos"].append(uuid_pdf)

        ev_e03, _, lat_e03 = _esperar_evento_auditoria(
            adm,
            top_post_dl_csv,
            t_pdf,
            lambda e: (
                (e.get("datos_nuevos") or {}).get("accion") == "EXPORTACION"
                and (e.get("datos_nuevos") or {}).get("id_archivo") == uuid_pdf
            ),
        )
        assert ev_e03 is not None, "E03: no aparecio evento EXPORTACION PDF en auditoria en <= 2 s"
        assert lat_e03 <= 2.0, f"E03 latencia fuera de SLA (<=2s): {lat_e03}s"
        assert ev_e03["id_usuario"] == id_actor
        assert (ev_e03["datos_nuevos"] or {}).get("formato") == "PDF"

        r_dl_pdf = adm.get(f"/suministros/reportes-gastos/exportaciones/{uuid_pdf}")
        assert r_dl_pdf.status_code == 200
        assert r_dl_pdf.content.startswith(b"%PDF")
        tot_post_e03, top_post_e03, _ = _snapshot_auditoria(adm)

        det["E03"] = {
            "status": r_pdf.status_code,
            "x_request_id": _req_id(r_pdf),
            "id_archivo_pdf": uuid_pdf,
            "latencia_s": lat_e03,
            "evento": ev_e03,
            "descarga_status": r_dl_pdf.status_code,
            "pdf_bytes": len(r_dl_pdf.content),
        }

        # --- E04: Regeneracion de reporte con cambio de datos + snapshot intacto ---
        r_con2 = adm.post(
            "/suministros/consumo-alimentos",
            {
                "id_activo_biologico": id_act,
                "id_tipo_alimento": 1,
                "fecha_consumo": "2026-08-15",
                "hora_suministro": "09:00:00",
                "cantidad_alimento": 5,
                "costo_unitario": 2000,
            },
        )
        assert r_con2.status_code == 201
        _, top_pre_reg, _ = _snapshot_auditoria(adm)

        r_reg = adm.get(f"/suministros/reportes-gastos/{id_rep}/regenerar")
        t_reg = time.perf_counter()
        assert r_reg.status_code == 200, f"E04 regenerar fallo: HTTP {r_reg.status_code}"
        reg_j = r_reg.json()
        assert reg_j.get("advertencia"), "E04: respuesta sin advertencia"
        assert Decimal(str(reg_j.get("gasto_total_acumulado"))) == Decimal("20000.0000")

        r_snap = adm.get(f"/suministros/reportes-gastos/{id_rep}")
        assert r_snap.status_code == 200
        snap_total = Decimal(str(r_snap.json().get("gasto_total_acumulado")))
        assert snap_total == Decimal("10000.0000"), f"Snapshot mutado: {snap_total}"

        ev_e04, _, lat_e04 = _esperar_evento_auditoria(
            adm,
            top_pre_reg,
            t_reg,
            lambda e: (
                e.get("entidad_afectada") == "reporte_gastos_acumulados"
                and (e.get("datos_nuevos") or {}).get("accion") == "REGENERACION"
                and (e.get("datos_nuevos") or {}).get("id_reporte_gasto_acumulado") == id_rep
            ),
        )
        assert ev_e04 is not None, "E04: no aparecio evento REGENERACION en auditoria en <= 2 s"
        assert lat_e04 <= 2.0, f"E04 latencia fuera de SLA (<=2s): {lat_e04}s"
        assert ev_e04["tipo_operacion"] == "SELECT"
        assert ev_e04["id_usuario"] == id_actor

        det["E04"] = {
            "status": r_reg.status_code,
            "x_request_id": _req_id(r_reg),
            "gasto_regenerado": str(reg_j.get("gasto_total_acumulado")),
            "gasto_snapshot_original": str(snap_total),
            "latencia_s": lat_e04,
            "evento": ev_e04,
        }

        # --- E05: Consulta normal (historial y detalle) no debe mutar bitacora ---
        tot_pre_e05, top_pre_e05, _ = _snapshot_auditoria(adm)
        r_hist = adm.get("/suministros/reportes-gastos/historial", params={"limite": 20})
        assert r_hist.status_code == 200
        r_det = adm.get(f"/suministros/reportes-gastos/{id_rep}")
        assert r_det.status_code == 200
        tot_post_e05, top_post_e05, _ = _snapshot_auditoria(adm)

        det["E05"] = {
            "historial_status": r_hist.status_code,
            "historial_x_request_id": _req_id(r_hist),
            "detalle_status": r_det.status_code,
            "detalle_x_request_id": _req_id(r_det),
            "auditoria_total_pre": tot_pre_e05,
            "auditoria_total_post": tot_post_e05,
            "delta_auditoria": tot_post_e05 - tot_pre_e05,
            "top_id_sin_cambios": top_pre_e05 == top_post_e05,
        }
        assert tot_post_e05 == tot_pre_e05

        # --- E06: Errores controlados en exportacion ---
        tot_pre_e06, top_pre_e06, _ = _snapshot_auditoria(adm)
        r_fmt_inv = adm.post(f"/suministros/reportes-gastos/{id_rep}/exportacion", {"formato_exportacion": "XML"})
        r_rep_404 = adm.post("/suministros/reportes-gastos/999999999/exportacion", {"formato_exportacion": "CSV"})
        tot_post_e06, top_post_e06, _ = _snapshot_auditoria(adm)

        det["E06"] = {
            "formato_invalido": {
                "status": r_fmt_inv.status_code,
                "x_request_id": _req_id(r_fmt_inv),
                "error_code": r_fmt_inv.json().get("error_code"),
            },
            "reporte_inexistente": {
                "status": r_rep_404.status_code,
                "x_request_id": _req_id(r_rep_404),
                "error_code": r_rep_404.json().get("error_code"),
            },
            "delta_auditoria": tot_post_e06 - tot_pre_e06,
            "nota_e6a": (
                "E6a (fallo interno del motor PDF -> HTTP 500 ERROR_GENERACION_PDF y evento FALLIDO) "
                "no es inyectable por HTTP publico en TEST sin mock/instrumentacion."
            ),
        }

        # --- E07: Factibilidad IDOR bajo DEF-04 y rollback ---
        uuid_prod_rollback = (_ESTADO.get("prod_e07") or {}).get("uuid_archivo_prod")
        r_idor_rollback = None
        if uuid_prod_rollback:
            r_post_rb = adm.get(f"/suministros/reportes-gastos/exportaciones/{uuid_prod_rollback}")
            r_idor_rollback = {
                "uuid": uuid_prod_rollback,
                "status": r_post_rb.status_code,
                "x_request_id": _req_id(r_post_rb),
                "error_code": r_post_rb.json().get("error_code") if r_post_rb.headers.get("content-type", "").startswith("application/json") else None,
            }

        # Buscar solo lectura en bitacora por si existe algun archivo historico vigente de otro usuario
        r_exp_hist = adm.get(
            "/suministros/auditoria",
            params={"entidad_afectada": "archivos_exportacion_suministros", "registros_por_pagina": 20},
        )
        otro_uuid = None
        otro_uid = None
        if r_exp_hist.status_code == 200:
            for it in r_exp_hist.json().get("items", []):
                dn = it.get("datos_nuevos") or {}
                if it.get("id_usuario") != id_actor and dn.get("id_archivo"):
                    otro_uuid = dn.get("id_archivo")
                    otro_uid = it.get("id_usuario")
                    break
        prueba_otro_historico = None
        if otro_uuid:
            tot_pre_idor, _, _ = _snapshot_auditoria(adm)
            r_aj = adm.get(f"/suministros/reportes-gastos/exportaciones/{otro_uuid}")
            tot_post_idor, _, _ = _snapshot_auditoria(adm)
            prueba_otro_historico = {
                "uuid": otro_uuid,
                "id_usuario_propietario": otro_uid,
                "status": r_aj.status_code,
                "x_request_id": _req_id(r_aj),
                "error_code": r_aj.json().get("error_code") if r_aj.headers.get("content-type", "").startswith("application/json") else None,
                "delta_auditoria": tot_post_idor - tot_pre_idor,
            }

        det["E07"] = {
            "factible_dinamico_con_def04": False,
            "motivo_codigo": (
                "get_current_user valida el JWT contra modulo1.tokens en BD (TOKEN_REVOCADO si falta o "
                "fecha_uso IS NOT NULL). Bajo corridas sandbox secuenciales con rollback y DEF-04 (un "
                "solo POST /sesiones/ por run_id), los registros creados por Productor (Tokens y "
                "archivos_exportacion_suministros) se revierten al cerrar Run 2, por lo que en Run 3 Admin "
                "el UUID de Productor no existe (HTTP 404) y no es posible tener ambos usuarios con "
                "sesion+archivo en la misma transaccion sandbox sin violar DEF-04 o escribir fuera del sandbox."
            ),
            "post_rollback_prod_uuid": r_idor_rollback,
            "archivo_historico_ajeno_en_test": prueba_otro_historico,
        }
    finally:
        det["teardown"] = adm.cerrar()
        _ESTADO["main"] = det


def test_04_inocuidad_final_y_404_por_id(guardar_resultado_diag):
    """Run 4 (Admin, solo lectura): total final auditoria == base y 404 en cada ID creado."""
    adm = SandboxCliente("final", "TEST_ADMIN_EMAIL", "TEST_ADMIN_PASSWORD")
    try:
        login_info = adm.login()
        tot_fin, top_fin, xid = _snapshot_auditoria(adm)
        base = _ESTADO["base_auditoria"]
        verificaciones_id = []

        for id_act in _ESTADO["ids_creados"]["activos"]:
            r = adm.get(f"/activos-biologicos/{id_act}")
            verificaciones_id.append({"recurso": f"/activos-biologicos/{id_act}", "status": r.status_code, "x_request_id": _req_id(r)})
            assert r.status_code == 404, f"Posible contaminacion activo {id_act}: HTTP {r.status_code}"

        for id_rep in _ESTADO["ids_creados"]["reportes"]:
            r = adm.get(f"/suministros/reportes-gastos/{id_rep}")
            verificaciones_id.append({"recurso": f"/suministros/reportes-gastos/{id_rep}", "status": r.status_code, "x_request_id": _req_id(r)})
            assert r.status_code == 404, f"Posible contaminacion reporte {id_rep}: HTTP {r.status_code}"

        for uid_arch in _ESTADO["ids_creados"]["archivos"]:
            r = adm.get(f"/suministros/reportes-gastos/exportaciones/{uid_arch}")
            verificaciones_id.append({"recurso": f"/suministros/reportes-gastos/exportaciones/{uid_arch}", "status": r.status_code, "x_request_id": _req_id(r)})
            assert r.status_code == 404, f"Posible contaminacion archivo {uid_arch}: HTTP {r.status_code}"

        _ESTADO["final_inocuidad"] = {
            "run_id": adm.run_id,
            "login": login_info,
            "auditoria_total_base": base["total"],
            "auditoria_top_base": base["top_id"],
            "auditoria_total_final": tot_fin,
            "auditoria_top_final": top_fin,
            "x_request_id": xid,
            "verificaciones_id_404": verificaciones_id,
        }
        assert tot_fin == base["total"], f"Total auditoria cambio: base={base['total']}, final={tot_fin}"
        assert top_fin == base["top_id"], f"top_id auditoria cambio: base={base['top_id']}, final={top_fin}"
    finally:
        _ESTADO["final_inocuidad"]["teardown"] = adm.cerrar()

