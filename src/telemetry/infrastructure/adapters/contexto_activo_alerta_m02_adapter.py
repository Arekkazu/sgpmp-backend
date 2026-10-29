# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-28 | destroyerban | INC-M03-169-G77 RF-57 Fase 3: resuelve el activo de la alerta (RF-61, asociación del sensor, unidad) |
"""RF-57 Fase 3 / E6 / CA-7: a qué activo biológico pertenece la alerta de un sensor.

Orden (del dato más preciso al más general):
1. Vinculación RF-61 de la lectura (``modulo3.vinculaciones_lecturas``), si el evento trae ``id_telemetria``.
2. Asociación explícita del sensor a un activo (M02 ``asociaciones_activos_sensores`` tipo directa o
   poblacional) vigente en el momento del evento.
3. Asociación ambiental del sensor, si apunta a un único activo.
4. Si el sensor no tiene asociaciones: el único activo presente en la unidad productiva en ese momento.
Más de un candidato en el mismo nivel no se adivina: queda incompleto (VARIOS_ACTIVOS_CANDIDATOS).
"""
from __future__ import annotations

from sqlalchemy import text

from src.shared.db_error_translator import raise_from_db_error
from src.telemetry.domain.repositories.contexto_activo_alerta_port import ContextoActivoAlerta, ContextoActivoAlertaPort
from src.telemetry.infrastructure.adapters.activo_biologico_m02_adapter import ActivoBiologicoM02Adapter

_SQL_VINCULACION = text("""
    SELECT id_activo_biologico FROM modulo3.vinculaciones_lecturas
    WHERE id_telemetria = :lectura AND id_activo_biologico IS NOT NULL
      AND fecha_fin_vinculacion IS NULL AND estado_vinculacion <> 'SUPERADA'
    ORDER BY fecha_creacion DESC, id_vinculacion_lectura DESC LIMIT 1
""")

_SQL_ASOCIACIONES = text("""
    SELECT DISTINCT id_activo_biologico, tipo::text AS tipo
    FROM modulo2.asociaciones_activos_sensores
    WHERE id_sensor = :sensor AND estado_asociacion = 'ACTIVA'
      AND fecha_inicio <= :momento AND (fecha_fin IS NULL OR fecha_fin > :momento)
""")

_SQL_DESCRIPCION = text("""
    SELECT a.id_activo_biologico, a.identificador, a.tipo AS modelo_manejo, a.id_especie, e.nombre AS especie,
           i.id_infraestructura, i.nombre AS unidad_productiva, i.tipo AS tipo_unidad,
           f.id_finca, f.nombre AS finca, f.ubicacion AS ubicacion_finca
    FROM modulo2.activos_biologicos a
    LEFT JOIN modulo9.especies e ON e.id_especie = a.id_especie
    LEFT JOIN modulo9.infraestructuras i ON i.id_infraestructura = COALESCE(:area_momento, a.id_infraestructura)
    LEFT JOIN modulo9.fincas f ON f.id_finca = i.id_finca
    WHERE a.id_activo_biologico = :activo
""")


class ContextoActivoAlertaM02Adapter(ContextoActivoAlertaPort):
    def __init__(self, db):
        self.db = db
        self._historico = ActivoBiologicoM02Adapter(db)

    def resolver(self, id_sensor, id_infraestructura, momento, id_telemetria=None):
        try:
            if id_telemetria is not None:
                activo = self.db.execute(_SQL_VINCULACION, {"lectura": id_telemetria}).scalar_one_or_none()
                if activo is not None:
                    return self._completo(activo, "VINCULACION_RF61", momento)
            asociaciones = self.db.execute(_SQL_ASOCIACIONES, {"sensor": id_sensor, "momento": momento}).all()
            explicitas = {a.id_activo_biologico for a in asociaciones if a.tipo in ("directa", "poblacional")}
            ambientales = {a.id_activo_biologico for a in asociaciones if a.tipo == "ambiental"}
            for candidatos, fuente in ((explicitas, "ASOCIACION_SENSOR"), (ambientales, "ASOCIACION_AMBIENTAL")):
                if len(candidatos) == 1:
                    return self._completo(next(iter(candidatos)), fuente, momento)
                if len(candidatos) > 1:
                    return ContextoActivoAlerta(None, None, fuente, "VARIOS_ACTIVOS_CANDIDATOS")
            if id_infraestructura is not None:
                presentes = self._historico.obtener_activos_en_momento(id_infraestructura, momento)
                if len(presentes) == 1:
                    return self._completo(presentes[0].id_activo_biologico, "UNIDAD_PRODUCTIVA", momento)
                if len(presentes) > 1:
                    return ContextoActivoAlerta(None, None, "UNIDAD_PRODUCTIVA", "VARIOS_ACTIVOS_CANDIDATOS")
            return ContextoActivoAlerta(None, None, None, "SIN_ACTIVO_ASOCIADO")
        except Exception as exc:
            raise_from_db_error(exc)

    def _completo(self, id_activo, fuente, momento) -> ContextoActivoAlerta:
        historico = self._historico.obtener_contexto(id_activo, momento)
        area_momento = (historico.get("ubicacion") or {}).get("id_infraestructura")
        fila = self.db.execute(_SQL_DESCRIPCION, {"activo": id_activo, "area_momento": area_momento}).mappings().one()
        contexto = {
            "id_activo_biologico": fila["id_activo_biologico"],
            "identificador": fila["identificador"],
            "modelo_manejo": fila["modelo_manejo"],
            "id_especie": fila["id_especie"],
            "especie": fila["especie"],
            "unidad_productiva": {"id_infraestructura": fila["id_infraestructura"], "nombre": fila["unidad_productiva"],
                                  "tipo": fila["tipo_unidad"]},
            "ubicacion": {"id_finca": fila["id_finca"], "finca": fila["finca"], "geografica": fila["ubicacion_finca"]},
            "fuente_vinculacion": fuente,
            "rf61": historico,
        }
        return ContextoActivoAlerta(id_activo, contexto, fuente)
