"""Ciclos productivos que se le pueden asignar a un activo (RF-37).

Arekkazu/SGPMP-FRONT-END-PWA#288: el modal "Cambiar fase" no tenía de dónde
sacar los ciclos productivos y listaba ciclos biológicos, cuyo ID no es el que
espera ``POST /{id_activo}/fases``. Se listan solo los de la especie del activo.
"""
from __future__ import annotations

from typing import Optional

from src.biological_assets.domain.repositories.activo_biologico_repository import ActivoBiologicoRepository
from src.biological_assets.domain.repositories.ciclo_consulta_port import (
    CicloConsultaPort,
    CicloProductivoConsulta,
)
from src.shared.errors import NotFoundError


class ListarCiclosProductivosActivoUseCase:
    def __init__(self, repo: ActivoBiologicoRepository, ciclo_port: CicloConsultaPort) -> None:
        self.repo = repo
        self.ciclo_port = ciclo_port

    def execute(
        self,
        id_activo: int,
        *,
        ids_fincas_permitidas: Optional[list[int]] = None,
    ) -> list[CicloProductivoConsulta]:
        activo = self.repo.obtener_por_id(id_activo, ids_fincas_permitidas=ids_fincas_permitidas)
        if activo is None:
            raise NotFoundError(
                code='ACTIVO_NO_ENCONTRADO',
                message=f'El activo biológico con ID {id_activo} no existe.',
            )
        return self.ciclo_port.listar_por_especie(activo.id_especie)
