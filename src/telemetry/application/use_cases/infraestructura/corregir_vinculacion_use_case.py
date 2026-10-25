# | Fecha      | Nombre  | Que se hizo |
# |------------|---------|-------------|
# | 2026-10-22 | Leandro | DEV-44 RF-61: correccion SUPERADA conserva periodo y contexto |
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from src.shared.errors import BusinessRuleError, NotFoundError, ServiceUnavailableError
from src.telemetry.application.use_cases.infraestructura.evidencia_vinculacion import registrar_evidencia
from src.telemetry.domain.entities.vinculacion_lectura import VinculacionLectura
from src.telemetry.domain.repositories.vinculacion_lectura_repository import VinculacionLecturaRepository
from src.telemetry.infrastructure.dto.corregir_vinculacion_dto import CorregirVinculacionDTO

logger = logging.getLogger(__name__)


class CorregirVinculacionUseCase:
    """RF-61-C: Corrección post-vinculación (inmutabilidad).
    Cierra la anterior como SUPERADA y crea una nueva sin sobrescribir su contexto.
    """

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
        self, id_vinculacion_lectura: int, dto: CorregirVinculacionDTO, id_usuario: int, *, ids_fincas_permitidas=None
    ) -> VinculacionLectura:
        ahora = datetime.now(timezone.utc)
        try:
            original = self.vinculacion_repo.obtener_por_id(id_vinculacion_lectura,ids_fincas_permitidas=ids_fincas_permitidas)
            if original is None:
                raise NotFoundError(
                    code='VINCULACION_NO_ENCONTRADA',
                    message='Vinculación no encontrada.',
                )
            self.vinculacion_repo.bloquear_lectura(original.id_telemetria)
            original=self.vinculacion_repo.obtener_por_id(id_vinculacion_lectura,ids_fincas_permitidas=ids_fincas_permitidas)
            if original.estado_vinculacion == 'SUPERADA' or original.fecha_fin_vinculacion is not None:
                raise BusinessRuleError(
                    code='VINCULACION_YA_CORREGIDA',
                    message='La vinculación ya fue corregida previamente.',
                )

            contexto=None
            captura=original.fecha_inicio_vinculacion
            if original.contexto_activo and original.contexto_activo.get('timestamp_captura'):
                captura=datetime.fromisoformat(original.contexto_activo['timestamp_captura'])
            if self.activo_port is None:
                raise ServiceUnavailableError('CONTEXTO_ACTIVO_NO_DISPONIBLE', 'No se puede verificar la elegibilidad historica del activo.')
            self.activo_port.bloquear_activos([dto.id_activo_biologico])
            candidatos=self.activo_port.obtener_activos_en_momento(original.id_infraestructura,captura)
            if not any(a.id_activo_biologico==dto.id_activo_biologico and a.modelo_manejo==dto.modelo_manejo for a in candidatos):
                raise BusinessRuleError('ACTIVO_NO_ELEGIBLE','El activo no era elegible en la estructura y fecha de la lectura.')
            contexto=self.activo_port.obtener_contexto(dto.id_activo_biologico,captura)
            original.estado_vinculacion = 'SUPERADA'
            original.fecha_fin_vinculacion=ahora
            self.vinculacion_repo.actualizar(original)

            # Crear nueva vinculación como corrección
            nueva = self.vinculacion_repo.guardar(VinculacionLectura(
                id_vinculacion_lectura=None,
                id_telemetria=original.id_telemetria,
                modelo_manejo=dto.modelo_manejo,
                id_activo_biologico=dto.id_activo_biologico,
                id_infraestructura=original.id_infraestructura,
                fecha_inicio_vinculacion=ahora,
                fecha_fin_vinculacion=None,
                mecanismo_vinculacion='CORRECCION',
                estado_vinculacion='CONFIRMADA',
                id_usuario=id_usuario,
                motivo_correccion=dto.motivo,
                id_vinculacion_reemplazada=original.id_vinculacion_lectura,
                fecha_creacion=ahora,
                contexto_activo=contexto,
            ))

            if self.auditoria_repo is not None:
                registrar_evidencia(self.auditoria_repo,'CORRECCION_VINCULACION',nueva.id_vinculacion_lectura,
                    {'id_telemetria':nueva.id_telemetria,'id_reemplazada':original.id_vinculacion_lectura,
                     'id_activo_biologico':nueva.id_activo_biologico,'motivo':dto.motivo},id_usuario)

            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        # INC-M09-106-G31: reclasificar el semáforo contra RF-17 (best-effort, fuera de la transacción)
        if self.reclasificar_semaforo_use_case is not None and nueva.id_activo_biologico:
            try:
                self.reclasificar_semaforo_use_case.execute(
                    id_telemetria=nueva.id_telemetria,
                    id_activo_biologico=nueva.id_activo_biologico,
                )
            except Exception:
                logger.warning(
                    'INC-M09-106-G31: fallo al reclasificar semáforo para vinculación %s.',
                    id_vinculacion_lectura,
                    exc_info=True,
                )

        return nueva
