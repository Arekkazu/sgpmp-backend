# | Fecha      | Nombre  | Que se hizo |
# |------------|---------|-------------|
# | 2026-10-22 | Leandro | DEV-47 RF-63: serializa incidentes y consulta avisos persistidos |
# | 2026-10-25 | Arekkazu | INC-M03-135/136/137 RF-63: filtros id_usuario, rf_origen, registro_incompleto y verificación acotada |
# | 2026-10-25 | Arekkazu | USAB-M03 M3-14 RF-63: bitácora limitada a los equipos de las fincas del usuario |
# | 2026-10-27 | destroyerban | INC-M03-116-G59 RF-56 CA-8: filtro entidad_afectada_tipo y alcance por finca de PAQUETE_IA |
from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import String, and_, cast, false, or_, select, text
from sqlalchemy.orm import Session

from src.telemetry.domain.entities.evento_auditoria_iot import (
    ClasificacionRegistro,
    ComponenteOrigen,
    EntidadAfectadaTipo,
    EventoAuditoriaIot,
    SeveridadLog,
    TipoResultado,
)
from src.telemetry.domain.repositories.bitacora_auditoria_iot_repository import BitacoraAuditoriaIotRepository
from src.telemetry.infrastructure.models.alerta_model import AlertaModel
from src.telemetry.infrastructure.models.bitacora_auditoria_iot_model import BitacoraAuditoriaIotModel
from src.telemetry.infrastructure.models.heartbeat_model import HeartbeatModel
from src.telemetry.infrastructure.models.observacion_vision_model import ObservacionVisionModel
from src.telemetry.infrastructure.models.paquete_inferencia_model import PaqueteInferenciaModel
from src.telemetry.infrastructure.models.telemetria_model import TelemetriaModel

_SQL_EQUIPOS_DE_FINCAS = text(
    'SELECT d.id_dispositivo_iot FROM modulo9.dispositivos_iot d '
    'JOIN modulo9.infraestructuras i ON i.id_infraestructura = d.id_infraestructura '
    'WHERE i.id_finca = ANY(:fincas)'
)
_SQL_INFRAESTRUCTURAS_DE_FINCAS = text(
    'SELECT id_infraestructura FROM modulo9.infraestructuras WHERE id_finca = ANY(:fincas)'
)


