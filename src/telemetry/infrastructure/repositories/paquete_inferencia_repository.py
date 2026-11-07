# | Fecha      | Nombre  | Que se hizo |
# |------------|---------|-------------|
# | 2026-10-22 | Leandro | DEV-47 RF-63: audita paquete pendiente y resultado real de envio |
# | 2026-10-26 | destroyerban | INC-M03-112-G55 RF-56: envio de pendientes en lotes de maximo 500 |
# | 2026-10-27 | destroyerban | INC-M03-113-G56 RF-56: 5 intentos con backoff 0/5/15/30/60 s y reenvio automatico |
# | 2026-10-27 | destroyerban | INC-M03-116-G59 RF-56: consulta del paquete por id con alcance por finca |
# | 2026-10-30 | Arekkazu | RF-66: la cola bloquea con FOR NO KEY UPDATE (el motor IA inserta resultados que referencian el paquete) |
from src.telemetry.application.use_cases.auditoria.evidencia_iot import registrar_evidencia
from src.telemetry.domain.entities.evento_auditoria_iot import ComponenteOrigen, EntidadAfectadaTipo
from src.telemetry.infrastructure.repositories.bitacora_auditoria_iot_repository import (
    _SQL_EQUIPOS_DE_FINCAS,
    SqlAlchemyBitacoraAuditoriaIotRepository,
)

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import case, func, or_, text
from sqlalchemy.orm import Session

from src.shared.db_error_translator import raise_from_db_error
from src.telemetry.domain.entities.telemetria import ESPERAS_REINTENTO_INFERENCIA_SEG, PaqueteInferencia
from src.telemetry.domain.repositories.paquete_inferencia_repository import PaqueteInferenciaRepository
from src.telemetry.infrastructure.models.paquete_inferencia_model import PaqueteInferenciaModel
from src.telemetry.infrastructure.models.evento_edge_model import EventoEdgeComputingModel


# Espera antes del siguiente intento según los intentos ya hechos (RF-56 restricción 14).
_ESPERA_SQL = case(
    {n: espera for n, espera in enumerate(ESPERAS_REINTENTO_INFERENCIA_SEG)},
    value=PaqueteInferenciaModel.intento_envios,
    else_=ESPERAS_REINTENTO_INFERENCIA_SEG[-1],
)


