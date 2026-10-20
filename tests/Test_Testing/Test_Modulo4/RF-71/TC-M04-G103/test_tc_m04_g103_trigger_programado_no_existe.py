"""
TC-M04-G103 (RF-71 Fase 1/Restricción 6, CU-01) - "Activación por trigger
PROGRAMADO." Grupo existente de RF-71.

RELACIÓN CON TC-M04-G102 (hallazgo raíz): no existe ningún endpoint
`PUT /api/v1/config/m04/retraining` ni `GET /api/v1/m04/retraining/
{id_proceso}` -- confirmado exhaustivamente en G102. Este TC añade un
hallazgo específico de (a)/(c): no solo falta la API, falta el propio
MECANISMO DE DISPARO AUTOMÁTICO.

Código bajo prueba: búsqueda de cualquier scheduler (APScheduler, Celery
beat, cron) en `src/` y `main.py`, y de `pg_cron`/`cron.schedule` en el
DDL baseline.

(a) Disparo en la ventana semestral sin intervención humana -- HALLAZGO:
    no existe ningún scheduler en la aplicación Python (ni APScheduler ni
    Celery) ni ninguna extensión `pg_cron` programada en el DDL -- el
    único mecanismo que podría disparar `sp_iniciar_ciclo_reentrenamiento`
    automáticamente (`CALL` dentro de `sp_evaluar_degradacion_modelo` o
    uno equivalente para PROGRAMADO) no tiene nada que lo invoque
    periódicamente. Ni siquiera existe un procedimiento
    `sp_evaluar_...programado` separado -- solo `sp_evaluar_degradacion_modelo`
    (DEGRADACION) fue encontrado en el DDL.
(b)/(d)/(e) -- NO EJECUTABLES: dependen de (a); sin ningún disparo
    automático que observar, no hay intervalo mínimo que verificar, ni
    proceso en curso que colisionar, ni ventana de indisponibilidad que
    simular.
(c) "Cambiar la periodicidad en M09 sin redespliegue" -- HALLAZGO: no
    existe `PUT /api/v1/config/m04/retraining` (confirmado en G102); no
    hay ningún parámetro de periodicidad de reentrenamiento en M09 que
    cambiar.

Cómo se prueba: grep exhaustivo de schedulers y de `pg_cron` en el
repositorio.

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
            f"HALLAZGO (a)/(c): '{termino}' no aparece en src/, main.py ni en el DDL baseline -- "
            f"no existe ningun mecanismo que dispare sp_iniciar_ciclo_reentrenamiento ni ningun "
            f"otro proceso de forma periodica/automatica."
        ) if not hay_match else None

    def test_no_existe_un_procedimiento_separado_para_trigger_programado(self):
        texto_ddl = (REPO_ROOT / 'alembic/baseline/esquema_baseline.sql').read_text(
            encoding='utf-8', errors='ignore')
        pytest.fail(
            "HALLAZGO (a): el unico procedimiento de evaluacion de trigger encontrado en el DDL "
            "es sp_evaluar_degradacion_modelo (trigger=DEGRADACION) -- no existe ningun "
            "procedimiento equivalente para el trigger PROGRAMADO (semestral). Ademas, ninguno "
            "de los dos tiene nada que lo invoque periodicamente (ver G102)."
        ) if 'sp_evaluar_degradacion_modelo' in texto_ddl and 'sp_evaluar_programado' not in texto_ddl else None
