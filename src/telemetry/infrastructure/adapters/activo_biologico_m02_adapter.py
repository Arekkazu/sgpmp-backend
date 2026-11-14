# | Fecha      | Nombre  | Que se hizo |
# |------------|---------|-------------|
# | 2026-10-22 | Leandro | DEV-44 RF-61: resuelve ubicacion y contexto a la captura |
"""Consulta fuentes historicas M02 sin sustituir una captura por el presente."""
from datetime import datetime
from sqlalchemy import text
from src.telemetry.domain.repositories.activo_biologico_dependency_port import ActivoBiologicoDependencyPort, ActivoBiologicoInfo


class ActivoBiologicoM02Adapter(ActivoBiologicoDependencyPort):
    def __init__(self, db):
        self.db = db

    def obtener_activos_en_momento(self, id_infraestructura, timestamp):
        filas=self.db.execute(text('''SELECT a.id_activo_biologico,a.tipo::text AS modelo_manejo
            FROM modulo2.activos_biologicos a
            WHERE a.fecha_creacion<=:captura AND EXISTS (
                SELECT 1 FROM modulo2.historial_infraestructura_activo h
                WHERE h.id_activo_biologico=a.id_activo_biologico AND h.id_infraestructura=:area
                  AND h.fecha_inicio<=:captura AND (h.fecha_fin IS NULL OR h.fecha_fin>:captura))
              AND COALESCE(
                (SELECT e.id_estado_nuevo FROM modulo2.historicos_estados_activos e
                 WHERE e.id_activo_biologico=a.id_activo_biologico AND e.fecha_cambio<=:captura
                 ORDER BY e.fecha_cambio DESC,e.id_historico_estado_activo DESC LIMIT 1),
                (SELECT e.id_estado_anterior FROM modulo2.historicos_estados_activos e
                 WHERE e.id_activo_biologico=a.id_activo_biologico AND e.fecha_cambio>:captura
                 ORDER BY e.fecha_cambio,e.id_historico_estado_activo LIMIT 1),a.id_estado)
                IN (SELECT id_estado_activo_biologico FROM modulo2.estados_activos_biologicos
                    WHERE nombre IN ('ACTIVO','EN_TRATAMIENTO','AISLADO'))
            ORDER BY a.id_activo_biologico'''),{'area':id_infraestructura,'captura':timestamp}).all()
        return [ActivoBiologicoInfo(f.id_activo_biologico,f.modelo_manejo) for f in filas]

    def obtener_contexto(self, id_activo_biologico, timestamp):
        p={'id':id_activo_biologico,'captura':timestamp}
        ubicacion=self.db.execute(text('''SELECT id_historial,id_infraestructura,fecha_inicio,fecha_fin
            FROM modulo2.historial_infraestructura_activo WHERE id_activo_biologico=:id
              AND fecha_inicio<=:captura AND (fecha_fin IS NULL OR fecha_fin>:captura)
            ORDER BY fecha_inicio DESC,id_historial DESC LIMIT 1'''),p).mappings().first()
        historico=self.db.execute(text('''SELECT id_historial_activo,json_snapshot,fecha_evento
            FROM modulo2.historial_activos WHERE id_activo_biologico=:id AND fecha_evento<=:captura
            ORDER BY fecha_evento DESC,version DESC LIMIT 1'''),p).mappings().first()
        fase=self.db.execute(text('''SELECT g.id_gestion_fases,g.id_ciclo_productiva,
            g.id_ciclos_productivo_biologico,b.id_ciclo_biologico,b.nombre,
            c.nombre AS ciclo_productivo,g.fecha_inicio,g.fecha_finalizacion
            FROM modulo2.gestiones_fases g
            JOIN modulo9.ciclos_productivos c ON c.id_ciclo_productivo=g.id_ciclo_productiva
            JOIN modulo9.ciclos_productivos_biologicos cb ON cb.id_ciclos_productivo_biologico=g.id_ciclos_productivo_biologico
            JOIN modulo9.ciclos_biologicos b ON b.id_ciclo_biologico=cb.id_ciclo_biologico
            WHERE g.id_activo_biologico=:id AND g.fecha_inicio<=:captura
              AND (g.fecha_finalizacion IS NULL OR g.fecha_finalizacion>:captura)
            ORDER BY g.fecha_inicio DESC,g.id_gestion_fases DESC LIMIT 1'''),p).mappings().first()
        peso=self.db.execute(text('''SELECT e.id_eventos,e.fecha,c.valor_medicion,c.unidad_medida,c.tipo_agregacion
            FROM modulo2.eventos_activos e JOIN modulo2.eventos_crecimeinto c ON c.id_evento=e.id_eventos
            WHERE e.id_activo_biologico=:id AND e.fecha<=:captura AND upper(c.tipo_medicion)='PESO'
            ORDER BY e.fecha DESC,e.id_eventos DESC LIMIT 1'''),p).mappings().first()
        sanitario=self.db.execute(text('''SELECT e.id_eventos,e.fecha,s.tipo::text
            FROM modulo2.eventos_activos e JOIN modulo2.eventos_sanitarios s ON s.id_evento=e.id_eventos
            WHERE e.id_activo_biologico=:id AND e.fecha<=:captura
            ORDER BY e.fecha DESC,e.id_eventos DESC LIMIT 1'''),p).mappings().first()
        snapshot=historico['json_snapshot'] if historico else {}
        nacimiento=(snapshot.get('detalle_individual') or {}).get('fecha_nacimiento')
        # M02 conserva nacimiento, pero no publica edad_dias historica ni una
        # regla de calendario/redondeo. Se preservan los insumos sin inventarla.
        edad=None
        def serializar(fila):
            if not fila:return None
            return {k:v.isoformat() if isinstance(v,datetime) else str(v) if k=='valor_medicion' else v for k,v in fila.items()}
        return {'timestamp_captura':timestamp.isoformat(),'id_activo_biologico':id_activo_biologico,
            'id_especie':snapshot.get('id_especie'),'fase_productiva':serializar(fase),
            'ubicacion':serializar(ubicacion),
            'edad_dias':edad,'fecha_nacimiento':nacimiento,'peso_referencia':serializar(peso),
            'estado_sanitario_vigente':None,'ultimo_evento_sanitario':serializar(sanitario),
            'fuente_snapshot':historico['id_historial_activo'] if historico else None,
            'edad_referencia':None,
            'datos_no_disponibles':[k for k,v in {'fase_productiva':fase,'edad_dias':edad,
                'peso_referencia':peso,'estado_sanitario_vigente':None}.items() if v is None]}

    def historial_inconsistente(self,id_infraestructura,timestamp):
        return bool(self.db.execute(text('''SELECT EXISTS(SELECT 1 FROM modulo2.activos_biologicos a
            WHERE a.id_infraestructura=:area AND a.fecha_creacion<=:captura
              AND NOT EXISTS(SELECT 1 FROM modulo2.historial_infraestructura_activo h
                WHERE h.id_activo_biologico=a.id_activo_biologico AND h.fecha_inicio<=:captura
                  AND (h.fecha_fin IS NULL OR h.fecha_fin>:captura)))'''),
            {'area':id_infraestructura,'captura':timestamp}).scalar_one())

    def bloquear_activos(self,identificadores):
        if identificadores:
            self.db.execute(text('''SELECT id_activo_biologico FROM modulo2.activos_biologicos
                WHERE id_activo_biologico=ANY(:ids) ORDER BY id_activo_biologico FOR KEY SHARE'''),{'ids':sorted(set(identificadores))}).all()
