from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

from src.biological_assets.domain.entities.activo_biologico import AsociacionSensorActivo, EventoAuditoria
from src.biological_assets.domain.repositories.activo_biologico_repository import ActivoBiologicoRepository
from src.biological_assets.domain.repositories.asociacion_sensor_activo_repository import (
    AsociacionSensorActivoRepository,
)
from src.biological_assets.domain.repositories.bitacora_auditoria_repository import BitacoraAuditoriaRepository
from src.biological_assets.domain.repositories.infraestructura_consulta_port import InfraestructuraConsultaPort
from src.biological_assets.domain.repositories.sensor_consulta_port import SensorConsultaPort
from src.biological_assets.domain.value_objects.estado_activo import EstadoActivo
from src.shared.errors import BusinessRuleError, ConflictError, NotFoundError

if TYPE_CHECKING:
    from src.identity_access.infrastructure.dependencies import UsuarioActual
    from src.biological_assets.infrastructure.dto.asociar_sensor_activo_dto import AsociarSensorActivoDTO

# Mapa de tipo_asociacion DTO (uppercase) → valor en DB (lowercase)
_TIPO_DB = {
    'DIRECTA': 'directa',
    'AMBIENTAL': 'ambiental',
    'POBLACIONAL': 'poblacional',
}


class AsociarSensorActivoUseCase:

    def __init__(
        self,
        db: Session,
        repo: AsociacionSensorActivoRepository,
        activo_repo: ActivoBiologicoRepository,
        sensor_port: SensorConsultaPort,
        infra_port: InfraestructuraConsultaPort,
        bitacora_repo: BitacoraAuditoriaRepository | None = None,
    ) -> None:
        self.db = db
        self.repo = repo
        self.activo_repo = activo_repo
        self.sensor_port = sensor_port
        self.infra_port = infra_port
        self.bitacora_repo = bitacora_repo

    def execute(
        self,
        id_activo: int,
        dto: AsociarSensorActivoDTO,
        usuario_actual: UsuarioActual,
    ) -> AsociacionSensorActivo:
        # V1 — Activo existe
        activo = self.activo_repo.obtener_por_id(id_activo)
        if activo is None:
            raise NotFoundError(
                code='ACTIVO_NO_ENCONTRADO',
                message=f'No existe un activo biológico con id {id_activo}.',
            )

        # V2 — Activo no está en BAJA
        if activo.id_estado == EstadoActivo.BAJA:
            raise BusinessRuleError(
                code='ACTIVO_EN_BAJA',
                message=(
                    f'El activo {id_activo} se encuentra en estado BAJA '
                    'y no admite nuevas asociaciones de sensores.'
                ),
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
                    'Asocie el sensor a una infraestructura (RF-22) antes de vincularlo a un activo.'
                ),
            )

        # V6 — Coherencia de infraestructura (misma finca)
        infra_sensor = self.infra_port.obtener_activa(sensor.id_infraestructura_area)
        infra_activo = self.infra_port.obtener_activa(activo.id_infraestructura)

        if infra_sensor is None or infra_activo is None:
            raise BusinessRuleError(
                code='INFRAESTRUCTURA_NO_DISPONIBLE',
                message='No fue posible verificar la infraestructura del sensor o del activo.',
            )

        if infra_sensor.id_finca != infra_activo.id_finca:
            raise ConflictError(
                code='INFRAESTRUCTURA_INCOMPATIBLE',
                message=(
                    f'Error de ubicación. El activo está en la finca {infra_activo.id_finca} '
                    f'y el sensor en la finca {infra_sensor.id_finca}. '
                    'La asociación solo es permitida dentro de la misma unidad territorial.'
                ),
            )

        tipo_db = _TIPO_DB[dto.tipo_asociacion]

        # V8 — Cardinalidad DIRECTA: sensor no puede tener otro activo individual activo
        if dto.tipo_asociacion == 'DIRECTA':
            activas_sensor = self.repo.listar_activas_por_sensor(dto.sensor_id, 'directa')
            conflicto = next(
                (a for a in activas_sensor if a.id_activo_biologico != id_activo),
                None,
            )
            if conflicto:
                raise ConflictError(
                    code='SENSOR_YA_VINCULADO',
                    message=(
                        f'El sensor {dto.sensor_id} ya está vinculado al activo '
                        f'{conflicto.id_activo_biologico} con una asociación DIRECTA activa. '
                        'Debe desvincularlo primero.'
                    ),
                )

        # V8b — Cardinalidad POBLACIONAL: activo no puede tener otro sensor poblacional activo
        if dto.tipo_asociacion == 'POBLACIONAL':
            activas_activo = self.repo.listar_activas_por_activo(id_activo, 'poblacional')
            conflicto_pob = next(
                (a for a in activas_activo if a.sensor_id != dto.sensor_id),
                None,
            )
            if conflicto_pob:
                raise ConflictError(
                    code='ACTIVO_YA_TIENE_SENSOR_POBLACIONAL',
                    message=(
                        f'El activo {id_activo} ya tiene el sensor {conflicto_pob.sensor_id} '
                        'con asociación POBLACIONAL activa. Desactívelo primero.'
                    ),
                )

        fecha_inicio = dto.fecha_inicio or datetime.datetime.now(datetime.timezone.utc)

        # Si existe asociación ACTIVA previa para el mismo sensor+activo → marcarla SUPERADA
        asociacion_previa = self.repo.obtener_activa_por_sensor_y_activo(dto.sensor_id, id_activo)
        snapshot_anterior: dict | None = None

        try:
            if asociacion_previa is not None:
                snapshot_anterior = {
                    'id_asociacion': asociacion_previa.id_asociacion_activo_sensor,
                    'estado_asociacion': asociacion_previa.estado_asociacion,
                    'fecha_inicio': asociacion_previa.fecha_inicio.isoformat(),
                    'tipo': asociacion_previa.tipo_asociacion,
                }
                asociacion_previa.estado_asociacion = 'SUPERADA'
                asociacion_previa.fecha_fin = fecha_inicio
                asociacion_previa.motivo = 'Reemplazada por nueva asociación'
                asociacion_previa = self.repo.actualizar_estado(asociacion_previa)
                self.repo.registrar_auditoria(
                    id_asociacion=asociacion_previa.id_asociacion_activo_sensor,
                    id_usuario=usuario_actual.id_usuario,
                    tipo_op='UPDATE',
                    valores_anteriores=snapshot_anterior,
                    valores_nuevos={
                        'estado_asociacion': 'SUPERADA',
                        'fecha_fin': fecha_inicio.isoformat(),
                    },
                )

            nueva = AsociacionSensorActivo(
                id_activo_biologico=id_activo,
                tipo_activo=dto.tipo_activo,
                tipo_asociacion=tipo_db,
                dispositivo_iot_id=dto.dispositivo_iot_id,
                sensor_id=dto.sensor_id,
                id_infraestructura=dto.id_infraestructura,
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
                    'id_activo_biologico': nueva.id_activo_biologico,
                    'sensor_id': nueva.sensor_id,
                    'tipo_asociacion': nueva.tipo_asociacion,
                    'tipo_activo': nueva.tipo_activo,
                    'id_infraestructura': nueva.id_infraestructura,
                    'dispositivo_iot_id': nueva.dispositivo_iot_id,
                    'fecha_inicio': nueva.fecha_inicio.isoformat(),
                    'estado_asociacion': nueva.estado_asociacion,
                },
            )

            self.db.commit()

        except Exception as exc:
            self.db.rollback()
            if self.bitacora_repo:
                try:
                    self.bitacora_repo.registrar(EventoAuditoria(
                        rf_origen='RF49', tipo_evento='ASOCIACION_IOT_FALLIDA',
                        clasificacion_biologica='GESTION_OPERATIVA', resultado='FALLIDO',
                        severidad_log='ERROR', timestamp_evento=datetime.datetime.now(datetime.timezone.utc),
                        id_activo_biologico=id_activo, tipo_activo=activo.tipo,
                        detalle_tecnico={'error': str(exc), 'sensor_id': dto.sensor_id},
                        id_usuario_responsable=usuario_actual.id_usuario,
                    ))
                    self.db.commit()
                except Exception:
                    pass
            raise

        if self.bitacora_repo:
            try:
                self.bitacora_repo.registrar(EventoAuditoria(
                    rf_origen='RF49', tipo_evento='ASOCIACION_IOT_CREADA',
                    clasificacion_biologica='GESTION_OPERATIVA', resultado='EXITOSO',
                    severidad_log='INFO', timestamp_evento=datetime.datetime.now(datetime.timezone.utc),
                    id_activo_biologico=id_activo, tipo_activo=activo.tipo,
                    descripcion=f'Sensor {dto.sensor_id} asociado con tipo {dto.tipo_asociacion}',
                    detalle_tecnico={'sensor_id': dto.sensor_id, 'tipo_asociacion': dto.tipo_asociacion},
                    id_usuario_responsable=usuario_actual.id_usuario,
                ))
                self.db.commit()
            except Exception:
                pass

        return nueva
