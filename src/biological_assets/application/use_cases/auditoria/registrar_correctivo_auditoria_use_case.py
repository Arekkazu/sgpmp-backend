"""RF-52 E5: "El administrador puede crear un registro correctivo en RF-52 con
tipo_evento = REGISTRO_CORRECTIVO_AUDITORIA y el motivo". El historial RF-46 no
se modifica; solo se completa su rastro en la bitácora.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.biological_assets.domain.entities.activo_biologico import EventoAuditoria, registros_rf46
from src.biological_assets.domain.repositories.bitacora_auditoria_repository import BitacoraAuditoriaRepository
from src.biological_assets.domain.repositories.reconciliacion_auditoria_repository import (
    ReconciliacionAuditoriaRepository,
)
from src.biological_assets.infrastructure.dto.registrar_correctivo_auditoria_dto import (
    RegistrarCorrectivoAuditoriaDTO,
)
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import ConflictError, NotFoundError


class RegistrarCorrectivoAuditoriaUseCase:

    def __init__(
        self,
        db: Session,
        repo: ReconciliacionAuditoriaRepository,
        bitacora_repo: BitacoraAuditoriaRepository,
    ) -> None:
        self.db = db
        self.repo = repo
        self.bitacora_repo = bitacora_repo

    def execute(self, dto: RegistrarCorrectivoAuditoriaDTO, usuario: UsuarioActual) -> EventoAuditoria:
        registro = self.repo.obtener_registro(dto.tabla, dto.id_registro)
        if registro is None:
            raise NotFoundError(
                code='REGISTRO_RF46_NO_ENCONTRADO',
                message=f'No existe un registro {dto.id_registro} de {dto.tabla} en el historial del activo (RF-46).',
            )

        # Un aviso de inconsistencia también lleva la llave, pero no es el registro
        # que falta: lo que se descarta es corregir algo que ya tiene su registro.
        if self.repo.tiene_auditoria(dto.tabla, dto.id_registro):
            raise ConflictError(
                code='REGISTRO_YA_AUDITADO',
                message=(
                    f'El registro {dto.id_registro} de {dto.tabla} ya tiene su registro en la bitácora; '
                    'no requiere un registro correctivo.'
                ),
            )

        evento = EventoAuditoria(
            rf_origen='RF52',
            tipo_evento='REGISTRO_CORRECTIVO_AUDITORIA',
            clasificacion_biologica='GESTION_OPERATIVA',
            resultado='EXITOSO',
            severidad_log='WARNING',
            timestamp_evento=datetime.now(timezone.utc),
            id_activo_biologico=registro.id_activo_biologico,
            descripcion=dto.motivo,
            detalle_tecnico={
                'registros_rf46': registros_rf46(**{dto.tabla: dto.id_registro}),
                'motivo': dto.motivo,
            },
            id_usuario_responsable=usuario.id_usuario,
        )
        # Aquí la bitácora es la operación misma, no un efecto secundario: si falla,
        # el administrador tiene que enterarse (500), no quedar en el buffer.
        try:
            self.bitacora_repo.registrar(evento)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return evento
