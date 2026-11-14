# | Fecha      | Nombre                   | Que se hizo                                                          |
# |------------|--------------------------|----------------------------------------------------------------------|
# | 2026-11-07 | Juan Sebastian Gutierrez | TC-M05-G14 RF-76: diagnóstico de precisión de dosis_aplicada (B03)  |
"""Diagnóstico B03: ¿la dosis se redondea a 3 decimales al persistirse?

Corridas SECUENCIALES (nunca dos abiertas), un login admin por run_id, teardown verificado:
  1. BASE  : conteo de medicamentos del activo 853.
  2. PRUEBA: abre la fase dentro del sandbox (como la suite) y envía un POST por dosis, en orden:
             0.001, 0.0004, 0.0005, 0.0015 (payload base de G14, retiro 0, hora distinta en cada uno).
             Con 201, lee la 'cantidad' persistida en el listado. Conteo antes/después dentro de la corrida.
  3. FINAL : conteo del activo 853 (debe ser igual al base).
Cada request lleva un X-Request-ID propio. Traza en lista blanca: sin bodies, cabeceras ni tokens.
Credenciales y secreto solo desde .env.test; no se imprimen ni se escriben.
"""
from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from dotenv import dotenv_values

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[6]
TRAZA = AQUI / "trazas_diagnostico_B03.jsonl"
ENV = dotenv_values(RAIZ / ".env.test")
BASE = ENV["TEST_BASE_URL"].rstrip("/")
ZONA = "America/Bogota"
BOGOTA = timezone(timedelta(hours=-5), ZONA)  # UTC-05:00 fijo (sin horario de verano)
ACTIVO = 853
RUTA_MED = "/suministros/medicamentos"
DOSIS = [("0.001", "11:01"), ("0.0004", "11:02"), ("0.0005", "11:03"), ("0.0015", "11:04")]


def _json(resp) -> dict:
    try:
        b = resp.json()
    except ValueError:
        return {}
    return b if isinstance(b, dict) else {}


def _escribir(linea: dict) -> None:
    with open(TRAZA, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(linea, ensure_ascii=False, default=str) + "\n")


class Corrida:
    def __init__(self, nombre: str) -> None:
        self.nombre = nombre
        self.run_id = f"diag-b03-{nombre.lower()}-{uuid.uuid4()}"
        self.s = requests.Session()
        self.s.headers.update({"X-Test-Run-Id": self.run_id, "X-Sandbox-Secret": ENV["TEST_SANDBOX_SECRET"],
                               "X-Zona-Horaria": ZONA})
        self.teardown = None

    def req(self, metodo: str, ruta: str, **kw):
        rid = f"g14b03-{self.nombre.lower()}-{uuid.uuid4().hex[:12]}"
        t0 = time.perf_counter()
        r = self.s.request(metodo, BASE + ruta, timeout=45, headers={"X-Request-ID": rid}, **kw)
        b = _json(r)
        _escribir({"tipo": "http", "corrida": self.nombre,
                   "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
                   "metodo": metodo, "ruta": ruta, "http": r.status_code, "error_code": b.get("error_code"),
                   "x_request_id": rid, "x_request_id_devuelto": r.headers.get("X-Request-ID") == rid,
                   "timestamp_servidor": b.get("timestamp"), "latencia_ms": round((time.perf_counter() - t0) * 1000, 1)})
        return r, rid

    def __enter__(self):
        r, _ = self.req("POST", "/sesiones/", json={"correo_electronico": ENV["TEST_ADMIN_EMAIL"],
                                                    "contrasena": ENV["TEST_ADMIN_PASSWORD"]})
        if r.status_code != 200 or not _json(r).get("token"):
            self.__exit__()
            raise RuntimeError(f"{self.nombre}: login HTTP {r.status_code}")
        self.s.headers["Authorization"] = "Bearer " + _json(r)["token"]
        return self

    def __exit__(self, *exc):
        if self.teardown is None:
            try:
                r, _ = self.req("DELETE", f"/test-control/runs/{self.run_id}")
                self.teardown = f"{r.status_code} {_json(r).get('status') or _json(r).get('detail')}"
            except requests.RequestException as e:
                self.teardown = f"EXC {type(e).__name__}"
            finally:
                self.s.close()
            _escribir({"tipo": "teardown", "corrida": self.nombre, "resultado": self.teardown})
        return False

    def items(self) -> list[dict]:
        r, _ = self.req("GET", RUTA_MED, params={"id_activo_biologico": ACTIVO})
        assert r.status_code == 200, f"listado HTTP {r.status_code}"
        return _json(r).get("items") or []


