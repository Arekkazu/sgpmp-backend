# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-24 | Arekkazu | USAB-M03 M3-14 RF-62: calidad limitada a las fincas del usuario |
from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import func, literal_column, select, text
from sqlalchemy.orm import Session, aliased

from src.shared.db_error_translator import raise_from_db_error
from src.telemetry.domain.entities.telemetria_calidad import ClasificacionCalidad, EstadoEvaluacion, TelemetriaCalidad
from src.telemetry.domain.repositories.telemetria_calidad_repository import TelemetriaCalidadRepository
from src.telemetry.infrastructure.models.telemetria_calidad_model import TelemetriaCalidadModel


class SqlAlchemyTelemetriaCalidadRepository(TelemetriaCalidadRepository):

    def __init__(self, db: Session) -> None:
        self.db = db

    def _consulta_vigentes(self, id_telemetria: Optional[int] = None):
        """Una evaluación no superada por lectura, con desempate estable.

        Se respeta tanto el estado explícito como la cadena de sustitución.
        El ranking resuelve registros históricos con varios VIGENTE sin
        multiplicar lecturas ni recuperar una aptitud anterior por un filtro.
        """
        candidata = aliased(TelemetriaCalidadModel)
        posterior = aliased(TelemetriaCalidadModel)
        superada = self.db.query(posterior.id_evaluacion).filter(
            posterior.id_evaluacion_superada == candidata.id_evaluacion,
            posterior.id_telemetria == candidata.id_telemetria,
        ).exists()
        ranking = self.db.query(
            candidata.id_evaluacion.label('id_evaluacion'),
            func.row_number().over(
                partition_by=candidata.id_telemetria,
                order_by=(
                    candidata.timestamp_evaluacion.desc(),
                    candidata.fecha_creacion.desc(),
                    candidata.id_evaluacion.desc(),
                ),
            ).label('posicion'),
        ).filter(candidata.estado_evaluacion == 'VIGENTE', ~superada)
        if id_telemetria is not None:
            ranking = ranking.filter(candidata.id_telemetria == id_telemetria)
        vigentes = ranking.subquery()
        return self.db.query(TelemetriaCalidadModel).join(
            vigentes, vigentes.c.id_evaluacion == TelemetriaCalidadModel.id_evaluacion,
        ).filter(vigentes.c.posicion == 1)

    def guardar(self, evaluacion: TelemetriaCalidad) -> TelemetriaCalidad:
        try:
            orm = TelemetriaCalidadModel(
                id_telemetria=evaluacion.id_telemetria,
                id_sensor=evaluacion.id_sensor,
                timestamp_evaluacion=evaluacion.timestamp_evaluacion,
                indice_calidad=evaluacion.indice_calidad,
                clasificacion_calidad=evaluacion.clasificacion_calidad.value,
                apto_para_ia=evaluacion.apto_para_ia,
                apto_para_nic41=evaluacion.apto_para_nic41,
                flags_detectados=evaluacion.flags_detectados,
                version_limites_fisicos_aplicada=evaluacion.version_limites_fisicos_aplicada,
                parametros_aplicados=evaluacion.parametros_aplicados,
                parametros_calibracion_aplicados=evaluacion.parametros_calibracion_aplicados,
                estado_evaluacion=evaluacion.estado_evaluacion.value,
                motivo_reevaluacion=evaluacion.motivo_reevaluacion,
                id_evaluacion_superada=evaluacion.id_evaluacion_superada,
                version_evaluacion=evaluacion.version_evaluacion,
            )
            self.db.add(orm)
            self.db.flush()
            self.db.refresh(orm)
            return self._a_entidad(orm)
        except Exception as exc:
            raise_from_db_error(exc)

    def obtener_por_lectura(self, id_telemetria: int) -> Optional[TelemetriaCalidad]:
        orm = self._consulta_vigentes(id_telemetria).first()
        return self._a_entidad(orm) if orm else None

    def listar(
        self,
        id_sensor: Optional[int] = None,
        clasificacion: Optional[str] = None,
        fecha_desde: Optional[datetime] = None,
        fecha_hasta: Optional[datetime] = None,
        estado_evaluacion: Optional[str] = None,
        pagina: int = 1,
        por_pagina: int = 50,
        *,
        ids_fincas_permitidas: Optional[list[int]] = None,
    ) -> tuple[list[TelemetriaCalidad], int]:
        # La consulta ordinaria expone aptitud vigente. El histórico SUPERADA
        # sigue disponible cuando se solicita explícitamente ese estado.
        q = (self._consulta_vigentes() if estado_evaluacion in (None, 'VIGENTE')
             else self.db.query(TelemetriaCalidadModel))
        if id_sensor is not None:
            q = q.filter(TelemetriaCalidadModel.id_sensor == id_sensor)
        if clasificacion:
            q = q.filter(TelemetriaCalidadModel.clasificacion_calidad == clasificacion)
        if fecha_desde:
            q = q.filter(TelemetriaCalidadModel.timestamp_evaluacion >= fecha_desde)
        if fecha_hasta:
            q = q.filter(TelemetriaCalidadModel.timestamp_evaluacion <= fecha_hasta)
        if estado_evaluacion:
            q = q.filter(TelemetriaCalidadModel.estado_evaluacion == estado_evaluacion)
        # M3-14: antes la lista era global para todo rol con permiso, incluso el Contador
        # sin finca. Mismo alcance que Monitoreo, Alertas y Vinculaciones.
        if ids_fincas_permitidas is not None:
            q = q.filter(TelemetriaCalidadModel.id_sensor.in_(
                select(literal_column('s.id_sensores')).select_from(text(
                    'modulo9.sensores s JOIN modulo9.dispositivos_iot d ON d.id_dispositivo_iot = s.id_dispositivo_iot '
                    'JOIN modulo9.infraestructuras i ON i.id_infraestructura = d.id_infraestructura'
                )).where(literal_column('i.id_finca').in_(ids_fincas_permitidas))
            ))
        total = q.count()
        items = q.order_by(
            TelemetriaCalidadModel.timestamp_evaluacion.desc(),
            TelemetriaCalidadModel.id_evaluacion.desc(),
        ).offset((pagina - 1) * por_pagina).limit(por_pagina).all()
        return [self._a_entidad(o) for o in items], total

    def marcar_superada(self, id_evaluacion: UUID, motivo: str) -> None:
        orm = self.db.query(TelemetriaCalidadModel).filter(
            TelemetriaCalidadModel.id_evaluacion == id_evaluacion
        ).first()
        if orm:
            orm.estado_evaluacion = 'SUPERADA'
            orm.motivo_reevaluacion = motivo
            self.db.flush()

    def listar_vigentes_por_sensor_rango(
        self,
        id_sensor: int,
        fecha_desde: datetime,
        fecha_hasta: datetime,
    ) -> list[TelemetriaCalidad]:
        items = (
            self._consulta_vigentes()
            .filter(
                TelemetriaCalidadModel.id_sensor == id_sensor,
                TelemetriaCalidadModel.estado_evaluacion == 'VIGENTE',
                TelemetriaCalidadModel.timestamp_evaluacion >= fecha_desde,
                TelemetriaCalidadModel.timestamp_evaluacion <= fecha_hasta,
            )
            .all()
        )
        return [self._a_entidad(o) for o in items]

    @staticmethod
    def _a_entidad(orm: TelemetriaCalidadModel) -> TelemetriaCalidad:
        return TelemetriaCalidad(
            id_evaluacion=orm.id_evaluacion,
            id_telemetria=orm.id_telemetria,
            id_sensor=orm.id_sensor,
            timestamp_evaluacion=orm.timestamp_evaluacion,
            indice_calidad=orm.indice_calidad,
            clasificacion_calidad=ClasificacionCalidad(orm.clasificacion_calidad),
            apto_para_ia=orm.apto_para_ia,
            apto_para_nic41=orm.apto_para_nic41,
            flags_detectados=orm.flags_detectados or {},
            version_limites_fisicos_aplicada=orm.version_limites_fisicos_aplicada,
            parametros_aplicados=orm.parametros_aplicados or {},
            parametros_calibracion_aplicados=orm.parametros_calibracion_aplicados,
            estado_evaluacion=EstadoEvaluacion(orm.estado_evaluacion),
            motivo_reevaluacion=orm.motivo_reevaluacion,
            id_evaluacion_superada=orm.id_evaluacion_superada,
            version_evaluacion=orm.version_evaluacion,
            fecha_creacion=orm.fecha_creacion,
        )
