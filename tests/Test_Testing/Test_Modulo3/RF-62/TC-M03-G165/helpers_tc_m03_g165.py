"""helpers_tc_m03_g165.py — Funciones auxiliares y cliente Sandbox para TC-M03-G165.

Contiene:
- Cliente HTTP Sandbox (inyecta X-Test-Run-Id y X-Sandbox-Secret en todas las peticiones).
- Generación determinista de series cronológicas espaciadas.
- Cálculo de offset para drift desde la media real almacenada.
- Cálculo de valor para forzar outlier estadístico.
- Teardown idempotente de sandbox.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Optional
import sys
from pathlib import Path
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
    for k in ("TEST_BASE_URL", "ENABLE_TEST_SANDBOX", "TEST_SANDBOX_SECRET", "TEST_ADMIN_PASSWORD", "TEST_ADMIN_EMAIL"):
        val = os.environ.get(k) or env_vars.get(k)
        if val:
            env_vars[k] = val

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
    """Cliente HTTP que envuelve peticiones con contexto transaccional Sandbox."""

    def __init__(self, base_url: str, run_id: str, secret: str, token: Optional[str] = None):
        self.base_url = base_url.rstrip("/")
        self.run_id = run_id
        self.secret = secret
        self.token = token

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

    def get(self, path: str, headers: Optional[dict] = None, params: Optional[dict] = None) -> requests.Response:
        url = f"{self.base_url}/{path.lstrip('/')}"
        return requests.get(url, headers=self._headers(headers), params=params, timeout=15)

    def post(self, path: str, json: Optional[Any] = None, headers: Optional[dict] = None) -> requests.Response:
        url = f"{self.base_url}/{path.lstrip('/')}"
        return requests.post(url, json=json, headers=self._headers(headers), timeout=15)

    def delete(self, path: str, headers: Optional[dict] = None) -> requests.Response:
        url = f"{self.base_url}/{path.lstrip('/')}"
        return requests.delete(url, headers=self._headers(headers), timeout=15)

    def query_sql(self, sql: str) -> list[dict]:
        """Ejecuta una consulta SELECT pura en /test-control/query dentro del sandbox."""
        resp = self.post("test-control/query", json={"query": sql})
        if resp.status_code != 200:
            raise RuntimeError(f"Error en query sandbox ({resp.status_code}): {resp.text}")
        data = resp.json().get("data", [])
        return data

    def teardown_rollback(self) -> tuple[int, dict]:
        """Ejecuta DELETE /test-control/runs/{run_id} de forma idempotente."""
        resp = self.delete(f"test-control/runs/{self.run_id}")
        try:
            body = resp.json()
        except Exception:
            body = {"raw": resp.text}
        return resp.status_code, body


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
    """Calcula el offset necesario para inducir un drift relativo objetivo d.
    
    Fórmula:
      con ganancia g = 1.0:
      val_cal_esperado = media_real + offset
      magnitud_drift = |media_real - val_cal_esperado| / |val_cal_esperado| = d
      
      Si val_cal_esperado = media_real / (1 + d), entonces:
      offset = - (d * media_real) / (1 + d)
    """
    d = float(drift_objetivo)
    mu = float(media_real_serie)
    offset = -(d * mu) / (1.0 + d)
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
