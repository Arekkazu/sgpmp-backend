"""Modelo de lectura ``UsuarioDetalle`` del contexto de identidad y acceso.

A diferencia de la entidad :class:`~src.identity_access.domain.entities.usuario.Usuario`
(el agregado, con conducta y reglas), este es un *modelo de lectura*: una
proyección plana e inmutable pensada para las consultas que necesitan datos ya
unidos de varias tablas (el nombre del rol y el nombre del estado de cuenta),
que el agregado puro no transporta.

Lo construye el repositorio a partir del grafo ORM (``usuarios`` + ``roles`` +
``cuentas_usuarios`` + ``estados_cuentas``) y lo consumen los use cases de
consulta de perfil, detalle y listado. No tiene conducta ni se persiste.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional


@dataclass(frozen=True)
class UsuarioDetalle:
    """Proyección de lectura de un usuario con su rol y estado de cuenta resueltos.

    Attributes:
        id_usuario: Identidad del usuario.
        nombre: Nombre(s) del usuario.
        apellidos: Apellido(s) del usuario.
        correo_electronico: Correo electrónico.
        tipo_identificacion: Tipo de documento.
        numero_identificacion: Número de documento, sin enmascarar (el use case
            decide si lo enmascara según los permisos del actor).
        fecha_nacimiento: Fecha de nacimiento.
        fecha_registro: Marca temporal de creación.
        nombre_rol: Nombre del rol asignado (resuelto desde ``roles``).
        estado_cuenta: Nombre del estado de la cuenta, o ``None`` si no tiene cuenta.
    """

    id_usuario: int
    nombre: str
    apellidos: str
    correo_electronico: str
    tipo_identificacion: str
    numero_identificacion: str
    fecha_nacimiento: date
    fecha_registro: datetime
    nombre_rol: str
    estado_cuenta: Optional[str] = None
