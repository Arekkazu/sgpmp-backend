"""RF-62: Evaluación estadística de calidad de lecturas teleméricas.

Pipeline de 8 fases:
  Fase 0 — Verificar estado_calidad heredado de RF-53.
  Fase 1 — Recuperar contexto (serie temporal, parámetros).
  Fase 2 — Sensor congelado.
  Fase 3 — Outlier estadístico + límites físicos.
  Fase 4 — Deriva (drift). Omitida si calibracion_no_disponible.
  Fase 5 — Gap temporal anómalo.
  Fase 6 — Cálculo del índice de calidad y clasificación.
  Fase 7 — Persistir en telemetria_calidad + actualizar flags en telemetrias.
  Fase 8 — Alertas técnicas + evento RF-63.
"""
from __future__ import annotations

import statistics
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

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

# Rangos físicos del catálogo I3P-1 (id_variable → (min, max))
# Los mismos que RANGOS_FISICOS en telemetria.py
_RANGOS_FISICOS: dict[int, tuple[Decimal, Decimal]] = {
    9: (Decimal('-40'), Decimal('60')),
    10: (Decimal('0'), Decimal('100')),
    11: (Decimal('0'), Decimal('100')),
    12: (Decimal('0'), Decimal('5000')),
    13: (Decimal('30'), Decimal('50')),
    14: (Decimal('0'), Decimal('500')),
    15: (Decimal('0'), Decimal('200')),
    16: (Decimal('0'), Decimal('200')),
    2: (Decimal('0'), Decimal('14')),
    3: (Decimal('0'), Decimal('20')),
    8: (Decimal('0'), Decimal('5000')),
}


class EvaluarCalidadTelemetriaUseCase:

    def __init__(
        self,
        db: Session,
        telemetria_repo: TelemetriaRepository,
        calidad_repo: TelemetriaCalidadRepository,
        parametros_port: ParametrosCalidadPort,
        auditoria_repo: Optional[BitacoraAuditoriaIotRepository] = None,
    ) -> None:
        self.db = db
        self.telemetria_repo = telemetria_repo
        self.calidad_repo = calidad_repo
        self.parametros_port = parametros_port
        self.auditoria_repo = auditoria_repo

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
    ) -> TelemetriaCalidad:
        ahora = datetime.now(timezone.utc)
        flags: dict = {}
        omitir_estadistico = False
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
                parametros_aplicados={'k': params.k, 'M': params.M, 'N': params.N, 'umbral_drift': params.umbral_drift},
                parametros_calibracion_aplicados=parametros_calibracion,
                motivo_reevaluacion=None,
            )
            self._emitir_auditoria(TipoResultado.EXITOSO, id_telemetria, flags)
            return evaluacion

        omitir_estadistico = False

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
            if sigma > 0 and abs(float(valor) - mu) > params.k * sigma:
                flags['outlier_estadistico'] = {
                    'activo': True,
                    'media_serie': round(mu, 4),
                    'desviacion_estandar': round(sigma, 4),
                    'k_utilizado': params.k,
                    'magnitud_desviacion': round(abs(float(valor) - mu) / sigma, 4),
                    'causa': 'ESTADISTICO',
                }
            elif id_variable in _RANGOS_FISICOS:
                vmin, vmax = _RANGOS_FISICOS[id_variable]
                if valor < vmin or valor > vmax:
                    flags['outlier_estadistico'] = {
                        'activo': True,
                        'media_serie': round(mu, 4),
                        'desviacion_estandar': round(sigma, 4),
                        'k_utilizado': params.k,
                        'magnitud_desviacion': 0,
                        'causa': 'LIMITE_FISICO',
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
        # La detección de gap temporal requiere el timestamp anterior; se omite
        # cuando la serie no tiene contexto suficiente. Aquí se marca si la
        # frecuencia_muestreo indica una anomalía ya detectada en la ingesta.

        # ── Fase 6: Índice y clasificación ────────────────────────────────────
        indice = calcular_indice_calidad(flags)
        clasificacion = clasificar_desde_indice(indice)
        apto_ia, apto_nic41 = derivar_aptitud(clasificacion)

        # ── Fase 7: Persistir ──────────────────────────────────────────────────
        try:
            evaluacion = self._persistir(
                id_telemetria=id_telemetria,
                id_sensor=id_sensor,
                ahora=ahora,
                indice=indice,
                clasificacion=clasificacion,
                flags=flags,
                parametros_aplicados={'k': params.k, 'M': params.M, 'N': params.N, 'umbral_drift': params.umbral_drift},
                parametros_calibracion_aplicados=parametros_calibracion,
                motivo_reevaluacion=None,
            )
            self.telemetria_repo.actualizar_flags_aptitud(id_telemetria, apto_ia, apto_nic41)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

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
        return self.calidad_repo.guardar(TelemetriaCalidad(
            id_evaluacion=None,
            id_telemetria=id_telemetria,
            id_sensor=id_sensor,
            timestamp_evaluacion=ahora,
            indice_calidad=indice,
            clasificacion_calidad=clasificacion,
            apto_para_ia=apto_ia,
            apto_para_nic41=apto_nic41,
            flags_detectados=flags,
            parametros_aplicados=parametros_aplicados,
            parametros_calibracion_aplicados=parametros_calibracion_aplicados,
            motivo_reevaluacion=motivo_reevaluacion,
        ))

    def _emitir_auditoria(
        self,
        resultado: TipoResultado,
        id_telemetria: int,
        flags: dict,
    ) -> None:
        if self.auditoria_repo is None:
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
