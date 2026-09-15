from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from src.biological_assets.application.use_cases._registrar_evento_bitacora import registrar_evento_bitacora
from src.biological_assets.domain.entities.activo_biologico import AsociacionSensorActivo, EventoAuditoria
from src.biological_assets.domain.repositories.activo_biologico_repository import ActivoBiologicoRepository
from src.biological_assets.domain.repositories.asociacion_sensor_activo_repository import (
    AsociacionSensorActivoRepository,
)
from src.biological_assets.domain.repositories.bitacora_auditoria_repository import BitacoraAuditoriaRepository
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import NotFoundError, ValidationError


class ConsultarAsociacionesSensorUseCase:
    """RF-49 (INC-M02-68-G91 / issue #218): expone en lectura las filas de
    `modulo2.asociaciones_activos_sensores` de un activo. Antes de este fix no
    existía ningún endpoint para esto — la asociación se persistía
    correctamente pero era invisible para el frontend, M03, M04 y reportes,
    incumpliendo el criterio de aceptación "el sistema refleja la asociación
    en consultas posteriores" del RF-49.
    """

    def __init__(
        self,
        db: Session,
        repo: AsociacionSensorActivoRepository,
        activo_repo: ActivoBiologicoRepository,
        bitacora_repo: BitacoraAuditoriaRepository | None = None,
    ) -> None:
        self.db = db
        self.repo = repo
        self.activo_repo = activo_repo
        self.bitacora_repo = bitacora_repo

    def execute(
        self,
        id_activo: int,
        tipo_consulta: str,
        usuario: Optional[UsuarioActual] = None,
        *,
        ids_fincas_permitidas: Optional[list[int]] = None,
    ) -> tuple[str, int, list[AsociacionSensorActivo]]:
        if tipo_consulta not in ('ACTIVA', 'HISTORIAL'):
            raise ValidationError(
                code='TIPO_CONSULTA_INVALIDO',
                message="tipo_consulta debe ser 'ACTIVA' o 'HISTORIAL'.",
                field='tipo_consulta',
            )

        activo = self.activo_repo.obtener_por_id(id_activo, ids_fincas_permitidas=ids_fincas_permitidas)
        if activo is None:
            raise NotFoundError(
                code='ACTIVO_NO_ENCONTRADO',
                message=f'No existe un activo biológico con id {id_activo}.',
            )

        if tipo_consulta == 'ACTIVA':
            asociaciones = self.repo.listar_activas_por_activo(id_activo)
        else:
            asociaciones = self.repo.listar_todas_por_activo(id_activo)

        registrar_evento_bitacora(self.bitacora_repo, self.db, EventoAuditoria(
            rf_origen='RF49', tipo_evento='ASOCIACIONES_SENSOR_CONSULTADAS',
            clasificacion_biologica='ACCESO_DATOS', resultado='EXITOSO',
            severidad_log='INFO', timestamp_evento=datetime.now(timezone.utc),
            id_activo_biologico=id_activo, tipo_activo=activo.tipo,
            detalle_tecnico={'tipo_consulta': tipo_consulta, 'total': len(asociaciones)},
            id_usuario_responsable=usuario.id_usuario if usuario else None,
        ))

        return tipo_consulta, id_activo, asociaciones
