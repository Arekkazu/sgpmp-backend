# | Fecha      | Nombre  | Que se hizo                                      |
# |------------|---------|--------------------------------------------------|
# | 2026-10-21 | Leandro | DEV-49 RF-57: evita duplicar historial de alerta tecnica |
# | 2026-10-21 | Leandro | DEV-27 RF-60: evalua umbrales y alerta INACTIVO critica |
"""Evaluación periódica: parámetros reales y algoritmo único de RF-60."""
from datetime import datetime, timezone

from .transicion_comunicacion import completar_transicion_comunicacion


class EvaluarEstadoDispositivosUseCase:
    def __init__(self, db, estado_repo, transicion_repo, periodo_repo,
                 alerta_repo, historico_alerta_repo, parametros_port):
        self.db = db
        self.estado_repo = estado_repo
        self.alerta_repo = alerta_repo
        self.periodo_repo = periodo_repo
        self.parametros_port = parametros_port
        # Los puertos previos se conservan en la composición. Las funciones
        # fn_log_transicion_dispositivo y los triggers de alerta ya escriben
        # historial y períodos dentro de la transacción del cambio de estado.

    def execute(self) -> int:
        ahora = datetime.now(timezone.utc)
        transiciones = 0
        try:
            for estado in self.estado_repo.listar_activos():
                if estado.fecha_ultimo_contacto is None:
                    continue
                parametros = self.parametros_port.obtener_comunicacion(estado.id_dispositivo_iot)
                tiempo = int((ahora-estado.fecha_ultimo_contacto).total_seconds())
                nuevo = estado.evaluar_transicion(tiempo, parametros.estado_local_buffer,
                    parametros.umbral_activo, parametros.umbral_sin_senal, parametros.umbral_inactivo)
                if nuevo is None:
                    continue
                causa = 'FALLO_CONECTIVIDAD' if nuevo in ('SIN_SEÑAL', 'INACTIVO', 'BUFFER_ACTIVO') else None
                estado.aplicar_transicion(nuevo, causa, ahora)
                estado.tiempo_sin_contacto = tiempo
                self.estado_repo.actualizar(estado)
                completar_transicion_comunicacion(estado, parametros, tiempo, ahora,
                    self.alerta_repo, self.periodo_repo, 'EVALUACION_PERIODICA')
                transiciones += 1
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return transiciones
