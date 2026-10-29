# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-20 | Arekkazu | DEV-32 RF-57: puerto de notificación de alertas (destinatarios, envío, reintento) |
"""Puerto de notificación de alertas de RF-57 (Fase 8, E6, E7, E8, E10)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional


class NotificacionAlertaPort(ABC):

    @abstractmethod
    def destinatarios(self, id_infraestructura: Optional[int], *, escalamiento: bool) -> list[int]:
        """Usuarios vinculados a la finca del área cuyo rol puede leer las alertas operativas
        o, con ``escalamiento``, descartarlas (Veterinario y Administrador tras DB-08).
        Sin roles quemados: sale de ``modulo1.permisos``."""

    @abstractmethod
    def administradores(self) -> list[int]:
        """Usuarios con el rol protegido (Administrador), sin importar la finca."""

    @abstractmethod
    def enviar(self, id_usuario: int, titulo: str, cuerpo: str, *, agrupable: bool) -> Optional[bool]:
        """Bandeja + push + correo por el canal de RF-14. ``agrupable`` aplica la ventana
        anti-spam (LEVE/MODERADO); CRITICO nunca se agrupa. Devuelve ``False`` si el correo
        se intentó y falló (E7), ``True`` si salió y ``None`` si no se intentó."""

    @abstractmethod
    def reintentar_fallidas(self, ahora: datetime) -> int:
        """E7: reintenta los correos de alerta fallidos con backoff. Devuelve cuántos salieron."""
