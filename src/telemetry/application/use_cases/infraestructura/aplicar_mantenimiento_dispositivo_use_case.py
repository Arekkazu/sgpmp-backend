# | Fecha      | Nombre  | Que se hizo |
# |------------|---------|-------------|
# | 2026-10-22 | Leandro | DEV-42 RF-60: restringe mantenimiento y alcance de finca |
"""RF-60 CA-7/CA-8: Transición manual de mantenimiento de un dispositivo IoT.

Permite a Administrador/Ingeniero poner un dispositivo EN_MANTENIMIENTO o
devolverlo a ACTIVO tras resolver la intervención. El job periódico
(``EvaluarEstadoDispositivosUseCase``) ignora el estado EN_MANTENIMIENTO, por lo
que no pisa esta transición manual.

Registro del histórico: la tabla ``historico_transiciones_dispositivos`` se
alimenta automáticamente por el trigger de BD ``trg_rf60_02_log_transicion_estado``
(``fn_log_transicion_dispositivo``), que inserta la fila de transición en cada
cambio de ``estado_actual`` copiando ``id_usuario`` → ``id_usuairo_responsable``.
Por eso este caso de uso **no** inserta manualmente en el histórico (lo haría
duplicado). El ``motivo`` legible y el nombre del actor se conservan en la
bitácora de auditoría RF-63.

Nota de dominio: ``causa_primaria`` es del enum PG ``enum_causa_inactividad``,
que no contempla un valor de "mantenimiento"; por eso la transición manual la
deja en ``NULL``. Lo "manual" se distingue por ``id_usuario_responsable`` no nulo
en el histórico y por el evento de auditoría RF-63.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from src.shared.errors import BusinessRuleError, NotFoundError, ServiceUnavailableError
from src.telemetry.domain.entities.estado_dispositivo_iot import EstadoDispositivoIoT
from src.telemetry.domain.entities.evento_auditoria_iot import (
    ComponenteOrigen,
    EventoAuditoriaIot,
    clasificar_componente,
    EntidadAfectadaTipo,
    SeveridadLog,
    TipoResultado,
)
from src.telemetry.domain.repositories.bitacora_auditoria_iot_repository import BitacoraAuditoriaIotRepository
from src.telemetry.domain.repositories.estado_dispositivo_iot_repository import EstadoDispositivoIoTRepository
from src.telemetry.infrastructure.dto.aplicar_mantenimiento_dto import AplicarMantenimientoDTO


class AplicarMantenimientoDispositivoUseCase:

    def __init__(
        self,
        db: Session,
        estado_repo: EstadoDispositivoIoTRepository,
        auditoria_repo: Optional[BitacoraAuditoriaIotRepository] = None,
    ) -> None:
        self.db = db
        self.estado_repo = estado_repo
        self.auditoria_repo = auditoria_repo

    def execute(
        self,
        id_dispositivo_iot: int,
        dto: AplicarMantenimientoDTO,
        id_usuario: int,
        nombre_usuario: str,
        ids_fincas_permitidas: Optional[list[int]] = None,
    ) -> EstadoDispositivoIoT:
        if ids_fincas_permitidas is not None and not self.estado_repo.pertenece_a_fincas(
            id_dispositivo_iot, ids_fincas_permitidas):
            raise NotFoundError('ESTADO_DISPOSITIVO_NO_ENCONTRADO',
                                'No existe un estado accesible para el dispositivo indicado.')
        estado = self.estado_repo.bloquear_por_dispositivo(id_dispositivo_iot)
        if estado is None:
            raise NotFoundError(
                code='ESTADO_DISPOSITIVO_NO_ENCONTRADO',
                message='No existe un estado registrado para el dispositivo indicado.',
            )

        estado_anterior = estado.estado_actual
        if estado_anterior == dto.nuevo_estado:
            raise BusinessRuleError(
                code='ESTADO_SIN_CAMBIO',
                message=f'El dispositivo ya se encuentra en estado {dto.nuevo_estado}.',
                field='nuevo_estado',
            )

        ahora = datetime.now(timezone.utc)

        try:
            estado.validar_transicion_manual(dto.nuevo_estado)
            # causa=None: enum_causa_inactividad no tiene un valor de mantenimiento (ver docstring).
            # El histórico de transición lo inserta el trigger trg_rf60_02_log_transicion_estado
            # al actualizar el estado (usa estado.id_usuario como id_usuairo_responsable).
            estado.aplicar_transicion(
                nuevo_estado=dto.nuevo_estado,
                causa=None,
                ahora=ahora,
                id_usuario=id_usuario,
            )
            self.estado_repo.actualizar(estado)
            self._emitir_auditoria(id_dispositivo_iot, estado_anterior, dto.nuevo_estado,
                dto.motivo, id_usuario, nombre_usuario)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return estado

    def _emitir_auditoria(
        self,
        id_dispositivo_iot: int,
        estado_anterior: str,
        estado_nuevo: str,
        motivo: Optional[str],
        id_usuario: int,
        nombre_usuario: str,
    ) -> None:
        if self.auditoria_repo is None:
            return
        from src.telemetry.application.use_cases.auditoria.registrar_evento_auditoria_iot_use_case import _calcular_hash
        clasificacion, retencion = clasificar_componente(ComponenteOrigen.RF60)
        evento = EventoAuditoriaIot(
            id_evento=None, tipo_evento='TRANSICION_MANTENIMIENTO_MANUAL',
            fecha_hora=datetime.now(timezone.utc), resultado=TipoResultado.EXITOSO,
            componente_origen=ComponenteOrigen.RF60, severidad_log=SeveridadLog.INFO,
            clasificacion_registro=clasificacion, retencion_aplicable=retencion,
            descripcion=f'Transición manual de dispositivo {id_dispositivo_iot} a {estado_nuevo}.',
            entidad_afectada_tipo=EntidadAfectadaTipo.DISPOSITIVO,
            entidad_afectada_id=str(id_dispositivo_iot), id_usuario=id_usuario,
            nombre_usuario=nombre_usuario,
            accion_detallada={'id_dispositivo_iot': id_dispositivo_iot,
                'estado_anterior': estado_anterior, 'estado_nuevo': estado_nuevo, 'motivo': motivo},
        )
        evento.hash_integridad = _calcular_hash(evento)
        registrado = self.auditoria_repo.registrar(evento)
        if registrado.id_evento is None:
            raise ServiceUnavailableError('AUDITORIA_NO_DISPONIBLE',
                'No fue posible registrar la transición manual.')
