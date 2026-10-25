# | Fecha      | Nombre  | Que se hizo |
# |------------|---------|-------------|
# | 2026-10-22 | Leandro | DEV-44 RF-48/61: cierra origen sin inventar lecturas de destino |
from sqlalchemy import text
from src.shared.errors import ConflictError
from src.telemetry.application.use_cases.infraestructura.evidencia_vinculacion import registrar_evidencia
from src.telemetry.infrastructure.repositories.bitacora_auditoria_iot_repository import SqlAlchemyBitacoraAuditoriaIotRepository


class VinculacionTrasladoM03Adapter:
    def __init__(self,db):
        self.db=db

    def procesar(self, *, id_activo, origen, destino, fecha_efectiva, id_movimiento, id_usuario):
        # RF-48 ya mantiene FOR UPDATE sobre el activo. Misma clave para reintentos del movimiento.
        self.db.execute(text('SELECT pg_advisory_xact_lock(3544,:id)'),{'id':id_activo})
        procesado=self.db.execute(text('''SELECT EXISTS(SELECT 1 FROM modulo3.bitacora_auditoria_iot
            WHERE tipo_evento='TRASLADO_PROCESADO' AND accion_detallada->>'id_movimiento'=:mov)'''),{'mov':str(id_movimiento)}).scalar_one()
        if procesado:return
        dispositivos=list(self.db.execute(text('''SELECT DISTINCT t.id_dispositivo_iot
            FROM modulo3.vinculaciones_lecturas v JOIN modulo3.telemetrias t ON t.id_telemetria=v.id_telemetria
            WHERE v.id_activo_biologico=:id AND v.id_infraestructura=:origen
              AND v.fecha_fin_vinculacion IS NULL ORDER BY t.id_dispositivo_iot'''),{'id':id_activo,'origen':origen}).scalars())
        for dispositivo in dispositivos:
            if not self.db.execute(text('SELECT pg_try_advisory_xact_lock(3505,:id)'),{'id':dispositivo}).scalar_one():
                # RF-48 mantiene FOR UPDATE sobre el activo. Esperar aqui puede
                # cruzarse con el FK del worker que ya mantiene el lock de dispositivo.
                raise ConflictError('TRANSFERENCIA_CONCURRENTE','El dispositivo tiene una vinculacion en proceso; reintente la transferencia.')
        cerradas=list(self.db.execute(text('''UPDATE modulo3.vinculaciones_lecturas
            SET estado_vinculacion='SUPERADA',fecha_fin_vinculacion=:fecha
            WHERE id_activo_biologico=:id AND id_infraestructura=:origen
              AND estado_vinculacion='CONFIRMADA' AND fecha_fin_vinculacion IS NULL
              AND fecha_inicio_vinculacion<:fecha RETURNING id_vinculacion_lectura'''),
            {'id':id_activo,'origen':origen,'fecha':fecha_efectiva}).scalars())
        # DB-13 modela vinculos POR LECTURA. No se reutiliza una lectura de A para B.
        # El worker abre los vinculos de destino al recibir sus propias lecturas.
        registrar_evidencia(SqlAlchemyBitacoraAuditoriaIotRepository(self.db),'TRASLADO_PROCESADO',id_movimiento,
            {'id_movimiento':id_movimiento,'id_activo_biologico':id_activo,'origen':origen,'destino':destino,
             'fecha_efectiva':fecha_efectiva.isoformat(),'vinculaciones_superadas':cerradas,
             'apertura_destino':'AL_PROCESAR_LECTURAS_DEL_DESTINO'},id_usuario,entidad=None)
