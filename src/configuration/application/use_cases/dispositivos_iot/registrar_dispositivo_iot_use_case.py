"""Caso de uso: Registrar dispositivo IoT (POST RF-21).

Un dispositivo puede registrarse ya vinculado a su Gateway Edge
(``id_dispositivo_gateway``); un dispositivo de tipo GATEWAY_EDGE es el Edge.

RF-21 v2.0 (RFC-011): si el tipo es de categoría CAMARA, la resolución, los fps
y el área de cobertura son obligatorios y se validan; para un SENSOR se ignoran.
"""
from __future__ import annotations

import re
from typing import Optional

from sqlalchemy.orm import Session

from src.configuration.application.use_cases.dispositivos_iot.gateway_edge_use_case import (
    sincronizar_gateways,
    validar_gateway_edge,
)
from src.configuration.domain.entities.dispositivo_iot import DispositivoIot
from src.configuration.domain.repositories.auditoria_dispositivo_iot_repository import AuditoriaDispositivoIotRepository
from src.configuration.domain.repositories.bitacora_iot_port import BitacoraIotPort
from src.configuration.domain.repositories.dispositivo_iot_repository import DispositivoIotRepository
from src.configuration.domain.repositories.infraestructura_repository import InfraestructuraRepository
from src.configuration.domain.repositories.mqtt_port import MqttPort
from src.configuration.domain.entities.tipo_dispositivo_iot import TipoDispositivoIot
from src.configuration.domain.repositories.tipo_dispositivo_iot_repository import TipoDispositivoIotRepository
from src.configuration.domain.value_objects.serial_dispositivo import SerialDispositivo
from src.configuration.infrastructure.dto.registrar_dispositivo_iot_dto import RegistrarDispositivoIotDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import BusinessRuleError, ConflictError, NotFoundError, ValidationError

_RESOLUCION = re.compile(r"^[1-9][0-9]*x[1-9][0-9]*$")  # ANCHOxALTO en píxeles


def _atributos_vision(tipo: TipoDispositivoIot, dto: RegistrarDispositivoIotDTO) -> tuple:
    """Devuelve (resolucion, fps, area_cobertura_m2) a persistir según la categoría del tipo."""
    if not tipo.es_camara:
        return None, None, None  # mismo criterio de campos no aplicables que RF-16
    for campo, valido in (
        ("resolucion", dto.resolucion is not None and _RESOLUCION.match(dto.resolucion)),
        ("fps", dto.fps is not None and 1 <= dto.fps <= 60),
        ("area_cobertura_m2", dto.area_cobertura_m2 is not None and dto.area_cobertura_m2 > 0),
    ):
        if not valido:
            raise ValidationError(
                code="ATRIBUTOS_VISION_INVALIDOS",
                message=(
                    "Error de validación: La cámara requiere resolución (formato ANCHOxALTO), "
                    f"fps (1–60) y área de cobertura (m²) válidos. Verifique el atributo '{campo}'."
                ),
                field=campo,
            )
    return dto.resolucion, dto.fps, dto.area_cobertura_m2


class RegistrarDispositivoIotUseCase:
    """Registra un dispositivo en un área activa; el serial es único (409).

    Las cámaras exigen resolución, fps y área de cobertura (400).
    """

    def __init__(
        self,
        db: Session,
        dispositivo_repo: DispositivoIotRepository,
        infra_repo: InfraestructuraRepository,
        tipo_repo: TipoDispositivoIotRepository,
        auditoria_repo: AuditoriaDispositivoIotRepository,
        mqtt_port: Optional[MqttPort] = None,
        bitacora: Optional[BitacoraIotPort] = None,
    ) -> None:
        self.db = db
        self.dispositivo_repo = dispositivo_repo
        self.infra_repo = infra_repo
        self.tipo_repo = tipo_repo
        self.auditoria_repo = auditoria_repo
        self.mqtt_port = mqtt_port
        self.bitacora = bitacora

    def execute(self, dto: RegistrarDispositivoIotDTO, usuario_actual: UsuarioActual) -> DispositivoIot:
        area = self.infra_repo.obtener_por_id(dto.id_infraestructura)
        if area is None:
            raise NotFoundError(
                code="AREA_NO_ENCONTRADA",
                message=f"No existe un área productiva con ID {dto.id_infraestructura}.",
            )
        if not area.es_activo:
            raise BusinessRuleError(
                code="AREA_NO_DISPONIBLE",
                message="No se puede registrar el dispositivo porque el área productiva seleccionada está desactivada.",
            )

        tipo = self.tipo_repo.obtener_por_id(dto.id_tipo_dispositivo)
        if tipo is None:
            # RF-21 v2.0, FA "Tipo/categoría de dispositivo inexistente": HTTP 422.
            raise BusinessRuleError(
                code="TIPO_DISPOSITIVO_NO_ENCONTRADO",
                message="Error de catálogo: El tipo de dispositivo indicado no existe. Seleccione un tipo válido del catálogo.",
                field="id_tipo_dispositivo",
            )
        resolucion, fps, area_cobertura_m2 = _atributos_vision(tipo, dto)

        gateway = None
        if dto.id_dispositivo_gateway is not None:
            gateway = validar_gateway_edge(
                dispositivo_repo=self.dispositivo_repo,
                infra_repo=self.infra_repo,
                tipo_repo=self.tipo_repo,
                id_dispositivo_gateway=dto.id_dispositivo_gateway,
                tipo_dispositivo=tipo,
                id_infraestructura=dto.id_infraestructura,
            )

        serial = SerialDispositivo(dto.serial)

        existente = self.dispositivo_repo.obtener_por_serial(serial.valor)
        if existente is not None:
            raise ConflictError(
                code="SERIAL_DUPLICADO",
                message=f"El serial '{serial.valor}' ya está registrado en el sistema.",
                field="serial",
            )

        dispositivo = DispositivoIot.crear(
            serial=serial,
            descripcion=dto.descripcion,
            id_infraestructura=dto.id_infraestructura,
            id_tipo_dispositivo=dto.id_tipo_dispositivo,
            es_activo=dto.es_activo,
            id_dispositivo_gateway=dto.id_dispositivo_gateway,
            resolucion=resolucion,
            fps=fps,
            area_cobertura_m2=area_cobertura_m2,
        )

        try:
            dispositivo_guardado = self.dispositivo_repo.guardar(dispositivo)
            self.auditoria_repo.registrar(
                id_dispositivo_iot=dispositivo_guardado.id_dispositivo_iot,
                id_usuario=usuario_actual.id_usuario,
                tipo_operacion="CREATE",
                valores_nuevos=dispositivo_guardado._snapshot(),
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        if gateway is not None:  # el Edge gana los topics del dispositivo nuevo
            sincronizar_gateways(self.mqtt_port, self.bitacora, [gateway], usuario_actual.id_usuario)
        return dispositivo_guardado
