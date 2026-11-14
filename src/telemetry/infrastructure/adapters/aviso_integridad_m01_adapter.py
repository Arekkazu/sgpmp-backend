# | Fecha      | Nombre  | Que se hizo |
# |------------|---------|-------------|
# | 2026-10-22 | Leandro | DEV-47 RF-63: integra avisos con contrato real RF-14 |
"""Sin semillas ni sustitución por eventos de otros módulos."""
from sqlalchemy import select, text
from src.identity_access.infrastructure.models.eventos_model import Eventos

from src.shared.errors import ServiceUnavailableError
from src.identity_access.infrastructure.repositories.evento_repository import SqlAlchemyEventoRepository
from src.identity_access.infrastructure.repositories.notificacion_repository import (
    ID_CANAL_INTERNO, SqlAlchemyNotificacionRepository,
)
from src.identity_access.domain.value_objects.evento_categoria import categoria_para_tipo_evento


class AvisoIntegridadM01Adapter:
    def __init__(self, db):
        self.db = db

    def notificar(self, id_incidente, ids_comprometidos):
        tipo = self.db.execute(text("SELECT id_tipo_evento FROM modulo1.tipos_eventos WHERE nombre='INTEGRIDAD_COMPROMETIDA'")).scalar_one_or_none()
        if tipo is None:
            raise ServiceUnavailableError(code='CONTRATO_AVISO_INTEGRIDAD_PENDIENTE',
                message='Falta el tipo de evento RF-14 para integridad IoT.')
        try:
            categoria_para_tipo_evento(tipo)
        except ValueError as exc:
            raise ServiceUnavailableError(code='CONTRATO_AVISO_INTEGRIDAD_PENDIENTE',
                message='El tipo de evento no está integrado en el contrato RF-10.') from exc
        usuarios = list(self.db.execute(text('''SELECT DISTINCT u.id_usuario FROM modulo1.usuarios u
            JOIN modulo1.cuentas_usuarios c ON c.id_usuario=u.id_usuario
            JOIN modulo1.estados_cuentas e ON e.id_estado_cuenta=c.id_estado_cuenta
            WHERE modulo1.fn_rol_protegido(u.id_rol) AND lower(e.nombre)='activo'
            ORDER BY u.id_usuario''')).scalars())
        if not usuarios:
            raise ServiceUnavailableError(code='DESTINATARIOS_INTEGRIDAD_NO_DISPONIBLES',
                message='No hay Administradores activos disponibles para el aviso.')
        eventos = SqlAlchemyEventoRepository(self.db)
        avisos = SqlAlchemyNotificacionRepository(self.db)
        eventos.registrar(tipo_evento=tipo, exitoso=False, id_usuario=usuarios[0],
            detalle={'id_incidente_iot': id_incidente, 'ids_comprometidos': ids_comprometidos})
        id_evento = self.db.execute(select(Eventos.id_evento).where(
            Eventos.tipo_evento == tipo, Eventos.id_usuario == usuarios[0],
            Eventos.detalle['id_incidente_iot'].astext == id_incidente,
        )).scalar_one_or_none()
        if id_evento is None:
            raise RuntimeError('No se confirmó el evento origen RF-14.')
        for usuario in usuarios:
            avisos.registrar(id_evento, usuario, ID_CANAL_INTERNO,
                f'Integridad IoT comprometida. Incidente {id_incidente}.', 'en_cola')
        return len(usuarios)
