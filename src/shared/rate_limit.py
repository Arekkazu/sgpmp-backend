"""Límite de tasa en memoria para endpoints sensibles a ráfagas de escritura.

INC-M09-21-G125-02: `POST /configuracion/dispositivos-iot` no aplicaba ningún
control de tasa — una ráfaga de 50 registros concurrentes se completó en
segundos sin ningún 429. Este módulo agrega un limitador reutilizable como
dependencia de FastAPI, en el mismo estilo que `require_permission`.

ponytail: contador en memoria de un solo proceso (ventana deslizante con
`deque` + `threading.Lock`), no distribuido entre workers/réplicas. Si el
backend se despliega con más de un proceso, cada uno lleva su propio contador
y el límite efectivo se multiplica por el número de instancias. Si eso llega
a importar, migrar a un backend compartido (Redis INCR+EXPIRE).
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from fastapi import Depends, Request

from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.shared.errors import TooManyRequestsError

_lock = threading.Lock()
_llamadas: dict[str, deque[float]] = defaultdict(deque)


def rate_limit(max_llamadas: int, ventana_segundos: float, *, alcance: str):
    """Limita a ``max_llamadas`` por ``ventana_segundos`` por usuario autenticado.

    Args:
        max_llamadas: Cantidad máxima de solicitudes permitidas en la ventana.
        ventana_segundos: Tamaño de la ventana deslizante, en segundos.
        alcance: Identificador del endpoint que reutiliza este limitador
            (evita que dos endpoints distintos compartan el mismo contador).

    Returns:
        Dependencia de FastAPI que lanza `TooManyRequestsError` (429) cuando
        el usuario autenticado excede el límite.
    """

    def dependencia(
        request: Request,
        usuario_actual: UsuarioActual = Depends(get_current_user),
    ) -> None:
        clave = f"{alcance}:{usuario_actual.id_usuario}"
        ahora = time.monotonic()
        with _lock:
            marcas = _llamadas[clave]
            while marcas and ahora - marcas[0] > ventana_segundos:
                marcas.popleft()
            if len(marcas) >= max_llamadas:
                raise TooManyRequestsError(
                    code="LIMITE_TASA_EXCEDIDO",
                    message=(
                        "Demasiadas solicitudes en poco tiempo. "
                        "Intenta de nuevo en unos momentos."
                    ),
                )
            marcas.append(ahora)

    return dependencia
