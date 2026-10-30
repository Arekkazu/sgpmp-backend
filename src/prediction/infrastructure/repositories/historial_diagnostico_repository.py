# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-25 | Arekkazu | INC-M04-143/144/146 RF-67: eventos ordenados, id estable y nombre histórico |
# | 2026-10-25 | Arekkazu | INC-M04-146-G012 RF-67: MD5 del id de alerta marcado como no criptográfico (Bandit B324) |
# | 2026-10-30 | Arekkazu | INC-M04-223-G034 RF-68/RF-67: cálculos de contagio del lote en el historial |
# | 2026-10-30 | Arekkazu | INC-M04-223-G034 RF-67: id de CONTAGIO sin hash; id de alerta sin cambios (Bearer CWE-328) |
"""Historial diagnóstico (RF-67) sobre resultados de inferencia, alertas y retroalimentación.

- Orden y cursor por (fecha_evento, id_evento) DESC, sobre los tres tipos de
  evento juntos (antes cada alerta o retroalimentación quedaba pegada a su
  inferencia y la página perdía el orden, INC-M04-143-G010).
- ``id_evento`` estable: el de la inferencia, el de la retroalimentación, o un
  UUID derivado del id de la alerta. Así la misma consulta repetida o
  simultánea no materializa el evento dos veces (INC-M04-146-G012).
- ``nombre_patologia`` es el vigente a la fecha del evento según el historial
  del catálogo de M04, no el actual (INC-M04-144-G012, RF-67 CA-11).
- RF-68 paso 9: el resultado de contagio se almacena "vinculado al lote para el
  historial diagnóstico". Se lee de ``resultados_riesgo_contagio`` como evento
  CONTAGIO, sin inferencia asociada, y no se materializa: la tabla de eventos
  solo admite los tres tipos de RF-67 (INC-M04-223-G034).
"""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Text, and_, cast, func, literal, select, text, tuple_
from sqlalchemy.dialects.postgresql import UUID, insert
from sqlalchemy.orm import Session

from src.prediction.domain.entities.historial_diagnostico import EventoHistorial
from src.prediction.domain.repositories.historial_diagnostico_repository import HistorialDiagnosticoRepository
from src.prediction.infrastructure.models.alerta_patologica_model import AlertaPatologicaModel
from src.prediction.infrastructure.models.historial_diagnostico_evento_model import HistorialDiagnosticoEventoModel
from src.prediction.infrastructure.models.resultado_inferencia_model import ResultadoInferenciaModel
from src.prediction.infrastructure.models.resultado_riesgo_contagio_model import ResultadoRiesgoContagioModel
from src.prediction.infrastructure.models.retroalimentacion_clinica_model import RetroalimentacionClinicaModel
from src.shared.db_error_translator import raise_from_db_error


# Tipos de evento del historial (no de la bitácora de auditoría RF-73).
INFERENCIA, ALERTA, RETROALIMENTACION = "INFERENCIA", "ALERTA", "RETROALIMENTACION"
CONTAGIO = "CONTAGIO"


def id_evento_alerta(id_alerta_patologica: int) -> uuid.UUID:
    """UUID estable de una alerta (su id es entero); igual al ``md5(...)::uuid`` del SQL.

    MD5 solo deriva un identificador determinista, no protege nada.
    """
    return uuid.UUID(hashlib.md5(f"ALERTA:{id_alerta_patologica}".encode(), usedforsecurity=False).hexdigest())


# Prefijo fijo + id en los 12 dígitos finales: estable, sin hash y sin choque con los
# UUID v4 de inferencias y retroalimentaciones ni con los de alertas (md5).
_PREFIJO_CONTAGIO = "c047a610-0000-0000-0000-"


def id_evento_contagio(id_resultado_contagio: int) -> uuid.UUID:
    """UUID estable de un cálculo de contagio; igual a ``_id_contagio_sql``."""
    return uuid.UUID(f"{_PREFIJO_CONTAGIO}{id_resultado_contagio:012x}")


def _id_contagio_sql(columna):
    return cast(literal(_PREFIJO_CONTAGIO) + func.lpad(func.to_hex(columna), 12, "0"), UUID)


# Nombre de la patología vigente en cada instante: el último cambio del catálogo
# hasta esa fecha; si el primer cambio registrado es posterior, el nombre que
# tenía antes de ese cambio; sin historial (base o anterior a M04), el actual.
_NOMBRES_A_LA_FECHA = text("""
    SELECT x.id_patologia, x.fecha, COALESCE(
        (SELECT h.datos_nuevos ->> 'nombre' FROM modulo4.historial_catalogo_patologias h
          WHERE h.id_patologia = x.id_patologia AND h.timestamp_cambio <= x.fecha
          ORDER BY h.timestamp_cambio DESC, h.id_historial_catalogo DESC LIMIT 1),
        (SELECT h.datos_anteriores ->> 'nombre' FROM modulo4.historial_catalogo_patologias h
          WHERE h.id_patologia = x.id_patologia AND h.timestamp_cambio > x.fecha
            AND h.datos_anteriores IS NOT NULL
          ORDER BY h.timestamp_cambio, h.id_historial_catalogo LIMIT 1),
        p.nombre) AS nombre
    FROM unnest(CAST(:ids AS integer[]), CAST(:fechas AS timestamptz[])) AS x(id_patologia, fecha)
    JOIN modulo9.patologias p ON p.id_patologia = x.id_patologia
""")


