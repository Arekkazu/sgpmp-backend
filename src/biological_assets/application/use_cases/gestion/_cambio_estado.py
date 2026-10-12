"""Helper compartido: única vía para cambiar el estado de un activo y dejar su histórico
(RF-44).
"""

from __future__ import annotations

from datetime import datetime, timedelta

from src.biological_assets.domain.entities.activo_biologico import ActivoBiologico, HistoricoEstado
from src.biological_assets.domain.repositories.historico_estado_repository import HistoricoEstadoRepository


def aplicar_cambio_estado(
    activo: ActivoBiologico,
    id_estado_nuevo: int,
    fecha: datetime,
    motivo: str,
    usuario_id: int,
    historico_repo: HistoricoEstadoRepository,
    modulo_origen: str,
) -> HistoricoEstado:
    """Punto único de cambio de estado (RF-44).

    Muta la entidad (que valida BAJA irreversible, redundancia y la matriz de
    transiciones) y registra el histórico correspondiente. Invocado por los
    tres flujos que pueden cambiar el estado de un activo biológico — manual
    (RF-44, ``MANUAL``), cierre de ciclo (RF-38, ``RF-38``) y baja (RF-45,
    ``RF-45``) — para que ninguno reimplemente la regla por su cuenta.

    ``modulo_origen`` es obligatorio para que el histórico distinga el origen
    real del cambio (RF-44), en lugar de un ``modulo2`` genérico.
    """
    id_estado_anterior = activo.id_estado
    activo.cambiar_estado(id_estado_nuevo)
    # INC-M02-78-G49 (#573): trg_fn_estado_activo_unico_vigente toma como
    # "último estado" el de mayor fecha_cambio. Un cambio cuya fecha es solo
    # día (medianoche o fin de día UTC) quedaba antes de otro cambio del mismo
    # día guardado con la hora real (p. ej. un evento sanitario) y el
    # siguiente cambio respondía 409 ESTADO_ACTIVO_INCONSISTENTE. El
    # histórico debe seguir el orden real de los cambios.
    ultimo = historico_repo.obtener_ultimo_cambio(activo.id_activo_biologico)
    if ultimo is not None and fecha <= ultimo.fecha_cambio:
        fecha = ultimo.fecha_cambio + timedelta(microseconds=1)
    return historico_repo.registrar(
        id_activo=activo.id_activo_biologico,
        id_estado_anterior=id_estado_anterior,
        id_estado_nuevo=id_estado_nuevo,
        fecha=fecha,
        motivo=motivo,
        usuario_id=usuario_id,
        modulo_origen=modulo_origen,
    )
