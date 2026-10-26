# | Fecha      | Nombre  | Que se hizo                                      |
# |------------|---------|--------------------------------------------------|
# | 2026-10-21 | Leandro | DEV-43 RF-62: gaps, omisiones y evidencia de limites |
# | 2026-10-26 | Leandro | INC-M03-104-G165 RF-62: detectar outlier con sigma cero y auditar notificaciones de drift pendientes sin perder calidad. |
"""RF-62: Evaluación estadística de calidad de lecturas teleméricas.

Pipeline de 8 fases:
  Fase 0 — Verificar estado_calidad heredado de RF-53.
  Fase 1 — Recuperar contexto (serie temporal, parámetros).
  Fase 2 — Sensor congelado.
  Fase 3 — Outlier estadístico + límites físicos.
  Fase 4 — Deriva (drift). Omitida si calibracion_no_disponible.
  Fase 5 — Gap temporal anómalo.
  Fase 6 — Cálculo del índice de calidad y clasificación.
  Fase 7 — Persistir aptitud en telemetria_calidad, sin modificar telemetrias.
  Fase 8 — Alertas técnicas + evento RF-63.
"""
from __future__ import annotations

import statistics
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from src.shared.errors import ServiceUnavailableError
from src.telemetry.domain.repositories.contexto_calidad_port import ContextoCalidadPort
from src.telemetry.domain.entities.consistencia_temporal_calidad import (
    utc, unir_periodos, cubierto, detectar_gaps,
)

from sqlalchemy.orm import Session

from src.telemetry.domain.entities.telemetria_calidad import (
    ClasificacionCalidad,
    TelemetriaCalidad,
    calcular_indice_calidad,
    clasificar_desde_indice,
    derivar_aptitud,
)
from src.telemetry.domain.entities.evento_auditoria_iot import ComponenteOrigen, EntidadAfectadaTipo, SeveridadLog, TipoResultado
from src.telemetry.domain.repositories.bitacora_auditoria_iot_repository import BitacoraAuditoriaIotRepository
from src.telemetry.domain.repositories.parametros_calidad_port import ParametrosCalidadPort
from src.telemetry.domain.repositories.telemetria_calidad_repository import TelemetriaCalidadRepository
from src.telemetry.domain.repositories.telemetria_repository import TelemetriaRepository

