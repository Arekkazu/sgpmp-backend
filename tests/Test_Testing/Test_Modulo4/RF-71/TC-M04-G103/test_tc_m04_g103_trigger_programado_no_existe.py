"""
TC-M04-G103 (RF-71 v2.0 Fase 1/Restricción 6/RFC-009, CU-01) - "Activación
por trigger PROGRAMADO." Reintento sobre la ficha v2.0 (añade
modo_generacion por defecto y colisión entre modos distintos).

RELACIÓN CON TC-M04-G102 (hallazgo raíz, vigente): no existe ningún
endpoint ni scheduler que dispare nada automáticamente; `modo_generacion`
no existe en ningún archivo de `src/` ni en el DDL (confirmado en G102).

(a) Disparo semestral sin intervención humana, con `modo_generacion =
    REENTRENAMIENTO` por defecto -- HALLAZGO: no existe ningún scheduler
    (APScheduler/Celery/pg_cron) en todo el repositorio; y como
    `modo_generacion` no existe, tampoco puede tener "un valor por
    defecto".
(b)/(c)/(e) -- NO EJECUTABLES, mismo motivo que (a).
(d) Colisión también entre `modo_generacion` distintos (REENTRENAMIENTO
    en curso vs. ventana que dispararía CALIBRACION_EN_SITIO) -- NO
    EVALUABLE: ninguno de los dos conceptos existe, por lo que no puede
    haber colisión entre ellos.

Cómo se prueba: grep exhaustivo de schedulers y de `modo_generacion` en
el repositorio.

Como correrlo:
    python -m pytest <ruta>\\test_tc_m04_g103_trigger_programado_no_existe.py -v \
        --html=<ruta>\\resultados\\resultado_TC-M04-G103.html --self-contained-html
"""
from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[5]


class TestNoExisteMecanismoDeDisparoAutomatico:
    @pytest.mark.parametrize('termino', ['apscheduler', 'celery', 'pg_cron', 'cron.schedule'])
    def test_no_existe_ningun_scheduler(self, termino):
        archivos = [
            str(p.relative_to(REPO_ROOT)) for p in (REPO_ROOT / 'src').rglob('*.py')
            if termino in p.read_text(encoding='utf-8', errors='ignore').lower()
        ]
        texto_main = (REPO_ROOT / 'main.py').read_text(encoding='utf-8').lower()
        texto_ddl = (REPO_ROOT / 'alembic/baseline/esquema_baseline.sql').read_text(
            encoding='utf-8', errors='ignore').lower()
        hay_match = bool(archivos) or termino in texto_main or termino in texto_ddl
        pytest.fail(
            f"HALLAZGO (a): '{termino}' no aparece en src/, main.py ni en el DDL baseline -- "
            f"no existe ningun mecanismo que dispare procesos de forma periodica/automatica."
        ) if not hay_match else None


class TestSubCasoDColisionEntreModosNoEvaluable:
    def test_modo_generacion_sigue_sin_existir(self):
        archivos = [
            str(p.relative_to(REPO_ROOT)) for p in (REPO_ROOT / 'src').rglob('*.py')
            if 'modo_generacion' in p.read_text(encoding='utf-8', errors='ignore')
        ]
        pytest.fail(
            f"HALLAZGO (d): 'modo_generacion' no existe en ningun archivo de src/ (encontrados: "
            f"{archivos or 'ninguno'}) -- no puede haber colision entre modos de generacion "
            f"distintos porque el concepto de modo de generacion no existe."
        ) if not archivos else None
