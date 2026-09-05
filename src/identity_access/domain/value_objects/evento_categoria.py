"""Categorías funcionales de los eventos de auditoría del Módulo 1.

La categoría se deriva del tipo de evento en un único punto del dominio. De
esta forma, los casos de uso solo indican qué ocurrió y no pueden asignar una
categoría distinta para el mismo tipo de evento.
"""
from __future__ import annotations

from enum import Enum


class EventoCategoria(str, Enum):
    """Categorías admitidas por el historial de auditoría."""

    AUTENTICACION = "AUTENTICACION"
    MODIFICACION = "MODIFICACION"
    CONSULTA = "CONSULTA"


_CATEGORIA_POR_TIPO_EVENTO: dict[int, EventoCategoria] = {
    # Registro, activación, sesiones y contraseñas.
    1: EventoCategoria.AUTENTICACION,
    2: EventoCategoria.AUTENTICACION,
    3: EventoCategoria.AUTENTICACION,
    4: EventoCategoria.AUTENTICACION,
    5: EventoCategoria.AUTENTICACION,
    6: EventoCategoria.AUTENTICACION,
    7: EventoCategoria.AUTENTICACION,
    8: EventoCategoria.AUTENTICACION,
    # Autenticación y aprovisionamiento mediante AgroFusion/SSO.
    20: EventoCategoria.AUTENTICACION,
    21: EventoCategoria.AUTENTICACION,
    22: EventoCategoria.AUTENTICACION,
    # Rotación y protección del refresh token.
    23: EventoCategoria.AUTENTICACION,
    24: EventoCategoria.AUTENTICACION,
    # Perfil, estado de cuenta, roles y permisos.
    9: EventoCategoria.MODIFICACION,
    10: EventoCategoria.MODIFICACION,
    11: EventoCategoria.MODIFICACION,
    12: EventoCategoria.MODIFICACION,
    13: EventoCategoria.MODIFICACION,
    14: EventoCategoria.MODIFICACION,
    15: EventoCategoria.MODIFICACION,
    # Fallo del proceso automático de retención de auditoría (RF-10). No es una
    # consulta ni una autenticación: el proceso actúa sobre el propio almacén de
    # auditoría, así que se clasifica como MODIFICACION.
    25: EventoCategoria.MODIFICACION,
    # Consultas de auditoría, usuarios y perfil propio.
    16: EventoCategoria.CONSULTA,
    17: EventoCategoria.CONSULTA,
    18: EventoCategoria.CONSULTA,
    19: EventoCategoria.CONSULTA,
    # Exportación del historial (RF-10). Lee el log, igual que una consulta, pero
    # con tipo propio para poder responder "quién se llevó la auditoría" sin
    # rebuscar dentro del JSON de `detalle`.
    26: EventoCategoria.CONSULTA,
}


# Espejo de `modulo1.tipos_eventos.nombre`. El código ya referencia los tipos por
# número en todos lados; tener el nombre aquí permite decir qué operación se
# canceló cuando falla la auditoría obligatoria, sin una consulta extra a la DB
# justo cuando la DB es lo que está fallando.
# `test_nombres_de_tipo_evento_coinciden_con_el_catalogo` vigila que no derive.
_NOMBRE_POR_TIPO_EVENTO: dict[int, str] = {
    1: "REGISTRO_USUARIO",
    2: "ACTIVACION_CUENTA",
    3: "LOGIN_EXITOSO",
    4: "LOGIN_FALLIDO",
    5: "CIERRE_SESION",
    6: "CAMBIO_CONTRASENA",
    7: "SOLICITUD_RECUPERACION",
    8: "RESTABLECIMIENTO_CONTRASENA",
    9: "ACTUALIZACION_PERFIL",
    10: "CAMBIO_ESTADO_CUENTA",
    11: "CREACION_ROL",
    12: "MODIFICACION_ROL",
    13: "ELIMINACION_ROL",
    14: "ASIGNACION_PERMISO",
    15: "REVOCACION_PERMISO",
    16: "CONSULTA_AUDITORIA",
    17: "CONSULTA_LISTA_USUARIOS",
    18: "CONSULTA_DETALLE_USUARIO",
    19: "CONSULTA_PERFIL_PROPIO",
    20: "LOGIN_SSO_EXITOSO",
    21: "PROVISION_SSO_MINIMA",
    22: "PROVISION_AGROFUSION_SYNC",
    23: "REFRESH_TOKEN_ROTADO",
    24: "REUSO_TOKEN_REFRESCO_DETECTADO",
    25: "FALLO_ARCHIVADO_AUDITORIA",
    26: "EXPORTACION_AUDITORIA",
}


def nombre_para_tipo_evento(tipo_evento: int) -> str:
    """Nombre legible del tipo de evento, o un marcador si no está catalogado."""
    return _NOMBRE_POR_TIPO_EVENTO.get(tipo_evento, f"TIPO_EVENTO_{tipo_evento}")


def categoria_para_tipo_evento(tipo_evento: int) -> EventoCategoria:
    """Obtiene la categoría configurada para un tipo de evento conocido.

    Los tipos desconocidos se rechazan para evitar volver a guardar una
    categoría por defecto que oculte un catálogo incompleto.
    """
    try:
        return _CATEGORIA_POR_TIPO_EVENTO[tipo_evento]
    except KeyError as exc:
        raise ValueError(
            f"El tipo de evento {tipo_evento} no tiene una categoría configurada."
        ) from exc


def tipos_evento_para_categoria(categoria: EventoCategoria) -> tuple[int, ...]:
    """Retorna los tipos de evento pertenecientes a una categoría."""
    return tuple(
        tipo_evento
        for tipo_evento, categoria_configurada in _CATEGORIA_POR_TIPO_EVENTO.items()
        if categoria_configurada == categoria
    )
