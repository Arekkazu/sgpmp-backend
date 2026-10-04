"""Gateway Edge de los dispositivos IoT (RF-21, RF-23 / TC-M09-250/251).

El Gateway Edge es la computadora de borde del sitio (hoy una Raspberry), el
"Gateway IoT" de M03: recibe por radio los datos de N dispositivos y es lo único
que habla MQTT con el broker. Se registra como un dispositivo más (tipo
GATEWAY_EDGE) y cada dispositivo que atiende apunta a él con
``id_dispositivo_gateway``. El broker deriva de esa relación los topics que puede
usar la credencial MQTT del Edge, así que cada cambio se le avisa
(``sincronizar_gateways``) sin rotar la clave.
"""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session

from src.configuration.domain.entities.dispositivo_iot import DispositivoIot
from src.configuration.domain.entities.tipo_dispositivo_iot import TipoDispositivoIot
from src.configuration.domain.repositories.bitacora_iot_port import BitacoraIotPort
from src.configuration.domain.repositories.dispositivo_iot_repository import DispositivoIotRepository
from src.configuration.domain.repositories.infraestructura_repository import InfraestructuraRepository
from src.configuration.domain.repositories.mqtt_port import MqttPort
from src.configuration.domain.repositories.tipo_dispositivo_iot_repository import TipoDispositivoIotRepository
from src.configuration.infrastructure.dto.asignar_gateway_edge_dto import AsignarGatewayEdgeDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import AppError, BusinessRuleError, NotFoundError

logger = logging.getLogger(__name__)

EVENTO_GATEWAY_ASIGNADO = "DISPOSITIVO_GATEWAY_EDGE_ASIGNADO"
EVENTO_SINCRONIZACION_FALLIDA = "CREDENCIAL_MQTT_SINCRONIZACION_FALLIDA"
_CAMPO = "id_dispositivo_gateway"


def validar_gateway_edge(
    *,
    dispositivo_repo: DispositivoIotRepository,
    infra_repo: InfraestructuraRepository,
    tipo_repo: TipoDispositivoIotRepository,
    id_dispositivo_gateway: int,
    tipo_dispositivo: Optional[TipoDispositivoIot],
    id_infraestructura: int,
    ids_fincas_permitidas: Optional[list[int]] = None,
) -> DispositivoIot:
    """Devuelve el Gateway Edge si el dispositivo (de ``tipo_dispositivo``, en el
    área ``id_infraestructura``) puede depender de él. Un Edge no depende de otro
    Edge, y el Edge debe estar activo y en la misma finca (puede ser otra área)."""
    if tipo_dispositivo is not None and tipo_dispositivo.es_gateway_edge:
        raise BusinessRuleError(
            code="EDGE_NO_TIENE_GATEWAY",
            message="Un Gateway Edge no puede depender de otro Gateway Edge.",
            field=_CAMPO,
        )
    gateway = dispositivo_repo.obtener_por_id(
        id_dispositivo_gateway, ids_fincas_permitidas=ids_fincas_permitidas
    )
    if gateway is None:
        raise NotFoundError(
            code="GATEWAY_EDGE_NO_ENCONTRADO",
            message=f"No existe un Gateway Edge con ID {id_dispositivo_gateway}.",
            field=_CAMPO,
        )
    tipo_gateway = tipo_repo.obtener_por_id(gateway.id_tipo_dispositivo)
    if tipo_gateway is None or not tipo_gateway.es_gateway_edge:
        raise BusinessRuleError(
            code="NO_ES_GATEWAY_EDGE",
            message=f"El dispositivo {gateway.serial.valor} no es un Gateway Edge.",
            field=_CAMPO,
        )
    if not gateway.es_activo:
        raise BusinessRuleError(
            code="GATEWAY_EDGE_INACTIVO",
            message=f"El Gateway Edge {gateway.serial.valor} está inactivo.",
            field=_CAMPO,
        )
    area_gateway = infra_repo.obtener_por_id(gateway.id_infraestructura)
    area = infra_repo.obtener_por_id(id_infraestructura)
    if area_gateway is None or area is None or area_gateway.id_finca != area.id_finca:
        raise BusinessRuleError(
            code="GATEWAY_EDGE_OTRA_FINCA",
            message="El Gateway Edge debe pertenecer a la misma finca que el dispositivo.",
            field=_CAMPO,
        )
    return gateway


