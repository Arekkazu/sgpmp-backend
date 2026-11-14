# | Fecha      | Nombre  | Que se hizo |
# |------------|---------|-------------|
# | 2026-10-22 | Leandro | DEV-28 RF-60: reconstruye ventanas y consulta evidencia RF-63 |
from sqlalchemy import text
from src.telemetry.domain.entities.secuencia_vision import VentanaVision


class SqlAlchemyVentanasVisionRepository:
    def __init__(self,db):
        self.db=db

    def recientes(self,identificador,cantidad):
        # Reevalua el ultimo cierre de la camara tambien cuando la fila
        # reclamada llega tarde y completa una secuencia antes incompleta.
        filas=self.db.execute(text('''SELECT id_observacion_vision,id_dispositivo_iot,
            id_infraestructura,fecha_inicio_ventana,fecha_observacion,cobertura_ventana
            FROM modulo3.observaciones_vision
            WHERE id_dispositivo_iot=(SELECT id_dispositivo_iot FROM modulo3.observaciones_vision
                WHERE id_observacion_vision=:id)
            ORDER BY fecha_observacion DESC,id_observacion_vision DESC LIMIT :cantidad'''),
            {'id':identificador,'cantidad':cantidad}).all()
        # Un lote antiguo sin inicio verificable interrumpe la cadena.
        resultado=[]
        for f in filas:
            if f.fecha_inicio_ventana is None:
                break
            resultado.append(VentanaVision(*f))
        return resultado

    def diagnostico_existente(self,identificador):
        return bool(self.db.execute(text('''SELECT EXISTS (SELECT 1 FROM modulo3.bitacora_auditoria_iot
            WHERE tipo_evento='SIN_DETECCION_VALIDA' AND entidad_afectada_tipo='LECTURA'
              AND entidad_afectada_id=:id AND accion_detallada->>'fuente'='observaciones_vision')'''),
            {'id':str(identificador)}).scalar_one())
