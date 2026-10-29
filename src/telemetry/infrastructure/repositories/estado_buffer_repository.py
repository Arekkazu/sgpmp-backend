# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-10-27 | Leandro | INC-M03-126-G27 RF-54: leer un único heartbeat vigente sin mezclar métricas antiguas ni omitir alcance de finca. |
from sqlalchemy import text
from src.shared.db_error_translator import raise_from_db_error
from src.shared.errors import InfrastructureError
from src.telemetry.domain.entities.estado_buffer import EstadoBufferReportado
from src.telemetry.domain.repositories.estado_buffer_repository import EstadoBufferRepository
from src.telemetry.infrastructure.dto.metricas_buffer_dto import MetricasBufferDTO


class SqlAlchemyEstadoBufferRepository(EstadoBufferRepository):
    def __init__(self, db):
        self.db = db

    def obtener(self, id_dispositivo_iot, ids_fincas_permitidas):
        try:
            fila = self.db.execute(text('''
                SELECT d.id_dispositivo_iot, h.id_heartbeat, h.fecha_registro AS fecha_reporte,
                       h.fecha_recepcion, h.estado_local_buffer, h.datos_pendientes_buffer AS datos_pendientes,
                       h.json_metricas_buffer
                FROM modulo9.dispositivos_iot d
                JOIN modulo9.infraestructuras i ON i.id_infraestructura=d.id_infraestructura
                LEFT JOIN LATERAL (
                    SELECT x.id_heartbeat,x.fecha_registro,x.fecha_recepcion,x.estado_local_buffer,
                           x.datos_pendientes_buffer,x.json_metricas_buffer
                    FROM modulo3.heartbeats x WHERE x.id_dispositivo_iot=d.id_dispositivo_iot
                    ORDER BY x.fecha_recepcion DESC,x.id_heartbeat DESC LIMIT 1
                ) h ON true
                WHERE d.id_dispositivo_iot=:id
                  AND (CAST(:fincas AS int[]) IS NULL OR i.id_finca=ANY(CAST(:fincas AS int[])))
            '''), {'id':id_dispositivo_iot,'fincas':ids_fincas_permitidas}).mappings().one_or_none()
        except Exception as exc:
            raise_from_db_error(exc)
        if fila is None:
            return None
        datos = dict(fila)
        snapshot = datos.pop('json_metricas_buffer')
        try:
            metricas = MetricasBufferDTO.model_validate(snapshot).a_dominio() if snapshot is not None else None
        except ValueError as exc:
            raise InfrastructureError('REPORTE_BUFFER_INVALIDO', 'El reporte de buffer almacenado no es válido.') from exc
        return EstadoBufferReportado(**datos,metricas=metricas)
