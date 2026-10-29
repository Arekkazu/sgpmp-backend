# | Fecha      | Nombre  | Que se hizo |
# |------------|---------|-------------|
# | 2026-10-22 | Leandro | DEV-28 RF-62: evalua sobre normativo con snapshot DEV-14 |
# | 2026-10-25 | Arekkazu | INC-M03-134-G192 RF-62: evalua y persiste la observacion ingerida |
"""RF-62: calidad de una observación de visión ya ingerida (AIOT-SPEC-01).

Corre después de la ingesta: lo llaman el worker post-commit (etapa
``VISION_CALIDAD``) y ``POST /iot/calidad/vision/{id}/evaluar``. Es idempotente:
una observación evaluada se devuelve tal cual, sin recalcular, porque su índice
debe seguir siendo el de los parámetros vigentes al evaluarla.
"""
from datetime import datetime, timezone
from decimal import Decimal

from src.shared.errors import NotFoundError


class EvaluarCalidadVisionUseCase:
    def __init__(self, db, repo, parametros, dispositivo_port):
        self.db = db
        self.repo = repo
        self.parametros = parametros
        self.dispositivo_port = dispositivo_port

    def execute(self, id_observacion_vision):
        observacion = self.repo.obtener(id_observacion_vision)
        if observacion is None:
            raise NotFoundError(
                code='OBSERVACION_VISION_NO_ENCONTRADA',
                message=f'No existe la observación de visión {id_observacion_vision}.',
            )
        # Con RLS, una cámara de otra finca no es visible para el usuario.
        camara = self.dispositivo_port.obtener_camara_por_id(observacion.id_dispositivo_iot)
        if camara is None:
            raise NotFoundError(
                code='OBSERVACION_VISION_NO_ENCONTRADA',
                message=f'No existe la observación de visión {id_observacion_vision}.',
            )
        if observacion.esta_evaluada:
            return observacion

        # fps configurado de la cámara en RF-23; sin él el adaptador responde 503.
        parametros = self.parametros.obtener(camara.fps_nominal)
        if observacion.fecha_inicio_ventana is not None:
            duracion = (observacion.fecha_observacion - observacion.fecha_inicio_ventana).total_seconds()
        else:
            # El lote legado no trae la ventana: se usa la duración configurada (DEV-27).
            duracion = self.parametros.obtener_ventanas().duracion_seg

        observacion.evaluar(parametros, duracion_seg=Decimal(str(duracion)), ahora=datetime.now(timezone.utc))
        try:
            self.repo.guardar_evaluacion(observacion)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return observacion
