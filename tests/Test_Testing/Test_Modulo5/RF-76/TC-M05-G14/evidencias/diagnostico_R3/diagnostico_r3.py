# | Fecha      | Nombre                   | Que se hizo                                                          |
# |------------|--------------------------|----------------------------------------------------------------------|
# | 2026-11-07 | Juan Sebastian Gutierrez | TC-M05-G14 RF-76: diagnóstico discriminante de R3 (500 en POST)      |
"""Diagnóstico discriminante de R3 (TC-M05-G14): 500 ERROR_INTERNO en todo POST válido.

Uso (desde la raíz del repo):
    .venv\\Scripts\\python.exe tests\\Test_Testing\\Test_Modulo5\\RF-76\\TC-M05-G14\\evidencias\\diagnostico_R3\\diagnostico_r3.py

Reglas que aplica:
- Todo en sandbox (X-Test-Run-Id + X-Sandbox-Secret + X-Zona-Horaria en TODA request).
- Corridas SECUENCIALES, un solo login admin por run_id, teardown en finally con
  verificación de 200 + "Rollback exitoso" (nunca dos corridas abiertas a la vez: R2).
- periodo_retiro_dias = 0 siempre (el correo de retiro solo se envía con retiro > 0).
- Tope duro de 8 POST válidos a /suministros/medicamentos.
- Cada request lleva un X-Request-ID propio (correlativo para buscar en los logs del
  servidor) y se registra si la respuesta lo devuelve. Un 500 SIN X-Request-ID indica una
  excepción no controlada (ServerErrorMiddleware); CON X-Request-ID, un AppError/DBAPIError.
- Traza en trazas_diagnostico_R3.jsonl: lista blanca de campos, sin bodies ni cabeceras.
- Credenciales y secreto solo desde .env.test; nunca se imprimen ni se escriben.
"""
from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

import requests
from dotenv import dotenv_values

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[6]
TRAZA = AQUI / "trazas_diagnostico_R3.jsonl"
ENV = dotenv_values(RAIZ / ".env.test")
BASE = ENV["TEST_BASE_URL"].rstrip("/")
ZONA = "America/Bogota"
BOGOTA = timezone(timedelta(hours=-5), ZONA)  # UTC-05:00 fijo (sin horario de verano)
TIMEOUT = 45
TOPE_POST_VALIDOS = 8
ACTIVO_REF = 5        # activo con fase real abierta
ACTIVO_G14 = 853      # activo del caso (control de contaminación)
RUTA_MED = "/suministros/medicamentos"

_post_validos = 0
_resumen: list[dict] = []


def _hoy():
    return datetime.now(BOGOTA).date()


def _escribir(linea: dict) -> None:
    with open(TRAZA, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(linea, ensure_ascii=False, default=str) + "\n")


def _json(resp) -> dict:
    try:
        b = resp.json()
    except ValueError:
        return {}
    return b if isinstance(b, dict) else {}


