# | Fecha      | Nombre  | Que se hizo |
# |------------|---------|-------------|
# | 2026-10-22 | Leandro | DEV-44 RF-48/61: puerto transaccional del traslado |
from typing import Protocol


class VinculacionTrasladoPort(Protocol):
    def procesar(self, *, id_activo, origen, destino, fecha_efectiva, id_movimiento, id_usuario):
        """Misma transaccion RF-48; sin commits ni reasignar lecturas anteriores."""
        ...
