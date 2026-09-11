"""Schemas de respuesta de RF-77 — Reporte de Gastos Acumulados."""
from __future__ import annotations

import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel

from src.supplies.domain.entities.reporte_gasto import ReporteGasto
from src.supplies.domain.entities.trabajo_reporte_gasto import EjecucionReporteGasto, TrabajoReporteGasto


class DesgloseCategoriaResponse(BaseModel):
    categoria: str
    subtotal: Decimal
    num_registros: int
    porcentaje: Decimal


class DesglosePeriodoResponse(BaseModel):
    etiqueta: str
    fecha_inicio: datetime.date
    fecha_fin: datetime.date
    monto: Decimal


class TendenciaGastoResponse(BaseModel):
    gasto_periodo_actual: Decimal
    gasto_periodo_anterior: Optional[Decimal]
    variacion_porcentual: Optional[Decimal]
    estado: str
    nota: Optional[str]


class RegistroSinCostoResponse(BaseModel):
    categoria: str
    id_origen: int
    fecha: datetime.date
    descripcion: str


class ReporteGastoResponse(BaseModel):
    id_reporte_gasto_acumulado: Optional[int]
    id_activo_biologico: Optional[int]
    id_infraestructura: Optional[int]
    id_especie: Optional[int]
    fecha_inicio: datetime.date
    fecha_fin: datetime.date
    tipo_periodo: str
    gasto_total_acumulado: Decimal
    gasto_promedio_individuo: Optional[Decimal]
    causa_no_calculable_promedio: Optional[str]
    sin_datos: bool
    desglose_categorias: list[DesgloseCategoriaResponse]
    desglose_temporal: list[DesglosePeriodoResponse]
    registros_sin_costo: list[RegistroSinCostoResponse]
    tendencia: Optional[TendenciaGastoResponse]
    fecha_generacion: Optional[datetime.datetime]

    @classmethod
    def desde_entidad(cls, r: ReporteGasto) -> "ReporteGastoResponse":
        return cls(
            id_reporte_gasto_acumulado=r.id_reporte_gasto_acumulado,
            id_activo_biologico=r.id_activo_biologico,
            id_infraestructura=r.id_infraestructura,
            id_especie=r.id_especie,
            fecha_inicio=r.fecha_inicio,
            fecha_fin=r.fecha_fin,
            tipo_periodo=r.tipo_periodo,
            gasto_total_acumulado=r.gasto_total_acumulado,
            gasto_promedio_individuo=r.gasto_promedio_individuo,
            causa_no_calculable_promedio=r.causa_no_calculable_promedio,
            sin_datos=r.sin_datos,
            desglose_categorias=[
                DesgloseCategoriaResponse(
                    categoria=d.categoria, subtotal=d.subtotal, num_registros=d.num_registros, porcentaje=d.porcentaje
                )
                for d in r.desglose_categorias
            ],
            desglose_temporal=[
                DesglosePeriodoResponse(
                    etiqueta=p.etiqueta, fecha_inicio=p.fecha_inicio, fecha_fin=p.fecha_fin, monto=p.monto
                )
                for p in r.desglose_temporal
            ],
            registros_sin_costo=[
                RegistroSinCostoResponse(
                    categoria=s.categoria, id_origen=s.id_origen, fecha=s.fecha, descripcion=s.descripcion
                )
                for s in r.registros_sin_costo
            ],
            tendencia=(
                TendenciaGastoResponse(
                    gasto_periodo_actual=r.tendencia.gasto_periodo_actual,
                    gasto_periodo_anterior=r.tendencia.gasto_periodo_anterior,
                    variacion_porcentual=r.tendencia.variacion_porcentual,
                    estado=r.tendencia.estado,
                    nota=r.tendencia.nota,
                )
                if r.tendencia is not None
                else None
            ),
            fecha_generacion=r.fecha_generacion,
        )

    @classmethod
    def desde_snapshot_y_resultado_json(cls, snapshot: ReporteGasto, resultado_json: dict) -> "ReporteGastoResponse":
        """Reconstruye la respuesta completa de un reporte generado async.

        ``reporte_gastos_acumulados`` solo persiste el encabezado y el total
        (columnas fijas); el desglose/tendencia/registros sin costo viven en
        ``ejecuciones_generacion_reportes_gastos.resultado_json`` (ver
        ``ProcesarColaReportesGastosUseCase._resultado_json``). Combina ambos.
        """
        tendencia_json = resultado_json.get("tendencia")
        return cls(
            id_reporte_gasto_acumulado=snapshot.id_reporte_gasto_acumulado,
            id_activo_biologico=snapshot.id_activo_biologico,
            id_infraestructura=snapshot.id_infraestructura,
            id_especie=snapshot.id_especie,
            fecha_inicio=snapshot.fecha_inicio,
            fecha_fin=snapshot.fecha_fin,
            tipo_periodo=snapshot.tipo_periodo,
            gasto_total_acumulado=Decimal(resultado_json["gasto_total_acumulado"]),
            gasto_promedio_individuo=(
                Decimal(resultado_json["gasto_promedio_individuo"])
                if resultado_json.get("gasto_promedio_individuo") is not None
                else None
            ),
            causa_no_calculable_promedio=resultado_json.get("causa_no_calculable_promedio"),
            sin_datos=resultado_json.get("sin_datos", False),
            desglose_categorias=[
                DesgloseCategoriaResponse(
                    categoria=d["categoria"],
                    subtotal=Decimal(d["subtotal"]),
                    num_registros=d["num_registros"],
                    porcentaje=Decimal(d["porcentaje"]),
                )
                for d in resultado_json.get("desglose_categorias", [])
            ],
            desglose_temporal=[
                DesglosePeriodoResponse(
                    etiqueta=p["etiqueta"],
                    fecha_inicio=datetime.date.fromisoformat(p["fecha_inicio"]),
                    fecha_fin=datetime.date.fromisoformat(p["fecha_fin"]),
                    monto=Decimal(p["monto"]),
                )
                for p in resultado_json.get("desglose_temporal", [])
            ],
            registros_sin_costo=[
                RegistroSinCostoResponse(
                    categoria=s["categoria"],
                    id_origen=s["id_origen"],
                    fecha=datetime.date.fromisoformat(s["fecha"]),
                    descripcion=s["descripcion"],
                )
                for s in resultado_json.get("registros_sin_costo", [])
            ],
            tendencia=(
                TendenciaGastoResponse(
                    gasto_periodo_actual=Decimal(tendencia_json["gasto_periodo_actual"]),
                    gasto_periodo_anterior=(
                        Decimal(tendencia_json["gasto_periodo_anterior"])
                        if tendencia_json.get("gasto_periodo_anterior") is not None
                        else None
                    ),
                    variacion_porcentual=(
                        Decimal(tendencia_json["variacion_porcentual"])
                        if tendencia_json.get("variacion_porcentual") is not None
                        else None
                    ),
                    estado=tendencia_json["estado"],
                    nota=tendencia_json.get("nota"),
                )
                if tendencia_json is not None
                else None
            ),
            fecha_generacion=snapshot.fecha_generacion,
        )


