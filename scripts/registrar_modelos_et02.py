# | Fecha      | Nombre   | Que se hizo                                                        |
# |------------|----------|--------------------------------------------------------------------|
# | 2026-10-31 | Arekkazu | RFC-010 RF-69/RF-66: registra ET-02 en RF-69 y arma el catálogo del motor |
"""Registra los modelos individuales de ET-02 en RF-69, los pone en SOMBRA y arma el
catálogo del motor M04 (``catalogo.json`` + artefactos) con los IDs de ese ambiente.

Solo usa la API del ambiente (RBAC, RLS y auditoría RF-73 aplican igual que en la app):

1. ``GET /configuracion/variables-ambientales``: traduce las variables de ET-02 a IDs I3P-1.
2. ``POST /prediccion/modelos`` (X-RF71-Internal-Key) por animal con ``.onnx`` y
   ``apto_despliegue_sombra``; los SINTETICA quedan APROBADO solo para sombra (RFC-010).
3. ``POST /prediccion/modelos/{id}/sombra`` (token de un Administrador o Veterinario).
4. Copia ``<ANIMAL>.onnx``, línea base y metadatos a ``--salida`` y escribe ``catalogo.json``.

Es idempotente: una versión con el mismo hash y el mismo animal no se registra dos veces.
Por defecto solo valida; ``--aplicar`` escribe en el ambiente. Los IDs de activo son los de
la BD de ese ambiente (cada uno tiene los suyos)::

    RF71_INTERNAL_KEY=... SGPMP_ACCESS_TOKEN=... python scripts/registrar_modelos_et02.py \\
        --backend https://api.inmero.co/api-sgpmp-test --modelos <salidas_ET02_v5> \\
        --animal BOV-001=885 --animal TER-001=890 --salida modelos/ --aplicar

Después, la carpeta ``--salida`` se sube al motor del ambiente
(``docs/MOTOR_IA_MODELOS_DOKPLOY.md`` del broker).
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

import httpx

# ET-02 nombra las variables como el generador; I3P-1 (M09) las identifica por codigo_telemetria.
CODIGO_TELEMETRIA = {
    "frecuencia_cardiaca": "FRECUENCIA_CARDIACA",
    "temperatura_corporal": "TEMP_CORPORAL",
    "actividad_indice": "ACTIVIDAD",
}


class ErrorRegistro(RuntimeError):
    pass


def _dict(valor):
    # Los metadatos de ET-02 v5 serializan algunos objetos como repr de Python.
    return ast.literal_eval(valor) if isinstance(valor, str) else valor


def _respuesta(r: httpx.Response, que: str) -> dict:
    if r.status_code >= 400:
        raise ErrorRegistro(f"{que}: HTTP {r.status_code} {r.text}")
    return r.json()


def leer_animal(carpeta: Path, codigo: str) -> dict:
    """Artefactos de ET-02 del animal, con el hash verificado. ErrorRegistro si no es registrable."""
    metadatos_path = carpeta / f"{codigo}_metadatos_rf69.json"
    onnx_path, linea_base_path = carpeta / f"{codigo}.onnx", carpeta / f"{codigo}_linea_base.json"
    for p in (metadatos_path, onnx_path, linea_base_path):
        if not p.is_file():
            raise ErrorRegistro(f"{codigo}: falta {p.name}")
    metadatos = json.loads(metadatos_path.read_text(encoding="utf-8"))
    if not metadatos.get("apto_despliegue_sombra"):
        raise ErrorRegistro(f"{codigo}: ET-02 lo marca no apto para sombra (apto_despliegue_sombra=false)")
    artefacto = onnx_path.read_bytes()
    sha = hashlib.sha256(artefacto).hexdigest()
    if sha != metadatos.get("hash_artefacto_modelo"):
        raise ErrorRegistro(f"{codigo}: el SHA-256 de {onnx_path.name} no coincide con hash_artefacto_modelo")
    return {
        "codigo": codigo, "metadatos": metadatos, "artefacto": artefacto, "sha": sha,
        "rutas": (onnx_path, linea_base_path, metadatos_path),
    }


def ids_variables(cliente: httpx.Client, nombres: list[str]) -> list[int]:
    items = _respuesta(cliente.get("/configuracion/variables-ambientales"), "Variables I3P-1")["items"]
    por_codigo = {v.get("codigo_telemetria"): v["id_variable_ambiental"] for v in items}
    faltan = [n for n in nombres if por_codigo.get(CODIGO_TELEMETRIA.get(n)) is None]
    if faltan:
        raise ErrorRegistro(f"Variables de ET-02 sin equivalente activo en I3P-1: {faltan}")
    return [por_codigo[CODIGO_TELEMETRIA[n]] for n in nombres]


def version_existente(cliente: httpx.Client, tipo_modelo: str, sha: str, id_activo: int):
    offset = 0
    while True:
        pagina = _respuesta(
            cliente.get("/prediccion/modelos", params={"tipo_modelo": tipo_modelo, "limit": 100, "offset": offset}),
            "Listar versiones",
        )
        for v in pagina["items"]:
            if v["hash_artefacto_sha256"] == sha and v.get("id_activo_biologico") == id_activo and v["estado_version"] in ("APROBADO", "SOMBRA", "ACTIVO"):
                return v
        offset += 100
        if offset >= pagina["total"]:
            return None


def registrar(cliente: httpx.Client, clave_rf71: str, animal: dict, id_activo: int, variables: list[int]) -> dict:
    m = animal["metadatos"]
    datos = {
        "tipo_modelo": m["tipo_modelo"],
        "hash_artefacto_sha256": animal["sha"],
        "dataset_entrenamiento_hash": m["dataset_entrenamiento_hash"],
        "metricas_validacion": json.dumps(_dict(m["metricas_validacion"])),
        "fecha_entrenamiento": m["fecha_entrenamiento"],
        "compatibilidad_variables": json.dumps(variables),
        "id_proceso_rf71": m["id_proceso_rf71"],
        "id_activo_biologico": str(id_activo),
        "fuente_datos": m.get("fuente_datos", "REAL"),
    }
    r = cliente.post(
        "/prediccion/modelos", data=datos, headers={"X-RF71-Internal-Key": clave_rf71},
        files={"archivo_modelo": (animal["rutas"][0].name, animal["artefacto"])},
    )
    return _respuesta(r, f"{animal['codigo']}: registrar en RF-69")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--backend", required=True, help="URL base del backend del ambiente, con su prefijo")
    p.add_argument("--modelos", required=True, type=Path, help="Carpeta salidas_ET02_v5")
    p.add_argument("--animal", action="append", required=True, metavar="CODIGO=ID_ACTIVO",
                   help="Animal de ET-02 y su id_activo_biologico en ese ambiente (repetible)")
    p.add_argument("--salida", required=True, type=Path, help="Carpeta del catálogo del motor")
    p.add_argument("--aplicar", action="store_true", help="Registrar de verdad (por defecto solo valida)")
    args = p.parse_args(argv)

    token, clave = os.environ.get("SGPMP_ACCESS_TOKEN"), os.environ.get("RF71_INTERNAL_KEY")
    if not token or not clave:
        print("Faltan SGPMP_ACCESS_TOKEN (Administrador o Veterinario) y RF71_INTERNAL_KEY.", file=sys.stderr)
        return 2
    pares = []
    for valor in args.animal:
        codigo, _, id_activo = valor.partition("=")
        if not id_activo.isdigit():
            print(f"--animal {valor}: se espera CODIGO=ID_ACTIVO (ej. BOV-001=885)", file=sys.stderr)
            return 2
        pares.append((codigo, int(id_activo)))

    cliente = httpx.Client(base_url=args.backend.rstrip("/"), headers={"Authorization": f"Bearer {token}"}, timeout=60)
    catalogo, errores = [], 0
    for codigo, id_activo in pares:
        try:
            animal = leer_animal(args.modelos, codigo)
            variables = ids_variables(cliente, animal["metadatos"]["compatibilidad_variables"])
            version = version_existente(cliente, animal["metadatos"]["tipo_modelo"], animal["sha"], id_activo)
            if not args.aplicar:
                estado = f"ya registrado (v{version['id_version_modelo']}, {version['estado_version']})" if version else "se registraría"
                print(f"{codigo} → activo {id_activo}: válido, {estado}")
                continue
            if version is None:
                version = registrar(cliente, clave, animal, id_activo, variables)
                print(f"{codigo}: registrado v{version['id_version_modelo']} {version['estado_version']}")
            if version["estado_version"] == "APROBADO":
                version = _respuesta(
                    cliente.post(f"/prediccion/modelos/{version['id_version_modelo']}/sombra"),
                    f"{codigo}: poner en sombra",
                )
            if version["estado_version"] not in ("SOMBRA", "ACTIVO"):
                raise ErrorRegistro(f"{codigo}: v{version['id_version_modelo']} quedó {version['estado_version']}")
            print(f"{codigo}: v{version['id_version_modelo']} en {version['estado_version']}")
            catalogo.append((animal, id_activo, version["id_version_modelo"]))
        except ErrorRegistro as exc:
            errores += 1
            print(f"ERROR {exc}", file=sys.stderr)

    if args.aplicar and catalogo:
        args.salida.mkdir(parents=True, exist_ok=True)
        entradas = []
        for animal, id_activo, id_version in catalogo:
            onnx, linea_base, metadatos = animal["rutas"]
            for ruta in (onnx, linea_base, metadatos):
                shutil.copy2(ruta, args.salida / ruta.name)
            entradas.append({
                "id_activo_biologico": id_activo, "id_version_modelo": id_version,
                "onnx": onnx.name, "linea_base": linea_base.name, "metadatos": metadatos.name,
            })
        (args.salida / "catalogo.json").write_text(json.dumps({"modelos": entradas}, indent=2) + "\n", encoding="utf-8")
        print(f"catalogo.json con {len(entradas)} modelo(s) en {args.salida}")
    return 1 if errores else 0


if __name__ == "__main__":
    sys.exit(main())
