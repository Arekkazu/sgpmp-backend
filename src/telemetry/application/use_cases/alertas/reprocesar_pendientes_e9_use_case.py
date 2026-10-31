# | Fecha      | Nombre | Que se hizo |
# |------------|--------|-------------|
# | 2026-10-31 | Claude | INC-M03-173-G85 RF-57 E9: eventos PENDIENTE_EVALUACION se reevalúan al configurar la regla |
"""RF-57 E9 — recuperación tras corregir la configuración (#878, BUG-G85-01 parte 2).

Un evento de una variable sin umbral RF-17 queda PENDIENTE_EVALUACION dentro de una alerta
técnica ERROR_CONFIGURACION_REGLA, sin alerta operativa. Antes, aunque luego se creara el
umbral, ese evento no se evaluaba nunca: había que reenviarlo a mano.

Este caso de uso lo corre el worker periódico: si la variable ya tiene umbral en el área,
reevalúa el evento guardado con la misma regla de ``POST /iot/alertas`` (puede generar la
alerta, deduplicarse o quedar en banda NORMAL), marca el evento como EVALUADO y deja
evidencia en la bitácora. La técnica sigue abierta: documenta que hubo un error de
configuración y la cierra el Administrador.
"""
from __future__ import annotations

import logging
from typing import Callable

from sqlalchemy.orm import Session

from src.telemetry.application.use_cases.auditoria.registrar_evento_auditoria_iot_use_case import (
    RegistrarEventoAuditoriaIotUseCase,
)
from src.telemetry.domain.entities.evento_auditoria_iot import (
    ComponenteOrigen, EntidadAfectadaTipo, SeveridadLog, TipoResultado,
)
from src.telemetry.domain.repositories.alerta_repository import AlertaRepository
from src.telemetry.domain.repositories.bitacora_auditoria_iot_repository import BitacoraAuditoriaIotRepository
from src.telemetry.domain.repositories.umbral_configurado_port import UmbralConfiguradoPort
from src.telemetry.infrastructure.dto.procesar_evento_alerta_dto import ProcesarEventoAlertaDTO

logger = logging.getLogger(__name__)


class ReprocesarPendientesE9UseCase:
    def __init__(
        self,
        db: Session,
        alerta_repo: AlertaRepository,
        umbral_port: UmbralConfiguradoPort,
        generar_alerta: Callable[[], object],
        auditoria_repo: BitacoraAuditoriaIotRepository | None = None,
    ) -> None:
        self.db = db
        self.alerta_repo = alerta_repo
        self.umbral_port = umbral_port
        # Fábrica: cada evento usa una instancia nueva de GenararAlertaUseCase.
        self.generar_alerta = generar_alerta
        self.auditoria_repo = auditoria_repo

    def execute(self, limite: int = 20) -> dict:
        resumen = {'reevaluados': 0, 'sin_regla': 0, 'fallidos': 0}
        for tecnica in self.alerta_repo.listar_pendientes_e9(limite):
            evento = dict((tecnica.metadato_evento or {}).get('evento_pendiente') or {})
            campos = {k: v for k, v in evento.items() if k in ProcesarEventoAlertaDTO.model_fields}
            try:
                dto = ProcesarEventoAlertaDTO.model_validate(campos)
            except Exception:
                resumen['fallidos'] += 1
                logger.warning('E9: evento pendiente ilegible en la alerta técnica %s', tecnica.id_alerta)
                continue
            if not self.umbral_port.consultar(dto.tipo_variable, tecnica.id_infraestructura).configurado:
                resumen['sin_regla'] += 1
                continue
            try:
                resultado = self.generar_alerta().execute(
                    dto,
                    id_dispositivo_ioit=tecnica.id_dispositivo_ioit,
                    id_infraestructura=tecnica.id_infraestructura,
                )
                detalle = {
                    'id_alerta_generada': getattr(resultado, 'id_alerta', None),
                    'es_duplicado': getattr(resultado, 'es_duplicado', False),
                    'motivo_descarte': getattr(resultado, 'motivo_descarte', None),
                }
                self.alerta_repo.marcar_pendiente_e9_evaluado(tecnica.id_alerta, detalle)
                self._auditar(tecnica.id_alerta, dto, detalle)
                self.db.commit()
                resumen['reevaluados'] += 1
            except Exception as exc:
                self.db.rollback()
                resumen['fallidos'] += 1
                logger.warning('E9: no se pudo reevaluar el evento de la alerta técnica %s (%s)',
                               tecnica.id_alerta, getattr(exc, 'code', type(exc).__name__))
        return resumen

    def _auditar(self, id_alerta: int, dto: ProcesarEventoAlertaDTO, detalle: dict) -> None:
        if self.auditoria_repo is None:
            return
        RegistrarEventoAuditoriaIotUseCase(self.db, self.auditoria_repo).execute(
            tipo_evento='EVENTO_PENDIENTE_REEVALUADO',
            resultado=TipoResultado.EXITOSO,
            componente_origen=ComponenteOrigen.RF57,
            severidad_log=SeveridadLog.INFO,
            descripcion=f'Regla configurada para {dto.tipo_variable}: el evento PENDIENTE_EVALUACION se reevaluó.',
            entidad_afectada_tipo=EntidadAfectadaTipo.DISPOSITIVO,
            entidad_afectada_id=str(dto.device_id),
            accion_detallada={'id_alerta_tecnica': id_alerta, 'id_sensor': dto.sensor_id,
                              'tipo_variable': dto.tipo_variable, **detalle},
        )
