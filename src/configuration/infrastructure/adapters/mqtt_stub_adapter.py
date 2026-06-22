"""Stub del puerto MQTT para configuración remota de dispositivos IoT (RF-23).

Retorna siempre False (dispositivo offline) hasta que se integre el broker
MQTT real sobre LoRaWAN. El use case almacena la configuración como PENDIENTE.
"""
from src.configuration.domain.repositories.mqtt_port import MqttPort


class MqttStubAdapter(MqttPort):

    def enviar_configuracion(self, id_dispositivo_iot: int, payload: dict) -> bool:
        return False
