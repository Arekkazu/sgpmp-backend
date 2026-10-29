"""TC-M09-106 — Ediciones realmente simultáneas sobre la misma área (complementa la colección Newman).

La colección prueba el control optimista en secuencia (A guarda, luego B con la marca vieja -> 412).
Este script lanza dos PATCH a la vez (barrera de hilos) con la misma `fecha_actualizacion`
sobre un área recién creada, repetido N veces. Lo esperado en cada intento es exactamente un
200 y un 412 CONFLICTO_CONCURRENCIA, y que el área quede con los datos del 200.

Un intento con 200/200 es una actualización perdida: las dos ediciones se aceptan y la última
sobrescribe a la otra sin aviso.

Uso:
    python concurrencia_simultanea_g54.py [--intentos 10]
Sale con código 1 si hubo alguna actualización perdida.
"""
from __future__ import annotations

import argparse
import json
import random
import string
import sys
import threading
import urllib.error
import urllib.request

BASE = "https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test"


def call(method, path, token=None, body=None):
    req = urllib.request.Request(BASE + path, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    data = json.dumps(body).encode() if body is not None else None
    try:
        with urllib.request.urlopen(req, data, timeout=30) as r:
            return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"null")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--intentos", type=int, default=10)
    args = parser.parse_args()

    suf = "".join(random.choice(string.ascii_lowercase) for _ in range(8))
    _, sesion = call("POST", "/sesiones/", body={"correo_electronico": "admin@pecuaria.co", "contrasena": "Test1234!"})
    tok = sesion["token"]
    _, finca = call("POST", "/configuracion/fincas", tok, {
        "nombre": f"Finca Concurrencia Real {suf}",
        "ubicacion": {"departamento": "Antioquia", "municipio": "Medellin", "vereda": "La Estrella",
                      "latitud": "6.25", "longitud": "-75.56"},
        "tamano_h": "10.0",
    })
    _, especie = call("POST", "/configuracion/especies", tok, {"nombre": f"Especie Concurrencia {suf}", "tipo_modelo": "MODELO_AVES"})

    resumen: dict[str, int] = {}
    perdidas = 0
    for intento in range(1, args.intentos + 1):
        _, area = call("POST", "/configuracion/infraestructuras", tok, {
            "nombre_infraestructura": f"Concurrencia {intento} {suf}", "tipo_area": "Galpón", "superficie": "100.00",
            "finca_id": finca["id_finca"], "especie_id": especie["id_especie"],
        })
        aid = area["id_infraestructura"]
        _, leido = call("GET", f"/configuracion/infraestructuras/{aid}", tok)
        marca = leido["fecha_actualizacion"]  # misma marca para los dos editores
        barrera = threading.Barrier(2)
        res: dict[str, tuple] = {}

        def editar(quien: str, superficie: str) -> None:
            barrera.wait()
            res[quien] = call("PATCH", f"/configuracion/infraestructuras/{aid}", tok, {
                # nombres únicos por intento para no chocar con la unicidad de nombre por finca (409)
                "nombre_infraestructura": f"Editada por {quien} {intento}", "tipo_area": "Galpón",
                "superficie": superficie, "especie_id": especie["id_especie"], "fecha_actualizacion": marca,
            })

        hilos = [threading.Thread(target=editar, args=("A", "150.00")), threading.Thread(target=editar, args=("B", "200.00"))]
        for h in hilos:
            h.start()
        for h in hilos:
            h.join()
        _, final = call("GET", f"/configuracion/infraestructuras/{aid}", tok)

        codigos = f"A={res['A'][0]} B={res['B'][0]}"
        clave = "/".join(str(c) for c in sorted(r[0] for r in res.values()))
        resumen[clave] = resumen.get(clave, 0) + 1
        if clave == "200/200":
            perdidas += 1
            veredicto = f"ACTUALIZACION PERDIDA: ambas 200, queda '{final['nombre_infraestructura']}'"
        elif clave == "200/412":
            ganador = "A" if res["A"][0] == 200 else "B"
            ok = final["nombre_infraestructura"] == f"Editada por {ganador} {intento}"
            veredicto = f"OK: gana {ganador}, el otro 412" + ("" if ok else " (pero el estado final no coincide)")
        else:
            veredicto = "inesperado: " + json.dumps({q: (r[0], (r[1] or {}).get('error_code')) for q, r in res.items()})
        print(f"intento {intento:2d} area {aid}: {codigos}  {veredicto}")

    print(f"\nResumen: {resumen}  ->  actualizaciones perdidas: {perdidas}/{args.intentos}")
    return 1 if perdidas else 0


if __name__ == "__main__":
    sys.exit(main())
