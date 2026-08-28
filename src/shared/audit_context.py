"""Contexto por request para la auditoría de RF-10.

RF-10 exige que **cada** registro de auditoría almacene la IP, el user-agent y la
sesión del actor. Pasar esos datos a mano desde cada router hasta cada
``registrar()`` obligaría a tocar los 29 puntos de registro y a no olvidar
ninguno en el futuro.

En vez de eso, el middleware deposita el origen de la petición aquí y
``SqlAlchemyEventoRepository.registrar`` lo lee como valor por defecto. Un caso
de uso que ya conozca el dato (por ejemplo el login, que recibe la IP explícita)
lo sigue pasando y tiene prioridad.

Se usa ``contextvars`` y no una variable global porque el valor debe ser propio
de cada request, incluidas las que corren en hilos distintos.

La variable guarda un objeto **mutable** a propósito. FastAPI ejecuta las
dependencias síncronas —como ``get_current_user``— en un threadpool con una
*copia* del contexto, así que un ``ContextVar.set()`` hecho ahí se perdería al
volver. Mutar un objeto ya enlazado sí se ve desde fuera, porque la copia del
contexto comparte la misma referencia.
"""
from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
from typing import Optional

LARGO_MAX_IP = 45
LARGO_MAX_USER_AGENT = 255


@dataclass
class OrigenPeticion:
    """Datos de origen del request en curso, para adjuntar a la auditoría."""

    ip: Optional[str] = None
    user_agent: Optional[str] = None
    id_token: Optional[int] = None


_origen: ContextVar[OrigenPeticion] = ContextVar("auditoria_origen")


def iniciar_request(ip: Optional[str], user_agent: Optional[str]) -> OrigenPeticion:
    """Abre el contexto del request con su IP y user-agent, truncados a columna."""
    origen = OrigenPeticion(
        ip=ip[:LARGO_MAX_IP] if ip else None,
        user_agent=user_agent[:LARGO_MAX_USER_AGENT] if user_agent else None,
    )
    _origen.set(origen)
    return origen


def establecer_id_token(id_token: Optional[int]) -> None:
    """Registra el token de acceso del request, del que se deriva la sesión.

    Muta el objeto en vez de reenlazar la variable, para que el valor sobreviva
    aunque se escriba desde el threadpool de una dependencia síncrona.
    """
    origen = _origen.get(None)
    if origen is not None:
        origen.id_token = id_token


def obtener_origen() -> OrigenPeticion:
    """Retorna el origen del request actual; vacío fuera de un request."""
    return _origen.get(None) or OrigenPeticion()


def limpiar() -> None:
    """Cierra el contexto. Pensado para pruebas y tareas de fondo."""
    _origen.set(OrigenPeticion())
