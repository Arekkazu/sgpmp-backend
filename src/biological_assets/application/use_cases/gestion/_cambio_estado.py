from __future__ import annotations

from datetime import datetime

from src.biological_assets.domain.entities.activo_biologico import ActivoBiologico, HistoricoEstado
from src.biological_assets.domain.repositories.historico_estado_repository import HistoricoEstadoRepository


def aplicar_cambio_estado(
    activo: ActivoBiologico,
    id_estado_nuevo: int,
    fecha: datetime,
    motivo: str,
    usuario_id: int,
    historico_repo: HistoricoEstadoRepository,
    modulo_origen: str = 'modulo2',
) -> HistoricoEstado:
    """Punto único de cambio de estado (RF-44).

    Muta la entidad (que valida BAJA irreversible, redundancia y la matriz de
    transiciones) y registra el histórico correspondiente. Invocado por los
    tres flujos que pueden cambiar el estado de un activo biológico — manual
    (RF-44), cierre de ciclo (RF-38) y baja (RF-45) — para que ninguno
    reimplemente la regla por su cuenta.
    """
    id_estado_anterior = activo.id_estado
    activo.cambiar_estado(id_estado_nuevo)
    return historico_repo.registrar(
        id_activo=activo.id_activo_biologico,
        id_estado_anterior=id_estado_anterior,
        id_estado_nuevo=id_estado_nuevo,
        fecha=fecha,
        motivo=motivo,
        usuario_id=usuario_id,
        modulo_origen=modulo_origen,
    )