class EvaluarCalidadTelemetriaUseCase:

    def __init__(
        self,
        db: Session,
        telemetria_repo: TelemetriaRepository,
        calidad_repo: TelemetriaCalidadRepository,
        parametros_port: ParametrosCalidadPort,
        auditoria_repo: Optional[BitacoraAuditoriaIotRepository] = None,
        contexto_port: ContextoCalidadPort | None = None,
        alertas_calidad=None,
    ) -> None:
        self.db = db
        self.telemetria_repo = telemetria_repo
        self.calidad_repo = calidad_repo
        self.parametros_port = parametros_port
        self.auditoria_repo = auditoria_repo
        self.contexto_port = contexto_port
        self.alertas_calidad = alertas_calidad
        self._version_limites = None
        self._contexto = {}

    def execute(
        self,
        id_telemetria: int,
        id_sensor: int,
        id_variable: int,
        valor: Decimal,
        valor_ajustado: Optional[Decimal],
        timestamp_captura: datetime,
        estado_calidad_rf53: str,
        parametros_calibracion: Optional[dict],
        tipo_variable: Optional[str] = None,
    ) -> TelemetriaCalidad | None:
        try:
            return self._execute(id_telemetria,id_sensor,id_variable,valor,valor_ajustado,
                                 timestamp_captura,estado_calidad_rf53,parametros_calibracion,tipo_variable)
        except Exception:
            self.db.rollback()
            raise

    def _execute(
        self,
        id_telemetria: int,
        id_sensor: int,
        id_variable: int,
        valor: Decimal,
        valor_ajustado: Optional[Decimal],
        timestamp_captura: datetime,
        estado_calidad_rf53: str,
        parametros_calibracion: Optional[dict],
        tipo_variable: Optional[str] = None,
    ) -> TelemetriaCalidad | None:
        self._version_limites = None
        self._contexto = {'id_variable': id_variable}
        if self.contexto_port is not None:
            self.contexto_port.bloquear_evaluacion(id_telemetria)
        ahora = datetime.now(timezone.utc)
        flags: dict = {}
        omitir_drift = False

        # ── Fase 0: estado heredado de RF-53 ──────────────────────────────────
        if estado_calidad_rf53 == 'FUERA_DE_RANGO':
            flags['fuera_de_rango_rf53'] = {'activo': True}
            evaluacion = self._persistir(
                id_telemetria=id_telemetria,
                id_sensor=id_sensor,
                ahora=ahora,
                indice=0,
                clasificacion=ClasificacionCalidad.NO_APTO,
                flags=flags,
                parametros_aplicados={},
                parametros_calibracion_aplicados=parametros_calibracion,
                motivo_reevaluacion=None,
            )
            self._emitir_auditoria(TipoResultado.EXITOSO, id_telemetria, flags)
            return evaluacion

        calibracion_no_disponible = False
        if estado_calidad_rf53 == 'ERROR_CALIBRACION':
            calibracion_no_disponible = True
            flags['calibracion_no_disponible'] = {'activo': True}
            omitir_drift = True

        # ── Fase 1: Recuperar contexto ─────────────────────────────────────────
        params = self.parametros_port.obtener_parametros(id_sensor, tipo_variable)
        contexto = None
        gaps, excluidos = [], []
        if self.contexto_port is not None:
            contexto = self.contexto_port.obtener(id_telemetria,id_sensor,id_variable,timestamp_captura,params.N)
            fechas = [utc(l.timestamp_captura) for l in contexto.lecturas] + [utc(timestamp_captura)]
            periodos = unir_periodos(contexto.periodos, utc(timestamp_captura))
            if contexto.lecturas and cubierto(min(fechas), max(fechas), periodos):
                if self.contexto_port.omision_registrada(id_telemetria) is True:
                    self.db.commit()
                    return None
                self._registrar_evidencia(id_telemetria, {},
                    'EVALUACION_OMITIDA_POR_INACTIVIDAD',
                    {'id_sensor':id_sensor,'inicio':min(fechas).isoformat(),
                     'fin':max(fechas).isoformat(),'periodos':[(a.isoformat(),b.isoformat()) for a,b in periodos]})
                self.db.commit()
                return None
            frecuencia = (contexto.frecuencia_muestreo_min if contexto.frecuencia_muestreo_min is not None
                          else params.frecuencia_muestreo_min)
            gaps, excluidos = detectar_gaps(contexto.lecturas,timestamp_captura,frecuencia,periodos)
            serie = [l.valor for l in sorted(contexto.lecturas,
                key=lambda l:(utc(l.timestamp_captura),l.id_telemetria),reverse=True)
                if not cubierto(utc(l.timestamp_captura),utc(l.timestamp_captura),periodos)]
            excluidas = len(contexto.lecturas)-len(serie)
            if contexto.lecturas_estadisticas is not None:
                serie = [l.valor for l in contexto.lecturas_estadisticas]
            self._contexto['consistencia_temporal'] = {
                'frecuencia_muestreo_min':frecuencia,'gaps_excluidos_rf60':excluidos,
                'lecturas_excluidas_rf60':excluidas,
                'inicio_serie':min(fechas).isoformat(),'fin_serie':max(fechas).isoformat(),
            }
            limites = contexto.limites
            if limites is not None and limites.version is not None:
                if (not limites.version.strip() or len(limites.version)>50 or
                        not limites.minimo.is_finite() or not limites.maximo.is_finite() or
                        limites.minimo > limites.maximo):
                    raise ServiceUnavailableError('LIMITES_FISICOS_INVALIDOS','El snapshot de límites físicos es inválido.')
                self._version_limites = limites.version
                self._contexto['limites_fisicos_aplicados'] = {
                    'minimo':str(limites.minimo),'maximo':str(limites.maximo),'fuente':limites.fuente}
            else:
                self._contexto['limites_fisicos'] = {
                    'estado':'PENDIENTE_VERSIONADO_M09','aplicados':False,
                    'fuente':limites.fuente if limites else None}
        else:
            # Uso aislado con puertos estadísticos; los entrypoints productivos
            # siempre inyectan el contexto real, sin catálogo físico alternativo.
            serie = self.telemetria_repo.obtener_serie_temporal(id_sensor, params.N, timestamp_captura)

        if len(serie) < params.N:
            flags['serie_insuficiente'] = {'activo': True}
            evaluacion = self._persistir(
                id_telemetria=id_telemetria,
                id_sensor=id_sensor,
                ahora=ahora,
                indice=None,
                clasificacion=ClasificacionCalidad.INDETERMINADA,
                flags=flags,
                parametros_aplicados={'k': params.k, 'M': params.M, 'N': params.N, 'umbral_drift': params.umbral_drift, 'P': params.P, 'frecuencia_muestreo_min': params.frecuencia_muestreo_min, 'umbral_drift_significativo': params.umbral_drift_significativo},
                parametros_calibracion_aplicados=parametros_calibracion,
                motivo_reevaluacion=None,
            )
            self._emitir_auditoria(TipoResultado.EXITOSO, id_telemetria, flags)
            return evaluacion

        # ── Fase 2: Sensor congelado ───────────────────────────────────────────
        ultimas_m = serie[:params.M]
        if len(ultimas_m) == params.M and len(set(str(v) for v in ultimas_m)) == 1:
            repeticiones = sum(1 for v in serie if v == ultimas_m[0])
            if repeticiones >= 20:
                sev = 'CRITICO'
            elif repeticiones >= 10:
                sev = 'MODERADO'
            else:
                sev = 'LEVE'
            flags['sensor_congelado'] = {
                'activo': True,
                'severidad': sev,
                'N_evaluadas': len(serie),
                'M_repeticiones': repeticiones,
                'valor_repetido': str(ultimas_m[0]),
            }

        # ── Fase 3: Outlier estadístico ────────────────────────────────────────
        if len(serie) >= 2:
            mu = statistics.mean(float(v) for v in serie)
            sigma = statistics.stdev(float(v) for v in serie)
            desviacion = abs(float(valor) - mu)
            if desviacion > params.k * sigma:
                flags['outlier_estadistico'] = {
                    'activo': True,
                    'media_serie': round(mu, 4),
                    'desviacion_estandar': round(sigma, 4),
                    'k_utilizado': params.k,
                    # Con sigma cero, la desigualdad sigue siendo válida,
                    # pero el z-score no está definido. Nunca serializar infinito.
                    'magnitud_desviacion': round(desviacion / sigma, 4) if sigma > 0 else None,
                    'causa': 'ESTADISTICO',
                }
                if sigma == 0:
                    flags['outlier_estadistico'].update(
                        sigma_cero=True, desviacion_absoluta=round(desviacion, 4),
                    )
            elif self._version_limites is not None:
                if valor < contexto.limites.minimo or valor > contexto.limites.maximo:
                    flags['outlier_estadistico'] = {
                        'activo': True, 'media_serie': round(mu, 4),
                        'desviacion_estandar': round(sigma, 4), 'k_utilizado': params.k,
                        'magnitud_desviacion': 0, 'causa': 'LIMITE_FISICO',
                    }

        # ── Fase 4: Drift ──────────────────────────────────────────────────────
        if not omitir_drift and parametros_calibracion and serie:
            ganancia = Decimal(str(parametros_calibracion.get('ganancia', 1)))
            offset = Decimal(str(parametros_calibracion.get('offset', 0)))
            val_cal_esperado = statistics.mean(float(v) * float(ganancia) + float(offset) for v in serie)
            media_n = statistics.mean(float(v) for v in serie)
            if val_cal_esperado != 0:
                magnitud = abs(media_n - val_cal_esperado) / abs(val_cal_esperado) * 100
                if magnitud > params.umbral_drift:
                    misma_dir = sum(1 for v in serie if (float(v) - val_cal_esperado) * (media_n - val_cal_esperado) > 0)
                    if misma_dir >= params.P:
                        flags['posible_drift'] = {
                            'activo': True,
                            'valor_calibrado_esperado': round(val_cal_esperado, 4),
                            'media_ultimas_N': round(media_n, 4),
                            'magnitud_drift_porcentaje': round(magnitud, 4),
                            'P_lecturas_consistentes': misma_dir,
                            'umbral_aplicado': params.umbral_drift,
                        }

        # ── Fase 5: Gap temporal ───────────────────────────────────────────────
        if gaps:
            flags['gap_temporal_anomalo'] = {'activo':True, **gaps[-1], 'gaps_detectados':gaps}

        # ── Fase 6: Índice y clasificación ────────────────────────────────────
        indice = calcular_indice_calidad(flags)
        clasificacion = clasificar_desde_indice(indice)
        # ── Fase 7: Persistir ──────────────────────────────────────────────────
        evaluacion = self._persistir(
            id_telemetria=id_telemetria,
            id_sensor=id_sensor,
            ahora=ahora,
            indice=indice,
            clasificacion=clasificacion,
            flags=flags,
            parametros_aplicados={'k': params.k, 'M': params.M, 'N': params.N, 'umbral_drift': params.umbral_drift, 'P': params.P, 'frecuencia_muestreo_min': params.frecuencia_muestreo_min, 'umbral_drift_significativo': params.umbral_drift_significativo},
            parametros_calibracion_aplicados=parametros_calibracion,
            motivo_reevaluacion=None,
        )

        # ── Fase 8: Notificaciones ─────────────────────────────────────────────
        self._emitir_auditoria(TipoResultado.EXITOSO, id_telemetria, flags)
        return evaluacion

    def _persistir(
        self,
        id_telemetria: int,
        id_sensor: int,
        ahora: datetime,
        indice: Optional[int],
        clasificacion: ClasificacionCalidad,
        flags: dict,
        parametros_aplicados: dict,
        parametros_calibracion_aplicados: Optional[dict],
        motivo_reevaluacion: Optional[str],
    ) -> TelemetriaCalidad:
        apto_ia, apto_nic41 = derivar_aptitud(clasificacion)
        evaluacion = TelemetriaCalidad(
            id_evaluacion=None,
            id_telemetria=id_telemetria,
            id_sensor=id_sensor,
            timestamp_evaluacion=ahora,
            indice_calidad=indice,
            clasificacion_calidad=clasificacion,
            apto_para_ia=apto_ia,
            apto_para_nic41=apto_nic41,
            flags_detectados=flags,
            version_limites_fisicos_aplicada=self._version_limites,
            parametros_aplicados={**parametros_aplicados, **self._contexto},
            parametros_calibracion_aplicados=parametros_calibracion_aplicados,
            motivo_reevaluacion=motivo_reevaluacion,
        )
        # Todas las ramas (incluidas FUERA_DE_RANGO e INDETERMINADA) confirman
        # la evaluación antes de emitir auditoría. RF-53 permanece inmutable.
        try:
            anterior = self.calidad_repo.obtener_por_lectura(id_telemetria)
            if anterior is not None:
                evaluacion.id_evaluacion_superada = anterior.id_evaluacion
            guardada = self.calidad_repo.guardar(evaluacion)
            if anterior is not None:
                self.calidad_repo.marcar_superada(
                    anterior.id_evaluacion,
                    motivo=motivo_reevaluacion or 'Superada por una evaluación posterior de RF-62.',
                )
            pendientes = []
            if self.alertas_calidad is not None:
                pendientes = self.alertas_calidad.execute(guardada) or []
            if self.contexto_port is not None:
                detalle = {
                    'id_evaluacion': str(guardada.id_evaluacion),
                    'version_limites_fisicos_aplicada': self._version_limites,
                    'parametros_aplicados': guardada.parametros_aplicados,
                }
                if pendientes:
                    detalle['notificaciones_pendientes'] = pendientes
                self._registrar_evidencia(id_telemetria,flags,'EVALUACION_CALIDAD_COMPLETADA',
                    detalle)
            self.db.commit()
            return guardada
        except Exception:
            raise

    def _emitir_auditoria(
        self,
        resultado: TipoResultado,
        id_telemetria: int,
        flags: dict,
    ) -> None:
        if self.contexto_port is not None or self.auditoria_repo is None:
            return
        try:
            from src.telemetry.application.use_cases.auditoria.registrar_evento_auditoria_iot_use_case import RegistrarEventoAuditoriaIotUseCase
            svc = RegistrarEventoAuditoriaIotUseCase(db=self.db, auditoria_repo=self.auditoria_repo)
            anomalias = [k for k, v in flags.items() if isinstance(v, dict) and v.get('activo')]
            sev = SeveridadLog.WARNING if anomalias else SeveridadLog.INFO
            svc.execute(
                tipo_evento='EVALUACION_CALIDAD_COMPLETADA',
                resultado=resultado,
                componente_origen=ComponenteOrigen.RF62,
                severidad_log=sev,
                descripcion=f'Evaluación de calidad completada. Anomalías: {anomalias or "ninguna"}.',
                entidad_afectada_tipo=EntidadAfectadaTipo.CALIDAD_DATO,
                entidad_afectada_id=str(id_telemetria),
                accion_detallada={'flags': flags},
            )
        except Exception:
            pass

    def _registrar_evidencia(self, id_telemetria, flags, tipo, detalle):
        """Evidencia obligatoria y atómica; el repositorio best-effort no basta."""
        from src.telemetry.application.use_cases.auditoria.registrar_evento_auditoria_iot_use_case import _calcular_hash
        from src.telemetry.domain.entities.evento_auditoria_iot import EventoAuditoriaIot, clasificar_componente
        if self.auditoria_repo is None:
            raise ServiceUnavailableError('AUDITORIA_CALIDAD_NO_DISPONIBLE',
                                          'RF-62 requiere persistir la evidencia de evaluación.')
        clasificacion, retencion = clasificar_componente(ComponenteOrigen.RF62)
        limites_pendientes = detalle.get('parametros_aplicados',{}).get('limites_fisicos',{}).get('estado')
        evento = EventoAuditoriaIot(
            id_evento=None, tipo_evento=tipo, fecha_hora=datetime.now(timezone.utc),
            resultado=(TipoResultado.PARCIAL if limites_pendientes or detalle.get('notificaciones_pendientes')
                       else TipoResultado.EXITOSO), modulo='M03',
            descripcion='RF-62: evaluación omitida por inactividad.' if 'OMITIDA' in tipo else 'RF-62: evaluación de calidad completada.',
            entidad_afectada_tipo=EntidadAfectadaTipo.CALIDAD_DATO, entidad_afectada_id=str(id_telemetria),
            severidad_log=SeveridadLog.WARNING if flags else SeveridadLog.INFO,
            componente_origen=ComponenteOrigen.RF62, accion_detallada={'flags':flags,**detalle},
            clasificacion_registro=clasificacion,retencion_aplicable=retencion,hash_integridad='',
        )
        evento.hash_integridad = _calcular_hash(evento)
        if self.auditoria_repo.registrar(evento).id_evento is None:
            raise ServiceUnavailableError('AUDITORIA_CALIDAD_NO_DISPONIBLE',
                                          'No se pudo persistir la evidencia de calidad.')
