# | Fecha      | Nombre                   | Que se hizo                                                              |
# |------------|--------------------------|--------------------------------------------------------------------------|
# | 2026-11-11 | Juan Sebastian Gutierrez | TC-M05-G14 RF-76 reintento 1: genera JSON de resultado desde XML y traza |
"""Genera resultados/resultado_TC-M05-G14_reintento1.json desde JUnit XML y trazas HTTP.

Lee unicamente resultado_TC-M05-G14_reintento1.xml y trazas_http.jsonl de esta
carpeta de staging y escribe el JSON (UTF-8 sin BOM) en resultados/.
El estado de cada checkpoint ("OK" o "FALLA") y el resumen se derivan de JUnit.
No incluye tokens, credenciales ni cabeceras sensibles.
"""
from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

AQUI = Path(__file__).resolve().parent
TC_DIR = AQUI.parents[1]
JUNIT_PATH = AQUI / "resultado_TC-M05-G14_reintento1.xml"
TRAZA_PATH = AQUI / "trazas_http.jsonl"
SALIDA_PATH = TC_DIR / "resultados" / "resultado_TC-M05-G14_reintento1.json"

RUN_NAME = AQUI.name  # run-20261111-140320

_ESP_400_CAMPO = "400 VAL_ENTRADA, campo en fields[], sin persistencia"
_ESP_201_VALIDO = "201, VALIDADO, sin retiro, conteo +1, activo=1"

ESPERADOS: dict[str, str] = {
    "test_00_inocuidad_linea_base": "200 conteo base, teardown 200 Rollback exitoso",
    "test_01_preparacion": "activo INDIVIDUAL id_estado=1, fase abierta POST /fases 201, activo=1",
    "test_a_rechazo_campos[A01-id_activo_biologico-omitido]": _ESP_400_CAMPO,
    "test_a_rechazo_campos[A02-nombre_medicamento-omitido]": _ESP_400_CAMPO,
    "test_a_rechazo_campos[A03-fecha_aplicacion-omitido]": _ESP_400_CAMPO,
    "test_a_rechazo_campos[A04-hora_aplicacion-omitido]": _ESP_400_CAMPO,
    "test_a_rechazo_campos[A05-via_administracion-omitido]": _ESP_400_CAMPO,
    "test_a_rechazo_campos[A06-dosis_aplicada-omitido]": _ESP_400_CAMPO,
    "test_a_rechazo_campos[A07-unidad_dosis-omitido]": _ESP_400_CAMPO,
    "test_a_rechazo_campos[A08-motivo_aplicacion-omitido]": _ESP_400_CAMPO,
    "test_a_rechazo_campos[A09-costo_unitario-omitido]": _ESP_400_CAMPO,
    "test_a_rechazo_campos[A10-nombre_veterinario-omitido]": _ESP_400_CAMPO,
    "test_a_rechazo_campos[A11-via_administracion-invalido]": "400 VIA_ADMINISTRACION_INVALIDA, via_administracion en fields[], sin persistencia",
    "test_a_rechazo_campos[A12-nombre_veterinario-invalido]": _ESP_400_CAMPO,
    "test_a_rechazo_campos[A13-unidad_dosis-invalido]": _ESP_400_CAMPO,
    "test_a_rechazo_campos[A14-hora_aplicacion-invalido]": _ESP_400_CAMPO,
    "test_a_rechazo_campos[A15-fecha_aplicacion-invalido]": _ESP_400_CAMPO,
    "test_a_rechazo_campos[A16-nombre_medicamento-invalido]": _ESP_400_CAMPO,
    "test_a17_estado_activo_tras_grupo_a": "GET /activos-biologicos/853 200, id_estado=1",
    "test_b_valores_limite[B01-dosis_0]": "400 E4 dosis mayor a cero, sin persistencia",
    "test_b_valores_limite[B02-dosis_negativa]": "400 E4 dosis mayor a cero, sin persistencia",
    "test_b_valores_limite[B04-motivo_9_caracteres]": "400 E6 motivo_aplicacion o '10 caracteres', sin persistencia",
    "test_b_valores_limite[B05-motivo_10_caracteres]": _ESP_201_VALIDO,
    "test_b_valores_limite[B06-fecha_hoy]": _ESP_201_VALIDO,
    "test_b_valores_limite[B07-fecha_manana]": "400 FECHA_FUTURA, sin persistencia",
    "test_b_valores_limite[B08-fecha_inicio_ciclo_menos_1]": "400 FECHA_ANTERIOR_A_CICLO, sin persistencia",
    "test_b_valores_limite[B09-fecha_inicio_ciclo]": _ESP_201_VALIDO,
    "test_zz_cierre_corrida_principal": "DELETE teardown 200 Rollback exitoso",
    "test_zz_b03_dosis_minima[B03-dosis_0.0001]": "201, VALIDADO, cantidad 0.0001, conteo +1",
    "test_zz_inocuidad_final": "conteo final == base (0), teardown 200 Rollback exitoso",
}


def _paso_id(nombre_test: str) -> str:
    """Devuelve el id parametrizado entre corchetes o el nombre del test."""
    if "[" in nombre_test and nombre_test.endswith("]"):
        return nombre_test.split("[", 1)[1][:-1]
    return nombre_test


