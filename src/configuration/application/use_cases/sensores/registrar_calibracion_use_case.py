"""Caso de uso: Registrar calibración de sensor (POST /{id}/calibrar RF-24).

Valida: dispositivo activo, sensor pertenece al dispositivo, sensor tiene
asociación activa con el área indicada, y que valor_referencia/offset caigan
dentro del rango de seguridad definido para el tipo de sensor (categoria).

RF-24 v1.1 (RFC-006, OWASP A09): todo intento rechazado (404/422/400 aquí, 403 en
el router) queda en el historial de RF-10 con resultado FALLIDO.
RF-24 v2.0: cada calibración exitosa también genera un evento RF-10, en la
misma transacción que la calibración y su auditoría interna de M09.
"""
from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation
from typing import Optional

from sqlalchemy.orm import Session

from src.configuration.domain.entities.calibracion import Calibracion
from src.configuration.domain.repositories.auditoria_calibracion_repository import AuditoriaCalibracionRepository
from src.configuration.domain.repositories.calibracion_repository import CalibracionRepository
from src.configuration.domain.repositories.dispositivo_iot_repository import DispositivoIotRepository
from src.configuration.domain.repositories.rango_calibracion_repository import RangoCalibracionRepository
from src.configuration.domain.repositories.sensor_area_repository import SensorAreaRepository
from src.configuration.domain.repositories.sensor_repository import SensorRepository
from src.configuration.infrastructure.dto.registrar_calibracion_dto import RegistrarCalibracionDTO
from src.identity_access.domain.repositories.evento_repository import EventoRepository
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import AppError, BusinessRuleError, InfrastructureError, NotFoundError, ValidationError

logger = logging.getLogger(__name__)

TIPO_EVENTO_CALIBRACION_RECHAZADA = 29  # modulo1.tipos_eventos (migración cf12e716a4ec)
TIPO_EVENTO_CALIBRACION_EXITOSA = 30  # modulo1.tipos_eventos (migración b6f2d8a40c91)
MENSAJE_ACCESO_DENEGADO = (
    "Acceso denegado: La calibración de sensores es una función crítica restringida "
    "exclusivamente al Ingeniero de Campo o al Administrador."
)
MENSAJE_HARDWARE_NO_ENCONTRADO = (
    "Error de referencia: El sensor o dispositivo especificado no existe. "
    "No se puede registrar una calibración sobre un hardware inexistente."
)


def auditar_rechazo_calibracion(
    db: Session,
    eventos_repo: EventoRepository,
    *,
    id_usuario: int,
    id_sensor: int,
    error: AppError,
    id_dispositivo_iot: Optional[int] = None,
    id_infraestructura: Optional[int] = None,
) -> None:
    """Deja el intento rechazado en el historial de RF-10 con resultado FALLIDO.

    Best-effort: en un rechazo no hay calibración que revertir, así que si la
    escritura falla se deja constancia en el log y el rechazo conserva su 4xx en
    vez de volverse un 500 (a diferencia del camino exitoso).
    """
    try:
        eventos_repo.registrar(
            tipo_evento=TIPO_EVENTO_CALIBRACION_RECHAZADA,
            exitoso=False,
            id_usuario=id_usuario,
            detalle={
                "operacion": "CALIBRACION_SENSOR",
                "id_sensor": id_sensor,
                "id_dispositivo_iot": id_dispositivo_iot,
                "id_infraestructura": id_infraestructura,
                "codigo_http": error.status_code,
                "codigo_error": error.code,
                "motivo": error.message,
            },
            descripcion=f"Calibración rechazada (HTTP {error.status_code} {error.code})",
            modulo="MODULO9",
        )
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("RF-24: no se pudo auditar el rechazo de calibración del sensor %s", id_sensor)


