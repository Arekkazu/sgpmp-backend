"""Casos de uso: credencial MQTT por Raspberry (RF-23, TC-M09-250/251).

Cada Raspberry se conecta al broker con su propia credencial (usuario = serial
del dispositivo del path) que solo tiene permiso sobre los topics de sus
seriales. La emite y la revoca BROKER-MQTT-SGPMP, el único componente que habla
MQTT; acá van la autorización (RBAC en el router), el alcance por finca, las
reglas de negocio y la auditoría. La contraseña no se persiste: se devuelve
una sola vez al usuario que la generó.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from src.configuration.domain.entities.dispositivo_iot import DispositivoIot
from src.configuration.domain.repositories.bitacora_credencial_mqtt_port import (
    BitacoraCredencialMqttPort,
)
from src.configuration.domain.repositories.dispositivo_iot_repository import DispositivoIotRepository
from src.configuration.domain.repositories.mqtt_port import (
    CredencialMqtt,
    EstadoCredencialMqtt,
    MqttPort,
)
from src.configuration.infrastructure.dto.emitir_credencial_mqtt_dto import EmitirCredencialMqttDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import AppError, BusinessRuleError, NotFoundError

EVENTO_EMITIDA = "CREDENCIAL_MQTT_EMITIDA"
EVENTO_REVOCADA = "CREDENCIAL_MQTT_REVOCADA"


def _obtener_dispositivo(
    repo: DispositivoIotRepository,
    id_dispositivo_iot: int,
    ids_fincas_permitidas: Optional[list[int]],
) -> DispositivoIot:
    dispositivo = repo.obtener_por_id(id_dispositivo_iot, ids_fincas_permitidas=ids_fincas_permitidas)
    if dispositivo is None:
        raise NotFoundError(
            code="DISPOSITIVO_NO_ENCONTRADO",
            message=f"No existe un dispositivo IoT con ID {id_dispositivo_iot}.",
        )
    return dispositivo


class EmitirCredencialMqttUseCase:
    """Crea la credencial o la rota: la clave anterior deja de servir."""

    def __init__(
        self,
        db: Session,
        dispositivo_repo: DispositivoIotRepository,
        mqtt_port: MqttPort,
        bitacora: BitacoraCredencialMqttPort,
    ) -> None:
        self.db = db
        self.dispositivo_repo = dispositivo_repo
        self.mqtt_port = mqtt_port
        self.bitacora = bitacora

    def execute(
        self,
        id_dispositivo_iot: int,
        dto: EmitirCredencialMqttDTO,
        usuario_actual: UsuarioActual,
        *,
        ids_fincas_permitidas: Optional[list[int]] = None,
    ) -> CredencialMqtt:
        ids = [id_dispositivo_iot, *dto.ids_dispositivos_adicionales]
        dispositivos = [
            _obtener_dispositivo(self.dispositivo_repo, i, ids_fincas_permitidas)
            for i in dict.fromkeys(ids)  # principal primero, sin repetidos
        ]
        for d in dispositivos:
            if not d.es_activo:
                raise BusinessRuleError(
                    code="DISPOSITIVO_INACTIVO",
                    message=f"No se puede emitir una credencial MQTT para el dispositivo inactivo {d.serial.valor}.",
                )

        principal, *adicionales = dispositivos
        seriales_adicionales = [d.serial.valor for d in adicionales]
        try:
            credencial = self.mqtt_port.emitir_credencial(principal.serial.valor, seriales_adicionales)
        except AppError as exc:
            self._auditar(principal, usuario_actual, False, {"seriales_adicionales": seriales_adicionales, "error": exc.code})
            raise
        self._auditar(principal, usuario_actual, True, {"seriales": credencial.seriales})
        return credencial

    def _auditar(self, d: DispositivoIot, usuario: UsuarioActual, exitoso: bool, detalle: dict) -> None:
        self.bitacora.registrar(
            evento=EVENTO_EMITIDA,
            exitoso=exitoso,
            id_dispositivo_iot=d.id_dispositivo_iot,
            serial=d.serial.valor,
            id_usuario=usuario.id_usuario,
            detalle=detalle,
        )


class ConsultarCredencialMqttUseCase:

    def __init__(self, db: Session, dispositivo_repo: DispositivoIotRepository, mqtt_port: MqttPort) -> None:
        self.db = db
        self.dispositivo_repo = dispositivo_repo
        self.mqtt_port = mqtt_port

    def execute(
        self,
        id_dispositivo_iot: int,
        *,
        ids_fincas_permitidas: Optional[list[int]] = None,
    ) -> Optional[EstadoCredencialMqtt]:
        """None si el dispositivo no tiene credencial propia (todavía usa la
        compartida, o transmite a través de otra Raspberry)."""
        dispositivo = _obtener_dispositivo(self.dispositivo_repo, id_dispositivo_iot, ids_fincas_permitidas)
        return self.mqtt_port.consultar_credencial(dispositivo.serial.valor)


class RevocarCredencialMqttUseCase:
    """Desconecta a la Raspberry en el acto. Se permite también sobre
    dispositivos inactivos (desactivar ya revoca, pero puede haber fallado)."""

    def __init__(
        self,
        db: Session,
        dispositivo_repo: DispositivoIotRepository,
        mqtt_port: MqttPort,
        bitacora: BitacoraCredencialMqttPort,
    ) -> None:
        self.db = db
        self.dispositivo_repo = dispositivo_repo
        self.mqtt_port = mqtt_port
        self.bitacora = bitacora

    def execute(
        self,
        id_dispositivo_iot: int,
        usuario_actual: UsuarioActual,
        *,
        ids_fincas_permitidas: Optional[list[int]] = None,
    ) -> None:
        dispositivo = _obtener_dispositivo(self.dispositivo_repo, id_dispositivo_iot, ids_fincas_permitidas)
        revocar_y_auditar(self.mqtt_port, self.bitacora, dispositivo, usuario_actual.id_usuario)


def revocar_y_auditar(
    mqtt_port: MqttPort,
    bitacora: BitacoraCredencialMqttPort,
    dispositivo: DispositivoIot,
    id_usuario: int,
    *,
    motivo: str = "manual",
) -> None:
    """Revoca y deja rastro del resultado. Relanza el error del broker."""
    serial = dispositivo.serial.valor
    try:
        mqtt_port.revocar_credencial(serial)
    except AppError as exc:
        bitacora.registrar(
            evento=EVENTO_REVOCADA,
            exitoso=False,
            id_dispositivo_iot=dispositivo.id_dispositivo_iot,
            serial=serial,
            id_usuario=id_usuario,
            detalle={"motivo": motivo, "error": exc.code},
        )
        raise
    bitacora.registrar(
        evento=EVENTO_REVOCADA,
        exitoso=True,
        id_dispositivo_iot=dispositivo.id_dispositivo_iot,
        serial=serial,
        id_usuario=id_usuario,
        detalle={"motivo": motivo},
    )
