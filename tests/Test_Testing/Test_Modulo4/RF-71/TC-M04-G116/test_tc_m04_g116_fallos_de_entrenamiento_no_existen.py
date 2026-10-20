"""
TC-M04-G116 (RF-71 E3/E7/RNF-13, CU-12) - "Fallos del entrenamiento y
degradación no resuelta." Grupo existente de RF-71.

RELACIÓN CON TC-M04-G102/G104 (hallazgos raíz): no existe ningún proceso
de entrenamiento observable que pueda fallar (confirmado en G102); el
único punto donde el modelo activo se preserva ante un fallo es, por
diseño estructural, trivialmente cierto -- no porque exista un manejo de
fallos explícito, sino porque no existe ningún mecanismo que PUEDA
modificar el modelo activo fuera de `ActivarVersionModeloUseCase` (ver
TC-M04-G112(d)).

(a)/(d) Error de ejecución -> REENTRENAMIENTO_FALLIDO; fallos
    consecutivos sin bucle de reintentos -- HALLAZGO: no existe ningún
    código que pueda fallar de esta manera; `REENTRENAMIENTO_FALLIDO`
    solo existe como valor de enum en el DDL, nunca usado desde Python
    (mismo patrón que G102/G104).
(b) E7: con trigger=DEGRADACION, si el proceso no entrega versión -> el
    modelo activo se MANTIENE, alerta CRITICAL al administrador --
    PARCIALMENTE CONFIRMADO, SOLO EN EL EFECTO: el modelo activo SÍ se
    mantiene siempre que no se llame a `ActivarVersionModeloUseCase`
    (confirmado en TC-M04-G112(d)) -- pero no porque exista una lógica
    de "fallo de degradación [es igual a] preservar el activo"; es una
    consecuencia estructural de que ningún código de este backend activa
    modelos automáticamente. No existe ninguna alerta CRITICAL específica
    para este escenario (grep de 'alerta.*CRITICAL' ligado a
    reentrenamiento: cero coincidencias).
(c) Sin residuos tras un fallo (artefactos parciales, datasets
    temporales, entradas incompletas en RF-69) -- NO EVALUABLE: no hay
    ningún proceso que pueda dejar residuos porque no hay ningún proceso.
(e) RNF-13: en ningún fallo se compromete el modelo activo -- CONFIRMADO
    CORRECTO, mismo fundamento estructural que (b).

Cómo se prueba: grep exhaustivo de 'REENTRENAMIENTO_FALLIDO' en código
Python + confirmación de que ActivarVersionModeloUseCase es el único
camino hacia `esta_produccion=True` (ya probado en TC-M04-G112).

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
            f"src/ (encontrados: {archivos or 'ninguno'}) -- solo existe como valor de enum en "
            f"el DDL baseline, nunca emitido desde codigo alcanzable."
        ) if not archivos else None

    def test_no_existe_ninguna_alerta_critical_especifica_de_degradacion_fallida(self):
        archivos = [
            str(p.relative_to(REPO_ROOT)) for p in (REPO_ROOT / 'src/prediction').rglob('*.py')
            if 'DEGRADACION' in p.read_text(encoding='utf-8', errors='ignore')
        ]
        pytest.fail(
            f"HALLAZGO (b): 'DEGRADACION' no aparece en ningun archivo de src/prediction/ "
            f"(encontrados: {archivos or 'ninguno'}) -- no existe ninguna alerta CRITICAL "
            f"especifica para 'degradacion detectada pero reentrenamiento fallido'."
        ) if not archivos else None
