# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-28 | destroyerban | INC-M03-177-G57B RF-58: aviso E7 fuera del GET del dashboard (BackgroundTasks) |
"""Aviso de RF-58 E7 en segundo plano: el dashboard no espera al SMTP.

INC-M03-177-G57B (CA-13, 500 ms): ``AvisoSinUmbralEmailAdapter`` corría dentro del GET.
Por cada sensor GRIS sin aviso en 24 h escribía la bitácora y enviaba un correo por
Administrador, con un timeout SMTP de 8 s. Con unas 25 conexiones que no respondían, QA
midió 3 min 21 s y un 500. Ahora la respuesta sale de inmediato y el aviso corre después,
con su propia sesión de sistema. Mismo patrón que ``NotificacionSesionBackgroundAdapter``.

Mientras un aviso está en curso, sus sensores no se agendan otra vez: un refresco del
dashboard antes de que el primero termine no duplica correos. La bitácora sigue siendo
la que evita repetir el aviso en 24 h.
"""
from __future__ import annotations

import copy
import logging
import threading

from fastapi import BackgroundTasks

from src.shared.database import sesion_sistema
from src.telemetry.domain.entities.monitoreo import EstadoSensorActual
from src.telemetry.domain.repositories.aviso_sin_umbral_port import AvisoSinUmbralPort
from src.telemetry.infrastructure.adapters.aviso_sin_umbral_email_adapter import AvisoSinUmbralEmailAdapter

logger = logging.getLogger(__name__)

_EN_CURSO: set[int] = set()
_CANDADO = threading.Lock()


def _procesar_aviso_sin_umbral(sensores: list[EstadoSensorActual]) -> None:
    """Avisa con una sesión independiente del request y libera los sensores al terminar."""
    db = None
    try:
        db = sesion_sistema()
        AvisoSinUmbralEmailAdapter(db).avisar(sensores)
    except Exception:
        logger.exception('RF-58 E7: no se pudo procesar en segundo plano el aviso de variables sin umbral')
    finally:
        if db is not None:
            db.close()
        with _CANDADO:
            _EN_CURSO.difference_update(s.id_sensor for s in sensores)


class AvisoSinUmbralBackgroundAdapter(AvisoSinUmbralPort):
    def __init__(self, background_tasks: BackgroundTasks) -> None:
        self._background_tasks = background_tasks

    def avisar(self, sensores: list[EstadoSensorActual]) -> int:
        with _CANDADO:
            nuevos = [s for s in sensores if s.id_sensor not in _EN_CURSO]
            _EN_CURSO.update(s.id_sensor for s in nuevos)
        if not nuevos:
            return 0
        # Copias: el use case sigue preparando la respuesta sobre los mismos objetos.
        self._background_tasks.add_task(_procesar_aviso_sin_umbral, [copy.copy(s) for s in nuevos])
        return len(nuevos)
