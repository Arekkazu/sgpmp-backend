# | Fecha      | Nombre           | Que se hizo                                   |
# |------------|------------------|-----------------------------------------------|
# | 2026-10-22 | Arekkazu         | M05 RF-76: consulta limitada a las fincas     |
"""Caso de uso: consultar/buscar aplicaciones de medicamento (RF-76).

Permite filtrar por activo, rango de fechas y estado. Solo devuelve registros
de activos de las fincas del usuario (RF-25): ``modulo5`` no tiene RLS, así
que el alcance se aplica aquí.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.supplies.domain.entities.medicamento import Medicamento
from src.supplies.domain.repositories.alcance_activo_port import AlcanceActivoPort
from src.supplies.domain.repositories.medicamento_repository import MedicamentoRepository


class ConsultarMedicamentosUseCase:
    """Lista aplicaciones de medicamento aplicando los filtros de búsqueda de RF-76."""

    def __init__(self, medicamento_repo: MedicamentoRepository, alcance_port: AlcanceActivoPort) -> None:
        self.medicamento_repo = medicamento_repo
        self.alcance_port = alcance_port

    def execute(
        self,
        usuario_actual: UsuarioActual,
        *,
        id_activo_biologico: Optional[int] = None,
        fecha_desde: Optional[date] = None,
        fecha_hasta: Optional[date] = None,
        estado_registro: Optional[str] = None,
    ) -> list[Medicamento]:
        return self.medicamento_repo.listar(
            id_activo_biologico=id_activo_biologico,
            fecha_desde=fecha_desde,
            fecha_hasta=fecha_hasta,
            estado_registro=estado_registro,
            ids_permitidos=self.alcance_port.listar_ids_activos_permitidos(
                usuario_actual.id_usuario, usuario_actual.id_rol
            ),
        )
