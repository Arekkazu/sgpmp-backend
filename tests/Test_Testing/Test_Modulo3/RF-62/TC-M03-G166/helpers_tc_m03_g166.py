"""helpers_tc_m03_g166.py — Clientes y funciones auxiliares para TC-M03-G166.

Contiene:
- Carga segura de configuración de entorno (.env.test / os.environ) sin exponer secretos.
- SandboxClient (inyecta X-Test-Run-Id y X-Sandbox-Secret en todas las peticiones HTTP).
- Generador determinista del dataset de 41 lecturas (B1..B20 + I1..I21) con Decimal.
- Replicación local del cálculo de ventanas del motor para verificación estática sin red.
- Teardown idempotente del Sandbox (DELETE /test-control/runs/{run_id}).
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

_DIR = Path(__file__).resolve().parent
if str(_DIR) not in sys.path:
    sys.path.insert(0, str(_DIR))

from spec_tc_m03_g166 import SpecTCM03G166


class SandboxConfigError(Exception):
    """Lanzada cuando falta una variable requerida sin exponer secretos."""
    pass


def cargar_configuracion_entorno(env_path: Optional[str] = None) -> dict[str, str]:
    """Carga y valida las variables requeridas desde el entorno o .env.test.

    Si falta alguna variable requerida, falla con mensaje claro SIN imprimir valores.
    """
    env_vars: dict[str, str] = {}

    root_env_test = env_path or os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../../.env.test"))
    if root_env_test and os.path.exists(root_env_test):
        with open(root_env_test, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env_vars[k.strip()] = v.strip()

    for k in (
        "TEST_BASE_URL",
        "ENABLE_TEST_SANDBOX",
        "TEST_SANDBOX_SECRET",
        "TEST_ADMIN_PASSWORD",
        "TEST_ADMIN_EMAIL",
    ):
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
        return requests.post(url, json=json, headers=self._headers(headers), timeout=45)  # aumento desde 15s: contención de triggers tras 41 inserts (ver INC-M03-G166-LATENCY)

    def delete(self, path: str, headers: Optional[dict] = None) -> requests.Response:
        url = f"{self.base_url}/{path.lstrip('/')}"
        return requests.delete(url, headers=self._headers(headers), timeout=15)

    def execute_query(self, sql_query: str) -> requests.Response:
        """Ejecuta una consulta SELECT mediante /test-control/query."""
        return self.post("test-control/query", json={"query": sql_query})


def extraer_filas(resp: Any) -> list[dict]:
    """Extrae la lista de filas de una respuesta de consulta SQL (/test-control/query).

    Tolera respuestas dict, requests.Response (o mocks con .json()) o list, buscando las claves 'rows', 'data' o 'result'.
    """
    if hasattr(resp, "json") and callable(resp.json):
        try:
            resp = resp.json()
        except Exception:
            raise AssertionError(f"Respuesta no es JSON válido")
    if isinstance(resp, list):
        return resp
    if isinstance(resp, dict):
        for k in ("rows", "data", "result"):
            if k in resp and isinstance(resp[k], list):
                return resp[k]
        raise AssertionError(f"Respuesta sin filas reconocidas: {list(resp.keys())}")
    raise AssertionError(f"Tipo de respuesta no soportado: {type(resp)}")


def obtener_token_admin(base_url: str, email: str, password: str, run_id: str, secret: str) -> str:
    """Autentica contra /sesiones/ dentro del sandbox para obtener un Bearer token."""
    client = SandboxClient(base_url, run_id, secret)
    resp = client.post(
        "sesiones/",
        json={"correo_electronico": email, "contrasena": password},
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Fallo de autenticación admin: HTTP {resp.status_code} - {resp.text}")
    data = resp.json()
    token = (
        data.get("token")
        or data.get("access_token")
        or (data.get("data", {}) if isinstance(data.get("data"), dict) else {}).get("access_token")
        or (data.get("data", {}) if isinstance(data.get("data"), dict) else {}).get("token")
    )
    if not token:
        raise RuntimeError(f"Respuesta de login sin access_token o token: {data}")
    return token


# ── RECETA Y CONSTRUCCIÓN DE LA SERIE DE DATOS ───────────────────────────────

def generar_dataset_g166(
    base: Decimal = SpecTCM03G166.VALOR_BASE,
    tiempo_fin: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
    """Construye las 41 lecturas con Decimal uniforme y espaciado de 10 min.

    Estructura:
    - 20 lecturas distintas B1..B20: base ± δ (10 pares alternados)
    - 21 lecturas idénticas I1..I21: valor constante base (25.40)
    
    Cada lectura contiene:
    - indice_serie: 1..41
    - etiqueta: 'B1'..'B20' / 'I1'..'I21'
    - valor: Decimal con dos decimales exactos
    - valor_str: f"{valor:.2f}"
    - timestamp_captura: datetime UTC
    - es_identica: bool
    """
    if tiempo_fin is None:
        # Por defecto: anclado 5 minutos antes de ahora para holgura de 300 s
        tiempo_fin = datetime.now(timezone.utc) - timedelta(minutes=5)

    deltas = [
        Decimal("0.15"), Decimal("0.25"), Decimal("0.35"), Decimal("0.45"), Decimal("0.55"),
        Decimal("0.65"), Decimal("0.75"), Decimal("0.85"), Decimal("0.95"), Decimal("1.05"),
    ]

    valores_distintos: List[Decimal] = []
    for d in deltas:
        valores_distintos.append(base + d)
        valores_distintos.append(base - d)

    valores_identicos = [base] * 21

    total_lecturas = 41
    items: List[Dict[str, Any]] = []

    # Tiempos hacia atrás: lectura 41 es tiempo_fin; lectura 1 es tiempo_fin - 40 * 10 min
    for i in range(total_lecturas):
        pos = i + 1
        ts = tiempo_fin - timedelta(minutes=(total_lecturas - pos) * SpecTCM03G166.MUESTREO_MINUTOS)
        if pos <= 20:
            val = valores_distintos[pos - 1]
            etiqueta = f"B{pos}"
            es_id = False
        else:
            val = valores_identicos[pos - 21]
            etiqueta = f"I{pos - 20}"
            es_id = True

        items.append({
            "posicion": pos,
            "etiqueta": etiqueta,
            "valor": val,
            "valor_str": f"{val:.2f}",
            "timestamp_captura": ts,
            "es_identica": es_id,
        })

    return items


def simular_ventana_motor(dataset: List[Dict[str, Any]], etiqueta_evaluada: str) -> List[Decimal]:
    """Extrae las N=20 lecturas previas que recuperaría el motor para una lectura evaluada.

    Regla exacta del repositorio (telemetria_repository.py:121-129):
    SELECT valor_crudo FROM telemetrias
    WHERE id_sensor = :s AND estado_calidad = 'LECTURA_VALIDA' AND timestamp_captura < :ts
    ORDER BY timestamp_captura DESC LIMIT 20
    """
    eval_item = next(it for it in dataset if it["etiqueta"] == etiqueta_evaluada)
    ts_eval = eval_item["timestamp_captura"]

    # Filtrar lecturas estrictamente anteriores ordenadas de más reciente a más antigua
    previas = [it for it in dataset if it["timestamp_captura"] < ts_eval]
    previas_desc = sorted(previas, key=lambda it: it["timestamp_captura"], reverse=True)
    serie_20 = previas_desc[:SpecTCM03G166.N]
    return [it["valor"] for it in serie_20]


def evaluar_congelado_local(serie: List[Decimal], m: int = SpecTCM03G166.M) -> Tuple[bool, Optional[str], int]:
    """Replicación pura de la Fase 2 de EvaluarCalidadTelemetriaUseCase:131-147."""
    ultimas_m = serie[:m]
    if len(ultimas_m) == m and len(set(str(v) for v in ultimas_m)) == 1:
        repeticiones = sum(1 for v in serie if v == ultimas_m[0])
        if repeticiones >= 20:
            sev = "CRITICO"
        elif repeticiones >= 10:
            sev = "MODERADO"
        else:
            sev = "LEVE"
        return True, sev, repeticiones
    return False, None, 0


def cerrar_run_sandbox_idempotente(client: SandboxClient) -> bool:
    """Cierra el run de sandbox de forma idempotente: tolera 404 (ya cerrado)."""
    try:
        resp = client.delete(f"test-control/runs/{client.run_id}")
        return resp.status_code in (200, 404)
    except Exception:
        return False
