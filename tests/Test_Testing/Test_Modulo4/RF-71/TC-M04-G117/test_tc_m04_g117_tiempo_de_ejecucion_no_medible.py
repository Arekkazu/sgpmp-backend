"""
TC-M04-G117 (RF-71 RNF-01/RNF-02/RNF-15/Restricción 7, CU-13) - "Tiempo de
ejecución y aislamiento del entorno productivo." Ficha sin cambios de
fondo por la RFC-009.

RELACIÓN CON TC-M04-G102 (hallazgo raíz): no existe ningún endpoint que
inicie un proceso de entrenamiento de forma asíncrona ni que devuelva un
`id_proceso` -- no hay nada que cronometrar.

(a)-(e) -- HALLAZGO ÚNICO: el único endpoint real relacionado
    (`POST /prediccion/modelos`) es sincrónico de principio a fin.

Cómo se prueba: confirmación de que el handler de registro ejecuta el
caso de uso directamente, sin cola ni tarea en background.

Como correrlo:
    python -m pytest <ruta>\\test_tc_m04_g117_tiempo_de_ejecucion_no_medible.py -v \
        --html=<ruta>\\resultados\\resultado_TC-M04-G117.html --self-contained-html
"""
from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[5]


class TestNoHayProcesoAsincronoQueCronometrar:
    def test_el_endpoint_de_registro_ejecuta_sincronicamente_sin_cola(self):
        archivo = REPO_ROOT / 'src/prediction/infrastructure/routers/version_modelo_router.py'
        texto = archivo.read_text(encoding='utf-8')
        bloque = texto.split('async def registrar_version_modelo(')[1].split('@router.get(')[0]
        pytest.fail(
            "HALLAZGO: el handler de POST /prediccion/modelos llama a "
            "use_case.execute(dto, internal_key=...) directamente y devuelve el resultado -- "
            "no encola ninguna tarea en background ni devuelve un id_proceso para consultar "
            "despues. Es sincrono de principio a fin."
        ) if 'background' not in bloque.lower() and 'celery' not in bloque.lower() and '.delay(' not in bloque else None
