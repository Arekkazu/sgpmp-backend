"""TC-M09-286 — Compuerta previa al laboratorio local (RF-24 v2.0, CU05 Flujo F).

El caso es LOCAL, pero antes de levantar nada hay que comprobar que el artefacto que se llevaría
al laboratorio contiene realmente VISION. El paquete es explícito: **no se crea un laboratorio
local para una función inexistente** y no se construyen mocks para simular VISION.

Este test implementa esa compuerta sobre el código y las migraciones de la rama. Si falta
cualquiera de las piezas esenciales, deja TC-M09-286 como BLOQUEADO y **no** levanta Docker, no
crea base, no siembra datos y no toca configuración.

No ejecuta ningún POST ni abre ningún contenedor.

Uso:
    pytest test_tc_m09_286_local.py -v --noconftest
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest

FOLDER = "TC-M09-G140"
BASE_DIR = Path(__file__).resolve().parent
if BASE_DIR.name != FOLDER:
    raise RuntimeError(f"Directorio no autorizado para {FOLDER}")

GRUPO = "TC-M09-G140"
CASO = "TC-M09-286"
RF = "RF-24 v2.0"

RUN_ID = os.environ["G140_RUN_ID_LOCAL"]
OUT_DIR = BASE_DIR / "RESULTADOS" / RUN_ID
OUT_DIR.mkdir(parents=True, exist_ok=True)


def repo_root() -> Path:
    d = BASE_DIR
    for _ in range(12):
        if (d / ".git").exists():
            return d
        d = d.parent
    return BASE_DIR


# Coincidencias que NO acreditan VISION y hay que descartar para no producir un falso
# positivo de ejecutabilidad:
#   - CAMARA_VISION / _atributos_vision / ATRIBUTOS_VISION: es el TIPO DE DISPOSITIVO cámara y
#     sus atributos (resolución, fps, área de cobertura), no una operación de calibración VISION.
#   - "linea base de integridad" / integridad_baseline: es el baseline de integridad de RF-10,
#     no la línea base VISION del Flujo F.
FALSOS_POSITIVOS = (
    r"CAMARA_VISION",
    r"_atributos_vision",
    r"ATRIBUTOS_VISION",
    r"linea[_ ]?base de integridad",
    r"integridad_baseline",
)


def _sin_falsos_positivos(linea: str) -> bool:
    return not any(re.search(p, linea, re.IGNORECASE) for p in FALSOS_POSITIVOS)


def buscar(patron: str, carpetas: list[str]) -> list[str]:
    """Archivos del artefacto cuyo patrón coincide en una línea que no es falso positivo."""
    raiz = repo_root()
    hallados: list[str] = []
    for carpeta in carpetas:
        base = raiz / carpeta
        if not base.is_dir():
            continue
        for ruta in base.rglob("*.py"):
            try:
                texto = ruta.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for linea in texto.splitlines():
                if re.search(patron, linea, re.IGNORECASE) and _sin_falsos_positivos(linea):
                    hallados.append(str(ruta.relative_to(raiz)).replace("\\", "/"))
                    break
    return sorted(hallados)


def buscar_sin_filtro(patron: str, carpetas: list[str]) -> list[str]:
    """Igual que `buscar`, pero conservando los falsos positivos: sirve para documentarlos."""
    raiz = repo_root()
    hallados: list[str] = []
    for carpeta in carpetas:
        base = raiz / carpeta
        if not base.is_dir():
            continue
        for ruta in base.rglob("*.py"):
            try:
                texto = ruta.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if re.search(patron, texto, re.IGNORECASE):
                hallados.append(str(ruta.relative_to(raiz)).replace("\\", "/"))
    return sorted(hallados)


def test_compuerta_previa_al_laboratorio_local():
    raiz = repo_root()
    carpetas = ["src", "alembic"]

    # Piezas esenciales que el laboratorio necesitaría para que TC-286 sea ejecutable.
    piezas = {
        "operacion_vision": r"(?<![A-Za-z])VISION(?![A-Za-z])",
        "modo_calibracion": r"modo_calibracion",
        "persistencia_baseline_vision": r"linea[_ ]?base|lineas_base",
        "algoritmo_refinamiento": r"refinamiento|convergencia|mediana_iterativa",
        "configuracion_max_iter": r"max_iter|maximo_iteraciones",
        "configuracion_epsilon": r"epsilon",
        "fuente_vector_vision": r"vector_comportamiento|ventana_observacion",
        "percentiles_p5_p95": r"winsoriz|percentil|p95",
    }
    hallazgos = {nombre: buscar(patron, carpetas) for nombre, patron in piezas.items()}
    presentes = {nombre: bool(archivos) for nombre, archivos in hallazgos.items()}

    # "baseline" sí aparece en la rama, pero corresponde al baseline de integridad de RF-10 y al
    # dump de esquema: se deja constancia para que nadie lo confunda con la línea base VISION.
    baseline_integridad = buscar_sin_filtro(r"integridad_baseline|esquema_baseline", carpetas)
    falsos_positivos = {
        "CAMARA_VISION_y_atributos_de_camara": buscar_sin_filtro(r"CAMARA_VISION|ATRIBUTOS_VISION", carpetas),
        "linea_base_de_integridad_rf10": buscar_sin_filtro(r"linea[_ ]?base de integridad", carpetas),
    }

    ev = {
        "grupo": GRUPO, "caso": CASO, "requisito": RF,
        "ambiente": "LOCAL_AISLADO", "prueba_local": True, "run_id": RUN_ID,
        "fecha": datetime.now(timezone.utc).isoformat(),
        "artefacto_evaluado": {"repositorio": str(raiz.name), "carpetas": carpetas},
        "compuerta_previa": {
            "piezas_requeridas": presentes,
            "archivos_por_pieza": hallazgos,
            "cumplidas": sum(1 for v in presentes.values() if v),
            "total": len(presentes),
        },
        "falsos_positivos_descartados": {
            "coincidencias": falsos_positivos,
            "nota": ("CAMARA_VISION es el tipo de dispositivo cámara y ATRIBUTOS_VISION sus "
                     "atributos (resolución, fps, área de cobertura): no acreditan una operación "
                     "de calibración VISION. 'Línea base de integridad' es de RF-10. Contarlos "
                     "como presencia daría un falso positivo de ejecutabilidad."),
        },
        "baseline_existente_no_vision": {
            "archivos": baseline_integridad,
            "nota": ("Los 'baseline' de la rama son el baseline de integridad de RF-10 "
                     "(modulo1.integridad_baseline) y el dump de esquema. No son la línea base "
                     "VISION del Flujo F."),
        },
        "laboratorio": {
            "levantado": False,
            "motivo": ("No se crea un laboratorio local para una función inexistente: el paquete "
                       "lo prohíbe expresamente y no se construyen mocks para simular VISION."),
            "compose_no_creado": True,
        },
        "config": {"epsilon": None, "max_iter_original": None,
                   "max_iter_durante": None, "max_iter_restaurado": None},
        "baseline_previa": None, "dataset_no_convergente": None, "oracle": None,
        "response": None, "auditoria": None, "baseline_post": None,
        "presupuesto": {"postVisionPlanificadosLocal": 2, "postVisionEjecutados": 0},
    }

    ejecutable = all(presentes.values())
    ev["resultado"] = "APROBADO" if ejecutable else "BLOQUEADO / NO VERIFICABLE"
    ev["motivo"] = None if ejecutable else (
        "El artefacto de la rama no contiene la implementación VISION: faltan "
        + ", ".join(n for n, v in presentes.items() if not v)
        + ". Sin operación VISION, persistencia de línea base, algoritmo de refinamiento ni "
          "configuración de ε/máximo de iteraciones, el laboratorio no puede probar nada."
    )
    ev["seguridad"] = {"limpio": True, "criterio": "La compuerta solo lee archivos del repositorio."}

    (OUT_DIR / "evidencia.json").write_text(
        json.dumps(ev, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    assert ejecutable, (
        "TC-M09-286 queda BLOQUEADO / NO VERIFICABLE.\n" + ev["motivo"] +
        f"\nPiezas presentes: {ev['compuerta_previa']['cumplidas']}/{ev['compuerta_previa']['total']}"
    )
