# | Fecha      | Nombre           | Que se hizo                                   |
# |------------|------------------|-----------------------------------------------|
# | 2026-10-22 | Arekkazu         | M05 RF-77: logo de la finca (RF-26, M09)      |
"""Adaptador de :class:`LogoInstitucionalPort` contra ``modulo9.identidad_visuales`` (RF-26).

Toma la versión más reciente de la identidad visual de la finca del activo o de
la infraestructura. El PDF solo embebe PNG/JPEG; un SVG o un archivo ausente
deja el encabezado sin logo.
"""
from __future__ import annotations

import os
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.shared.almacen_logos import DIRECTORIO_LOGOS, RUTA_PUBLICA_LOGOS
from src.supplies.domain.repositories.logo_institucional_port import LogoInstitucionalPort

_SQL_LOGO = text(
    """
    SELECT iv.logo_path
    FROM modulo9.identidad_visuales iv
    JOIN modulo9.infraestructuras i ON i.id_finca = iv.id_finca
    LEFT JOIN modulo2.activos_biologicos ab ON ab.id_infraestructura = i.id_infraestructura
    WHERE iv.logo_path IS NOT NULL
      AND (ab.id_activo_biologico = :id_activo OR (CAST(:id_activo AS integer) IS NULL AND i.id_infraestructura = :id_infra))
    ORDER BY iv.version DESC
    LIMIT 1
    """
)


class LogoFincaM09Adapter(LogoInstitucionalPort):
    def __init__(self, db: Session) -> None:
        self.db = db

    def ruta_logo(self, *, id_activo_biologico: Optional[int] = None,
                  id_infraestructura: Optional[int] = None) -> Optional[str]:
        if id_activo_biologico is None and id_infraestructura is None:
            return None
        logo = self.db.execute(
            _SQL_LOGO, {"id_activo": id_activo_biologico, "id_infra": id_infraestructura}
        ).scalar()
        if not logo or not logo.lower().endswith((".png", ".jpg", ".jpeg")):
            return None
        ruta = os.path.join(DIRECTORIO_LOGOS, logo.removeprefix(RUTA_PUBLICA_LOGOS).lstrip("/"))
        return ruta if os.path.isfile(ruta) else None
