"""Métricas de la especie del activo para los formularios de eventos (RF-40, RF-43).

El formulario de evento productivo pedía el producto como texto libre y el
usuario tenía que adivinar el valor; además leía el catálogo de M09 con el
permiso de métricas (recurso 19), que el Productor no tiene. Aquí se exponen
bajo el permiso de activos y marcadas según la fase activa, que es lo que
valida ``POST /{id_activo}/eventos/productivo`` (E-03 y E-04).
"""
from __future__ import annotations

from typing import Optional

from src.biological_assets.domain.repositories.activo_biologico_repository import ActivoBiologicoRepository
from src.biological_assets.domain.repositories.ciclo_consulta_port import CicloConsultaPort
from src.biological_assets.domain.repositories.parametros_especie_port import MetricaProductiva, ParametrosEspeciePort
from src.shared.errors import NotFoundError


class ListarMetricasActivoUseCase:
    """Devuelve cada métrica de la especie con si está habilitada en la fase activa."""

    def __init__(
        self,
        repo: ActivoBiologicoRepository,
        parametros_port: ParametrosEspeciePort,
        ciclo_port: CicloConsultaPort,
    ) -> None:
        self.repo = repo
        self.parametros_port = parametros_port
        self.ciclo_port = ciclo_port

    def execute(
        self,
        id_activo: int,
        *,
        ids_fincas_permitidas: Optional[list[int]] = None,
    ) -> list[tuple[MetricaProductiva, bool]]:
        activo = self.repo.obtener_por_id(id_activo, ids_fincas_permitidas=ids_fincas_permitidas)
        if activo is None:
            raise NotFoundError(
                code='ACTIVO_NO_ENCONTRADO',
                message=f'El activo biológico con ID {id_activo} no existe.',
            )
        fase = self.repo.obtener_fase_activa(id_activo)
        return [
            (
                m,
                fase is not None
                and self.ciclo_port.metrica_habilitada_en_ciclo(fase.id_ciclo_productiva, m.id_metrica_produccion),
            )
            for m in self.parametros_port.listar_metricas_productivas(activo.id_especie, activo.tipo)
        ]
