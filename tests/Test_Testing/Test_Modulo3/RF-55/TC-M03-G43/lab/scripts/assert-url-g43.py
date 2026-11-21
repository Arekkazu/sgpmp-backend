"""Guardia de laboratorio G43: rechaza cualquier URL que no sea sgpmp_g43_test:5439.

No imprime la URL ni secretos. No altera el backend de producción.
"""
from __future__ import annotations

import os
import sys
from urllib.parse import urlparse

PROHIBIDOS = {"sgpmp", "sgpmp_pr14_test"}
NOMBRE = "sgpmp_g43_test"
PUERTO = 5439


def validar(url: str, etiqueta: str) -> list[str]:
    errores: list[str] = []
    if not url:
        return [f"{etiqueta} vacia"]
    parsed = urlparse(url.replace("postgresql+psycopg2", "postgresql").replace("postgresql+asyncpg", "postgresql"))
    nombre = (parsed.path or "/").lstrip("/").split("?")[0]
    host = parsed.hostname or ""
    puerto = parsed.port
    if nombre in PROHIBIDOS:
        errores.append(f"{etiqueta}: nombre de base prohibido")
    if nombre != NOMBRE:
        errores.append(f"{etiqueta}: no es {NOMBRE}")
    if host not in {"127.0.0.1", "localhost"}:
        errores.append(f"{etiqueta}: host no es loopback")
    if puerto != PUERTO:
        errores.append(f"{etiqueta}: puerto no es {PUERTO}")
    return errores


def main() -> int:
    errores: list[str] = []
    for clave in ("DATABASE_URL", "ALEMBIC_DATABASE_URL", "TEST_DATABASE_URL"):
        valor = os.environ.get(clave, "")
        if clave != "DATABASE_URL" and not valor:
            continue
        errores.extend(validar(valor, clave))
    db = os.environ.get("POSTGRES_DB", NOMBRE)
    if db != NOMBRE:
        errores.append("POSTGRES_DB distinto de sgpmp_g43_test")
    if os.environ.get("MQTT_HOST", "127.0.0.1") not in {"127.0.0.1", "localhost"}:
        errores.append("MQTT_HOST no es loopback")
    if os.environ.get("MQTT_PORT", "1884") not in {"1884"}:
        errores.append("MQTT_PORT no es 1884")
    backend = os.environ.get("BACKEND_URL", "")
    if backend and "127.0.0.1:18043" not in backend and "localhost:18043" not in backend:
        errores.append("BACKEND_URL no apunta a 127.0.0.1:18043")
    if errores:
        for e in errores:
            print(f"FAIL {e}")
        return 1
    print("OK aislamiento G43 (sgpmp_g43_test @ 127.0.0.1:5439, MQTT 1884, API 18043)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
