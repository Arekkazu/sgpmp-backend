from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import and_, exists, select, text
from sqlalchemy.orm import Session

from src.prediction.domain.entities.historial_diagnostico import EventoHistorial
from src.prediction.domain.repositories.historial_diagnostico_repository import HistorialDiagnosticoRepository
from src.prediction.infrastructure.models.alerta_patologica_model import AlertaPatologicaModel
from src.prediction.infrastructure.models.historial_diagnostico_evento_model import HistorialDiagnosticoEventoModel
from src.prediction.infrastructure.models.resultado_inferencia_model import ResultadoInferenciaModel
from src.prediction.infrastructure.models.retroalimentacion_clinica_model import RetroalimentacionClinicaModel
from src.shared.db_error_translator import raise_from_db_error


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
        cursor: Optional[tuple[datetime, str]],
        limite: int,
    ) -> list[dict]:
        ri = ResultadoInferenciaModel
        rc = RetroalimentacionClinicaModel
        ap = AlertaPatologicaModel

        stmt = select(ri).filter(
            and_(
                ri.id_activo_biologico == id_activo_biologico,
                ri.fecha_inferencia >= fecha_inicio,
                ri.fecha_inferencia <= fecha_fin,
                *([] if nivel_riesgo is None else [ri.nivel_riesgo == nivel_riesgo]),
                *([] if id_patologia is None else [ri.id_patologia == id_patologia]),
            )
        )

        if cursor is not None:
            cursor_fecha, cursor_id = cursor
            stmt = stmt.filter(
                text(
                    "(resultados_inferencia.fecha_inferencia, resultados_inferencia.id_resultado_inferencia) < (:cf, :ci::uuid)"
                ).bindparams(cf=cursor_fecha, ci=cursor_id)
            )

        stmt = stmt.order_by(ri.fecha_inferencia.desc(), ri.id_resultado_inferencia.desc())
        stmt = stmt.limit(limite)

        rows_ri = self._db.execute(stmt).scalars().all()

        ids_resultado = [r.id_resultado_inferencia for r in rows_ri]

        retros_por_resultado: dict[uuid.UUID, list[RetroalimentacionClinicaModel]] = {}
        if ids_resultado:
            retros = self._db.execute(
                select(rc).where(
                    and_(
                        rc.id_resultado_inferencia.in_(ids_resultado),
                        rc.estado_registro == "ACTIVO",
                    )
                )
            ).scalars().all()
            for retro in retros:
                retros_por_resultado.setdefault(retro.id_resultado_inferencia, []).append(retro)

        alertas_por_inferencia: dict[uuid.UUID, AlertaPatologicaModel] = {}
        if incluir_alertas and ids_resultado:
            ids_alerta = [r.id_alerta_generada for r in rows_ri if r.id_alerta_generada is not None]
            if ids_alerta:
                alertas = self._db.execute(
                    select(ap).where(ap.id_alerta_patologica.in_(ids_alerta))
                ).scalars().all()
                id_alerta_a_resultado = {r.id_alerta_generada: r.id_resultado_inferencia for r in rows_ri if r.id_alerta_generada}
                for alerta in alertas:
                    id_ri = id_alerta_a_resultado.get(alerta.id_alerta_patologica)
                    if id_ri:
                        alertas_por_inferencia[id_ri] = alerta

        nombres_patologia: dict[int, str] = {}
        if ids_resultado:
            ids_pat = list({r.id_patologia for r in rows_ri if r.id_patologia is not None})
            if ids_pat:
                filas = self._db.execute(
                    text("SELECT id_patologia, nombre FROM modulo9.patologias WHERE id_patologia = ANY(:ids)").bindparams(ids=ids_pat)
                ).all()
                nombres_patologia = {fila.id_patologia: fila.nombre for fila in filas}

        resultados: list[dict] = []
        for ri_row in rows_ri:
            nombre_pat = nombres_patologia.get(ri_row.id_patologia) if ri_row.id_patologia else None

            payload_inferencia: dict = {
                "nivel_riesgo": ri_row.nivel_riesgo,
                "id_patologia": ri_row.id_patologia,
                "nombre_patologia": nombre_pat,
                "probabilidad_riesgo": ri_row.probabilidad_riesgo,
                "probabilidad_enfermedad": ri_row.probabilidad_enfermedad,
                "confianza_global": float(ri_row.confianza_global),
                "tipo_modelo": ri_row.tipo_modelo,
                "id_version_modelo": ri_row.id_version_modelo,
                "modo_ejecucion": ri_row.modo_ejecucion,
                "contexto_incompleto": ri_row.contexto_incompleto,
                "latencia_excedida": ri_row.latencia_excedida,
                "latencia_ms": ri_row.latencia_ms,
                "fecha_inicio_ventana": ri_row.fecha_inicio_ventana.isoformat() if ri_row.fecha_inicio_ventana else None,
                "fecha_fin_ventana": ri_row.fecha_fin_ventana.isoformat() if ri_row.fecha_fin_ventana else None,
                "tiene_alerta_generada": ri_row.tiene_alerta_generada,
                "id_alerta_generada": ri_row.id_alerta_generada,
            }

            resultados.append({
                "tipo_evento": "INFERENCIA",
                "id_activo_biologico": ri_row.id_activo_biologico,
                "fecha_evento": ri_row.fecha_inferencia,
                "id_resultado_inferencia": ri_row.id_resultado_inferencia,
                "payload": payload_inferencia,
            })

            if incluir_alertas and ri_row.id_resultado_inferencia in alertas_por_inferencia:
                alerta = alertas_por_inferencia[ri_row.id_resultado_inferencia]
                resultados.append({
                    "tipo_evento": "ALERTA",
                    "id_activo_biologico": ri_row.id_activo_biologico,
                    "fecha_evento": alerta.fecha_generacion,
                    "id_resultado_inferencia": ri_row.id_resultado_inferencia,
                    "payload": {
                        "id_alerta_patologica": alerta.id_alerta_patologica,
                        "id_patologia": alerta.id_patologia,
                        "nombre_patologia": nombres_patologia.get(alerta.id_patologia),
                        "probabilidad_pct": float(alerta.probabilidad_pct),
                        "nivel_criticidad": alerta.nivel_criticidad,
                        "estado_alerta": alerta.estado_alerta,
                    },
                })

            for retro in retros_por_resultado.get(ri_row.id_resultado_inferencia, []):
                resultados.append({
                    "tipo_evento": "RETROALIMENTACION",
                    "id_activo_biologico": ri_row.id_activo_biologico,
                    "fecha_evento": retro.fecha_retroalimentacion,
                    "id_resultado_inferencia": ri_row.id_resultado_inferencia,
                    "payload": {
                        "id_retroalimentacion": str(retro.id_retroalimentacion),
                        "estado_retroalimentacion": retro.estado_retroalimentacion,
                        "diagnosticos_reales": retro.diagnosticos_reales,
                        "observaciones_clinicas": retro.observaciones_clinicas,
                        "id_usuario_veterinario": retro.id_usuario_veterinario,
                        "es_conflicto_retroalimentacion": retro.es_conflicto_retroalimentacion,
                    },
                })

        return resultados

    def materializar_eventos(self, eventos: list[EventoHistorial]) -> None:
        try:
            for evento in eventos:
                ya_existe = self._db.execute(
                    select(
                        exists().where(
                            and_(
                                HistorialDiagnosticoEventoModel.id_resultado_inferencia == evento.id_resultado_inferencia,
                                HistorialDiagnosticoEventoModel.tipo_evento == evento.tipo_evento,
                            )
                        )
                    )
                ).scalar()
                if not ya_existe:
                    self._db.add(
                        HistorialDiagnosticoEventoModel(
                            id_evento=evento.id_evento,
                            tipo_evento=evento.tipo_evento,
                            id_activo_biologico=evento.id_activo_biologico,
                            fecha_evento=evento.fecha_evento,
                            id_resultado_inferencia=evento.id_resultado_inferencia,
                            payload=evento.payload,
                        )
                    )
            self._db.flush()
        except Exception as exc:
            raise_from_db_error(exc)
