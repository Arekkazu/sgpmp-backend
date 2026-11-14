# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-11-10 | destroyerban | INC-M06-336-G36 RF-86: solicitudes de correctivo de variaciones |
# | 2026-11-11 | Arekkazu | USAB-M05-M06 T-01 RF-75..94: el activo sin identificador se nombra «Lote N», nunca null |
"""Implementación SQL de :class:`CorrectivoVariacionRepository`."""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from src.financial_valuation.domain.entities.valoracion import SolicitudCorrectivo, VariacionRegistro
from src.financial_valuation.domain.repositories.correctivo_variacion_repository import CorrectivoVariacionRepository
from src.financial_valuation.infrastructure.repositories.sql import escribir, fila, filas
from src.shared.nombre_activo import nombre_activo_sql

_COLUMNAS_SOLICITUD = """id_solicitud_correctivo_variacion, id_variacion_valor_razonable, motivo, estado, id_usuario_solicitante,
    fecha_solicitud, id_usuario_resolutor, fecha_resolucion, motivo_rechazo, id_variacion_correctiva"""

_CONFLICTOS = {"uq_solicitud_correctivo_variacion_vigente":
               "La variación ya tiene un correctivo pendiente o aprobado."}

_FILTROS = (("estado", "sc.estado = :estado"), ("id_periodo_contable", "v.id_periodo_contable = :id_periodo_contable"),
            ("id_activo_biologico", "v.id_activo_biologico = :id_activo_biologico"))


class SqlAlchemyCorrectivoVariacionRepository(CorrectivoVariacionRepository):
    def __init__(self, db: Session) -> None:
        self.db = db

    def variacion(self, id_variacion: int) -> Optional[VariacionRegistro]:
        f = fila(self.db, """
            SELECT id_variacion_valor_razonable, id_activo_biologico, tipo::text AS tipo, variacion_transformacion,
                   variacion_precio_mercado, valor_razonable_anterior, valor_razonable_nuevo, id_periodo_contable,
                   id_usuario, tiene_estimacion, id_medicion_posterior, id_evento, id_precio_mercado, id_cierre,
                   id_variacion_corregida
            FROM modulo6.variaciones_valor_razonable WHERE id_variacion_valor_razonable = :id""", {"id": id_variacion})
        return VariacionRegistro(**f) if f else None

    def solicitud_vigente(self, id_variacion: int) -> Optional[SolicitudCorrectivo]:
        f = fila(self.db, f"""SELECT {_COLUMNAS_SOLICITUD} FROM modulo6.solicitudes_correctivos_variaciones
                              WHERE id_variacion_valor_razonable = :v AND estado IN ('PENDIENTE', 'APROBADA')""",
                 {"v": id_variacion})
        return SolicitudCorrectivo(**f) if f else None

    def obtener(self, id_solicitud: int, bloquear: bool = False) -> Optional[SolicitudCorrectivo]:
        f = fila(self.db, f"""SELECT {_COLUMNAS_SOLICITUD} FROM modulo6.solicitudes_correctivos_variaciones
                              WHERE id_solicitud_correctivo_variacion = :id {"FOR UPDATE" if bloquear else ""}""",
                 {"id": id_solicitud})
        return SolicitudCorrectivo(**f) if f else None

    def agregar(self, id_variacion: int, motivo: str, id_usuario: int) -> int:
        return escribir(self.db, """
            INSERT INTO modulo6.solicitudes_correctivos_variaciones (id_variacion_valor_razonable, motivo, id_usuario_solicitante)
            VALUES (:v, :m, :u) RETURNING id_solicitud_correctivo_variacion
        """, {"v": id_variacion, "m": motivo, "u": id_usuario}, _CONFLICTOS)

    def aprobar(self, id_solicitud: int, id_usuario: int, id_variacion_correctiva: int) -> None:
        escribir(self.db, """
            UPDATE modulo6.solicitudes_correctivos_variaciones
               SET estado = 'APROBADA', id_usuario_resolutor = :u, fecha_resolucion = now(), id_variacion_correctiva = :c
             WHERE id_solicitud_correctivo_variacion = :id AND estado = 'PENDIENTE'
        """, {"id": id_solicitud, "u": id_usuario, "c": id_variacion_correctiva})

    def rechazar(self, id_solicitud: int, id_usuario: int, motivo_rechazo: str) -> None:
        escribir(self.db, """
            UPDATE modulo6.solicitudes_correctivos_variaciones
               SET estado = 'RECHAZADA', id_usuario_resolutor = :u, fecha_resolucion = now(), motivo_rechazo = :m
             WHERE id_solicitud_correctivo_variacion = :id AND estado = 'PENDIENTE'
        """, {"id": id_solicitud, "u": id_usuario, "m": motivo_rechazo})

    def listar(self, filtros: dict) -> list[dict]:
        condiciones, params = [], {}
        for campo, sql in _FILTROS:
            if filtros.get(campo) not in (None, ""):
                condiciones.append(sql)
                params[campo] = filtros[campo]
        return filas(self.db, f"""
            SELECT sc.id_solicitud_correctivo_variacion, sc.id_variacion_valor_razonable, sc.motivo, sc.estado,
                   sc.fecha_solicitud, sc.id_usuario_solicitante,
                   NULLIF(trim(coalesce(us.nombre, '') || ' ' || coalesce(us.apellidos, '')), '') AS nombre_solicitante,
                   sc.fecha_resolucion, sc.id_usuario_resolutor,
                   NULLIF(trim(coalesce(ur.nombre, '') || ' ' || coalesce(ur.apellidos, '')), '') AS nombre_resolutor,
                   sc.motivo_rechazo, sc.id_variacion_correctiva,
                   v.id_activo_biologico, {nombre_activo_sql()} AS identificador, v.id_periodo_contable, v.tipo::text AS tipo_variacion,
                   v.monto_variacion, v.fecha_registro AS fecha_variacion
            FROM modulo6.solicitudes_correctivos_variaciones sc
            JOIN modulo6.variaciones_valor_razonable v ON v.id_variacion_valor_razonable = sc.id_variacion_valor_razonable
            JOIN modulo2.activos_biologicos a ON a.id_activo_biologico = v.id_activo_biologico
            LEFT JOIN modulo1.usuarios us ON us.id_usuario = sc.id_usuario_solicitante
            LEFT JOIN modulo1.usuarios ur ON ur.id_usuario = sc.id_usuario_resolutor
            WHERE {" AND ".join(condiciones) or "true"}
            ORDER BY sc.fecha_solicitud DESC, sc.id_solicitud_correctivo_variacion DESC LIMIT 500""", params)
