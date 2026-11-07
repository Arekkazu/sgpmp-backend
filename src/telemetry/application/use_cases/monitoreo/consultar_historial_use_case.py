# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-23 | destroyerban | DEV-38 RF-59: zona horaria, truncado con aviso, bitácora y vacíos temporales |
# | 2026-10-23 | Arekkazu | PR-667: fechas en UTC y día calendario en la zona del usuario (X-Zona-Horaria) |
# | 2026-10-26 | Arekkazu | INC-M03 lote 26-10 RF-59: E2 en 422, combinaciones R12, alertas, series y estado vacío E3 |
# | 2026-10-31 | Arekkazu | USAB-M03-M04 M3-09/N-06 RF-59: semáforo y % en rango con el umbral de la especie del área |
# | 2026-10-31 | Arekkazu | TC-DIS-160 RF-59: más de 90 días solo con filtro de variable, sensor o especie |
# | 2026-10-31 | Claude | INC-M03-246-G88 RF-58/59: mismo semáforo que el dashboard (bandas RF-17 + tolerancia T) |
from __future__ import annotations

from dataclasses import asdict
from typing import Optional

from src.shared.errors import BusinessRuleError
from src.shared.fechas import hoy_usuario
from src.telemetry.application.use_cases.auditoria.registrar_evento_auditoria_iot_use_case import (
    RegistrarEventoAuditoriaIotUseCase,
)
from src.telemetry.domain.entities.evento_auditoria_iot import (
    ComponenteOrigen,
    EntidadAfectadaTipo,
    SeveridadLog,
    TipoResultado,
)
from src.telemetry.domain.entities.monitoreo import (
    FiltrosHistorial,
    LecturaHistorica,
    describir_combinaciones_validas,
    ResumenEstadistico,
    SemaforoCalculator,
    VacioTemporal,
)
from src.telemetry.domain.repositories.historial_telemetria_repository import HistorialTelemetriaRepository
from src.telemetry.domain.repositories.umbral_historico_port import UmbralHistoricoPort

_MAX_DIAS_SIN_FILTRO = 90
_MAX_REGISTROS = 10_000

#: RF-59 E3: estado vacío con orientación, no error.
MENSAJE_SIN_RESULTADOS = (
    'No se encontraron registros para los filtros seleccionados. '
    'Amplíe el rango de fechas o modifique los filtros.'
)


