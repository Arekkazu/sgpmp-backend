"""helpers_tc_m03_g165.py — Funciones auxiliares y cliente Sandbox para TC-M03-G165.

Contiene:
- Cliente HTTP Sandbox (inyecta X-Test-Run-Id y X-Sandbox-Secret en todas las peticiones).
- Ingesta en lote (batch) de lecturas de telemetría.
- Consulta de frecuencia de muestreo activa (solo lectura) y cálculo dinámico de gap mínimo.
- Generación determinista de series cronológicas espaciadas.
- Cálculo de offset positivo para drift desde la media real almacenada.
- Cálculo de valor para forzar outlier estadístico.
- Teardown idempotente de sandbox con reintento ante timeout.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Optional

import requests

_DIR = Path(__file__).resolve().parent
if str(_DIR) not in sys.path:
    sys.path.insert(0, str(_DIR))

from spec_tc_m03_g165 import SpecParametrosBase


class SandboxConfigError(Exception):
    """Lanzada cuando falta una variable de entorno requerida sin exponer secretos."""
    pass


def cargar_configuracion_entorno() -> dict[str, str]:
    """Carga y valida las variables requeridas desde el entorno o .env.test.
    
    Si falta alguna variable requerida, falla con mensaje claro SIN imprimir valores.
    """
    env_vars: dict[str, str] = {}
    
    # Si existe .env.test en la raíz del workspace, leerlo de respaldo
    root_env_test = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../../.env.test"))
    if os.path.exists(root_env_test):
        with open(root_env_test, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env_vars[k.strip()] = v.strip()

    # Prevalecen las variables de os.environ si existen
    for k in (
        "TEST_BASE_URL",
        "ENABLE_TEST_SANDBOX",
        "TEST_SANDBOX_SECRET",
        "TEST_ADMIN_PASSWORD",
        "TEST_ADMIN_EMAIL",
        "BROKER_SERVICE_TOKEN",
    ):
        val = os.environ.get(k) or env_vars.get(k)
        if val:
            env_vars[k] = val
            if not os.environ.get(k):
                os.environ[k] = val

    requeridas = ["TEST_BASE_URL", "ENABLE_TEST_SANDBOX", "TEST_SANDBOX_SECRET", "TEST_ADMIN_PASSWORD"]
    faltantes = [k for k in requeridas if not env_vars.get(k)]
    if faltantes:
        raise SandboxConfigError(
            f"Faltan variables requeridas de testing: {', '.join(faltantes)}. "
            "Configure el archivo .env.test o variables de entorno del sistema."
        )

    # Validar cuenta administrativa autorizada
    email = env_vars.get("TEST_ADMIN_EMAIL", "administador.dev@gmail.com")
    if "admin@pecuaria.co" in email:
        raise SandboxConfigError("Cuenta no autorizada para el set: NO uses admin@pecuaria.co.")

    env_vars["TEST_ADMIN_EMAIL"] = email
    return env_vars


class SandboxClient:
    """Cliente HTTP que envuelve peticiones con contexto transaccional Sandbox.

    Timeout subido a 45s en Fase 4b para tolerar latencia de RDS TEST
    bajo carga (INC-M03-G166-LATENCY).
    """

    DEFAULT_TIMEOUT = 45
    TEARDOWN_TIMEOUT = 60

    def __init__(
        self,
        base_url: str,
        run_id: str,
        secret: str,
        token: Optional[str] = None,
        admin_email: Optional[str] = None,
        timeout: Optional[int] = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.run_id = run_id
        self.secret = secret
        self.token = token
        self.timeout = timeout or self.DEFAULT_TIMEOUT
        self.admin_email = (
            admin_email
            or os.environ.get("TEST_ADMIN_EMAIL")
            or "administador.dev@gmail.com"
        )

    def _headers(self, headers: Optional[dict] = None) -> dict:
        h = {
            "X-Test-Run-Id": self.run_id,
            "X-Sandbox-Secret": self.secret,
            "Content-Type": "application/json",
        }
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        if headers:
            h.update(headers)
        return h

    def get(
        self,
        path: str,
        headers: Optional[dict] = None,
        params: Optional[dict] = None,
        timeout: Optional[int] = None,
    ) -> requests.Response:
        url = f"{self.base_url}/{path.lstrip('/')}"
        return requests.get(
            url,
            headers=self._headers(headers),
            params=params,
            timeout=timeout or self.timeout,
        )

    def post(
        self,
        path: str,
        json: Optional[Any] = None,
        headers: Optional[dict] = None,
        timeout: Optional[int] = None,
    ) -> requests.Response:
        url = f"{self.base_url}/{path.lstrip('/')}"
        return requests.post(
            url,
            json=json,
            headers=self._headers(headers),
            timeout=timeout or self.timeout,
        )

    def delete(
        self,
        path: str,
        headers: Optional[dict] = None,
        timeout: Optional[int] = None,
    ) -> requests.Response:
        url = f"{self.base_url}/{path.lstrip('/')}"
        return requests.delete(
            url,
            headers=self._headers(headers),
            timeout=timeout or self.timeout,
        )

    def query_sql(self, sql: str) -> list[dict]:
        """Ejecuta una consulta SELECT pura en /test-control/query dentro del sandbox con contexto RLS."""
        sql_clean = sql.strip().rstrip(";")
        email_rls = self.admin_email.replace("'", "''")
        sql_envuelto = (
            "SELECT _q.* FROM ("
            "SELECT set_config('app.current_role', 'Administrador', true) AS r, "
            "set_config('app.current_user_id', "
            f"(SELECT modulo1.fn_id_usuario_por_correo('{email_rls}')::text), true) AS u"
            f") _rls CROSS JOIN LATERAL ({sql_clean}) _q "
            "WHERE _rls.r != '' AND _rls.u != ''"
        )
        resp = self.post("test-control/query", json={"query": sql_envuelto})
        if resp.status_code != 200:
            raise RuntimeError(f"Error en query sandbox ({resp.status_code}): {resp.text}")
        data = resp.json().get("data", [])
        return data

    def teardown_rollback(self) -> tuple[int, dict]:
        """Ejecuta DELETE /test-control/runs/{run_id} de forma idempotente con reintento ante timeout."""
        try:
            resp = self.delete(f"test-control/runs/{self.run_id}", timeout=self.TEARDOWN_TIMEOUT)
        except requests.exceptions.Timeout:
            resp = self.delete(f"test-control/runs/{self.run_id}", timeout=90)
        try:
            body = resp.json()
        except Exception:
            body = {"raw": resp.text}
        return resp.status_code, body


# ── HELPERS DE INGESTA BATCH Y FRECUENCIA DINÁMICA (FASE 4b) ────────────────

def ingerir_telemetria_batch(sandbox: SandboxClient, registros: list[dict]) -> requests.Response:
    """Ingesta múltiples lecturas en un solo request (máx 500).
    Payload: {"registros": [...], "idempotency_key": None}
    """
    broker_token = os.getenv("BROKER_SERVICE_TOKEN")
    if not broker_token:
        raise RuntimeError("BROKER_SERVICE_TOKEN no configurado en el ambiente")
    resp = sandbox.post(
        "/iot/telemetria/batch",
        json={
            "registros": registros,
            "idempotency_key": None,
        },
        headers={"Authorization": f"Bearer {broker_token}"},
        timeout=45,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Fallo en ingesta batch ({resp.status_code}): {resp.text}")
    body = resp.json()
    if body.get("aceptados") != len(registros):
        raise RuntimeError(
            f"Ingesta batch incompleta: esperados={len(registros)}, aceptados={body.get('aceptados')}, "
            f"rechazados={body.get('rechazados')}, duplicados={body.get('duplicados')}"
        )
    return resp


def obtener_frecuencia_actual(sandbox: SandboxClient) -> int:
    """Lee frecuencia_muestreo de la configuración global (solo lectura).
    No modifica nada, no bloquea.
    """
    r = sandbox.get("/configuracion/parametros", timeout=30)
    assert r.status_code == 200, f"GET /configuracion/parametros falló: {r.status_code}"
    data = r.json()
    if isinstance(data, list):
        data = data[0] if data else {}
    return int(data.get("frecuencia_muestreo", 45))


def calcular_gap_minimo(frecuencia_min: int) -> int:
    """Gap mínimo para activar gap_temporal_anomalo.
    Regla: gap > 2 * frecuencia. Añadimos +5 de margen para robustez.
    """
    return 2 * frecuencia_min + 5


# ── GENERACIÓN DETERMINISTA DE SERIES Y CÁLCULOS ESTADÍSTICOS ────────────────

def generar_serie_temporal_determinista(
    t_referencia: datetime,
    valores: list[float],
    intervalo_min: int = SpecParametrosBase.intervalo_muestreo_min,
) -> list[dict]:
    """Genera una lista de tuplas (timestamp_iso, valor_str) espaciadas hacia el pasado.
    
    t_referencia es la fecha base de la lectura más reciente de la serie.
    Para una serie de 20 lecturas con intervalo de 10 min:
      lectura i (1..N): t_referencia - (N - i) * intervalo_min
    """
    n = len(valores)
    serie_payload = []
    for i, val in enumerate(valores):
        minutos_atras = (n - 1 - i) * intervalo_min
        ts = t_referencia - timedelta(minutes=minutos_atras)
        serie_payload.append({
            "timestamp": ts.isoformat(),
            "valor": round(float(val), 2),
            "valor_str": f"{round(float(val), 2):.2f}",
        })
    return serie_payload


def calcular_offset_para_drift(media_real_serie: float, drift_objetivo: float) -> float:
    """Calcula offset POSITIVO dentro de [0, 45] para inducir drift relativo d.

    Con ganancia = 1.0 y val_cal = mu + offset = mu / (1 - d):
      abs(val_cal - mu) / abs(val_cal) = d
    Para mu=20, d=0.07 -> +1.5054; para d=0.15 -> +3.5294.
    """
    d = float(drift_objetivo)
    mu = float(media_real_serie)
    offset = (d * mu) / (1.0 - d)
    return round(offset, 4)


def calcular_valor_outlier_crudo(
    media_serie: float,
    sigma_serie: float,
    multiplicador_sigma: float = SpecParametrosBase.outlier_mult_sigma,
    offset_actual: float = 0.0,
    ganancia_actual: float = 1.0,
) -> float:
    """Calcula el valor a enviar para forzar un outlier estadístico (|v - mu| > k * sigma).
    
    Ajuste 1: Dado que el motor compara el `valor_crudo` guardado por la ingesta:
      En `obtener_serie_temporal` se selecciona `valor_crudo`.
      En `calidad_router.py` se envía `valor = Decimal(str(row[2]))` (valor_crudo).
      Por tanto, el valor evaluado en Fase 3 es directamente el valor enviado en la ingesta.
      Si en el futuro la ingesta aplicara calibración al crudo, se neutraliza despejando.
    """
    mu = float(media_serie)
    sigma = float(sigma_serie)
    if sigma == 0:
        # Si sigma es 0, se define un delta determinista positivo
        objetivo = mu + 6.0
    else:
        objetivo = mu + (multiplicador_sigma * sigma)

    return round(objetivo, 2)
