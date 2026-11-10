# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-04 | Arekkazu | M06 RF-83/85/87: cola de eventos de M02 para la medición por evento |
# | 2026-11-08 | destroyerban | INC-M06-312-G14 RF-83: evento en período cerrado queda pendiente y alerta |
# | 2026-11-08 | destroyerban | INC-M06-313-G14 RF-83: excluye y registra los activos no elegibles |
# | 2026-11-09 | destroyerban | INC-M06-323-G27 RF-85 FA-1/FA-2: la cosecha pendiente continúa con precio o costos manuales |
"""Adaptador de :class:`EventoM02Port`.

Entran los eventos de activos con reconocimiento CONFIRMADO y posteriores a él: los anteriores ya
están en el valor del reconocimiento. También los posteriores a la reversión de un activo que quedó
sin reconocimiento confirmado (PENDIENTE_RECONOCIMIENTO): no se miden, pero su exclusión queda
registrada (RF-83). Un evento ENCOLADO_CIERRE (su período estaba en cierre) se vuelve a tomar en cada
pasada; uno con ERROR, hasta 3 intentos. Una cosecha pendiente (MEDICION_PENDIENTE de un evento
productivo, RF-85 FA-1/FA-2) se vuelve a tomar cuando, después de su último procesamiento, se registra
un precio o un parámetro de costos de venta de la especie."""
from __future__ import annotations

from sqlalchemy.orm import Session

from src.financial_valuation.domain.repositories.evento_m02_port import EventoM02, EventoM02Port
from src.financial_valuation.infrastructure.repositories.sql import escribir, fila, filas

_SELECT = """
SELECT ea.id_eventos AS id_evento, ea.id_activo_biologico, ea.fecha,
       CASE WHEN eb.id_evento IS NOT NULL THEN 'BAJA'
            WHEN ep.id_evento IS NOT NULL THEN 'PRODUCTIVO'
            WHEN ei.id_evento IS NOT NULL THEN 'INGRESO'
            WHEN ec.id_evento IS NOT NULL THEN 'CRECIMIENTO'
            WHEN er.id_evento_reproductivo IS NOT NULL THEN 'REPRODUCTIVO'
            WHEN es.id_evento IS NOT NULL THEN 'SANITARIO'
            ELSE 'OTRO' END AS tipo,
       upper(ec.tipo_medicion) AS tipo_medicion, eb.tipo::text AS tipo_baja, eb.cantidad_afectada,
       ep.cantidad AS cantidad_producida, ep.id_metrica_produccion, ei.tipo::text AS tipo_ingreso,
       ei.cantidad_ingresada, coalesce(pr.resultado = 'ENCOLADO_CIERRE', false) AS encolado_en_cierre,
       ri.id_reconocimiento_inicial IS NULL AS sin_reconocimiento
FROM modulo2.eventos_activos ea
LEFT JOIN modulo6.reconocimientos_iniciales ri
  ON ri.id_activo_biologico = ea.id_activo_biologico AND ri.estado = 'CONFIRMADO'
LEFT JOIN LATERAL (
  SELECT max(r.fecha_reversion) AS fecha_reversion FROM modulo6.reconocimientos_iniciales r
  WHERE r.id_activo_biologico = ea.id_activo_biologico AND r.estado = 'REVERTIDO'
) rv ON ri.id_reconocimiento_inicial IS NULL
LEFT JOIN modulo6.procesamientos_eventos_m02 pr ON pr.id_evento = ea.id_eventos
LEFT JOIN modulo2.eventos_bajas eb ON eb.id_evento = ea.id_eventos
LEFT JOIN modulo2.eventos_productivos ep ON ep.id_evento = ea.id_eventos
LEFT JOIN modulo2.eventos_ingresos ei ON ei.id_evento = ea.id_eventos
LEFT JOIN modulo2.eventos_crecimeinto ec ON ec.id_evento = ea.id_eventos
LEFT JOIN modulo2.eventos_reproductivos er ON er.id_evento_reproductivo = ea.id_eventos
LEFT JOIN modulo2.eventos_sanitarios es ON es.id_evento = ea.id_eventos
"""

# Posterior al reconocimiento CONFIRMADO o, si el activo quedó sin él, a su reversión (RF-83).
_ELEGIBLE = "(ea.fecha >= ri.fecha_creacion OR (ri.id_reconocimiento_inicial IS NULL AND ea.fecha >= rv.fecha_reversion))"

# RF-85 FA-1/FA-2: lo que faltaba (precio o costos de venta de la especie) cambió después del último intento.
_COSECHA_REANUDABLE = """(pr.resultado = 'MEDICION_PENDIENTE' AND ep.id_evento IS NOT NULL AND EXISTS (
    SELECT 1 FROM modulo2.activos_biologicos ab WHERE ab.id_activo_biologico = ea.id_activo_biologico AND (
        EXISTS (SELECT 1 FROM modulo6.precios_mercado pm
                WHERE pm.id_especie = ab.id_especie AND pm.fecha_registro > pr.fecha_procesamiento)
        OR EXISTS (SELECT 1 FROM modulo6.parametros_costos_venta pc
                   WHERE pc.id_especie = ab.id_especie AND pc.fecha_creacion > pr.fecha_procesamiento))))"""

