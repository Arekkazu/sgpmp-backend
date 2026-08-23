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
    # Consultas de auditoría, usuarios y perfil propio.
    16: EventoCategoria.CONSULTA,
    17: EventoCategoria.CONSULTA,
    18: EventoCategoria.CONSULTA,
    19: EventoCategoria.CONSULTA,
}


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
