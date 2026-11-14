# | Fecha      | Nombre           | Que se hizo                                   |
# |------------|------------------|-----------------------------------------------|
# | 2026-10-22 | Arekkazu         | M05 RF-75: consulta limitada a las fincas     |
"""Caso de uso: consultar/buscar registros de consumo de alimento (RF-75).

Permite filtrar por activo, rango de fechas, tipo de alimento y estado. Solo
devuelve consumos de activos de las fincas del usuario (RF-25): ``modulo5`` no
tiene RLS, así que el alcance se aplica aquí.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.supplies.domain.entities.consumo_alimento import ConsumoAlimento
from src.supplies.domain.repositories.alcance_activo_port import AlcanceActivoPort
from src.supplies.domain.repositories.consumo_alimento_repository import ConsumoAlimentoRepository


class ConsultarConsumosUseCase:
    """Lista registros de consumo aplicando los filtros de búsqueda de RF-75."""

    def __init__(self, consumo_repo: ConsumoAlimentoRepository, alcance_port: AlcanceActivoPort) -> None:
        self.consumo_repo = consumo_repo
        self.alcance_port = alcance_port

    def execute(
        self,
        usuario_actual: UsuarioActual,
        *,
        id_activo_biologico: Optional[int] = None,
        fecha_desde: Optional[date] = None,
        fecha_hasta: Optional[date] = None,
        tipo_alimento: Optional[str] = None,
        estado_registro: Optional[str] = None,
    ) -> list[ConsumoAlimento]:
        return self.consumo_repo.listar(
            id_activo_biologico=id_activo_biologico,
            fecha_desde=fecha_desde,
            fecha_hasta=fecha_hasta,
            tipo_alimento=tipo_alimento,
            estado_registro=estado_registro,
            ids_permitidos=self.alcance_port.listar_ids_activos_permitidos(
                usuario_actual.id_usuario, usuario_actual.id_rol
            ),
        )
