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
        correo_electronico: Correo electrónico.
        fecha_registro: Marca temporal de creación.
        nombre_rol: Nombre del rol asignado (resuelto desde ``roles``).
        version: Contador de concurrencia optimista del registro.
        nombre: Nombre(s) del usuario. ``None`` en cuentas SSO mínimas
            (``Pendiente Datos``) que aún no completaron su perfil.
        apellidos: Apellido(s) del usuario. Mismo caso ``None`` que ``nombre``.
        tipo_identificacion: Tipo de documento. Mismo caso ``None`` que ``nombre``.
        numero_identificacion: Número de documento, sin enmascarar (el use case
            decide si lo enmascara según los permisos del actor). Mismo caso
            ``None`` que ``nombre``.
        fecha_nacimiento: Fecha de nacimiento. Mismo caso ``None`` que ``nombre``.
        estado_cuenta: Nombre del estado de la cuenta, o ``None`` si no tiene cuenta.
    """

    id_usuario: int
    correo_electronico: str
    fecha_registro: datetime
    nombre_rol: str
    version: int
    nombre: Optional[str] = None
    apellidos: Optional[str] = None
    tipo_identificacion: Optional[str] = None
    numero_identificacion: Optional[str] = None
    fecha_nacimiento: Optional[date] = None
    estado_cuenta: Optional[str] = None
