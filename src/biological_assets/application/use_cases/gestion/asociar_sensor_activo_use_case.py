from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

from src.biological_assets.application.use_cases._registrar_evento_bitacora import registrar_evento_bitacora
from src.biological_assets.application.use_cases.gestion._auditoria_rechazos import (
    ejecutar_con_auditoria_de_rechazo,
)
from src.biological_assets.domain.entities.activo_biologico import AsociacionSensorActivo, EventoAuditoria
from src.biological_assets.domain.repositories.activo_biologico_repository import ActivoBiologicoRepository
from src.biological_assets.domain.repositories.asociacion_sensor_activo_repository import (
    AsociacionSensorActivoRepository,
)
from src.biological_assets.domain.repositories.bitacora_auditoria_repository import BitacoraAuditoriaRepository
from src.biological_assets.domain.repositories.dispositivo_iot_estado_port import DispositivoIotEstadoPort
from src.biological_assets.domain.repositories.infraestructura_consulta_port import InfraestructuraConsultaPort
from src.biological_assets.domain.repositories.sensor_consulta_port import SensorConsultaPort
from src.biological_assets.domain.value_objects.estado_activo import EstadoActivo
from src.shared.errors import AppError, BusinessRuleError, ConflictError, NotFoundError, ValidationError

if TYPE_CHECKING:
    from src.identity_access.infrastructure.dependencies import UsuarioActual
    from src.biological_assets.infrastructure.dto.asociar_sensor_activo_dto import AsociarSensorActivoDTO

# Mapa de tipo_asociacion DTO (uppercase) → valor en DB (lowercase).
# AMBIENTAL no es alcanzable aquí -- el DTO ya la excluye del Literal (#351);
# ese caso lo maneja AsociarSensorInfraestructuraUseCase.
_TIPO_DB = {
    'DIRECTA': 'directa',
    'POBLACIONAL': 'poblacional',
}

# RF-49 FA "Dispositivo IoT Fuera de Línea": sin heartbeat en los últimos 30 min.
_UMBRAL_DESCONEXION_MINUTOS = 30


