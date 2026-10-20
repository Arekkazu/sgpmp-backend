"""
TC-M04-G117 (RF-71 RNF-01/RNF-02/RNF-15/Restricción 7, CU-13) - "Tiempo de
ejecución y aislamiento del entorno productivo." Grupo existente de
RF-71.

RELACIÓN CON TC-M04-G102 (hallazgo raíz): no existe ningún endpoint que
inicie un proceso de entrenamiento de forma asíncrona ni que devuelva un
`id_proceso` (confirmado en G102) -- no hay nada que cronometrar.

(a)-(e) -- HALLAZGO ÚNICO: no existe ningún proceso observable cuyo
    tiempo de ejecución por fase pueda medirse, ni ninguna petición que
    responda de inmediato con un `id_proceso` para consultar después. El
    único endpoint real relacionado (`POST /prediccion/modelos`) es
    sincrónico: recibe el artefacto YA ENTRENADO vía HTTP multipart y
    responde con el resultado del registro en la misma petición -- no
    hay ningún "proceso asíncrono de 2-6 horas" que este backend orqueste
    u observe.

Cómo se prueba: confirmación de que el endpoint de registro es un
`async def` que ejecuta el caso de uso de forma sincrónica (sin cola,
sin tarea en segundo plano) dentro de la misma función del handler.

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
            "use_case.execute(dto, internal_key=...) directamente dentro de la misma funcion y "
            "devuelve el resultado de esa llamada -- no encola una tarea en background, no "
            "despacha a Celery/RQ, no devuelve un id_proceso para consultar despues. Es "
            "sincrono de principio a fin; no hay ningun proceso de 2-6 horas que este backend "
            "orqueste."
        ) if 'background' not in bloque.lower() and 'celery' not in bloque.lower() and '.delay(' not in bloque else None
