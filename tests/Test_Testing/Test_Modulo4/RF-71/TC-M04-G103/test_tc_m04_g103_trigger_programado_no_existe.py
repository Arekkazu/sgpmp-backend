# | Fecha      | Nombre           | Que se hizo                                                        |
# |------------|------------------|--------------------------------------------------------------------|
# | 2026-11-03 | HulkyZeus        | TC-M04-G103 RF-71: reconstruye el test desde su reporte HTML       |
"""
TC-M04-G103 (RF-71) - Trigger PROGRAMADO del pipeline de reentrenamiento.

Verifica por inspeccion estatica del codigo que:
  (a) no existe ningun mecanismo que dispare procesos de forma
      periodica/automatica (scheduler), y
  (d) el concepto `modo_generacion` no existe, por lo que no puede evaluarse
      una colision entre modos de generacion distintos.

NOTA DE PROCEDENCIA (2026-11-03): el archivo original nunca se versiono en el
repositorio; solo se subio su reporte (resultados/resultado_TC-M04-G103.html).
Este archivo se RECONSTRUYO a partir del codigo y los mensajes que figuran en
ese reporte (5 tests: 4 parametrizados de (a) + 1 de (d)). Si Juan Pablo
conserva el original, debe prevalecer sobre este.

Estilo: igual que TC-M04-G102 -- el test FALLA ("HALLAZGO") mientras el
mecanismo no exista, y pasa cuando se implemente.
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