class AsociarSensorActivoUseCase:

    def __init__(
        self,
        db: Session,
        repo: AsociacionSensorActivoRepository,
        activo_repo: ActivoBiologicoRepository,
        sensor_port: SensorConsultaPort,
        infra_port: InfraestructuraConsultaPort,
        bitacora_repo: BitacoraAuditoriaRepository | None = None,
        dispositivo_estado_port: DispositivoIotEstadoPort | None = None,
    ) -> None:
        self.db = db
        self.repo = repo
        self.activo_repo = activo_repo
        self.sensor_port = sensor_port
        self.infra_port = infra_port
        self.bitacora_repo = bitacora_repo
        self.dispositivo_estado_port = dispositivo_estado_port

    def execute(
        self,
        id_activo: int,
        dto: AsociarSensorActivoDTO,
        usuario_actual: UsuarioActual,
        *,
        ids_fincas_permitidas: list[int] | None = None,
    ) -> AsociacionSensorActivo:
        def obtener_activo_en_alcance(activo_id: int):
            return self.activo_repo.obtener_por_id(
                activo_id,
                ids_fincas_permitidas=ids_fincas_permitidas,
            )
        return ejecutar_con_auditoria_de_rechazo(
            lambda: self._execute(
                id_activo,
                dto,
                usuario_actual,
                ids_fincas_permitidas=ids_fincas_permitidas,
            ),
            db=self.db,
            bitacora_repo=self.bitacora_repo,
            obtener_activo=obtener_activo_en_alcance,
            id_activo=id_activo,
            id_usuario=usuario_actual.id_usuario,
            rf_origen='RF49',
            tipo_evento_rechazado='ASOCIACION_IOT_RECHAZADA',
            clasificacion_biologica='GESTION_OPERATIVA',
        )

    def _execute(
        self,
        id_activo: int,
        dto: AsociarSensorActivoDTO,
        usuario_actual: UsuarioActual,
        *,
        ids_fincas_permitidas: list[int] | None = None,
    ) -> AsociacionSensorActivo:
        # V1 — Activo existe (CU11 Flujo Alterno "Activo Biológico No Válido":
        # inexistente o BAJA comparten el mismo flujo -> BusinessRuleError/422,
        # no NotFoundError/404. V2 abajo ya usa BusinessRuleError para el caso
        # BAJA; esto solo alinea el caso "inexistente" con esa misma regla.
        activo = self.activo_repo.obtener_por_id(
            id_activo,
            ids_fincas_permitidas=ids_fincas_permitidas,
        )
        if activo is None:
            raise BusinessRuleError(
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

        # V7 — Compatibilidad biologica sensor-especie (RF-49 R3 / FA-04).
        # La configuracion de M09 es una lista blanca por sensor. Fallar
        # cerrado cuando no hay parametrizacion evita que la ausencia del
        # catalogo vuelva a equivaler a "cualquier especie es compatible".
        compatibilidad = self.sensor_port.obtener_compatibilidad_especie(
            dto.sensor_id,
            activo.id_especie,
        )
        if compatibilidad is None or not compatibilidad.configurada:
            raise ValidationError(
                code='COMPATIBILIDAD_SENSOR_NO_CONFIGURADA',
                message=(
                    f'No existe una parametrización de compatibilidad biológica para el sensor '
                    f'{dto.sensor_id}. Configure al menos una especie compatible en M09 antes '
                    'de asociarlo a un activo biológico.'
                ),
                field='sensor_id',
            )

        if not compatibilidad.es_compatible:
            especies = ', '.join(compatibilidad.especies_compatibles)
            raise ValidationError(
                code='INCOMPATIBILIDAD_ESPECIE_SENSOR',
                message=(
                    f'Incompatibilidad biológica. El sensor {dto.sensor_id} está parametrizado '
                    f'para {especies}, no es compatible con el activo {id_activo} de tipo '
                    f'{compatibilidad.nombre_especie_activo}.'
                ),
                field='sensor_id',
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

            # V8c — Restricción 4 (RF-49): un sensor POBLACIONAL solo puede estar
            # activo en un único lote a la vez. V8b solo valida por activo (que el
            # LOTE no tenga ya otro sensor); esta es la simétrica por SENSOR (que
            # el sensor no esté ya activo en otro lote), ausente hasta ahora.
            activas_sensor_pob = self.repo.listar_activas_por_sensor(dto.sensor_id, 'poblacional')
            conflicto_sensor = next(
                (a for a in activas_sensor_pob if a.id_activo_biologico != id_activo),
                None,
            )
            if conflicto_sensor:
                raise ConflictError(
                    code='SENSOR_YA_ASOCIADO_A_OTRO_LOTE',
                    message=(
                        f'El sensor {dto.sensor_id} ya está asociado con tipo POBLACIONAL '
                        f'al activo {conflicto_sensor.id_activo_biologico}. Un sensor solo puede '
                        'estar activo en un único lote a la vez. Desactive esa asociación primero.'
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
            nueva.advertencia = self._calcular_advertencia_desconexion(sensor.id_dispositivo_iot)

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

        except AppError:
            self.db.rollback()
            raise
        except Exception as exc:
            self.db.rollback()
            registrar_evento_bitacora(self.bitacora_repo, self.db, EventoAuditoria(
                rf_origen='RF49', tipo_evento='ASOCIACION_IOT_FALLIDA',
                clasificacion_biologica='GESTION_OPERATIVA', resultado='FALLIDO',
                severidad_log='ERROR', timestamp_evento=datetime.datetime.now(datetime.timezone.utc),
                id_activo_biologico=id_activo, tipo_activo=activo.tipo,
                detalle_tecnico={'error': str(exc), 'sensor_id': dto.sensor_id},
                id_usuario_responsable=usuario_actual.id_usuario,
            ))
            raise

        registrar_evento_bitacora(self.bitacora_repo, self.db, EventoAuditoria(
            rf_origen='RF49', tipo_evento='ASOCIACION_IOT_CREADA',
            clasificacion_biologica='GESTION_OPERATIVA', resultado='EXITOSO',
            severidad_log='INFO', timestamp_evento=datetime.datetime.now(datetime.timezone.utc),
            id_activo_biologico=id_activo, tipo_activo=activo.tipo,
            descripcion=f'Sensor {dto.sensor_id} asociado con tipo {dto.tipo_asociacion}',
            detalle_tecnico={'sensor_id': dto.sensor_id, 'tipo_asociacion': dto.tipo_asociacion},
            id_usuario_responsable=usuario_actual.id_usuario,
        ))

        return nueva

    def _calcular_advertencia_desconexion(self, id_dispositivo_iot: int) -> str | None:
        """RF-49 FA "Dispositivo IoT Fuera de Línea": sin heartbeat hace más de
        30 min, la asociación igual se crea (HTTP 201) pero con advertencia."""
        if self.dispositivo_estado_port is None:
            return None

        estado = self.dispositivo_estado_port.obtener_estado(id_dispositivo_iot)
        if estado is None or estado.fecha_ultimo_contacto is None:
            return None

        ultimo_contacto = estado.fecha_ultimo_contacto
        if ultimo_contacto.tzinfo is None:
            ultimo_contacto = ultimo_contacto.replace(tzinfo=datetime.timezone.utc)

        ahora = datetime.datetime.now(datetime.timezone.utc)
        sin_contacto = ahora - ultimo_contacto
        if sin_contacto <= datetime.timedelta(minutes=_UMBRAL_DESCONEXION_MINUTOS):
            return None

        return (
            f'El dispositivo {id_dispositivo_iot} se encuentra desconectado desde las '
            f'{ultimo_contacto.strftime("%H:%M:%S")}. Las lecturas podrían no verse reflejadas de inmediato.'
        )
