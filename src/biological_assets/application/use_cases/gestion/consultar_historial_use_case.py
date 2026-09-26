from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from src.biological_assets.application.use_cases._registrar_evento_bitacora import registrar_evento_bitacora
from src.biological_assets.domain.entities.activo_biologico import EventoAuditoria, PaginaHistorial
from src.biological_assets.domain.repositories.activo_biologico_repository import ActivoBiologicoRepository
from src.biological_assets.domain.repositories.bitacora_auditoria_repository import BitacoraAuditoriaRepository
from src.biological_assets.domain.repositories.transferencia_repository import TransferenciaRepository
from src.biological_assets.infrastructure.dto.consultar_historial_dto import ConsultarHistorialDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import BusinessRuleError, NotFoundError


class ConsultarHistorialUseCase:

    def __init__(
        self,
        db: Session,
        activo_repo: ActivoBiologicoRepository,
        transferencia_repo: TransferenciaRepository,
        bitacora_repo: BitacoraAuditoriaRepository | None = None,
    ) -> None:
        self.db = db
        self.activo_repo = activo_repo
        self.transferencia_repo = transferencia_repo
        self.bitacora_repo = bitacora_repo

    def execute(
        self,
        id_activo: int,
        dto: ConsultarHistorialDTO,
        usuario: UsuarioActual,
        *,
        ids_fincas_permitidas: Optional[list[int]] = None,
    ) -> PaginaHistorial:
        # E-03: "No se ejecuta ninguna consulta" -- se valida antes de tocar la BD.
        if dto.fecha_inicio and dto.fecha_fin and dto.fecha_inicio > dto.fecha_fin:
            raise BusinessRuleError(
                code='RANGO_FECHAS_INVALIDO',
                message=(
                    f'La fecha de inicio del filtro {dto.fecha_inicio.isoformat()} no puede ser posterior '
                    f'a la fecha de fin {dto.fecha_fin.isoformat()}. Corrija el rango de fechas.'
                ),
                field='fecha_inicio',
            )

        # E-01: el activo debe existir
        activo = self.activo_repo.obtener_por_id(id_activo, ids_fincas_permitidas=ids_fincas_permitidas)
        if activo is None:
            raise NotFoundError(
                code='ACTIVO_NO_ENCONTRADO',
                message=f'El activo biológico con id {id_activo} no fue encontrado en el sistema.',
            )

        resultado = self.transferencia_repo.consultar_historial(
            id_activo=id_activo,
            fecha_inicio=dto.fecha_inicio,
            fecha_fin=dto.fecha_fin,
            categoria=dto.categoria_evento,
            pagina=dto.pagina,
            page_size=dto.page_size,
        )

        filtros_aplicados = any((dto.fecha_inicio, dto.fecha_fin, dto.categoria_evento))
        if filtros_aplicados and resultado.total_registros == 0:
            resultado.mensaje = (
                f'No se encontraron eventos para el activo {id_activo} con los filtros aplicados. '
                'Puede ampliar el rango de fechas o cambiar la categoría de evento.'
            )

        registrar_evento_bitacora(self.bitacora_repo, self.db, EventoAuditoria(
            rf_origen='RF46', tipo_evento='HISTORIAL_CONSULTADO',
            clasificacion_biologica='ACCESO_DATOS', resultado='EXITOSO',
            severidad_log='INFO', timestamp_evento=datetime.now(timezone.utc),
            id_activo_biologico=id_activo,
            id_usuario_responsable=usuario.id_usuario,
        ))

        return resultado
