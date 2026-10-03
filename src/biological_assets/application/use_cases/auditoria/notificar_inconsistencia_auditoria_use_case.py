"""RF-52 E5: alerta CRITICAL al administrador cuando la reconciliación encuentra
filas del historial RF-46 sin su registro en la bitácora.

Mismo mecanismo que la alerta de fallo de archivado de RF-10
(``NotificarFalloArchivadoUseCase``): un evento en ``modulo1.eventos`` y una
notificación en la bandeja interna (RF-14) por destinatario.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from src.biological_assets.domain.entities.activo_biologico import RegistroRf46
from src.identity_access.domain.repositories.evento_repository import EventoRepository
from src.identity_access.domain.repositories.notificacion_repository import NotificacionRepository
from src.identity_access.domain.repositories.usuario_repository import UsuarioRepository

TIPO_INCONSISTENCIA_AUDITORIA_M02 = 28
ID_CANAL_INTERNO = 2

# Destinatarios: quien puede crear el registro correctivo (recurso 31
# bitacora_auditoria_m02, acción C), resuelto contra modulo1.permisos y no con un
# id_rol fijo en código.
RECURSO_BITACORA_M02 = 31
ACCION_CREAR = 1


class NotificarInconsistenciaAuditoriaUseCase:

    def __init__(
        self,
        eventos_repo: EventoRepository,
        notificaciones_repo: NotificacionRepository,
        usuarios_repo: UsuarioRepository,
        db: Session,
    ) -> None:
        self.eventos_repo = eventos_repo
        self.notificaciones_repo = notificaciones_repo
        self.usuarios_repo = usuarios_repo
        self.db = db

    def execute(self, inconsistencias: list[RegistroRf46]) -> int:
        """Devuelve cuántas notificaciones creó; 0 si nadie tiene el permiso."""
        destinatarios = self.usuarios_repo.listar_ids_con_permiso(
            id_recurso=RECURSO_BITACORA_M02,
            id_accion=ACCION_CREAR,
        )
        # El evento exige un id_usuario y este proceso no tiene actor humano: se
        # atribuye al primer destinatario. Sin destinatarios solo quedan la
        # entrada CRITICAL de la bitácora y el log.
        if not destinatarios:
            return 0

        try:
            self.eventos_repo.registrar(
                tipo_evento=TIPO_INCONSISTENCIA_AUDITORIA_M02,
                exitoso=False,
                id_usuario=destinatarios[0],
                detalle={
                    'proceso': 'RECONCILIACION_RF46_RF52',
                    'registros_rf46': [{'tabla': r.tabla, 'id': r.id} for r in inconsistencias],
                },
            )
            id_evento = self.notificaciones_repo.buscar_ultimo_evento_id(
                id_usuario=destinatarios[0],
                tipo_evento=TIPO_INCONSISTENCIA_AUDITORIA_M02,
            )
            mensaje = (
                f'Inconsistencia de auditoría en Activos Biológicos: {len(inconsistencias)} registros '
                'del historial no tienen su registro en la bitácora. Revise los eventos '
                'INCONSISTENCIA_RF46_RF52 y cree el registro correctivo que corresponda.'
            )
            for id_usuario in destinatarios:
                self.notificaciones_repo.registrar(
                    id_evento=id_evento,
                    id_usuario=id_usuario,
                    id_canal=ID_CANAL_INTERNO,
                    mensaje=mensaje,
                    estado='en_cola',
                )
            self.db.commit()
            return len(destinatarios)
        except Exception:
            self.db.rollback()
            raise
