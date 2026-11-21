"""
TC-M07-G035 (RF-97 RNF-97.1, RNF-97.7, CA-7) - Chequeo ligero de aislamiento
bajo concurrencia contra TEST en vivo.

NO es una prueba de carga formal (eso requiere k6/JMeter, ver
NOTA_rendimiento_concurrencia.md) -- esto confirma, con tráfico real, que
solicitudes concurrentes de distintos titulares no mezclan datos entre sí
(parte de CA-7). No modifica nada (solo lee `vista-previa`).

Ejecutado 2026-11-21: 8 llamadas concurrentes (2 titulares x 4 repeticiones,
el default de --repeticiones), 0.53 s total, 0 mezclas detectadas. (La nota
de 2026-11-18, "12 llamadas / 3 titulares", correspondía a una corrida
exploratoria anterior a este script -- quedó desactualizada y ya no
describe lo que este archivo ejecuta; corregido 2026-11-21.)

Cómo correrlo (requiere la clave real del Contador, no se guarda aquí):
    python chequeo_aislamiento_concurrente.py --pass "<clave real>"
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import time
import urllib.error
import urllib.request

BASE = "https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test"
CORREO = "contador@pecuaria.co"
CASOS = [
    ("901444215", "2026-10-01", "2026-10-31"),
    ("901333217", "2026-11-01", "2026-11-30"),
]  # 901458732 se retiró: desde 2026-11-21 da 403 ALCANCE_INSUFICIENTE (cambio de otro QA en sus fincas, ver ficha.md)


def _login(contrasena: str) -> str:
    req = urllib.request.Request(
        f"{BASE}/sesiones/",
        data=json.dumps({"correo_electronico": CORREO, "contrasena": contrasena}).encode(),
        headers={"Content-Type": "application/json"},
    )
    return json.load(urllib.request.urlopen(req))["token"]


def _llamar(caso: tuple[str, str, str], token: str) -> tuple:
    nit, desde, hasta = caso
    url = f"{BASE}/integracion/aaef/vista-previa/productores/{nit}?desde={desde}&hasta={hasta}"
    try:
        r = urllib.request.urlopen(urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"}))
        data = json.loads(r.read().decode("utf-8"))
        return (nit, data["metadata"]["SourceSystem"]["SystemNIT"], len(data["invoices"]))
    except urllib.error.HTTPError as e:
        return (nit, "ERROR", e.code)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pass", dest="contrasena", required=True, help="Clave real del Contador (no commitear)")
    parser.add_argument("--repeticiones", type=int, default=4)
    args = parser.parse_args()

    token = _login(args.contrasena)
    casos = CASOS * args.repeticiones

    inicio = time.monotonic()
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(casos)) as ex:
        resultados = list(ex.map(lambda c: _llamar(c, token), casos))
    duracion = time.monotonic() - inicio

    mezclados = [r for r in resultados if r[1] != "ERROR" and r[0] != r[1]]
    print(f"Duración total: {duracion:.2f}s, {len(resultados)} llamadas concurrentes")
    print("Mezclas detectadas:", mezclados or "NINGUNA")
    for r in resultados:
        print(r)
    assert not mezclados, "Se detectó una mezcla de datos entre titulares bajo concurrencia"


if __name__ == "__main__":
    main()
