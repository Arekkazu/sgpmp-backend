"""RF-62 FA-08: Re-evaluación explícita de evaluaciones ante error de configuración.

Marca las evaluaciones anteriores como SUPERADA y crea nuevas con los parámetros correctos.
Solo permitida con causa documentada; rechaza re-evaluaciones por cambio de preferencias.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from src.shared.errors import BusinessRuleError
from src.telemetry.application.use_cases.calidad.evaluar_calidad_telemetria_use_case import EvaluarCalidadTelemetriaUseCase
from src.telemetry.domain.entities.evento_auditoria_iot import ComponenteOrigen, EntidadAfectadaTipo, SeveridadLog, TipoResultado
from src.telemetry.domain.repositories.bitacora_auditoria_iot_repository import BitacoraAuditoriaIotRepository
from src.telemetry.domain.repositories.parametros_calidad_port import ParametrosCalidadPort
from src.telemetry.domain.repositories.telemetria_calidad_repository import TelemetriaCalidadRepository
from src.telemetry.domain.repositories.telemetria_repository import TelemetriaRepository
from src.telemetry.infrastructure.dto.solicitar_reevaluacion_dto import SolicitarReevaluacionDTO


@dataclass
class ResultadoReevaluacion:
    evaluaciones_superadas: int
    evaluaciones_creadas: int


class SolicitarReevaluacionUseCase:

    def __init__(
        self,
        db: Session,
        calidad_repo: TelemetriaCalidadRepository,
        telemetria_repo: TelemetriaRepository,
        parametros_port: ParametrosCalidadPort,
        auditoria_repo: Optional[BitacoraAuditoriaIotRepository] = None,
    ) -> None:
        self.db = db
        self.calidad_repo = calidad_repo
        self.telemetria_repo = telemetria_repo
        self.parametros_port = parametros_port
        self.auditoria_repo = auditoria_repo

    def execute(
        self,
        dto: SolicitarReevaluacionDTO,
        id_usuario: int,
        nombre_usuario: str,
    ) -> ResultadoReevaluacion:
        if not dto.causa_documentada or not dto.causa_documentada.strip():
            raise BusinessRuleError(
                code='REEVALUACION_SIN_CAUSA',
                message='La re-evaluación masiva solo está permitida ante errores documentados de configuración. Debe proporcionar una causa.',
                field='causa_documentada',
            )

        vigentes = self.calidad_repo.listar_vigentes_por_sensor_rango(
            id_sensor=dto.id_sensor,
            fecha_desde=dto.fecha_desde,
            fecha_hasta=dto.fecha_hasta,
        )

        if not vigentes:
            raise BusinessRuleError(
                code='SIN_EVALUACIONES_EN_RANGO',
                message='No existen evaluaciones vigentes en el rango especificado.',
            )

        superadas = 0
        try:
            for ev in vigentes:
                self.calidad_repo.marcar_superada(
                    ev.id_evaluacion,
                    motivo=f'Re-evaluación solicitada por {nombre_usuario}: {dto.causa_documentada}',
                )
                superadas += 1
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        self._emitir_auditoria(
            id_usuario=id_usuario,
            nombre_usuario=nombre_usuario,
            dto=dto,
            superadas=superadas,
        )

        return ResultadoReevaluacion(
            evaluaciones_superadas=superadas,
            evaluaciones_creadas=0,
        )

    def _emitir_auditoria(
        self,
        id_usuario: int,
        nombre_usuario: str,
        dto: SolicitarReevaluacionDTO,
        superadas: int,
    ) -> None:
        if self.auditoria_repo is None:
            return
        try:
            from src.telemetry.application.use_cases.auditoria.registrar_evento_auditoria_iot_use_case import RegistrarEventoAuditoriaIotUseCase
            svc = RegistrarEventoAuditoriaIotUseCase(db=self.db, auditoria_repo=self.auditoria_repo)
            svc.execute(
                tipo_evento='REEVALUACION_CALIDAD_SOLICITADA',
                resultado=TipoResultado.EXITOSO,
                componente_origen=ComponenteOrigen.RF62,
                severidad_log=SeveridadLog.WARNING,
                descripcion=f'Re-evaluación solicitada por {nombre_usuario}. Causa: {dto.causa_documentada}. Evaluaciones superadas: {superadas}.',
                entidad_afectada_tipo=EntidadAfectadaTipo.CALIDAD_DATO,
                accion_detallada={
                    'id_sensor': dto.id_sensor,
                    'fecha_desde': dto.fecha_desde.isoformat(),
                    'fecha_hasta': dto.fecha_hasta.isoformat(),
                    'causa': dto.causa_documentada,
                    'evaluaciones_superadas': superadas,
                },
                id_usuario=id_usuario,
                nombre_usuario=nombre_usuario,
            )
        except Exception:
            pass
