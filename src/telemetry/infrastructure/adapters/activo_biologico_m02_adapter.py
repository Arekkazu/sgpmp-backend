"""Adaptador real de M02 para la vinculación automática de lecturas (RF-61-A).

INC-M09-64-G31 (#494): reemplaza al stub que siempre devolvía ``[]``, por lo que
ninguna lectura nueva se vinculaba sola y RF-17 nunca clasificaba la ingesta.
"""
from datetime import datetime
from typing import List

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.telemetry.domain.repositories.activo_biologico_dependency_port import (
    ActivoBiologicoDependencyPort,
    ActivoBiologicoInfo,
)

# Activos que ocupan el área: los de estado operativo en M02 (ACTIVO, EN_TRATAMIENTO,
# AISLADO, los mismos que admiten eventos en RF-39). INACTIVO, CERRADO o BAJA no
# reciben lecturas (RF-61 E4). `tipo` es el modelo de manejo: el lote es el activo
# POBLACIONAL.
_SQL_ACTIVOS_EN_AREA = text(
    """
    SELECT id_activo_biologico, tipo::text AS modelo_manejo
    FROM modulo2.activos_biologicos
    WHERE id_infraestructura = :id_infraestructura
      AND id_estado IN (1, 3, 4)
    ORDER BY id_activo_biologico
    """
)


class ActivoBiologicoM02Adapter(ActivoBiologicoDependencyPort):

    def __init__(self, db: Session) -> None:
        self.db = db

    # ponytail: estado actual del área (Subcomponente A, alcance MVP de RF-61). Una
    # lectura de buffer con timestamp viejo se vincula a quien ocupa el área hoy; el
    # historial de ubicaciones (Subcomponente B) es Fase 2 de RF-61.
    def obtener_activos_en_momento(
        self, id_infraestructura: int, timestamp: datetime
    ) -> List[ActivoBiologicoInfo]:
        filas = self.db.execute(
            _SQL_ACTIVOS_EN_AREA, {'id_infraestructura': id_infraestructura}
        ).fetchall()
        return [ActivoBiologicoInfo(f.id_activo_biologico, f.modelo_manejo) for f in filas]
