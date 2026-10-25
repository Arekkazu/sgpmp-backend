# | Fecha      | Nombre  | Que se hizo |
# |------------|---------|-------------|
# | 2026-10-22 | Leandro | DEV-28 RF-62: evalua sobre normativo con snapshot DEV-14 |
from decimal import Decimal
from src.telemetry.domain.entities.calidad_vision import evaluar_calidad_vision


class EvaluarCalidadVisionUseCase:
    """Oraculo de aplicacion; la persistencia asincrona depende de DB-09."""
    def __init__(self,parametros):
        self.parametros=parametros

    def execute(self,sobre,fps_configurado):
        p=self.parametros.obtener(fps_configurado)
        duracion=Decimal(str((sobre.ventana_fin-sobre.ventana_inicio).total_seconds()))
        return evaluar_calidad_vision(cobertura=sobre.calidad.cobertura_ventana,
            fps=sobre.calidad.fps_efectivo,perdidos=sobre.calidad.n_tracks_perdidos,
            calibracion=sobre.calidad.estado_calibracion,parametros=p,duracion_seg=duracion)
