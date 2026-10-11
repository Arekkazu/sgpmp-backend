"""Paso post-commit compartido por registrar y editar umbral: propagarlo al Nodo Edge (RF-17).

INC-M09-104-G29: el umbral ya quedó guardado (primer commit). Acá se resuelven
los Gateway Edge de las áreas de su especie, se le envía a cada uno, se
consolida un único estado de sincronización para el umbral y se persiste en un
segundo commit. Si la propagación se intentó y falló, RF-17 exige responder
500 -- después de haber persistido, para que el dato nunca se pierda.

Consolidación (un estado por umbral, no por Gateway):

| Resultados por Gateway                    | Estado     | Respuesta |
|-------------------------------------------|------------|-----------|
| todos APLICADA                            | APLICADA   | 201 / 200 |
| alguno NO_CONF (u otro estado)            | NO_CONF    | 500       |
| ninguno falló, alguno desconectado        | PENDIENTE  | 500       |
| la especie no tiene Gateway Edge          | PENDIENTE  | 201 / 200 |
| el ambiente no tiene broker configurado   | PENDIENTE  | 201 / 200 |

Un Edge desconectado (TC-M09-63) es el flujo alterno "Error de sincronización
con el Nodo Edge" de RF-17: el umbral queda "Pendiente de Sincronización", el
Edge sigue con el anterior y se responde 500. Solo no es un error cuando no
hubo a quién enviarlo o con qué (TC-M09-58-G22, #459: sin intento no hay
fallo que reportar). Con el Edge desconectado el broker no publica, así que
no hay reenvío automático al reconectar (igual que RF-23): el umbral se
propaga en la próxima edición.

INC-M09-70-G29: cada intento queda en la bitácora IoT (RF-63) como
``PROPAGACION_UMBRAL_EDGE`` sobre la entidad ``UMBRAL``, con el Gateway, si el
broker publicó, si hubo ``ACK_UMBRAL``, la causa y la duración. Se consulta en
``GET /iot/auditoria?tipo_evento=PROPAGACION_UMBRAL_EDGE&entidad_afectada_id=<id_umbral>``.
La última versión con ``ack_umbral`` de cada Gateway es la configuración que ese
Edge tiene vigente: el Edge solo confirma después de guardar ``umbrales.json``.
"""
from __future__ import annotations

import datetime
import time

from sqlalchemy.orm import Session

from src.configuration.domain.entities.umbral_ambiental import UmbralAmbiental
from src.configuration.domain.repositories.bitacora_iot_port import BitacoraIotPort
from src.configuration.domain.repositories.destino_edge_repository import DestinoEdgeRepository
from src.configuration.domain.repositories.edge_sincronizacion_port import (
    ESTADO_SIN_INTEGRACION,
    EdgeSincronizacionPort,
)
from src.configuration.domain.repositories.mqtt_port import ResultadoEnvioMqtt
from src.configuration.domain.repositories.umbral_ambiental_repository import UmbralAmbientalRepository
from src.shared.errors import InfrastructureError

EVENTO_PROPAGACION_UMBRAL = "PROPAGACION_UMBRAL_EDGE"

MENSAJE_FALLO_SINCRONIZACION_EDGE = (
    "Configuración guardada en la base de datos, pero falló la actualización de los "
    "nodos Edge. Es posible que las alertas en campo sigan operando con los valores "
    "anteriores hasta que se restablezca la conexión."
)

MOTIVO_SIN_GATEWAY_EDGE = (
    "Ningún Gateway Edge activo atiende las áreas de esta especie. El umbral quedó "
    "guardado y se propagará cuando se vuelva a editar con un Gateway asignado."
)


def payload_umbral(umbral: UmbralAmbiental, nombre_variable: str) -> dict:
    """Cuerpo del comando ``origen: "umbral"`` del broker (sin ``origen``/``serial``)."""
    return {
        'id_umbral_ambiental': umbral.id_umbral_ambiental,
        'version': umbral.fecha_actualizacion.isoformat() if umbral.fecha_actualizacion else None,
        'variable': nombre_variable,
        'unidad': umbral.unidad_medida,
        'valor_min': str(umbral.valor_min),
        'valor_max': str(umbral.valor_max),
        'niveles': [
            {
                'nivel': n.nivel.value,
                'limite_inferior': str(n.limite_inferior),
                'limite_superior': str(n.limite_superior),
            }
            for n in umbral.niveles
        ],
    }


