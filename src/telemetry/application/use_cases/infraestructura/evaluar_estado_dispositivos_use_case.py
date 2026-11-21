# | Fecha      | Nombre  | Que se hizo                                      |
# |------------|---------|--------------------------------------------------|
# | 2026-10-21 | Leandro | DEV-49 RF-57: evita duplicar historial de alerta tecnica |
# | 2026-10-21 | Leandro | DEV-27 RF-60: evalua umbrales y alerta INACTIVO critica |
# | 2026-10-22 | Leandro | DEV-42 RF-60: evalua diagnosticos aunque no cambie estado |
# | 2026-10-22 | Leandro | DEV-47 RF-63: conserva al trigger como fuente unica de transiciones |
# | 2026-10-27 | Leandro | INC-M03-127-G27 RF-54/60: evaluar la cola reportada sin confundir contacto reciente con sincronización terminada. |
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

    def execute(self, id_dispositivo=None, *, confirmar=True) -> int:
        ahora = datetime.now(timezone.utc)
        transiciones = 0
        try:
            candidatos = (self.estado_repo.listar_activos() if id_dispositivo is None else
                [self.estado_repo.obtener_por_dispositivo(id_dispositivo)])
            for candidato in candidatos:
                if candidato is None:
                    continue
                estado = self.estado_repo.bloquear_por_dispositivo(candidato.id_dispositivo_iot)
                if estado is None or estado.estado_actual == 'EN_MANTENIMIENTO':
                    continue
                if estado.fecha_ultimo_contacto is None:
                    continue
                parametros = self.parametros_port.obtener_comunicacion(estado.id_dispositivo_iot)
                tiempo = int((ahora-estado.fecha_ultimo_contacto).total_seconds())
                nuevo = estado.evaluar_transicion(tiempo, parametros.estado_local_buffer,
                    parametros.umbral_activo, parametros.umbral_sin_senal, parametros.umbral_inactivo,
                    datos_pendientes_buffer=parametros.datos_pendientes_buffer)
                if nuevo is None:
                    completar_transicion_comunicacion(estado, parametros, tiempo, ahora,
                        self.alerta_repo, self.periodo_repo, 'EVALUACION_PERIODICA')
                    continue
                causa = 'FALLO_CONECTIVIDAD' if nuevo in ('SIN_SEÑAL', 'INACTIVO', 'BUFFER_ACTIVO') else None
                estado.aplicar_transicion(nuevo, causa, ahora)
                estado.tiempo_sin_contacto = tiempo
                self.estado_repo.actualizar(estado)
                completar_transicion_comunicacion(estado, parametros, tiempo, ahora,
                    self.alerta_repo, self.periodo_repo, 'EVALUACION_PERIODICA')
                transiciones += 1
            if confirmar:
                self.db.commit()
        except Exception:
            if confirmar:
                self.db.rollback()
            raise
        return transiciones