class SqlAlchemyBitacoraAuditoriaIotRepository(BitacoraAuditoriaIotRepository):

    def __init__(self, db: Session) -> None:
        self.db = db

    def registrar(self, evento: EventoAuditoriaIot) -> EventoAuditoriaIot:
        try:
            orm = BitacoraAuditoriaIotModel(
                id_usuario=evento.id_usuario,
                nombre_usuario=evento.nombre_usuario,
                tipo_evento=evento.tipo_evento,
                modulo=evento.modulo,
                descripcion=evento.descripcion,
                resultado=evento.resultado.value if isinstance(evento.resultado, TipoResultado) else evento.resultado,
                direccion_ip=evento.direccion_ip,
                user_agent=evento.user_agent,
                id_sesion=evento.id_sesion,
                fecha_hora=evento.fecha_hora,
                accion_detallada=evento.accion_detallada,
                entidad_afectada_tipo=evento.entidad_afectada_tipo.value if isinstance(evento.entidad_afectada_tipo, EntidadAfectadaTipo) else evento.entidad_afectada_tipo,
                entidad_afectada_id=evento.entidad_afectada_id,
                severidad_log=evento.severidad_log.value if isinstance(evento.severidad_log, SeveridadLog) else evento.severidad_log,
                hash_integridad=evento.hash_integridad,
                clasificacion_registro=evento.clasificacion_registro.value if isinstance(evento.clasificacion_registro, ClasificacionRegistro) else evento.clasificacion_registro,
                retencion_aplicable=evento.retencion_aplicable,
                registro_incompleto=evento.registro_incompleto,
                componente_origen=evento.componente_origen.value if isinstance(evento.componente_origen, ComponenteOrigen) else evento.componente_origen,
            )
            self.db.add(orm)
            self.db.flush()
            self.db.refresh(orm)
            return self._a_entidad(orm)
        except Exception:
            # Auditoría es best-effort: no propaga error para no bloquear flujo principal
            return evento

    def obtener(
        self, id_evento: UUID, *, ids_fincas_permitidas: Optional[list[int]] = None,
    ) -> Optional[EventoAuditoriaIot]:
        q = self.db.query(BitacoraAuditoriaIotModel).filter(BitacoraAuditoriaIotModel.id_evento == id_evento)
        if ids_fincas_permitidas is not None:
            q = q.filter(self._de_las_fincas(ids_fincas_permitidas))
        orm = q.first()
        return self._marcar([self._a_entidad(orm)])[0] if orm else None

    def _de_las_fincas(self, ids_fincas: list[int]):
        """M3-14: solo los eventos de equipos, lecturas y alertas de esas fincas.

        La bitácora no guarda la finca: se llega a ella por la entidad afectada.
        ponytail: los eventos sin entidad o de otro tipo (VINCULACION, BUFFER,
        UMBRAL…) quedan fuera para quien no es auditor; si un rol con finca los
        necesita, agregar su tipo aquí con su propio camino a la finca.
        """
        m = BitacoraAuditoriaIotModel
        dispositivos = [fila[0] for fila in self.db.execute(_SQL_EQUIPOS_DE_FINCAS, {'fincas': ids_fincas}).all()]
        infraestructuras = [fila[0] for fila in self.db.execute(
            _SQL_INFRAESTRUCTURAS_DE_FINCAS, {'fincas': ids_fincas}).all()]
        if not infraestructuras:
            return false()

        def ids(columna, por):
            return m.entidad_afectada_id.in_(select(cast(columna, String)).where(por))

        # Las observaciones de visión también se registran como LECTURA, con su propio id.
        es_vision = m.tipo_evento.like('%VISION%')
        return or_(
            and_(m.entidad_afectada_tipo == 'DISPOSITIVO', m.entidad_afectada_id.in_([str(d) for d in dispositivos])),
            and_(m.entidad_afectada_tipo == 'HEARTBEAT', ids(
                HeartbeatModel.id_heartbeat, HeartbeatModel.id_dispositivo_iot.in_(dispositivos))),
            and_(m.entidad_afectada_tipo == 'LECTURA', ~es_vision, ids(
                TelemetriaModel.id_telemetria, TelemetriaModel.id_dispositivo_iot.in_(dispositivos))),
            and_(m.entidad_afectada_tipo == 'LECTURA', es_vision, ids(
                ObservacionVisionModel.id_observacion_vision,
                ObservacionVisionModel.id_dispositivo_iot.in_(dispositivos))),
            and_(m.entidad_afectada_tipo == 'ALERTA', ids(
                AlertaModel.id_alerta, AlertaModel.id_infraestructura.in_(infraestructuras))),
            # INC-M03-116-G59: el ciclo de vida del paquete (RF-56 CA-8) llega a la finca por su equipo.
            and_(m.entidad_afectada_tipo == 'PAQUETE_IA', ids(
                PaqueteInferenciaModel.id_paquetes_inferencia,
                PaqueteInferenciaModel.id_dispositivo_iot.in_(dispositivos))),
        )

    def listar(
        self,
        fecha_desde: Optional[datetime] = None,
        fecha_hasta: Optional[datetime] = None,
        tipo_evento: Optional[str] = None,
        severidad_log: Optional[str] = None,
        clasificacion_registro: Optional[str] = None,
        entidad_afectada_id: Optional[str] = None,
        resultado: Optional[str] = None,
        pagina: int = 1,
        por_pagina: int = 50,
        id_usuario: Optional[int] = None,
        rf_origen: Optional[str] = None,
        registro_incompleto: Optional[bool] = None,
        entidad_afectada_tipo: Optional[str] = None,
        *,
        ids_fincas_permitidas: Optional[list[int]] = None,
    ) -> tuple[list[EventoAuditoriaIot], int]:
        q = self.db.query(BitacoraAuditoriaIotModel)
        if ids_fincas_permitidas is not None:
            q = q.filter(self._de_las_fincas(ids_fincas_permitidas))
        if id_usuario is not None:
            q = q.filter(BitacoraAuditoriaIotModel.id_usuario == id_usuario)
        if rf_origen:
            # rf_origen es componente_origen: se filtra por él pero no se expone (RF-63).
            q = q.filter(BitacoraAuditoriaIotModel.componente_origen == rf_origen)
        if registro_incompleto is not None:
            q = q.filter(BitacoraAuditoriaIotModel.registro_incompleto == registro_incompleto)
        if fecha_desde:
            q = q.filter(BitacoraAuditoriaIotModel.fecha_hora >= fecha_desde)
        if fecha_hasta:
            q = q.filter(BitacoraAuditoriaIotModel.fecha_hora <= fecha_hasta)
        if tipo_evento:
            q = q.filter(BitacoraAuditoriaIotModel.tipo_evento == tipo_evento)
        if severidad_log:
            q = q.filter(BitacoraAuditoriaIotModel.severidad_log == severidad_log)
        if clasificacion_registro:
            q = q.filter(BitacoraAuditoriaIotModel.clasificacion_registro == clasificacion_registro)
        if entidad_afectada_tipo:
            q = q.filter(BitacoraAuditoriaIotModel.entidad_afectada_tipo == entidad_afectada_tipo)
        if entidad_afectada_id:
            q = q.filter(BitacoraAuditoriaIotModel.entidad_afectada_id == entidad_afectada_id)
        if resultado:
            q = q.filter(BitacoraAuditoriaIotModel.resultado == resultado)
        total = q.count()
        items = q.order_by(BitacoraAuditoriaIotModel.fecha_hora.desc()).offset((pagina - 1) * por_pagina).limit(por_pagina).all()
        return self._marcar([self._a_entidad(o) for o in items]), total

    def listar_todos_para_verificacion(
        self,
        fecha_desde: Optional[datetime] = None,
        fecha_hasta: Optional[datetime] = None,
        limite: Optional[int] = None,
    ) -> list[EventoAuditoriaIot]:
        q = self.db.query(BitacoraAuditoriaIotModel)
        if fecha_desde:
            q = q.filter(BitacoraAuditoriaIotModel.fecha_hora >= fecha_desde)
        if fecha_hasta:
            q = q.filter(BitacoraAuditoriaIotModel.fecha_hora <= fecha_hasta)
        q = q.order_by(BitacoraAuditoriaIotModel.fecha_hora)
        if limite is not None:
            q = q.limit(limite)
        return [self._a_entidad(o) for o in q.all()]

    def _marcar(self, eventos):
        if not eventos:
            return eventos
        tabla = BitacoraAuditoriaIotModel
        ids = [str(e.id_evento) for e in eventos]
        afectados = set(self.db.query(tabla.accion_detallada['compromiso']['id_evento'].astext).filter(
            tabla.tipo_evento == 'INTEGRIDAD_COMPROMETIDA',
            tabla.accion_detallada['compromiso']['id_evento'].astext.in_(ids),
        ).all())
        ids_comprometidos = {fila[0] for fila in afectados}
        for evento in eventos:
            evento.integridad_comprometida = str(evento.id_evento) in ids_comprometidos
        return eventos

    def bloquear_integridad(self, id_evento):
        self.db.execute(text('SELECT pg_advisory_xact_lock(6363, hashtext(:id))'), {'id': str(id_evento)})

    def buscar_incidente(self, clave):
        orm = self.db.query(BitacoraAuditoriaIotModel).filter(
            BitacoraAuditoriaIotModel.tipo_evento == 'INTEGRIDAD_COMPROMETIDA',
            BitacoraAuditoriaIotModel.accion_detallada['compromiso'] == clave,
        ).order_by(BitacoraAuditoriaIotModel.fecha_hora).first()
        return self._a_entidad(orm) if orm else None

    def aviso_confirmado(self, id_incidente):
        return self.db.query(BitacoraAuditoriaIotModel.id_evento).filter(
            BitacoraAuditoriaIotModel.tipo_evento == 'INTEGRIDAD_COMPROMETIDA',
            BitacoraAuditoriaIotModel.accion_detallada['aviso_incidente'].astext == str(id_incidente),
        ).first() is not None

    @staticmethod
    def _a_entidad(orm: BitacoraAuditoriaIotModel) -> EventoAuditoriaIot:
        return EventoAuditoriaIot(
            id_evento=orm.id_evento,
            tipo_evento=orm.tipo_evento,
            fecha_hora=orm.fecha_hora,
            resultado=TipoResultado(orm.resultado),
            modulo=orm.modulo,
            id_usuario=orm.id_usuario,
            nombre_usuario=orm.nombre_usuario,
            descripcion=orm.descripcion,
            direccion_ip=orm.direccion_ip,
            user_agent=orm.user_agent,
            id_sesion=orm.id_sesion,
            accion_detallada=orm.accion_detallada,
            entidad_afectada_tipo=EntidadAfectadaTipo(orm.entidad_afectada_tipo) if orm.entidad_afectada_tipo else None,
            entidad_afectada_id=orm.entidad_afectada_id,
            severidad_log=SeveridadLog(orm.severidad_log),
            hash_integridad=orm.hash_integridad,
            clasificacion_registro=ClasificacionRegistro(orm.clasificacion_registro),
            retencion_aplicable=orm.retencion_aplicable,
            registro_incompleto=orm.registro_incompleto,
            componente_origen=ComponenteOrigen(orm.componente_origen) if orm.componente_origen else None,
            timestamp_registro=orm.timestamp_registro,
        )
