"""Caso de uso: consultar/filtrar la bitácora de auditoría de M05 (RF-80, CU-06).

Solo lectura. No se auto-audita: RF-80 no define un tipo de evento de negocio
para "se consultó la bitácora" (a diferencia de RF-81, donde
``CONSULTA_HISTORIAL_EJECUTADA`` sí está en el catálogo — ver el gap cerrado
en ``consultar_historial_suministros_use_case.py``).
"""
from __future__ import annotations

from src.supplies.domain.entities.evento_auditoria_suministro import EventoAuditoriaSuministroConsulta
from src.supplies.domain.repositories.auditoria_suministro_read_port import (
    AuditoriaSuministroReadPort,
    FiltrosAuditoriaSuministro,
)


class ConsultarAuditoriaSuministrosUseCase:
    def __init__(self, read_port: AuditoriaSuministroReadPort) -> None:
        self.read_port = read_port

    def listar(
        self, filtros: FiltrosAuditoriaSuministro
    ) -> tuple[list[EventoAuditoriaSuministroConsulta], int]:
        return self.read_port.consultar(filtros)

    def obtener_por_id(self, id_auditoria_suministro: int) -> EventoAuditoriaSuministroConsulta:
        return self.read_port.obtener_por_id(id_auditoria_suministro)
