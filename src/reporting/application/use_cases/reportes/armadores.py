# | Fecha      | Nombre   | Que se hizo                                                        |
# |------------|----------|--------------------------------------------------------------------|
# | 2026-11-18 | Arekkazu | M08 RF-104: contenido de los 18 reportes según la matriz de campos |
# | 2026-11-19 | Arekkazu | M08 RF-104 M8-08: indicadores de las plantillas y encabezado con la finca del animal |
# | 2026-11-22 | Arekkazu | USAB2 M807 RF-104: el portafolio del ejecutivo es el de la valoración NIC 41 del período |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Arma el contenido de cada reporte de RF-104 con los datos de la fuente (matriz de campos del Drive).

Cada armador recibe el :class:`Contexto` (fuente en la instantánea, filtros ya validados, fincas del alcance) y
devuelve un :class:`ContenidoReporte`. Aquí se ponen los textos de lo que falta («Sin registro SINIGAN», «Causa
no registrada»), las advertencias de trazabilidad y los totales que pide cada reporte.

Los reportes gerenciales (ejecutivo, rentabilidad, comparativo) solo usan consultas de totales de la fuente: no
reciben filas por animal de la valoración (RNF-11, CA-19).
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Callable, Optional

from src.reporting.domain.repositories.fuente_reportes_repository import FuenteReportesRepository
from src.reporting.domain.reportes.catalogo import CATALOGO
from src.reporting.domain.reportes.contenido import (
    ENTERO,
    FECHA,
    FECHA_HORA,
    MONEDA,
    NUMERO,
    PORCENTAJE,
    Columna,
    ContenidoReporte,
    Indicador,
    Seccion,
    Tabla,
)
from src.reporting.domain.widgets import patron_variable
from src.shared.fechas import en_zona_usuario, etiqueta_zona, fin_dia_usuario, inicio_dia_usuario

SIN_SINIGAN = "Sin registro SINIGAN"
SIN_CAUSA = "Causa no registrada"
SIN_TRATAMIENTO = "Sin tratamiento registrado"
SIN_REGISTRO = "Sin registro"
NO_APLICA = "No aplica"
EXPORTACION_PENDIENTE = "Exportación pendiente"
DIAS_PREDICCION_ACTIVA = 7
DIAS_SIN_CALIBRAR = 90
HORAS_PRIORITARIO = 24

_NIVEL_TEXTO = {3: "Alto", 2: "Medio", 1: "Bajo", 0: "Sin riesgo"}
_NIVEL_FILTRO = {"ALTO": 3, "MEDIO": 2, "BAJO": 1}
_SALIDAS = {"MUERTE": "Muerte", "VENTA": "Venta", "SACRIFICIO": "Sacrificio", "PERDIDA": "Pérdida",
            "DESCARTE_SANITARIO": "Descarte sanitario", "TRASLADO": "Traslado a otra finca"}
_METODOS = {"VALOR_RAZONABLE": "Valor razonable", "VALORACION_POR_COSTO": "Costo"}
_SUMINISTROS = {"ALIMENTACION": "Alimentación", "MEDICACION": "Medicación", "OTROS": "Otros"}
_EVENTOS = {"DIAGNOSTICO": "Diagnóstico", "VACUNACION": "Vacunación", "TRATAMIENTO": "Tratamiento",
            "CONTROL_PREVENTIVO": "Control preventivo", "PREDICCION": "Diagnóstico predictivo"}
_RETRO = {"CORRECTO": "Predicción confirmada", "PARCIAL": "Predicción parcialmente acertada",
          "INCORRECTO": "Predicción descartada", "SIN_EVENTO": "Sin evento clínico"}
_VIAS = {"IM": "Intramuscular", "IV": "Intravenosa", "SC": "Subcutánea", "ORAL": "Oral", "TOPICA": "Tópica",
         "INTRAMAMARIA": "Intramamaria"}
_INSUMOS = {"VACUNA": "Vacuna", "MEDICAMENTO": "Medicamento", "ANTIPARASITARIO": "Antiparasitario"}
_DISPOSITIVO = {"ACTIVO": "Activo", "BUFFER_ACTIVO": "Activo (con datos en espera)", "SIN_SEÑAL": "Sin señal",
                "INACTIVO": "Inactivo", "EN_MANTENIMIENTO": "En mantenimiento", "DESCONOCIDO": "Falla o sin estado"}
_FILTRO_DISPOSITIVO = {"ACTIVO": ("ACTIVO", "BUFFER_ACTIVO"), "INACTIVO": ("INACTIVO",), "FALLO": ("DESCONOCIDO",),
                       "SIN_SEÑAL": ("SIN_SEÑAL",), "MANTENIMIENTO": ("EN_MANTENIMIENTO",)}
_ALERTA = {"FUERA_DE_RANGO": "Fuera de rango", "DESCONEXION": "Desconexión", "FALLO_DISPOSITIVO": "Falla del dispositivo"}
_DESCONEXION = ("DISPOSITIVO_SIN_SEÑAL", "DISPOSITIVO_INACTIVO", "HEARTBEAT_AUSENTE")
_SEVERIDAD = {"CRITICO": "CRITICA", "MODERADO": "ADVERTENCIA", "LEVE": "INFORMATIVA"}
_SEVERIDAD_TEXTO = {"CRITICA": "Crítica", "ADVERTENCIA": "Advertencia", "INFORMATIVA": "Informativa"}
_RECOMENDACION = {3: "Revisar al animal hoy y considerar aislarlo.", 2: "Vigilar de cerca en las próximas 24 horas.",
                  1: "Mantener el seguimiento de rutina."}


@dataclass
class Contexto:
    """Datos y filtros con los que se arma el contenido de un reporte."""
    fuente: FuenteReportesRepository
    tipo: str
    filtros: dict[str, Any]
    fincas: Optional[list[int]]  # alcance efectivo: None = todas
    hoy: date
    nombre_usuario: str = ""
    incluir_nic41: bool = False
    periodos: dict[str, dict[str, Any]] = field(default_factory=dict)
    generado: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def titulo(self) -> str:
        """Título del reporte."""
        return CATALOGO[self.tipo].titulo

    @property
    def desde(self) -> Optional[datetime]:
        """Inicio del rango en la zona del usuario, o ``None``."""
        inicio = self.filtros.get("fecha_inicio")
        return inicio_dia_usuario(inicio) if inicio else None

    @property
    def hasta(self) -> datetime:
        """Fin del rango en la zona del usuario (hoy si no hay fecha fin)."""
        return fin_dia_usuario(self.filtros.get("fecha_fin") or self.hoy)


def legible(valor: Optional[str]) -> str:
    """«EN_TRATAMIENTO» → «En tratamiento»."""
    return valor.replace("_", " ").capitalize() if valor else SIN_REGISTRO


def _nivel(valor: Optional[int]) -> str:
    return _NIVEL_TEXTO.get(valor if valor is not None else 0, "Sin riesgo")


def _num(valor: Any) -> Decimal:
    return Decimal(str(valor)) if valor is not None else Decimal(0)


def _nit(f: dict) -> Optional[str]:
    if not f.get("nit"):
        return None
    return f"{f['nit']}-{f['dv']}" if f.get("dv") else f["nit"]


def _rango(ctx: Contexto) -> str:
    inicio, fin = ctx.filtros.get("fecha_inicio"), ctx.filtros.get("fecha_fin")
    if inicio and fin:
        return f"{inicio:%d/%m/%Y} a {fin:%d/%m/%Y}"
    return f"Hasta {fin:%d/%m/%Y}" if fin else ""


def _periodo_texto(p: dict) -> str:
    return f"{p['fecha_inicio']:%d/%m/%Y} a {p['fecha_fin']:%d/%m/%Y}"


