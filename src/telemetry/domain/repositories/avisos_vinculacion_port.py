# | Fecha      | Nombre  | Que se hizo |
# |------------|---------|-------------|
# | 2026-10-22 | Leandro | DEV-44 RF-61: contrato de avisos con clave idempotente |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Puerto de avisos de vinculaciones ambiguas o con configuración incompleta."""
from typing import Protocol


class AvisosVinculacionPort(Protocol):
    """Puerto para notificar problemas de vinculación lectura-activo."""
    def configuracion_incompleta(self, vinculacion, *, clave: str, destinatarios: list[int]) -> bool:
        """RF-57: severidad aprobada, deduplicacion y destinatarios autorizados."""
        ...

    def ambiguedad(self, vinculacion, *, clave: str, destinatarios: list[int]) -> bool:
        """Incluye candidatos y confirma entrega/registro segun contrato del canal."""
        ...