def main() -> None:
    TRAZA.unlink(missing_ok=True)
    hoy = datetime.now(BOGOTA).date().isoformat()

    with Corrida("BASE") as c:
        base = len(c.items())
    print("BASE conteo:", base, "| teardown:", c.teardown)

    filas = []
    with Corrida("PRUEBA") as c:
        fases = _json(c.req("GET", f"/activos-biologicos/{ACTIVO}/fases")[0]).get("fases") or []
        if not any(f.get("es_activa") for f in fases):
            ciclos = [ci for ci in _json(c.req("GET", f"/activos-biologicos/{ACTIVO}/ciclos-productivos")[0]).get("items") or []
                      if ci.get("fases")]
            id_ciclo = sorted(ciclos, key=lambda ci: ci["id_ciclo_productivo"])[0]["id_ciclo_productivo"]
            rf, _ = c.req("POST", f"/activos-biologicos/{ACTIVO}/fases",
                          json={"id_ciclo_productiva": id_ciclo, "motivo_cambio": "Diagnóstico B03: fase en sandbox"})
            print("Apertura de fase:", rf.status_code, _json(rf).get("error_code"))
            assert rf.status_code == 201, "no se pudo abrir la fase"
        antes = len(c.items())
        for dosis, hora in DOSIS:
            payload = {"id_activo_biologico": ACTIVO, "nombre_medicamento": "Oxitetraciclina", "fecha_aplicacion": hoy,
                       "hora_aplicacion": hora, "via_administracion": "INTRAMUSCULAR", "dosis_aplicada": dosis,
                       "unidad_dosis": "ml", "periodo_retiro_dias": 0,
                       "motivo_aplicacion": "Tratamiento de infección respiratoria", "costo_unitario": 500,
                       "nombre_veterinario": "Dr. Pérez"}
            r, rid = c.req("POST", RUTA_MED, json=payload)
            b = _json(r)
            med = b.get("medicamento") or {}
            fila = {"dosis_enviada": dosis, "http": r.status_code, "error_code": b.get("error_code"),
                    "cantidad_respuesta": None if r.status_code != 201 else str(med.get("cantidad")),
                    "cantidad_persistida": None, "x_request_id": rid, "hora_utc_servidor": b.get("timestamp"),
                    "hora_aplicacion": hora, "id_registro": med.get("id_registro_medicamento")}
            if r.status_code == 201:
                persistido = [m for m in c.items() if m.get("id_registro_medicamento") == fila["id_registro"]]
                fila["cantidad_persistida"] = str(persistido[0].get("cantidad")) if persistido else "no encontrado"
            if fila["hora_utc_servidor"] is None:  # en el 201 el body no trae timestamp: hora del cliente
                fila["hora_utc_servidor"] = datetime.now(timezone.utc).isoformat(timespec="milliseconds") + " (cliente)"
            fila.pop("id_registro")
            filas.append(fila)
            _escribir({"tipo": "dosis", **fila})
            print("DOSIS", json.dumps(fila, ensure_ascii=False))
        despues = len(c.items())
    exitos = sum(f["http"] == 201 for f in filas)
    print(f"PRUEBA conteo antes={antes} despues={despues} (201 obtenidos={exitos}) | teardown: {c.teardown}")
    _escribir({"tipo": "conteo_prueba", "antes": antes, "despues": despues, "201": exitos})

    with Corrida("FINAL") as c:
        final = len(c.items())
    print("FINAL conteo:", final, "| igual a base:", final == base, "| teardown:", c.teardown)
    _escribir({"tipo": "conteo", "base": base, "final": final, "iguales": final == base})


if __name__ == "__main__":
    main()
