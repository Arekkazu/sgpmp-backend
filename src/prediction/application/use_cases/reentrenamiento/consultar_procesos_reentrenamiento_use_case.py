# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-02 | Arekkazu | AJF-14 RF-71 BE-4: procesos de reentrenamiento para la pantalla |
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from src.prediction.domain.entities.proceso_reentrenamiento import ESTADOS_ABIERTOS, ESTADOS_FINALES, ProcesoReentrenamiento
from src.prediction.domain.repositories.proceso_reentrenamiento_repository import ProcesoReentrenamientoRepository
from src.shared.errors import NotFoundError, ValidationError

POR_PAGINA_MAXIMO = 100


class ConsultarProcesosReentrenamientoUseCase:
    """Solo lectura; la RLS limita a los animales de las fincas del usuario."""

    def __init__(self, procesos: ProcesoReentrenamientoRepository) -> None:
        self._procesos = procesos

    def listar(self, *, tipo_modelo: Optional[str] = None, id_activo_biologico: Optional[int] = None,
               estado: Optional[str] = None, desde: Optional[datetime] = None, hasta: Optional[datetime] = None,
               pagina: int = 1, por_pagina: int = 20) -> tuple[list[ProcesoReentrenamiento], int]:
        if estado is not None and estado not in ESTADOS_ABIERTOS | ESTADOS_FINALES:
            raise ValidationError("ESTADO_INVALIDO", f"estado debe ser uno de {sorted(ESTADOS_ABIERTOS | ESTADOS_FINALES)}.", field="estado")
        if pagina < 1 or not 1 <= por_pagina <= POR_PAGINA_MAXIMO:
            raise ValidationError("PAGINACION_INVALIDA", f"pagina ≥ 1 y por_pagina entre 1 y {POR_PAGINA_MAXIMO}.", field="por_pagina")
        if desde and hasta and desde > hasta:
            raise ValidationError("RANGO_FECHAS_INVALIDO", "La fecha de inicio no puede ser posterior a la de fin.", field="desde")
        return self._procesos.listar(tipo_modelo=tipo_modelo, id_activo_biologico=id_activo_biologico, estado=estado,
                                     desde=desde, hasta=hasta, pagina=pagina, por_pagina=por_pagina)

    def obtener(self, id_proceso: uuid.UUID) -> ProcesoReentrenamiento:
        proceso = self._procesos.obtener(id_proceso)
        if proceso is None:
            raise NotFoundError("PROCESO_NO_ENCONTRADO", "El proceso de reentrenamiento no existe o no está en tus fincas.")
        return proceso
