from __future__ import annotations

from datetime import datetime, timezone
from typing import List

from sqlalchemy.orm import Session

from src.telemetry.domain.entities.alerta import Alerta
from src.telemetry.domain.entities.historico_transicion_dispositivo import HistoricoTransicionDispositivo
from src.telemetry.domain.entities.periodo_inactividad import PeriodoInactividad
from src.telemetry.domain.repositories.alerta_repository import AlertaRepository
from src.telemetry.domain.repositories.estado_dispositivo_iot_repository import EstadoDispositivoIoTRepository
from src.telemetry.domain.repositories.historico_transicion_dispositivo_repository import HistoricoTransicionDispositivoRepository
from src.telemetry.domain.repositories.historico_estado_alerta_repository import HistoricoEstadoAlertaRepository
from src.telemetry.domain.repositories.periodo_inactividad_repository import PeriodoInactividadRepository


class EvaluarEstadoDispositivosUseCase:
    """Tarea periódica (60 s) que evalúa la máquina de estados de todos los dispositivos activos.
    Detecta SIN_SEÑAL e INACTIVO para dispositivos que dejaron de enviar heartbeats.
    """

    def __init__(
        self,
        db: Session,
        estado_repo: EstadoDispositivoIoTRepository,
        transicion_repo: HistoricoTransicionDispositivoRepository,
        periodo_repo: PeriodoInactividadRepository,
        alerta_repo: AlertaRepository,
        historico_alerta_repo: HistoricoEstadoAlertaRepository,
    ) -> None:
        self.db = db
        self.estado_repo = estado_repo
        self.transicion_repo = transicion_repo
        self.periodo_repo = periodo_repo
        self.alerta_repo = alerta_repo
        self.historico_alerta_repo = historico_alerta_repo

    def execute(self) -> int:
        """Evalúa todos los dispositivos. Retorna el número de transiciones registradas."""
        ahora = datetime.now(timezone.utc)
        estados = self.estado_repo.listar_activos()
        transiciones = 0

        try:
            for estado in estados:
                if estado.fecha_ultimo_contacto is None:
                    continue

                tiempo_seg = int((ahora - estado.fecha_ultimo_contacto).total_seconds())
                nuevo_estado = estado.evaluar_transicion(
                    tiempo_sin_contacto_seg=tiempo_seg,
                    estado_local_buffer=None,  # sin heartbeat reciente → no conocemos buffer
                )

                if nuevo_estado is None:
                    continue

                estado_anterior = estado.estado_actual
                estado.aplicar_transicion(nuevo_estado, causa='FALLO_CONECTIVIDAD', ahora=ahora)
                estado.tiempo_sin_contacto = tiempo_seg
                self.estado_repo.actualizar(estado)

                self.transicion_repo.registrar(HistoricoTransicionDispositivo(
                    id_transaccion=None,
                    id_dispositivo_iot=estado.id_dispositivo_iot,
                    estado_anterior=estado_anterior,
                    estado_nuevo=nuevo_estado,
                    causa_primaria='FALLO_CONECTIVIDAD',
                    causa_secundaria=None,
                    id_usuario_responsable=None,
                    notas='Transición automática por evaluación periódica (sin heartbeat).',
                    fecha_transicion=ahora,
                ))

                # Abrir periodo de inactividad si transición a SIN_SEÑAL o INACTIVO
                if nuevo_estado in ('SIN_SEÑAL', 'INACTIVO'):
                    periodo_existente = self.periodo_repo.obtener_abierto_por_dispositivo(
                        estado.id_dispositivo_iot
                    )
                    if periodo_existente is None:
                        periodo = self.periodo_repo.abrir(PeriodoInactividad(
                            id_periodo_inactividad=None,
                            id_dispositivo_iot=estado.id_dispositivo_iot,
                            sensores_afectados=[],
                            fecha_inicio=ahora,
                            fecha_fin=None,
                            duracion_min=None,
                            estado_durante_periodo=nuevo_estado,
                            causa_primaria='FALLO_CONECTIVIDAD',
                            caso_diagnosticado={},
                            buffer_activo_durante=False,
                            id_alerta=None,
                        ))

                        # Generar alerta técnica de conectividad
                        alerta = self.alerta_repo.guardar(Alerta(
                            tipo_alerta='TECNICA',
                            severidad='ALTA' if nuevo_estado == 'INACTIVO' else 'MEDIA',
                            estado_alerta='ACTIVA',
                            origen_evento='EVALUACION_PERIODICA',
                            tipo_variable='FALLO_CONECTIVIDAD',
                            fecha_evento=ahora,
                            fecha_generacion=ahora,
                            id_dispositivo_ioit=estado.id_dispositivo_iot,
                        ))
                        self.historico_alerta_repo.registrar(
                            id_alerta=alerta.id_alerta,
                            estado_anterior='',
                            estado_nuevo='ACTIVA',
                            motivo=f'Dispositivo en estado {nuevo_estado}',
                        )

                elif nuevo_estado == 'ACTIVO':
                    periodo = self.periodo_repo.obtener_abierto_por_dispositivo(estado.id_dispositivo_iot)
                    if periodo is not None:
                        periodo.cerrar(ahora)
                        self.periodo_repo.cerrar(periodo)

                transiciones += 1

            self.db.commit()

        except Exception:
            self.db.rollback()
            raise

        return transiciones
