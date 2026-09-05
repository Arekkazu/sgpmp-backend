"""Caso de uso: encolar un trabajo pesado de historial de suministros (RF-81).

Cubre las dos rutas que exigen procesamiento asíncrono: ``CONSULTA_PESADA``
(nivel de volumen 3/4) y ``EXPORTACION`` (> 10.000 registros). Valida el
límite de concurrencia por tipo de trabajo (429) antes de encolar.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from src.shared.errors import TooManyRequestsError
from src.supplies.domain.entities.historial_suministro import FiltrosHistorialSuministro
from src.supplies.domain.entities.trabajo_historial_suministro import TrabajoHistorialSuministro
from src.supplies.domain.repositories.configuracion_batch_historial_repository import (
    ConfiguracionBatchHistorialRepository,
)
from src.supplies.domain.repositories.trabajo_historial_suministro_repository import (
    TrabajoHistorialSuministroRepository,
)
from src.supplies.domain.value_objects.historial_suministro_enums import TipoTrabajoHistorial


class SolicitarTrabajoHistorialUseCase:
    def __init__(
        self,
        db: Session,
        trabajo_repo: TrabajoHistorialSuministroRepository,
        config_repo: ConfiguracionBatchHistorialRepository,
    ) -> None:
        self.db = db
        self.trabajo_repo = trabajo_repo
        self.config_repo = config_repo

    def execute(
        self, tipo_trabajo: str, filtros: FiltrosHistorialSuministro, id_usuario: int, id_rol: int
    ) -> TrabajoHistorialSuministro:
        config = self.config_repo.obtener()
        es_exportacion = tipo_trabajo == TipoTrabajoHistorial.EXPORTACION.value
        limite = config.limite_concurrencia_exportaciones if es_exportacion else config.limite_concurrencia_consultas

        if self.trabajo_repo.contar_activos(tipo_trabajo) >= limite:
            if es_exportacion:
                raise TooManyRequestsError(
                    code="LIMITE_EXPORTACIONES_EXCEDIDO",
                    message=(
                        "Límite de exportaciones concurrentes alcanzado. Espere a que alguna "
                        "exportación finalice antes de solicitar otra."
                    ),
                )
            raise TooManyRequestsError(
                code="LIMITE_CONCURRENCIA_EXCEDIDO",
                message="El sistema ha alcanzado el límite de consultas pesadas en procesamiento simultáneo.",
            )

        trabajo = TrabajoHistorialSuministro(
            tipo_trabajo=tipo_trabajo,
            parametros=self._filtros_a_dict(filtros, id_rol),
            id_usuario_solicitante=id_usuario,
        )
        try:
            trabajo = self.trabajo_repo.encolar(trabajo)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return trabajo

    @staticmethod
    def _filtros_a_dict(filtros: FiltrosHistorialSuministro, id_rol: int) -> dict:
        return {
            "id_rol_solicitante": id_rol,
            "id_activo_biologico": filtros.id_activo_biologico,
            "id_ciclo_productivo": filtros.id_ciclo_productivo,
            "fecha_inicio_filtro": filtros.fecha_inicio_filtro.isoformat() if filtros.fecha_inicio_filtro else None,
            "fecha_fin_filtro": filtros.fecha_fin_filtro.isoformat() if filtros.fecha_fin_filtro else None,
            "tipo_suministro_filtro": filtros.tipo_suministro_filtro,
            "origen_precio_filtro": filtros.origen_precio_filtro,
            "costo_min": str(filtros.costo_min) if filtros.costo_min is not None else None,
            "costo_max": str(filtros.costo_max) if filtros.costo_max is not None else None,
            "pagina": filtros.pagina,
            "registros_por_pagina": filtros.registros_por_pagina,
        }
