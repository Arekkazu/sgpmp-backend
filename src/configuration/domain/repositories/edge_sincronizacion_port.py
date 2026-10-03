"""Puerto (ABC) para propagar umbrales ambientales hacia el Nodo Edge (RF-17).

INC-M09-104-G29: a diferencia de ``MqttPort`` (RF-23), que envía un comando a
UN dispositivo identificado por su serial, un umbral se define por
(id_especie, id_variable_ambiental) y no tiene una relación ya modelada en el
sistema hacia dispositivos/sensores concretos -- ver
``anotaciones/modulo_9/inc_m09_104_g29_sincronizacion_edge_umbrales.md``. Este
puerto registra un único intento de sincronización lógico por umbral, no uno
por dispositivo destino.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from src.configuration.domain.repositories.mqtt_port import ResultadoEnvioMqtt


class EdgeSincronizacionPort(ABC):

    @abstractmethod
    def propagar_umbral(self, id_especie: int, id_variable_ambiental: int, payload: dict) -> ResultadoEnvioMqtt:
        """Intenta propagar la configuración del umbral hacia el Nodo Edge.

        Nunca lanza -- el umbral ya quedó persistido antes de llamar acá. El
        ``estado`` devuelto decide la respuesta HTTP (TC-M09-58-G22, #459):

        - ``"APLICADA"``: el Edge confirmó. 201/200.
        - ``"PENDIENTE"``: la propagación no se intentó o quedó encolada (p. ej.
          aún no hay contrato de publicación). 201/200 con
          ``estado_sincronizacion=PENDIENTE``; no es un error.
        - ``"NO_CONF"``: se intentó y falló (broker caído, timeout, sin ACK). Es
          el "Error de sincronización con el Nodo Edge" de RF-17: 500.

        Un adaptador real NO debe devolver ``PENDIENTE`` ante un fallo de
        comunicación: ocultaría el 500 que el RF exige.
        """
        ...
