# | Fecha      | Nombre           | Que se hizo                                   |
# |------------|------------------|-----------------------------------------------|
# | 2026-10-22 | Arekkazu         | M05 RF-77: guarda y relee los parámetros      |
# | 2026-11-08 | Leandro | INC-M05-277-G20 RF-77: conservar promedio y causa del reporte en el snapshot JSON existente. |
# | 2026-11-10 | Arekkazu | H-M05-19 RF-77: el snapshot guarda y devuelve desglose, tendencia y registros sin costo |
"""Implementación SQLAlchemy de :class:`ReporteGastoRepository` (RF-77).

Persiste el snapshot en ``modulo5.reporte_gastos_acumulados``: encabezado y totales en sus
columnas, y lo que no tiene columna propia (promedio, desglose por categoría y por período,
tendencia, registros sin costo y nota de bajas) dentro de ``json_parametros`` bajo
``resumen_promedio`` y ``resumen``. Así, reabrir un reporte desde el historial muestra lo mismo
que se vio al generarlo (H-M05-19), sin migración. Los reportes guardados antes de esto solo
recuperan el desglose por categoría, que se rehace con las columnas de totales.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from src.shared.db_error_translator import raise_from_db_error
from src.supplies.domain.entities.reporte_gasto import (
    DesgloseCategoria,
    DesglosePeriodo,
    RegistroSinCosto,
    ReporteGasto,
    TendenciaGasto,
)
from src.supplies.domain.repositories.reporte_gasto_repository import ReporteGastoRepository
from src.supplies.infrastructure.models.reporte_gasto_acumulado_model import ReporteGastoAcumuladoModel


def _dec(v) -> Optional[Decimal]:
    return Decimal(v) if v is not None else None


def _texto(v) -> Optional[str]:
    return str(v) if v is not None else None


def _resumen(r: ReporteGasto) -> dict:
    """Lo que el reporte mostró al generarse y no tiene columna propia, en JSON."""
    t = r.tendencia
    return {
        "desglose_categorias": [
            {"categoria": d.categoria, "subtotal": str(d.subtotal), "num_registros": d.num_registros,
             "porcentaje": str(d.porcentaje)} for d in r.desglose_categorias
        ],
        "desglose_temporal": [
            {"etiqueta": d.etiqueta, "fecha_inicio": d.fecha_inicio.isoformat(), "fecha_fin": d.fecha_fin.isoformat(),
             "monto": str(d.monto)} for d in r.desglose_temporal
        ],
        "registros_sin_costo": [
            {"categoria": s.categoria, "id_origen": s.id_origen, "fecha": s.fecha.isoformat(), "descripcion": s.descripcion}
            for s in r.registros_sin_costo
        ],
        "tendencia": None if t is None else {
            "gasto_periodo_actual": _texto(t.gasto_periodo_actual), "gasto_periodo_anterior": _texto(t.gasto_periodo_anterior),
            "variacion_porcentual": _texto(t.variacion_porcentual), "estado": t.estado, "nota": t.nota,
        },
        "nota_bajas": r.nota_bajas,
        "sin_datos": r.sin_datos,
    }


def _desde_resumen(orm: ReporteGastoAcumuladoModel) -> dict:
    """Campos del reporte reconstruidos desde ``json_parametros.resumen`` (o desde las columnas, si es antiguo)."""
    resumen = (orm.json_parametros or {}).get("resumen")
    if resumen is None:
        total = orm.total_costo_directo or Decimal("0")
        categorias = [(c, v) for c, v in (("ALIMENTACION", getattr(orm, "total_costo_alimento", None)), ("MEDICACION", getattr(orm, "total_costo_medicamento", None))) if v]
        return {"desglose_categorias": [
            DesgloseCategoria(c, Decimal(v), 0, (Decimal(v) * 100 / total).quantize(Decimal("0.01")) if total else Decimal("0"))
            for c, v in categorias
        ]}
    t = resumen.get("tendencia")
    return {
        "desglose_categorias": [
            DesgloseCategoria(d["categoria"], Decimal(d["subtotal"]), int(d["num_registros"]), Decimal(d["porcentaje"]))
            for d in resumen.get("desglose_categorias", [])
        ],
        "desglose_temporal": [
            DesglosePeriodo(d["etiqueta"], date.fromisoformat(d["fecha_inicio"]), date.fromisoformat(d["fecha_fin"]), Decimal(d["monto"]))
            for d in resumen.get("desglose_temporal", [])
        ],
        "registros_sin_costo": [
            RegistroSinCosto(s["categoria"], int(s["id_origen"]), date.fromisoformat(s["fecha"]), s["descripcion"])
            for s in resumen.get("registros_sin_costo", [])
        ],
        "tendencia": None if t is None else TendenciaGasto(
            _dec(t["gasto_periodo_actual"]), _dec(t["gasto_periodo_anterior"]), _dec(t["variacion_porcentual"]), t["estado"], t.get("nota"),
        ),
        "nota_bajas": resumen.get("nota_bajas"),
        "sin_datos": bool(resumen.get("sin_datos")),
    }


class SqlAlchemyReporteGastoRepository(ReporteGastoRepository):
    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _a_entidad(orm: ReporteGastoAcumuladoModel) -> ReporteGasto:
        promedio = (orm.json_parametros or {}).get("resumen_promedio", {})
        return ReporteGasto(
            id_reporte_gasto_acumulado=orm.id_reporte_gasto_acumulado,
            id_activo_biologico=orm.id_activo_biologico,
            id_infraestructura=orm.id_infraestructura,
            fecha_inicio=orm.fecha_incio_reporte,
            fecha_fin=orm.fecha_fin_report,
            tipo_periodo=orm.categoria or "CICLO_COMPLETO",
            gasto_total_acumulado=orm.total_costo_directo,
            id_usuario=orm.id_usuario,
            fecha_generacion=orm.fecha_generacion,
            id_especie=(orm.json_parametros or {}).get("id_especie"),
            parametros=orm.json_parametros,
            gasto_promedio_individuo=(
                Decimal(promedio["gasto_promedio_individuo"])
                if promedio.get("gasto_promedio_individuo") is not None else None
            ),
            causa_no_calculable_promedio=promedio.get("causa_no_calculable_promedio"),
            **_desde_resumen(orm),
        )

    def guardar(self, reporte: ReporteGasto) -> ReporteGasto:
        try:
            orm = ReporteGastoAcumuladoModel(
                id_activo_biologico=reporte.id_activo_biologico,
                id_infraestructura=reporte.id_infraestructura,
                fecha_incio_reporte=reporte.fecha_inicio,
                fecha_fin_report=reporte.fecha_fin,
                categoria=reporte.tipo_periodo,
                total_costo_alimento=next(
                    (d.subtotal for d in reporte.desglose_categorias if d.categoria == "ALIMENTACION"),
                    0,
                ),
                total_costo_medicamento=next(
                    (d.subtotal for d in reporte.desglose_categorias if d.categoria == "MEDICACION"),
                    0,
                ),
                total_costo_directo=reporte.gasto_total_acumulado,
                id_usuario=reporte.id_usuario,
                json_parametros={
                    **(reporte.parametros or {}),
                    "resumen_promedio": {
                        "gasto_promedio_individuo": (
                            str(reporte.gasto_promedio_individuo)
                            if reporte.gasto_promedio_individuo is not None else None
                        ),
                        "causa_no_calculable_promedio": reporte.causa_no_calculable_promedio,
                    },
                    "resumen": _resumen(reporte),
                },
            )
            self.db.add(orm)
            self.db.flush()
            self.db.refresh(orm)
        except Exception as exc:
            raise_from_db_error(exc, {})
        reporte.id_reporte_gasto_acumulado = orm.id_reporte_gasto_acumulado
        reporte.fecha_generacion = orm.fecha_generacion
        return reporte

    def obtener(self, id_reporte_gasto_acumulado: int) -> Optional[ReporteGasto]:
        orm = self.db.get(ReporteGastoAcumuladoModel, id_reporte_gasto_acumulado)
        return self._a_entidad(orm) if orm else None

    def listar_historial(self, id_usuario: Optional[int], limite: int = 20) -> list[ReporteGasto]:
        query = self.db.query(ReporteGastoAcumuladoModel)
        if id_usuario is not None:
            query = query.filter(ReporteGastoAcumuladoModel.id_usuario == id_usuario)
        registros = (
            query.order_by(ReporteGastoAcumuladoModel.fecha_generacion.desc()).limit(limite).all()
        )
        return [self._a_entidad(o) for o in registros]
