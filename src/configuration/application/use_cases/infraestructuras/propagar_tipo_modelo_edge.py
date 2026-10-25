"""Paso post-commit de crear y editar área: enviar el ``tipo_modelo_asignado`` al Gateway Edge (DEV-10).

M09·RF-20, D-06 de AIOT-DEV-03 §3 D7: cuando un área se crea con modelo o
cambia su ``tipo_modelo_asignado``, se envía a los Gateway Edge del área por el
broker con ``origen: "tipo_modelo"`` (BRK-05: ``tipo_comando =
TIPO_MODELO_ASIGNADO``, confirmación ``ACK_TIPO_MODELO``). El nodo reinicia su
módulo de procesamiento con el esquema nuevo y conserva la calibración activa.

El área ya quedó guardada: el resultado no cambia la respuesta HTTP. Queda en
la bitácora IoT (RF-63) como ``PROPAGACION_TIPO_MODELO_EDGE``, un evento por
Gateway sobre la entidad DISPOSITIVO, consultable en
``GET /iot/auditoria?tipo_evento=PROPAGACION_TIPO_MODELO_EDGE``.

Sin Gateway Edge en el área (un área recién creada todavía no tiene
dispositivos) no hay a quién enviarlo ni evento que registrar. Un modelo que se
quita (``None``) tampoco se envía: el comando exige un ``tipo_modelo_asignado``.
"""
from __future__ import annotations

import time

from src.configuration.domain.entities.infraestructura import Infraestructura
from src.configuration.domain.repositories.bitacora_iot_port import BitacoraIotPort
from src.configuration.domain.repositories.destino_edge_repository import DestinoEdgeRepository
from src.configuration.domain.repositories.edge_sincronizacion_port import EdgeSincronizacionPort

EVENTO_PROPAGACION_TIPO_MODELO = "PROPAGACION_TIPO_MODELO_EDGE"


def payload_tipo_modelo(infra: Infraestructura) -> dict:
    """Cuerpo del comando ``origen: "tipo_modelo"`` del broker (sin ``origen``/``serial``)."""
    return {
        "id_infraestructura": infra.id_infraestructura,
        "tipo_modelo_asignado": infra.tipo_modelo_asignado,
    }


class PropagadorTipoModeloEdge:

    def __init__(
        self,
        destino_repo: DestinoEdgeRepository,
        edge_port: EdgeSincronizacionPort,
        bitacora: BitacoraIotPort,
    ) -> None:
        self.destino_repo = destino_repo
        self.edge_port = edge_port
        self.bitacora = bitacora

    def propagar(self, infra: Infraestructura, id_usuario: int) -> None:
        """Envía el modelo del área (ya confirmada en BD) a sus Gateway y registra cada resultado."""
        if not infra.tipo_modelo_asignado:
            return
        gateways = self.destino_repo.listar_gateways_por_infraestructura(infra.id_infraestructura)
        if not gateways:
            return

        inicio = time.monotonic()
        resultados = self.edge_port.propagar_tipo_modelo(
            [g.serial for g in gateways], payload_tipo_modelo(infra)
        )
        duracion_ms = round((time.monotonic() - inicio) * 1000)

        for gateway in gateways:
            resultado = resultados[gateway.serial]
            self.bitacora.registrar_propagacion_tipo_modelo(
                evento=EVENTO_PROPAGACION_TIPO_MODELO,
                id_dispositivo_iot=gateway.id_dispositivo_iot,
                serial=gateway.serial,
                id_infraestructura=infra.id_infraestructura,
                id_usuario=id_usuario,
                estado=resultado.estado,
                detalle={
                    "tipo_modelo_asignado": infra.tipo_modelo_asignado,
                    "publicado": resultado.publicado,
                    # El broker solo responde APLICADA cuando llegó el ACK_TIPO_MODELO.
                    "ack_tipo_modelo": resultado.estado == "APLICADA",
                    "mensaje": resultado.mensaje,
                    "duracion_ms": duracion_ms,
                },
            )
