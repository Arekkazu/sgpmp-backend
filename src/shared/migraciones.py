"""Chequeo de arranque: ¿la BD tiene aplicadas las migraciones que este código espera?

INC-M02-51-G44: TEST corría código de rc.48 sobre una base sin la migración
``d8e232bc81a3``. El refresh fallaba con HTTP 500 y el desfase solo se descubría
cuando un usuario perdía la sesión. Esto lo deja en el log al arrancar.
"""
from __future__ import annotations

import logging
from pathlib import Path

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Engine

logger = logging.getLogger(__name__)

_DIRECTORIO_ALEMBIC = Path(__file__).resolve().parents[2] / "alembic"


def verificar_migraciones_aplicadas(engine: Engine) -> None:
    """Compara las heads de ``alembic/versions`` con las de ``alembic_version``.

    Solo lectura y nunca bloquea el arranque: aplicar migraciones sigue siendo
    una acción deliberada del DBA (``alembic upgrade head``).
    """
    config = Config()
    config.set_main_option("script_location", str(_DIRECTORIO_ALEMBIC))
    try:
        esperadas = set(ScriptDirectory.from_config(config).get_heads())
        with engine.connect() as conexion:
            aplicadas = set(MigrationContext.configure(conexion).get_current_heads())
    except Exception:
        logger.warning("No se pudo verificar la revisión de Alembic de la BD al arrancar.", exc_info=True)
        return

    if aplicadas != esperadas:
        logger.error(
            "La BD no está en la revisión de Alembic que espera este código "
            "(BD: %s, código: %s). Los endpoints que dependen de migraciones "
            "pendientes van a fallar; ejecuta 'alembic upgrade head' si la BD "
            "está atrasada.",
            sorted(aplicadas) or "sin alembic_version",
            sorted(esperadas),
        )
