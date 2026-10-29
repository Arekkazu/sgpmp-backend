# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-10-27 | Leandro | INC-M03-126-G27 RF-54: leer un único heartbeat vigente sin mezclar métricas antiguas ni omitir alcance de finca. |
# | 2026-10-29 | Arekkazu | TC-DIS-148 RF-54: listado del buffer de todos los dispositivos del alcance |
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
        filas = self._consultar(id_dispositivo_iot, ids_fincas_permitidas)
        return filas[0] if filas else None

    def listar(self, ids_fincas_permitidas):
        reportes = self._consultar(None, ids_fincas_permitidas)
        # Primero los que más se acercan a perder datos; sin métricas al final.
        return sorted(reportes, key=lambda r: (
            r.metricas is None,
            -(r.metricas.porcentaje_ocupacion if r.metricas else 0),
            -(r.datos_pendientes or 0),
        ))

    def _consultar(self, id_dispositivo_iot, ids_fincas_permitidas):
        try:
            filas = self.db.execute(text('''
                SELECT d.id_dispositivo_iot, d.serial, d.descripcion,
                       i.nombre AS nombre_infraestructura, f.nombre AS nombre_finca,
                       e.estado_actual::text AS estado_dispositivo,
                       h.id_heartbeat, h.fecha_registro AS fecha_reporte,
                       h.fecha_recepcion, h.estado_local_buffer, h.datos_pendientes_buffer AS datos_pendientes,
                       h.json_metricas_buffer
                FROM modulo9.dispositivos_iot d
                JOIN modulo9.infraestructuras i ON i.id_infraestructura=d.id_infraestructura
                JOIN modulo9.fincas f ON f.id_finca=i.id_finca
                LEFT JOIN LATERAL (
                    SELECT x.id_heartbeat,x.fecha_registro,x.fecha_recepcion,x.estado_local_buffer,
                           x.datos_pendientes_buffer,x.json_metricas_buffer
                    FROM modulo3.heartbeats x WHERE x.id_dispositivo_iot=d.id_dispositivo_iot
                    ORDER BY x.fecha_recepcion DESC,x.id_heartbeat DESC LIMIT 1
                ) h ON true
                LEFT JOIN LATERAL (
                    SELECT y.estado_actual FROM modulo3.estados_dispositivos_iot y
                    WHERE y.id_dispositivo_iot=d.id_dispositivo_iot
                    ORDER BY y.fecha_ultima_actualizacion DESC LIMIT 1
                ) e ON true
                WHERE (CAST(:id AS int) IS NULL AND d.es_activo OR d.id_dispositivo_iot=CAST(:id AS int))
                  AND (CAST(:fincas AS int[]) IS NULL OR i.id_finca=ANY(CAST(:fincas AS int[])))
                ORDER BY f.nombre, i.nombre, d.serial
            '''), {'id':id_dispositivo_iot,'fincas':ids_fincas_permitidas}).mappings().all()
        except Exception as exc:
            raise_from_db_error(exc)
        return [self._a_reporte(dict(fila)) for fila in filas]

    @staticmethod
    def _a_reporte(datos):
        snapshot = datos.pop('json_metricas_buffer')
        try:
            metricas = MetricasBufferDTO.model_validate(snapshot).a_dominio() if snapshot is not None else None
        except ValueError as exc:
            raise InfrastructureError('REPORTE_BUFFER_INVALIDO', 'El reporte de buffer almacenado no es válido.') from exc
        return EstadoBufferReportado(**datos,metricas=metricas)
