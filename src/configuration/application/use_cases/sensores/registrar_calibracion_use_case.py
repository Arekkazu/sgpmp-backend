"""Caso de uso: Registrar calibración de sensor (POST /{id}/calibrar RF-24).

Valida: dispositivo activo, sensor pertenece al dispositivo,
sensor tiene asociación activa con el área indicada, valor_referencia > 0.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

from sqlalchemy.orm import Session

from src.configuration.domain.entities.calibracion import Calibracion
from src.configuration.domain.repositories.calibracion_repository import CalibracionRepository
from src.configuration.domain.repositories.dispositivo_iot_repository import DispositivoIotRepository
from src.configuration.domain.repositories.sensor_area_repository import SensorAreaRepository
from src.configuration.domain.repositories.sensor_repository import SensorRepository
from src.configuration.infrastructure.dto.registrar_calibracion_dto import RegistrarCalibracionDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import BusinessRuleError, NotFoundError, ValidationError


class RegistrarCalibracionUseCase:

    def __init__(
        self,
        db: Session,
        sensor_repo: SensorRepository,
        dispositivo_repo: DispositivoIotRepository,
        sensor_area_repo: SensorAreaRepository,
        calibracion_repo: CalibracionRepository,
    ) -> None:
        self.db = db
        self.sensor_repo = sensor_repo
        self.dispositivo_repo = dispositivo_repo
        self.sensor_area_repo = sensor_area_repo
        self.calibracion_repo = calibracion_repo

    def execute(self, id_sensor: int, dto: RegistrarCalibracionDTO, usuario_actual: UsuarioActual) -> Calibracion:
        dispositivo = self.dispositivo_repo.obtener_por_id(dto.id_dispositivo_iot)
        if dispositivo is None:
            raise NotFoundError(
                code="DISPOSITIVO_NO_ENCONTRADO",
                message=f"No existe un dispositivo IoT con ID {dto.id_dispositivo_iot}.",
            )
        if not dispositivo.es_activo:
            raise BusinessRuleError(
                code="DISPOSITIVO_INACTIVO",
                message="Solo se pueden calibrar sensores de dispositivos activos.",
            )

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

        asociacion_activa = self.sensor_area_repo.obtener_asociacion_activa(id_sensor)
        if asociacion_activa is None or asociacion_activa.id_infraestructura != dto.id_infraestructura:
            raise ValidationError(
                code="SENSOR_AREA_INVALIDA",
                message=f"El sensor {id_sensor} no está asociado al área {dto.id_infraestructura}. Verifique la ubicación física y lógica del equipo antes de calibrar.",
                field="id_infraestructura",
            )

        try:
            valor = Decimal(str(dto.valor_referencia))
        except InvalidOperation:
            raise ValidationError(
                code="VALOR_CALIBRACION_INVALIDO",
                message="El valor de referencia debe ser un número decimal válido.",
                field="valor_referencia",
            )
        if valor <= 0:
            raise ValidationError(
                code="VALOR_CALIBRACION_INVALIDO",
                message="El valor de referencia debe ser un número positivo.",
                field="valor_referencia",
            )

        calibracion = Calibracion.crear(
            id_dispositivo_iot=dto.id_dispositivo_iot,
            id_sensor=id_sensor,
            valor_referencia=valor,
            fecha_calibracion=dto.fecha_calibracion,
            id_usuario=usuario_actual.id_usuario,
            observaciones=dto.observaciones,
        )

        try:
            calibracion_guardada = self.calibracion_repo.guardar(calibracion)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return calibracion_guardada


class ConsultarCalibracionesUseCase:

    def __init__(self, db: Session, calibracion_repo: CalibracionRepository) -> None:
        self.db = db
        self.calibracion_repo = calibracion_repo

    def listar_por_sensor(self, id_sensor: int) -> list[Calibracion]:
        return self.calibracion_repo.listar_por_sensor(id_sensor)
