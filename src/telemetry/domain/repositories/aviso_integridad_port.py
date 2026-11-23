# | Fecha      | Nombre  | Que se hizo |
# |------------|---------|-------------|
# | 2026-10-22 | Leandro | DEV-47 RF-63: delimita aviso interno de compromiso |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""El adaptador participa en la transacción del aviso, sin commits propios."""
from typing import Protocol


class AvisoIntegridadPort(Protocol):
    """Puerto para avisar incidentes de integridad de la bitácora de auditoría."""
    def notificar(self, id_incidente: str, ids_comprometidos: list[str]) -> int:
        """Devuelve destinatarios con aviso interno persistido; nunca simula entrega."""
        ...
