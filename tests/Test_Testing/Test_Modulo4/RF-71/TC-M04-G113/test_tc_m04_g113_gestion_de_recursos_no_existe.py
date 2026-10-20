"""
TC-M04-G113 (RF-71 Restricción 9/RNF-03, CU-10) - "Gestión y límites de
recursos." Grupo existente de RF-71.

RELACIÓN CON TC-M04-G102 (hallazgo raíz): no existe ningún endpoint de
retraining ni proceso observable (confirmado en G102).

(a)-(f) -- HALLAZGO ÚNICO: no existe ningún monitoreo de CPU/RAM/disco,
    ninguna reducción de paralelización ni ningún límite configurable en
    M09 relacionado con recursos de entrenamiento. Grep exhaustivo de
    "ALMACENAMIENTO_INSUFICIENTE", "paralelizacion" y "cgroups"/"stress"
    en todo `src/`: cero coincidencias. No hay ningún proceso real cuyo
    consumo de recursos pudiera medirse.

Cómo se prueba: grep exhaustivo de los términos de gestión de recursos de
la ficha en todo src/.

Como correrlo:
    python -m pytest <ruta>\\test_tc_m04_g113_gestion_de_recursos_no_existe.py -v \
        --html=<ruta>\\resultados\\resultado_TC-M04-G113.html --self-contained-html
"""
from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[5]


class TestNoExisteGestionDeRecursos:
    @pytest.mark.parametrize('termino', [
        'ALMACENAMIENTO_INSUFICIENTE', 'paralelizacion', 'limite_cpu', 'limite_ram',
    ])
    def test_termino_de_gestion_de_recursos_no_existe(self, termino):
        archivos = [
            str(p.relative_to(REPO_ROOT)) for p in (REPO_ROOT / 'src').rglob('*.py')
            if termino in p.read_text(encoding='utf-8', errors='ignore')
        ]
        pytest.fail(
            f"HALLAZGO: '{termino}' no existe en ningun archivo de src/ (encontrados: "
            f"{archivos or 'ninguno'}). No hay ningun mecanismo de monitoreo ni limite de "
            f"recursos para procesos de entrenamiento."
        ) if not archivos else None