class Corrida:
    """run_id propio, un login, teardown verificado. Se usa como context manager."""

    def __init__(self, exp: str) -> None:
        self.exp = exp
        self.run_id = f"diag-r3-{exp.lower()}-{uuid.uuid4()}"
        self.s = requests.Session()
        self.s.headers.update({
            "X-Test-Run-Id": self.run_id,
            "X-Sandbox-Secret": ENV["TEST_SANDBOX_SECRET"],
            "X-Zona-Horaria": ZONA,
        })
        self.teardown = None

    def req(self, metodo: str, ruta: str, **kw):
        rid = f"g14r3-{self.exp.lower()}-{uuid.uuid4().hex[:12]}"
        t0 = time.perf_counter()
        resp, err = None, None
        try:
            resp = self.s.request(metodo, BASE + ruta, timeout=TIMEOUT, headers={"X-Request-ID": rid}, **kw)
        except requests.RequestException as exc:
            err = type(exc).__name__
        b = _json(resp) if resp is not None else {}
        _escribir({
            "tipo": "http",
            "exp": self.exp,
            "run_id": self.run_id,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "metodo": metodo,
            "ruta": ruta,
            "http": resp.status_code if resp is not None else None,
            "error_code": b.get("error_code"),
            "fields": [f.get("field") for f in b.get("fields") or [] if isinstance(f, dict)],
            "x_request_id_enviado": rid,
            "x_request_id_devuelto": resp.headers.get("X-Request-ID") if resp is not None else None,
            "timestamp_servidor": b.get("timestamp"),
            "latencia_ms": round((time.perf_counter() - t0) * 1000, 1),
            "error_conexion": err,
        })
        if err:
            raise RuntimeError(f"{self.exp}: {metodo} {ruta} -> {err}")
        return resp

    def __enter__(self) -> "Corrida":
        r = self.req("POST", "/sesiones/", json={"correo_electronico": ENV["TEST_ADMIN_EMAIL"],
                                                   "contrasena": ENV["TEST_ADMIN_PASSWORD"]})
        if r.status_code != 200 or not _json(r).get("token"):
            self._cerrar()
            raise RuntimeError(f"{self.exp}: login HTTP {r.status_code}")
        self.s.headers["Authorization"] = "Bearer " + _json(r)["token"]
        return self

    def _cerrar(self) -> None:
        try:
            r = self.req("DELETE", f"/test-control/runs/{self.run_id}")
            self.teardown = f"{r.status_code} {_json(r).get('status') or _json(r).get('detail')}"
        except Exception as exc:  # noqa: BLE001 - se reporta, no se oculta
            self.teardown = f"EXC {type(exc).__name__}"
        finally:
            self.s.close()

    def __exit__(self, *exc) -> bool:
        self._cerrar()
        ok = self.teardown is not None and self.teardown.startswith("200") and "Rollback exitoso" in self.teardown
        _escribir({"tipo": "teardown", "exp": self.exp, "run_id": self.run_id, "resultado": self.teardown, "ok": ok})
        if not ok:
            print(f"!! TEARDOWN NO OK en {self.exp}: {self.teardown}")
        return False

    def contar(self, id_activo: int) -> int:
        r = self.req("GET", RUTA_MED, params={"id_activo_biologico": id_activo})
        if r.status_code != 200:
            raise RuntimeError(f"{self.exp}: conteo HTTP {r.status_code}")
        return int(_json(r).get("total"))

    def post_valido(self, payload: dict):
        global _post_validos
        if _post_validos >= TOPE_POST_VALIDOS:
            raise RuntimeError("tope de 8 POST válidos alcanzado")
        _post_validos += 1
        return self.req("POST", RUTA_MED, json=payload)


def payload_base(id_activo: int, fecha, hora: str, **cambios) -> dict:
    p = {
        "id_activo_biologico": id_activo,
        "nombre_medicamento": "Oxitetraciclina",
        "fecha_aplicacion": fecha.isoformat(),
        "hora_aplicacion": hora,
        "via_administracion": "INTRAMUSCULAR",
        "dosis_aplicada": 10,
        "unidad_dosis": "ml",
        "periodo_retiro_dias": 0,
        "motivo_aplicacion": "Tratamiento de infección respiratoria",
        "costo_unitario": 500,
        "nombre_veterinario": "Dr. Pérez",
    }
    p.update(cambios)
    return p


def registrar(exp, activo, fase, variante, resp, antes=None, despues=None, teardown=None, cantidad=None):
    b = _json(resp) if resp is not None else {}
    fila = {
        "exp": exp, "activo": activo, "fase": fase, "variante": variante,
        "http": resp.status_code if resp is not None else None,
        "error_code": b.get("error_code"),
        "x_request_id": resp.headers.get("X-Request-ID") if resp is not None else None,
        "antes": antes, "despues": despues, "cantidad": cantidad, "teardown": teardown,
    }
    _resumen.append(fila)
    _escribir({"tipo": "experimento", **fila})
    return fila


