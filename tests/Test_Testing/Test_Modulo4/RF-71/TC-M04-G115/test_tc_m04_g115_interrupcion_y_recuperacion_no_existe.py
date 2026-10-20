"""
TC-M04-G115 (RF-71 E8/CA-16/RNF-13/RNF-14, CU-11) - "Interrupción,
recuperación y reanudación." Grupo existente de RF-71.

RELACIÓN CON TC-M04-G102 (hallazgo raíz): no existen
`POST /api/v1/m04/retraining/{id_proceso}/cancel` ni `.../resume`
(confirmado en G102).

(a)-(f) -- HALLAZGO ÚNICO: no existe ningún mecanismo de checkpoint,
    reanudación por fase ni detección de "datos ya no válidos". El
    estado `estado_ciclo` de `modulo4.ciclos_entrenamientos` en el DDL
    baseline (`PLANIFICADO`/`EN_PROCESO`/...) sugiere que se pensó una
    máquina de estados para esto, pero -- como confirma G102 -- ninguna
    fila llega a existir nunca en esa tabla desde código alcanzable, y
    no hay ningún endpoint de cancelación/reanudación en ningún router.
    El subescenario (f), el más crítico de la ficha (un artefacto
    parcial que pase la verificación de hash), no es evaluable: no hay
    ningún artefacto parcial posible porque no hay ningún entrenamiento
    que interrumpir.

Cómo se prueba: grep exhaustivo de "cancel"/"resume"/"reanudar"/
"checkpoint" en todos los routers de M04.

Como correrlo:
    python -m pytest <ruta>\\test_tc_m04_g115_interrupcion_y_recuperacion_no_existe.py -v \
        --html=<ruta>\\resultados\\resultado_TC-M04-G115.html --self-contained-html
"""
from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[5]


class TestNoExisteCancelacionNiReanudacion:
    @pytest.mark.parametrize('termino', ['cancel', 'resume', 'reanudar', 'checkpoint'])
    def test_termino_no_existe_en_ningun_router_de_m04(self, termino):
        archivos = [
            str(p.relative_to(REPO_ROOT)) for p in (REPO_ROOT / 'src/prediction/infrastructure/routers').glob('*.py')
            if termino in p.read_text(encoding='utf-8', errors='ignore').lower()
        ]
        pytest.fail(
            f"HALLAZGO: '{termino}' no existe en ningun router de src/prediction/infrastructure/"
            f"routers/ (encontrados: {archivos or 'ninguno'}). No hay ningun endpoint de "
            f"cancelacion ni reanudacion para procesos de entrenamiento."
        ) if not archivos else None