class HistorialReportesResponse(BaseModel):
    total: int
    items: list[ReporteGastoResponse]


class TrabajoReporteResponse(BaseModel):
    """Respuesta HTTP 202 al encolar un reporte async."""

    id_cola: Optional[int]
    estado: str
    fecha_solicitud: Optional[datetime.datetime]
    mensaje: str

    @classmethod
    def desde_entidad(cls, t: TrabajoReporteGasto, mensaje: str) -> "TrabajoReporteResponse":
        return cls(id_cola=t.id_cola, estado=t.estado.value, fecha_solicitud=t.fecha_solicitud, mensaje=mensaje)


class EstadoTrabajoReporteResponse(BaseModel):
    """Respuesta de polling del estado de un trabajo async (RF-77)."""

    id_cola: Optional[int]
    estado: str
    fecha_solicitud: Optional[datetime.datetime]
    fecha_procesado: Optional[datetime.datetime]
    intento: Optional[int]
    reporte: Optional[ReporteGastoResponse] = None

    @classmethod
    def desde_entidades(
        cls,
        trabajo: TrabajoReporteGasto,
        ejecucion: Optional[EjecucionReporteGasto],
        reporte_snapshot: Optional[ReporteGasto],
    ) -> "EstadoTrabajoReporteResponse":
        reporte_response = None
        if ejecucion is not None and ejecucion.resultado_json is not None and reporte_snapshot is not None:
            reporte_response = ReporteGastoResponse.desde_snapshot_y_resultado_json(
                reporte_snapshot, ejecucion.resultado_json
            )
        elif reporte_snapshot is not None:
            reporte_response = ReporteGastoResponse.desde_entidad(reporte_snapshot)
        return cls(
            id_cola=trabajo.id_cola,
            estado=trabajo.estado.value,
            fecha_solicitud=trabajo.fecha_solicitud,
            fecha_procesado=trabajo.fecha_procesado,
            intento=ejecucion.intento if ejecucion else None,
            reporte=reporte_response,
        )
