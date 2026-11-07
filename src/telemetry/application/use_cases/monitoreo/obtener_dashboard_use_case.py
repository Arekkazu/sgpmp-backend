# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-23 | destroyerban | DEV-39 RF-58: vista por permiso, GRIS sin umbral y anomalías visibles |
# | 2026-10-25 | Arekkazu | USAB-M03 M3-08 RF-58: conteo del semáforo sobre todos los sensores, no la página |
# | 2026-10-26 | Leandro | ISSUE-678 G87 RF-58: conservar la referencia válida y adaptar la condición posterior al permiso técnico. |
# | 2026-10-28 | destroyerban | INC-M03-177-G57B RF-58: conteo del semáforo sin repetir la consulta de estados |
# | 2026-10-28 | destroyerban | INC-M03-178-G57B RF-57: alertas vencidas sin atención en el dashboard |
# | 2026-10-29 | Arekkazu | INC-M03-211-G98 RF-58: panel integrado de alertas activas |
# | 2026-10-31 | Claude | INC-M03-247-G92 RF-58: estado general de la unidad con todos sus sensores, no la página |
# | 2026-10-31 | Claude | INC-M03-246-G88 RF-58: semáforo con la última lectura, el umbral vigente y su tolerancia T |
from __future__ import annotations

import logging
from collections import Counter
from typing import Optional

from src.telemetry.domain.entities.monitoreo import (
    CALIDADES_CON_VALOR_SEMAFORO,
    EstadoSensorActual,
    ResumenUnidadProductiva,
    SemaforoBaseSensor,
    SemaforoCalculator,
)
from src.telemetry.domain.entities.indicadores_alertas import AlertaActivaPanel, FiltroIndicadoresAlertas
from src.telemetry.domain.repositories.aviso_sin_umbral_port import AvisoSinUmbralPort
from src.telemetry.domain.repositories.indicadores_alertas_repository import IndicadoresAlertasRepository
from src.telemetry.domain.repositories.monitoreo_repository import MonitoreoRepository

logger = logging.getLogger(__name__)

# R2 / E2: lecturas que llegan al panel (DB-12) pero no son valores operativos normales.
_ANOMALIAS = ('FUERA_DE_RANGO', 'ERROR_CALIBRACION')
ETIQUETA_SIN_UMBRAL = 'Sin umbral configurado'
ETIQUETA_REQUIERE_CALIBRACION = 'Requiere calibración'
ETIQUETA_EN_REVISION = 'En revisión técnica'
ETIQUETA_FUERA_DE_RANGO = 'Lectura fuera de rango'