def main() -> None:
    TRAZA.unlink(missing_ok=True)
    hoy = _hoy()

    # ---------------- PASO 1: lectura del activo de referencia
    forma = None
    with Corrida("P1") as c:
        a = _json(c.req("GET", f"/activos-biologicos/{ACTIVO_REF}"))
        fases = _json(c.req("GET", f"/activos-biologicos/{ACTIVO_REF}/fases")).get("fases") or []
        activa = [f for f in fases if f.get("es_activa")]
        meds = _json(c.req("GET", RUTA_MED, params={"id_activo_biologico": ACTIVO_REF})).get("items") or []
        validos = [m for m in meds if m.get("estado_registro") == "VALIDADO"]
        if validos:
            m = sorted(validos, key=lambda x: str(x.get("fecha_registro")))[-1]
            forma = {k: m.get(k) for k in ("nombre_medicamento", "via_aplicacion", "unidad_dosis", "cantidad",
                                           "costo_unitario_medicamento", "fecha_aplicacion", "hora_aplicacion",
                                           "motivo_aplicacion", "nombre_veterinario", "fecha_registro")}
        ocupadas = {(str(x.get("fecha_aplicacion")), str(x.get("hora_aplicacion"))[:5]) for x in validos}
        info = {
            "tipo": a.get("tipo"), "id_estado": a.get("id_estado"), "fecha_inicio_ciclo": a.get("fecha_inicio_ciclo"),
            "id_especie": a.get("id_especie"),
            "fase_activa": [(f.get("id_gestion_fases"), f.get("id_ciclo_productiva"), f.get("paso_actual"),
                             f.get("total_pasos")) for f in activa],
            "medicamentos": len(meds), "validados": len(validos),
        }
        _escribir({"tipo": "paso1", **info,
                   "forma_registro_previo": {k: v for k, v in (forma or {}).items() if k != "nombre_veterinario"},
                   "nombre_veterinario_presente": bool(forma and forma.get("nombre_veterinario"))})
        print("PASO1", json.dumps(info, default=str))
        print("PASO1 forma (sin veterinario):",
              json.dumps({k: v for k, v in (forma or {}).items() if k != "nombre_veterinario"}, default=str))
    if not activa:
        print("PASO1: el activo 5 no tiene fase activa; E1 no aplica tal como está diseñado")

    def hora_libre(fecha, preferida: str) -> str:
        h = preferida
        while (fecha.isoformat(), h) in ocupadas:
            hh, mm = map(int, h.split(":"))
            mm = (mm + 1) % 60
            h = f"{hh:02d}:{mm:02d}"
        return h

    # ---------------- E5a: conteos base
    with Corrida("E5a") as c:
        base = {ACTIVO_G14: c.contar(ACTIVO_G14), ACTIVO_REF: c.contar(ACTIVO_REF)}
    _escribir({"tipo": "conteo", "momento": "base", "conteos": base})
    print("E5a base:", base)

    # ---------------- E1: activo 5, fase real ya abierta
    with Corrida("E1") as c:
        antes = c.contar(ACTIVO_REF)
        r = c.post_valido(payload_base(ACTIVO_REF, hoy, hora_libre(hoy, "10:41")))
        despues = c.contar(ACTIVO_REF)
    e1 = registrar("E1", ACTIVO_REF, "real", "payload base G14", r, antes, despues, c.teardown)
    print("E1:", e1)

    # ---------------- E2: activo 5, fase NUEVA abierta en el sandbox
    e2 = None
    if activa:
        with Corrida("E2") as c:
            rf = c.req("POST", f"/activos-biologicos/{ACTIVO_REF}/fases",
                       json={"id_ciclo_productiva": activa[0].get("id_ciclo_productiva"),
                             "motivo_cambio": "TC-M05-G14 diagnóstico R3: fase en sandbox"})
            fase_res = f"POST /fases {rf.status_code} {_json(rf).get('error_code') or ''}".strip()
            _escribir({"tipo": "e2_fase", "resultado": fase_res})
            print("E2 apertura de fase:", fase_res)
            if rf.status_code == 201:
                antes = c.contar(ACTIVO_REF)
                r = c.post_valido(payload_base(ACTIVO_REF, hoy, hora_libre(hoy, "10:42")))
                despues = c.contar(ACTIVO_REF)
            else:
                r, antes, despues = None, None, None
        e2 = registrar("E2", ACTIVO_REF, "sandbox", fase_res if r is None else "payload base G14", r, antes, despues,
                       c.teardown)
        print("E2:", e2)

    # ---------------- E3: variantes (solo si E1 o E2 dio 500)
    hubo_500 = e1["http"] == 500 or (e2 is not None and e2["http"] == 500)
    combinacion_201 = None
    if e1["http"] == 201:
        combinacion_201 = ("E1", lambda f, h, **k: payload_base(ACTIVO_REF, f, h, **k))
    if hubo_500:
        minimo = {k: v for k, v in payload_base(ACTIVO_REF, hoy, "x").items() if k != "periodo_retiro_dias"}
        variantes = [
            ("E3i", "payload mínimo (10 obligatorios)",
             lambda: {**minimo, "hora_aplicacion": hora_libre(hoy, "10:43")}),
            ("E3ii", "valores clonados de un registro real",
             lambda: payload_base(ACTIVO_REF, hoy, hora_libre(hoy, "10:44"),
                                  nombre_medicamento=forma["nombre_medicamento"],
                                  via_administracion=forma["via_aplicacion"],
                                  unidad_dosis=forma["unidad_dosis"],
                                  dosis_aplicada=str(forma["cantidad"]),
                                  costo_unitario=str(forma["costo_unitario_medicamento"]),
                                  motivo_aplicacion=forma["motivo_aplicacion"] or "Tratamiento clonado de registro previo",
                                  nombre_veterinario=forma["nombre_veterinario"] or "Dr. Pérez") if forma else None),
            ("E3iii", "fecha hoy-3 y hora 23:59",
             lambda: payload_base(ACTIVO_REF, hoy - timedelta(days=3), "23:59")),
            ("E3iv", "dosis=1 y costo_unitario=1",
             lambda: payload_base(ACTIVO_REF, hoy, hora_libre(hoy, "10:46"), dosis_aplicada=1, costo_unitario=1)),
        ]
        for exp, desc, construir in variantes:
            payload = construir()
            if payload is None:
                registrar(exp, ACTIVO_REF, "real", desc + " (omitida: sin registro previo)", None)
                continue
            with Corrida(exp) as c:
                antes = c.contar(ACTIVO_REF)
                r = c.post_valido(payload)
                despues = c.contar(ACTIVO_REF)
            fila = registrar(exp, ACTIVO_REF, "real", desc, r, antes, despues, c.teardown)
            print(f"{exp}:", fila)
            if fila["http"] == 201 and combinacion_201 is None:
                combinacion_201 = (exp, payload)

    # ---------------- E4: precisión de la dosis (solo si alguna combinación dio 201)
    if combinacion_201 is not None:
        origen, plantilla = combinacion_201
        for exp, dosis, hora in (("E4a", "0.001", "10:47"), ("E4b", "0.0001", "10:48")):
            if callable(plantilla):
                payload = plantilla(hoy, hora_libre(hoy, hora), dosis_aplicada=dosis)
            else:
                payload = {**plantilla, "dosis_aplicada": dosis, "hora_aplicacion": hora_libre(hoy, hora)}
            with Corrida(exp) as c:
                antes = c.contar(ACTIVO_REF)
                r = c.post_valido(payload)
                despues = c.contar(ACTIVO_REF)
                cant = None
                if r.status_code == 201:
                    bruto = (_json(r).get("medicamento") or {}).get("cantidad")
                    try:
                        cant = {"recibido": str(bruto), "igual_a_enviado": Decimal(str(bruto)) == Decimal(dosis)}
                    except (InvalidOperation, TypeError):
                        cant = {"recibido": str(bruto), "igual_a_enviado": None}
            print(f"{exp}:", registrar(exp, ACTIVO_REF, "real", f"dosis {dosis} (plantilla {origen})", r, antes,
                                       despues, c.teardown, cant))

    # ---------------- E5b: conteos finales (rollback de cualquier escritura real)
    with Corrida("E5b") as c:
        final = {ACTIVO_G14: c.contar(ACTIVO_G14), ACTIVO_REF: c.contar(ACTIVO_REF)}
    _escribir({"tipo": "conteo", "momento": "final", "conteos": final, "iguales_a_base": final == base})
    print("E5b final:", final, "| iguales a base:", final == base)
    print("POST válidos usados:", _post_validos, "de", TOPE_POST_VALIDOS)

    # ---------------- Escaneo de secretos de todo lo escrito en esta carpeta
    patrones = [ENV["TEST_ADMIN_PASSWORD"], ENV["TEST_SANDBOX_SECRET"], ENV["TEST_SANDBOX_SECRET"][-20:], "ey" + "J"]
    for archivo in sorted(AQUI.glob("*")):
        if archivo.is_file() and archivo.suffix in (".jsonl", ".txt", ".log"):
            texto = archivo.read_text(encoding="utf-8")
            print(f"ESCANEO {archivo.name}: {'CONTIENE SECRETOS' if any(p and p in texto for p in patrones) else 'limpio'}")


if __name__ == "__main__":
    main()
