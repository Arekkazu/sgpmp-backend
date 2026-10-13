"""Patologías de la especie del activo para el evento sanitario (RF-41).

El formulario sanitario leía las patologías de la configuración de M09 (recurso
18), que solo leen Administrador y Veterinario; a Productor e Ingeniero de
campo, que RF-41 también nombra como actores, la lista les salía vacía.
"""
from __future__ import annotations

from typing import Optional

from src.biological_assets.domain.repositories.activo_biologico_repository import ActivoBiologicoRepository
from src.biological_assets.domain.repositories.parametros_especie_port import ParametrosEspeciePort, PatologiaEspecie
from src.shared.errors import NotFoundError


class ListarPatologiasActivoUseCase:
    """Patologías activas de la especie del activo."""

    def __init__(self, repo: ActivoBiologicoRepository, parametros_port: ParametrosEspeciePort) -> None:
        self.repo = repo
        self.parametros_port = parametros_port

    def execute(self, id_activo: int, *, ids_fincas_permitidas: Optional[list[int]] = None) -> list[PatologiaEspecie]:
        activo = self.repo.obtener_por_id(id_activo, ids_fincas_permitidas=ids_fincas_permitidas)
        if activo is None:
            raise NotFoundError(
                code='ACTIVO_NO_ENCONTRADO',
                message=f'El activo biológico con ID {id_activo} no existe.',
            )
        return self.parametros_port.listar_patologias(activo.id_especie)
