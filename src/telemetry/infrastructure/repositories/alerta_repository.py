from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from src.shared.db_error_translator import raise_from_db_error
from src.telemetry.domain.entities.alerta import Alerta
from src.telemetry.domain.repositories.alerta_repository import AlertaRepository
from src.telemetry.infrastructure.models.alerta_model import AlertaModel


class SqlAlchemyAlertaRepository(AlertaRepository):

    def __init__(self, db: Session) -> None:
        self.db = db

    def guardar(self, alerta: Alerta) -> Alerta:
        try:
            orm = AlertaModel(
                tipo_alerta=alerta.tipo_alerta,
                severidad=alerta.severidad,
                estado_alerta=alerta.estado_alerta,
                origen_evento=alerta.origen_evento,
                tipo_variable=alerta.tipo_variable,
                valor=alerta.valor,
                unidad=alerta.unidad,
                reglas_activas=list(alerta.reglas_activas or []),
                contexto_activo_biologico=alerta.contexto_activo_biologico,
                metadato_evento=alerta.metadato_evento,
                accion_sugerida=alerta.accion_sugerida,
                motivo_descarte=alerta.motivo_descarte,
                diagnostico=alerta.diagnostico,
                tiene_inferencia_no_disponible=alerta.tiene_inferencia_no_disponible,
                tiene_contexto_incompleto=alerta.tiene_contexto_incompleto,
                tiene_generada_por_reevaluacion=alerta.tiene_generada_por_reevaluacion,
                conflicto_resolucion=alerta.conflicto_resolucion,
                severidad_edge_original=alerta.severidad_edge_original,
                serveridad_ia=alerta.severidad_ia,  # typo en DB
                frecuencia_evento=alerta.frecuencia_evento,
                ultima_ocurrencia=alerta.ultima_ocurrencia,
                fecha_evento=alerta.fecha_evento,
                fecha_generacion=alerta.fecha_generacion,
                fecha_vencimiento=alerta.fecha_vencimiento,
                id_sensor=alerta.id_sensor,
                id_dispositivo_ioit=alerta.id_dispositivo_ioit,
                id_activo_biologico=alerta.id_activo_biologico,
                id_infraestructura=alerta.id_infraestructura,
                id_evento_edge_computing=alerta.id_evento_edge_computing,
                id_telemetria=alerta.id_telemetria,
                id_paquete_inferencia=alerta.id_paquete_inferencia,
                id_regla_alerta=alerta.id_regla_alerta,
                id_usuario_atencion=alerta.id_usuario_atencion,
                id_usuario_resolucion=alerta.id_usuario_resolucion,
                referencia_alerta_original=alerta.referencia_alerta_original,
            )
            self.db.add(orm)
            self.db.flush()
            self.db.refresh(orm)
            return self._a_entidad(orm)
        except Exception as exc:
            raise_from_db_error(exc)

    def buscar_activa_duplicada(
        self,
        id_sensor: int,
        tipo_variable: str,
        ventana_min: int = 30,
    ) -> Optional[Alerta]:
        orm = (
            self.db.query(AlertaModel)
            .filter(
                AlertaModel.id_sensor == id_sensor,
                AlertaModel.tipo_variable == tipo_variable.upper(),
                AlertaModel.estado_alerta.in_(['ACTIVA', 'EN_ATENCION']),
                AlertaModel.fecha_generacion >= func.now() - text(f"interval '{ventana_min} minutes'"),
            )
            .order_by(AlertaModel.fecha_generacion.desc())
            .first()
        )
        return self._a_entidad(orm) if orm else None

    def actualizar_deduplicacion(
        self,
        id_alerta: int,
        ultima_ocurrencia: datetime,
        nueva_severidad: Optional[str] = None,
    ) -> None:
        try:
            orm = self.db.query(AlertaModel).filter(AlertaModel.id_alerta == id_alerta).first()
            if orm is None:
                return
            orm.frecuencia_evento = (orm.frecuencia_evento or 1) + 1
            orm.ultima_ocurrencia = ultima_ocurrencia
            if nueva_severidad is not None:
                orm.severidad = nueva_severidad
            self.db.flush()
        except Exception as exc:
            raise_from_db_error(exc)

    def actualizar_estado(
        self,
        id_alerta: int,
        nuevo_estado: str,
        id_usuario: Optional[int],
        motivo: Optional[str],
        fecha_atencion: Optional[datetime] = None,
        fecha_resolucion: Optional[datetime] = None,
    ) -> Alerta:
        try:
            orm = self.db.query(AlertaModel).filter(AlertaModel.id_alerta == id_alerta).first()
            if orm is None:
                from src.shared.errors import NotFoundError
                raise NotFoundError(code="ALERTA_NO_ENCONTRADA", message=f"Alerta {id_alerta} no encontrada.")
            orm.estado_alerta = nuevo_estado
            if nuevo_estado == 'EN_ATENCION':
                orm.fecha_atencion = fecha_atencion
                orm.id_usuario_atencion = id_usuario
            elif nuevo_estado in ('RESUELTA', 'DESCARTADA'):
                orm.fecha_resolucion = fecha_resolucion
                orm.id_usuario_resolucion = id_usuario
                if nuevo_estado == 'DESCARTADA':
                    orm.motivo_descarte = motivo
            self.db.flush()
            self.db.refresh(orm)
            return self._a_entidad(orm)
        except Exception as exc:
            raise_from_db_error(exc)

    def obtener_por_id(self, id_alerta: int) -> Optional[Alerta]:
        orm = self.db.query(AlertaModel).filter(AlertaModel.id_alerta == id_alerta).first()
        return self._a_entidad(orm) if orm else None

    def listar(
        self,
        estado: Optional[str] = None,
        severidad: Optional[str] = None,
        tipo_alerta: Optional[str] = None,
        id_sensor: Optional[int] = None,
        id_activo_biologico: Optional[int] = None,
        origen_evento: Optional[str] = None,
        fecha_desde: Optional[datetime] = None,
        fecha_hasta: Optional[datetime] = None,
        pagina: int = 1,
        por_pagina: int = 50,
    ) -> tuple[list[Alerta], int]:
        q = self.db.query(AlertaModel)
        if estado:
            q = q.filter(AlertaModel.estado_alerta == estado)
        if severidad:
            q = q.filter(AlertaModel.severidad == severidad)
        if tipo_alerta:
            q = q.filter(AlertaModel.tipo_alerta == tipo_alerta)
        if id_sensor:
            q = q.filter(AlertaModel.id_sensor == id_sensor)
        if id_activo_biologico:
            q = q.filter(AlertaModel.id_activo_biologico == id_activo_biologico)
        if origen_evento:
            q = q.filter(AlertaModel.origen_evento == origen_evento)
        if fecha_desde:
            q = q.filter(AlertaModel.fecha_generacion >= fecha_desde)
        if fecha_hasta:
            q = q.filter(AlertaModel.fecha_generacion <= fecha_hasta)

        total = q.count()
        offset = (pagina - 1) * por_pagina
        orms = q.order_by(AlertaModel.fecha_generacion.desc()).offset(offset).limit(por_pagina).all()
        return [self._a_entidad(o) for o in orms], total

    @staticmethod
    def _a_entidad(orm: AlertaModel) -> Alerta:
        return Alerta(
            id_alerta=orm.id_alerta,
            tipo_alerta=orm.tipo_alerta,
            severidad=orm.severidad,
            estado_alerta=orm.estado_alerta,
            origen_evento=orm.origen_evento,
            tipo_variable=orm.tipo_variable,
            valor=orm.valor,
            unidad=orm.unidad,
            reglas_activas=list(orm.reglas_activas or []),
            contexto_activo_biologico=dict(orm.contexto_activo_biologico) if orm.contexto_activo_biologico else None,
            metadato_evento=dict(orm.metadato_evento) if orm.metadato_evento else None,
            accion_sugerida=orm.accion_sugerida,
            motivo_descarte=orm.motivo_descarte,
            diagnostico=orm.diagnostico,
            tiene_inferencia_no_disponible=orm.tiene_inferencia_no_disponible,
            tiene_contexto_incompleto=orm.tiene_contexto_incompleto,
            tiene_generada_por_reevaluacion=orm.tiene_generada_por_reevaluacion,
            conflicto_resolucion=orm.conflicto_resolucion,
            severidad_edge_original=orm.severidad_edge_original,
            severidad_ia=orm.serveridad_ia,  # typo en DB: serveridad_ia
            frecuencia_evento=orm.frecuencia_evento or 1,
            ultima_ocurrencia=orm.ultima_ocurrencia,
            fecha_evento=orm.fecha_evento,
            fecha_generacion=orm.fecha_generacion,
            fecha_registro=orm.fecha_registro,
            fecha_notificacion=orm.fecha_notificacion,
            fecha_atencion=orm.fecha_atencion,
            fecha_resolucion=orm.fecha_resolucion,
            fecha_vencimiento=orm.fecha_vencimiento,
            id_sensor=orm.id_sensor,
            id_dispositivo_ioit=orm.id_dispositivo_ioit,
            id_activo_biologico=orm.id_activo_biologico,
            id_infraestructura=orm.id_infraestructura,
            id_evento_edge_computing=orm.id_evento_edge_computing,
            id_telemetria=orm.id_telemetria,
            id_paquete_inferencia=orm.id_paquete_inferencia,
            id_regla_alerta=orm.id_regla_alerta,
            id_usuario_atencion=orm.id_usuario_atencion,
            id_usuario_resolucion=orm.id_usuario_resolucion,
            referencia_alerta_original=orm.referencia_alerta_original,
        )
