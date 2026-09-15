from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

from src.biological_assets.application.use_cases._registrar_evento_bitacora import registrar_evento_bitacora
from src.biological_assets.application.use_cases.gestion._auditoria_rechazos import (
    ejecutar_con_auditoria_de_rechazo,
)
from src.biological_assets.domain.entities.activo_biologico import AsociacionSensorActivo, EventoAuditoria
from src.biological_assets.domain.repositories.asociacion_sensor_activo_repository import (
    AsociacionSensorActivoRepository,
)
from src.biological_assets.domain.repositories.bitacora_auditoria_repository import BitacoraAuditoriaRepository
from src.biological_assets.domain.repositories.infraestructura_consulta_port import InfraestructuraConsultaPort
from src.biological_assets.domain.repositories.sensor_consulta_port import SensorConsultaPort
from src.shared.errors import AppError, BusinessRuleError, ConflictError, NotFoundError

if TYPE_CHECKING:
    from src.identity_access.infrastructure.dependencies import UsuarioActual
    from src.biological_assets.infrastructure.dto.asociar_sensor_infraestructura_dto import (
        AsociarSensorInfraestructuraDTO,
    )


class AsociarSensorInfraestructuraUseCase:
    """RF-49 Tipo B (INC-M02-66-G90/#217): "Asociación Ambiental Compartida" --
    un sensor ambiental se asocia a una infraestructura productiva completa
    (no a un activo puntual) y aplica automáticamente a todos los activos que
    residan en ella (cardinalidad 1 sensor -> N activos, mediada por la
    infraestructura). Antes de este fix el único endpoint disponible
    (`POST /{id_activo}/sensores`) exigía un activo en el path y siempre
    persistía `id_activo_biologico` con ese valor -- monitorear N activos de
    una infraestructura requería N asociaciones idénticas en vez de una sola.

    Persiste una única fila con `id_activo_biologico = NULL` (la columna ya
    lo permitía en el esquema); `ConsultarAsociacionesSensorUseCase` la
    resuelve por herencia al consultar cualquier activo de esa infraestructura.
    """

    def __init__(
        self,
        db: Session,
        repo: AsociacionSensorActivoRepository,
        sensor_port: SensorConsultaPort,
        infra_port: InfraestructuraConsultaPort,
        bitacora_repo: BitacoraAuditoriaRepository | None = None,
    ) -> None:
        self.db = db
        self.repo = repo
        self.sensor_port = sensor_port
        self.infra_port = infra_port
        self.bitacora_repo = bitacora_repo

    def execute(
        self,
        id_infraestructura: int,
        dto: AsociarSensorInfraestructuraDTO,
        usuario_actual: UsuarioActual,
    ) -> AsociacionSensorActivo:
        return ejecutar_con_auditoria_de_rechazo(
            lambda: self._execute(id_infraestructura, dto, usuario_actual),
            db=self.db,
            bitacora_repo=self.bitacora_repo,
            obtener_activo=None,
            id_activo=None,
            id_usuario=usuario_actual.id_usuario,
            rf_origen='RF49',
            tipo_evento_rechazado='ASOCIACION_AMBIENTAL_RECHAZADA',
            clasificacion_biologica='GESTION_OPERATIVA',
        )

    def _execute(
        self,
        id_infraestructura: int,
        dto: AsociarSensorInfraestructuraDTO,
        usuario_actual: UsuarioActual,
    ) -> AsociacionSensorActivo:
        # V1 — Infraestructura existe y está activa
        infra = self.infra_port.obtener_activa(id_infraestructura)
        if infra is None:
            raise BusinessRuleError(
                code='INFRAESTRUCTURA_NO_ENCONTRADA',
                message=f'No existe una infraestructura activa con id {id_infraestructura}.',
            )

        # V3 — Sensor existe
        sensor = self.sensor_port.obtener_sensor_con_contexto(dto.sensor_id)
        if sensor is None:
            raise NotFoundError(
                code='SENSOR_NO_ENCONTRADO',
                message=f'No existe un sensor con id {dto.sensor_id}.',
            )

        # V4 — Sensor activo
        if not sensor.es_activo:
            raise BusinessRuleError(
                code='SENSOR_INACTIVO',
                message=f'El sensor {dto.sensor_id} no está activo. Solo se permiten asociaciones con sensores activos.',
            )

        # V4b — Dispositivo IoT activo
        if not sensor.dispositivo_es_activo:
            raise BusinessRuleError(
                code='DISPOSITIVO_INACTIVO',
                message=f'El dispositivo IoT {sensor.id_dispositivo_iot} no está activo.',
            )

        # V5 — Sensor tiene área asociada activa
        if sensor.id_infraestructura_area is None:
            raise BusinessRuleError(
                code='SENSOR_SIN_AREA',
                message=(
                    f'El sensor {dto.sensor_id} no tiene asociación activa a ninguna infraestructura. '
                    'Asocie el sensor a una infraestructura (RF-22) antes de vincularlo.'
                ),
            )

        # V6 — Coherencia territorial: misma finca (mismo criterio que
        # AsociarSensorActivoUseCase usa entre sensor y activo; aquí se
        # compara directo contra la infraestructura objetivo).
        infra_sensor = self.infra_port.obtener_activa(sensor.id_infraestructura_area)
        if infra_sensor is None:
            raise BusinessRuleError(
                code='INFRAESTRUCTURA_NO_DISPONIBLE',
                message='No fue posible verificar la infraestructura del sensor.',
            )

        if infra_sensor.id_finca != infra.id_finca:
            raise ConflictError(
                code='INFRAESTRUCTURA_INCOMPATIBLE',
                message=(
                    f'Error de ubicación. La infraestructura destino está en la finca {infra.id_finca} '
                    f'y el sensor en la finca {infra_sensor.id_finca}. '
                    'La asociación solo es permitida dentro de la misma unidad territorial.'
                ),
            )

        # V7 — Evitar una asociación AMBIENTAL duplicada para el mismo par
        # sensor+infraestructura (el índice único de BD no lo cubre: compara
        # id_activo_biologico, y NULL nunca es igual a NULL).
        existente = self.repo.obtener_activa_por_sensor_e_infraestructura(dto.sensor_id, id_infraestructura)
        if existente is not None:
            raise ConflictError(
                code='ASOCIACION_AMBIENTAL_YA_EXISTE',
                message=(
                    f'El sensor {dto.sensor_id} ya tiene una asociación AMBIENTAL activa '
                    f'con la infraestructura {id_infraestructura}.'
                ),
            )

        fecha_inicio = dto.fecha_inicio or datetime.datetime.now(datetime.timezone.utc)

        try:
            nueva = AsociacionSensorActivo(
                id_activo_biologico=None,
                tipo_activo=None,
                tipo_asociacion='ambiental',
                dispositivo_iot_id=dto.dispositivo_iot_id,
                sensor_id=dto.sensor_id,
                id_infraestructura=id_infraestructura,
                id_usuario=usuario_actual.id_usuario,
                fecha_inicio=fecha_inicio,
                fecha_fin=dto.fecha_fin,
                motivo=dto.motivo,
                estado_asociacion='ACTIVA',
            )
            nueva = self.repo.guardar(nueva)

            self.repo.registrar_auditoria(
                id_asociacion=nueva.id_asociacion_activo_sensor,
                id_usuario=usuario_actual.id_usuario,
                tipo_op='CREATE',
                valores_anteriores=None,
                valores_nuevos={
                    'id_infraestructura': nueva.id_infraestructura,
                    'sensor_id': nueva.sensor_id,
                    'tipo_asociacion': nueva.tipo_asociacion,
                    'dispositivo_iot_id': nueva.dispositivo_iot_id,
                    'fecha_inicio': nueva.fecha_inicio.isoformat(),
                    'estado_asociacion': nueva.estado_asociacion,
                },
            )

            self.db.commit()

        except AppError:
            self.db.rollback()
            raise
        except Exception as exc:
            self.db.rollback()
            registrar_evento_bitacora(self.bitacora_repo, self.db, EventoAuditoria(
                rf_origen='RF49', tipo_evento='ASOCIACION_AMBIENTAL_FALLIDA',
                clasificacion_biologica='GESTION_OPERATIVA', resultado='FALLIDO',
                severidad_log='ERROR', timestamp_evento=datetime.datetime.now(datetime.timezone.utc),
                id_activo_biologico=None, tipo_activo=None,
                detalle_tecnico={'error': str(exc), 'sensor_id': dto.sensor_id, 'id_infraestructura': id_infraestructura},
                id_usuario_responsable=usuario_actual.id_usuario,
            ))
            raise

        registrar_evento_bitacora(self.bitacora_repo, self.db, EventoAuditoria(
            rf_origen='RF49', tipo_evento='ASOCIACION_AMBIENTAL_CREADA',
            clasificacion_biologica='GESTION_OPERATIVA', resultado='EXITOSO',
            severidad_log='INFO', timestamp_evento=datetime.datetime.now(datetime.timezone.utc),
            id_activo_biologico=None, tipo_activo=None,
            descripcion=f'Sensor {dto.sensor_id} asociado a la infraestructura {id_infraestructura} (AMBIENTAL)',
            detalle_tecnico={'sensor_id': dto.sensor_id, 'id_infraestructura': id_infraestructura},
            id_usuario_responsable=usuario_actual.id_usuario,
        ))

        return nueva
