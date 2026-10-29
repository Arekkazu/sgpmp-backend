# | Fecha      | Nombre           | Que se hizo                                   |
# |------------|------------------|-----------------------------------------------|
# | 2026-10-22 | Arekkazu         | M05 RF-81: niveles de volumen y 202 automático |
"""Caso de uso: consultar el historial/trazabilidad de suministros (RF-81).

Solo lectura. Aplica el alcance por fincas vía :class:`AlcanceActivoPort` (E2,
403) y valida la combinación de filtros (E5, 422). Según el volumen histórico
del activo (Restricción 11):

- Nivel 1-2: consulta síncrona.
- Nivel 3: síncrona con límite de 10 s; con más de 3 filtros, o si supera el
  límite, pasa sola a modo asíncrono (E7, 202 con ``id_consulta_asincrona``).
- Nivel 4: asíncrona siempre (202).

La respuesta 202 trae ``info_nivel_volumen`` (CA-17). Registra
``CONSULTA_HISTORIAL_EJECUTADA`` en la bitácora de M05 (RF-80) sin bloquear la
respuesta si la auditoría falla.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, Union

from sqlalchemy.orm import Session

from src.shared.errors import AuthorizationError, BusinessRuleError, NotFoundError
from src.supplies.domain.entities.historial_suministro import (
    FiltrosHistorialSuministro,
    LineaHistorialSuministro,
    ResumenConsultaHistorial,
)
from src.supplies.domain.entities.trabajo_historial_suministro import TrabajoHistorialSuministro
from src.supplies.domain.repositories.activo_consulta_port import ActivoConsultaPort
from src.supplies.domain.repositories.alcance_activo_port import AlcanceActivoPort
from src.supplies.domain.repositories.auditoria_suministro_port import (
    AuditoriaSuministroPort,
    EventoAuditoriaSuministro,
)
from src.supplies.domain.repositories.configuracion_batch_historial_repository import (
    ConfiguracionBatchHistorialRepository,
)
from src.supplies.domain.repositories.historial_suministro_read_port import (
    ConsultaExcedioTiempo,
    HistorialSuministroReadPort,
)
from src.supplies.domain.value_objects.historial_suministro_enums import (
    TIEMPO_ESTIMADO_SEGUNDOS,
    NivelVolumen,
    TipoTrabajoHistorial,
    nivel_volumen,
)

logger = logging.getLogger(__name__)

_TIEMPO_LIMITE_NIVEL3_SEGUNDOS = 10
_MAX_FILTROS_SINCRONOS = 3


@dataclass(frozen=True)
class ResultadoConsultaHistorial:
    lineas: list[LineaHistorialSuministro]
    resumen: ResumenConsultaHistorial


@dataclass(frozen=True)
class ConsultaHistorialAsincrona:
    """RF-81 E7 / CA-17: la consulta se procesa en segundo plano."""

    trabajo: TrabajoHistorialSuministro
    nivel: NivelVolumen
    total_registros_activo: int

    @property
    def tiempo_estimado_segundos(self) -> int:
        return TIEMPO_ESTIMADO_SEGUNDOS.get(self.nivel, 60)

    @property
    def mensaje(self) -> str:
        return (
            f"La consulta sobre el activo con {self.total_registros_activo} registros (nivel {self.nivel.value}) "
            "supera el límite de procesamiento sincrónico y se procesará de forma asíncrona. El resultado estará "
            f"disponible en ≤ {self.tiempo_estimado_segundos} segundos; recibirá una notificación. Consulte el "
            f"estado con id_consulta_asincrona={self.trabajo.id_cola}."
        )


class ConsultarHistorialSuministrosUseCase:
    def __init__(
        self,
        historial_port: HistorialSuministroReadPort,
        alcance_port: AlcanceActivoPort,
        activo_port: ActivoConsultaPort,
        config_repo: ConfiguracionBatchHistorialRepository,
        db: Session,
        auditoria_port: AuditoriaSuministroPort,
        solicitar: Optional[object] = None,
    ) -> None:
        self.historial_port = historial_port
        self.alcance_port = alcance_port
        self.activo_port = activo_port
        self.config_repo = config_repo
        self.db = db
        self.auditoria_port = auditoria_port
        self.solicitar = solicitar

    def execute(
        self, filtros: FiltrosHistorialSuministro, *, id_usuario: int, id_rol: int
    ) -> Union[ResultadoConsultaHistorial, ConsultaHistorialAsincrona]:
        ids_permitidos = self._validar(filtros, id_usuario, id_rol)

        config = self.config_repo.obtener()
        total_historico = self.historial_port.contar_total_activo(filtros.id_activo_biologico)
        nivel = nivel_volumen(total_historico, config.umbral_nivel3, config.umbral_nivel4)

        if nivel == NivelVolumen.NIVEL_4 or (
            nivel == NivelVolumen.NIVEL_3 and filtros.cantidad_filtros > _MAX_FILTROS_SINCRONOS
        ):
            return self._asincrona(filtros, id_usuario, id_rol, nivel, total_historico)

        limite = _TIEMPO_LIMITE_NIVEL3_SEGUNDOS if nivel == NivelVolumen.NIVEL_3 else None
        try:
            resultado = self.historial_port.consultar(filtros, ids_permitidos, tiempo_limite_segundos=limite)
        except ConsultaExcedioTiempo:
            return self._asincrona(filtros, id_usuario, id_rol, nivel, total_historico)
        return self._resultado(filtros, resultado, nivel, id_usuario)

    def consultar_forzado(
        self, filtros: FiltrosHistorialSuministro, *, id_usuario: int, id_rol: int
    ) -> ResultadoConsultaHistorial:
        """Usado por el worker del motor async (trabajo CONSULTA_PESADA): sin gate de nivel."""
        ids_permitidos = self._validar(filtros, id_usuario, id_rol)
        config = self.config_repo.obtener()
        total_historico = self.historial_port.contar_total_activo(filtros.id_activo_biologico)
        nivel = nivel_volumen(total_historico, config.umbral_nivel3, config.umbral_nivel4)
        resultado = self.historial_port.consultar(filtros, ids_permitidos)
        return self._resultado(filtros, resultado, nivel, id_usuario)

    # ── Auxiliares ───────────────────────────────────────────────────────────
    def _validar(self, filtros: FiltrosHistorialSuministro, id_usuario: int, id_rol: int) -> Optional[list[int]]:
        self._validar_filtros(filtros)

        activo = self.activo_port.obtener(filtros.id_activo_biologico)
        if activo is None:
            raise NotFoundError(
                code="ACTIVO_NO_ENCONTRADO",
                message=f"El activo biológico {filtros.id_activo_biologico} no existe.",
                field="id_activo_biologico",
            )

        ids_permitidos = self.alcance_port.listar_ids_activos_permitidos(id_usuario, id_rol)
        if ids_permitidos is not None and filtros.id_activo_biologico not in ids_permitidos:
            raise AuthorizationError(
                code="ACCESO_DENEGADO",
                message=(
                    f"No tiene permisos para consultar el historial del activo {filtros.id_activo_biologico}. "
                    "Verifique su rol y unidades productivas asignadas."
                ),
            )
        return ids_permitidos

    def _asincrona(self, filtros, id_usuario: int, id_rol: int, nivel: NivelVolumen,
                   total: int) -> ConsultaHistorialAsincrona:
        trabajo = self.solicitar.execute(TipoTrabajoHistorial.CONSULTA_PESADA.value, filtros, id_usuario, id_rol)
        return ConsultaHistorialAsincrona(trabajo=trabajo, nivel=nivel, total_registros_activo=total)

    def _resultado(self, filtros, resultado, nivel: NivelVolumen, id_usuario: int) -> ResultadoConsultaHistorial:
        total_paginas = max(1, -(-resultado.total_registros_filtrados // filtros.registros_por_pagina))
        resumen = ResumenConsultaHistorial(
            total_registros_filtrados=resultado.total_registros_filtrados,
            monto_total_filtrado=resultado.monto_total_filtrado,
            desglose_por_tipo_suministro=resultado.desglose_por_tipo_suministro,
            desglose_por_ciclo=resultado.desglose_por_ciclo,
            pagina_actual=filtros.pagina,
            total_paginas=total_paginas,
            datos_contexto_no_disponibles=False,
            datos_actualizados_hasta=datetime.now(timezone.utc),
            nivel_volumen=nivel.value,
            mensaje=(
                None if resultado.total_registros_filtrados else
                "No se encontraron registros de suministros con los filtros aplicados para el activo "
                f"{filtros.id_activo_biologico}."
            ),
        )
        self._auditar_consulta(filtros, id_usuario)
        return ResultadoConsultaHistorial(lineas=resultado.lineas, resumen=resumen)

    def _auditar_consulta(self, filtros: FiltrosHistorialSuministro, id_usuario: int) -> None:
        try:
            self.auditoria_port.registrar(
                EventoAuditoriaSuministro(
                    entidad_afectada="historial_suministros",
                    tipo_operacion="CONSULTA_HISTORIAL_EJECUTADA",
                    id_usuario=id_usuario,
                    resultado="EXITOSO",
                    id_activo_biologico=filtros.id_activo_biologico,
                    id_ciclo_productivo=filtros.id_ciclo_productivo,
                )
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            logger.exception("Error al auditar CONSULTA_HISTORIAL_EJECUTADA para activo %s", filtros.id_activo_biologico)

    def _validar_filtros(self, filtros: FiltrosHistorialSuministro) -> None:
        """Restricción 7 / E5: un 422 por cada conflicto, con el conflicto en el mensaje."""
        if (
            filtros.fecha_inicio_filtro is not None
            and filtros.fecha_fin_filtro is not None
            and filtros.fecha_fin_filtro < filtros.fecha_inicio_filtro
        ):
            raise BusinessRuleError(
                code="COMBINACION_FILTROS_INVALIDA",
                message=(
                    f"Combinación de filtros inválida: fecha_fin_filtro ({filtros.fecha_fin_filtro}) es anterior a "
                    f"fecha_inicio_filtro ({filtros.fecha_inicio_filtro})."
                ),
                field="fecha_fin_filtro",
            )
        if filtros.costo_min is not None and filtros.costo_max is not None and filtros.costo_max < filtros.costo_min:
            raise BusinessRuleError(
                code="COMBINACION_FILTROS_INVALIDA",
                message=(
                    f"Combinación de filtros inválida: costo_max ({filtros.costo_max}) es menor que costo_min "
                    f"({filtros.costo_min})."
                ),
                field="costo_max",
            )
        if filtros.id_ciclo_productivo is not None and not self.historial_port.ciclo_pertenece_a_activo(
            filtros.id_activo_biologico, filtros.id_ciclo_productivo
        ):
            raise BusinessRuleError(
                code="CICLO_NO_PERTENECE_AL_ACTIVO",
                message=(
                    f"Combinación de filtros inválida: el ciclo productivo {filtros.id_ciclo_productivo} no "
                    f"pertenece al activo {filtros.id_activo_biologico}."
                ),
                field="id_ciclo_productivo",
            )
