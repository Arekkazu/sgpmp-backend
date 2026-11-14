# | Fecha      | Nombre                   | Que se hizo                                                          |
# |------------|--------------------------|----------------------------------------------------------------------|
# | 2026-11-07 | Juan Sebastian Gutierrez | TC-M05-G14 RF-76: genera resultado JSON (checkpoints) desde JUnit    |
"""Genera resultados/resultado_TC-M05-G14.json a partir del JUnit XML y de la traza HTTP.

Solo lee evidencias/run-20261107-105918/{resultado_TC-M05-G14.xml, trazas_http.jsonl} (la carpeta
de este script) y escribe el JSON (UTF-8 sin BOM) en resultados/. Todo se deriva de ESTA corrida:
veredicto y "defectos" salen de los tests fallidos reales. No incluye bodies, cabeceras, tokens,
rutas absolutas ni run_id.
"""
from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

AQUI = Path(__file__).resolve().parent
TC = AQUI.parents[1]
JUNIT = AQUI / "resultado_TC-M05-G14.xml"
TRAZA = AQUI / "trazas_http.jsonl"
SALIDA = TC / "resultados" / "resultado_TC-M05-G14.json"

E400 = "HTTP 400 VAL_ENTRADA, campo en fields[]"
E201 = "HTTP 201 estado_registro VALIDADO, sin fecha_fin_retiro y conteo +1"

# nombre del test (id de pytest) -> (paso, esperado)
DESCRIPCION = {
    "test_00_inocuidad_linea_base": ("Inocuidad: conteo base", "conteo base registrado y HTTP 200 Rollback exitoso"),
    "test_01_preparacion": ("Preparacion: activo y fase abierta",
                            "activo INDIVIDUAL id_estado=1 con fecha_inicio_ciclo y fase abierta (POST /fases 201)"),
    "test_a_rechazo_campos[A01-id_activo_biologico-omitido]": ("A01 sin id_activo_biologico", E400),
    "test_a_rechazo_campos[A02-nombre_medicamento-omitido]": ("A02 sin nombre_medicamento", E400),
    "test_a_rechazo_campos[A03-fecha_aplicacion-omitido]": ("A03 sin fecha_aplicacion", E400),
    "test_a_rechazo_campos[A04-hora_aplicacion-omitido]": ("A04 sin hora_aplicacion", E400),
    "test_a_rechazo_campos[A05-via_administracion-omitido]": ("A05 sin via_administracion", E400),
    "test_a_rechazo_campos[A06-dosis_aplicada-omitido]": ("A06 sin dosis_aplicada", E400),
    "test_a_rechazo_campos[A07-unidad_dosis-omitido]": ("A07 sin unidad_dosis", E400),
    "test_a_rechazo_campos[A08-motivo_aplicacion-omitido]": ("A08 sin motivo_aplicacion", E400),
    "test_a_rechazo_campos[A09-costo_unitario-omitido]": ("A09 sin costo_unitario", E400),
    "test_a_rechazo_campos[A10-nombre_veterinario-omitido]": ("A10 sin nombre_veterinario", E400),
    "test_a_rechazo_campos[A11-via_administracion-invalido]": (
        "A11 via_administracion ORAL2", "HTTP 400 VIA_ADMINISTRACION_INVALIDA, campo en fields[]"),
    "test_a_rechazo_campos[A12-nombre_veterinario-invalido]": ("A12 nombre_veterinario null", E400),
    "test_a_rechazo_campos[A13-unidad_dosis-invalido]": ("A13 unidad_dosis vacia", E400),
    "test_a_rechazo_campos[A14-hora_aplicacion-invalido]": ("A14 hora_aplicacion 25:99", E400),
    "test_a_rechazo_campos[A15-fecha_aplicacion-invalido]": ("A15 fecha_aplicacion 15-09-2026", E400),
    "test_a_rechazo_campos[A16-nombre_medicamento-invalido]": ("A16 nombre_medicamento de 51 caracteres", E400),
    "test_a17_estado_activo_tras_grupo_a": ("A17 activo sigue ACTIVO tras subcaso (a)",
                                            "HTTP 200 con id_estado=1 (RF-44 no invocado)"),
    "test_b_valores_limite[B01-dosis_0]": ("B01 dosis 0", "HTTP 400, mensaje 'mayor a cero' (E4)"),
    "test_b_valores_limite[B02-dosis_negativa]": ("B02 dosis -1", "HTTP 400, mensaje 'mayor a cero' (E4)"),
    "test_b_valores_limite[B04-motivo_9_caracteres]": ("B04 motivo de 9 caracteres",
                                                       "HTTP 400 (E6), motivo_aplicacion en fields[] o '10 caracteres'"),
    "test_b_valores_limite[B05-motivo_10_caracteres]": ("B05 motivo de 10 caracteres", E201),
    "test_b_valores_limite[B06-fecha_hoy]": ("B06 fecha hoy", E201),
    "test_b_valores_limite[B07-fecha_manana]": ("B07 fecha hoy+1", "HTTP 400 FECHA_FUTURA (E2)"),
    "test_b_valores_limite[B08-fecha_inicio_ciclo_menos_1]": ("B08 fecha_inicio_ciclo - 1",
                                                              "HTTP 400 FECHA_ANTERIOR_A_CICLO (E3)"),
    "test_b_valores_limite[B09-fecha_inicio_ciclo]": ("B09 fecha = fecha_inicio_ciclo", E201),
    "test_zz_cierre_corrida_principal": ("Teardown corrida principal", "HTTP 200 Rollback exitoso"),
    "test_zz_b03_dosis_minima[B03-dosis_0.0001]": ("B03 dosis 0.0001",
                                                   "HTTP 201 VALIDADO, conteo +1 y cantidad = 0.0001 (decimal 10,4)"),
    "test_zz_inocuidad_final": ("Inocuidad: conteo final", "conteo final = base y HTTP 200 Rollback exitoso"),
}


