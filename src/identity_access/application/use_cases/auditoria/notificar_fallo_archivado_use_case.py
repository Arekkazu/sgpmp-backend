"""Caso de uso de la alerta interna por fallo del archivado de auditoría RF-10.

Cubre el flujo alterno "Error en el proceso de archivado automático": cuando la
tarea diaria de retención no puede completarse, el RF exige disparar una alerta
crítica al administrador como notificación interna, no solo dejar rastro en el log.

La alerta se materializa como un evento de auditoría de tipo
``FALLO_ARCHIVADO_AUDITORIA`` más una notificación en la bandeja interna (RF-14)
por cada destinatario.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from src.identity_access.domain.repositories.evento_repository import EventoRepository
from src.identity_access.domain.repositories.notificacion_repository import (
    NotificacionRepository,
)
from src.identity_access.domain.repositories.usuario_repository import UsuarioRepository

TIPO_FALLO_ARCHIVADO = 25
ID_CANAL_INTERNO = 2

# Destinatarios: quien puede leer el historial de auditoría (recurso 6, acción 2).
# Se resuelve contra `modulo1.permisos` en vez de fijar un id_rol en código.
RECURSO_AUDITORIA = 6
ACCION_LEER = 2

MENSAJE_ALERTA = (
    "Fallo en política de retención: No se pudo completar el archivado de logs "
    "antiguos."
)


class NotificarFalloArchivadoUseCase:
    """Emite la alerta interna cuando el archivado automático RF-10 falla."""

    def __init__(
        self,
        eventos_repo: EventoRepository,
        notificaciones_repo: NotificacionRepository,
        usuarios_repo: UsuarioRepository,
        db: Session,
    ):
        self.eventos_repo = eventos_repo
        self.notificaciones_repo = notificaciones_repo
        self.usuarios_repo = usuarios_repo
        self.db = db

    def execute(self, causa: str) -> int:
        """Registra el evento de fallo y notifica a cada destinatario.

        Args:
            causa: Resumen del error real. El RF ejemplifica falta de espacio en
                disco, pero la causa concreta no se puede afirmar, así que se
                adjunta el texto de la excepción que interrumpió el proceso.

        Returns:
            Cantidad de notificaciones creadas. Cero si ningún usuario tiene
            permiso de lectura de auditoría: en ese caso solo queda el evento.
        """
        destinatarios = self.usuarios_repo.listar_ids_con_permiso(
            id_recurso=RECURSO_AUDITORIA,
            id_accion=ACCION_LEER,
        )

        try:
            # El evento necesita un id_usuario (NOT NULL con FK hacia usuarios) y
            # este proceso no tiene actor humano; se atribuye al primer
            # destinatario. Si no hay ninguno, no hay a quién atribuirlo ni a quién
            # avisar, así que solo queda el log del scheduler.
            if not destinatarios:
                return 0

            self.eventos_repo.registrar(
                tipo_evento=TIPO_FALLO_ARCHIVADO,
                exitoso=False,
                id_usuario=destinatarios[0],
                detalle={"proceso": "ARCHIVADO_AUDITORIA", "causa": causa},
            )
            id_evento = self.notificaciones_repo.buscar_ultimo_evento_id(
                id_usuario=destinatarios[0],
                tipo_evento=TIPO_FALLO_ARCHIVADO,
            )

            mensaje = f"{MENSAJE_ALERTA} Detalle: {causa}"
            for id_usuario in destinatarios:
                self.notificaciones_repo.registrar(
                    id_evento=id_evento,
                    id_usuario=id_usuario,
                    id_canal=ID_CANAL_INTERNO,
                    mensaje=mensaje,
                    estado="en_cola",
                )

            self.db.commit()
            return len(destinatarios)
        except Exception:
            self.db.rollback()
            raise
