"""Entidad de dominio ``Usuario`` del contexto de identidad y acceso.

A diferencia del modelo ORM (``infrastructure/models/usuarios_model.py``), esta
clase es Python puro: no sabe nada de SQLAlchemy ni de tablas. Representa el
*concepto de negocio* "usuario" y concentra las reglas y cálculos propios de
ese concepto (nombre completo, mayoría de edad, rol por defecto al registrarse).

Una entidad se identifica por su identidad (``id_usuario``), no por sus
atributos: dos instancias con el mismo ``id_usuario`` son el mismo usuario
aunque el resto de campos difiera. Esto contrasta con los *value objects*
(:class:`Email`, :class:`Contrasena`), que se comparan por valor.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import ClassVar, Optional

from src.identity_access.domain.value_objects.contrasena import Contrasena
from src.identity_access.domain.value_objects.email import Email
from src.identity_access.domain.value_objects.identificacion import (
    identificacion_valida,
    mensaje_identificacion_invalida,
)
from src.shared.errors import ValidationError


@dataclass(eq=False)
class Usuario:
    """Usuario registrado en el sistema.

    Attributes:
        correo: Correo electrónico validado (value object).
        contrasena: Contraseña representada por su hash (value object).
        nombre: Nombre(s) del usuario. ``None`` solo en una cuenta provista vía
            SSO de AgroFusion sin datos completos (ver :meth:`crear_minimo_sso`).
        apellidos: Apellido(s) del usuario. Mismo caso ``None`` que ``nombre``.
        fecha_nacimiento: Fecha de nacimiento, base del cálculo de edad. Mismo
            caso ``None`` que ``nombre``.
        genero: Género como texto (``.value`` del enum de género). Mismo caso
            ``None`` que ``nombre``.
        tipo_identificacion: Tipo de documento (``CC``, ``CE``, ``Pasaporte``).
            Mismo caso ``None`` que ``nombre``.
        numero_identificacion: Número de documento, único en el sistema.
            Mismo caso ``None`` que ``nombre``.
        id_rol: Rol asignado. Por defecto productor al registrarse.
        id_usuario: Identidad del usuario. ``None`` hasta que se persiste.
        telefono: Teléfono de contacto opcional.
        direccion: Dirección física opcional.
        version: Contador de concurrencia optimista.
        fecha_registro: Marca temporal de creación (la asigna la base de datos).
    """

    EDAD_MINIMA: ClassVar[int] = 18
    ROL_PRODUCTOR: ClassVar[int] = 2

    correo: Email
    contrasena: Contrasena
    nombre: Optional[str]
    apellidos: Optional[str]
    fecha_nacimiento: Optional[date]
    genero: Optional[str]
    tipo_identificacion: Optional[str]
    numero_identificacion: Optional[str]
    id_rol: int
    id_usuario: Optional[int] = None
    telefono: Optional[str] = None
    direccion: Optional[str] = None
    version: int = 1
    fecha_registro: Optional[datetime] = None

    @classmethod
    def registrar_nuevo(
        cls,
        *,
        correo: Email,
        contrasena: Contrasena,
        nombre: str,
        apellidos: str,
        fecha_nacimiento: date,
        genero: str,
        tipo_identificacion: str,
        numero_identificacion: str,
        telefono: Optional[str] = None,
        direccion: Optional[str] = None,
        id_rol: Optional[int] = None,
    ) -> "Usuario":
        """Crea un usuario nuevo, aún sin persistir.

        Encapsula las invariantes del alta: sin identidad asignada
        (``id_usuario=None``), versión inicial 1 y rol productor por defecto.

        Args:
            id_rol: Rol a asignar. Si es ``None`` (caso normal de autorregistro)
                usa :data:`ROL_PRODUCTOR`. Lo pasa explícito la sincronización
                server-to-server de AgroFusion, que ya resuelve el rol destino.

        Returns:
            Una nueva instancia de :class:`Usuario` lista para validar y guardar.
        """
        if not identificacion_valida(tipo_identificacion, numero_identificacion):
            raise ValidationError(
                code="NUMERO_IDENTIFICACION_INVALIDO",
                message=mensaje_identificacion_invalida(tipo_identificacion),
                field="numero_identificacion",
            )

        return cls(
            correo=correo,
            contrasena=contrasena,
            nombre=nombre,
            apellidos=apellidos,
            fecha_nacimiento=fecha_nacimiento,
            genero=genero,
            tipo_identificacion=tipo_identificacion,
            numero_identificacion=numero_identificacion,
            id_rol=id_rol if id_rol is not None else cls.ROL_PRODUCTOR,
            telefono=telefono,
            direccion=direccion,
        )

    @classmethod
    def crear_minimo_sso(
        cls,
        *,
        correo: Email,
        contrasena: Contrasena,
        id_rol: int,
    ) -> "Usuario":
        """Crea un usuario mínimo a partir de un handoff SSO de AgroFusion.

        El payload RS256 del Mecanismo A solo trae ``sub``+``email`` — no hay
        nombre, apellidos ni documento de identidad para poblar. En vez de
        inventar esos datos, la entidad queda deliberadamente incompleta
        (``None`` en los 6 campos personales) hasta que el propio usuario los
        complete vía :class:`EditarPerfilUseCase` (que transiciona la cuenta
        de ``PENDIENTE_DATOS`` a ``ACTIVO`` cuando ya están todos presentes).

        Args:
            correo: Correo verificado por AgroFusion.
            contrasena: Hash de un secreto aleatorio inutilizable (la cuenta no
                tiene contraseña propia hasta que el usuario la fije).
            id_rol: Rol de mínimo privilegio para cuentas SSO sin sincronizar.

        Returns:
            Una nueva instancia de :class:`Usuario` lista para guardar.
        """
        return cls(
            correo=correo,
            contrasena=contrasena,
            nombre=None,
            apellidos=None,
            fecha_nacimiento=None,
            genero=None,
            tipo_identificacion=None,
            numero_identificacion=None,
            id_rol=id_rol,
        )

    def cambiar_contrasena(self, nueva: Contrasena) -> None:
        """Reemplaza la contraseña del usuario por una nueva ya cifrada.

        Args:
            nueva: Value object :class:`Contrasena` con el nuevo hash. La
                validación de política y el cifrado son responsabilidad de quien
                construye la contraseña (DTO + :meth:`Contrasena.cifrar`).
        """
        self.contrasena = nueva

    def nombre_completo(self) -> str:
        """Devuelve el nombre y los apellidos concatenados."""
        return f"{self.nombre} {self.apellidos}"

    def edad(self, hoy: Optional[date] = None) -> int:
        """Calcula la edad en años cumplidos.

        Args:
            hoy: Fecha de referencia. Si es ``None`` usa la fecha actual.

        Returns:
            Edad en años cumplidos.
        """
        hoy = hoy or date.today()
        return hoy.year - self.fecha_nacimiento.year - (
            (hoy.month, hoy.day) < (self.fecha_nacimiento.month, self.fecha_nacimiento.day)
        )

    def es_mayor_de_edad(self, hoy: Optional[date] = None) -> bool:
        """Indica si el usuario alcanza la edad mínima para registrarse.

        Args:
            hoy: Fecha de referencia. Si es ``None`` usa la fecha actual.

        Returns:
            ``True`` si tiene al menos :data:`EDAD_MINIMA` años.
        """
        return self.edad(hoy) >= self.EDAD_MINIMA

    def __eq__(self, other: object) -> bool:
        # Igualdad por identidad: mismo id_usuario => mismo usuario. Dos usuarios
        # sin persistir (id None) solo son iguales si son el mismo objeto.
        if not isinstance(other, Usuario):
            return NotImplemented
        if self.id_usuario is None or other.id_usuario is None:
            return self is other
        return self.id_usuario == other.id_usuario

    def __hash__(self) -> int:
        return hash(self.id_usuario)
