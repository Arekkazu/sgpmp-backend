"""Implementación SQLAlchemy del puerto :class:`AuditoriaSuministroReadPort` (RF-80, CU-06).

Mismo patrón de paginación que ``evento_auditoria_m04_repository.py``:
``select()`` + ``func.count()`` sobre subquery, ``order_by(fecha_evento.desc())``.
Lee ``AuditoriaSuministroModel`` (ya existía, generado con sqlacodegen para
CU-05) — no crea tabla ni modelo nuevo.
"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.shared.errors import NotFoundError
from src.supplies.domain.entities.evento_auditoria_suministro import EventoAuditoriaSuministroConsulta
from src.supplies.domain.repositories.auditoria_suministro_read_port import (
    AuditoriaSuministroReadPort,
    FiltrosAuditoriaSuministro,
)
from src.supplies.infrastructure.models.auditoria_suministro_model import AuditoriaSuministroModel


def _a_entidad(orm: AuditoriaSuministroModel) -> EventoAuditoriaSuministroConsulta:
    return EventoAuditoriaSuministroConsulta(
        id_auditoria_suministro=orm.id_auditoria_suministro,
        entidad_afectada=orm.entidad_afectada,
        tipo_operacion=orm.tipo_operacion,
        id_usuario=orm.id_usuario,
        resultado=orm.resultado,
        fecha_evento=orm.fecha_evento,
        datos_anteriores=orm.datos_anteriores,
        datos_nuevos=orm.datos_nuevos,
        ip_origen=orm.ip_origen,
        id_sesion=orm.id_sesion,
        fecha_emision=orm.fecha_emision,
        id_activo_biologico=orm.id_activo_biologico,
        id_ciclo_productivo=orm.id_ciclo_productivo,
        costo_afectado=orm.costo_afectado,
        origen_precio=orm.origen_precio,
        clasificacion_registro=orm.clasificacion_registro,
        retencion_aplicable=orm.retencion_aplicable,
        hash_integridad=orm.hash_integridad,
        registro_incompleto=orm.registro_incompleto,
        detalle_causa=orm.detalle_causa,
        numero_reintentos=orm.numero_reintentos,
        fecha_intentos=orm.fecha_intentos,
        id_gestion_fases=orm.id_gestion_fases,
    )


class SqlAlchemyAuditoriaSuministroReadRepository(AuditoriaSuministroReadPort):
    def __init__(self, db: Session) -> None:
        self.db = db

    def consultar(
        self, filtros: FiltrosAuditoriaSuministro
    ) -> tuple[list[EventoAuditoriaSuministroConsulta], int]:
        q = select(AuditoriaSuministroModel)

        if filtros.tipo_operacion:
            q = q.where(AuditoriaSuministroModel.tipo_operacion == filtros.tipo_operacion)
        if filtros.id_usuario is not None:
            q = q.where(AuditoriaSuministroModel.id_usuario == filtros.id_usuario)
        if filtros.fecha_desde:
            q = q.where(AuditoriaSuministroModel.fecha_evento >= filtros.fecha_desde)
        if filtros.fecha_hasta:
            q = q.where(AuditoriaSuministroModel.fecha_evento <= filtros.fecha_hasta)
        if filtros.entidad_afectada:
            q = q.where(AuditoriaSuministroModel.entidad_afectada == filtros.entidad_afectada)
        if filtros.id_activo_biologico is not None:
            q = q.where(AuditoriaSuministroModel.id_activo_biologico == filtros.id_activo_biologico)
        if filtros.id_ciclo_productivo is not None:
            q = q.where(AuditoriaSuministroModel.id_ciclo_productivo == filtros.id_ciclo_productivo)
        if filtros.resultado:
            q = q.where(AuditoriaSuministroModel.resultado == filtros.resultado)
        if filtros.clasificacion_registro:
            q = q.where(AuditoriaSuministroModel.clasificacion_registro == filtros.clasificacion_registro)

        total_q = select(func.count()).select_from(q.subquery())
        total = self.db.execute(total_q).scalar_one()

        offset = (filtros.pagina - 1) * filtros.registros_por_pagina
        items = (
            self.db.execute(
                q.order_by(AuditoriaSuministroModel.fecha_evento.desc())
                .offset(offset)
                .limit(filtros.registros_por_pagina)
            )
            .scalars()
            .all()
        )
        return [_a_entidad(row) for row in items], total

    def obtener_por_id(self, id_auditoria_suministro: int) -> EventoAuditoriaSuministroConsulta:
        orm = self.db.get(AuditoriaSuministroModel, id_auditoria_suministro)
        if orm is None:
            raise NotFoundError(
                code="AUDITORIA_SUMINISTRO_NO_ENCONTRADA",
                message=f"No existe el evento de auditoría {id_auditoria_suministro}.",
            )
        return _a_entidad(orm)
