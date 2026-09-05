"""Puerto de alcance de activos por usuario/rol (RF-81, restricción de Gestor de Granja).

No existe en el sistema (ningún schema) un modelo real de "unidad productiva
asignada a un usuario" — ver ``cu04_gaps_bd_rf77_rf81.md``. Este puerto aísla
esa deuda: toda la lógica condicional por rol vive únicamente en su
implementación de infraestructura (``AlcanceActivoM02Adapter``), nunca en el
use case ni en el router.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional


class AlcanceActivoPort(ABC):
    @abstractmethod
    def listar_ids_activos_permitidos(self, id_usuario: int, id_rol: int) -> Optional[list[int]]:
        """``None`` si el rol no tiene restricción de alcance (ve todos los activos).

        Una lista (posiblemente vacía) con los ``id_activo_biologico`` a los
        que el usuario tiene acceso, si el rol sí está restringido.
        """
        raise NotImplementedError
