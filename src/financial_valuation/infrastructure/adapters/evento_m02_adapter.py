# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-04 | Arekkazu | M06 RF-83/85/87: cola de eventos de M02 para la medición por evento |
"""Adaptador de :class:`EventoM02Port`.

Solo entran los eventos de activos con reconocimiento CONFIRMADO y posteriores a él: los
anteriores ya están en el valor del reconocimiento. Un evento ENCOLADO_CIERRE (su período estaba
en cierre) se vuelve a tomar en cada pasada; uno con ERROR, hasta 3 intentos."""
from __future__ import annotations

from sqlalchemy.orm import Session

from src.financial_valuation.domain.repositories.evento_m02_port import EventoM02, EventoM02Port
from src.financial_valuation.infrastructure.repositories.sql import escribir, fila, filas

_PENDIENTES = """
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
       ei.cantidad_ingresada
FROM modulo2.eventos_activos ea
JOIN modulo6.reconocimientos_iniciales ri
  ON ri.id_activo_biologico = ea.id_activo_biologico AND ri.estado = 'CONFIRMADO' AND ea.fecha >= ri.fecha_creacion
LEFT JOIN modulo6.procesamientos_eventos_m02 pr ON pr.id_evento = ea.id_eventos
LEFT JOIN modulo2.eventos_bajas eb ON eb.id_evento = ea.id_eventos
LEFT JOIN modulo2.eventos_productivos ep ON ep.id_evento = ea.id_eventos
LEFT JOIN modulo2.eventos_ingresos ei ON ei.id_evento = ea.id_eventos
LEFT JOIN modulo2.eventos_crecimeinto ec ON ec.id_evento = ea.id_eventos
LEFT JOIN modulo2.eventos_reproductivos er ON er.id_evento_reproductivo = ea.id_eventos
LEFT JOIN modulo2.eventos_sanitarios es ON es.id_evento = ea.id_eventos
WHERE pr.id_evento IS NULL OR pr.resultado = 'ENCOLADO_CIERRE' OR (pr.resultado = 'ERROR' AND pr.intentos < 3)
ORDER BY ea.fecha, ea.id_eventos
LIMIT :limite
"""


class EventoM02Adapter(EventoM02Port):
    def __init__(self, db: Session) -> None:
        self.db = db

    def pendientes(self, limite: int) -> list[EventoM02]:
        eventos = []
        for f in filas(self.db, _PENDIENTES, {"limite": limite}):
            datos = {k: f[k] for k in ("tipo_medicion", "tipo_baja", "cantidad_afectada", "cantidad_producida",
                                       "id_metrica_produccion", "tipo_ingreso", "cantidad_ingresada")}
            eventos.append(EventoM02(f["id_evento"], f["id_activo_biologico"], f["fecha"], f["tipo"], datos))
        return eventos

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
