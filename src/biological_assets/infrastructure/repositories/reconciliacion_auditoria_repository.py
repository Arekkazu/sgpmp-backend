from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.biological_assets.domain.entities.activo_biologico import MarcaReconciliacion, RegistroRf46
from src.biological_assets.domain.repositories.reconciliacion_auditoria_repository import (
    ReconciliacionAuditoriaRepository,
)

_CANDADO_RECONCILIACION = 5246052  # pg_try_advisory_xact_lock: RF-52 E5 / RF-46

# Tabla -> (llave primaria, condición para que la fila aparezca en el historial RF-46).
# Refleja las fuentes de TransferenciaRepository.consultar_historial y de la vista
# vw_rf46_historial_completo_activo. Los nombres vienen de este dict, nunca del
# cliente, así que se pueden interpolar en el SQL.
_FUENTES_RF46: dict[str, tuple[str, str]] = {
    'eventos_activos': (
        'id_eventos',
        'EXISTS (SELECT 1 FROM modulo2.eventos_sanitarios x WHERE x.id_evento = t.id_eventos)'
        ' OR EXISTS (SELECT 1 FROM modulo2.eventos_crecimeinto x WHERE x.id_evento = t.id_eventos)'
        ' OR EXISTS (SELECT 1 FROM modulo2.eventos_productivos x WHERE x.id_evento = t.id_eventos)'
        ' OR EXISTS (SELECT 1 FROM modulo2.eventos_reproductivos x WHERE x.id_evento_reproductivo = t.id_eventos)'
        ' OR EXISTS (SELECT 1 FROM modulo2.eventos_bajas x WHERE x.id_evento = t.id_eventos)',
    ),
    # La vista une el estado anterior con INNER JOIN: sin anterior, no hay fila en RF-46.
    'historicos_estados_activos': ('id_historico_estado_activo', 't.id_estado_anterior IS NOT NULL'),
    'gestiones_fases': ('id_gestion_fases', 'TRUE'),
    'movimientos': ('id_movimiento', 'TRUE'),
    'historial_activos': ('id_historial_activo', "t.tipo_evento = 'CREACION'"),
}
# indicadores_zootecnicos queda fuera a propósito: RF-51 calcula on-demand y ningún
# código de M02 escribe esa tabla, así que no hay emisor que pueda haber fallado.


class SqlAlchemyReconciliacionAuditoriaRepository(ReconciliacionAuditoriaRepository):

    def __init__(self, db: Session) -> None:
        self.db = db

    def adquirir_turno(self) -> bool:
        return bool(self.db.execute(
            text('SELECT pg_try_advisory_xact_lock(:candado)'),
            {'candado': _CANDADO_RECONCILIACION},
        ).scalar_one())

    def ids_maximos(self) -> dict[str, int]:
        return {
            tabla: int(self.db.execute(text(f'SELECT COALESCE(max({pk}), 0) FROM modulo2.{tabla}')).scalar_one())
            for tabla, (pk, _) in _FUENTES_RF46.items()
        }

    def ultimas_marcas(self, limite: int) -> list[MarcaReconciliacion]:
        filas = self.db.execute(
            text(
                "SELECT timestamp_registro, detalle_tecnico->'hasta' AS hasta "
                'FROM modulo2.bitacora_auditoria_m02 '
                "WHERE rf_origen = 'RF52' AND tipo_evento = 'RECONCILIACION_RF46_RF52' "
                'ORDER BY id_bitacora DESC LIMIT :limite'
            ),
            {'limite': limite},
        ).fetchall()
        return [
            MarcaReconciliacion(registrada_en=f.timestamp_registro, hasta={k: int(v) for k, v in (f.hasta or {}).items()})
            for f in filas
        ]

    def registros_sin_bitacora(
        self,
        desde: dict[str, int],
        hasta: dict[str, int],
        bitacora_desde: datetime,
    ) -> list[RegistroRf46]:
        # Una tabla que falte en alguna marca (agregada después) no se revisa en esta
        # corrida: tomarla desde 0 marcaría como inconsistente todo su histórico.
        tablas = [t for t in _FUENTES_RF46 if t in desde and t in hasta and hasta[t] > desde[t]]
        if not tablas:
            return []

        parametros: dict = {'bitacora_desde': bitacora_desde}
        candidatos = []
        for tabla in tablas:
            pk, condicion = _FUENTES_RF46[tabla]
            parametros[f'd_{tabla}'] = desde[tabla]
            parametros[f'h_{tabla}'] = hasta[tabla]
            candidatos.append(
                f"SELECT '{tabla}' AS tabla, t.{pk} AS id, t.id_activo_biologico FROM modulo2.{tabla} t "
                f'WHERE t.{pk} > :d_{tabla} AND t.{pk} <= :h_{tabla} AND ({condicion})'
            )

        filas = self.db.execute(
            text(
                'WITH cubiertos AS ('
                "  SELECT r->>'tabla' AS tabla, (r->>'id')::int AS id "
                '  FROM modulo2.bitacora_auditoria_m02 b '
                '  CROSS JOIN LATERAL jsonb_array_elements('
                "    CASE WHEN jsonb_typeof(b.detalle_tecnico->'registros_rf46') = 'array' "
                "         THEN b.detalle_tecnico->'registros_rf46' ELSE '[]'::jsonb END"
                '  ) r '
                '  WHERE b.timestamp_registro >= :bitacora_desde'
                "    AND b.tipo_evento <> 'INCONSISTENCIA_RF46_RF52'"
                ') '
                f"SELECT c.tabla, c.id, c.id_activo_biologico FROM ({' UNION ALL '.join(candidatos)}) c "
                'WHERE NOT EXISTS (SELECT 1 FROM cubiertos k WHERE k.tabla = c.tabla AND k.id = c.id) '
                'ORDER BY c.tabla, c.id'
            ),
            parametros,
        ).fetchall()
        return [RegistroRf46(tabla=f.tabla, id=f.id, id_activo_biologico=f.id_activo_biologico) for f in filas]

    def obtener_registro(self, tabla: str, id_registro: int) -> Optional[RegistroRf46]:
        if tabla not in _FUENTES_RF46:
            return None
        pk, condicion = _FUENTES_RF46[tabla]
        fila = self.db.execute(
            text(f'SELECT t.id_activo_biologico FROM modulo2.{tabla} t WHERE t.{pk} = :id AND ({condicion})'),
            {'id': id_registro},
        ).fetchone()
        if fila is None:
            return None
        return RegistroRf46(tabla=tabla, id=id_registro, id_activo_biologico=fila.id_activo_biologico)

    def tiene_auditoria(self, tabla: str, id_registro: int) -> bool:
        return bool(self.db.execute(
            text(
                'SELECT EXISTS ('
                '  SELECT 1 FROM modulo2.bitacora_auditoria_m02 b '
                "  WHERE b.tipo_evento <> 'INCONSISTENCIA_RF46_RF52' "
                "    AND b.detalle_tecnico->'registros_rf46' @> jsonb_build_array("
                "      jsonb_build_object('tabla', CAST(:tabla AS text), 'id', CAST(:id AS integer)))"
                ')'
            ),
            {'tabla': tabla, 'id': id_registro},
        ).scalar_one())
