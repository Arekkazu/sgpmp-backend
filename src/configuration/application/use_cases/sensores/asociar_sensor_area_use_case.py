"""Caso de uso: Asociar sensor a área productiva (POST /{id}/asociar RF-22).

Si el sensor ya tiene una asociación activa en la misma área → 409 duplicado.
Si la asociación activa es en otra área → termina la anterior y crea la nueva (reasignación).
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from src.configuration.domain.entities.sensor_area import SensorArea
from src.configuration.domain.repositories.auditoria_sensor_area_repository import AuditoriaSensorAreaRepository
from src.configuration.domain.repositories.infraestructura_repository import InfraestructuraRepository
from src.configuration.domain.repositories.sensor_area_repository import SensorAreaRepository
from src.configuration.domain.repositories.sensor_repository import SensorRepository
from src.configuration.domain.value_objects.punto_instalacion import PuntoInstalacion
from src.configuration.infrastructure.dto.asociar_sensor_area_dto import AsociarSensorAreaDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import BusinessRuleError, ConflictError, NotFoundError


class AsociarSensorAreaUseCase:

    def __init__(
        self,
        db: Session,
        sensor_repo: SensorRepository,
        sensor_area_repo: SensorAreaRepository,
        infra_repo: InfraestructuraRepository,
        auditoria_repo: AuditoriaSensorAreaRepository,
    ) -> None:
        self.db = db
        self.sensor_repo = sensor_repo
        self.sensor_area_repo = sensor_area_repo
        self.infra_repo = infra_repo
        self.auditoria_repo = auditoria_repo

    def execute(self, id_sensor: int, dto: AsociarSensorAreaDTO, usuario_actual: UsuarioActual) -> SensorArea:
        sensor = self.sensor_repo.obtener_por_id(id_sensor)
        if sensor is None:
            raise NotFoundError(
                code="SENSOR_NO_ENCONTRADO",
                message=f"No existe un sensor con ID {id_sensor}.",
            )
        if sensor.id_dispositivo_iot != dto.id_dispositivo_iot:
            raise BusinessRuleError(
                code="SENSOR_DISPOSITIVO_INVALIDO",
                message=f"El sensor {id_sensor} no pertenece al dispositivo {dto.id_dispositivo_iot}.",
            )

        area = self.infra_repo.obtener_por_id(dto.id_infraestructura)
        if area is None:
            raise NotFoundError(
                code="AREA_NO_ENCONTRADA",
                message=f"No existe un área productiva con ID {dto.id_infraestructura}.",
            )
        if not area.es_activo:
            raise BusinessRuleError(
                code="AREA_NO_DISPONIBLE",
                message="No se pueden asociar sensores a áreas productivas inactivas.",
            )

        # Verificar historial de asociaciones para respetar la regla de infraestructura fija
        historial = self.sensor_area_repo.listar_por_sensor(id_sensor)
        if historial:
            area_historica = historial[0].id_infraestructura
            if area_historica != dto.id_infraestructura:
                raise BusinessRuleError(
                    code="SENSOR_INFRAESTRUCTURA_FIJA",
                    message=(
                        f"El sensor ID {id_sensor} está vinculado de por vida al área ID {area_historica}. "
                        f"Los sensores no pueden reasignarse a una infraestructura diferente."
                    ),
                )

        asociacion_activa = self.sensor_area_repo.obtener_asociacion_activa(id_sensor)
        if asociacion_activa is not None:
            raise ConflictError(
                code="ASOCIACION_DUPLICADA",
                message=f"El sensor ya está activo en el punto '{asociacion_activa.punto_instalacion.valor}' de esta área.",
            )

        punto = PuntoInstalacion(dto.punto_instalacion)
        nueva_asociacion = SensorArea.crear(
            id_sensor=id_sensor,
            id_dispositivo_iot=dto.id_dispositivo_iot,
            id_infraestructura=dto.id_infraestructura,
            punto_instalacion=punto,
            id_usuario=usuario_actual.id_usuario,
        )

        try:
            asociacion_guardada = self.sensor_area_repo.guardar(nueva_asociacion)
            self.auditoria_repo.registrar(
                id_sensores_area_asociada=asociacion_guardada.id_sensores_area_asociada,
                id_usuario=usuario_actual.id_usuario,
                tipo_operacion="CREATE",
                valores_nuevos=asociacion_guardada._snapshot(),
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return asociacion_guardada


class ConsultarAsociacionesUseCase:

    def __init__(self, db: Session, sensor_area_repo: SensorAreaRepository) -> None:
        self.db = db
        self.sensor_area_repo = sensor_area_repo

    def listar_por_sensor(self, id_sensor: int) -> list[SensorArea]:
        return self.sensor_area_repo.listar_por_sensor(id_sensor)
