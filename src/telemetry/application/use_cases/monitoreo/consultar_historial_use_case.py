from __future__ import annotations

from datetime import date, timezone

from src.shared.errors import BusinessRuleError, ValidationError
from src.telemetry.domain.entities.monitoreo import (
    FiltrosHistorial,
    LecturaHistorica,
    ResumenEstadistico,
    SemaforoCalculator,
)
from src.telemetry.domain.repositories.historial_telemetria_repository import HistorialTelemetriaRepository
from src.telemetry.domain.repositories.umbral_historico_port import UmbralHistoricoPort

_MAX_DIAS_SIN_FILTRO = 90
_MAX_REGISTROS = 10_000


class ConsultarHistorialUseCase:
    """RF-59 — CU04 Flujo principal pasos 8–9.

    Solo lectura. No emite commit ni modifica datos.
    """

    def __init__(
        self,
        historial_repo: HistorialTelemetriaRepository,
        umbral_port: UmbralHistoricoPort,
    ) -> None:
        self.historial_repo = historial_repo
        self.umbral_port = umbral_port

    def execute(
        self, filtros: FiltrosHistorial
    ) -> tuple[list[LecturaHistorica], list[ResumenEstadistico], int, dict]:
        self._validar_fechas(filtros)
        self._validar_rango(filtros)
        self._validar_combinacion(filtros)

        lecturas, total = self.historial_repo.consultar(filtros)

        # FA-10 / CA-19: bloquear si supera volumen máximo
        if total > _MAX_REGISTROS:
            raise BusinessRuleError(
                code='VOLUMEN_EXCESIVO',
                message=(
                    f'La consulta recupera {total} registros, superando el límite de '
                    f'{_MAX_REGISTROS}. Aplique filtros adicionales para acotar el resultado.'
                ),
            )

        # Calcular semáforo histórico contra umbral vigente en timestamp_captura (CA-4, CA-21)
        for lectura in lecturas:
            lectura.estado_semaforo_historico = self._semaforo_historico(lectura)

        estadisticas = self.historial_repo.calcular_estadisticas(filtros)

        metadatos = self._build_metadatos(filtros, total, lecturas)
        return lecturas, estadisticas, total, metadatos

    # ------------------------------------------------------------------
    # Validaciones
    # ------------------------------------------------------------------

    @staticmethod
    def _validar_fechas(filtros: FiltrosHistorial) -> None:
        hoy = date.today()
        if filtros.fecha_inicio > filtros.fecha_fin:
            raise ValidationError(
                code='FECHA_INICIO_POSTERIOR',
                message='fecha_inicio no puede ser posterior a fecha_fin.',
                field='fecha_inicio',
            )
        if filtros.fecha_fin > hoy:
            raise ValidationError(
                code='FECHA_FIN_FUTURA',
                message='fecha_fin no puede ser posterior a la fecha actual.',
                field='fecha_fin',
            )

    @staticmethod
    def _validar_rango(filtros: FiltrosHistorial) -> None:
        dias = (filtros.fecha_fin - filtros.fecha_inicio).days
        if dias > _MAX_DIAS_SIN_FILTRO and not filtros.tiene_filtro_adicional():
            raise BusinessRuleError(
                code='RANGO_MAXIMO_EXCEDIDO',
                message=(
                    f'El rango máximo sin filtros adicionales es {_MAX_DIAS_SIN_FILTRO} días. '
                    f'Agregue al menos un filtro de variable, sensor, unidad productiva o especie.'
                ),
            )

    @staticmethod
    def _validar_combinacion(filtros: FiltrosHistorial) -> None:
        if not filtros.combinacion_valida():
            raise ValidationError(
                code='COMBINACION_FILTROS_INVALIDA',
                message='La combinación de filtros no es válida. fecha_inicio y fecha_fin son obligatorios.',
            )

    # ------------------------------------------------------------------
    # Semáforo histórico
    # ------------------------------------------------------------------

    def _semaforo_historico(self, lectura: LecturaHistorica) -> str:
        umbral = self.umbral_port.obtener_umbral_vigente(
            tipo_variable=lectura.tipo_variable,
            id_especie=None,  # id_especie no disponible por ahora (stub M09)
            timestamp=lectura.timestamp_captura,
        )
        if umbral is None:
            return 'GRIS'
        if lectura.valor is None:
            return 'GRIS'
        return SemaforoCalculator.calcular(
            valor=lectura.valor,
            umbral_min=umbral['umbral_min'],
            umbral_max=umbral['umbral_max'],
            tolerancia_pct=umbral.get('tolerancia_pct', 10.0),
        )

    # ------------------------------------------------------------------
    # Metadatos de respuesta
    # ------------------------------------------------------------------

    @staticmethod
    def _build_metadatos(filtros: FiltrosHistorial, total: int, lecturas: list[LecturaHistorica]) -> dict:
        timestamps = [l.timestamp_captura for l in lecturas if l.timestamp_captura]
        return {
            'total_registros': total,
            'pagina_actual': filtros.pagina,
            'total_paginas': max(1, -(-total // filtros.por_pagina)),  # ceil division
            'filtros_aplicados': {
                'fecha_inicio': filtros.fecha_inicio.isoformat(),
                'fecha_fin': filtros.fecha_fin.isoformat(),
                'sensor_id': filtros.sensor_id,
                'tipo_variable': filtros.tipo_variable,
                'categoria_variable': filtros.categoria_variable,
                'id_infraestructura': filtros.id_infraestructura,
                'especie': filtros.especie,
                'estado_dato': filtros.estado_dato,
                'origen_dato': filtros.origen_dato,
                'incluir_alertas': filtros.incluir_alertas,
            },
            'rango_real_datos': {
                'primer_timestamp': min(timestamps).isoformat() if timestamps else None,
                'ultimo_timestamp': max(timestamps).isoformat() if timestamps else None,
            },
        }
