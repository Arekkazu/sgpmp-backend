from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.shared.db_error_translator import raise_from_db_error
from src.telemetry.domain.entities.telemetria import PaqueteInferencia
from src.telemetry.domain.repositories.paquete_inferencia_repository import PaqueteInferenciaRepository
from src.telemetry.infrastructure.models.paquete_inferencia_model import PaqueteInferenciaModel


class SqlAlchemyPaqueteInferenciaRepository(PaqueteInferenciaRepository):

    def __init__(self, db: Session) -> None:
        self.db = db

    def guardar(self, entidad: PaqueteInferencia) -> PaqueteInferencia:
        try:
            orm = PaqueteInferenciaModel(
                id_sensor=entidad.id_sensor,
                id_dispositivo_iot=entidad.id_dispositivo_iot,
                id_evento_edge_computing=entidad.id_evento_edge_computing,
                tipo_variable=entidad.tipo_variable,
                valor_numerico=entidad.valor_numerico,
                unidad=entidad.unidad,
                estado_calidad=entidad.estado_calidad,
                estado_desviacion=entidad.estado_desviacion,
                severidad=entidad.severidad,
                origen=entidad.origen,
                contexto_ambiental=entidad.contexto_ambiental,
                # Mapeo explícito del typo de BD
                contexto_incomplento=entidad.contexto_incompleto,
                metadatos=entidad.metadatos,
                id_version_modelo=entidad.id_version_modelo,
                fecha_envio=entidad.fecha_envio,
                estado_paquete=entidad.estado_paquete,
                intento_envios=entidad.intento_envios,
            )
            self.db.add(orm)
            self.db.flush()
            self.db.refresh(orm)
            return self._a_entidad(orm)
        except Exception as exc:
            raise_from_db_error(exc)

    def actualizar_estado(self, id_paquete: int, estado: str, intento: int) -> None:
        try:
            self.db.execute(
                text(
                    'UPDATE modulo3.paquetes_inferencia '
                    'SET estado_paquete = :estado, intento_envios = :intento '
                    'WHERE id_paquetes_inferencia = :id'
                ),
                {'estado': estado, 'intento': intento, 'id': id_paquete},
            )
            self.db.flush()
        except Exception as exc:
            raise_from_db_error(exc)

    @staticmethod
    def _a_entidad(orm: PaqueteInferenciaModel) -> PaqueteInferencia:
        return PaqueteInferencia(
            id_paquetes_inferencia=orm.id_paquetes_inferencia,
            id_sensor=orm.id_sensor,
            id_dispositivo_iot=orm.id_dispositivo_iot,
            id_evento_edge_computing=orm.id_evento_edge_computing,
            tipo_variable=orm.tipo_variable,
            valor_numerico=orm.valor_numerico,
            unidad=orm.unidad,
            estado_calidad=orm.estado_calidad,
            estado_desviacion=orm.estado_desviacion,
            severidad=orm.severidad,
            origen=orm.origen,
            contexto_ambiental=orm.contexto_ambiental,
            # Mapeo explícito del typo de BD → nombre limpio en entidad
            contexto_incompleto=orm.contexto_incomplento,
            metadatos=orm.metadatos,
            id_version_modelo=orm.id_version_modelo,
            fecha_envio=orm.fecha_envio,
            estado_paquete=orm.estado_paquete,
            intento_envios=orm.intento_envios,
        )
