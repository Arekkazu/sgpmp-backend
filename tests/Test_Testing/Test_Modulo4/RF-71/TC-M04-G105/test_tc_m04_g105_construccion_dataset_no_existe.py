"""
TC-M04-G105 (RF-71 Fase 2/Restricción 1/CA-1/CA-15, CU-03) - "Construcción
del dataset y prioridad de etiquetas." Grupo existente de RF-71.

RELACIÓN CON TC-M04-G102 (hallazgo raíz): no existe `POST /api/v1/m04/
retraining` ni `GET /api/v1/m04/datasets/{dataset_hash}` (confirmado en
G102). Este TC confirma, además, que no existe ningún código -- ni
siquiera un stub -- para la construcción del dataset en sí.

(a)-(f) -- HALLAZGO ÚNICO, que invalida los 6 subescenarios por igual: no
    existe ningún caso de uso, servicio ni función que construya un
    dataset de entrenamiento a partir de RF-62 (apto_para_ia)/RF-67
    (inferencia histórica)/RF-72 (retroalimentación clínica)/RF-59
    (telemetría). No hay ninguna noción de "prioridad de etiquetas" en el
    código -- ni siquiera una función con ese nombre o similar. A
    diferencia de TC-M03-G152 (RF-61), donde existía al menos un
    `ActivoBiologicoStubAdapter` que devolvía una lista vacía, aquí no
    hay absolutamente ningún punto de extensión, ni real ni stub.

Cómo se prueba: grep exhaustivo de términos del dominio de construcción de
dataset en todo `src/`.

Como correrlo:
    python -m pytest <ruta>\\test_tc_m04_g105_construccion_dataset_no_existe.py -v \
        --html=<ruta>\\resultados\\resultado_TC-M04-G105.html --self-contained-html
"""
from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[5]


class TestNoExisteConstruccionDeDataset:
    @pytest.mark.parametrize('termino', [
        'apto_para_ia', 'construir_dataset', 'ConstruirDataset', 'prioridad_etiquetado',
    ])
    def test_termino_de_construccion_de_dataset_no_existe_en_prediction(self, termino):
        archivos = [
            str(p.relative_to(REPO_ROOT)) for p in (REPO_ROOT / 'src/prediction').rglob('*.py')
            if termino in p.read_text(encoding='utf-8', errors='ignore')
        ]
        pytest.fail(
            f"HALLAZGO: '{termino}' no existe en ningun archivo de src/prediction/ (encontrados: "
            f"{archivos or 'ninguno'}). No hay ningun caso de uso de construccion de dataset en "
            f"el modulo real de M04 -- ni siquiera un stub, a diferencia de RF-61 (TC-M03-G152)."
        ) if not archivos else None
