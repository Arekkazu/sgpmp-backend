# | Fecha      | Nombre   | Que se hizo                                                     |
# |------------|----------|-----------------------------------------------------------------|
# | 2026-11-14 | Arekkazu | M08 RF-105: filtros por nivel, estado y módulo, y archivo a 90 días |
# | 2026-11-21 | destroyerban | INC-M08-382-G013 RF-105: la bandeja se pagina de 50 en 50 por defecto |
"""Caso de uso para consultar la bandeja interna del usuario autenticado.

RF-105: sin filtro de estado se ve el panel principal (nuevas y leídas); lo atendido o descartado
se consulta filtrando por ese estado. Lo de más de 90 días está archivado y solo sale si se pide.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

from src.identity_access.domain.repositories.notificacion_repository import (
    FiltroBandeja,
    NotificacionRepository,
)
from src.identity_access.domain.value_objects.nivel_notificacion import CRITICA

_ARCHIVO = timedelta(days=90)
# RF-105 reglas 7 y 10: la bandeja se pagina de 50 en 50. Es el valor por defecto y el máximo.
TAMANO_PAGINA_BANDEJA = 50


class ListarNotificacionesUseCase:
    """Consulta paginada y aislada por propietario de notificaciones internas."""

    def __init__(self, notificaciones_repo: NotificacionRepository):
        self.notificaciones_repo = notificaciones_repo

    def execute(
        self,
        id_usuario: int,
        pagina: int,
        tamano: int,
        solo_no_leidas: bool,
        nivel: Optional[str] = None,
        estado: Optional[str] = None,
        modulo: Optional[str] = None,
        incluir_archivadas: bool = False,
        ahora: Optional[datetime] = None,
    ) -> dict:
        tamano = min(tamano, TAMANO_PAGINA_BANDEJA)
        offset = (pagina - 1) * tamano
        desde = None if incluir_archivadas else (ahora or datetime.now(timezone.utc)) - _ARCHIVO
        filtro = FiltroBandeja(solo_no_leidas=solo_no_leidas, nivel=nivel, estado=estado, modulo=modulo,
                               desde=desde)
        repo = self.notificaciones_repo
        items = repo.listar_internas(id_usuario=id_usuario, filtro=filtro, offset=offset, limit=tamano)
        return {
            "total": repo.contar_internas(id_usuario=id_usuario, filtro=filtro),
            "no_leidas": repo.contar_internas(id_usuario=id_usuario, filtro=FiltroBandeja(solo_no_leidas=True)),
            # RF-103 FA-3: una crítica sin atender deja un aviso fijo en el dashboard.
            "criticas_pendientes": repo.contar_internas(id_usuario=id_usuario, filtro=FiltroBandeja(nivel=CRITICA)),
            "pagina": pagina,
            "tamano": tamano,
            "items": items,
        }
