"""Estado de la configuración del motor en cada nodo Edge (DEV-09, RF-65)."""
from __future__ import annotations

from src.prediction.domain.entities.sincronizacion_nodo_edge import (
    ESTADO_APLICADA,
    ESTADO_PENDIENTE,
    ResultadoSincronizacionMotor,
    consolidar,
)
from src.prediction.domain.repositories.configuracion_motor_ia_repository import ConfiguracionMotorIARepository
from src.prediction.domain.repositories.sincronizacion_nodo_edge_repository import SincronizacionNodoEdgeRepository
from src.shared.errors import NotFoundError


class ConsultarSincronizacionMotorUseCase:
    def __init__(
        self,
        *,
        repo: ConfiguracionMotorIARepository,
        sincronizacion_repo: SincronizacionNodoEdgeRepository,
    ) -> None:
        self._repo = repo
        self._sincronizacion_repo = sincronizacion_repo

    def execute(self, tipo_modelo: str) -> ResultadoSincronizacionMotor:
        configuracion = self._repo.obtener_por_tipo(tipo_modelo)
        if configuracion is None:
            raise NotFoundError(
                code="CONFIGURACION_MOTOR_NO_ENCONTRADA",
                message=f"No existe configuración para el tipo de modelo '{tipo_modelo}'.",
            )
        resultado = consolidar(self._sincronizacion_repo.listar_por_tipo_modelo(tipo_modelo))
        # Un nodo que confirmó una versión anterior no tiene la vigente.
        atrasados = [n.serial for n in resultado.nodos if n.config_version_servidor < configuracion.config_version]
        if atrasados and resultado.estado == ESTADO_APLICADA:
            resultado.estado = ESTADO_PENDIENTE
            resultado.mensaje = (
                f"La configuración va en config_version {configuracion.config_version}; sin sincronizar: "
                + ", ".join(atrasados)
                + "."
            )
        return resultado
