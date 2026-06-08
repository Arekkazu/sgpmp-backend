"""Entidad de dominio ``Cuenta`` del contexto de identidad y acceso.

Representa el estado operativo y de seguridad de la cuenta de un usuario
(estado, intentos fallidos, bloqueos, tokens, verificación). Python puro,
independiente del ORM. Concentra las transiciones de estado y los contadores
de seguridad que antes vivían dispersos entre el repositorio y los use cases.
Se identifica por ``id_cuenta_usuario``.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import ClassVar, Optional


@dataclass(eq=False)
class Cuenta:
    """Cuenta de acceso de un usuario (relación 1:1 con :class:`Usuario`).

    Attributes:
        id_usuario: Usuario propietario de la cuenta.
        id_estado_cuenta: Estado actual (ver constantes ``ESTADO_*``).
        tiene_correo_verificado: Si el correo fue verificado.
        intentos_fallidos: Contador de intentos de login fallidos consecutivos.
        fecha_verificacion: Cuándo se verificó el correo, o ``None``.
        ultimo_acceso: Último login exitoso, o ``None``.
        bloqueado_hasta: Hasta cuándo está bloqueada por seguridad, o ``None``.
        ultimo_intento_fallido: Marca del último intento fallido, o ``None``.
        token_activacion_actual: Token vigente de activación o recuperación, o ``None``.
        fecha_cambio_estado: Marca del último cambio de estado/token.
        motivo_ultimo_cambio: Justificación del último cambio de estado, o ``None``.
        id_cuenta_usuario: Identidad de la cuenta. ``None`` hasta que se persiste.
    """

    ESTADO_PENDIENTE: ClassVar[int] = 1
    ESTADO_ACTIVO: ClassVar[int] = 2
    ESTADO_INACTIVO: ClassVar[int] = 3
    ESTADO_BLOQUEADO: ClassVar[int] = 4
    ESTADO_ELIMINADO: ClassVar[int] = 5

    TOKEN_EXPIRACION_HORAS: ClassVar[int] = 24
    MINUTOS_BLOQUEO_LOGIN: ClassVar[int] = 15
    MINUTOS_BLOQUEO_CONTRASENA: ClassVar[int] = 30

    id_usuario: int
    id_estado_cuenta: int
    tiene_correo_verificado: bool = False
    intentos_fallidos: int = 0
    fecha_verificacion: Optional[datetime] = None
    ultimo_acceso: Optional[datetime] = None
    bloqueado_hasta: Optional[datetime] = None
    ultimo_intento_fallido: Optional[datetime] = None
    token_activacion_actual: Optional[str] = None
    fecha_cambio_estado: Optional[datetime] = None
    motivo_ultimo_cambio: Optional[str] = None
    id_cuenta_usuario: Optional[int] = None

    # ── Consultas de estado ─────────────────────────────────────────────────
    def esta_activa(self) -> bool:
        return self.id_estado_cuenta == self.ESTADO_ACTIVO

    def esta_pendiente(self) -> bool:
        return self.id_estado_cuenta == self.ESTADO_PENDIENTE

    def esta_bloqueada(self) -> bool:
        return self.id_estado_cuenta == self.ESTADO_BLOQUEADO

    # ── Activación / tokens ─────────────────────────────────────────────────
    def expiracion_token(self, horas: Optional[int] = None) -> datetime:
        """Calcula el instante en que expira el token vigente.

        Args:
            horas: Ventana de validez. Por defecto :data:`TOKEN_EXPIRACION_HORAS`.

        Returns:
            Marca temporal (UTC) de expiración, basada en ``fecha_cambio_estado``.
        """
        horas = self.TOKEN_EXPIRACION_HORAS if horas is None else horas
        base = self.fecha_cambio_estado
        if base is not None and base.tzinfo is None:
            base = base.replace(tzinfo=timezone.utc)
        return base + timedelta(hours=horas)

    def token_expirado(self, ahora: datetime, horas: Optional[int] = None) -> bool:
        """Indica si el token de activación ya expiró respecto a ``ahora``."""
        return ahora > self.expiracion_token(horas)

    def activar(self, ahora: datetime) -> None:
        """Marca la cuenta como activa y consume el token de activación."""
        self.id_estado_cuenta = self.ESTADO_ACTIVO
        self.tiene_correo_verificado = True
        self.fecha_verificacion = ahora
        self.token_activacion_actual = None
        self.fecha_cambio_estado = ahora

    def asignar_token_activacion(self, token: str, ahora: datetime) -> None:
        """Asigna un nuevo token de activación (reenvío)."""
        self.token_activacion_actual = token
        self.fecha_cambio_estado = ahora

    def asignar_token_recuperacion(self, token: str, ahora: datetime) -> None:
        """Asigna un token de recuperación de contraseña (misma columna que activación)."""
        self.token_activacion_actual = token
        self.fecha_cambio_estado = ahora

    def poner_pendiente(self, token: str, ahora: datetime) -> None:
        """Pasa la cuenta a PENDIENTE con un nuevo token (reverificación de correo)."""
        self.id_estado_cuenta = self.ESTADO_PENDIENTE
        self.token_activacion_actual = token
        self.fecha_cambio_estado = ahora

    # ── Contadores de seguridad (login) ─────────────────────────────────────
    def incrementar_intentos(self, ahora: datetime) -> None:
        self.intentos_fallidos += 1
        self.ultimo_intento_fallido = ahora

    def bloquear(self, ahora: datetime, minutos: Optional[int] = None) -> None:
        """Bloquea la cuenta por exceso de intentos de login."""
        minutos = self.MINUTOS_BLOQUEO_LOGIN if minutos is None else minutos
        self.id_estado_cuenta = self.ESTADO_BLOQUEADO
        self.bloqueado_hasta = ahora + timedelta(minutes=minutos)

    def desbloquear(self) -> None:
        """Reactiva una cuenta cuyo bloqueo temporal ya expiró."""
        self.id_estado_cuenta = self.ESTADO_ACTIVO

    def resetear_intentos(self) -> None:
        self.intentos_fallidos = 0
        self.ultimo_intento_fallido = None

    def registrar_acceso(self, ahora: datetime) -> None:
        self.ultimo_acceso = ahora

    # ── Contadores de seguridad (cambio de contraseña) ──────────────────────
    def bloquear_cambio_contrasena(self, ahora: datetime, minutos: Optional[int] = None) -> None:
        minutos = self.MINUTOS_BLOQUEO_CONTRASENA if minutos is None else minutos
        self.bloqueado_hasta = ahora + timedelta(minutes=minutos)

    def resetear_cambio_contrasena(self) -> None:
        self.intentos_fallidos = 0
        self.ultimo_intento_fallido = None
        self.bloqueado_hasta = None

    # ── Gestión administrativa ──────────────────────────────────────────────
    def cambiar_estado(self, nuevo_estado: int, motivo: str) -> None:
        """Aplica un cambio de estado administrativo con su motivo."""
        self.id_estado_cuenta = nuevo_estado
        self.motivo_ultimo_cambio = motivo

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Cuenta):
            return NotImplemented
        if self.id_cuenta_usuario is None or other.id_cuenta_usuario is None:
            return self is other
        return self.id_cuenta_usuario == other.id_cuenta_usuario

    def __hash__(self) -> int:
        return hash(self.id_cuenta_usuario)