def encabezado(ctx: Contexto, fincas: Optional[list[int]], extra: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Razón social, NIT y finca(s) del reporte, más lo propio de cada uno (período, rango, exportación)."""
    filas = ctx.fuente.fincas(fincas)
    razones = sorted({f["razon_social"] for f in filas if f.get("razon_social")})
    nits = sorted({n for n in (_nit(f) for f in filas) if n})
    datos = [
        ("Razón social", ", ".join(razones) or "Sin razón social registrada"),
        ("NIT", ", ".join(nits) or "Sin NIT registrado"),
        ("Finca", ", ".join(f["nombre"] for f in filas) if filas else "Sin fincas asignadas"),
    ]
    generado = en_zona_usuario(ctx.generado)
    datos += extra + [("Fecha de generación", f"{generado:%d/%m/%Y %H:%M} ({etiqueta_zona(generado)})")]
    return datos


def _encabezado_rango(ctx: Contexto, fincas: Optional[list[int]], *extra: tuple[str, str]) -> list[tuple[str, str]]:
    return encabezado(ctx, fincas, [("Rango de fechas", _rango(ctx)), *extra])


def _fincas_filtro(ctx: Contexto) -> Optional[list[int]]:
    """Las fincas del alcance, la elegida en el filtro (ya validada) o, si se eligió un animal, la suya: así el
    encabezado lleva el titular y la finca del animal y no todas las del usuario (M8-08)."""
    activo = ctx.filtros.get("activo_biologico_id")
    ubicacion = ctx.fuente.ubicar("activo", activo) if activo else None
    if ubicacion and ubicacion.get("id_finca"):
        return [ubicacion["id_finca"]]
    finca = ctx.filtros.get("finca_id")
    return [finca] if finca else ctx.fincas


def _fincas_periodo(ctx: Contexto, periodo: dict) -> list[int]:
    """Fincas del titular del período dentro del alcance (y del filtro de finca, si hay)."""
    return ctx.fuente.fincas_de_titular(periodo["nit"], _fincas_filtro(ctx)) if periodo.get("nit") else []


def _sumar(filas: list[dict], clave: str) -> Decimal:
    return sum((_num(f.get(clave)) for f in filas), Decimal(0))


# --- Productivos -------------------------------------------------------------------------------

def inventario(ctx: Contexto) -> ContenidoReporte:
    """Arma el reporte de inventario de activos biológicos."""
    fincas = _fincas_filtro(ctx)
    filas = ctx.fuente.inventario(fincas=fincas, inicio=ctx.filtros["fecha_inicio"], fin=ctx.filtros["fecha_fin"],
                                  hasta=ctx.hasta, especie=ctx.filtros.get("especie_id"),
                                  estado=ctx.filtros.get("estado_activo"))
    detalle, sin_sinigan = [], 0
    for f in filas:
        sin_sinigan += f["sinigan"] is None
        estado = {"venta": "Vendido", "muerte": "Muerto"}.get(f["tipo_baja"] or "", legible(f["estado"])) \
            if f["estado"] == "BAJA" else legible(f["estado"])
        detalle.append({
            "id_activo": f["identificador"], "especie": f["especie"] or SIN_REGISTRO,
            "raza": f["raza"] or (NO_APLICA if f["tipo_activo"] == "POBLACIONAL" else SIN_REGISTRO),
            "sinigan": f["sinigan"] or SIN_SINIGAN, "estado": estado, "fecha_ingreso": f["fecha_ingreso"],
            "animales": f["cantidad"], "peso_kg": f["peso_kg"] if f["peso_kg"] is not None else "Sin pesaje",
            "etapa": f["etapa"] or "Sin etapa", "metodo": _METODOS.get(f["metodo"], "Sin valorar"),
            "valor": f["valor"] if f["valor"] is not None else "Sin valorar", "finca": f["finca"],
            "lote": f["identificador"] if f["tipo_activo"] == "POBLACIONAL" else NO_APLICA,
        })
    por_especie: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for f in filas:
        par = por_especie[f["especie"] or SIN_REGISTRO]
        par[0] += 1
        par[1] += f["cantidad"] or 0
    advertencias = []
    if sin_sinigan:
        advertencias.append(f"{sin_sinigan} {'activo no tiene' if sin_sinigan == 1 else 'activos no tienen'} "
                            "identificación SINIGAN registrada: su trazabilidad ante el ICA está incompleta.")
    return ContenidoReporte(
        titulo=ctx.titulo, encabezado=_encabezado_rango(ctx, fincas),
        resumen=[
            Tabla("Animales por especie", [Columna("especie", "Especie"), Columna("registros", "Registros", ENTERO),
                                           Columna("animales", "Animales", ENTERO)],
                  [{"especie": k, "registros": v[0], "animales": v[1]} for k, v in sorted(por_especie.items())]),
            Tabla("Valor del inventario", [Columna("concepto", "Concepto"), Columna("valor", "Valor (COP)", MONEDA)],
                  [{"concepto": "Valor total del inventario", "valor": _sumar(filas, "valor")}]),
        ],
        detalle=Tabla("Inventario", [
            Columna("id_activo", "ID activo"), Columna("especie", "Especie"), Columna("raza", "Raza"),
            Columna("sinigan", "SINIGAN"), Columna("estado", "Estado"),
            Columna("fecha_ingreso", "Fecha de ingreso", FECHA), Columna("animales", "Animales", ENTERO),
            Columna("peso_kg", "Peso (kg)", NUMERO), Columna("etapa", "Etapa productiva"),
            Columna("metodo", "Método de valoración"), Columna("valor", "Valor razonable (COP)", MONEDA),
            Columna("finca", "Finca"), Columna("lote", "Lote"),
        ], detalle),
        indicadores=[Indicador("Total de activos", len(filas), ENTERO),
                     Indicador("Valor total del inventario", _sumar(filas, "valor"), MONEDA),
                     Indicador("Activos sin SINIGAN", sin_sinigan, ENTERO)],
        advertencias=advertencias,
    )


def costos_suministros(ctx: Contexto) -> ContenidoReporte:
    """Arma el reporte de costos de suministros."""
    fincas = _fincas_filtro(ctx)
    filas = ctx.fuente.costos(fincas=fincas, inicio=ctx.filtros["fecha_inicio"], fin=ctx.filtros["fecha_fin"],
                              especie=ctx.filtros.get("especie_id"), tipo=ctx.filtros.get("tipo_suministro"))
    detalle = [{
        "tipo": _SUMINISTROS[f["tipo"]], "nombre": f["nombre"] or SIN_REGISTRO, "cantidad": f["cantidad"],
        "unidad": f["unidad"] or SIN_REGISTRO, "costo_unitario": f["costo_unitario"], "costo_total": f["costo_total"],
        "proveedor": "Sin proveedor registrado", "fecha": f["fecha"], "especie": f["especie"] or SIN_REGISTRO,
        "finca": f["finca"],
    } for f in filas]
    por_tipo: dict[str, Decimal] = defaultdict(Decimal)
    for f in filas:
        por_tipo[_SUMINISTROS[f["tipo"]]] += _num(f["costo_total"])
    totales = [{"tipo": t, "total": v} for t, v in sorted(por_tipo.items())]
    totales.append({"tipo": "Gran total", "total": sum(por_tipo.values(), Decimal(0))})
    gran_total = sum(por_tipo.values(), Decimal(0))
    por_nombre: dict[str, Decimal] = defaultdict(Decimal)
    for d in detalle:
        por_nombre[d["nombre"]] += _num(d["costo_total"])
    dias = (ctx.filtros["fecha_fin"] - ctx.filtros["fecha_inicio"]).days + 1
    tabla_totales = Tabla("Totales por tipo de suministro",
                          [Columna("tipo", "Tipo de suministro"), Columna("total", "Costo total (COP)", MONEDA)], totales)
    return ContenidoReporte(
        titulo=ctx.titulo, encabezado=_encabezado_rango(ctx, fincas),
        detalle=Tabla("Costos de suministros", [
            Columna("tipo", "Tipo de suministro"), Columna("nombre", "Suministro"),
            Columna("cantidad", "Cantidad", NUMERO), Columna("unidad", "Unidad"),
            Columna("costo_unitario", "Costo unitario (COP)", MONEDA), Columna("costo_total", "Costo total (COP)", MONEDA),
            Columna("proveedor", "Proveedor"), Columna("fecha", "Fecha de aplicación", FECHA),
            Columna("especie", "Especie"), Columna("finca", "Finca"),
        ], detalle),
        resumen=[tabla_totales], finales=[tabla_totales],
        indicadores=[Indicador("Costo total del período", gran_total, MONEDA),
                     Indicador("Suministro con mayor costo",
                               max(por_nombre, key=por_nombre.get) if por_nombre else "Sin consumos"),
                     Indicador("Costo promedio diario", gran_total / dias, MONEDA)],
    )


def productividad(ctx: Contexto) -> ContenidoReporte:
    """Arma el reporte de productividad."""
    fincas = _fincas_filtro(ctx)
    activo = ctx.filtros.get("lote_id")
    filas = ctx.fuente.produccion(fincas=fincas, desde=ctx.desde, hasta=ctx.hasta,
                                  especie=ctx.filtros.get("especie_id"), activo=activo)
    grupos: dict[tuple, list[dict]] = defaultdict(list)
    for f in filas:
        grupos[(f["id_activo_biologico"], f["metrica"], f["tipo_metrica"])].append(f)
    detalle = []
    for (_, metrica, tipo), medidas in grupos.items():
        ultima = max(medidas, key=lambda m: m["fecha"])
        animales = ultima["numero_animales"] or 1
        if tipo == "PESO":
            promedio = _num(ultima["valor"])
            total = promedio * animales
        else:
            total = _sumar(medidas, "valor")
            promedio = total / animales
        detalle.append({
            "especie": ultima["especie"] or SIN_REGISTRO, "lote": ultima["identificador"], "animales": animales,
            "metrica": f"{metrica} ({legible(tipo).lower()})", "promedio": promedio, "total": total,
            "unidad": ultima["unidad"] or SIN_REGISTRO, "fecha": en_zona_usuario(ultima["fecha"]).date(),
            "etapa": ultima["etapa"] or "Sin etapa", "finca": ultima["finca"],
        })
    conversion = ctx.fuente.conversion(fincas=fincas, inicio=ctx.filtros["fecha_inicio"], fin=ctx.filtros["fecha_fin"],
                                       especie=ctx.filtros.get("especie_id"), activo=activo)
    calculadas = [c for c in conversion if c["ca_calculado"] is not None]
    mejor = min(calculadas, key=lambda c: c["ca_calculado"]) if calculadas else None
    return ContenidoReporte(
        titulo=ctx.titulo, encabezado=_encabezado_rango(ctx, fincas),
        detalle=Tabla("Producción por lote", [
            Columna("especie", "Especie"), Columna("lote", "Lote"), Columna("animales", "Número de animales", ENTERO),
            Columna("metrica", "Métrica productiva"), Columna("promedio", "Valor promedio por animal", NUMERO),
            Columna("total", "Valor total del lote", NUMERO), Columna("unidad", "Unidad"),
            Columna("fecha", "Fecha de medición", FECHA), Columna("etapa", "Etapa productiva"), Columna("finca", "Finca"),
        ], detalle),
        resumen=[Tabla("Conversión alimenticia por lote", [
            Columna("lote", "Lote"), Columna("especie", "Especie"), Columna("desde", "Desde", FECHA),
            Columna("hasta", "Hasta", FECHA), Columna("alimento", "Alimento consumido (kg)", NUMERO),
            Columna("ganancia", "Producto obtenido (kg)", NUMERO),
            Columna("conversion", "kg de alimento por kg de producto", NUMERO), Columna("finca", "Finca"),
        ], [{"lote": c["identificador"], "especie": c["especie"] or SIN_REGISTRO, "desde": c["fecha_inicio_periodo"],
             "hasta": c["fecha_fin_periodo"], "alimento": c["alimento_consumido_total_kg"],
             "ganancia": c["ganancia_peso_kg"],
             "conversion": c["ca_calculado"] if c["ca_calculado"] is not None else "Sin calcular",
             "finca": c["finca"]} for c in conversion])],
        indicadores=[
            Indicador("Lotes con medición", len({d["lote"] for d in detalle}), ENTERO),
            Indicador("Mejor lote (menor conversión)", mejor["identificador"] if mejor else "Sin calcular"),
            Indicador("Conversión alimenticia promedio",
                      _sumar(calculadas, "ca_calculado") / len(calculadas) if calculadas else "Sin calcular", NUMERO),
        ],
    )


def bajas_y_salidas(ctx: Contexto) -> ContenidoReporte:
    """Arma el reporte de bajas y salidas."""
    fincas = _fincas_filtro(ctx)
    tipo = ctx.filtros.get("tipo_salida")
    filas = [f for f in ctx.fuente.salidas(fincas=fincas, desde=ctx.desde, hasta=ctx.hasta,
                                           especie=ctx.filtros.get("especie_id"))
             if tipo is None or f["tipo"] == tipo]
    detalle, sin_causa = [], 0
    for f in filas:
        if f["tipo"] == "MUERTE" and not f["motivo"]:
            sin_causa += 1
        if f["valor_venta"] is not None:
            valor, origen = f["valor_venta"], "Venta registrada"
        elif f["valor_referencia"] is not None:
            valor, origen = f["valor_referencia"], "Valor razonable del último cierre"
        else:
            valor, origen = "Sin valor", "Sin valor registrado"
        detalle.append({
            "id_activo": f["identificador"], "sinigan": f["sinigan"] or SIN_SINIGAN,
            "especie": f["especie"] or SIN_REGISTRO, "tipo": _SALIDAS.get(f["tipo"], legible(f["tipo"])),
            "fecha": en_zona_usuario(f["fecha"]).date(), "animales": f["cantidad"] or 1,
            "motivo": f["motivo"] or (SIN_CAUSA if f["tipo"] == "MUERTE" else "Sin motivo registrado"),
            "valor": valor, "origen_valor": origen, "destino": f["destino"] or NO_APLICA, "finca": f["finca"],
        })
    por_tipo: dict[str, int] = defaultdict(int)
    for d in detalle:
        por_tipo[d["tipo"]] += d["animales"]
    sin_sinigan = sum(1 for f in filas if not f["sinigan"])
    advertencias = []
    if sin_sinigan:
        advertencias.append(f"{sin_sinigan} {'registro no tiene' if sin_sinigan == 1 else 'registros no tienen'} "
                            "identificación SINIGAN: revísalos antes de reportar ante la autoridad sanitaria.")
    if sin_causa:
        advertencias.append(f"{sin_causa} {'muerte no tiene' if sin_causa == 1 else 'muertes no tienen'} causa "
                            "registrada: la trazabilidad de la baja ante el ICA está incompleta.")
    return ContenidoReporte(
        titulo=ctx.titulo, encabezado=_encabezado_rango(ctx, fincas),
        resumen=[Tabla("Salidas por tipo", [Columna("tipo", "Tipo de salida"), Columna("animales", "Animales", ENTERO)],
                       [{"tipo": k, "animales": v} for k, v in sorted(por_tipo.items())])],
        detalle=Tabla("Bajas y salidas", [
            Columna("id_activo", "ID activo"), Columna("sinigan", "Identificación SINIGAN"),
            Columna("especie", "Especie"), Columna("tipo", "Tipo de salida"), Columna("fecha", "Fecha de salida", FECHA),
            Columna("animales", "Animales", ENTERO), Columna("motivo", "Causa o motivo"),
            Columna("valor", "Valor al salir (COP)", MONEDA), Columna("origen_valor", "Origen del valor"),
            Columna("destino", "Comprador o destino"), Columna("finca", "Finca de origen"),
        ], detalle),
        indicadores=[
            Indicador("Total de salidas", sum(por_tipo.values()), ENTERO),
            Indicador("Total en ventas", sum((_num(d["valor"]) for d in detalle
                                              if d["tipo"] == "Venta" and not isinstance(d["valor"], str)), Decimal(0)),
                      MONEDA),
            Indicador("Total de muertes", por_tipo.get("Muerte", 0), ENTERO),
            Indicador("Sin registro SINIGAN", sin_sinigan, ENTERO),
        ],
        advertencias=advertencias,
    )


# --- Contables ---------------------------------------------------------------------------------

def _estado_exportacion(exportaciones: list[dict]) -> dict[str, Any]:
    """La exportación del período: la última exitosa; si no hay, «Exportación pendiente»."""
    exitosas = [e for e in exportaciones if e["estado"] == "SUCCESS"]
    if exitosas:
        e = exitosas[-1]
        return {"id": str(e["id_integracion_solicitud"]), "fecha": e["fecha_confirmacion"] or e["fecha_envio"],
                "estado": "Exitosa"}
    return {"id": EXPORTACION_PENDIENTE, "fecha": EXPORTACION_PENDIENTE,
            "estado": "Fallida" if exportaciones else "Pendiente"}


def valoracion_nic41(ctx: Contexto) -> ContenidoReporte:
    """Arma el reporte de valoración NIC 41 del periodo."""
    periodo = ctx.periodos["periodo_contable"]
    fincas = _fincas_periodo(ctx, periodo)
    filas = ctx.fuente.valoracion_periodo(id_periodo=periodo["id_periodo_contable"], fincas=fincas)
    exportacion = _estado_exportacion(ctx.fuente.exportaciones(periodo["id_periodo_contable"]))
    fecha_exp = exportacion["fecha"]
    fecha_texto = (f"{en_zona_usuario(fecha_exp):%d/%m/%Y %H:%M}" if isinstance(fecha_exp, datetime) else fecha_exp)
    detalle = [{
        "id_activo": f["identificador"], "sinigan": f["sinigan"] or SIN_SINIGAN, "especie": f["especie"] or SIN_REGISTRO,
        "metodo": _METODOS[f["metodo"]],
        "valor_razonable": f["valor_razonable"] if f["valor_razonable"] is not None else NO_APLICA,
        "costo": f["costo_atribuido"] if f["costo_atribuido"] is not None else NO_APLICA,
        "variacion": f["variacion"], "id_exportacion": exportacion["id"], "fecha_exportacion": fecha_exp,
        "estado_exportacion": exportacion["estado"],
    } for f in filas]
    por_metodo: dict[str, Decimal] = defaultdict(Decimal)
    for f in filas:
        por_metodo[_METODOS[f["metodo"]]] += _num(f["valor_razonable"] if f["metodo"] == "VALOR_RAZONABLE"
                                                  else f["costo_atribuido"])
    return ContenidoReporte(
        titulo=ctx.titulo,
        encabezado=encabezado(ctx, fincas, [("Período contable", _periodo_texto(periodo)),
                                            ("Exportación contable", exportacion["id"]),
                                            ("Fecha de la exportación contable", fecha_texto)]),
        resumen=[Tabla("Valor por método de valoración",
                       [Columna("metodo", "Método"), Columna("valor", "Valor (COP)", MONEDA)],
                       [{"metodo": k, "valor": v} for k, v in sorted(por_metodo.items())]
                       + [{"metodo": "Total", "valor": sum(por_metodo.values(), Decimal(0))},
                          {"metodo": "Variación total del período", "valor": _sumar(filas, "variacion")}])],
        detalle=Tabla("Valoración por activo", [
            Columna("id_activo", "ID activo"), Columna("sinigan", "Identificación SINIGAN"),
            Columna("especie", "Especie"), Columna("metodo", "Método de valoración"),
            Columna("valor_razonable", "Valor razonable (COP)", MONEDA), Columna("costo", "Costo atribuido (COP)", MONEDA),
            Columna("variacion", "Variación frente al período anterior (COP)", MONEDA),
            Columna("id_exportacion", "Exportación contable"),
            Columna("fecha_exportacion", "Fecha de la exportación", FECHA_HORA),
            Columna("estado_exportacion", "Estado de la exportación"),
        ], detalle),
        indicadores=[
            Indicador("Valor razonable total", _sumar(filas, "valor_razonable"), MONEDA),
            Indicador("Costo atribuido total", _sumar(filas, "costo_atribuido"), MONEDA),
            Indicador("Variación total frente al período anterior", _sumar(filas, "variacion"), MONEDA),
        ],
        firma=ctx.nombre_usuario or "Contador",
    )


def estado_exportaciones(ctx: Contexto) -> ContenidoReporte:
    """Arma el reporte del estado de las exportaciones contables del periodo."""
    periodo = ctx.periodos["periodo_contable"]
    filas = ctx.fuente.exportaciones(periodo["id_periodo_contable"])
    detalle = []
    for e in filas:
        exitosa = e["estado"] == "SUCCESS"
        errores = []
        if not exitosa:
            errores.append(e["error"] or "La integración contable no respondió a tiempo o rechazó la solicitud.")
        if e["fallidos"]:
            errores.append(f"{e['fallidos']} documento(s) no se generaron.")
        detalle.append({
            "id": str(e["id_integracion_solicitud"]), "estado": "Exitosa" if exitosa else "Fallida",
            "confirmacion": str(e["confirmacion"]) if exitosa and e["confirmacion"] else
            ("Sin confirmación" if exitosa else NO_APLICA),
            "envio": e["fecha_envio"], "fecha_confirmacion": e["fecha_confirmacion"] or "Sin confirmación",
            "activos": e["activos"] or 0, "monto": e["monto"] if e["monto"] is not None else Decimal(0),
            "errores": " ".join(errores) or "Sin errores", "hash": e["hash_paquete"] or "Sin hash registrado",
        })
    if not detalle:
        detalle.append({"id": EXPORTACION_PENDIENTE, "estado": "Pendiente", "confirmacion": NO_APLICA,
                        "envio": "Sin envío", "fecha_confirmacion": "Sin confirmación", "activos": 0,
                        "monto": Decimal(0), "errores": "El período aún no se ha exportado.", "hash": NO_APLICA})
    conteo: dict[str, int] = defaultdict(int)
    for d in detalle:
        conteo[d["estado"]] += 1
    return ContenidoReporte(
        titulo=ctx.titulo,
        encabezado=encabezado(ctx, _fincas_periodo(ctx, periodo), [("Período contable", _periodo_texto(periodo))]),
        resumen=[Tabla("Exportaciones por estado", [Columna("estado", "Estado"), Columna("total", "Exportaciones", ENTERO)],
                       [{"estado": k, "total": v} for k, v in sorted(conteo.items())])],
        detalle=Tabla("Exportaciones del período", [
            Columna("id", "Exportación"), Columna("estado", "Estado"), Columna("confirmacion", "Confirmación"),
            Columna("envio", "Enviada", FECHA_HORA), Columna("fecha_confirmacion", "Confirmada", FECHA_HORA),
            Columna("activos", "Activos incluidos", ENTERO), Columna("monto", "Monto total (COP)", MONEDA),
            Columna("errores", "Errores"), Columna("hash", "Huella del paquete"),
        ], detalle),
        indicadores=[Indicador("Total de exportaciones", len(filas), ENTERO)]
        + [Indicador(texto, conteo.get(clave, 0) if filas else 0, ENTERO)
           for texto, clave in (("Exitosas", "Exitosa"), ("Fallidas", "Fallida"))]
        + [Indicador("Pendientes", 0 if filas else 1, ENTERO)],
    )


def _causa_variacion(f: dict) -> str:
    base = f["base_vr"] if f["base_vr"] is not None else f["base_costo"]
    comp = f["comp_vr"] if f["comp_vr"] is not None else f["comp_costo"]
    if f["dado_de_baja"]:
        return "Baja"
    if comp is None:
        return "Nuevo activo"
    if f["deterioro"]:
        return "Deterioro"
    if base is not None and (f["base_vr"] is None) != (f["comp_vr"] is None):
        return "Ajuste de método"
    return "Crecimiento biológico"


def variacion_periodos(ctx: Contexto) -> ContenidoReporte:
    """Arma el reporte de variación de valor entre dos periodos."""
    base, comp = ctx.periodos["periodo_contable_base"], ctx.periodos["periodo_contable_comparacion"]
    fincas = _fincas_periodo(ctx, base)
    filas = ctx.fuente.variacion_periodos(base=base["id_periodo_contable"], comparacion=comp["id_periodo_contable"],
                                          fincas=fincas)
    detalle = []
    for f in filas:
        valor_base = Decimal(0) if f["dado_de_baja"] else _num(f["base_vr"] if f["base_vr"] is not None
                                                                 else f["base_costo"])
        valor_comp = _num(f["comp_vr"] if f["comp_vr"] is not None else f["comp_costo"])
        variacion = valor_base - valor_comp
        detalle.append({
            "id_activo": f["identificador"], "especie": f["especie"] or SIN_REGISTRO, "base": valor_base,
            "comparacion": valor_comp, "variacion": variacion,
            "porcentaje": (variacion / valor_comp * 100) if valor_comp else NO_APLICA,
            "causa": _causa_variacion(f), "finca": f["finca"],
        })
    pivote: dict[tuple[str, str], Decimal] = defaultdict(Decimal)
    por_finca: dict[str, Decimal] = defaultdict(Decimal)
    for d in detalle:
        pivote[(d["especie"], d["finca"])] += d["variacion"]
        por_finca[d["finca"]] += d["variacion"]
    resumen = [{"especie": e, "finca": fi, "variacion": v} for (e, fi), v in sorted(pivote.items())]
    resumen.append({"especie": "Gran total", "finca": "Todas", "variacion": _sumar(detalle, "variacion")})
    return ContenidoReporte(
        titulo=ctx.titulo,
        encabezado=encabezado(ctx, fincas, [("Período base", _periodo_texto(base)),
                                            ("Período de comparación", _periodo_texto(comp))]),
        resumen=[Tabla("Variación por especie y finca", [
            Columna("especie", "Especie"), Columna("finca", "Finca"), Columna("variacion", "Variación (COP)", MONEDA)],
            resumen)],
        detalle=Tabla("Variación por activo", [
            Columna("id_activo", "ID activo"), Columna("especie", "Especie"),
            Columna("base", "Valor razonable período base (COP)", MONEDA),
            Columna("comparacion", "Valor razonable período de comparación (COP)", MONEDA),
            Columna("variacion", "Variación absoluta (COP)", MONEDA), Columna("porcentaje", "Variación (%)", PORCENTAJE),
            Columna("causa", "Causa de la variación"), Columna("finca", "Finca"),
        ], detalle),
        indicadores=[
            Indicador("Variación total (COP)", _sumar(detalle, "variacion"), MONEDA),
            Indicador("Variación total (%)", _sumar(detalle, "variacion") / _sumar(detalle, "comparacion") * 100
                      if _sumar(detalle, "comparacion") else NO_APLICA, PORCENTAJE),
            Indicador("Finca con mayor variación", max(por_finca, key=lambda k: abs(por_finca[k]))
                      if por_finca else "Sin variaciones"),
        ],
    )


# --- Sanitarios --------------------------------------------------------------------------------

def _filas_sanitarias(ctx: Contexto, filas: list[dict]) -> list[dict]:
    nombres = ctx.fuente.nombres_usuarios([f["id_veterinario"] for f in filas if f["id_veterinario"]])
    salida = []
    for f in filas:
        prediccion = f["fuente"] == "M04"
        if prediccion:
            confianza = f" (confianza {round(_num(f['confianza']) * 100)} %)" if f["confianza"] is not None else ""
            descripcion = f"Posible {f['descripcion'] or 'condición no identificada'}{confianza}"
            resultado = _RETRO.get(f["resultado"] or "", "Sin retroalimentación del veterinario")
        else:
            descripcion = f["descripcion"] or "Sin descripción"
            resultado = f["resultado"] or "Sin resultado registrado"
        tratamiento = SIN_TRATAMIENTO
        if f["tipo"] == "TRATAMIENTO" and f["medicamento"]:
            partes = [f["medicamento"], f["frecuencia"], f["duracion"]]
            tratamiento = " · ".join(p for p in partes if p)
        dosis = f"{f['dosis']} {f['unidad_dosis'] or ''}".strip() if f["dosis"] is not None else "Sin dosis registrada"
        salida.append({
            "id_activo": f["identificador"], "sinigan": f["sinigan"] or SIN_SINIGAN,
            "especie": f["especie"] or SIN_REGISTRO, "tipo": _EVENTOS.get(f["tipo"], legible(f["tipo"])),
            "fecha": f["fecha"], "descripcion": descripcion, "nivel": _nivel(f["nivel_riesgo"]),
            "veterinario": nombres.get(f["id_veterinario"]) or "Sin veterinario registrado",
            "tratamiento": tratamiento, "medicamento": f["medicamento"] or "Sin medicamento",
            "dosis": dosis, "resultado": resultado, "finca": f["finca"], "_tipo": f["tipo"],
            "_nivel": f["nivel_riesgo"],
        })
    return salida


# Tablas de 12 o más columnas: «SINIGAN» a secas, para que quepan en carta sin partir palabras (M8-12).
_COLUMNAS_SANITARIAS = [
    Columna("id_activo", "ID activo"), Columna("sinigan", "SINIGAN"), Columna("especie", "Especie"),
    Columna("tipo", "Tipo de evento"), Columna("fecha", "Fecha", FECHA_HORA), Columna("descripcion", "Descripción"),
    Columna("nivel", "Nivel de riesgo"), Columna("veterinario", "Veterinario responsable"),
    Columna("tratamiento", "Tratamiento aplicado"), Columna("medicamento", "Medicamento"), Columna("dosis", "Dosis"),
    Columna("resultado", "Resultado clínico"), Columna("finca", "Finca"),
]


def historico_sanitario(ctx: Contexto) -> ContenidoReporte:
    """Arma el reporte del histórico sanitario."""
    fincas = _fincas_filtro(ctx)
    filas = _filas_sanitarias(ctx, ctx.fuente.eventos_sanitarios(
        fincas=fincas, desde=ctx.desde, hasta=ctx.hasta, especie=ctx.filtros.get("especie_id"),
        activo=ctx.filtros.get("activo_biologico_id")))
    tipo, nivel = ctx.filtros.get("tipo_evento"), _NIVEL_FILTRO.get(ctx.filtros.get("nivel_riesgo") or "")
    if tipo:
        filas = [f for f in filas if f["_tipo"] == tipo or (tipo == "DIAGNOSTICO" and f["_tipo"] == "PREDICCION")]
    if nivel is not None:
        filas = [f for f in filas if f["_nivel"] == nivel]
    conteo: dict[str, int] = defaultdict(int)
    for f in filas:
        conteo[f["tipo"]] += 1
    clinicos = [f for f in filas if f["_tipo"] != "PREDICCION"]
    resueltos = [f for f in clinicos if f["resultado"] != "Sin resultado registrado"]
    sin_sinigan = len({f["id_activo"] for f in filas if f["sinigan"] == SIN_SINIGAN})
    return ContenidoReporte(
        titulo=ctx.titulo, encabezado=_encabezado_rango(ctx, fincas),
        indicadores=[
            Indicador("Total de eventos", len(filas), ENTERO),
            Indicador("Tasa de resolución clínica",
                      Decimal(len(resueltos) * 100) / len(clinicos) if clinicos else "Sin eventos clínicos", PORCENTAJE),
            Indicador("Activos atendidos", len({f["id_activo"] for f in filas}), ENTERO),
        ],
        advertencias=[f"{sin_sinigan} {'activo no tiene' if sin_sinigan == 1 else 'activos no tienen'} identificación "
                      "oficial SINIGAN. Para la compatibilidad con el ICA, regístrala en Activos biológicos."]
        if sin_sinigan else [],
        resumen=[Tabla("Eventos por tipo", [Columna("tipo", "Tipo de evento"), Columna("total", "Eventos", ENTERO)],
                       [{"tipo": k, "total": v} for k, v in sorted(conteo.items())])],
        detalle=Tabla("Historial sanitario", _COLUMNAS_SANITARIAS, filas),
    )


def _prediccion(f: dict) -> dict[str, Any]:
    probabilidades = [v for v in (f.get("probabilidad_enfermedad") or {}).values() if isinstance(v, (int, float))]
    probabilidad = (max(probabilidades) if probabilidades else _num(f["confianza_global"])) * 100
    factores = [f"{legible(k)}: {v}" for k, v in (f.get("probabilidad_riesgo") or {}).items()
                if not k.startswith("umbral")]
    return {
        "id_activo": f["identificador"], "sinigan": f["sinigan"] or SIN_SINIGAN, "especie": f["especie"] or SIN_REGISTRO,
        "nivel": _nivel(f["nivel_riesgo"]), "condicion": f["condicion"] or "Condición no identificada",
        "probabilidad": round(_num(probabilidad), 2), "fecha": f["fecha_inferencia"],
        "vence": f["fecha_inferencia"] + timedelta(days=DIAS_PREDICCION_ACTIVA),
        "factores": "; ".join(factores) or "Sin factores registrados",
        "recomendacion": f["accion_sugerida"] or _RECOMENDACION.get(f["nivel_riesgo"], "Sin recomendación"),
        "finca": f["finca"], "_nivel": f["nivel_riesgo"],
    }


_COLUMNAS_PREDICCION = [
    Columna("id_activo", "ID activo"), Columna("sinigan", "Identificación SINIGAN"), Columna("especie", "Especie"),
    Columna("nivel", "Nivel de riesgo"), Columna("condicion", "Condición predicha"),
    Columna("probabilidad", "Probabilidad (%)", PORCENTAJE), Columna("fecha", "Fecha de la predicción", FECHA_HORA),
    Columna("vence", "Vence", FECHA_HORA), Columna("factores", "Factores de riesgo detectados"),
    Columna("recomendacion", "Recomendación"), Columna("finca", "Finca"),
]


def ficha_animal(ctx: Contexto) -> ContenidoReporte:
    """Arma la ficha de un animal."""
    activo = ctx.filtros["activo_biologico_id"]
    ficha = ctx.fuente.ficha(activo) or {}
    fincas = [ficha["id_finca"]] if ficha.get("id_finca") else ctx.fincas
    desde = ctx.desde
    nombres = ctx.fuente.nombres_usuarios([ficha.get("id_propietario")] if ficha.get("id_propietario") else [])
    individual = ficha.get("tipo_activo") != "POBLACIONAL"
    identificacion = Tabla("Identificación", [Columna("dato", "Dato"), Columna("valor", "Valor")], [
        {"dato": "Identificador", "valor": ficha.get("identificador")},
        {"dato": "Identificación SINIGAN", "valor": ficha.get("sinigan") or SIN_SINIGAN},
        {"dato": "Especie", "valor": ficha.get("especie") or SIN_REGISTRO},
        {"dato": "Raza", "valor": ficha.get("raza") or (SIN_REGISTRO if individual else NO_APLICA)},
        {"dato": "Fecha de nacimiento o ingreso",
         "valor": f"{(ficha.get('fecha_nacimiento') or ficha.get('fecha_ingreso')):%d/%m/%Y}"
         if (ficha.get("fecha_nacimiento") or ficha.get("fecha_ingreso")) else SIN_REGISTRO},
        {"dato": "Sexo", "valor": legible(ficha.get("sexo")) if ficha.get("sexo") else
         (SIN_REGISTRO if individual else NO_APLICA)},
        {"dato": "Propietario", "valor": nombres.get(ficha.get("id_propietario")) or SIN_REGISTRO},
        {"dato": "Finca actual", "valor": ficha.get("finca") or SIN_REGISTRO},
        {"dato": "Área", "valor": ficha.get("area") or SIN_REGISTRO},
        {"dato": "Estado", "valor": legible(ficha.get("estado"))},
        {"dato": "Animales", "valor": str(ficha.get("cantidad") or 1)},
    ])
    produccion = ctx.fuente.produccion(fincas=fincas, desde=desde, hasta=ctx.hasta, especie=None, activo=activo)
    historial = Tabla("Historial productivo", [
        Columna("fecha", "Fecha de medición", FECHA_HORA), Columna("metrica", "Métrica"),
        Columna("valor", "Valor", NUMERO), Columna("unidad", "Unidad"), Columna("etapa", "Etapa productiva"),
    ], [{"fecha": p["fecha"], "metrica": p["metrica"], "valor": p["valor"], "unidad": p["unidad"] or SIN_REGISTRO,
         "etapa": p["etapa"] or "Sin etapa"} for p in produccion])
    sanitario = _filas_sanitarias(ctx, ctx.fuente.eventos_sanitarios(fincas=fincas, desde=desde, hasta=ctx.hasta,
                                                                     especie=None, activo=activo))
    tabla_sanitaria = Tabla("Historial sanitario", [c for c in _COLUMNAS_SANITARIAS
                                                    if c.clave not in ("id_activo", "sinigan", "especie", "finca")],
                            sanitario)
    suministros = ctx.fuente.costos(fincas=fincas, inicio=ctx.filtros.get("fecha_inicio"), fin=ctx.filtros["fecha_fin"],
                                    especie=None, tipo=None, activo=activo)
    tabla_suministros = Tabla("Suministros aplicados", [
        Columna("fecha", "Fecha", FECHA), Columna("tipo", "Tipo"), Columna("nombre", "Suministro"),
        Columna("cantidad", "Cantidad", NUMERO), Columna("unidad", "Unidad"), Columna("costo", "Costo (COP)", MONEDA),
    ], [{"fecha": s["fecha"], "tipo": _SUMINISTROS[s["tipo"]], "nombre": s["nombre"] or SIN_REGISTRO,
         "cantidad": s["cantidad"], "unidad": s["unidad"] or SIN_REGISTRO, "costo": s["costo_total"]}
        for s in suministros])
    valoracion = Tabla("Valoración financiera por período cerrado", [
        Columna("periodo", "Período"), Columna("metodo", "Método"), Columna("valor", "Valor (COP)", MONEDA),
    ], [{"periodo": f"{v['fecha_inicio']:%d/%m/%Y} a {v['fecha_fin']:%d/%m/%Y}",
         "metodo": "Valor razonable" if v["valor_razonable"] is not None else "Costo",
         "valor": v["valor_razonable"] if v["valor_razonable"] is not None else v["costo"]}
        for v in ctx.fuente.valoracion_por_periodo(activo)])
    predicciones = [_prediccion(p) for p in ctx.fuente.predicciones_activas(fincas=fincas, especie=None,
                                                                            activo=activo, desde=None)]
    seccion_predicciones = Seccion("Predicciones sanitarias activas")
    if predicciones:
        seccion_predicciones.tablas.append(Tabla("Predicciones activas", [
            c for c in _COLUMNAS_PREDICCION if c.clave not in ("id_activo", "sinigan", "especie", "finca")],
            predicciones))
    else:
        seccion_predicciones.textos.append("Sin alertas predictivas activas.")
    vacias = {"Historial productivo": "Sin mediciones productivas en el rango.",
              "Historial sanitario": "Sin eventos sanitarios en el rango.",
              "Suministros aplicados": "Sin suministros registrados en el rango.",
              "Valoración financiera por período cerrado": "Sin valoración en períodos cerrados."}
    secciones = [Seccion("Identificación", [identificacion])]
    for tabla in (historial, tabla_sanitaria, tabla_suministros, valoracion):
        secciones.append(Seccion(tabla.titulo, [tabla] if tabla.filas else [], [] if tabla.filas else
                                 [vacias[tabla.titulo]]))
    secciones.append(seccion_predicciones)
    rango = _rango(ctx) if ctx.filtros.get("fecha_inicio") else f"Desde el ingreso hasta {ctx.filtros['fecha_fin']:%d/%m/%Y}"
    return ContenidoReporte(titulo=ctx.titulo, encabezado=encabezado(ctx, fincas, [("Rango de fechas", rango)]),
                            secciones=secciones, secciones_vista_previa=2)


def vacunacion_medicamentos(ctx: Contexto) -> ContenidoReporte:
    """Arma el reporte de vacunación y medicamentos."""
    fincas = _fincas_filtro(ctx)
    activo, especie = ctx.filtros.get("activo_biologico_id"), ctx.filtros.get("especie_id")
    tipo = ctx.filtros.get("tipo_insumo")
    filas = [f for f in ctx.fuente.medicamentos(fincas=fincas, inicio=ctx.filtros["fecha_inicio"],
                                                fin=ctx.filtros["fecha_fin"], especie=especie, activo=activo)
             if tipo is None or f["tipo_insumo"] == tipo]
    nombres = ctx.fuente.nombres_usuarios([f["id_veterinario"] for f in filas if f["id_veterinario"]])
    detalle = [{
        "nombre": f["nombre"], "tipo": _INSUMOS[f["tipo_insumo"]], "principio": SIN_REGISTRO, "laboratorio": SIN_REGISTRO,
        "lote": f["lote"] or SIN_REGISTRO, "vencimiento": f["vencimiento"] or SIN_REGISTRO, "dosis": f["dosis"],
        "unidad": f["unidad_dosis"] or SIN_REGISTRO, "via": _VIAS.get(f["via"] or "", legible(f["via"])) if f["via"] else SIN_REGISTRO,
        "animales": f["animales"], "tratados": f["identificador"], "fecha": f["fecha_aplicacion"],
        "veterinario": f["veterinario"] or nombres.get(f["id_veterinario"]) or "Sin veterinario registrado",
        "retiro": f["periodo_retiro_dias"] if f["periodo_retiro_dias"] is not None else NO_APLICA, "finca": f["finca"],
    } for f in filas]
    retiros = ctx.fuente.retiros_vigentes(fincas=fincas, hoy=ctx.hoy, especie=especie, activo=activo)
    return ContenidoReporte(
        titulo=ctx.titulo, encabezado=_encabezado_rango(ctx, fincas),
        detalle=Tabla("Vacunas y medicamentos aplicados", [
            Columna("nombre", "Medicamento o vacuna"), Columna("tipo", "Tipo de insumo"),
            Columna("principio", "Principio activo"), Columna("laboratorio", "Laboratorio fabricante"),
            Columna("lote", "Lote del medicamento"), Columna("vencimiento", "Vencimiento del medicamento", FECHA),
            Columna("dosis", "Dosis aplicada", NUMERO), Columna("unidad", "Unidad de dosis"),
            Columna("via", "Vía de administración"), Columna("animales", "Animales tratados", ENTERO),
            Columna("tratados", "Animales o lotes tratados"), Columna("fecha", "Fecha de aplicación", FECHA),
            Columna("veterinario", "Veterinario responsable"), Columna("retiro", "Período de retiro (días)", ENTERO),
            Columna("finca", "Finca"),
        ], detalle),
        finales=[Tabla("Animales en período de retiro", [
            Columna("animal", "Animal o lote"), Columna("especie", "Especie"), Columna("medicamento", "Medicamento"),
            Columna("aplicado", "Aplicado", FECHA), Columna("fin", "Fin del retiro", FECHA), Columna("finca", "Finca"),
        ], [{"animal": r["identificador"], "especie": r["especie"] or SIN_REGISTRO, "medicamento": r["medicamento"],
             "aplicado": r["fecha_aplicacion"], "fin": r["fecha_fin_retiro"], "finca": r["finca"]} for r in retiros],
            nota="No sacrificar estos animales ni comercializar su leche hasta que termine el retiro."
            if retiros else "Ningún animal está en período de retiro a la fecha del reporte.")],
        indicadores=[Indicador("Total de aplicaciones", len(detalle), ENTERO),
                     Indicador("Animales en período de retiro", len({r["identificador"] for r in retiros}), ENTERO)],
    )


def riesgo_sanitario(ctx: Contexto) -> ContenidoReporte:
    """Arma el reporte de riesgo sanitario predicho."""
    fincas = _fincas_filtro(ctx)
    desde = ctx.filtros.get("fecha_prediccion_desde")
    filas = [_prediccion(p) for p in ctx.fuente.predicciones_activas(
        fincas=fincas, especie=ctx.filtros.get("especie_id"), activo=None,
        desde=inicio_dia_usuario(desde) if desde else None)]
    nivel = _NIVEL_FILTRO.get(ctx.filtros.get("nivel_riesgo") or "")
    if nivel is not None:
        filas = [f for f in filas if f["_nivel"] == nivel]
    conteo = {texto: sum(1 for f in filas if f["_nivel"] == n) for n, texto in ((3, "Alto"), (2, "Medio"), (1, "Bajo"))}
    top = sorted(filas, key=lambda f: f["probabilidad"], reverse=True)[:10]
    indicadores = [Indicador(f"Riesgo {k.lower()}", v, ENTERO) for k, v in conteo.items()]
    extra = [("Predicciones desde", f"{desde:%d/%m/%Y}")] if desde else []
    return ContenidoReporte(
        titulo=ctx.titulo, encabezado=encabezado(ctx, fincas, extra),
        resumen=[
            Tabla("Animales por nivel de riesgo", [Columna("nivel", "Nivel"), Columna("animales", "Animales", ENTERO)],
                  [{"nivel": k, "animales": v} for k, v in conteo.items()]),
            Tabla("Los 10 animales con mayor probabilidad de riesgo", [
                Columna("id_activo", "ID activo"), Columna("especie", "Especie"), Columna("nivel", "Nivel"),
                Columna("condicion", "Condición"), Columna("probabilidad", "Probabilidad (%)", PORCENTAJE)], top),
        ],
        detalle=Tabla("Predicciones activas", _COLUMNAS_PREDICCION, filas),
        indicadores=indicadores,
    )


# --- IoT ---------------------------------------------------------------------------------------

def telemetria(ctx: Contexto) -> ContenidoReporte:
    """Arma el reporte de telemetría de un área."""
    variable = ctx.filtros.get("variable_ambiental")
    infra = ctx.filtros["infraestructura_id"]
    filas = ctx.fuente.telemetria(infraestructura=infra, desde=ctx.desde, hasta=ctx.hasta,
                                  sensor=ctx.filtros.get("sensor_id"),
                                  patron_variable=patron_variable(variable.lower()) if variable else None)
    detalle = [{
        "sensor": f["sensor"] or f"Sensor {f['id_sensor']}", "variable": f["variable"] or SIN_REGISTRO,
        "valor": f["valor"], "unidad": f["unidad"] or SIN_REGISTRO, "fecha": f["timestamp_captura"],
        "estado": _DISPOSITIVO.get(f["estado"] or "", "Sin registro de estado"), "area": f["area"], "finca": f["finca"],
    } for f in filas]
    grupos: dict[tuple[str, str], list] = defaultdict(list)
    for d in detalle:
        if d["valor"] is not None:
            grupos[(d["sensor"], d["variable"])].append(_num(d["valor"]))
    estadisticas = [{"sensor": s, "variable": v, "lecturas": len(vals), "promedio": sum(vals) / len(vals),
                     "minimo": min(vals), "maximo": max(vals)} for (s, v), vals in sorted(grupos.items())]
    ubicacion = ctx.fuente.ubicar("infraestructura", infra) or {}
    valores = [v for vals in grupos.values() for v in vals]
    una_variable = len({v for _, v in grupos}) == 1
    indicadores = ([Indicador("Promedio del período", sum(valores) / len(valores), NUMERO),
                    Indicador("Valor mínimo", min(valores), NUMERO), Indicador("Valor máximo", max(valores), NUMERO)]
                   if valores and una_variable else [])
    return ContenidoReporte(
        titulo=ctx.titulo,
        encabezado=_encabezado_rango(ctx, [ubicacion["id_finca"]] if ubicacion.get("id_finca") else ctx.fincas,
                                     ("Área", filas[0]["area"] if filas else "Área seleccionada")),
        resumen=[Tabla("Promedio, mínimo y máximo por sensor", [
            Columna("sensor", "Sensor"), Columna("variable", "Variable"), Columna("lecturas", "Lecturas", ENTERO),
            Columna("promedio", "Promedio", NUMERO), Columna("minimo", "Mínimo", NUMERO),
            Columna("maximo", "Máximo", NUMERO)], estadisticas)],
        detalle=Tabla("Lecturas", [
            Columna("sensor", "Sensor"), Columna("variable", "Variable"), Columna("valor", "Valor medido", NUMERO),
            Columna("unidad", "Unidad"), Columna("fecha", "Fecha y hora de la medición", FECHA_HORA),
            Columna("estado", "Estado del dispositivo"), Columna("area", "Área"), Columna("finca", "Finca"),
        ], detalle),
        indicadores=indicadores,
    )


def estado_dispositivos(ctx: Contexto) -> ContenidoReporte:
    """Arma el reporte del estado de los dispositivos a una fecha de corte."""
    fincas = _fincas_filtro(ctx)
    corte_dia: date = ctx.filtros["fecha_corte"]
    es_hoy = corte_dia >= ctx.hoy
    corte = ctx.generado if es_hoy else fin_dia_usuario(corte_dia)
    filas = ctx.fuente.dispositivos(fincas=fincas, corte=corte, es_hoy=es_hoy,
                                    infraestructura=ctx.filtros.get("infraestructura_id"))
    filtro = _FILTRO_DISPOSITIVO.get(ctx.filtros.get("estado_dispositivo") or "")
    detalle = []
    for f in filas:
        estado = f["estado"] or "DESCONOCIDO"
        if filtro and estado not in filtro:
            continue
        horas = round(_num((corte - f["ultimo_dato"]).total_seconds() / 3600), 1) if f["ultimo_dato"] else None
        detalle.append({
            "id": f["id_dispositivo_iot"], "serial": f["serial"], "tipo": f["tipo"] or SIN_REGISTRO, "area": f["area"],
            "finca": f["finca"], "estado": _DISPOSITIVO.get(estado, legible(estado)),
            "ultimo": f["ultimo_dato"] or "Sin datos recibidos", "horas": horas if horas is not None else "Sin datos",
            "desconexiones": f["desconexiones"] or 0, "instalacion": f["instalacion"],
            "mantenimiento": f["mantenimiento"] or "Sin mantenimiento registrado",
            "revision": "Sin revisión programada", "firmware": f["version_firmware"] or SIN_REGISTRO,
            "_horas": horas,
        })
    conteo: dict[tuple[str, str], int] = defaultdict(int)
    for d in detalle:
        conteo[(d["finca"], d["estado"])] += 1
    prioritarios = [d for d in detalle if d["_horas"] is None or d["_horas"] > HORAS_PRIORITARIO]
    activos = sum(1 for d in detalle if d["estado"] in (_DISPOSITIVO["ACTIVO"], _DISPOSITIVO["BUFFER_ACTIVO"]))
    mantenimiento = sum(1 for d in detalle if d["estado"] == _DISPOSITIVO["EN_MANTENIMIENTO"])
    return ContenidoReporte(
        titulo=ctx.titulo, encabezado=encabezado(ctx, fincas, [("Fecha de corte", f"{corte_dia:%d/%m/%Y}")]),
        indicadores=[Indicador("Activos", activos, ENTERO),
                     Indicador("Inactivos, sin señal o en falla", len(detalle) - activos - mantenimiento, ENTERO),
                     Indicador("En mantenimiento", mantenimiento, ENTERO)],
        resumen=[
            Tabla("Dispositivos por estado y finca", [Columna("finca", "Finca"), Columna("estado", "Estado"),
                                                      Columna("total", "Dispositivos", ENTERO)],
                  [{"finca": fi, "estado": e, "total": t} for (fi, e), t in sorted(conteo.items())]),
            Tabla(f"Prioritarios: más de {HORAS_PRIORITARIO} horas sin enviar datos", [
                Columna("serial", "Serial"), Columna("area", "Área"), Columna("finca", "Finca"),
                Columna("horas", "Horas sin señal", NUMERO)], prioritarios),
        ],
        detalle=Tabla("Dispositivos", [
            Columna("id", "Dispositivo", ENTERO), Columna("serial", "Serial"), Columna("tipo", "Tipo de dispositivo"),
            Columna("area", "Área asignada"), Columna("finca", "Finca"), Columna("estado", "Estado"),
            Columna("ultimo", "Último dato recibido", FECHA_HORA), Columna("horas", "Horas sin señal", NUMERO),
            Columna("desconexiones", "Desconexiones (30 días)", ENTERO), Columna("instalacion", "Instalación", FECHA_HORA),
            Columna("mantenimiento", "Último mantenimiento", FECHA_HORA), Columna("revision", "Próxima revisión"),
            Columna("firmware", "Versión de firmware"),
        ], detalle),
    )


def calibracion_sensores(ctx: Contexto) -> ContenidoReporte:
    """Arma el reporte de calibración de sensores."""
    fincas = _fincas_filtro(ctx)
    sensor, infra = ctx.filtros.get("sensor_id"), ctx.filtros.get("infraestructura_id")
    filas = ctx.fuente.calibraciones(fincas=fincas, desde=ctx.desde, hasta=ctx.hasta, sensor=sensor,
                                     infraestructura=infra)
    nombres = ctx.fuente.nombres_usuarios([f["id_usuario"] for f in filas if f["id_usuario"]])
    detalle = [{
        "id": f["id_dispositivo_iot"], "serial": f["serial"], "sensor": f["sensor"] or SIN_REGISTRO,
        "variable": legible(f["variable"]), "fecha": f["fecha_calibracion"],
        "antes": f["antes"] if f["antes"] is not None else "Primera calibración", "despues": f["despues"],
        "ajuste": f"Ganancia {f['ganancia'] if f['ganancia'] is not None else 'sin cambio'} · "
                  f"desfase {f['offset_calibracion'] if f['offset_calibracion'] is not None else 'sin cambio'}",
        "unidad": f["unidad"] or SIN_REGISTRO, "ingeniero": nombres.get(f["id_usuario"]) or SIN_REGISTRO,
        "observaciones": f["observaciones"] or "Sin observaciones", "area": f["area"], "finca": f["finca"],
    } for f in filas]
    pendientes = ctx.fuente.sensores_sin_calibrar(
        fincas=fincas, antes_de=ctx.generado - timedelta(days=DIAS_SIN_CALIBRAR), sensor=sensor, infraestructura=infra)
    return ContenidoReporte(
        titulo=ctx.titulo, encabezado=_encabezado_rango(ctx, fincas),
        detalle=Tabla("Calibraciones", [
            Columna("id", "Dispositivo", ENTERO), Columna("serial", "Serial"), Columna("sensor", "Sensor"),
            Columna("variable", "Variable que mide"), Columna("fecha", "Fecha de calibración", FECHA_HORA),
            Columna("antes", "Valor de referencia antes", NUMERO), Columna("despues", "Valor de referencia después", NUMERO),
            Columna("ajuste", "Ajuste aplicado"), Columna("unidad", "Unidad"), Columna("ingeniero", "Ingeniero responsable"),
            Columna("observaciones", "Observaciones"), Columna("area", "Área asignada"), Columna("finca", "Finca"),
        ], detalle),
        finales=[Tabla(f"Sensores sin calibrar en más de {DIAS_SIN_CALIBRAR} días (pendientes de revisión)", [
            Columna("serial", "Serial"), Columna("sensor", "Sensor"), Columna("variable", "Variable"),
            Columna("ultima", "Última calibración", FECHA_HORA), Columna("area", "Área"), Columna("finca", "Finca"),
        ], [{"serial": p["serial"], "sensor": p["sensor"] or SIN_REGISTRO, "variable": legible(p["variable"]),
             "ultima": p["ultima"] or "Nunca calibrado", "area": p["area"], "finca": p["finca"]} for p in pendientes])],
    )


def _tipo_alerta(f: dict) -> str:
    if f["tipo_alerta"] == "TECNICA":
        return "DESCONEXION" if (f["tipo_variable"] or "") in _DESCONEXION else "FALLO_DISPOSITIVO"
    return "FUERA_DE_RANGO"


def alertas_sensores(ctx: Contexto) -> ContenidoReporte:
    """Arma el reporte de alertas de sensores."""
    fincas = _fincas_filtro(ctx)
    filas = ctx.fuente.alertas_sensores(fincas=fincas, desde=ctx.desde, hasta=ctx.hasta,
                                        infraestructura=ctx.filtros.get("infraestructura_id"))
    tipo, severidad = ctx.filtros.get("tipo_alerta"), ctx.filtros.get("nivel_severidad")
    detalle = []
    for f in filas:
        clase, nivel = _tipo_alerta(f), _SEVERIDAD.get(f["severidad"] or "", "INFORMATIVA")
        if (tipo and clase != tipo) or (severidad and nivel != severidad):
            continue
        umbral = (f"{f['umbral_min']} a {f['umbral_max']}" if f["umbral_min"] is not None or f["umbral_max"] is not None
                  else NO_APLICA)
        resuelta = f["estado"] in ("RESUELTA", "DESCARTADA", "VENCIDA")
        detalle.append({
            "id": f["id_alerta"], "dispositivo": f["id_dispositivo_iot"] or NO_APLICA,
            "serial": f["serial"] or SIN_REGISTRO, "tipo": _ALERTA[clase],
            "variable": legible(f["tipo_variable"]) if f["tipo_variable"] else SIN_REGISTRO,
            "valor": f["valor"] if f["valor"] is not None else NO_APLICA, "umbral": umbral, "fecha": f["fecha"],
            "duracion": round(_num(f["duracion_min"]), 1) if clase == "DESCONEXION" and f["duracion_min"] is not None
            else NO_APLICA,
            "estado": "Resuelta" if resuelta else "Pendiente",
            "resolucion": f["fecha_resolucion"] or ("Sin fecha registrada" if resuelta else NO_APLICA),
            "accion": f["accion"] or "Sin acción registrada", "severidad": _SEVERIDAD_TEXTO[nivel],
            "area": f["area"], "finca": f["finca"],
        })
    por_dispositivo: dict[str, int] = defaultdict(int)
    por_clase: dict[tuple[str, str], int] = defaultdict(int)
    for d in detalle:
        por_dispositivo[d["serial"]] += 1
        por_clase[(d["tipo"], d["severidad"])] += 1
    ranking = sorted(por_dispositivo.items(), key=lambda x: x[1], reverse=True)[:5]
    por_severidad: dict[str, int] = defaultdict(int)
    for d in detalle:
        por_severidad[d["severidad"]] += 1
    return ContenidoReporte(
        titulo=ctx.titulo, encabezado=_encabezado_rango(ctx, fincas),
        indicadores=[Indicador(f"Alertas {texto.lower()}s" if texto != "Advertencia" else "Alertas de advertencia",
                               por_severidad.get(texto, 0), ENTERO)
                     for texto in ("Crítica", "Advertencia", "Informativa")],
        resumen=[
            Tabla("Los 5 dispositivos con más alertas", [Columna("serial", "Serial"),
                                                          Columna("alertas", "Alertas", ENTERO)],
                  [{"serial": s, "alertas": n} for s, n in ranking]),
            Tabla("Alertas por tipo y severidad", [Columna("tipo", "Tipo"), Columna("severidad", "Severidad"),
                                                   Columna("total", "Alertas", ENTERO)],
                  [{"tipo": t, "severidad": s, "total": n} for (t, s), n in sorted(por_clase.items())]),
        ],
        detalle=Tabla("Alertas", [
            Columna("id", "Alerta", ENTERO), Columna("serial", "Serial del dispositivo"), Columna("tipo", "Tipo de alerta"),
            Columna("variable", "Variable afectada"), Columna("valor", "Valor detectado", NUMERO),
            Columna("umbral", "Umbral configurado"), Columna("fecha", "Fecha de la alerta", FECHA_HORA),
            Columna("duracion", "Duración (minutos)", NUMERO), Columna("estado", "Estado"),
            Columna("resolucion", "Resuelta el", FECHA_HORA), Columna("accion", "Acción tomada"),
            Columna("severidad", "Severidad"), Columna("area", "Área asignada"), Columna("finca", "Finca"),
        ], detalle),
    )


# --- Gerenciales: solo totales (RNF-11) --------------------------------------------------------

_SEMAFORO = {"VERDE": "Verde: el último cierre se exportó correctamente",
             "AMARILLO": "Amarillo: el último cierre aún no se ha exportado",
             "ROJO": "Rojo: la exportación del último cierre tuvo errores"}


def _semaforo_exportacion(ctx: Contexto, nit: Optional[str], hasta: date) -> str:
    cierre = ctx.fuente.ultimo_periodo_cerrado(nit=nit, hasta=hasta) if nit else None
    if cierre is None:
        return "Sin períodos cerrados"
    estados = {e["estado"] for e in ctx.fuente.exportaciones(cierre["id_periodo_contable"])}
    clave = "VERDE" if "SUCCESS" in estados else ("ROJO" if estados else "AMARILLO")
    return f"{_SEMAFORO[clave]} ({cierre['fecha_inicio']:%d/%m/%Y} a {cierre['fecha_fin']:%d/%m/%Y})"


def _riesgo(filas: list[dict], fuente: str) -> dict[str, int]:
    conteo: dict[str, int] = defaultdict(int)
    for f in filas:
        if f["fuente"] == fuente:
            conteo[_nivel(f["nivel_riesgo"])] += f["total"]
    return conteo


def ejecutivo_consolidado(ctx: Contexto) -> ContenidoReporte:
    """Arma el reporte ejecutivo consolidado del periodo."""
    periodo = ctx.periodos["periodo_contable"]
    fincas = _fincas_periodo(ctx, periodo)
    inicio, fin = periodo["fecha_inicio"], periodo["fecha_fin"]
    desde, hasta = inicio_dia_usuario(inicio), fin_dia_usuario(fin)
    f = ctx.fuente
    cierre = f.ultimo_periodo_cerrado(nit=periodo["nit"], hasta=fin) if periodo.get("nit") else None
    # USAB2 M807: el valor del portafolio sale del mismo cálculo que la valoración NIC 41 del período cerrado.
    valor = f.valor_portafolio_periodo(id_periodo=cierre["id_periodo_contable"], fincas=fincas) if cierre else []
    riesgo = f.riesgo_por_nivel(fincas=fincas, desde=desde, hasta=hasta)
    estados = defaultdict(lambda: [0, 0])
    for d in f.dispositivos_por_estado(fincas=fincas):
        estados[d["finca"]][0 if d["estado"] in ("ACTIVO", "BUFFER_ACTIVO") else 1] += d["total"]
    secciones = [
        Seccion("1. Inventario", [
            Tabla("Animales activos por especie y finca", [Columna("finca", "Finca"), Columna("especie", "Especie"),
                                                           Columna("animales", "Animales", ENTERO)],
                  [{"finca": a["finca"], "especie": a["especie"] or SIN_REGISTRO, "animales": a["animales"]}
                   for a in f.animales_por_especie(fincas=fincas, fin=fin)]),
            Tabla("Valor del portafolio de activos biológicos", [Columna("finca", "Finca"),
                                                                Columna("valor", "Valor (COP)", MONEDA)],
                  [{"finca": v["finca"], "valor": v["valor"] or 0} for v in valor]
                  + [{"finca": "Total", "valor": _sumar(valor, "valor")}],
                  nota=(f"Último período cerrado: {cierre['fecha_inicio']:%d/%m/%Y} a {cierre['fecha_fin']:%d/%m/%Y}."
                        if cierre else "Todavía no hay períodos cerrados.")),
            Tabla("Bajas y salidas del período", [Columna("tipo", "Tipo"), Columna("animales", "Animales", ENTERO)],
                  _agrupar(f.bajas_por_tipo(fincas=fincas, desde=desde, hasta=hasta), "tipo", "animales",
                           lambda t: _SALIDAS.get(t, legible(t)))),
        ]),
        Seccion("2. Costos", [Tabla("Costo de suministros por tipo y finca", [
            Columna("finca", "Finca"), Columna("tipo", "Tipo"), Columna("costo", "Costo (COP)", MONEDA)],
            [{"finca": c["finca"], "tipo": _SUMINISTROS[c["tipo"]], "costo": c["costo"]}
             for c in f.costos_por_tipo(fincas=fincas, inicio=inicio, fin=fin)])]),
        Seccion("3. Salud del hato", [
            Tabla("Eventos sanitarios del período por nivel de riesgo", [
                Columna("nivel", "Nivel de riesgo"), Columna("total", "Eventos", ENTERO)],
                [{"nivel": k, "total": v} for k, v in sorted(_riesgo(riesgo, "M02").items())]),
            Tabla("Animales con predicción de riesgo activa", [Columna("nivel", "Nivel de riesgo"),
                                                               Columna("animales", "Animales", ENTERO)],
                  _agrupar(f.animales_con_riesgo_activo(fincas=fincas), "nivel_riesgo", "animales", _nivel)),
        ]),
        Seccion("4. Infraestructura IoT", [Tabla("Dispositivos por finca", [
            Columna("finca", "Finca"), Columna("activos", "Activos", ENTERO),
            Columna("otros", "Inactivos o en falla", ENTERO)],
            [{"finca": k, "activos": v[0], "otros": v[1]} for k, v in sorted(estados.items())])]),
        Seccion("5. Exportación contable", [], [_semaforo_exportacion(ctx, periodo.get("nit"), fin)]),
    ]
    return ContenidoReporte(
        titulo=ctx.titulo,
        encabezado=encabezado(ctx, fincas, [("Período contable", f"{_periodo_texto(periodo)} "
                                                                 f"({'cerrado' if periodo['estado'] == 'CERRADO' else 'abierto'})")]),
        secciones=secciones,
        aclaraciones=["Este reporte muestra solo totales: no incluye valoraciones por animal, diagnósticos "
                      "individuales ni datos de la exportación contable."],
    )


def _agrupar(filas: list[dict], clave: str, valor: str, texto: Callable[[Any], str]) -> list[dict]:
    total: dict[str, int] = defaultdict(int)
    for f in filas:
        total[texto(f[clave])] += f[valor]
    return [{"tipo" if clave == "tipo" else "nivel": k, valor: v} for k, v in sorted(total.items())]


def rentabilidad_finca(ctx: Contexto) -> ContenidoReporte:
    """Arma el reporte de rentabilidad por finca del periodo."""
    periodo = ctx.periodos["periodo_contable"]
    fincas = _fincas_periodo(ctx, periodo)
    inicio, fin = periodo["fecha_inicio"], periodo["fecha_fin"]
    desde, hasta = inicio_dia_usuario(inicio), fin_dia_usuario(fin)
    f = ctx.fuente
    filas: dict[str, dict[str, Any]] = {}

    def fila(nombre: str) -> dict[str, Any]:
        return filas.setdefault(nombre, {"finca": nombre, "animales": 0, "bajas": 0, "valor": Decimal(0),
                                         "costo": Decimal(0), "alto_riesgo": 0, "activos": 0, "falla": 0})

    for nombre in (x["nombre"] for x in f.fincas(fincas)):
        fila(nombre)
    for a in f.animales_por_especie(fincas=fincas, fin=fin):
        fila(a["finca"])["animales"] += a["animales"]
    for b in f.bajas_por_tipo(fincas=fincas, desde=desde, hasta=hasta):
        fila(b["finca"])["bajas"] += b["animales"]
    for v in f.valor_portafolio(fincas=fincas, fin=fin):
        fila(v["finca"])["valor"] += _num(v["valor"])
    for c in f.costos_por_tipo(fincas=fincas, inicio=inicio, fin=fin):
        fila(c["finca"])["costo"] += _num(c["costo"])
    for r in f.riesgo_por_nivel(fincas=fincas, desde=desde, hasta=hasta):
        if r["nivel_riesgo"] == 3:
            fila(r["finca"])["alto_riesgo"] += r["total"]
    for d in f.dispositivos_por_estado(fincas=fincas):
        fila(d["finca"])["activos" if d["estado"] in ("ACTIVO", "BUFFER_ACTIVO") else "falla"] += d["total"]
    detalle = [{**x, "margen": x["valor"] - x["costo"]} for x in sorted(filas.values(), key=lambda x: x["finca"])]
    margen_total = _sumar(detalle, "margen")
    return ContenidoReporte(
        titulo=ctx.titulo, encabezado=encabezado(ctx, fincas, [("Período contable", _periodo_texto(periodo))]),
        detalle=Tabla("Rentabilidad por finca", [
            Columna("finca", "Finca"), Columna("animales", "Animales activos", ENTERO),
            Columna("bajas", "Animales dados de baja", ENTERO), Columna("valor", "Valor del inventario (COP)", MONEDA),
            Columna("costo", "Costo de suministros (COP)", MONEDA),
            Columna("margen", "Margen bruto estimado (COP)", MONEDA),
            Columna("alto_riesgo", "Eventos sanitarios de riesgo alto", ENTERO),
            Columna("activos", "Dispositivos IoT activos", ENTERO), Columna("falla", "Dispositivos IoT en falla", ENTERO),
        ], detalle),
        indicadores=[
            Indicador("Margen bruto total", margen_total, MONEDA),
            Indicador("Finca más rentable", max(detalle, key=lambda x: x["margen"])["finca"] if detalle else "Sin fincas"),
            Indicador("Margen promedio por finca", margen_total / len(detalle) if detalle else Decimal(0), MONEDA),
        ],
        aclaraciones=["El margen bruto estimado es un indicador de gestión interna calculado por el sistema "
                      "(valor del inventario menos costo de suministros) y no constituye un estado financiero "
                      "certificado. Para efectos contables y legales, el Contador debe generar el reporte de "
                      "valoración NIC 41."],
    )


def _indicadores(ctx: Contexto, periodo: dict, fincas: list[int]) -> dict[str, Decimal]:
    f = ctx.fuente
    inicio, fin = periodo["fecha_inicio"], periodo["fecha_fin"]
    desde, hasta = inicio_dia_usuario(inicio), fin_dia_usuario(fin)
    valores: dict[str, Decimal] = defaultdict(Decimal)
    for a in f.animales_por_especie(fincas=fincas, fin=fin):
        valores[f"Animales activos · {a['especie'] or SIN_REGISTRO}"] += _num(a["animales"])
    valores["Valor total del inventario (COP)"] += _sumar(f.valor_portafolio(fincas=fincas, fin=fin), "valor")
    valores["Costo total de suministros (COP)"] += _sumar(f.costos_por_tipo(fincas=fincas, inicio=inicio, fin=fin),
                                                          "costo")
    for b in f.bajas_por_tipo(fincas=fincas, desde=desde, hasta=hasta):
        valores[f"Bajas · {_SALIDAS.get(b['tipo'], legible(b['tipo']))}"] += _num(b["animales"])
    for nivel, total in _riesgo(f.riesgo_por_nivel(fincas=fincas, desde=desde, hasta=hasta), "M02").items():
        valores[f"Eventos sanitarios · riesgo {nivel.lower()}"] += total
    if ctx.incluir_nic41:
        valores["Variación del valor razonable NIC 41 (COP)"] += _num(
            f.variacion_total_periodo(id_periodo=periodo["id_periodo_contable"], fincas=fincas))
    return valores


def comparativo_periodos(ctx: Contexto) -> ContenidoReporte:
    """Arma el reporte comparativo entre dos periodos."""
    base, comp = ctx.periodos["periodo_contable_base"], ctx.periodos["periodo_contable_comparacion"]
    fincas = _fincas_periodo(ctx, base)
    v_base, v_comp = _indicadores(ctx, base, fincas), _indicadores(ctx, comp, fincas)
    detalle = []
    for indicador in sorted(set(v_base) | set(v_comp)):
        b, c = v_base.get(indicador, Decimal(0)), v_comp.get(indicador, Decimal(0))
        detalle.append({"indicador": indicador, "base": b, "comparacion": c, "variacion": b - c,
                        "porcentaje": (b - c) / c * 100 if c else NO_APLICA})
    con_cambio = [d for d in detalle if d["variacion"]]
    crece = max(con_cambio, key=lambda d: d["variacion"], default=None)
    cae = min(con_cambio, key=lambda d: d["variacion"], default=None)
    return ContenidoReporte(
        titulo=ctx.titulo,
        encabezado=encabezado(ctx, fincas, [("Período base", _periodo_texto(base)),
                                            ("Período de comparación", _periodo_texto(comp))]),
        detalle=Tabla("Indicadores", [
            Columna("indicador", "Indicador"), Columna("base", "Período base", NUMERO),
            Columna("comparacion", "Período de comparación", NUMERO), Columna("variacion", "Variación absoluta", NUMERO),
            Columna("porcentaje", "Variación (%)", PORCENTAJE),
        ], detalle),
        indicadores=[
            Indicador("Indicador con mayor crecimiento",
                      crece["indicador"] if crece and crece["variacion"] > 0 else "Ningún indicador creció"),
            Indicador("Indicador con mayor caída",
                      cae["indicador"] if cae and cae["variacion"] < 0 else "Ningún indicador cayó"),
        ],
    )


ARMADORES: dict[str, Callable[[Contexto], ContenidoReporte]] = {
    "REPORTE_INVENTARIO_BIOLOGICO": inventario,
    "REPORTE_COSTOS_SUMINISTROS": costos_suministros,
    "REPORTE_PRODUCTIVIDAD": productividad,
    "REPORTE_BAJAS_Y_SALIDAS": bajas_y_salidas,
    "REPORTE_VALORACION_NIC41": valoracion_nic41,
    "REPORTE_ESTADO_EXPORTACIONES": estado_exportaciones,
    "REPORTE_VARIACION_PERIODOS": variacion_periodos,
    "REPORTE_HISTORICO_SANITARIO": historico_sanitario,
    "REPORTE_FICHA_ANIMAL": ficha_animal,
    "REPORTE_VACUNACION_MEDICAMENTOS": vacunacion_medicamentos,
    "REPORTE_RIESGO_SANITARIO": riesgo_sanitario,
    "REPORTE_TELEMETRIA": telemetria,
    "REPORTE_ESTADO_DISPOSITIVOS": estado_dispositivos,
    "REPORTE_CALIBRACION_SENSORES": calibracion_sensores,
    "REPORTE_ALERTAS_SENSORES": alertas_sensores,
    "REPORTE_EJECUTIVO_CONSOLIDADO": ejecutivo_consolidado,
    "REPORTE_RENTABILIDAD_FINCA": rentabilidad_finca,
    "REPORTE_COMPARATIVO_PERIODOS": comparativo_periodos,
}
