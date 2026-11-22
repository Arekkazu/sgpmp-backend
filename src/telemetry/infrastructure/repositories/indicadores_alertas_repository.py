# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-28 | destroyerban | INC-M03-178-G57B RF-57: indicadores del sistema de alertas en SQL agregado |
# | 2026-10-29 | Arekkazu | INC-M03-211-G98 RF-58: panel integrado de alertas activas en el dashboard |
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.telemetry.domain.entities.indicadores_alertas import (
    AlertaActivaPanel,
    FiltroIndicadoresAlertas,
    IndicadoresAlertas,
)
from src.telemetry.domain.repositories.indicadores_alertas_repository import IndicadoresAlertasRepository

# Mismo alcance que GET /iot/alertas: operativas, del área pedida y de las fincas del
# usuario por el área de la alerta o por la del activo biológico.
_ALCANCE = """
WITH alcance AS (
    SELECT a.*
    FROM modulo3.alertas a
    WHERE a.tipo_alerta::text <> 'TECNICA'
      AND (CAST(:id_infraestructura AS integer) IS NULL OR a.id_infraestructura = :id_infraestructura)
      AND (:filtro_finca = FALSE
           OR a.id_infraestructura IN (
               SELECT i.id_infraestructura FROM modulo9.infraestructuras i WHERE i.id_finca = ANY(:ids_fincas))
           OR a.id_activo_biologico IN (
               SELECT ab.id_activo_biologico
               FROM modulo2.activos_biologicos ab
               JOIN modulo9.infraestructuras i ON i.id_infraestructura = ab.id_infraestructura
               WHERE i.id_finca = ANY(:ids_fincas)))
),
cerradas AS (
    SELECT * FROM alcance
    WHERE (CAST(:fecha_desde AS timestamptz) IS NULL OR fecha_resolucion >= :fecha_desde)
      AND (CAST(:fecha_hasta AS timestamptz) IS NULL OR fecha_resolucion <= :fecha_hasta)
)
"""

_SQL_INDICADORES = text(_ALCANCE + """
SELECT
    (SELECT count(*) FROM alcance WHERE estado_alerta::text IN ('ACTIVA', 'EN_ATENCION'))  AS activas,
    (SELECT count(*) FROM alcance
      WHERE estado_alerta::text IN ('ACTIVA', 'EN_ATENCION') AND severidad::text = 'CRITICO') AS criticas,
    (SELECT count(*) FROM cerradas WHERE estado_alerta::text = 'VENCIDA' AND fecha_atencion IS NULL) AS vencidas,
    (SELECT count(*) FROM cerradas WHERE estado_alerta::text = 'RESUELTA')                    AS resueltas,
    (SELECT count(*) FROM cerradas WHERE estado_alerta::text = 'DESCARTADA')                  AS descartadas,
    (SELECT avg(extract(epoch FROM fecha_resolucion - fecha_generacion)) / 60
       FROM cerradas WHERE estado_alerta::text = 'RESUELTA')                                  AS promedio_min
""")

_SQL_POR_TIPO = text(_ALCANCE + """
SELECT tipo_alerta::text AS tipo, count(*) AS total
FROM alcance
WHERE estado_alerta::text IN ('ACTIVA', 'EN_ATENCION')
GROUP BY tipo_alerta
ORDER BY tipo_alerta
""")

_SQL_VENCIDAS = text(_ALCANCE + """
SELECT count(*) FROM cerradas WHERE estado_alerta::text = 'VENCIDA' AND fecha_atencion IS NULL
""")


# RF-58 CA-11: solo ACTIVA; CRITICO > MODERADO > LEVE y, dentro de cada una, la más reciente.
_SQL_ACTIVAS = text(_ALCANCE + """
SELECT al.id_alerta, al.tipo_alerta::text AS tipo_alerta, al.severidad::text AS severidad,
       al.tipo_variable, al.valor, al.unidad, al.fecha_generacion,
       floor(extract(epoch FROM now() - al.fecha_generacion) / 60)::int AS minutos_transcurridos,
       COALESCE(al.id_infraestructura, ab.id_infraestructura) AS id_infraestructura,
       al.id_activo_biologico, ab.identificador AS identificador_activo,
       count(*) OVER () AS total
FROM alcance al
LEFT JOIN modulo2.activos_biologicos ab ON ab.id_activo_biologico = al.id_activo_biologico
WHERE al.estado_alerta::text = 'ACTIVA'
ORDER BY CASE al.severidad::text WHEN 'CRITICO' THEN 1 WHEN 'MODERADO' THEN 2 WHEN 'LEVE' THEN 3 ELSE 4 END,
         al.fecha_generacion DESC
LIMIT :limite
""")


class SqlAlchemyIndicadoresAlertasRepository(IndicadoresAlertasRepository):

    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _parametros(filtro: FiltroIndicadoresAlertas) -> dict:
        return {
            'id_infraestructura': filtro.id_infraestructura,
            'filtro_finca': filtro.ids_fincas_permitidas is not None,
            'ids_fincas': filtro.ids_fincas_permitidas or [],
            'fecha_desde': filtro.fecha_desde,
            'fecha_hasta': filtro.fecha_hasta,
        }

    def calcular(self, filtro: FiltroIndicadoresAlertas) -> IndicadoresAlertas:
        parametros = self._parametros(filtro)
        fila = self.db.execute(_SQL_INDICADORES, parametros).mappings().one()
        por_tipo = {f['tipo']: f['total'] for f in self.db.execute(_SQL_POR_TIPO, parametros).mappings()}
        promedio = fila['promedio_min']
        return IndicadoresAlertas(
            alertas_activas_total=fila['activas'],
            alertas_criticas_activas=fila['criticas'],
            alertas_por_tipo=por_tipo,
            alertas_vencidas_sin_atencion=fila['vencidas'],
            alertas_resueltas=fila['resueltas'],
            alertas_descartadas=fila['descartadas'],
            tiempo_promedio_resolucion_min=round(float(promedio), 2) if promedio is not None else None,
            tasa_falsos_positivos=IndicadoresAlertas.tasa(fila['descartadas'], fila['resueltas']),
        )

    def contar_vencidas_sin_atencion(self, filtro: FiltroIndicadoresAlertas) -> int:
        return self.db.execute(_SQL_VENCIDAS, self._parametros(filtro)).scalar_one()

    def listar_activas(self, filtro: FiltroIndicadoresAlertas, limite: int) -> tuple[list[AlertaActivaPanel], int]:
        filas = self.db.execute(_SQL_ACTIVAS, {**self._parametros(filtro), 'limite': limite}).mappings().all()
        total = filas[0]['total'] if filas else 0
        return [AlertaActivaPanel(**{k: v for k, v in f.items() if k != 'total'}) for f in filas], total
