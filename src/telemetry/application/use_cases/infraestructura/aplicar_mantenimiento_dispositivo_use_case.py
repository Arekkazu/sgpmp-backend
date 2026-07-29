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

from src.shared.errors import BusinessRuleError, NotFoundError
from src.telemetry.domain.entities.estado_dispositivo_iot import EstadoDispositivoIoT
from src.telemetry.domain.entities.evento_auditoria_iot import (
    ComponenteOrigen,
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
    ) -> EstadoDispositivoIoT:
        estado = self.estado_repo.obtener_por_dispositivo(id_dispositivo_iot)
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
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        self._emitir_auditoria(
            id_dispositivo_iot=id_dispositivo_iot,
            estado_anterior=estado_anterior,
            estado_nuevo=dto.nuevo_estado,
            motivo=dto.motivo,
            id_usuario=id_usuario,
            nombre_usuario=nombre_usuario,
        )

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
        try:
            from src.telemetry.application.use_cases.auditoria.registrar_evento_auditoria_iot_use_case import RegistrarEventoAuditoriaIotUseCase
            svc = RegistrarEventoAuditoriaIotUseCase(db=self.db, auditoria_repo=self.auditoria_repo)
            svc.execute(
                tipo_evento='TRANSICION_MANTENIMIENTO_MANUAL',
                resultado=TipoResultado.EXITOSO,
                componente_origen=ComponenteOrigen.RF60,
                severidad_log=SeveridadLog.INFO,
                descripcion=(
                    f'Transición manual de dispositivo {id_dispositivo_iot} a {estado_nuevo} '
                    f'por {nombre_usuario}.'
                ),
                entidad_afectada_tipo=EntidadAfectadaTipo.DISPOSITIVO,
                entidad_afectada_id=str(id_dispositivo_iot),
                accion_detallada={
                    'id_dispositivo_iot': id_dispositivo_iot,
                    'estado_anterior': estado_anterior,
                    'estado_nuevo': estado_nuevo,
                    'motivo': motivo,
                },
                id_usuario=id_usuario,
                nombre_usuario=nombre_usuario,
            )
        except Exception:
            pass
