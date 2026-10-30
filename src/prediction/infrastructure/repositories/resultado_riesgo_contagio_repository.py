# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-26 | Arekkazu | INC-M04-196-G026 RF-68: modelo de estimación de riesgo de contagio |
# | 2026-10-30 | Leandro | INC-M04-217-G026 RF-68: conservar umbrales aplicados en el snapshot histórico y su lectura. |
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.prediction.domain.entities.riesgo_contagio import ResultadoRiesgoContagio
from src.prediction.domain.repositories.resultado_riesgo_contagio_repository import (
    ResultadoRiesgoContagioRepository,
)
from src.prediction.infrastructure.models.resultado_riesgo_contagio_model import ResultadoRiesgoContagioModel
from src.shared.db_error_translator import raise_from_db_error


def _snapshot(r: ResultadoRiesgoContagio) -> dict:
    """Lo que la tabla no tiene como columna (RFC-009 y trazabilidad del cálculo)."""
    return {
        **r.variables_ambientales,
        "definicion_fs": r.definicion_fs,
        "motivos_degradacion": r.motivos_degradacion,
        "densidad_asumida": r.densidad_asumida,
        "id_area_productiva": r.id_area_productiva,
        "config_version": r.config_version,
        "umbrales_aplicados": {k: str(v) for k, v in r.umbrales_aplicados.items()},
        "huella_entradas": r.huella_entradas,
        "id_alerta_rf57": r.alerta_id,
    }


class SqlAlchemyResultadoRiesgoContagioRepository(ResultadoRiesgoContagioRepository):

    def __init__(self, db: Session) -> None:
        self.db = db

    def guardar(self, resultado: ResultadoRiesgoContagio) -> ResultadoRiesgoContagio:
        try:
            orm = ResultadoRiesgoContagioModel(
                id_activo_biologico=resultado.id_lote,
                id_configuracion_motor=resultado.id_configuracion_motor,
                # NOT NULL en la tabla: sin Fs se guarda 0 y "fs" queda en factores_ausentes.
                factor_sanitario_fs=resultado.factor_sanitario if resultado.factor_sanitario is not None else Decimal("0"),
                factor_ambiental_fa=resultado.factor_ambiental,
                factor_densidad_fd=resultado.factor_densidad,
                w_fs_aplicado=resultado.pesos_aplicados["fs"],
                w_fa_aplicado=resultado.pesos_aplicados["fa"],
                w_fd_aplicado=resultado.pesos_aplicados["fd"],
                probabilidad_contagio=resultado.probabilidad_contagio,
                nivel_riesgo_contagio=resultado.nivel_riesgo_contagio,
                confianza_baja=resultado.confianza_baja,
                data_quality_score=resultado.data_quality_score,
                factores_ausentes=resultado.factores_ausentes,
                modo_ejecucion_calculo=resultado.modo_ejecucion,
                n_enfermos_detectados=resultado.n_enfermos_detectados,
                total_activos_lote=resultado.total_activos_lote,
                porcentaje_sensores_activos=resultado.porcentaje_sensores_activos,
                variables_ambientales_snap=_snapshot(resultado),
                fecha_calculo=resultado.fecha_calculo,
            )
            self.db.add(orm)
            self.db.flush()
            resultado.id_resultado_contagio = orm.id_resultado_contagio
            return resultado
        except Exception as exc:
            raise_from_db_error(exc)

    def ultimos_por_lote(self, id_lote: int, cantidad: int) -> list[ResultadoRiesgoContagio]:
        filas = self.db.execute(
            select(ResultadoRiesgoContagioModel)
            .where(ResultadoRiesgoContagioModel.id_activo_biologico == id_lote)
            .order_by(ResultadoRiesgoContagioModel.fecha_calculo.desc(),
                      ResultadoRiesgoContagioModel.id_resultado_contagio.desc())
            .limit(cantidad)
        ).scalars().all()
        return [self._a_entidad(f) for f in filas]

    def asociar_alerta(self, id_resultado: int, id_alerta: int) -> None:
        orm = self.db.get(ResultadoRiesgoContagioModel, id_resultado)
        orm.variables_ambientales_snap = {**(orm.variables_ambientales_snap or {}), "id_alerta_rf57": id_alerta}
        self.db.flush()

    @staticmethod
    def _a_entidad(orm: ResultadoRiesgoContagioModel) -> ResultadoRiesgoContagio:
        snap = dict(orm.variables_ambientales_snap or {})
        ausentes = list(orm.factores_ausentes or [])
        propias = {"definicion_fs", "motivos_degradacion", "densidad_asumida", "id_area_productiva",
                   "config_version", "huella_entradas", "id_alerta_rf57", "umbrales_aplicados"}
        return ResultadoRiesgoContagio(
            id_lote=orm.id_activo_biologico,
            probabilidad_contagio=orm.probabilidad_contagio,
            nivel_riesgo_contagio=orm.nivel_riesgo_contagio,
            confianza_baja=orm.confianza_baja,
            data_quality_score=orm.data_quality_score,
            factor_sanitario=None if "fs" in ausentes else orm.factor_sanitario_fs,
            factor_ambiental=orm.factor_ambiental_fa,
            factor_densidad=orm.factor_densidad_fd,
            pesos_aplicados={"fs": orm.w_fs_aplicado, "fa": orm.w_fa_aplicado, "fd": orm.w_fd_aplicado},
            factores_ausentes=ausentes,
            motivos_degradacion=list(snap.get("motivos_degradacion") or []),
            definicion_fs=snap.get("definicion_fs"),
            n_enfermos_detectados=orm.n_enfermos_detectados,
            total_activos_lote=orm.total_activos_lote,
            porcentaje_sensores_activos=orm.porcentaje_sensores_activos,
            densidad_asumida=bool(snap.get("densidad_asumida")),
            fecha_calculo=orm.fecha_calculo,
            id_resultado_contagio=orm.id_resultado_contagio,
            id_configuracion_motor=orm.id_configuracion_motor,
            config_version=snap.get("config_version"),
            id_area_productiva=snap.get("id_area_productiva"),
            alerta_id=snap.get("id_alerta_rf57"),
            huella_entradas=snap.get("huella_entradas") or "",
            variables_ambientales={k: v for k, v in snap.items() if k not in propias},
            umbrales_aplicados={k: Decimal(v) for k, v in (snap.get("umbrales_aplicados") or {}).items()},
        )
