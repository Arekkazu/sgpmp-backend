"""Caso de uso: descargar el resultado de una exportación async de historial (RF-81).

Solo aplica a trabajos ``EXPORTACION`` ya ``COMPLETADO``. El archivo se
retiene 72 horas (Restricción 3 de RF-81) — la limpieza de trabajos vencidos
queda fuera de alcance de esta iteración (ver gap doc).
"""
from __future__ import annotations

from src.shared.errors import BusinessRuleError, NotFoundError
from src.supplies.domain.repositories.trabajo_historial_suministro_repository import (
    TrabajoHistorialSuministroRepository,
)
from src.supplies.domain.value_objects.estado_trabajo_async import EstadoTrabajoAsync


class DescargarResultadoTrabajoHistorialUseCase:
    def __init__(self, trabajo_repo: TrabajoHistorialSuministroRepository) -> None:
        self.trabajo_repo = trabajo_repo

    def execute(self, id_cola: int) -> tuple[str, str]:
        trabajo = self.trabajo_repo.obtener(id_cola)
        if trabajo is None:
            raise NotFoundError(
                code="TRABAJO_NO_ENCONTRADO",
                message=f"El trabajo de historial {id_cola} no existe.",
                field="id_cola",
            )
        if trabajo.estado != EstadoTrabajoAsync.COMPLETADO:
            raise BusinessRuleError(
                code="TRABAJO_NO_COMPLETADO",
                message=f"El trabajo {id_cola} aún no ha finalizado (estado actual: {trabajo.estado.value}).",
            )
        ejecucion = self.trabajo_repo.obtener_ultima_ejecucion(id_cola)
        if ejecucion is None or ejecucion.contenido_csv is None:
            raise NotFoundError(
                code="RESULTADO_NO_DISPONIBLE",
                message=f"El resultado del trabajo {id_cola} no está disponible para descarga.",
            )
        return ejecucion.contenido_csv, ejecucion.nombre_archivo or f"Historial_Suministros_{id_cola}.csv"
