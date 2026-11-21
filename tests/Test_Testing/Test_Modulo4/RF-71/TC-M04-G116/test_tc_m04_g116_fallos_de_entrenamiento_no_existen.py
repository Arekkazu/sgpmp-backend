"""
TC-M04-G116 (RF-71 E3/E7/RNF-13, CU-12) - "Fallos del entrenamiento y
degradación no resuelta." Ficha sin cambios de fondo por la RFC-009.

RELACIÓN CON TC-M04-G102/G112 (hallazgos raíz): no existe ningún proceso
de entrenamiento observable que pueda fallar; el modelo activo solo se
reemplaza desde `ActivarVersionModeloUseCase`, nunca desde el registro.

(a)/(d) Error de ejecución -> REENTRENAMIENTO_FALLIDO; sin bucle de
    reintentos -- HALLAZGO: `REENTRENAMIENTO_FALLIDO` solo existe como
    valor de enum en el DDL, nunca usado desde Python.
(b) E7, degradación + fallo -> modelo activo se MANTIENE + alerta
    CRITICAL -- PARCIALMENTE CONFIRMADO, SOLO EN EL EFECTO: el modelo
    activo se mantiene siempre porque ningún código de este backend lo
    activa automáticamente (confirmado en G112(d)) -- no existe ninguna
    alerta CRITICAL específica para este escenario.
(c) Sin residuos tras un fallo -- NO EVALUABLE: no hay ningún proceso que
    pueda dejar residuos.
(e) RNF-13 -- CONFIRMADO CORRECTO, mismo fundamento estructural que (b).

Cómo se prueba: grep exhaustivo de 'REENTRENAMIENTO_FALLIDO'/'DEGRADACION'
en código Python.

Como correrlo:
    python -m pytest <ruta>\\test_tc_m04_g116_fallos_de_entrenamiento_no_existen.py -v \
        --html=<ruta>\\resultados\\resultado_TC-M04-G116.html --self-contained-html
"""
from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[5]


class TestNoExisteManejoDeFallosDeEntrenamiento:
    def test_reentrenamiento_fallido_no_existe_en_codigo_python(self):
        archivos = [
            str(p.relative_to(REPO_ROOT)) for p in (REPO_ROOT / 'src').rglob('*.py')
            if 'REENTRENAMIENTO_FALLIDO' in p.read_text(encoding='utf-8', errors='ignore')
        ]
        pytest.fail(
            f"HALLAZGO (a)/(d): 'REENTRENAMIENTO_FALLIDO' no existe en ningun archivo Python de "
            f"src/ (encontrados: {archivos or 'ninguno'})."
        ) if not archivos else None

    def test_no_existe_ninguna_alerta_critical_especifica_de_degradacion_fallida(self):
        archivos = [
            str(p.relative_to(REPO_ROOT)) for p in (REPO_ROOT / 'src/prediction').rglob('*.py')
            if 'DEGRADACION' in p.read_text(encoding='utf-8', errors='ignore')
        ]
        pytest.fail(
            f"HALLAZGO (b): 'DEGRADACION' no aparece en ningun archivo de src/prediction/ "
            f"(encontrados: {archivos or 'ninguno'})."
        ) if not archivos else None
