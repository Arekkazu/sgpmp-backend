# | Fecha      | Nombre           | Que se hizo                                   |
# |------------|------------------|-----------------------------------------------|
# | 2026-11-14 | destroyerban     | INC-M05-353-G37 RF-80: rechazo de consulta/exportación del historial en la bitácora |
"""Auditoría compartida de la consulta y la exportación del historial (RF-81 → RF-80).

- :func:`ciclo_del_resultado`: el ciclo productivo del evento exitoso. Es el del
  filtro o, si el resultado abarca un solo ciclo, ese ciclo; si abarca varios no
  hay uno solo que registrar y el evento queda incompleto (Restricción 8).
- :func:`registrar_rechazo_historial`: patrón de RF-78 para un intento rechazado
  (403, 404, 422, 429): revierte lo que hubiera y confirma solo su evento, con el
  tipo de la operación y resultado ``RECHAZADO`` (``FALLIDO`` si fue un error
  interno). Solo enlaza el activo y el ciclo si el usuario los ve y existen; los
  valores pedidos quedan en ``datos_nuevos.filtros_aplicados``.
"""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session

from src.shared.errors import AppError
from src.supplies.domain.entities.historial_suministro import FiltrosHistorialSuministro
from src.supplies.domain.repositories.activo_consulta_port import ActivoConsultaPort
from src.supplies.domain.repositories.auditoria_suministro_port import (
    AuditoriaSuministroPort,
    EventoAuditoriaSuministro,
)
from src.supplies.domain.repositories.historial_suministro_read_port import HistorialSuministroReadPort
from src.supplies.domain.value_objects.eventos_auditoria_suministro_enums import (
    ResultadoAuditoriaSuministro,
    TipoEventoAuditoriaSuministro,
)

logger = logging.getLogger(__name__)

# Lo que lee el auditor en la bitácora: en palabras, sin el código del error ni nombres de parámetros.
_MOTIVOS_POR_CAMPO = {
    "fecha_fin_filtro": "la fecha final del filtro es anterior a la fecha inicial.",
    "costo_max": "el costo máximo del filtro es menor que el costo mínimo.",
}
_MOTIVOS = {
    "CICLO_NO_PERTENECE_AL_ACTIVO": "el ciclo productivo filtrado no pertenece al activo.",
    "ACCESO_DENEGADO": "el activo está fuera de las unidades productivas del usuario.",
    "ACTIVO_NO_ENCONTRADO": "el activo biológico no existe.",
    "FORMATO_EXPORTACION_INVALIDO": "el formato de exportación no es PDF ni Excel.",
    "LIMITE_EXPORTACIONES_EXCEDIDO": "el usuario ya tiene el máximo de exportaciones en curso.",
    "LIMITE_CONCURRENCIA_EXCEDIDO": "el usuario ya tiene el máximo de trabajos en curso.",
}
_OPERACION = {
    TipoEventoAuditoriaSuministro.CONSULTA_HISTORIAL_EJECUTADA: "Consulta del historial de suministros",
    TipoEventoAuditoriaSuministro.EXPORTACION_HISTORIAL_GENERADA: "Exportación del historial de suministros",
}


def ciclo_del_resultado(filtros: FiltrosHistorialSuministro, resultado) -> Optional[int]:
    """Ciclo productivo del evento: el filtrado o, si el resultado tiene uno solo, ese."""
    if filtros.id_ciclo_productivo is not None:
        return filtros.id_ciclo_productivo
    ciclos = {linea.id_ciclo_productivo for linea in resultado.lineas if linea.id_ciclo_productivo is not None}
    if len(ciclos) == 1 and len(resultado.desglose_por_ciclo) == 1:
        return ciclos.pop()
    return None


def _motivo(error: AppError) -> str:
    if error.status_code >= 500:
        return "ocurrió un error interno del sistema."
    if error.code == "COMBINACION_FILTROS_INVALIDA":
        return _MOTIVOS_POR_CAMPO.get(error.field or "", "la combinación de filtros no es válida.")
    return _MOTIVOS.get(error.code, "la operación incumple una regla de negocio.")


def registrar_rechazo_historial(
    *,
    db: Session,
    auditoria_port: AuditoriaSuministroPort,
    activo_port: ActivoConsultaPort,
    historial_port: HistorialSuministroReadPort,
    tipo: TipoEventoAuditoriaSuministro,
    filtros: FiltrosHistorialSuministro,
    id_usuario: int,
    error: AppError,
    datos_extra: Optional[dict] = None,
) -> None:
    """Confirma el evento del intento rechazado en una transacción propia. Nunca lanza."""
    try:
        db.rollback()
        activo = activo_port.obtener(filtros.id_activo_biologico)
        id_ciclo = None
        if (
            activo is not None
            and filtros.id_ciclo_productivo is not None
            and historial_port.ciclo_pertenece_a_activo(filtros.id_activo_biologico, filtros.id_ciclo_productivo)
        ):
            id_ciclo = filtros.id_ciclo_productivo
        rechazado = error.status_code < 500
        detalle = (
            f"{_OPERACION[tipo]} {'rechazada' if rechazado else 'fallida'}: {_motivo(error)} "
            f"Activo solicitado: {filtros.id_activo_biologico}."
        )
        auditoria_port.registrar(
            EventoAuditoriaSuministro(
                entidad_afectada="historial_suministros",
                tipo_operacion=tipo.value,
                id_usuario=id_usuario,
                resultado=(
                    ResultadoAuditoriaSuministro.RECHAZADO if rechazado else ResultadoAuditoriaSuministro.FALLIDO
                ).value,
                id_activo_biologico=activo.id_activo_biologico if activo is not None else None,
                id_ciclo_productivo=id_ciclo,
                detalle_causa=detalle,
                datos_nuevos={"filtros_aplicados": filtros.para_auditoria(), **(datos_extra or {})},
            )
        )
        db.commit()
    except Exception:
        logger.error(
            "No se pudo auditar el rechazo del historial: usuario=%s activo=%s codigo=%s",
            id_usuario, filtros.id_activo_biologico, error.code,
        )
        try:
            db.rollback()
        except Exception:
            logger.error("No se pudo revertir la transacción de auditoría del rechazo del historial.")
