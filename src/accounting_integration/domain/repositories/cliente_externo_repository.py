# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-06 | Arekkazu | M07 RF-101: puerto de clientes externos y credenciales |
"""Puerto de clientes externos (RF-101 v2.0)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from src.accounting_integration.domain.entities.cliente_externo import ClienteExterno, Credencial


class ClienteExternoRepository(ABC):
    @abstractmethod
    def obtener(self, id_cliente_externo: int) -> Optional[ClienteExterno]: ...

    @abstractmethod
    def obtener_por_identificador(self, identificador_publico: str) -> Optional[ClienteExterno]: ...

    @abstractmethod
    def listar(self) -> list[ClienteExterno]: ...

    @abstractmethod
    def guardar(self, cliente: ClienteExterno) -> ClienteExterno:
        """Inserta o actualiza el cliente y reemplaza sus canales."""

    @abstractmethod
    def credencial_activa(self, id_cliente_externo: int) -> Optional[Credencial]: ...

    @abstractmethod
    def reemplazar_credencial(self, id_cliente_externo: int, credencial: Credencial) -> None:
        """Revoca la credencial activa (si hay) y registra la nueva en la misma transacción."""
