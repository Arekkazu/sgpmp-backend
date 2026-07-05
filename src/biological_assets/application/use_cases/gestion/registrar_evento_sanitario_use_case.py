from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from src.biological_assets.application.use_cases.gestion._event_validations import (
    validar_estado_permite_eventos,
    validar_fecha_evento,
)
from src.biological_assets.domain.entities.activo_biologico import EventoActivo, EventoAuditoria, EventoSanitario, HistoricoEstado
from src.biological_assets.domain.repositories.activo_biologico_repository import ActivoBiologicoRepository
from src.biological_assets.domain.repositories.bitacora_auditoria_repository import BitacoraAuditoriaRepository
from src.biological_assets.domain.repositories.evento_activo_repository import EventoActivoRepository
from src.biological_assets.domain.repositories.historico_estado_repository import HistoricoEstadoRepository
from src.biological_assets.infrastructure.dto.registrar_evento_sanitario_dto import RegistrarEventoSanitarioDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import BusinessRuleError, NotFoundError

_TIPOS_REQUIEREN_DIAGNOSTICO = {'TRATAMIENTO', 'VACUNACION'}
_MAPA_ESTADO = {'EN_TRATAMIENTO': 3, 'AISLADO': 4}


class RegistrarEventoSanitarioUseCase:

    def __init__(
        self,
        db: Session,
        activo_repo: ActivoBiologicoRepository,
        evento_repo: EventoActivoRepository,
        historico_repo: HistoricoEstadoRepository,
        bitacora_repo: BitacoraAuditoriaRepository | None = None,
    ) -> None:
        self.db = db
        self.activo_repo = activo_repo
        self.evento_repo = evento_repo
        self.historico_repo = historico_repo
        self.bitacora_repo = bitacora_repo

    def execute(
        self,
        id_activo: int,
        dto: RegistrarEventoSanitarioDTO,
        usuario: UsuarioActual,
    ) -> tuple[EventoActivo, Optional[HistoricoEstado]]:
        activo = self.activo_repo.obtener_por_id(id_activo)
        if activo is None:
            raise NotFoundError(code='ACTIVO_NO_ENCONTRADO', message=f'El activo biológico con id {id_activo} no existe.')

        validar_estado_permite_eventos(activo)

        fecha = dto.fecha or datetime.now(timezone.utc)
        validar_fecha_evento(fecha, activo, self.evento_repo)

        if dto.tipo in _TIPOS_REQUIEREN_DIAGNOSTICO:
            if not self.evento_repo.tiene_diagnostico_previo(id_activo):
                raise BusinessRuleError(
                    code='DIAGNOSTICO_PREVIO_REQUERIDO',
                    message=(
                        f'No se puede registrar un evento de tipo {dto.tipo} sin un diagnóstico clínico previo. '
                        f'Registre primero un evento de tipo DIAGNOSTICO sobre este activo.'
                    ),
                )

        evento = EventoActivo(
            id_activo_biologico=id_activo,
            fecha=fecha,
            id_usuario=usuario.id_usuario,
            descripcion=dto.descripcion,
            sanitario=EventoSanitario(
                tipo=dto.tipo,
                diagnostico=dto.diagnostico,
                medicamento=dto.medicamento,
                dosis=dto.dosis,
                unidad_dosis=dto.unidad_dosis,
                frecuencia=dto.frecuencia,
                duracion=dto.duracion,
                observaciones=dto.observaciones,
            ),
        )

        try:
            resultado = self.evento_repo.guardar(evento)
            historico: Optional[HistoricoEstado] = None
            if dto.solicitar_estado:
                id_estado_nuevo = _MAPA_ESTADO[dto.solicitar_estado]
                id_estado_anterior = activo.id_estado
                activo.cambiar_estado(id_estado_nuevo)
                historico = self.historico_repo.registrar(
                    id_activo=id_activo,
                    id_estado_anterior=id_estado_anterior,
                    id_estado_nuevo=id_estado_nuevo,
                    fecha=datetime.now(timezone.utc),
                    motivo=f'Evento sanitario: {dto.tipo}',
                    usuario_id=usuario.id_usuario,
                    modulo_origen='modulo2',
                )
            self.db.commit()
        except Exception as exc:
            self.db.rollback()
            if self.bitacora_repo:
                try:
                    self.bitacora_repo.registrar(EventoAuditoria(
                        rf_origen='RF41', tipo_evento='EVENTO_SANITARIO_FALLIDO',
                        clasificacion_biologica='SANITARIO', resultado='FALLIDO',
                        severidad_log='ERROR', timestamp_evento=datetime.now(timezone.utc),
                        id_activo_biologico=id_activo, tipo_activo=activo.tipo,
                        detalle_tecnico={'error': str(exc), 'tipo_sanitario': dto.tipo},
                        id_usuario_responsable=usuario.id_usuario,
                    ))
                    self.db.commit()
                except Exception:
                    pass
            raise

        if self.bitacora_repo:
            try:
                self.bitacora_repo.registrar(EventoAuditoria(
                    rf_origen='RF41', tipo_evento='EVENTO_SANITARIO_REGISTRADO',
                    clasificacion_biologica='SANITARIO', resultado='EXITOSO',
                    severidad_log='INFO', timestamp_evento=datetime.now(timezone.utc),
                    id_activo_biologico=id_activo, tipo_activo=activo.tipo,
                    descripcion=f'Evento sanitario registrado: {dto.tipo}',
                    detalle_tecnico={'tipo_sanitario': dto.tipo},
                    id_usuario_responsable=usuario.id_usuario,
                ))
                self.db.commit()
            except Exception:
                pass

        return resultado, historico
