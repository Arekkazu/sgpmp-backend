"""
TC-M04-G107 (RF-71 Entradas/E5/CA-10, CU-04) - "Validación de parámetros
de entrenamiento y algoritmo por defecto." Grupo existente de RF-71.

RELACIÓN CON TC-M04-G102 (hallazgo raíz): no existe `POST /api/v1/m04/
retraining` ni `PUT /api/v1/config/m04/retraining` (confirmado en G102).

(a)-(f) -- HALLAZGO ÚNICO: no existe ningún DTO, validador ni catálogo en
    M09 para parámetros de entrenamiento (algoritmo, n_estimadores,
    tecnica_validacion, ventana_temporal_minutos, semilla_aleatoria). El
    único DTO real de M04 relacionado con un modelo es
    `RegistrarVersionModeloDTO` (RF-69), que recibe el artefacto YA
    ENTRENADO -- no parámetros de entrenamiento -- por lo que ninguno de
    estos 6 subescenarios tiene código que ejecutar.

Cómo se prueba: grep exhaustivo de los nombres de parámetros de la ficha
en src/prediction/ y src/configuration/ (M09).

Como correrlo:
    python -m pytest <ruta>\\test_tc_m04_g107_validacion_parametros_no_existe.py -v \
        --html=<ruta>\\resultados\\resultado_TC-M04-G107.html --self-contained-html
"""
from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[5]


class TestNoExisteValidacionDeParametrosDeEntrenamiento:
    @pytest.mark.parametrize('termino', [
        'n_estimadores', 'tecnica_validacion', 'ventana_temporal_minutos', 'semilla_aleatoria',
    ])
    def test_parametro_no_existe_en_prediction_ni_configuration(self, termino):
        archivos = [
            str(p.relative_to(REPO_ROOT)) for carpeta in ('src/prediction', 'src/configuration')
            for p in (REPO_ROOT / carpeta).rglob('*.py')
            if termino in p.read_text(encoding='utf-8', errors='ignore')
        ]
        pytest.fail(
            f"HALLAZGO: '{termino}' no existe en src/prediction/ ni en src/configuration/ (M09) "
            f"(encontrados: {archivos or 'ninguno'}). El unico DTO real relacionado con un modelo "
            f"(RegistrarVersionModeloDTO) recibe el artefacto ya entrenado, no parametros de "
            f"entrenamiento."
        ) if not archivos else None