def sincronizar_gateways(
    mqtt_port: Optional[MqttPort],
    bitacora: Optional[BitacoraIotPort],
    gateways: list[DispositivoIot],
    id_usuario: int,
) -> None:
    """Le pide al broker recalcular los permisos MQTT de cada Edge desde modulo9.

    Best-effort: si falla, el cambio en la BD se mantiene, queda en la bitácora y
    el broker lo corrige solo al reconciliar con modulo9 cuando reconecta.
    """
    if mqtt_port is None:
        return
    for gateway in gateways:
        try:
            mqtt_port.sincronizar_credencial(gateway.serial.valor)
        except AppError as exc:
            logger.warning(
                "No se pudo sincronizar la credencial MQTT de %s.", gateway.serial.valor, exc_info=True
            )
            if bitacora is not None:
                bitacora.registrar(
                    evento=EVENTO_SINCRONIZACION_FALLIDA,
                    exitoso=False,
                    id_dispositivo_iot=gateway.id_dispositivo_iot,
                    serial=gateway.serial.valor,
                    id_usuario=id_usuario,
                    detalle={"error": exc.code},
                )


class AsignarGatewayEdgeUseCase:
    """Asigna, cambia o quita el Gateway Edge de un dispositivo (PATCH /{id}/gateway)."""

    def __init__(
        self,
        db: Session,
        dispositivo_repo: DispositivoIotRepository,
        infra_repo: InfraestructuraRepository,
        tipo_repo: TipoDispositivoIotRepository,
        mqtt_port: Optional[MqttPort],
        bitacora: BitacoraIotPort,
    ) -> None:
        self.db = db
        self.dispositivo_repo = dispositivo_repo
        self.infra_repo = infra_repo
        self.tipo_repo = tipo_repo
        self.mqtt_port = mqtt_port
        self.bitacora = bitacora

    def execute(
        self,
        id_dispositivo_iot: int,
        dto: AsignarGatewayEdgeDTO,
        usuario_actual: UsuarioActual,
        *,
        ids_fincas_permitidas: Optional[list[int]] = None,
    ) -> DispositivoIot:
        dispositivo = self.dispositivo_repo.obtener_por_id(
            id_dispositivo_iot, ids_fincas_permitidas=ids_fincas_permitidas
        )
        if dispositivo is None:
            raise NotFoundError(
                code="DISPOSITIVO_NO_ENCONTRADO",
                message=f"No existe un dispositivo IoT con ID {id_dispositivo_iot}.",
            )
        if not dispositivo.es_activo:
            raise BusinessRuleError(
                code="DISPOSITIVO_INACTIVO",
                message="No se puede cambiar el Gateway Edge de un dispositivo inactivo.",
            )

        anterior, nuevo = dispositivo.id_dispositivo_gateway, dto.id_dispositivo_gateway
        if anterior == nuevo:
            return dispositivo

        afectados: list[DispositivoIot] = []
        if nuevo is not None:
            afectados.append(
                validar_gateway_edge(
                    dispositivo_repo=self.dispositivo_repo,
                    infra_repo=self.infra_repo,
                    tipo_repo=self.tipo_repo,
                    id_dispositivo_gateway=nuevo,
                    tipo_dispositivo=self.tipo_repo.obtener_por_id(dispositivo.id_tipo_dispositivo),
                    id_infraestructura=dispositivo.id_infraestructura,
                    ids_fincas_permitidas=ids_fincas_permitidas,
                )
            )
        if anterior is not None:
            gateway_anterior = self.dispositivo_repo.obtener_por_id(anterior)
            if gateway_anterior is not None:
                afectados.append(gateway_anterior)

        dispositivo.asignar_gateway(nuevo)
        try:
            dispositivo = self.dispositivo_repo.actualizar(dispositivo)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        self.bitacora.registrar(
            evento=EVENTO_GATEWAY_ASIGNADO,
            exitoso=True,
            id_dispositivo_iot=dispositivo.id_dispositivo_iot,
            serial=dispositivo.serial.valor,
            id_usuario=usuario_actual.id_usuario,
            detalle={"id_gateway_anterior": anterior, "id_gateway_nuevo": nuevo},
        )
        sincronizar_gateways(self.mqtt_port, self.bitacora, afectados, usuario_actual.id_usuario)
        return dispositivo