class RegistrarCalibracionUseCase:

    def __init__(
        self,
        db: Session,
        sensor_repo: SensorRepository,
        dispositivo_repo: DispositivoIotRepository,
        sensor_area_repo: SensorAreaRepository,
        calibracion_repo: CalibracionRepository,
        rango_repo: RangoCalibracionRepository,
        auditoria_repo: AuditoriaCalibracionRepository,
        eventos_repo: EventoRepository,
    ) -> None:
        self.db = db
        self.sensor_repo = sensor_repo
        self.dispositivo_repo = dispositivo_repo
        self.sensor_area_repo = sensor_area_repo
        self.calibracion_repo = calibracion_repo
        self.rango_repo = rango_repo
        self.auditoria_repo = auditoria_repo
        self.eventos_repo = eventos_repo

    def execute(
        self,
        id_sensor: int,
        dto: RegistrarCalibracionDTO,
        usuario_actual: UsuarioActual,
        *,
        ids_fincas_permitidas: Optional[list[int]] = None,
    ) -> Calibracion:
        try:
            valor, offset = self._validar(id_sensor, dto, ids_fincas_permitidas)
        except (NotFoundError, BusinessRuleError, ValidationError) as exc:
            auditar_rechazo_calibracion(
                self.db,
                self.eventos_repo,
                id_usuario=usuario_actual.id_usuario,
                id_sensor=id_sensor,
                error=exc,
                id_dispositivo_iot=dto.id_dispositivo_iot,
                id_infraestructura=dto.id_infraestructura,
            )
            raise

        calibracion = Calibracion.crear(
            id_dispositivo_iot=dto.id_dispositivo_iot,
            id_sensor=id_sensor,
            valor_referencia=valor,
            fecha_calibracion=dto.fecha_calibracion,
            id_usuario=usuario_actual.id_usuario,
            ganancia=Decimal(str(dto.ganancia)),
            offset=offset,
            observaciones=dto.observaciones,
            modo_calibracion=dto.modo_calibracion,
        )

        try:
            calibracion_guardada = self.calibracion_repo.guardar(calibracion)
            # Ambas trazas son obligatorias y se confirman con la calibración.
            # Si falla M09 o RF-10, se revierte toda la operación.
            try:
                self.auditoria_repo.registrar(
                    id_calibracion=calibracion_guardada.id_calibracion,
                    id_usuario=usuario_actual.id_usuario,
                    tipo_operacion="CREATE",
                    valores_nuevos=calibracion_guardada._snapshot(),
                )
                self.eventos_repo.registrar(
                    tipo_evento=TIPO_EVENTO_CALIBRACION_EXITOSA,
                    exitoso=True,
                    id_usuario=usuario_actual.id_usuario,
                    detalle={
                        "operacion": "CALIBRACION_SENSOR",
                        "id_calibracion": calibracion_guardada.id_calibracion,
                        "id_infraestructura": dto.id_infraestructura,
                        **calibracion_guardada._snapshot(),
                    },
                    descripcion=(
                        f"Calibración {calibracion_guardada.id_calibracion} registrada "
                        f"para el sensor {calibracion_guardada.id_sensor}."
                    ),
                    modulo="MODULO9",
                )
            except Exception as exc:
                raise InfrastructureError(
                    code="AUDITORIA_CALIBRACION_FALLIDA",
                    message=(
                        "Error de integridad: No se pudo garantizar la trazabilidad de la "
                        "calibración. El ajuste no ha sido aplicado; por favor, intente de nuevo."
                    ),
                    original_error=exc,
                )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return calibracion_guardada

    def _validar(
        self, id_sensor: int, dto: RegistrarCalibracionDTO, ids_fincas_permitidas: Optional[list[int]]
    ) -> tuple[Decimal, Decimal]:
        """Flujos alternos de RF-24. Devuelve (valor_referencia, offset) ya convertidos."""
        # TC-M09-141 (#503): sin alcance, un Ingeniero calibraba sensores de fincas
        # a las que no tiene acceso (y que ni siquiera puede listar). Un dispositivo
        # ajeno responde 404, igual que uno inexistente, para no confirmar que
        # existe; el sensor queda cubierto porque debe pertenecer a este dispositivo.
        dispositivo = self.dispositivo_repo.obtener_por_id(
            dto.id_dispositivo_iot, ids_fincas_permitidas=ids_fincas_permitidas
        )
        if dispositivo is None:
            raise NotFoundError(
                code="DISPOSITIVO_NO_ENCONTRADO",
                message=MENSAJE_HARDWARE_NO_ENCONTRADO,
            )
        if not dispositivo.es_activo:
            raise BusinessRuleError(
                code="DISPOSITIVO_INACTIVO",
                # INC-M09-76-G136 (#512): texto exacto de RF-24 v2.0, con el serial.
                message=(
                    f"Operación rechazada: El dispositivo {dispositivo.serial.valor} está inactivo. "
                    "Debe activar el dispositivo antes de proceder con el registro de nuevos "
                    "parámetros de calibración."
                ),
            )

        sensor = self.sensor_repo.obtener_por_id(id_sensor)
        if sensor is None:
            raise NotFoundError(
                code="SENSOR_NO_ENCONTRADO",
                message=MENSAJE_HARDWARE_NO_ENCONTRADO,
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
                message=(
                    f"Conflicto de ubicación: El sensor {id_sensor} no está asociado al área "
                    f"{dto.id_infraestructura}. Verifique la ubicación física y lógica del equipo "
                    "antes de calibrar."
                ),
                field="id_infraestructura",
            )

        try:
            valor = Decimal(str(dto.valor_referencia))
            offset = Decimal(str(dto.offset)) if dto.offset is not None else valor
        except InvalidOperation:
            valor_ingresado = "null" if dto.valor_referencia is None else str(dto.valor_referencia)
            raise ValidationError(
                code="VALOR_CALIBRACION_INVALIDO",
                message=(
                    "Error de formato: El valor de referencia debe ser un número decimal válido. "
                    f"Verifique la entrada '{valor_ingresado}'."
                ),
                field="valor_referencia",
            )
        # INC-M09-75-G132 (#511): Decimal("NaN") / Decimal("Infinity") se construyen
        # sin error, pero NaN revienta (500) al compararlo contra el rango e
        # Infinity se reportaba como fuera de rango. RF-24 v2.0 los trata como
        # formato decimal inválido, antes de la validación de rango.
        if not valor.is_finite():
            raise ValidationError(
                code="VALOR_CALIBRACION_INVALIDO",
                message=(
                    "Error de formato: El valor de referencia debe ser un número decimal "
                    f"válido. Verifique la entrada '{dto.valor_referencia}'."
                ),
                field="valor_referencia",
            )

        # RF-24: rango de seguridad por tipo de sensor (categoria).
        rango = self.rango_repo.obtener_por_categoria(sensor.categoria) if sensor.categoria else None
        if rango is not None:
            for campo, candidato in (("valor_referencia", valor), ("offset", offset)):
                viol = rango.verificar(candidato)
                if viol is not None:
                    raise ValidationError(
                        code="VALOR_FUERA_DE_RANGO",
                        message=(
                            f"Valor fuera de límites: El ajuste de {viol['valor']} excede los rangos de seguridad "
                            f"para la variable {sensor.categoria}. "
                            "Verifique el estándar de calibración utilizado."
                        ),
                        field=campo,
                    )
        # ponytail: sin rango configurado para la categoria -> fallback al chequeo > 0 previo.
        elif valor <= 0:
            raise ValidationError(
                code="VALOR_CALIBRACION_INVALIDO",
                message="El valor de referencia debe ser un número positivo.",
                field="valor_referencia",
            )
        return valor, offset


class ConsultarCalibracionesUseCase:

    def __init__(
        self,
        db: Session,
        calibracion_repo: CalibracionRepository,
        sensor_repo: SensorRepository,
        dispositivo_repo: DispositivoIotRepository,
    ) -> None:
        self.db = db
        self.calibracion_repo = calibracion_repo
        self.sensor_repo = sensor_repo
        self.dispositivo_repo = dispositivo_repo

    def listar_por_sensor(
        self, id_sensor: int, *, ids_fincas_permitidas: Optional[list[int]] = None,
    ) -> list[Calibracion]:
        # Mismo criterio que el historial de asociaciones (INC-M09-22-G126-02):
        # el historial de un sensor de una finca ajena responde 404.
        if ids_fincas_permitidas is not None:
            sensor = self.sensor_repo.obtener_por_id(id_sensor)
            if sensor is None or self.dispositivo_repo.obtener_por_id(
                sensor.id_dispositivo_iot, ids_fincas_permitidas=ids_fincas_permitidas
            ) is None:
                raise NotFoundError(
                    code="SENSOR_NO_ENCONTRADO",
                    message=f"No existe un sensor con ID {id_sensor}.",
                )
        return self.calibracion_repo.listar_por_sensor(id_sensor)