def _flotante(valor) -> Optional[float]:
    return None if valor is None else float(valor)


class SqlAlchemyHistorialDiagnosticoRepository(HistorialDiagnosticoRepository):
    def __init__(self, db: Session) -> None:
        self._db = db

    def consultar(
        self,
        *,
        id_activo_biologico: int,
        fecha_inicio: datetime,
        fecha_fin: datetime,
        nivel_riesgo: Optional[int],
        id_patologia: Optional[int],
        incluir_alertas: bool,
        cursor: Optional[tuple[datetime, uuid.UUID]],
        limite: int,
    ) -> list[EventoHistorial]:
        ri = ResultadoInferenciaModel
        rc = RetroalimentacionClinicaModel
        ap = AlertaPatologicaModel
        rrc = ResultadoRiesgoContagioModel

        # Los filtros son de la inferencia; alertas y retroalimentaciones la siguen.
        de_la_inferencia = and_(
            ri.id_activo_biologico == id_activo_biologico,
            ri.fecha_inferencia >= fecha_inicio,
            ri.fecha_inferencia <= fecha_fin,
            *([] if nivel_riesgo is None else [ri.nivel_riesgo == nivel_riesgo]),
            *([] if id_patologia is None else [ri.id_patologia == id_patologia]),
        )

        def pagina(stmt, fecha, id_evento):
            if cursor is not None:
                stmt = stmt.where(tuple_(fecha, id_evento) < tuple_(literal(cursor[0]), literal(cursor[1], UUID)))
            return self._db.execute(stmt.order_by(fecha.desc(), id_evento.desc()).limit(limite)).all()

        inferencias = pagina(select(ri).where(de_la_inferencia), ri.fecha_inferencia, ri.id_resultado_inferencia)
        retros = pagina(
            select(rc, ri.id_activo_biologico)
            .join(ri, ri.id_resultado_inferencia == rc.id_resultado_inferencia)
            .where(de_la_inferencia, rc.estado_registro == "ACTIVO"),
            rc.fecha_retroalimentacion, rc.id_retroalimentacion,
        )
        alertas = []
        if incluir_alertas:
            id_alerta = cast(func.md5(literal("ALERTA:") + cast(ap.id_alerta_patologica, Text)), UUID)
            alertas = pagina(
                select(ap, ri.id_resultado_inferencia, ri.id_activo_biologico)
                .join(ri, ri.id_alerta_generada == ap.id_alerta_patologica)
                .where(de_la_inferencia),
                ap.fecha_generacion, id_alerta,
            )

        # El cálculo de contagio no tiene patología: con ese filtro no aplica.
        contagios = []
        if id_patologia is None:
            contagios = pagina(
                select(rrc).where(
                    rrc.id_activo_biologico == id_activo_biologico,
                    rrc.fecha_calculo >= fecha_inicio,
                    rrc.fecha_calculo <= fecha_fin,
                    *([] if nivel_riesgo is None else [rrc.nivel_riesgo_contagio == nivel_riesgo]),
                ),
                rrc.fecha_calculo, _id_contagio_sql(rrc.id_resultado_contagio),
            )

        nombres = self._nombres_a_la_fecha(
            [(r.id_patologia, r.fecha_inferencia) for (r,) in inferencias if r.id_patologia is not None]
            + [(a.id_patologia, a.fecha_generacion) for (a, *_) in alertas if a.id_patologia is not None]
        )

        eventos = [
            EventoHistorial(
                id_evento=r.id_resultado_inferencia,
                tipo_evento=INFERENCIA,
                id_activo_biologico=r.id_activo_biologico,
                fecha_evento=r.fecha_inferencia,
                id_resultado_inferencia=r.id_resultado_inferencia,
                payload={
                    "nivel_riesgo": r.nivel_riesgo,
                    "id_patologia": r.id_patologia,
                    "nombre_patologia": nombres.get((r.id_patologia, r.fecha_inferencia)),
                    "probabilidad_riesgo": r.probabilidad_riesgo,
                    "probabilidad_enfermedad": r.probabilidad_enfermedad,
                    "confianza_global": float(r.confianza_global),
                    "tipo_modelo": r.tipo_modelo,
                    "id_version_modelo": r.id_version_modelo,
                    "modo_ejecucion": r.modo_ejecucion,
                    "contexto_incompleto": r.contexto_incompleto,
                    "latencia_excedida": r.latencia_excedida,
                    "latencia_ms": r.latencia_ms,
                    "fecha_inicio_ventana": r.fecha_inicio_ventana.isoformat() if r.fecha_inicio_ventana else None,
                    "fecha_fin_ventana": r.fecha_fin_ventana.isoformat() if r.fecha_fin_ventana else None,
                    "tiene_alerta_generada": r.tiene_alerta_generada,
                    "id_alerta_generada": r.id_alerta_generada,
                },
            )
            for (r,) in inferencias
        ] + [
            EventoHistorial(
                id_evento=id_evento_alerta(a.id_alerta_patologica),
                tipo_evento=ALERTA,
                id_activo_biologico=id_activo,
                fecha_evento=a.fecha_generacion,
                id_resultado_inferencia=id_resultado,
                payload={
                    "id_alerta_patologica": a.id_alerta_patologica,
                    "id_patologia": a.id_patologia,
                    "nombre_patologia": nombres.get((a.id_patologia, a.fecha_generacion)),
                    "probabilidad_pct": float(a.probabilidad_pct),
                    "nivel_criticidad": a.nivel_criticidad,
                    "estado_alerta": a.estado_alerta,
                },
            )
            for a, id_resultado, id_activo in alertas
        ] + [
            EventoHistorial(
                id_evento=retro.id_retroalimentacion,
                tipo_evento=RETROALIMENTACION,
                id_activo_biologico=id_activo,
                fecha_evento=retro.fecha_retroalimentacion,
                id_resultado_inferencia=retro.id_resultado_inferencia,
                payload={
                    "id_retroalimentacion": str(retro.id_retroalimentacion),
                    "estado_retroalimentacion": retro.estado_retroalimentacion,
                    "diagnosticos_reales": retro.diagnosticos_reales,
                    "observaciones_clinicas": retro.observaciones_clinicas,
                    "id_usuario_veterinario": retro.id_usuario_veterinario,
                    "es_conflicto_retroalimentacion": retro.es_conflicto_retroalimentacion,
                },
            )
            for retro, id_activo in retros
        ] + [
            EventoHistorial(
                id_evento=id_evento_contagio(c.id_resultado_contagio),
                tipo_evento=CONTAGIO,
                id_activo_biologico=c.id_activo_biologico,
                fecha_evento=c.fecha_calculo,
                id_resultado_inferencia=None,
                payload={
                    "id_resultado_contagio": c.id_resultado_contagio,
                    "probabilidad_contagio": float(c.probabilidad_contagio),
                    "nivel_riesgo_contagio": c.nivel_riesgo_contagio,
                    "factor_sanitario_fs": float(c.factor_sanitario_fs),
                    "factor_ambiental_fa": _flotante(c.factor_ambiental_fa),
                    "factor_densidad_fd": _flotante(c.factor_densidad_fd),
                    "w_fs_aplicado": float(c.w_fs_aplicado),
                    "w_fa_aplicado": float(c.w_fa_aplicado),
                    "w_fd_aplicado": float(c.w_fd_aplicado),
                    "confianza_baja": c.confianza_baja,
                    "data_quality_score": _flotante(c.data_quality_score),
                    "factores_ausentes": c.factores_ausentes,
                    "n_enfermos_detectados": c.n_enfermos_detectados,
                    "total_activos_lote": c.total_activos_lote,
                    "id_alerta_generada": c.id_alerta_generada,
                },
            )
            for (c,) in contagios
        ]
        eventos.sort(key=lambda e: (e.fecha_evento, e.id_evento), reverse=True)
        return eventos[:limite]

    def _nombres_a_la_fecha(self, pares: list[tuple[int, datetime]]) -> dict[tuple[int, datetime], str]:
        if not pares:
            return {}
        ids, fechas = zip(*set(pares))
        filas = self._db.execute(_NOMBRES_A_LA_FECHA, {"ids": list(ids), "fechas": list(fechas)}).all()
        return {(f.id_patologia, f.fecha): f.nombre for f in filas}

    def materializar_eventos(self, eventos: list[EventoHistorial]) -> None:
        hde = HistorialDiagnosticoEventoModel
        try:
            for evento in eventos:
                if evento.tipo_evento == CONTAGIO:
                    continue  # ya persiste en resultados_riesgo_contagio (RF-68)
                # Filas de antes de que id_evento fuera estable (tenían un id aleatorio).
                ya_existe = self._db.execute(select(select(hde.id_evento).where(
                    hde.id_resultado_inferencia == evento.id_resultado_inferencia,
                    hde.tipo_evento == evento.tipo_evento,
                    hde.fecha_evento == evento.fecha_evento,
                ).exists())).scalar()
                if ya_existe:
                    continue
                # Dos consultas simultáneas insertan el mismo id_evento: gana una.
                self._db.execute(insert(hde).values(
                    id_evento=evento.id_evento,
                    tipo_evento=evento.tipo_evento,
                    id_activo_biologico=evento.id_activo_biologico,
                    fecha_evento=evento.fecha_evento,
                    id_resultado_inferencia=evento.id_resultado_inferencia,
                    payload=evento.payload,
                ).on_conflict_do_nothing(index_elements=[hde.id_evento]))
        except Exception as exc:
            raise_from_db_error(exc)
