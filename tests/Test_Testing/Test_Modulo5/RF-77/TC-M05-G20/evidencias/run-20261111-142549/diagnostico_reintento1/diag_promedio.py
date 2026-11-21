# | Fecha      | Nombre                   | Que se hizo                                                              |
# |------------|--------------------------|--------------------------------------------------------------------------|
# | 2026-11-11 | Juan Sebastian Gutierrez | TC-M05-G20 RF-77 reintento 1: diagnostico de alcance P01-P09             |
"""Diagnostico del alcance de la correccion INC-M05-277-G20 (RF-77).

NO es un reporte oficial. Ejecuta P01-P09 en UNA corrida sandbox con UN login
de Administrador (DEF-04), verifica inocuidad base y final en corridas aparte
y guarda los resultados estructurados en ``diag_resultados.json`` (sin secretos).
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
import requests
from dotenv import dotenv_values

try:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
except ImportError:  # pragma: no cover
    ZoneInfo = None  # type: ignore[assignment]
    ZoneInfoNotFoundError = Exception  # type: ignore[misc,assignment]


def _zona_bogota():
    if ZoneInfo is not None:
        try:
            return ZoneInfo("America/Bogota")
        except ZoneInfoNotFoundError:
            pass
    return timezone(timedelta(hours=-5))


ZONA_BOGOTA = _zona_bogota()
TIMEOUT_S = 30
AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[7]
if not (RAIZ / ".env.test").exists():
    RAIZ = Path.cwd()
ENV_PATH = RAIZ / ".env.test"
_ENV = dotenv_values(ENV_PATH) if ENV_PATH.exists() else {}
OUT_JSON = AQUI / "diag_resultados.json"

_INOCUIDAD: dict[str, Any] = {}


def _cfg(nombre: str) -> str:
    val = os.environ.get(nombre) or _ENV.get(nombre)
    if not val:
        raise AssertionError(f"PRECONDICION: falta variable {nombre} en entorno/.env.test")
    return val


class SandboxDiagClient:
    """Cliente sandbox secuencial (un login por run_id, teardown garantizado)."""

    def __init__(self, prefix: str) -> None:
        self.base = _cfg("TEST_BASE_URL").rstrip("/")
        self.secret = _cfg("TEST_SANDBOX_SECRET")
        self.run_id = f"{prefix}-{uuid.uuid4().hex[:10]}"
        self.http = requests.Session()
        self.http.headers.update({
            "X-Test-Run-Id": self.run_id,
            "X-Sandbox-Secret": self.secret,
            "X-Zona-Horaria": "America/Bogota",
        })
        self.logged_in = False
        self.closed = False

    def login_admin(self) -> dict[str, Any]:
        assert not self.logged_in, "DEF-04: solo un POST /sesiones/ por run_id"
        r = self.http.post(
            f"{self.base}/sesiones/",
            json={
                "correo_electronico": _cfg("TEST_ADMIN_EMAIL"),
                "contrasena": _cfg("TEST_ADMIN_PASSWORD"),
            },
            timeout=TIMEOUT_S,
        )
        assert r.status_code == 200, (
            f"Login Admin fallo HTTP {r.status_code} "
            f"X-Request-ID={r.headers.get('X-Request-ID')}: {r.text[:300]}"
        )
        data = r.json()
        token = data.get("token") or data.get("access_token")
        assert token, "Login sin token"
        self.http.headers["Authorization"] = f"Bearer {token}"
        self.logged_in = True
        return {"http": r.status_code, "x_request_id": r.headers.get("X-Request-ID")}

    def req(self, method: str, path: str, **kwargs: Any) -> requests.Response:
        return self.http.request(method, f"{self.base}{path}", timeout=TIMEOUT_S, **kwargs)

    def close(self) -> dict[str, Any]:
        if self.closed:
            return {"status": "already_closed"}
        self.closed = True
        try:
            r = self.http.delete(f"{self.base}/test-control/runs/{self.run_id}", timeout=TIMEOUT_S)
            return {
                "http": r.status_code,
                "x_request_id": r.headers.get("X-Request-ID"),
                "body": r.text[:200],
            }
        finally:
            self.http.close()


def _conteo_historial(client: SandboxDiagClient) -> tuple[int, dict[str, Any]]:
    r = client.req("GET", "/suministros/reportes-gastos/historial", params={"limite": 100})
    assert r.status_code == 200, f"GET historial HTTP {r.status_code}: {r.text[:200]}"
    data = r.json()
    items = data if isinstance(data, list) else data.get("items", [])
    total = data.get("total", len(items)) if isinstance(data, dict) else len(items)
    return int(total), {"http": r.status_code, "x_request_id": r.headers.get("X-Request-ID"), "items_len": len(items)}


def _extraer_campos_reporte(r: requests.Response, cantidad_actual: int | None) -> dict[str, Any]:
    x_req = r.headers.get("X-Request-ID")
    try:
        body = r.json()
    except Exception:
        return {
            "http": r.status_code,
            "error_code": None,
            "x_request_id": x_req,
            "raw_text": r.text[:250],
        }
    if not isinstance(body, dict):
        return {"http": r.status_code, "x_request_id": x_req, "body_type": type(body).__name__}

    prom = body.get("gasto_promedio_individuo")
    return {
        "http": r.status_code,
        "error_code": body.get("error_code"),
        "id_reporte": body.get("id_reporte_gasto_acumulado"),
        "gasto_total_acumulado": body.get("gasto_total_acumulado"),
        "cantidad_actual": cantidad_actual,
        "gasto_promedio_individuo": prom,
        "gasto_promedio_tipo_json": type(prom).__name__ if prom is not None else "null",
        "causa_no_calculable_promedio": body.get("causa_no_calculable_promedio"),
        "nota_bajas": body.get("nota_bajas"),
        "advertencia": body.get("advertencia"),
        "estado": body.get("estado"),
        "x_request_id": x_req,
    }


def _crear_lote_y_gasto(
    c: SandboxDiagClient,
    tag: str,
    cantidad_inicial: int,
    fecha_ciclo: str,
    fecha_hoy: str,
    cantidad_alimento: float,
    costo_unitario: float,
) -> tuple[int, int]:
    r_lote = c.req(
        "POST",
        "/activos-biologicos",
        json={
            "tipo_activo": "POBLACIONAL",
            "id_especie": 1,
            "id_infraestructura": 2,
            "identificador_unico": f"QA-G20-DIAG-{tag}-{uuid.uuid4().hex[:6]}",
            "cantidad_inicial": cantidad_inicial,
            "fecha_ingreso": fecha_ciclo,
            "fecha_inicio_ciclo": fecha_ciclo,
            "origen_financiero": "nacimiento",
        },
    )
    assert r_lote.status_code == 201, f"Crear lote {tag} HTTP {r_lote.status_code}: {r_lote.text[:250]}"
    id_lote = r_lote.json()["id_activo_biologico"]

    r_fase = c.req(
        "POST",
        f"/activos-biologicos/{id_lote}/fases",
        json={
            "id_ciclo_productiva": 1,
            "motivo_cambio": f"Apertura fase diag {tag}",
            "fecha_inicio": f"{fecha_ciclo}T05:00:00Z",
        },
    )
    assert r_fase.status_code in (200, 201), f"Abrir fase {tag} HTTP {r_fase.status_code}: {r_fase.text[:250]}"

    r_cons = c.req(
        "POST",
        "/suministros/consumo-alimentos",
        json={
            "id_activo_biologico": id_lote,
            "id_tipo_alimento": 1,
            "fecha_consumo": fecha_hoy,
            "hora_suministro": "08:00:00",
            "cantidad_alimento": cantidad_alimento,
            "costo_unitario": costo_unitario,
        },
    )
    assert r_cons.status_code == 201, f"Consumo {tag} HTTP {r_cons.status_code}: {r_cons.text[:250]}"

    r_get = c.req("GET", f"/activos-biologicos/{id_lote}")
    cant_actual = _cantidad_actual_de_resp(r_get) if r_get.status_code == 200 else cantidad_inicial
    return id_lote, cant_actual


def _cantidad_actual_de_resp(r: requests.Response) -> int | None:
    if r.status_code != 200:
        return None
    data = r.json()
    if not isinstance(data, dict):
        return None
    if data.get("cantidad_actual") is not None:
        return data.get("cantidad_actual")
    dp = data.get("detalle_poblacional") or {}
    return dp.get("cantidad_actual") if isinstance(dp, dict) else None


def test_00_diag_inocuidad_base() -> None:
    """Captura conteo base de historial de reportes en sandbox separado."""
    c = SandboxDiagClient("diag-g20-base")
    orig_err: BaseException | None = None
    try:
        c.login_admin()
        total_base, meta = _conteo_historial(c)
        _INOCUIDAD["base"] = {"historial_total": total_base, **meta}
    except BaseException as exc:
        orig_err = exc
    finally:
        teardown = c.close()
        _INOCUIDAD["teardown_base"] = teardown
        if orig_err is not None:
            raise orig_err
        assert teardown.get("http") == 200 and "Rollback exitoso" in teardown.get("body", "")


def test_01_diag_alcance_p01_p09() -> None:
    """Ejecuta P01-P09 dentro de UNA unica corrida sandbox con UN login."""
    c = SandboxDiagClient("diag-g20-p")
    fecha_ciclo = "2026-11-01"
    fecha_hoy = datetime.now(ZONA_BOGOTA).date().isoformat()

    resultados: dict[str, Any] = {
        "fecha_ejecucion": datetime.now(ZONA_BOGOTA).isoformat(),
        "fecha_ciclo": fecha_ciclo,
        "fecha_hoy": fecha_hoy,
        "pasos": [],
    }
    orig_err: BaseException | None = None

    try:
        resultados["login"] = c.login_admin()

        # Preparacion Lote 1: 50 individuos, 50.000 COP
        id_l1, cant_l1_inicial = _crear_lote_y_gasto(c, "L1", 50, fecha_ciclo, fecha_hoy, 50.0, 1000.0)
        resultados["id_lote_1"] = id_l1

        payload_rep_l1 = {
            "activo_biologico_id": id_l1,
            "fecha_inicio_reporte": fecha_ciclo,
            "fecha_fin_reporte": fecha_hoy,
            "tipo_periodo": "MENSUAL",
        }

        # P01: Reporte R1 con 50 individuos -> 200, total 50000, promedio 1000
        r_p01 = c.req("POST", "/suministros/reportes-gastos", json=payload_rep_l1)
        d_p01 = _extraer_campos_reporte(r_p01, cant_l1_inicial)
        prom_p01_dec = Decimal(str(d_p01["gasto_promedio_individuo"])) == Decimal("1000") if d_p01.get("gasto_promedio_individuo") not in (None, "NO_CALCULABLE") else False
        tot_p01_dec = Decimal(str(d_p01["gasto_total_acumulado"])) == Decimal("50000") if d_p01.get("gasto_total_acumulado") is not None else False
        ok_p01 = r_p01.status_code == 200 and tot_p01_dec and prom_p01_dec and d_p01.get("causa_no_calculable_promedio") is None
        resultados["pasos"].append({
            "id": "P01",
            "origen": "[especificación]",
            "esperado": "200, total 50000, promedio 1000 (decimal, no string)",
            "veredicto": "OK" if ok_p01 else "FALLA",
            "detalle_tipo_json": f"tipo JSON recibido={d_p01.get('gasto_promedio_tipo_json')}",
            **d_p01,
        })
        id_r1 = d_p01["id_reporte"]

        # P02: Baja de los 50 individuos (cantidad_actual = 0)
        r_p02 = c.req(
            "POST",
            f"/activos-biologicos/{id_l1}/eventos/baja",
            json={
                "tipo_baja": "muerte",
                "fecha_baja": fecha_hoy,
                "motivo_baja": "Muerte total diagnostico QA G20",
                "cantidad_afectada": 50,
            },
        )
        r_l1_post_baja = c.req("GET", f"/activos-biologicos/{id_l1}")
        l1_after = r_l1_post_baja.json() if r_l1_post_baja.status_code == 200 else {}
        cant_l1_baja = _cantidad_actual_de_resp(r_l1_post_baja)
        ok_p02 = r_p02.status_code == 201 and cant_l1_baja == 0
        resultados["pasos"].append({
            "id": "P02",
            "origen": "[especificación]",
            "esperado": "201, cantidad_actual = 0",
            "http": r_p02.status_code,
            "error_code": (r_p02.json().get("error_code") if r_p02.headers.get("content-type", "").startswith("application/json") else None),
            "cantidad_actual": cant_l1_baja,
            "estado_activo": l1_after.get("id_estado"),
            "x_request_id": r_p02.headers.get("X-Request-ID"),
            "veredicto": "OK" if ok_p02 else "FALLA",
        })

        # P03: Reporte R2 -> 200, promedio "NO_CALCULABLE" (string), causa informada, nota de 50 bajas
        r_p03 = c.req("POST", "/suministros/reportes-gastos", json=payload_rep_l1)
        d_p03 = _extraer_campos_reporte(r_p03, cant_l1_baja)
        nota_p03 = d_p03.get("nota_bajas") or ""
        ok_p03 = (
            r_p03.status_code == 200
            and d_p03.get("gasto_promedio_individuo") == "NO_CALCULABLE"
            and isinstance(d_p03.get("gasto_promedio_individuo"), str)
            and bool(d_p03.get("causa_no_calculable_promedio"))
            and "50 bajas" in nota_p03
        )
        resultados["pasos"].append({
            "id": "P03",
            "origen": "[especificación R6]",
            "esperado": "200, promedio 'NO_CALCULABLE' (str), causa informada, nota 50 bajas",
            "veredicto": "OK" if ok_p03 else "FALLA",
            **d_p03,
        })
        id_r2 = d_p03["id_reporte"]

        # P04: Consultar snapshot de R2 -> "NO_CALCULABLE" + causa
        r_p04 = c.req("GET", f"/suministros/reportes-gastos/{id_r2}")
        if r_p04.status_code in (404, 405, 501):
            resultados["pasos"].append({
                "id": "P04",
                "origen": "[contrato Dev]",
                "esperado": "snapshot R2: 'NO_CALCULABLE' + causa",
                "http": r_p04.status_code,
                "x_request_id": r_p04.headers.get("X-Request-ID"),
                "veredicto": "NO_DISPONIBLE",
            })
        else:
            d_p04 = _extraer_campos_reporte(r_p04, cant_l1_baja)
            ok_p04 = (
                r_p04.status_code == 200
                and d_p04.get("gasto_promedio_individuo") == "NO_CALCULABLE"
                and d_p04.get("causa_no_calculable_promedio") == d_p03.get("causa_no_calculable_promedio")
            )
            resultados["pasos"].append({
                "id": "P04",
                "origen": "[contrato Dev]",
                "esperado": "200, snapshot R2 con 'NO_CALCULABLE' + causa",
                "veredicto": "OK" if ok_p04 else "HALLAZGO_DEV",
                **d_p04,
            })

        # P05: Consultar snapshot de R1 -> promedio original 1000, sin causa
        r_p05 = c.req("GET", f"/suministros/reportes-gastos/{id_r1}")
        if r_p05.status_code in (404, 405, 501):
            resultados["pasos"].append({
                "id": "P05",
                "origen": "[contrato Dev]",
                "esperado": "snapshot R1: promedio original 1000, sin causa",
                "http": r_p05.status_code,
                "x_request_id": r_p05.headers.get("X-Request-ID"),
                "veredicto": "NO_DISPONIBLE",
            })
        else:
            d_p05 = _extraer_campos_reporte(r_p05, cant_l1_inicial)
            prom_p05_ok = (
                d_p05.get("gasto_promedio_individuo") not in (None, "NO_CALCULABLE")
                and Decimal(str(d_p05["gasto_promedio_individuo"])) == Decimal("1000")
            )
            ok_p05 = r_p05.status_code == 200 and prom_p05_ok and d_p05.get("causa_no_calculable_promedio") is None
            resultados["pasos"].append({
                "id": "P05",
                "origen": "[contrato Dev]",
                "esperado": "200, snapshot R1 promedio original 1000, sin causa",
                "veredicto": "OK" if ok_p05 else "HALLAZGO_DEV",
                **d_p05,
            })

        # P06: Historial de reportes -> R1 y R2 con los valores de P05 y P04
        r_p06 = c.req("GET", "/suministros/reportes-gastos/historial", params={"limite": 20})
        if r_p06.status_code in (404, 405, 501):
            resultados["pasos"].append({
                "id": "P06",
                "origen": "[contrato Dev]",
                "esperado": "200, R1 y R2 en historial con valores de P05 y P04",
                "http": r_p06.status_code,
                "x_request_id": r_p06.headers.get("X-Request-ID"),
                "veredicto": "NO_DISPONIBLE",
            })
        else:
            h_body = r_p06.json() if r_p06.status_code == 200 else {}
            h_items = h_body if isinstance(h_body, list) else h_body.get("items", [])
            by_id = {it.get("id_reporte_gasto_acumulado"): it for it in h_items if isinstance(it, dict)}
            it_r1 = by_id.get(id_r1)
            it_r2 = by_id.get(id_r2)
            r1_ok = (
                it_r1 is not None
                and it_r1.get("gasto_promedio_individuo") not in (None, "NO_CALCULABLE")
                and Decimal(str(it_r1["gasto_promedio_individuo"])) == Decimal("1000")
                and it_r1.get("causa_no_calculable_promedio") is None
            )
            r2_ok = (
                it_r2 is not None
                and it_r2.get("gasto_promedio_individuo") == "NO_CALCULABLE"
                and bool(it_r2.get("causa_no_calculable_promedio"))
            )
            resultados["pasos"].append({
                "id": "P06",
                "origen": "[contrato Dev]",
                "esperado": "200, historial contiene R1 (1000, sin causa) y R2 ('NO_CALCULABLE' + causa)",
                "http": r_p06.status_code,
                "error_code": h_body.get("error_code") if isinstance(h_body, dict) else None,
                "total_historial": h_body.get("total") if isinstance(h_body, dict) else len(h_items),
                "r1_en_historial": {
                    "id_reporte": id_r1,
                    "gasto_promedio_individuo": it_r1.get("gasto_promedio_individuo") if it_r1 else None,
                    "causa_no_calculable_promedio": it_r1.get("causa_no_calculable_promedio") if it_r1 else None,
                } if it_r1 else None,
                "r2_en_historial": {
                    "id_reporte": id_r2,
                    "gasto_promedio_individuo": it_r2.get("gasto_promedio_individuo") if it_r2 else None,
                    "causa_no_calculable_promedio": it_r2.get("causa_no_calculable_promedio") if it_r2 else None,
                } if it_r2 else None,
                "x_request_id": r_p06.headers.get("X-Request-ID"),
                "veredicto": "OK" if (r_p06.status_code == 200 and r1_ok and r2_ok) else "HALLAZGO_DEV",
            })

        # P07: Regenerar R1 -> "NO_CALCULABLE" + causa (poblacion actual) y advertencia de regeneracion del RNF
        r_p07 = c.req("GET", f"/suministros/reportes-gastos/{id_r1}/regenerar")
        if r_p07.status_code in (404, 405, 501):
            resultados["pasos"].append({
                "id": "P07",
                "origen": "[especificación RNF + Dev]",
                "esperado": "200, 'NO_CALCULABLE' + causa y advertencia de regeneracion RNF",
                "http": r_p07.status_code,
                "x_request_id": r_p07.headers.get("X-Request-ID"),
                "veredicto": "NO_DISPONIBLE",
            })
        else:
            d_p07 = _extraer_campos_reporte(r_p07, cant_l1_baja)
            ok_p07 = (
                r_p07.status_code == 200
                and d_p07.get("gasto_promedio_individuo") == "NO_CALCULABLE"
                and bool(d_p07.get("causa_no_calculable_promedio"))
                and bool(d_p07.get("advertencia"))
            )
            resultados["pasos"].append({
                "id": "P07",
                "origen": "[especificación RNF + Dev]",
                "esperado": "200, 'NO_CALCULABLE' + causa y advertencia de regeneracion RNF",
                "veredicto": "OK" if ok_p07 else "HALLAZGO_DEV",
                **d_p07,
            })

        # P08: Reporte de activo INDIVIDUAL (activo 853 con medicamento periodo_retiro_dias=0 y fase abierta) -> promedio null
        r_f853 = c.req(
            "POST",
            "/activos-biologicos/853/fases",
            json={
                "id_ciclo_productiva": 5,
                "motivo_cambio": "Apertura fase diag P08 activo 853",
                "fecha_inicio": f"{fecha_ciclo}T05:00:00Z",
            },
        )
        assert r_f853.status_code in (200, 201), f"Fase 853 P08 HTTP {r_f853.status_code}: {r_f853.text[:200]}"
        r_m853 = c.req(
            "POST",
            "/suministros/medicamentos",
            json={
                "id_activo_biologico": 853,
                "nombre_medicamento": "Oxitetraciclina Diag P08",
                "via_administracion": "INTRAMUSCULAR",
                "dosis_aplicada": 10.0,
                "unidad_dosis": "ml",
                "fecha_aplicacion": fecha_hoy,
                "hora_aplicacion": "09:15:00",
                "costo_unitario": 1000.0,
                "periodo_retiro_dias": 0,
                "motivo_aplicacion": "Control sanitario diagnostico G20 P08",
                "nombre_veterinario": "Dr. QA Veterinario",
            },
        )
        assert r_m853.status_code == 201, f"Med 853 P08 HTTP {r_m853.status_code}: {r_m853.text[:250]}"
        r_g853 = c.req("GET", "/activos-biologicos/853")
        cant_853 = _cantidad_actual_de_resp(r_g853)
        r_p08 = c.req(
            "POST",
            "/suministros/reportes-gastos",
            json={
                "activo_biologico_id": 853,
                "fecha_inicio_reporte": fecha_ciclo,
                "fecha_fin_reporte": fecha_hoy,
                "tipo_periodo": "MENSUAL",
            },
        )
        d_p08 = _extraer_campos_reporte(r_p08, cant_853)
        ok_p08 = (
            r_p08.status_code == 200
            and d_p08.get("gasto_promedio_individuo") is None
            and d_p08.get("causa_no_calculable_promedio") is None
        )
        resultados["pasos"].append({
            "id": "P08",
            "origen": "[contrato Dev]",
            "esperado": "200, activo INDIVIDUAL 853 -> gasto_promedio_individuo null, sin causa",
            "veredicto": "OK" if ok_p08 else "HALLAZGO_DEV",
            **d_p08,
        })

        # P09: Regresion: otro lote de 100 individuos con 1.000.000 COP -> promedio 10000 (decimal)
        id_l2, cant_l2 = _crear_lote_y_gasto(c, "L2", 100, fecha_ciclo, fecha_hoy, 100.0, 10000.0)
        resultados["id_lote_2"] = id_l2
        r_p09 = c.req(
            "POST",
            "/suministros/reportes-gastos",
            json={
                "activo_biologico_id": id_l2,
                "fecha_inicio_reporte": fecha_ciclo,
                "fecha_fin_reporte": fecha_hoy,
                "tipo_periodo": "MENSUAL",
            },
        )
        d_p09 = _extraer_campos_reporte(r_p09, cant_l2)
        prom_p09_ok = (
            d_p09.get("gasto_promedio_individuo") not in (None, "NO_CALCULABLE")
            and Decimal(str(d_p09["gasto_promedio_individuo"])) == Decimal("10000")
        )
        tot_p09_ok = (
            d_p09.get("gasto_total_acumulado") is not None
            and Decimal(str(d_p09["gasto_total_acumulado"])) == Decimal("1000000")
        )
        ok_p09 = r_p09.status_code == 200 and tot_p09_ok and prom_p09_ok and d_p09.get("causa_no_calculable_promedio") is None
        resultados["pasos"].append({
            "id": "P09",
            "origen": "[caso G20 subcaso 2]",
            "esperado": "200, total 1000000, promedio 10000 (decimal)",
            "veredicto": "OK" if ok_p09 else "FALLA",
            "detalle_tipo_json": f"tipo JSON recibido={d_p09.get('gasto_promedio_tipo_json')}",
            **d_p09,
        })

        resultados["async_polling_nota"] = "No probado (requiere > 12 meses); fuera de alcance, ver G24."
    except BaseException as exc:
        orig_err = exc
    finally:
        teardown = c.close()
        resultados["teardown"] = teardown
        resultados["inocuidad"] = _INOCUIDAD
        OUT_JSON.write_text(json.dumps(resultados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if orig_err is not None:
            raise orig_err
        assert teardown.get("http") == 200 and "Rollback exitoso" in teardown.get("body", "")

    # Verificar P01-P03 y P09 obligatorios; hallazgos Dev en P04-P08 quedan registrados
    for paso in resultados["pasos"]:
        if paso["id"] in ("P01", "P02", "P03", "P09"):
            assert paso["veredicto"] == "OK", f"Fallo en {paso['id']}: {paso}"


def test_02_diag_inocuidad_final() -> None:
    """Verifica que historial_total final coincide exactamente con la linea base tras rollback."""
    c = SandboxDiagClient("diag-g20-fin")
    orig_err: BaseException | None = None
    try:
        c.login_admin()
        total_final, meta = _conteo_historial(c)
        _INOCUIDAD["final"] = {"historial_total": total_final, **meta}
    except BaseException as exc:
        orig_err = exc
    finally:
        teardown = c.close()
        _INOCUIDAD["teardown_final"] = teardown
        # Actualizar diag_resultados.json con inocuidad final
        if OUT_JSON.exists():
            data = json.loads(OUT_JSON.read_text(encoding="utf-8"))
            data["inocuidad"] = _INOCUIDAD
            OUT_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if orig_err is not None:
            raise orig_err
        assert teardown.get("http") == 200 and "Rollback exitoso" in teardown.get("body", "")

    assert _INOCUIDAD["final"]["historial_total"] == _INOCUIDAD["base"]["historial_total"], (
        f"Inocuidad fallida: base={_INOCUIDAD['base']} != final={_INOCUIDAD['final']}"
    )
