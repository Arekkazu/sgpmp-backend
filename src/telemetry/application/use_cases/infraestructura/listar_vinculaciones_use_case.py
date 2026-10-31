from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from src.shared.errors import ValidationError
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
        *,
        ids_fincas_permitidas: Optional[list[int]] = None,
        modelo_manejo: Optional[str] = None,
    ) -> Tuple[List[VinculacionLectura], int]:
        # CP84: un rango invertido devolvía 0 vinculaciones sin decir por qué.
        if fecha_desde and fecha_hasta and fecha_desde > fecha_hasta:
            raise ValidationError(
                code='RANGO_FECHAS_INVALIDO',
                message='fecha_desde no puede ser posterior a fecha_hasta.',
                field='fecha_desde',
            )
        return self.vinculacion_repo.listar(
            id_telemetria=id_telemetria,
            estado_vinculacion=estado_vinculacion,
            mecanismo_vinculacion=mecanismo_vinculacion,
            id_infraestructura=id_infraestructura,
            fecha_desde=fecha_desde,
            fecha_hasta=fecha_hasta,
            pagina=pagina,
            por_pagina=por_pagina,
            ids_fincas_permitidas=ids_fincas_permitidas,
            modelo_manejo=modelo_manejo,
        )
