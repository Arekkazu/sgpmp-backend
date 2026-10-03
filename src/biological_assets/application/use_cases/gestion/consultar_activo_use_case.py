from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from src.biological_assets.application.use_cases._registrar_evento_bitacora import registrar_evento_bitacora
from src.biological_assets.domain.entities.activo_biologico import ActivoBiologico, EventoAuditoria
from src.biological_assets.domain.repositories.activo_biologico_repository import ActivoBiologicoRepository
from src.biological_assets.domain.repositories.bitacora_auditoria_repository import BitacoraAuditoriaRepository
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import NotFoundError


class ConsultarActivoUseCase:
    def __init__(
        self,
        db: Session,
        repo: ActivoBiologicoRepository,
        bitacora_repo: BitacoraAuditoriaRepository | None = None,
    ) -> None:
        self.db = db
        self.repo = repo
        self.bitacora_repo = bitacora_repo

    def execute(
        self,
        id_activo: int,
        usuario: Optional[UsuarioActual] = None,
        *,
        ids_fincas_permitidas: Optional[list[int]] = None,
    ) -> ActivoBiologico:
        activo = self.repo.obtener_por_id(id_activo, ids_fincas_permitidas=ids_fincas_permitidas)
        if activo is None:
            raise NotFoundError(
                code='ACTIVO_NO_ENCONTRADO',
                message=f'El activo biológico con ID {id_activo} no existe.',
            )

        # INC-M02-34-G29/G31 v2: la bitácora auditaba TODA consulta de activo
        # como RF35/ACTIVO_INDIVIDUAL_CONSULTA, sin importar tipo_activo -- un
        # lote POBLACIONAL quedaba registrado con el rf_origen y tipo_evento
        # de RF-35 (gestión individual), que no le corresponde.
        if activo.tipo == 'POBLACIONAL':
            rf_origen, tipo_evento = 'RF36', 'ACTIVO_POBLACIONAL_CONSULTA'
        else:
            rf_origen, tipo_evento = 'RF35', 'ACTIVO_INDIVIDUAL_CONSULTA'

        registrar_evento_bitacora(self.bitacora_repo, self.db, EventoAuditoria(
            rf_origen=rf_origen, tipo_evento=tipo_evento,
            clasificacion_biologica='ACCESO_DATOS', resultado='EXITOSO',
            severidad_log='INFO', timestamp_evento=datetime.now(timezone.utc),
            id_activo_biologico=id_activo, tipo_activo=activo.tipo,
            id_usuario_responsable=usuario.id_usuario if usuario else None,
        ))

        return activo