class ConsultarHistorialUseCase:
    """RF-59 — CU04 Flujo principal pasos 8–9.

    No modifica la telemetría (postcondición 1). Lo único que escribe es el evento de
    la consulta en la bitácora de RF-63 (Fase 8, CA-16), si se inyecta ``auditoria``.
    """

    def __init__(
        self,
        historial_repo: HistorialTelemetriaRepository,
        umbral_port: UmbralHistoricoPort,
        auditoria: Optional[RegistrarEventoAuditoriaIotUseCase] = None,
    ) -> None:
        self.historial_repo = historial_repo
        self.umbral_port = umbral_port
        self.auditoria = auditoria

    def execute(
        self,
        filtros: FiltrosHistorial,
        *,
        id_usuario: Optional[int] = None,
        id_rol: Optional[int] = None,
    ) -> tuple[list[LecturaHistorica], list[ResumenEstadistico], int, dict]:
        # Fase 2 / E2: todo parámetro inválido responde 422 (INC-M03-180-G111).
        self._validar_fechas(filtros)
        self._validar_combinacion(filtros)
        self._validar_rango(filtros)
        self._validar_variables(filtros)

        lecturas, total = self.historial_repo.consultar(filtros)

        # E6 / CA-19 (DEV-38): más de _MAX_REGISTROS ya no es 422. Se devuelven los
        # primeros _MAX_REGISTROS (según el orden pedido) con aviso de truncado; las
        # páginas posteriores a ese tope llegan vacías.
        truncado = total > _MAX_REGISTROS
        if truncado:
            disponibles = _MAX_REGISTROS - (filtros.pagina - 1) * filtros.por_pagina
            lecturas = lecturas[:max(0, disponibles)]

        # Calcular semáforo histórico contra umbral vigente en timestamp_captura (CA-4, CA-21)
        for lectura in lecturas:
            lectura.estado_semaforo_historico = self._semaforo_historico(lectura)

        estadisticas = self.historial_repo.calcular_estadisticas(filtros)
        # E7 / CA-17: vacíos sobre todo el rango filtrado, no solo la página.
        vacios = self.historial_repo.detectar_vacios(filtros)

        metadatos = self._build_metadatos(filtros, total, lecturas, truncado, vacios)
        metadatos['series'] = self._series(lecturas)
        metadatos['alertas_correlacionadas'] = (
            [asdict(a) for a in self.historial_repo.alertas_correlacionadas(filtros)]
            if filtros.incluir_alertas else []
        )
        self._auditar(filtros, metadatos, len(lecturas), id_usuario, id_rol)
        return lecturas, estadisticas, min(total, _MAX_REGISTROS), metadatos

    # ------------------------------------------------------------------
    # Validaciones
    # ------------------------------------------------------------------

    @staticmethod
    def _validar_fechas(filtros: FiltrosHistorial) -> None:
        # E2 (DEV-38): "hoy" es el día en la zona del usuario; date.today() dependía de la zona del servidor.
        hoy = hoy_usuario()
        if filtros.fecha_inicio > filtros.fecha_fin:
            raise BusinessRuleError(
                code='FECHA_INICIO_POSTERIOR',
                message='fecha_inicio no puede ser posterior a fecha_fin.',
                field='fecha_inicio',
            )
        if filtros.fecha_fin > hoy:
            raise BusinessRuleError(
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
                    f'Agregue al menos un filtro de variable, sensor o especie.'
                ),
            )

    @staticmethod
    def _validar_combinacion(filtros: FiltrosHistorial) -> None:
        # Restricción 12 (INC-M03-184-G113): se rechaza sin ejecutar la consulta.
        if not filtros.combinacion_valida():
            presentes = ' + '.join(['fechas', *sorted(filtros.filtros_presentes())])
            raise BusinessRuleError(
                code='COMBINACION_FILTROS_INVALIDA',
                message=(
                    f'La combinación de filtros ({presentes}) no es válida. '
                    f'Combinaciones permitidas: {describir_combinaciones_validas()}.'
                ),
            )

    def _validar_variables(self, filtros: FiltrosHistorial) -> None:
        # INC-M03-181-G112: una variable desconocida ya no devuelve 0 lecturas sin aviso.
        if not filtros.tipo_variable:
            return
        desconocidas = self.historial_repo.variables_no_reconocidas(filtros.tipo_variable)
        if desconocidas:
            raise BusinessRuleError(
                code='TIPO_VARIABLE_INVALIDO',
                message=(
                    f"tipo_variable no reconocido: {', '.join(desconocidas)}. Use el código de la variable "
                    "(p. ej. TEMPERATURA_AMBIENTAL) o su nombre en el catálogo."
                ),
                field='tipo_variable',
            )

    # ------------------------------------------------------------------
    # Semáforo histórico
    # ------------------------------------------------------------------

    def _semaforo_historico(self, lectura: LecturaHistorica) -> str:
        if lectura.valor is None:
            return 'GRIS'

        if lectura.id_especie is not None:
            umbral = self.umbral_port.obtener_umbral_vigente(
                id_variable_ambiental=lectura.id_variable,
                id_especie=lectura.id_especie,
                timestamp=lectura.timestamp_captura,
            )
        else:
            # M3-09 / N-06: una lectura ambiental sin activo vinculado salía GRIS ("Sin
            # datos") aunque el área tiene umbral; se usa la especie del área.
            umbral = self.umbral_port.obtener_umbral_vigente_area(
                id_variable_ambiental=lectura.id_variable,
                id_infraestructura=lectura.id_infraestructura,
                timestamp=lectura.timestamp_captura,
            )
        if umbral is None:
            return 'GRIS'

        lectura.id_umbral_ambiental = umbral['id_umbral_ambiental']
        lectura.valor_min_umbral = umbral['umbral_min']
        lectura.valor_max_umbral = umbral['umbral_max']
        lectura.version_umbral = umbral['version']

        # G88: misma regla que el dashboard (RF-58 Fase 3) para que ambos coincidan.
        return SemaforoCalculator.calcular_rf58(
            valor=lectura.valor,
            valor_min=umbral['umbral_min'],
            valor_max=umbral['umbral_max'],
            niveles=umbral['niveles'],
            tolerancia=umbral.get('tolerancia_semaforo'),
        )

    @staticmethod
    def _series(lecturas: list[LecturaHistorica]) -> list[dict]:
        """Fase 5 / Salida 3 / CA-9: una serie por variable, sobre el mismo eje temporal,
        con sus pares (timestamp, valor, semáforo) y el umbral de referencia."""
        series: dict[str, dict] = {}
        for lectura in sorted(lecturas, key=lambda l: l.timestamp_captura):
            serie = series.setdefault(lectura.tipo_variable, {
                'tipo_variable': lectura.tipo_variable,
                'unidad_medida': lectura.unidad_medida,
                'umbral_min': None,
                'umbral_max': None,
                'puntos': [],
            })
            if lectura.valor_min_umbral is not None:
                serie['umbral_min'], serie['umbral_max'] = lectura.valor_min_umbral, lectura.valor_max_umbral
            serie['puntos'].append({
                'timestamp_captura': lectura.timestamp_captura,
                'valor': lectura.valor,
                'estado_semaforo_historico': lectura.estado_semaforo_historico,
                'id_sensor': lectura.id_sensor,
            })
        return list(series.values())

    # ------------------------------------------------------------------
    # Metadatos de respuesta
    # ------------------------------------------------------------------

    @staticmethod
    def _build_metadatos(
        filtros: FiltrosHistorial,
        total: int,
        lecturas: list[LecturaHistorica],
        truncado: bool,
        vacios: list[VacioTemporal],
    ) -> dict:
        timestamps = [l.timestamp_captura for l in lecturas if l.timestamp_captura]
        navegables = min(total, _MAX_REGISTROS)
        return {
            'total_registros': navegables,
            'total_encontrado': total,
            'truncado': truncado,
            'aviso': (
                f'La consulta encontró {total} registros y supera el límite de {_MAX_REGISTROS}: '
                f'se muestran los primeros {_MAX_REGISTROS}. Aplique filtros adicionales (variable, '
                'sensor, unidad productiva o especie) o acorte el rango de fechas para ver el resto.'
            ) if truncado else (MENSAJE_SIN_RESULTADOS if total == 0 else None),
            'pagina_actual': filtros.pagina,
            'total_paginas': max(1, -(-navegables // filtros.por_pagina)),  # ceil division
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
                'id_activo_biologico': filtros.id_activo_biologico,
                'incluir_alertas': filtros.incluir_alertas,
            },
            'rango_real_datos': {
                'primer_timestamp': min(timestamps).isoformat() if timestamps else None,
                'ultimo_timestamp': max(timestamps).isoformat() if timestamps else None,
            },
            'vacios_temporales': [asdict(v) for v in vacios],
        }

    # ------------------------------------------------------------------
    # Bitácora (Fase 8, postcondición 6, CA-16, E6)
    # ------------------------------------------------------------------

    def _auditar(
        self,
        filtros: FiltrosHistorial,
        metadatos: dict,
        registros_devueltos: int,
        id_usuario: Optional[int],
        id_rol: Optional[int],
    ) -> None:
        """Una constancia por consulta (best-effort: RF-63 no propaga sus fallos).

        Un resultado truncado queda como ADVERTENCIA/WARNING para el análisis de
        rendimiento de E6.
        """
        if self.auditoria is None:
            return
        truncado = metadatos['truncado']
        self.auditoria.execute(
            tipo_evento='HISTORIAL_CONSULTADO',
            resultado=TipoResultado.ADVERTENCIA if truncado else TipoResultado.EXITOSO,
            componente_origen=ComponenteOrigen.RF59,
            severidad_log=SeveridadLog.WARNING if truncado else SeveridadLog.INFO,
            descripcion=(
                f'Consulta de historial: {registros_devueltos} registros devueltos de '
                f'{metadatos["total_encontrado"]} encontrados' + (' (truncado).' if truncado else '.')
            ),
            entidad_afectada_tipo=EntidadAfectadaTipo.LECTURA,
            id_usuario=id_usuario,
            accion_detallada={
                'id_usuario': id_usuario,
                'id_rol': id_rol,
                'filtros': metadatos['filtros_aplicados'],
                'pagina': filtros.pagina,
                'por_pagina': filtros.por_pagina,
                'registros_devueltos': registros_devueltos,
                'total_encontrado': metadatos['total_encontrado'],
                'truncado': truncado,
                'vacios_temporales': len(metadatos['vacios_temporales']),
                'exportado': False,
            },
        )
