"""Caso de uso para consultar la bandeja interna del usuario autenticado."""
from src.identity_access.domain.repositories.notificacion_repository import (
    NotificacionRepository,
)


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
    ) -> dict:
        tamano = min(tamano, 50)
        offset = (pagina - 1) * tamano
        items = self.notificaciones_repo.listar_internas(
            id_usuario=id_usuario,
            solo_no_leidas=solo_no_leidas,
            offset=offset,
            limit=tamano,
        )
        total = self.notificaciones_repo.contar_internas(
            id_usuario=id_usuario,
            solo_no_leidas=solo_no_leidas,
        )
        no_leidas = self.notificaciones_repo.contar_internas(
            id_usuario=id_usuario,
            solo_no_leidas=True,
        )
        return {
            "total": total,
            "no_leidas": no_leidas,
            "pagina": pagina,
            "tamano": tamano,
            "items": items,
        }
