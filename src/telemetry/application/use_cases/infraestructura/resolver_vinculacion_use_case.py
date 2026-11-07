# | Fecha      | Nombre  | Que se hizo |
# |------------|---------|-------------|
# | 2026-10-22 | Leandro | DEV-44 RF-61: resuelve pendientes con contexto y alcance |
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session

from src.shared.errors import NotFoundError, BusinessRuleError, ServiceUnavailableError
from src.telemetry.application.use_cases.infraestructura.evidencia_vinculacion import registrar_evidencia
from src.telemetry.domain.entities.vinculacion_lectura import VinculacionLectura
from src.telemetry.domain.repositories.vinculacion_lectura_repository import VinculacionLecturaRepository
from src.telemetry.infrastructure.dto.resolver_vinculacion_dto import ResolverVinculacionDTO

logger = logging.getLogger(__name__)


class ResolverVinculacionUseCase:
    """RF-61-C: Resolución manual de una vinculación AMBIGUA o SIN_VINCULAR."""

    def __init__(
        self,
        db: Session,
        vinculacion_repo: VinculacionLecturaRepository,
        reclasificar_semaforo_use_case: Optional[object] = None,
        activo_port=None,
        auditoria_repo=None,
    ) -> None:
        self.db = db
        self.vinculacion_repo = vinculacion_repo
        self.reclasificar_semaforo_use_case = reclasificar_semaforo_use_case
        self.activo_port=activo_port
        self.auditoria_repo=auditoria_repo

    def execute(
        self, id_vinculacion_lectura: int, dto: ResolverVinculacionDTO, id_usuario: int, *, ids_fincas_permitidas=None
    ) -> VinculacionLectura:
        try:
            vinculacion = self.vinculacion_repo.obtener_por_id(id_vinculacion_lectura,ids_fincas_permitidas=ids_fincas_permitidas)
            if vinculacion is None:
                raise NotFoundError(
                    code='VINCULACION_NO_ENCONTRADA',
                    message='Vinculación no encontrada.',
                )
            self.vinculacion_repo.bloquear_lectura(vinculacion.id_telemetria)
            vinculacion=self.vinculacion_repo.obtener_por_id(id_vinculacion_lectura,ids_fincas_permitidas=ids_fincas_permitidas)
            if self.activo_port is None:
                raise ServiceUnavailableError('CONTEXTO_ACTIVO_NO_DISPONIBLE', 'No se puede verificar la elegibilidad historica del activo.')
            self.activo_port.bloquear_activos([dto.id_activo_biologico])
            candidatos=self.activo_port.obtener_activos_en_momento(vinculacion.id_infraestructura,vinculacion.fecha_inicio_vinculacion)
            if not any(a.id_activo_biologico==dto.id_activo_biologico and a.modelo_manejo==dto.modelo_manejo for a in candidatos):
                raise BusinessRuleError('ACTIVO_NO_ELEGIBLE','El activo no era elegible en la estructura y fecha de la lectura.')
            vinculacion.contexto_activo=self.activo_port.obtener_contexto(dto.id_activo_biologico,vinculacion.fecha_inicio_vinculacion)
            vinculacion.resolver(
                id_activo_biologico=dto.id_activo_biologico,
                id_usuario=id_usuario,
            )
            vinculacion.modelo_manejo = dto.modelo_manejo
            resultado = self.vinculacion_repo.actualizar(vinculacion)
            if self.auditoria_repo is not None:
                registrar_evidencia(self.auditoria_repo,'VINCULACION_MANUAL',resultado.id_vinculacion_lectura,
                    {'id_telemetria':resultado.id_telemetria,'id_activo_biologico':resultado.id_activo_biologico,
                     'contexto_activo':resultado.contexto_activo},id_usuario)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        # INC-M09-106-G31: reclasificar el semáforo contra RF-17 (best-effort, fuera de la transacción)
        if self.reclasificar_semaforo_use_case is not None and resultado.id_activo_biologico:
            try:
                self.reclasificar_semaforo_use_case.execute(
                    id_telemetria=resultado.id_telemetria,
                    id_activo_biologico=resultado.id_activo_biologico,
                )
            except Exception:
                logger.warning(
                    'INC-M09-106-G31: fallo al reclasificar semáforo para vinculación %s.',
                    id_vinculacion_lectura,
                    exc_info=True,
                )

        return resultado