def _trazas() -> tuple[dict[str, list[dict]], dict[str, int]]:
    por_test: dict[str, list[dict]] = {}
    conteos: dict[str, int] = {}
    for linea in TRAZA.read_text(encoding="utf-8").splitlines():
        d = json.loads(linea)
        if d.get("tipo") == "conteo":
            conteos[d["momento"]] = d["total_medicamentos"]
            continue
        por_test.setdefault(d["test"], []).append(d)
    return por_test, conteos


def _http(d: dict) -> str:
    texto = f"HTTP {d['http']}" if d.get("http") is not None else f"sin respuesta ({d.get('error_conexion')})"
    return texto + (f" {d['error_code']}" if d.get("error_code") else "")


def _obtenido(nombre: str, reqs: list[dict], conteos: dict[str, int]) -> str:
    post_med = [d for d in reqs if d["metodo"] == "POST" and d["ruta"] == "/suministros/medicamentos"]
    teardown = [d for d in reqs if d["metodo"] == "DELETE"]
    if nombre == "test_00_inocuidad_linea_base":
        return f"conteo base {conteos.get('base')}; teardown {_http(teardown[-1])}"
    if nombre == "test_zz_inocuidad_final":
        return (f"conteo final {conteos.get('final')} (base {conteos.get('base')}); "
                f"teardown {_http(teardown[-1])}")
    if nombre == "test_01_preparacion":
        fases = [d for d in reqs if d["metodo"] == "POST" and d["ruta"].endswith("/fases")]
        return f"POST /fases {_http(fases[-1])}" if fases else "fase ya abierta"
    if nombre == "test_a17_estado_activo_tras_grupo_a":
        return _http(reqs[-1]) + " (id_estado=1)"
    if nombre == "test_zz_cierre_corrida_principal":
        return _http(teardown[-1])
    if post_med:
        d = post_med[-1]
        texto = _http(d)
        campos = [c.get("field") for c in d.get("fields") or []]
        if campos:
            texto += f", fields={campos}"
        if nombre.startswith("test_zz_b03") and d.get("http") != 201:
            texto += " (sin cantidad devuelta)"
        return texto
    return "sin request registrada"


def main() -> None:
    por_test, conteos = _trazas()
    raiz = ET.parse(JUNIT).getroot()
    checkpoints, vistos = [], set()
    for caso in raiz.iter("testcase"):
        nombre = caso.get("name")
        if nombre in vistos:  # una entrada extra de teardown no es un test distinto
            continue
        vistos.add(nombre)
        fallo = caso.find("failure") is not None or caso.find("error") is not None
        paso, esperado = DESCRIPCION[nombre]
        checkpoints.append({
            "paso": paso,
            "esperado": esperado,
            "obtenido": _obtenido(nombre, por_test.get(nombre, []), conteos),
            "estado": "FALLA" if fallo else "OK",
        })
    ok = sum(c["estado"] == "OK" for c in checkpoints)
    falla = sum(c["estado"] == "FALLA" for c in checkpoints)
    summary = {
        "total": len(checkpoints), "ok": ok, "falla": falla,
        "veredicto": "RECHAZADO" if falla else "APROBADO",
    }
    fallidos = [c for c in checkpoints if c["estado"] == "FALLA"]
    if fallidos:  # "defectos" solo si hay fallos reales en ESTA corrida
        summary["defectos"] = {
            "fallos": [f"{c['paso']}: esperado {c['esperado']}; obtenido {c['obtenido']}" for c in fallidos],
            "subcasos_afectados": [c["paso"].split()[0] for c in fallidos],
        }
    resultado = {"tc": "TC-M05-G14", "summary": summary, "checkpoints": checkpoints}
    SALIDA.write_text(json.dumps(resultado, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"escrito {SALIDA.relative_to(TC)}: {len(checkpoints)} checkpoints, {ok} OK, {falla} FALLA")


if __name__ == "__main__":
    main()
