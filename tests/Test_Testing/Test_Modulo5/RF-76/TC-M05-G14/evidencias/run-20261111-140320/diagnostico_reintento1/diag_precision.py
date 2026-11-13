# | Fecha      | Nombre                   | Que se hizo                                                              |
# |------------|--------------------------|--------------------------------------------------------------------------|
# | 2026-11-11 | Juan Sebastian Gutierrez | TC-M05-G14 RF-76 reintento 1: diagnóstico de precisión decimal(10,4)     |
"""Diagnóstico del criterio de re-prueba para TC-M05-G14 (RF-76, activo 853).

NO es un reporte oficial. Ejecuta D01-D12 en una única corrida sandbox con un
solo login (DEF-04), verifica inocuidad base y final en corridas separadas y
guarda el resumen estructurado en ``diag_resultados.json`` (sin secretos).
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest
import requests
from dotenv import dotenv_values

try:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

    try:
        ZONA_USUARIO = ZoneInfo("America/Bogota")
    except ZoneInfoNotFoundError:
        ZONA_USUARIO = timezone(timedelta(hours=-5), "America/Bogota")
except ImportError:
    ZONA_USUARIO = timezone(timedelta(hours=-5), "America/Bogota")

NOMBRE_ZONA = "America/Bogota"
ID_ACTIVO = 853
TIMEOUT_S = 45
DIR_DIAG = Path(__file__).resolve().parent
RAIZ_REPO = Path(__file__).resolve().parents[8]
ENV_TEST = dotenv_values(RAIZ_REPO / ".env.test") if (RAIZ_REPO / ".env.test").exists() else {}

_INOCUIDAD: dict[str, int] = {}
_RESULTADOS: dict = {"activo": ID_ACTIVO, "casos": [], "observaciones_ledger_acumulado": []}


def _env(nombre: str) -> str:
    val = os.environ.get(nombre) or ENV_TEST.get(nombre)
    if not val:
        raise AssertionError(f"Falta variable de entorno requerida: {nombre}")
    return val


def _secretos() -> list[str]:
    vals = []
    for k in ("TEST_SANDBOX_SECRET", "TEST_ADMIN_PASSWORD"):
        v = os.environ.get(k) or ENV_TEST.get(k)
        if v:
            vals.append(v)
    return vals


def _seguro(texto: str, extra: tuple[str, ...] = ()) -> str:
    out = (texto or "")[:500]
    for s in [*_secretos(), *extra]:
        if s:
            out = out.replace(s, "***")
    return out


def _hoy_bogota() -> str:
    return datetime.now(ZONA_USUARIO).date().isoformat()


class _CuerpoSensible(dict):
    def __repr__(self) -> str:
        return "<cuerpo sensible omitido>"

    __str__ = __repr__


class CorridaDiag:
    def __init__(self, prefijo: str) -> None:
        self.base = _env("TEST_BASE_URL").rstrip("/")
        self.run_id = f"{prefijo}-{uuid.uuid4()}"
        self.token: str | None = None
        self.cerrada = False
        self.http = requests.Session()
        self.http.headers.update(
            {
                "X-Test-Run-Id": self.run_id,
                "X-Sandbox-Secret": _env("TEST_SANDBOX_SECRET"),
                "X-Zona-Horaria": NOMBRE_ZONA,
            }
        )

    def login(self) -> None:
        assert self.token is None, "DEF-04: un solo login por run_id"
        body = _CuerpoSensible(
            correo_electronico=_env("TEST_ADMIN_EMAIL"),
            contrasena=_env("TEST_ADMIN_PASSWORD"),
        )
        r = self.http.post(f"{self.base}/sesiones/", json=body, timeout=TIMEOUT_S)
        assert r.status_code == 200, f"Login HTTP {r.status_code}: {_seguro(r.text)}"
        token = r.json().get("token")
        assert token, "Login sin token"
        self.token = token
        self.http.headers["Authorization"] = f"Bearer {token}"

    def get(self, ruta: str, **kw) -> requests.Response:
        return self.http.get(f"{self.base}{ruta}", timeout=TIMEOUT_S, **kw)

    def post_json(self, ruta: str, payload: dict) -> requests.Response:
        return self.http.post(f"{self.base}{ruta}", json=payload, timeout=TIMEOUT_S)

    def post_raw_json(self, ruta: str, raw_body: str) -> requests.Response:
        return self.http.post(
            f"{self.base}{ruta}",
            data=raw_body.encode("utf-8"),
            headers={"Content-Type": "application/json"},
            timeout=TIMEOUT_S,
        )

    def query(self, sql: str) -> tuple[int, dict, str | None]:
        r = self.http.post(
            f"{self.base}/test-control/query",
            json={"query": sql},
            timeout=TIMEOUT_S,
        )
        try:
            body = r.json()
        except ValueError:
            body = {"raw": _seguro(r.text, (self.token,) if self.token else ())}
        return r.status_code, body, r.headers.get("X-Request-ID")

    def cerrar(self) -> tuple[int, str]:
        if self.cerrada:
            return 200, "ya cerrada"
        self.cerrada = True
        try:
            r = self.http.delete(f"{self.base}/test-control/runs/{self.run_id}", timeout=TIMEOUT_S)
            return r.status_code, _seguro(r.text, (self.token,) if self.token else ())
        finally:
            self.http.close()


def _cerrar_con_rollback(c: CorridaDiag) -> None:
    code, texto = c.cerrar()
    assert code == 200 and "Rollback exitoso" in texto, f"Teardown fallo: HTTP {code} {texto}"


def _contar_medicamentos_http(c: CorridaDiag, id_activo: int) -> int:
    r = c.get("/suministros/medicamentos", params={"id_activo_biologico": id_activo})
    assert r.status_code == 200, f"GET medicamentos HTTP {r.status_code}"
    return int(r.json()["total"])


def _preparar_fase(c: CorridaDiag, id_activo: int) -> dict:
    r_fases = c.get(f"/activos-biologicos/{id_activo}/fases")
    assert r_fases.status_code == 200, f"GET fases HTTP {r_fases.status_code}"
    activas = [f for f in r_fases.json().get("fases") or [] if f.get("es_activa") is True]
    if activas:
        return {"fase_abierta_por_diag": False, "fase": activas[0]}

    r_ciclos = c.get(f"/activos-biologicos/{id_activo}/ciclos-productivos")
    assert r_ciclos.status_code == 200, f"GET ciclos HTTP {r_ciclos.status_code}"
    con_fases = sorted(
        (ci for ci in r_ciclos.json().get("items") or [] if ci.get("fases")),
        key=lambda ci: ci["id_ciclo_productivo"],
    )
    assert con_fases, f"Activo {id_activo} sin ciclos productivos con fases"
    id_ciclo = con_fases[0]["id_ciclo_productivo"]
    rf = c.post_json(
        f"/activos-biologicos/{id_activo}/fases",
        {"id_ciclo_productiva": id_ciclo, "motivo_cambio": "TC-M05-G14 diag: apertura de fase en sandbox"},
    )
    assert rf.status_code == 201, f"POST fases HTTP {rf.status_code}: {_seguro(rf.text)}"
    return {"fase_abierta_por_diag": True, "fase": rf.json()}


def _payload_raw(id_activo: int, hora: str, dosis_raw: str, costo_unitario: int | float) -> str:
    base = {
        "id_activo_biologico": id_activo,
        "nombre_medicamento": "Oxitetraciclina",
        "fecha_aplicacion": _hoy_bogota(),
        "hora_aplicacion": hora,
        "via_administracion": "INTRAMUSCULAR",
        "dosis_aplicada": "__DOSIS_LITERAL__",
        "unidad_dosis": "ml",
        "periodo_retiro_dias": 0,
        "motivo_aplicacion": "Tratamiento de infección respiratoria",
        "costo_unitario": costo_unitario,
        "nombre_veterinario": "Dr. Pérez",
    }
    return json.dumps(base, ensure_ascii=False).replace('"__DOSIS_LITERAL__"', dosis_raw)


# (id, dosis_raw, costo_unitario, hora, expected_http, expected_error_code, expected_cantidad, expected_costo, origen)
CASOS_DIAG = [
    ("D01", "0.0001", 500, "10:01", 201, None, "0.0001", "0.0500", "[especificación + Dev]"),
    ("D02", "0.0004", 500, "10:02", 201, None, "0.0004", "0.2000", "[contrato Dev]"),
    ("D03", "0.0005", 500, "10:03", 201, None, "0.0005", "0.2500", "[criterio INC]"),
    ("D04", "0.0015", 500, "10:04", 201, None, "0.0015", "0.7500", "[criterio INC]"),
    ("D05", "0.001", 500, "10:05", 201, None, "0.001", None, "[control]"),
    ("D06", "0.00001", 500, "10:06", 400, "VAL_ENTRADA", None, None, "[contrato Dev]"),
    ("D07", "1.23456", 500, "10:07", 400, None, None, None, "[contrato Dev]"),
    ("D08", "0.00010", 500, "10:08", 201, None, "0.0001", None, "[contrato Dev]"),
    ("D09", "0", 500, "10:09", 400, None, None, None, "[especificación E4]"),
    ("D10", "999999.9999", 1, "10:10", 201, None, "999999.9999", None, "[contrato Dev / max 10,4]"),
    ("D11", "1000000", 1, "10:11", 400, None, None, None, "[contrato Dev]"),
    ("D12", "10", 500, "10:12", 201, None, "10", None, "[control post-400]"),
]


def _dec_eq(a, b) -> bool:
    if a is None or b is None:
        return False
    return Decimal(str(a)) == Decimal(str(b))


def test_00_diag_inocuidad_base():
    c = CorridaDiag("diag-m05-g14-base")
    try:
        c.login()
        total = _contar_medicamentos_http(c, ID_ACTIVO)
    except BaseException:
        c.cerrar()
        raise
    _cerrar_con_rollback(c)
    _INOCUIDAD["base"] = total
    _RESULTADOS["inocuidad_base"] = total


def test_01_diag_precision_d01_d12():
    c = CorridaDiag("diag-m05-g14")
    ids_creados: dict[str, int] = {}
    fallos_eval: list[str] = []

    try:
        c.login()
        prep = _preparar_fase(c, ID_ACTIVO)
        _RESULTADOS["preparacion"] = {
            "fase_abierta_por_diag": prep["fase_abierta_por_diag"],
            "id_gestion_fases": prep["fase"].get("id_gestion_fases"),
            "id_ciclo_productiva": prep["fase"].get("id_ciclo_productiva"),
        }

        for cid, dosis_raw, costo_u, hora, esp_http, esp_ec, esp_cant, esp_costo, origen in CASOS_DIAG:
            antes_http = _contar_medicamentos_http(c, ID_ACTIVO)
            raw_payload = _payload_raw(ID_ACTIVO, hora, dosis_raw, costo_u)
            resp = c.post_raw_json("/suministros/medicamentos", raw_payload)
            despues_http = _contar_medicamentos_http(c, ID_ACTIVO)
            req_id = resp.headers.get("X-Request-ID")

            try:
                body = resp.json()
            except ValueError:
                body = {}

            med = body.get("medicamento") if isinstance(body, dict) else None
            error_code = body.get("error_code") if isinstance(body, dict) else None
            id_reg = med.get("id_registro_medicamento") if isinstance(med, dict) else None
            resp_cant = med.get("cantidad") if isinstance(med, dict) else None
            resp_costo = med.get("costo_total_medicamento") if isinstance(med, dict) else None

            bd_info = {"query_http": None, "rows": [], "x_request_id": None}
            if id_reg is not None:
                ids_creados[cid] = id_reg
                q_http, q_body, q_req = c.query(
                    "SELECT id_registro_medicamento, id_registro_rf76::text AS id_registro_rf76, "
                    "cantidad::text AS cantidad, costo_unitario_medicamento::text AS costo_unitario_medicamento, "
                    "costo_total_medicamento::text AS costo_total_medicamento, "
                    "dosis_por_individuo::text AS dosis_por_individuo, estado_registro "
                    f"FROM modulo5.registros_medicamentos WHERE id_registro_medicamento = {int(id_reg)}"
                )
                bd_info = {
                    "query_http": q_http,
                    "rows": q_body.get("data", []) if isinstance(q_body, dict) else [],
                    "detail": q_body.get("detail") if isinstance(q_body, dict) else None,
                    "x_request_id": q_req,
                }

            ok = resp.status_code == esp_http
            if esp_http == 201:
                ok = ok and (despues_http == antes_http + 1)
                if esp_cant is not None:
                    ok = ok and _dec_eq(resp_cant, esp_cant)
                if esp_costo is not None:
                    ok = ok and _dec_eq(resp_costo, esp_costo)
            else:
                ok = ok and (despues_http == antes_http)
                if esp_ec is not None:
                    ok = ok and (error_code == esp_ec)

            registro = {
                "id": cid,
                "dosis_enviada_json": dosis_raw,
                "costo_unitario": costo_u,
                "hora": hora,
                "origen": origen,
                "esperado_http": esp_http,
                "esperado_error_code": esp_ec,
                "esperado_cantidad": esp_cant,
                "esperado_costo_total": esp_costo,
                "http": resp.status_code,
                "error_code": error_code,
                "x_request_id": req_id,
                "conteo_http_antes": antes_http,
                "conteo_http_despues": despues_http,
                "id_registro_medicamento": id_reg,
                "resp_cantidad": resp_cant,
                "resp_costo_total": resp_costo,
                "bd_registros_medicamentos": bd_info,
                "veredicto": "OK" if ok else "FALLA",
            }
            _RESULTADOS["casos"].append(registro)
            if not ok:
                fallos_eval.append(f"{cid} (http={resp.status_code}, error_code={error_code}, cant={resp_cant}, costo={resp_costo})")

        # Consultar ledger (modulo5.registro_suministro) y acumulado (modulo5.acumulado_ciclo) para D01 y D03
        for cid in ("D01", "D03"):
            if cid not in ids_creados:
                _RESULTADOS["observaciones_ledger_acumulado"].append(
                    {"caso": cid, "nota": "observación: no se creó registro para consultar ledger/acumulado"}
                )
                continue
            id_reg = ids_creados[cid]
            q_led_http, q_led_body, q_led_req = c.query(
                "SELECT rs.id_registro_suministro::text, rs.id_registro_rf76::text, "
                "rs.tipo_suministro, rs.cantidad::text, rs.precio_unitario_resuelto::text, "
                "rs.costo_registro::text, rs.id_gestion_fases, rs.id_ciclo_productivo "
                "FROM modulo5.registro_suministro rs "
                "JOIN modulo5.registros_medicamentos rm ON rm.id_registro_rf76 = rs.id_registro_rf76 "
                f"WHERE rm.id_registro_medicamento = {int(id_reg)}"
            )
            _RESULTADOS["observaciones_ledger_acumulado"].append(
                {
                    "caso": cid,
                    "tabla": "modulo5.registro_suministro",
                    "id_registro_medicamento": id_reg,
                    "query_http": q_led_http,
                    "x_request_id": q_led_req,
                    "rows": q_led_body.get("data", []) if isinstance(q_led_body, dict) else [],
                    "detail": q_led_body.get("detail") if isinstance(q_led_body, dict) else None,
                }
            )

        q_ac_http, q_ac_body, q_ac_req = c.query(
            "SELECT id_acumulado_ciclo, id_activo_biologico, id_ciclo_productivo, id_gestion_fases, "
            "acumulado_total_ciclo::text, acumulado_por_categoria::text, estado "
            f"FROM modulo5.acumulado_ciclo WHERE id_activo_biologico = {ID_ACTIVO}"
        )
        _RESULTADOS["observaciones_ledger_acumulado"].append(
            {
                "caso": "D01+D03_ciclo",
                "tabla": "modulo5.acumulado_ciclo",
                "query_http": q_ac_http,
                "x_request_id": q_ac_req,
                "rows": q_ac_body.get("data", []) if isinstance(q_ac_body, dict) else [],
                "detail": q_ac_body.get("detail") if isinstance(q_ac_body, dict) else None,
            }
        )

        # También consultar vía API HTTP de costeo directo (GET /suministros/costeo-directo/acumulado/activo/{id})
        r_costeo = c.get(f"/suministros/costeo-directo/acumulado/activo/{ID_ACTIVO}")
        _RESULTADOS["observaciones_ledger_acumulado"].append(
            {
                "caso": "API_acumulado_ciclo",
                "endpoint": f"/suministros/costeo-directo/acumulado/activo/{ID_ACTIVO}",
                "http": r_costeo.status_code,
                "x_request_id": r_costeo.headers.get("X-Request-ID"),
                "body": r_costeo.json() if r_costeo.headers.get("content-type", "").startswith("application/json") else _seguro(r_costeo.text),
            }
        )
    except BaseException:
        c.cerrar()
        raise
    _cerrar_con_rollback(c)

    (DIR_DIAG / "diag_resultados.json").write_text(
        json.dumps(_RESULTADOS, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    assert not fallos_eval, "Incumplimientos en diagnostico: " + "; ".join(fallos_eval)


def test_02_diag_inocuidad_final():
    c = CorridaDiag("diag-m05-g14-fin")
    try:
        c.login()
        total = _contar_medicamentos_http(c, ID_ACTIVO)
    except BaseException:
        c.cerrar()
        raise
    _cerrar_con_rollback(c)
    _INOCUIDAD["final"] = total
    _RESULTADOS["inocuidad_final"] = total
    (DIR_DIAG / "diag_resultados.json").write_text(
        json.dumps(_RESULTADOS, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    assert total == _INOCUIDAD["base"], (
        f"Contaminacion en diagnostico: base={_INOCUIDAD['base']}, final={total}"
    )