class SqlAlchemyPaqueteInferenciaRepository(PaqueteInferenciaRepository):

    def __init__(self, db: Session) -> None:
        self.db = db

    def obtener_por_evento(
        self, id_evento: int, *, bloquear_evento: bool = False,
    ) -> Optional[PaqueteInferencia]:
        try:
            if bloquear_evento:
                # Bloquear el padre también protege el caso sin paquete.
                # Una segunda consolidación espera al commit de la primera.
                self.db.query(EventoEdgeComputingModel.id_evento_edge_computing).filter(
                    EventoEdgeComputingModel.id_evento_edge_computing == id_evento,
                ).with_for_update().one()
            orm = self.db.query(PaqueteInferenciaModel).filter(
                PaqueteInferenciaModel.id_evento_edge_computing == id_evento,
            ).order_by(PaqueteInferenciaModel.id_paquetes_inferencia).first()
            return self._a_entidad(orm) if orm else None
        except Exception as exc:
            raise_from_db_error(exc)

    def obtener(
        self, id_paquete: int, *, ids_fincas_permitidas: Optional[list[int]] = None,
    ) -> Optional[PaqueteInferencia]:
        try:
            q = self.db.query(PaqueteInferenciaModel).filter(
                PaqueteInferenciaModel.id_paquetes_inferencia == id_paquete)
            if ids_fincas_permitidas is not None:
                # Mismo camino a la finca que la bitácora RF-63 (M3-14): por el equipo.
                equipos = [fila[0] for fila in self.db.execute(
                    _SQL_EQUIPOS_DE_FINCAS, {'fincas': ids_fincas_permitidas}).all()]
                q = q.filter(PaqueteInferenciaModel.id_dispositivo_iot.in_(equipos))
            orm = q.first()
            return self._a_entidad(orm) if orm else None
        except Exception as exc:
            raise_from_db_error(exc)

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
            self._auditar(orm, 'PAQUETE_INFERENCIA_GENERADO')
            if orm.contexto_incomplento:
                self._auditar(orm, 'CONTEXTO_INCOMPLETO')
            return self._a_entidad(orm)
        except Exception as exc:
            raise_from_db_error(exc)

    def actualizar_estado(
        self, id_paquete: int, estado: str, intento: int, fecha_intento: Optional[datetime] = None,
    ) -> None:
        try:
            orm = self.db.query(PaqueteInferenciaModel).filter(
                PaqueteInferenciaModel.id_paquetes_inferencia == id_paquete).with_for_update().one()
            anterior = (orm.estado_paquete, orm.intento_envios)
            if anterior == (estado, intento):
                return
            orm.estado_paquete, orm.intento_envios = estado, intento
            if fecha_intento is not None:
                orm.fecha_envio = fecha_intento
            self.db.flush()
            if estado in ('ENVIADO', 'FALLIDO'):
                self._auditar(orm, 'PAQUETE_ENVIADO_IA' if estado == 'ENVIADO' else 'FALLO_ENVIO_PAQUETE')
            elif intento > anterior[1]:
                # RF-56 restricción 14: intento no confirmado, queda programado el siguiente.
                self._auditar(orm, 'REINTENTO_ENVIO_PAQUETE_PROGRAMADO')
        except Exception as exc:
            raise_from_db_error(exc)

    def listar_pendientes(self, limite: int) -> list[PaqueteInferencia]:
        try:
            filas = self.db.query(PaqueteInferenciaModel).join(
                EventoEdgeComputingModel,
                EventoEdgeComputingModel.id_evento_edge_computing == PaqueteInferenciaModel.id_evento_edge_computing,
            ).filter(
                PaqueteInferenciaModel.estado_paquete == 'PENDIENTE',
                or_(
                    PaqueteInferenciaModel.intento_envios == 0,
                    PaqueteInferenciaModel.fecha_envio + func.make_interval(0, 0, 0, 0, 0, 0, _ESPERA_SQL)
                    <= func.now(),
                ),
            ).order_by(
                # RF-56 restricción 6: orden cronológico y secuencia original.
                EventoEdgeComputingModel.fecha_captura,
                PaqueteInferenciaModel.id_paquetes_inferencia,
            # FOR NO KEY UPDATE y no FOR UPDATE: el lote queda bloqueado mientras se espera al motor,
            # y el motor responde insertando en modulo4.resultados_inferencia, cuya FK hacia el
            # paquete pide FOR KEY SHARE. Con FOR UPDATE las dos esperas se cruzaban hasta el
            # timeout de 10 s y el paquete contaba un intento fallido aunque el resultado se guardó.
            ).limit(limite).with_for_update(of=PaqueteInferenciaModel, skip_locked=True, key_share=True).all()
            return [self._a_entidad(orm) for orm in filas]
        except Exception as exc:
            raise_from_db_error(exc)

    def _auditar(self, orm, tipo):
        from src.telemetry.domain.entities.evento_auditoria_iot import TipoResultado, SeveridadLog
        fallo = tipo in ('FALLO_ENVIO_PAQUETE', 'REINTENTO_ENVIO_PAQUETE_PROGRAMADO')
        registrar_evidencia(SqlAlchemyBitacoraAuditoriaIotRepository(self.db), tipo,
            ComponenteOrigen.RF56, entidad=EntidadAfectadaTipo.PAQUETE_IA,
            identificador=orm.id_paquetes_inferencia,
            resultado=TipoResultado.FALLIDO if fallo else TipoResultado.EXITOSO,
            severidad=SeveridadLog.WARNING if fallo else SeveridadLog.INFO,
            detalle={'estado_paquete': orm.estado_paquete, 'intentos': orm.intento_envios,
                     'id_evento_edge': orm.id_evento_edge_computing,
                     'id_dispositivo_iot': orm.id_dispositivo_iot})

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
