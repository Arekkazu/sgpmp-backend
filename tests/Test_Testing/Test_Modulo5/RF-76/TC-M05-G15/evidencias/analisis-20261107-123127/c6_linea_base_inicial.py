"""Medición de línea base de inocuidad inicial (sin sandbox) para Activos 853 y 462.
Registra:
- Conteo de medicamentos
- Estado del activo
- Número de fases totales y activas
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import requests
from dotenv import dotenv_values

_DIR_ACTUAL = Path(__file__).resolve().parent
_RAIZ_REPO = Path(__file__).resolve().parents[7]
if not (_RAIZ_REPO / ".env.test").exists():
    _RAIZ_REPO = Path.cwd()
_ENV_TEST = dotenv_values(_RAIZ_REPO / ".env.test")


def env(nombre: str) -> str:
    v = os.environ.get(nombre) or _ENV_TEST.get(nombre)
    if not v:
        raise RuntimeError(f"Falta variable de entorno: {nombre}")
    return v


BASE_URL = env("TEST_BASE_URL")
EMAIL = env("TEST_ADMIN_EMAIL")
PASSWORD = env("TEST_ADMIN_PASSWORD")


def consultar_estado_activo(token: str, id_activo: int) -> dict:
    headers = {"Authorization": f"Bearer {token}"}
    
    # 1. Conteo medicamentos
    r_med = requests.get(f"{BASE_URL}/suministros/medicamentos?id_activo_biologico={id_activo}", headers=headers, timeout=30)
    assert r_med.status_code == 200, f"Error medicamentos {id_activo}: {r_med.status_code} {r_med.text}"
    total_meds = r_med.json().get("total")
    
    # 2. Estado del activo
    r_act = requests.get(f"{BASE_URL}/activos-biologicos/{id_activo}", headers=headers, timeout=30)
    assert r_act.status_code == 200, f"Error activo {id_activo}: {r_act.status_code} {r_act.text}"
    data_act = r_act.json()
    
    # 3. Fases
    r_fas = requests.get(f"{BASE_URL}/activos-biologicos/{id_activo}/fases", headers=headers, timeout=30)
    assert r_fas.status_code == 200, f"Error fases {id_activo}: {r_fas.status_code} {r_fas.text}"
    fases = r_fas.json().get("fases") or []
    fases_activas = [f for f in fases if f.get("es_activa") is True]
    
    return {
        "id_activo_biologico": id_activo,
        "total_medicamentos": total_meds,
        "id_estado": data_act.get("id_estado"),
        "estado": data_act.get("estado"),
        "total_fases": len(fases),
        "total_fases_activas": len(fases_activas),
        "fases_ids": [f.get("id_gestion_fase") for f in fases],
    }


def main():
    # Login outside sandbox
    r_login = requests.post(f"{BASE_URL}/sesiones/", json={"correo_electronico": EMAIL, "contrasena": PASSWORD}, timeout=15)
    assert r_login.status_code == 200, f"Login fallo: {r_login.status_code}"
    token = r_login.json()["token"]
    
    res_853 = consultar_estado_activo(token, 853)
    res_462 = consultar_estado_activo(token, 462)
    
    datos = {
        "timestamp_iso": r_login.headers.get("Date", ""),
        "activo_853": res_853,
        "activo_462": res_462,
    }
    
    salida_json = _DIR_ACTUAL / "linea_base_inicial.json"
    with open(salida_json, "w", encoding="utf-8") as f:
        json.dump(datos, f, indent=2)
        
    print("LINEA_BASE_INICIAL_OK")
    print("Activo 853:", json.dumps(res_853))
    print("Activo 462:", json.dumps(res_462))


if __name__ == "__main__":
    main()