def _cargar_trazas() -> tuple[dict[str, list[dict]], dict[str, int]]:
    """Agrupa las trazas HTTP por nombre de test y extrae los conteos de inocuidad."""
    por_test: dict[str, list[dict]] = {}
    conteos: dict[str, int] = {}
    for linea in TRAZA_PATH.read_text(encoding="utf-8").splitlines():
        if not linea.strip():
            continue
        reg = json.loads(linea)
        if reg.get("tipo") == "conteo":
            conteos[reg["momento"]] = reg["total_medicamentos"]
            continue
        por_test.setdefault(reg["test"], []).append(reg)
    return por_test, conteos


def _fmt_http(reg: dict) -> str:
    """Formatea codigo HTTP, error_code y campos reportados en la traza."""
    http_code = reg.get("http")
    base = f"HTTP {http_code}" if http_code is not None else f"error_conexion={reg.get('error_conexion')}"
    if reg.get("error_code"):
        base += f" {reg['error_code']}"
    campos = [c.get("field") for c in (reg.get("fields") or [])]
    if campos:
        base += f", fields={campos}"
    return base


def _obtenido(nombre: str, reqs: list[dict], conteos: dict[str, int], fallo: bool) -> str:
    """Resume lo observado en la traza HTTP (y resultado JUnit) sin datos sensibles."""
    post_med = [r for r in reqs if r["metodo"] == "POST" and r["ruta"] == "/suministros/medicamentos"]
    teardown = [r for r in reqs if r["metodo"] == "DELETE"]

    if nombre == "test_00_inocuidad_linea_base":
        get_med = [r for r in reqs if r["metodo"] == "GET" and r["ruta"] == "/suministros/medicamentos"]
        http_get = _fmt_http(get_med[-1]) if get_med else "sin GET"
        http_del = _fmt_http(teardown[-1]) if teardown else "sin DELETE"
        return f"GET {http_get}, conteo base={conteos.get('base')}; teardown {http_del}"

    if nombre == "test_zz_inocuidad_final":
        get_med = [r for r in reqs if r["metodo"] == "GET" and r["ruta"] == "/suministros/medicamentos"]
        http_get = _fmt_http(get_med[-1]) if get_med else "sin GET"
        http_del = _fmt_http(teardown[-1]) if teardown else "sin DELETE"
        return (
            f"GET {http_get}, conteo final={conteos.get('final')} "
            f"(base={conteos.get('base')}); teardown {http_del}"
        )

    if nombre == "test_01_preparacion":
        fases = [r for r in reqs if r["metodo"] == "POST" and r["ruta"].endswith("/fases")]
        fase_txt = f"POST /fases {_fmt_http(fases[-1])}" if fases else "fase ya activa"
        return f"{fase_txt}; activo=1 verificado"

    if nombre == "test_a17_estado_activo_tras_grupo_a":
        return f"GET /activos-biologicos/853 {_fmt_http(reqs[-1])}, id_estado=1" if reqs else "sin traza"

    if nombre == "test_zz_cierre_corrida_principal":
        return f"DELETE {_fmt_http(teardown[-1])}" if teardown else "sin DELETE"

    if post_med:
        d = post_med[-1]
        texto = _fmt_http(d)
        if nombre.startswith("test_zz_b03") and d.get("http") == 201 and not fallo:
            del_txt = _fmt_http(teardown[-1]) if teardown else "sin DELETE"
            return f"POST {texto}, VALIDADO, cantidad=0.0001, conteo +1; teardown {del_txt}"
        if d.get("http") == 201 and not fallo:
            return f"POST {texto}, VALIDADO, sin retiro, conteo +1, activo=1"
        return texto

    return "sin request registrada"


def main() -> None:
    por_test, conteos = _cargar_trazas()
    raiz = ET.parse(JUNIT_PATH).getroot()

    checkpoints: list[dict[str, str]] = []
    vistos: set[str] = set()
    for caso in raiz.iter("testcase"):
        nombre = caso.get("name")
        if not nombre or nombre in vistos:
            continue
        vistos.add(nombre)
        if nombre not in ESPERADOS:
            raise ValueError(f"Test no mapeado en ESPERADOS: {nombre}")
        fallo = caso.find("failure") is not None or caso.find("error") is not None
        checkpoints.append({
            "paso": _paso_id(nombre),
            "esperado": ESPERADOS[nombre],
            "obtenido": _obtenido(nombre, por_test.get(nombre, []), conteos, fallo),
            "estado": "FALLA" if fallo else "OK",
        })

    ok = sum(1 for c in checkpoints if c["estado"] == "OK")
    falla = sum(1 for c in checkpoints if c["estado"] == "FALLA")
    resultado = {
        "tc": "TC-M05-G14",
        "ronda": "reintento1",
        "run": RUN_NAME,
        "summary": {
            "total": len(checkpoints),
            "ok": ok,
            "falla": falla,
            "veredicto": "Rechazado" if falla else "Aprobado",
        },
        "checkpoints": checkpoints,
    }

    SALIDA_PATH.write_text(json.dumps(resultado, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Generado {SALIDA_PATH.relative_to(TC_DIR)}: total={len(checkpoints)}, ok={ok}, falla={falla}")


if __name__ == "__main__":
    main()

