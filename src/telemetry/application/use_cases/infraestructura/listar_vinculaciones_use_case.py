from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from src.telemetry.domain.entities.vinculacion_lectura import VinculacionLectura
from src.telemetry.domain.repositories.vinculacion_lectura_repository import VinculacionLecturaRepository


class ListarVinculacionesUseCase:

    def __init__(self, db: Session, vinculacion_repo: VinculacionLecturaRepository) -> None:
        self.db = db
        self.vinculacion_repo = vinculacion_repo

    def execute(
        self,
        id_telemetria: Optional[int] = None,
        estado_vinculacion: Optional[str] = None,
        mecanismo_vinculacion: Optional[str] = None,
        id_infraestructura: Optional[int] = None,
        fecha_desde: Optional[datetime] = None,
        fecha_hasta: Optional[datetime] = None,
        pagina: int = 1,
        por_pagina: int = 50,
    ) -> Tuple[List[VinculacionLectura], int]:
        return self.vinculacion_repo.listar(
            id_telemetria=id_telemetria,
            estado_vinculacion=estado_vinculacion,
            mecanismo_vinculacion=mecanismo_vinculacion,
            id_infraestructura=id_infraestructura,
            fecha_desde=fecha_desde,
            fecha_hasta=fecha_hasta,
            pagina=pagina,
            por_pagina=por_pagina,
        )
