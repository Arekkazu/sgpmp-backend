# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-23 | destroyerban | DEV-36 RF-65: concurrencia optimista (config_version) e historial append-only |
from __future__ import annotations

from src.prediction.domain.entities.historial_configuracion_motor import (
    HistorialConfiguracionMotor,
    VersionConfiguracionMotor,
)
from src.prediction.domain.repositories.configuracion_motor_ia_repository import ConfiguracionMotorIARepository
from src.prediction.domain.repositories.historial_configuracion_motor_repository import (
    HistorialConfiguracionMotorRepository,
)
from src.shared.errors import NotFoundError
from src.shared.tipo_modelo import TIPOS_MODELO


class ConsultarHistorialMotorUseCase:
    """RF-65 Restricción 5: versiones de la configuración de un tipo_modelo, de la vigente a la más antigua.

    Solo lectura. La vigente sale de ``configuraciones_motor_ia`` y las anteriores
    del log append-only de DB-14.
    """

    def __init__(
        self,
        *,
        repo: ConfiguracionMotorIARepository,
        historial_repo: HistorialConfiguracionMotorRepository,
    ) -> None:
        self._repo = repo
        self._historial_repo = historial_repo

    def execute(self, tipo_modelo: str) -> HistorialConfiguracionMotor:
        vigente = self._repo.obtener_por_tipo(tipo_modelo) if tipo_modelo in TIPOS_MODELO else None
        anteriores = self._historial_repo.listar_por_tipo(tipo_modelo) if tipo_modelo in TIPOS_MODELO else []
        if vigente is None and not anteriores:
            raise NotFoundError(
                code="CONFIGURACION_MOTOR_NO_ENCONTRADA",
                message=f"No existe configuración para el tipo de modelo '{tipo_modelo}'.",
            )

        versiones = list(anteriores)
        if vigente is not None:
            versiones.insert(0, VersionConfiguracionMotor(
                config_version=vigente.config_version,
                vigente=True,
                id_usuario_responsable=vigente.id_usuario_responsable,
                configuracion=vigente._snapshot(),
                fecha_creacion_config=vigente.fecha_creacion,
            ))

        # Cada versión rige desde que se reemplazó la anterior; la v1, desde que se creó.
        # Las versiones previas a DB-14 no están en el log: la más antigua registrada
        # que no sea la v1 queda sin vigente_desde (se desconoce).
        desde = None
        for version in reversed(versiones):
            if desde is None and version.config_version == 1:
                desde = version.fecha_creacion_config
            version.vigente_desde = desde
            desde = version.vigente_hasta

        return HistorialConfiguracionMotor(
            tipo_modelo=tipo_modelo,
            config_version_vigente=vigente.config_version if vigente else None,
            versiones=versiones,
        )