_PENDIENTES = _SELECT + f"""
WHERE {_ELEGIBLE}
  AND (pr.id_evento IS NULL OR pr.resultado = 'ENCOLADO_CIERRE' OR (pr.resultado = 'ERROR' AND pr.intentos < 3)
       OR {_COSECHA_REANUDABLE})
ORDER BY ea.fecha, ea.id_eventos
LIMIT :limite
"""

# Bandeja de cosechas pendientes (RF-85 FA-1/FA-2) con lo que el Contador necesita para resolverlas.
_COSECHAS_PENDIENTES = """
SELECT ea.id_eventos AS id_evento, ea.id_activo_biologico, a.identificador, e.nombre AS especie, f.nombre AS finca,
       ri.clasificacion::text AS clasificacion, mp.nombre AS producto_agricola, mp.unidad_medida,
       ep.cantidad AS cantidad_cosechada, ea.fecha AS fecha_cosecha, pr.detalle AS motivo,
       pr.fecha_procesamiento AS fecha_ultimo_intento, pr.intentos
FROM modulo6.procesamientos_eventos_m02 pr
JOIN modulo2.eventos_activos ea ON ea.id_eventos = pr.id_evento
JOIN modulo2.eventos_productivos ep ON ep.id_evento = ea.id_eventos
JOIN modulo2.activos_biologicos a ON a.id_activo_biologico = ea.id_activo_biologico
JOIN modulo9.especies e ON e.id_especie = a.id_especie
JOIN modulo9.infraestructuras i ON i.id_infraestructura = a.id_infraestructura
JOIN modulo9.fincas f ON f.id_finca = i.id_finca
JOIN modulo6.reconocimientos_iniciales ri ON ri.id_activo_biologico = a.id_activo_biologico AND ri.estado = 'CONFIRMADO'
LEFT JOIN modulo9.metricas_produccion mp ON mp.id_metrica_produccion = ep.id_metrica_produccion
WHERE pr.resultado = 'MEDICION_PENDIENTE'
ORDER BY ea.fecha DESC, ea.id_eventos DESC
"""

_COSECHA_PENDIENTE = _SELECT + """
WHERE ea.id_eventos = :id AND ep.id_evento IS NOT NULL AND pr.resultado = 'MEDICION_PENDIENTE'
  AND ea.fecha >= ri.fecha_creacion
"""


def _evento(f: dict) -> EventoM02:
    datos = {k: f[k] for k in ("tipo_medicion", "tipo_baja", "cantidad_afectada", "cantidad_producida",
                               "id_metrica_produccion", "tipo_ingreso", "cantidad_ingresada")}
    return EventoM02(f["id_evento"], f["id_activo_biologico"], f["fecha"], f["tipo"], datos,
                     encolado_en_cierre=f["encolado_en_cierre"], sin_reconocimiento=f["sin_reconocimiento"])


class EventoM02Adapter(EventoM02Port):
    def __init__(self, db: Session) -> None:
        self.db = db

    def pendientes(self, limite: int) -> list[EventoM02]:
        return [_evento(f) for f in filas(self.db, _PENDIENTES, {"limite": limite})]

    def cosechas_pendientes(self) -> list[dict]:
        return [{**f, "admite_costos_manuales": f["clasificacion"] != "CONSUMO"}
                for f in filas(self.db, _COSECHAS_PENDIENTES)]

    def cosecha_pendiente(self, id_evento: int) -> EventoM02 | None:
        f = fila(self.db, _COSECHA_PENDIENTE, {"id": id_evento})
        return _evento(f) if f else None

    def registrar_procesamiento(self, id_evento: int, resultado: str, detalle: str | None) -> None:
        escribir(self.db, """
            INSERT INTO modulo6.procesamientos_eventos_m02 (id_evento, resultado, detalle)
            VALUES (:id, :resultado, :detalle)
            ON CONFLICT (id_evento) DO UPDATE SET resultado = EXCLUDED.resultado, detalle = EXCLUDED.detalle,
                intentos = modulo6.procesamientos_eventos_m02.intentos + 1, fecha_procesamiento = now()
        """, {"id": id_evento, "resultado": resultado, "detalle": (detalle or "")[:2000] or None})

    def pendientes_del_titular(self, numero_id_tributaria: str) -> int:
        f = fila(self.db, f"""
            SELECT count(*) AS n FROM ({_PENDIENTES.replace('LIMIT :limite', '')}) p
            JOIN modulo2.activos_biologicos a ON a.id_activo_biologico = p.id_activo_biologico
            JOIN modulo9.infraestructuras i ON i.id_infraestructura = a.id_infraestructura
            JOIN modulo9.fincas f ON f.id_finca = i.id_finca
            WHERE f.numero_id_tributaria = :nit
        """, {"nit": numero_id_tributaria})
        return f["n"] if f else 0
