"""Dobles de puertos para ejercitar RF-56 sin HTTP, sin M04 real y sin Edge.

No clasifican mediciones (RF-55). No implementan buffer de dispositivo (RF-54).
MotorInferenciaPort se usa solo para observar el intento síncrono del use case.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from src.telemetry.domain.entities.telemetria import (
    DispositivoInfo,
    EventoEdgeComputing,
    PaqueteInferencia,
)
from src.telemetry.domain.repositories.dispositivo_port import (
    CamaraInfo,
    DispositivoHeartbeatInfo,
    DispositivoPort,
)
from src.telemetry.domain.repositories.evento_edge_repository import EventoEdgeRepository
from src.telemetry.domain.repositories.motor_inferencia_port import MotorInferenciaPort
from src.telemetry.domain.repositories.paquete_inferencia_repository import (
    PaqueteInferenciaRepository,
)
from src.telemetry.infrastructure.dto.recibir_evento_edge_dto import RecibirEventoEdgeDTO


class SesionNula:
    """Session mínima: el use case llama commit/rollback; no hay motor SQL."""

    def commit(self) -> None:
        return None

    def rollback(self) -> None:
        return None


class EventoEdgeRepoMemoria(EventoEdgeRepository):
    def __init__(self) -> None:
        self.guardados: list[EventoEdgeComputing] = []
        self._seq = 1

    def guardar(self, evento: EventoEdgeComputing) -> EventoEdgeComputing:
        evento.id_evento_edge_computing = self._seq
        self._seq += 1
        self.guardados.append(evento)
        return evento


class PaqueteInferenciaRepoMemoria(PaqueteInferenciaRepository):
    def __init__(self) -> None:
        self.guardados: list[PaqueteInferencia] = []
        self.estados: list[tuple[int, str, int]] = []
        self._seq = 1

    def guardar(self, paquete: PaqueteInferencia) -> PaqueteInferencia:
        paquete.id_paquetes_inferencia = self._seq
        self._seq += 1
        self.guardados.append(paquete)
        return paquete

    def actualizar_estado(self, id_paquete: int, estado: str, intento: int) -> None:
        self.estados.append((id_paquete, estado, intento))
        for p in self.guardados:
            if p.id_paquetes_inferencia == id_paquete:
                p.estado_paquete = estado
                p.intento_envios = intento


class MotorObservado(MotorInferenciaPort):
    """No es M04: registra llamadas y devuelve el booleano que el test configure.

    Por defecto ``exito=False`` para no simular un envío exitoso a M04.
    Quien necesite el camino ENVIADO del use case debe pasar ``exito=True``
    y no interpretarlo como ACK real del motor de inferencia.
    """

    def __init__(self, exito: bool = False) -> None:
        self.exito = exito
        self.paquetes: list[PaqueteInferencia] = []

    def enviar_paquete(self, paquete: PaqueteInferencia) -> bool:
        self.paquetes.append(paquete)
        return self.exito

    def enviar_lote(self, paquetes: list[PaqueteInferencia]) -> bool:
        self.paquetes.extend(paquetes)
        return self.exito


class DispositivoPortFijo(DispositivoPort):
    def __init__(self, info: Optional[DispositivoInfo]) -> None:
        self.info = info
        self.llamadas: list[tuple[int, int, str]] = []

    def obtener_dispositivo_activo(
        self,
        device_id: int,
        sensor_id: int,
        access_key: str,
    ) -> Optional[DispositivoInfo]:
        self.llamadas.append((device_id, sensor_id, access_key))
        return self.info

    def validar_dispositivo_heartbeat(
        self,
        device_id: int,
        access_key: str,
    ) -> Optional[DispositivoHeartbeatInfo]:
        return None

    def obtener_camara(self, device_id: int, access_key: str) -> Optional[CamaraInfo]:
        return None


def ahora_utc() -> datetime:
    return datetime.now(timezone.utc)


def dto_evento_edge(
    *,
    clasificacion_rf55: str = "NORMAL",
    severidad: Optional[str] = None,
    access_key: str = "serial-prueba",
    device_id: int = 1,
    sensor_id: int = 1,
    estado_conectividad: bool = True,
    variables: Optional[list[dict]] = None,
) -> RecibirEventoEdgeDTO:
    ts = ahora_utc()
    if variables is None:
        variables = [
            {
                "tipo_variable": "TEMPERATURA_AMBIENTAL",
                "valor": Decimal("22.0"),
                "unidad": "C",
                "timestamp_captura": ts,
            }
        ]
    return RecibirEventoEdgeDTO(
        device_id=device_id,
        sensor_id=sensor_id,
        access_key=access_key,
        clasificacion_rf55=clasificacion_rf55,
        severidad=severidad,
        variables_involucradas=variables,
        timestamp_captura=ts,
        timestamp_procesamiento_edge=ts,
        origen="TIEMPO_REAL",
        estado_conectividad=estado_conectividad,
    )


def recibir_use_case(
    *,
    eventos: Optional[EventoEdgeRepoMemoria] = None,
    paquetes: Optional[PaqueteInferenciaRepoMemoria] = None,
    dispositivo: Optional[DispositivoPortFijo] = None,
    motor: Optional[MotorObservado] = None,
):
    """Ensambla RecibirEventoEdgeUseCase con dobles aislados (sin SQL ni HTTP)."""
    from src.telemetry.application.use_cases.inferencia.recibir_evento_edge_use_case import (
        RecibirEventoEdgeUseCase,
    )
    from src.telemetry.domain.entities.telemetria import DispositivoInfo

    if eventos is None:
        eventos = EventoEdgeRepoMemoria()
    if paquetes is None:
        paquetes = PaqueteInferenciaRepoMemoria()
    if motor is None:
        motor = MotorObservado(exito=False)
    if dispositivo is None:
        dispositivo = DispositivoPortFijo(
            DispositivoInfo(
                id_dispositivo_iot=7,
                id_sensor=8,
                es_activo_dispositivo=True,
                es_activo_sensor=True,
                id_infraestructura=3,
            )
        )
    use_case = RecibirEventoEdgeUseCase(
        db=SesionNula(),
        evento_edge_repo=eventos,
        paquete_repo=paquetes,
        dispositivo_port=dispositivo,
        motor_inferencia_port=motor,
    )
    return use_case, eventos, paquetes, motor, dispositivo


def evento_para_consolidar(
    *,
    clasificacion_rf55: str = "DESVIACION_SIMPLE",
    variables: Optional[list[dict]] = None,
) -> EventoEdgeComputing:
    ts = ahora_utc()
    if variables is None:
        variables = [
            {
                "tipo_variable": "TEMPERATURA_AMBIENTAL",
                "valor": Decimal("40.0"),
                "unidad": "C",
                "timestamp_captura": ts,
            },
            {
                "tipo_variable": "HUMEDAD_RELATIVA",
                "valor": Decimal("80.0"),
                "unidad": "%",
                "timestamp_captura": ts,
            },
        ]
    return EventoEdgeComputing(
        id_evento_edge_computing=10,
        id_dispositivo_iot=1,
        id_sensor=1,
        clasificacion_rf55=clasificacion_rf55,
        tipo_evento="ALERTA_GENERADA",
        fecha_captura=ts,
        fecha_procesamiento=ts,
        origen_dato="TIEMPO_REAL",
        estado_conectividad=True,
        variables_involucradas=variables,
        severidad="MODERADO",
        metadatos={},
    )
