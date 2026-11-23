# | Fecha      | Nombre  | Que se hizo |
# |------------|---------|-------------|
# | 2026-10-22 | Leandro | DEV-44 RF-48/61: puerto transaccional del traslado |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Puerto para actualizar las vinculaciones de lecturas al trasladar un activo."""
from typing import Protocol


class VinculacionTrasladoPort(Protocol):
    """Puerto que procesa las vinculaciones de un traslado en su misma transacción."""
    def procesar(self, *, id_activo, origen, destino, fecha_efectiva, id_movimiento, id_usuario):
        """Misma transaccion RF-48; sin commits ni reasignar lecturas anteriores."""
        ...