def consolidar_resultados(resultados: dict[str, ResultadoEnvioMqtt]) -> ResultadoEnvioMqtt:
    """Un único estado para el umbral a partir del resultado de cada Gateway Edge."""
    if not resultados:
        return ResultadoEnvioMqtt(estado='PENDIENTE', mensaje=MOTIVO_SIN_GATEWAY_EDGE)
    if _sin_intento(resultados):
        return ResultadoEnvioMqtt(estado='PENDIENTE', mensaje=next(iter(resultados.values())).mensaje)

    fallidos = {
        s: r for s, r in resultados.items() if r.estado not in ('APLICADA', 'PENDIENTE')
    }
    if fallidos:
        return ResultadoEnvioMqtt(estado='NO_CONF', mensaje=_detalle(fallidos))

    pendientes = {s: r for s, r in resultados.items() if r.estado == 'PENDIENTE'}
    if pendientes:
        return ResultadoEnvioMqtt(estado='PENDIENTE', mensaje=_detalle(pendientes))

    return ResultadoEnvioMqtt(
        estado='APLICADA',
        mensaje=f"Confirmado por {len(resultados)} Gateway Edge.",
    )


def _sin_intento(resultados: dict[str, ResultadoEnvioMqtt]) -> bool:
    """No hubo a quién enviarlo (sin Gateway) ni con qué (sin broker): no es un error."""
    return all(r.estado == ESTADO_SIN_INTEGRACION for r in resultados.values())


def _detalle(resultados: dict[str, ResultadoEnvioMqtt]) -> str:
    return " | ".join(f"{serial}: {r.mensaje}" for serial, r in sorted(resultados.items()))


def sincronizar_umbral_con_edge(
    *,
    db: Session,
    umbral: UmbralAmbiental,
    nombre_variable: str,
    umbral_repo: UmbralAmbientalRepository,
    destino_repo: DestinoEdgeRepository,
    edge_port: EdgeSincronizacionPort,
    bitacora: BitacoraIotPort,
    id_usuario: int,
) -> UmbralAmbiental:
    """Propaga ``umbral`` (ya confirmado en BD), persiste el estado y lanza 500 si falló."""
    seriales = destino_repo.listar_seriales_gateway_por_especie(umbral.id_especie)
    payload = payload_umbral(umbral, nombre_variable)
    inicio = time.monotonic()
    resultados = edge_port.propagar_umbral(seriales, payload)
    duracion_ms = round((time.monotonic() - inicio) * 1000)
    resultado = consolidar_resultados(resultados)
    # RF-17, flujo alterno "Error de sincronización con el Nodo Edge": el umbral
    # ya quedó guardado, pero el cliente debe saber que en campo pueden seguir
    # operando los valores anteriores (Edge sin ACK o desconectado).
    fallo = resultado.estado != 'APLICADA' and not _sin_intento(resultados)

    if resultado.estado == 'APLICADA':
        umbral.marcar_sincronizado(datetime.datetime.now(datetime.timezone.utc))
    elif resultado.estado == 'PENDIENTE':
        umbral.marcar_pendiente_sincronizacion(resultado.mensaje)
    else:
        umbral.marcar_fallo_sincronizacion(resultado.mensaje)

    try:
        umbral = umbral_repo.actualizar_estado_sincronizacion(umbral)
        db.commit()
    except Exception:
        db.rollback()
        raise

    bitacora.registrar_propagacion_umbral(
        evento=EVENTO_PROPAGACION_UMBRAL,
        id_umbral_ambiental=umbral.id_umbral_ambiental,
        id_usuario=id_usuario,
        estado=resultado.estado,
        fallo=fallo,
        detalle={
            'version': payload['version'],
            'variable': nombre_variable,
            'motivo': resultado.mensaje,
            'duracion_ms': duracion_ms,
            'gateways': [
                {
                    'serial': serial,
                    'estado': r.estado,
                    'publicado': r.publicado,
                    # El broker solo responde APLICADA cuando llegó el ACK_UMBRAL.
                    'ack_umbral': r.estado == 'APLICADA',
                    'mensaje': r.mensaje,
                }
                for serial, r in sorted(resultados.items())
            ],
        },
    )

    if fallo:
        raise InfrastructureError(
            code='FALLO_SINCRONIZACION_EDGE',
            message=MENSAJE_FALLO_SINCRONIZACION_EDGE,
        )

    return umbral
