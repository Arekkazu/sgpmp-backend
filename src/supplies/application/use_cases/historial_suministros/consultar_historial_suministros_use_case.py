"""Caso de uso: consultar el historial/trazabilidad de suministros (RF-81).

Solo lectura. Aplica el alcance por rol vía :class:`AlcanceActivoPort` (nunca
compara ``id_rol`` directamente — ver ``AlcanceActivoM02Adapter``) y enruta a
modo asíncrono cuando el volumen histórico del activo supera el umbral
síncrono (Restricción 11 / Nivel 3-4). Registra ``CONSULTA_HISTORIAL_EJECUTADA``
en la bitácora de auditoría de M05 (RF-80, cierre de gap CU-06): la falla de
auditoría no bloquea la respuesta de lectura, mismo criterio no-bloqueante
que ``consultar_auditoria_m04_use_case.py``.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.shared.errors import AuthorizationError, BusinessRuleError, NotFoundError
from src.supplies.domain.entities.historial_suministro import (
    FiltrosHistorialSuministro,
    LineaHistorialSuministro,
    ResumenConsultaHistorial,
)
from src.supplies.domain.repositories.activo_consulta_port import ActivoConsultaPort
from src.supplies.domain.repositories.alcance_activo_port import AlcanceActivoPort
from src.supplies.domain.repositories.auditoria_suministro_port import (
    AuditoriaSuministroPort,
    EventoAuditoriaSuministro,
)
from src.supplies.domain.repositories.configuracion_batch_historial_repository import (
    ConfiguracionBatchHistorialRepository,
)
from src.supplies.domain.repositories.historial_suministro_read_port import HistorialSuministroReadPort
from src.supplies.domain.value_objects.historial_suministro_enums import NivelVolumen

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ResultadoConsultaHistorial:
    lineas: list[LineaHistorialSuministro]
    resumen: ResumenConsultaHistorial


class ConsultarHistorialSuministrosUseCase:
    def __init__(
        self,
        historial_port: HistorialSuministroReadPort,
        alcance_port: AlcanceActivoPort,
        activo_port: ActivoConsultaPort,
        config_repo: ConfiguracionBatchHistorialRepository,
        db: Session,
        auditoria_port: AuditoriaSuministroPort,
    ) -> None:
        self.historial_port = historial_port
        self.alcance_port = alcance_port
        self.activo_port = activo_port
        self.config_repo = config_repo
        self.db = db
        self.auditoria_port = auditoria_port

    def execute(
        self, filtros: FiltrosHistorialSuministro, *, id_usuario: int, id_rol: int
    ) -> ResultadoConsultaHistorial:
        return self._consultar(filtros, id_usuario=id_usuario, id_rol=id_rol, forzar_sincrono=False)

    def consultar_forzado(
        self, filtros: FiltrosHistorialSuministro, *, id_usuario: int, id_rol: int
    ) -> ResultadoConsultaHistorial:
        """Usado por el worker del motor async (trabajo CONSULTA_PESADA): omite el
        gate de nivel de volumen, porque el trabajo ya fue encolado precisamente
        por superarlo."""
        return self._consultar(filtros, id_usuario=id_usuario, id_rol=id_rol, forzar_sincrono=True)

    def _consultar(
        self,
        filtros: FiltrosHistorialSuministro,
        *,
        id_usuario: int,
        id_rol: int,
        forzar_sincrono: bool,
    ) -> ResultadoConsultaHistorial:
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

        config = self.config_repo.obtener()
        total_historico = self.historial_port.contar_total_activo(filtros.id_activo_biologico)
        nivel = self._nivel_volumen(total_historico, config)
        if not forzar_sincrono and nivel != NivelVolumen.NIVEL_1:
            raise BusinessRuleError(
                code="CONSULTA_REQUIERE_MODO_ASINCRONO",
                message=(
                    f"El activo {filtros.id_activo_biologico} tiene {total_historico} registros históricos "
                    f"(Nivel {nivel.value}), que supera el límite de procesamiento síncrono. "
                    "Solicite la consulta vía POST /suministros/historial/trabajos (tipo CONSULTA_PESADA)."
                ),
            )

        resultado = self.historial_port.consultar(filtros, ids_permitidos)
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
        if not filtros.combinacion_valida():
            raise BusinessRuleError(
                code="COMBINACION_FILTROS_INVALIDA",
                message=(
                    "La combinación de filtros no es válida: fecha_fin_filtro no puede ser anterior a "
                    "fecha_inicio_filtro, ni costo_max menor que costo_min."
                ),
            )
        if filtros.id_ciclo_productivo is not None and not self.historial_port.ciclo_pertenece_a_activo(
            filtros.id_activo_biologico, filtros.id_ciclo_productivo
        ):
            raise BusinessRuleError(
                code="CICLO_NO_PERTENECE_AL_ACTIVO",
                message=(
                    f"El ciclo productivo {filtros.id_ciclo_productivo} no pertenece al activo "
                    f"{filtros.id_activo_biologico}."
                ),
            )

    @staticmethod
    def _nivel_volumen(total: int, config) -> NivelVolumen:
        if total <= config.umbral_nivel3:
            return NivelVolumen.NIVEL_1
        if total <= config.umbral_nivel4:
            return NivelVolumen.NIVEL_3
        return NivelVolumen.NIVEL_4
