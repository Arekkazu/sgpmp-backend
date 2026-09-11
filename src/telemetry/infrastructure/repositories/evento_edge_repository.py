from sqlalchemy.orm import Session

from src.shared.db_error_translator import raise_from_db_error
from src.telemetry.domain.entities.telemetria import EventoEdgeComputing, clasificacion_a_tipo_evento_bd
from src.telemetry.domain.repositories.evento_edge_repository import EventoEdgeRepository
from src.telemetry.infrastructure.models.evento_edge_model import EventoEdgeComputingModel


class SqlAlchemyEventoEdgeRepository(EventoEdgeRepository):

    def __init__(self, db: Session) -> None:
        self.db = db

    def guardar(self, entidad: EventoEdgeComputing) -> EventoEdgeComputing:
        try:
            metadatos = dict(entidad.metadatos)
            # Clasificación RF-55 real almacenada en metadatos (el enum de BD usa valores distintos)
            metadatos['clasificacion_rf55'] = entidad.clasificacion_rf55

            orm = EventoEdgeComputingModel(
                id_dispositivo_iot=entidad.id_dispositivo_iot,
                id_sensor=entidad.id_sensor,
                tipo_evento=entidad.tipo_evento,
                severidad=entidad.severidad,
                variables_involucradas=entidad.variables_involucradas,
                fecha_captura=entidad.fecha_captura,
                fecha_procesamiento=entidad.fecha_procesamiento,
                origen_dato=entidad.origen_dato,
                estado_conectividad=entidad.estado_conectividad,
                metadatos=metadatos,
                enviado_backend=False,
                almacendado_buffer=not entidad.estado_conectividad,
            )
            self.db.add(orm)
            self.db.flush()
            self.db.refresh(orm)
            return self._a_entidad(orm)
        except Exception as exc:
            raise_from_db_error(exc)

    @staticmethod
    def _a_entidad(orm: EventoEdgeComputingModel) -> EventoEdgeComputing:
        metadatos = dict(orm.metadatos or {})
        clasificacion_rf55 = metadatos.pop('clasificacion_rf55', orm.tipo_evento)
        return EventoEdgeComputing(
            id_evento_edge_computing=orm.id_evento_edge_computing,
            id_dispositivo_iot=orm.id_dispositivo_iot,
            id_sensor=orm.id_sensor,
            clasificacion_rf55=clasificacion_rf55,
            tipo_evento=orm.tipo_evento,
            severidad=orm.severidad,
            variables_involucradas=list(orm.variables_involucradas or []),
            fecha_captura=orm.fecha_captura,
            fecha_procesamiento=orm.fecha_procesamiento,
            origen_dato=orm.origen_dato,
            estado_conectividad=orm.estado_conectividad,
            metadatos=metadatos,
        )
