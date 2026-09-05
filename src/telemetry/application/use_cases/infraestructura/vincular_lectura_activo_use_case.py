from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.telemetry.domain.entities.vinculacion_lectura import VinculacionLectura
from src.telemetry.domain.repositories.activo_biologico_dependency_port import ActivoBiologicoDependencyPort
from src.telemetry.domain.repositories.vinculacion_lectura_repository import VinculacionLecturaRepository


class VincularLecturaActivoUseCase:
    """RF-61-A+B: Vinculación automática de una lectura telemétrica a su activo biológico.
    Se llama desde IngerirTelemetriaUseCase después del commit de la telemetría.
    Tiene su propia transacción.
    """

    def __init__(
        self,
        db: Session,
        vinculacion_repo: VinculacionLecturaRepository,
        activo_port: ActivoBiologicoDependencyPort,
    ) -> None:
        self.db = db
        self.vinculacion_repo = vinculacion_repo
        self.activo_port = activo_port

    def execute(
        self,
        id_telemetria: int,
        id_infraestructura: int,
        timestamp_captura: datetime,
    ) -> VinculacionLectura:
        ahora = datetime.now(timezone.utc)

        try:
            activos = self.activo_port.obtener_activos_en_momento(
                id_infraestructura=id_infraestructura,
                timestamp=timestamp_captura,
            )

            if len(activos) == 0:
                estado = 'SIN_VINCULAR'
                id_activo = None
                modelo_manejo = 'INDIVIDUAL'
            elif len(activos) == 1:
                estado = 'VINCULADA'
                id_activo = activos[0].id_activo_biologico
                modelo_manejo = activos[0].modelo_manejo
            else:
                estado = 'AMBIGUA'
                id_activo = None
                modelo_manejo = activos[0].modelo_manejo

            vinculacion = self.vinculacion_repo.guardar(VinculacionLectura(
                id_vinculacion_lectura=None,
                id_telemetria=id_telemetria,
                modelo_manejo=modelo_manejo,
                id_activo_biologico=id_activo,
                id_infraestructura=id_infraestructura,
                fecha_inicio_vinculacion=timestamp_captura,
                fecha_fin_vinculacion=None,
                mecanismo_vinculacion='AUTOMATICA',
                estado_vinculacion=estado,
                id_usuario=None,
                motivo_correccion=None,
                id_vinculacion_reemplazada=None,
                fecha_creacion=ahora,
            ))

            self.db.commit()
            return vinculacion

        except Exception:
            self.db.rollback()
            raise
