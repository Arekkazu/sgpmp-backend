# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-11-10 | destroyerban | INC-M06-336-G36 RF-86: solicitudes de correctivo de variaciones |
# | 2026-11-11 | Arekkazu | USAB-M05-M06 T-01 RF-75..94: el activo sin identificador se nombra «Lote N», nunca null |
# | 2026-11-15 | Arekkazu | INC-M06-93-G44 RF-86: el nombre de quien solicitó y resolvió el correctivo sale aunque la RLS de usuarios lo oculte |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Implementación SQL de :class:`CorrectivoVariacionRepository`."""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from src.financial_valuation.domain.entities.valoracion import SolicitudCorrectivo, VariacionRegistro
from src.financial_valuation.domain.repositories.correctivo_variacion_repository import CorrectivoVariacionRepository
from src.financial_valuation.infrastructure.repositories.sql import con_nombres, escribir, fila, filas
from src.shared.nombre_activo import nombre_activo_sql

_COLUMNAS_SOLICITUD = """id_solicitud_correctivo_variacion, id_variacion_valor_razonable, motivo, estado, id_usuario_solicitante,
    fecha_solicitud, id_usuario_resolutor, fecha_resolucion, motivo_rechazo, id_variacion_correctiva"""

_CONFLICTOS = {"uq_solicitud_correctivo_variacion_vigente":
               "La variación ya tiene un correctivo pendiente o aprobado."}

_FILTROS = (("estado", "sc.estado = :estado"), ("id_periodo_contable", "v.id_periodo_contable = :id_periodo_contable"),
            ("id_activo_biologico", "v.id_activo_biologico = :id_activo_biologico"))


class SqlAlchemyCorrectivoVariacionRepository(CorrectivoVariacionRepository):
    """Implementación SQLAlchemy de ``CorrectivoVariacionRepository``."""
    def __init__(self, db: Session) -> None:
        self.db = db

    def variacion(self, id_variacion: int) -> Optional[VariacionRegistro]:
        """La variación con su referencia al registro que corrige (``id_variacion_corregida``), si la tiene."""
        f = fila(self.db, """
            SELECT id_variacion_valor_razonable, id_activo_biologico, tipo::text AS tipo, variacion_transformacion,
                   variacion_precio_mercado, valor_razonable_anterior, valor_razonable_nuevo, id_periodo_contable,
                   id_usuario, tiene_estimacion, id_medicion_posterior, id_evento, id_precio_mercado, id_cierre,
                   id_variacion_corregida
            FROM modulo6.variaciones_valor_razonable WHERE id_variacion_valor_razonable = :id""", {"id": id_variacion})
        return VariacionRegistro(**f) if f else None

    def solicitud_vigente(self, id_variacion: int) -> Optional[SolicitudCorrectivo]:
        """La solicitud PENDIENTE o APROBADA de la variación (hay a lo sumo una)."""
        f = fila(self.db, f"""SELECT {_COLUMNAS_SOLICITUD} FROM modulo6.solicitudes_correctivos_variaciones
                              WHERE id_variacion_valor_razonable = :v AND estado IN ('PENDIENTE', 'APROBADA')""",
                 {"v": id_variacion})
        return SolicitudCorrectivo(**f) if f else None

    def obtener(self, id_solicitud: int, bloquear: bool = False) -> Optional[SolicitudCorrectivo]:
        """Devuelve la solicitud, opcionalmente bloqueada, o ``None``."""
        f = fila(self.db, f"""SELECT {_COLUMNAS_SOLICITUD} FROM modulo6.solicitudes_correctivos_variaciones
                              WHERE id_solicitud_correctivo_variacion = :id {"FOR UPDATE" if bloquear else ""}""",
                 {"id": id_solicitud})
        return SolicitudCorrectivo(**f) if f else None

    def agregar(self, id_variacion: int, motivo: str, id_usuario: int) -> int:
        """Registra la solicitud y devuelve su id."""
        return escribir(self.db, """
            INSERT INTO modulo6.solicitudes_correctivos_variaciones (id_variacion_valor_razonable, motivo, id_usuario_solicitante)
            VALUES (:v, :m, :u) RETURNING id_solicitud_correctivo_variacion
        """, {"v": id_variacion, "m": motivo, "u": id_usuario}, _CONFLICTOS)

    def aprobar(self, id_solicitud: int, id_usuario: int, id_variacion_correctiva: int) -> None:
        """Marca la solicitud como aprobada con su variación correctiva."""
        escribir(self.db, """
            UPDATE modulo6.solicitudes_correctivos_variaciones
               SET estado = 'APROBADA', id_usuario_resolutor = :u, fecha_resolucion = now(), id_variacion_correctiva = :c
             WHERE id_solicitud_correctivo_variacion = :id AND estado = 'PENDIENTE'
        """, {"id": id_solicitud, "u": id_usuario, "c": id_variacion_correctiva})

    def rechazar(self, id_solicitud: int, id_usuario: int, motivo_rechazo: str) -> None:
        """Marca la solicitud como rechazada con su motivo."""
        escribir(self.db, """
            UPDATE modulo6.solicitudes_correctivos_variaciones
               SET estado = 'RECHAZADA', id_usuario_resolutor = :u, fecha_resolucion = now(), motivo_rechazo = :m
             WHERE id_solicitud_correctivo_variacion = :id AND estado = 'PENDIENTE'
        """, {"id": id_solicitud, "u": id_usuario, "m": motivo_rechazo})

    def listar(self, filtros: dict) -> list[dict]:
        """Solicitudes con su variación y su activo; filtros por estado, período y activo (AND)."""
        condiciones, params = [], {}
        for campo, sql in _FILTROS:
            if filtros.get(campo) not in (None, ""):
                condiciones.append(sql)
                params[campo] = filtros[campo]
        return con_nombres(self.db, filas(self.db, f"""
            SELECT sc.id_solicitud_correctivo_variacion, sc.id_variacion_valor_razonable, sc.motivo, sc.estado,
                   sc.fecha_solicitud, sc.id_usuario_solicitante, sc.fecha_resolucion, sc.id_usuario_resolutor,
                   sc.motivo_rechazo, sc.id_variacion_correctiva,
                   v.id_activo_biologico, {nombre_activo_sql()} AS identificador, v.id_periodo_contable, v.tipo::text AS tipo_variacion,
                   v.monto_variacion, v.fecha_registro AS fecha_variacion
            FROM modulo6.solicitudes_correctivos_variaciones sc
            JOIN modulo6.variaciones_valor_razonable v ON v.id_variacion_valor_razonable = sc.id_variacion_valor_razonable
            JOIN modulo2.activos_biologicos a ON a.id_activo_biologico = v.id_activo_biologico
            WHERE {" AND ".join(condiciones) or "true"}
            ORDER BY sc.fecha_solicitud DESC, sc.id_solicitud_correctivo_variacion DESC LIMIT 500""", params),
            {"id_usuario_solicitante": "nombre_solicitante", "id_usuario_resolutor": "nombre_resolutor"})