class ObtenerDashboardUseCase:
    """RF-58 — CU04 Flujo principal pasos 1–7.

    Lee el estado actual de sensores desde `estados_actuales_sensores` y
    aplica las reglas de negocio del semáforo antes de devolver los datos.
    No modifica la telemetría; lo único que puede escribir es el aviso de E7.
    """

    def __init__(
        self,
        monitoreo_repo: MonitoreoRepository,
        aviso_sin_umbral: Optional[AvisoSinUmbralPort] = None,
        indicadores_alertas: Optional[IndicadoresAlertasRepository] = None,
    ) -> None:
        self.monitoreo_repo = monitoreo_repo
        self.aviso_sin_umbral = aviso_sin_umbral
        self.indicadores_alertas = indicadores_alertas
        # G92: execute y contar_semaforos usan el mismo alcance; una sola consulta por request.
        self._cache_semaforos: dict[tuple, list[SemaforoBaseSensor]] = {}

    def execute(
        self,
        id_infraestructura: Optional[int],
        pagina: int,
        por_pagina: int,
        *,
        ver_datos_tecnicos: bool,
        ids_fincas_permitidas: Optional[list[int]] = None,
    ) -> tuple[list[EstadoSensorActual], list[ResumenUnidadProductiva], int]:
        """``ver_datos_tecnicos``: el rol tiene R sobre ``datos_tecnicos_dashboard`` (DB-08).

        DEV-39: antes se decidía con ``id_rol == 2`` quemado; un rol personalizado de
        productor recibía batería y RSSI. Ahora lo resuelve el router por permiso.
        """
        sensores, total = self.monitoreo_repo.obtener_estados_sensores(
            id_infraestructura=id_infraestructura,
            pagina=pagina,
            por_pagina=por_pagina,
            ids_fincas_permitidas=ids_fincas_permitidas,
        )

        sin_umbral: list[EstadoSensorActual] = []
        for sensor in sensores:
            # E7 (DB-12): GRIS cuando ninguna especie del área tiene umbral activo para la
            # variable. G88: se mira el umbral vigente, no la caché de la última ingesta
            # (un umbral creado después ya cuenta). El GRIS por dato desactualizado (CA-5) es otro caso.
            sensor.sin_umbral = self._sin_umbral(sensor) and not sensor.dato_desactualizado
            sensor.estado_semaforo = self._calcular_semaforo_efectivo(sensor)
            self._marcar_estado(sensor, ver_datos_tecnicos)
            if sensor.sin_umbral:
                sin_umbral.append(sensor)

            # CA-8: sin el permiso de datos técnicos no se reciben datos del dispositivo
            if not ver_datos_tecnicos:
                sensor.nivel_bateria_pct = None
                sensor.calidad_senal_rssi = None
                sensor.calidad_senal_snr = None

        self._avisar_sin_umbral(sin_umbral)

        resumen = self.monitoreo_repo.obtener_resumen_unidades(
            ids_fincas_permitidas=ids_fincas_permitidas,
        )
        # #317: con filtro por área el cliente agrupa las tarjetas bajo su
        # unidad; devolver [] dejaba los KPIs bien y la vista sin tarjetas.
        if id_infraestructura is not None:
            resumen = [u for u in resumen if u.id_infraestructura == id_infraestructura]
        # G92: el estado general sale de TODOS los sensores de la unidad, con el mismo
        # semáforo efectivo de la vista. Con los de la página, una unidad de 60 sensores
        # con el único ROJO en la posición 55 se veía VERDE en la página 1 y ROJO en la 2.
        estados_por_unidad: dict[int, list[str]] = {}
        bases = self._semaforos_alcance(id_infraestructura, ids_fincas_permitidas) if resumen else []
        for base in bases:
            if base.id_infraestructura:
                estados_por_unidad.setdefault(base.id_infraestructura, []).append(
                    self._calcular_semaforo_efectivo(base))
        for unidad in resumen:
            estados = estados_por_unidad.get(unidad.id_infraestructura, [])
            if estados:
                unidad.estado_general = SemaforoCalculator.peor_semaforo(estados)

        return sensores, resumen, total

    def contar_semaforos(
        self,
        id_infraestructura: Optional[int],
        *,
        ids_fincas_permitidas: Optional[list[int]] = None,
    ) -> dict[str, int]:
        """M3-08: sensores por color (VERDE/AMARILLO/ROJO/GRIS) de todo el alcance.

        La vista trae a lo sumo 50 sensores (FA-07) y el front contaba esa página:
        "50 sensores" en un área de 200. Mismo semáforo efectivo que la vista.
        G57B: con el semáforo base de cada sensor, no con la consulta completa de estados.
        """
        todos = self._semaforos_alcance(id_infraestructura, ids_fincas_permitidas)
        return dict(Counter(self._calcular_semaforo_efectivo(s) for s in todos))

    def _semaforos_alcance(
        self,
        id_infraestructura: Optional[int],
        ids_fincas_permitidas: Optional[list[int]],
    ) -> list[SemaforoBaseSensor]:
        clave = (id_infraestructura, tuple(ids_fincas_permitidas) if ids_fincas_permitidas is not None else None)
        if clave not in self._cache_semaforos:
            self._cache_semaforos[clave] = self.monitoreo_repo.obtener_semaforos_sensores(
                id_infraestructura,
                ids_fincas_permitidas=ids_fincas_permitidas,
            )
        return self._cache_semaforos[clave]

    def contar_alertas_vencidas_sin_atencion(
        self,
        id_infraestructura: Optional[int],
        *,
        ids_fincas_permitidas: Optional[list[int]] = None,
    ) -> int:
        """G57B (RF-57 Salida 3): mismo indicador que GET /iot/alertas/indicadores, sin rango."""
        if self.indicadores_alertas is None:
            return 0
        return self.indicadores_alertas.contar_vencidas_sin_atencion(FiltroIndicadoresAlertas(
            id_infraestructura=id_infraestructura,
            ids_fincas_permitidas=ids_fincas_permitidas,
        ))

    def panel_alertas_activas(
        self,
        id_infraestructura: Optional[int],
        *,
        ids_fincas_permitidas: Optional[list[int]] = None,
        limite: int = 50,
    ) -> tuple[list[AlertaActivaPanel], int]:
        """RF-58 CU04 salida 2 / CA-11: alertas ACTIVA de RF-57, CRITICO primero, con su total."""
        if self.indicadores_alertas is None:
            return [], 0
        return self.indicadores_alertas.listar_activas(FiltroIndicadoresAlertas(
            id_infraestructura=id_infraestructura,
            ids_fincas_permitidas=ids_fincas_permitidas,
        ), limite)

    @staticmethod
    def _calcular_semaforo_efectivo(sensor: EstadoSensorActual | SemaforoBaseSensor) -> str:
        # CA-5: sensor sin datos recientes → GRIS (FA-05)
        if sensor.dato_desactualizado:
            return 'GRIS'

        estado = ObtenerDashboardUseCase._semaforo_base(sensor)

        # CA-4: alerta CRITICA activa → ROJO; alerta activa → al menos AMARILLO
        tiene_critica = sensor.severidad_alerta == 'CRITICO'
        tiene_activa = sensor.id_alerta is not None
        return SemaforoCalculator.aplicar_reglas_alerta(estado, tiene_critica, tiene_activa)

    @staticmethod
    def _sin_umbral(sensor: EstadoSensorActual | SemaforoBaseSensor) -> bool:
        if sensor.umbrales_vigentes is None:  # sin lectura: lo que dejó la caché
            return sensor.estado_semaforo == 'GRIS'
        return not sensor.umbrales_vigentes

    @staticmethod
    def _semaforo_base(sensor: EstadoSensorActual | SemaforoBaseSensor) -> str:
        """G88 (RF-58 Fase 3): color de la última lectura contra el umbral vigente.

        La caché ``estados_actuales_sensores`` guarda VERDE al ingerir (el trigger no
        evalúa RF-17): una lectura FUERA_DE_RANGO seguía VERDE y un cambio de umbral no
        recalculaba nada. Ahora el color sale en cada consulta de la última lectura
        (válida o fuera de rango) con el umbral de hoy y su tolerancia T. ERROR_CALIBRACION
        no trae un valor confiable: conserva lo que dejó la caché.
        """
        if sensor.umbrales_vigentes is None:
            return sensor.estado_semaforo or 'GRIS'
        if not sensor.umbrales_vigentes:
            return 'GRIS'
        if (sensor.valor_condicion_actual is None
                or sensor.calidad_condicion_actual not in CALIDADES_CON_VALOR_SEMAFORO):
            return sensor.estado_semaforo or 'GRIS'
        return SemaforoCalculator.calcular_con_umbrales(sensor.valor_condicion_actual, sensor.umbrales_vigentes)

    @staticmethod
    def _marcar_estado(sensor: EstadoSensorActual, ver_datos_tecnicos: bool) -> None:
        """R2 / E2 / E7: indicador y etiqueta de lo que no es un valor operativo normal.

        Nada se oculta del panel (R2: "no deben ser descartados ni ocultados"). En
        ERROR_CALIBRACION el diagnóstico solo lo ve el permiso técnico. La última
        lectura válida puede seguir como referencia para ambos permisos; el dato
        inválido no pasa a ser un valor operativo.
        """
        if sensor.estado_calidad in _ANOMALIAS:
            sensor.indicador_anomalia = True
            sensor.es_valor_operativo = (
                sensor.estado_calidad_valor_operativo == 'LECTURA_VALIDA'
                and sensor.ultimo_valor is not None
            )
            if sensor.estado_calidad == 'ERROR_CALIBRACION':
                if ver_datos_tecnicos:
                    sensor.etiqueta_estado = ETIQUETA_REQUIERE_CALIBRACION
                else:
                    sensor.etiqueta_estado = ETIQUETA_EN_REVISION
                    # El aviso genérico no expone el diagnóstico reservado al permiso técnico.
                    sensor.estado_calidad = None
                    sensor.valor_condicion_actual = None
                    if not sensor.es_valor_operativo:
                        sensor.ultimo_valor = None
            else:
                sensor.etiqueta_estado = ETIQUETA_FUERA_DE_RANGO
        elif sensor.sin_umbral:
            sensor.etiqueta_estado = ETIQUETA_SIN_UMBRAL

    def _avisar_sin_umbral(self, sensores: list[EstadoSensorActual]) -> None:
        # G57B: el router inyecta el aviso en segundo plano; el GET no espera al SMTP.
        if not sensores or self.aviso_sin_umbral is None:
            return
        try:
            self.aviso_sin_umbral.avisar(sensores)
        except Exception:  # el dashboard responde igual aunque el aviso falle
            logger.exception('RF-58 E7: no se pudo avisar de las variables sin umbral')
