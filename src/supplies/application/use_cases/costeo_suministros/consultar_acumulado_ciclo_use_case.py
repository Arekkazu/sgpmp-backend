"""Caso de uso: consultar el acumulado de inversión de una instancia de ciclo (RF-78).

Dos formas de acceso: por activo (resuelve la fase productiva actualmente
activa, uso operativo del Productor/Veterinario) y por ``id_gestion_fases``
directo (uso de M06/Contador tras el cierre del ciclo, cuando ya no hay fase
activa que resolver).
"""
from __future__ import annotations

from src.shared.errors import NotFoundError
from src.supplies.domain.entities.acumulado_ciclo import AcumuladoCiclo
from src.supplies.domain.repositories.acumulado_ciclo_repository import AcumuladoCicloRepository
from src.supplies.domain.repositories.ciclo_abierto_port import CicloAbiertoPort


class ConsultarAcumuladoCicloUseCase:
    """Consulta de solo lectura del acumulado de inversión de una instancia de ciclo."""

    def __init__(self, acumulado_repo: AcumuladoCicloRepository, ciclo_port: CicloAbiertoPort) -> None:
        self.acumulado_repo = acumulado_repo
        self.ciclo_port = ciclo_port

    def por_activo(self, id_activo_biologico: int) -> AcumuladoCiclo:
        ciclo = self.ciclo_port.obtener_abierto(id_activo_biologico)
        if ciclo is None or ciclo.id_gestion_fases is None:
            raise NotFoundError(
                code="CICLO_NO_ACTIVO",
                message=f"El activo {id_activo_biologico} no tiene un ciclo productivo activo.",
            )
        return self.por_gestion_fase(ciclo.id_gestion_fases)

    def por_gestion_fase(self, id_gestion_fases: int) -> AcumuladoCiclo:
        acumulado = self.acumulado_repo.obtener(id_gestion_fases)
        if acumulado is None:
            raise NotFoundError(
                code="ACUMULADO_NO_ENCONTRADO",
                message=(
                    f"No existe un acumulado para la instancia de ciclo {id_gestion_fases} — "
                    "aún no se han registrado suministros en ella."
                ),
            )
        return acumulado
