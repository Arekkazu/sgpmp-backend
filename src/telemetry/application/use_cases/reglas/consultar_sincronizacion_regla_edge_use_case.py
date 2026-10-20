"""Estado vigente de una regla compuesta en cada Gateway Edge (DEV-08)."""
from __future__ import annotations

from src.shared.errors import NotFoundError
from src.telemetry.application.use_cases.reglas.sincronizar_regla_edge_use_case import consolidar
from src.telemetry.domain.entities.sincronizacion_regla_edge import (
    ESTADO_APLICADA,
    ESTADO_PENDIENTE,
    ResultadoSincronizacionRegla,
)
from src.telemetry.domain.repositories.regla_alerta_repository import ReglaAlertaRepository
from src.telemetry.domain.repositories.sincronizacion_regla_edge_repository import (
    SincronizacionReglaEdgeRepository,
)


class ConsultarSincronizacionReglaEdgeUseCase:

    def __init__(
        self,
        regla_repo: ReglaAlertaRepository,
        sincronizacion_repo: SincronizacionReglaEdgeRepository,
    ) -> None:
        self.regla_repo = regla_repo
        self.sincronizacion_repo = sincronizacion_repo

    def execute(self, id_regla_alertas: int) -> ResultadoSincronizacionRegla:
        regla = self.regla_repo.obtener_por_id(id_regla_alertas)
        if regla is None:
            raise NotFoundError(code="REGLA_ALERTA_NO_ENCONTRADA", message="La regla de alerta no existe.")
        nodos = self.sincronizacion_repo.listar_por_regla(id_regla_alertas)
        estado, mensaje = consolidar(nodos)
        # La regla cambió después del último envío (el trigger subió version_regla):
        # aunque un nodo confirmó, tiene la versión anterior.
        desactualizados = [n.serial for n in nodos if n.version_regla < regla.version_regla]
        if desactualizados and estado == ESTADO_APLICADA:
            estado = ESTADO_PENDIENTE
            mensaje = (
                f"La regla va en la versión {regla.version_regla}; sin sincronizar: "
                + ", ".join(desactualizados)
                + "."
            )
        return ResultadoSincronizacionRegla(
            id_regla_alertas=id_regla_alertas,
            version_regla=regla.version_regla,
            estado=estado,
            mensaje=mensaje,
            nodos=nodos,
        )
