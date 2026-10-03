"""Stub de ``EdgeSincronizacionPort`` — INC-M09-104-G29 (RF-17).

El broker MQTT real (``BROKER-MQTT-SGPMP``, ver ``MqttHttpAdapter``) expone
hoy un contrato pensado para comandos a un dispositivo por su serial
(``POST /v1/commands`` con ``{"serial": ..., ...}``). Propagar un umbral por
(id_especie, id_variable_ambiental) a "el Nodo Edge correspondiente" requiere
que el equipo de IoT defina destino, topic, payload y mecánica de ACK/timeout
para este caso -- exactamente lo que pide la propia lista de acciones
requeridas del incidente. Hasta que exista ese contrato, este stub degrada
siempre a PENDIENTE, con el mismo espíritu de "nunca romper el flujo de
negocio" que ``MqttHttpAdapter`` usa cuando el broker real no está disponible.

Reemplazar por el adaptador real cuando el contrato de propagación de
umbrales esté definido (ver
anotaciones/modulo_9/inc_m09_104_g29_sincronizacion_edge_umbrales.md).
"""
from __future__ import annotations

from src.configuration.domain.repositories.edge_sincronizacion_port import EdgeSincronizacionPort
from src.configuration.domain.repositories.mqtt_port import ResultadoEnvioMqtt

_MENSAJE_SIN_CONTRATO = (
    "La propagación automática de umbrales hacia el Nodo Edge todavía no está "
    "disponible: el contrato de publicación (destino, topic, payload, ACK) "
    "está pendiente de definición con el equipo de IoT. La configuración "
    "quedó guardada y pendiente de sincronización."
)


class EdgeSincronizacionStubAdapter(EdgeSincronizacionPort):

    def propagar_umbral(self, id_especie: int, id_variable_ambiental: int, payload: dict) -> ResultadoEnvioMqtt:
        return ResultadoEnvioMqtt(estado="PENDIENTE", mensaje=_MENSAJE_SIN_CONTRATO)
