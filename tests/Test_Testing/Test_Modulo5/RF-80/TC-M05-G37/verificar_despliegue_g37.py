# | Fecha      | Nombre                   | Que se hizo                                                                              |
# |------------|--------------------------|------------------------------------------------------------------------------------------|
# | 2026-11-15 | Juan Sebastian Gutierrez | Control de despliegue en TEST del PR #1145 (INC-M05-353-G37) antes del reintento 2 de G37 |
"""Control de despliegue en TEST para el reintento 2 de TC-M05-G37 (INC-M05-353-G37, PR #1145).

Solo lectura: GET /openapi.json con las cabeceras del sandbox y cierre DELETE /test-control/runs/{run_id}.
Sin login, sin escritura y sin consultas SQL al sandbox.

Criterio (marcador del PR #1145): el esquema EventoAuditoriaSuministroResponse de GET /suministros/auditoria
expone id_registro_suministro e id_tipo_suministro (src/supplies/infrastructure/schema/auditoria_suministro_schema.py:39-40).

Codigos de salida: 0 = desplegado, 3 = NO desplegado (no ejecutar la corrida), 2 = TEST no verificable.
Las credenciales se leen del entorno del proceso (el runner carga .env.test) y nunca se imprimen.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

ZONA_USUARIO = timezone(timedelta(hours=-5))
ESQUEMA = "EventoAuditoriaSuministroResponse"
CAMPOS_PR_1145 = ("id_registro_suministro", "id_tipo_suministro")


def main() -> int:
    parser = argparse.ArgumentParser(description="Control de despliegue de INC-M05-353-G37 en TEST")
    parser.add_argument("--salida", required=True, help="Archivo .txt de evidencia del control")
    args = parser.parse_args()

    base = (os.environ.get("TEST_BASE_URL") or "").rstrip("/")
    secreto = os.environ.get("TEST_SANDBOX_SECRET") or ""
    lineas = [
        "CONTROL DE DESPLIEGUE TC-M05-G37 REINTENTO 2 (INC-M05-353-G37 / PR #1145)",
        f"Fecha/Hora: {datetime.now(ZONA_USUARIO).strftime('%Y-%m-%d %H:%M:%S')} (America/Bogota)",
        f"Criterio: {ESQUEMA} expone {', '.join(CAMPOS_PR_1145)}",
    ]
    if not base or not secreto:
        lineas.append("RESULTADO: NO_VERIFICABLE (faltan TEST_BASE_URL o TEST_SANDBOX_SECRET en el entorno)")
        Path(args.salida).write_text("\n".join(lineas) + "\n", encoding="utf-8")
        print(lineas[-1])
        return 2

    run_id = f"tc-m05-g37-deploy-{uuid.uuid4().hex[:8]}"
    http = requests.Session()
    http.headers.update({"X-Test-Run-Id": run_id, "X-Sandbox-Secret": secreto})
    codigo = 2
    try:
        try:
            r = http.get(f"{base}/openapi.json", timeout=30)
        except requests.RequestException as exc:
            lineas.append(f"GET /openapi.json -> ERROR_CONEXION {type(exc).__name__}")
            lineas.append("RESULTADO: NO_VERIFICABLE")
            return 2
        lineas.append(f"GET /openapi.json -> HTTP {r.status_code} [X-Request-Id={r.headers.get('X-Request-Id')}]")
        if r.status_code != 200:
            lineas.append("RESULTADO: NO_VERIFICABLE (openapi no disponible)")
            return 2
        try:
            esquemas = (r.json().get("components") or {}).get("schemas") or {}
        except ValueError:
            lineas.append("RESULTADO: NO_VERIFICABLE (openapi no es JSON)")
            return 2
        propiedades = sorted(((esquemas.get(ESQUEMA) or {}).get("properties") or {}).keys())
        lineas.append(f"{ESQUEMA} presente: {ESQUEMA in esquemas}")
        lineas.append(f"{ESQUEMA} propiedades ({len(propiedades)}): {json.dumps(propiedades)}")
        faltan = [c for c in CAMPOS_PR_1145 if c not in propiedades]
        if faltan:
            lineas.append(f"RESULTADO: NO_DESPLEGADO (faltan {faltan}); NO ejecutar la corrida oficial")
            codigo = 3
        else:
            lineas.append("RESULTADO: DESPLEGADO")
            codigo = 0
        return codigo
    finally:
        try:
            rc = http.delete(f"{base}/test-control/runs/{run_id}", timeout=30)
            lineas.append(f"DELETE /test-control/runs/{{run_id}} -> HTTP {rc.status_code} [X-Request-Id={rc.headers.get('X-Request-Id')}]")
        except requests.RequestException as exc:
            lineas.append(f"DELETE /test-control/runs/{{run_id}} -> ERROR_CONEXION {type(exc).__name__}")
        http.close()
        Path(args.salida).write_text("\n".join(lineas) + "\n", encoding="utf-8")
        for linea in lineas:
            print(linea)


if __name__ == "__main__":
    sys.exit(main())
