# | Fecha      | Nombre   | Que se hizo                                                  |
# |------------|----------|--------------------------------------------------------------|
# | 2026-11-18 | Arekkazu | M08 RF-104: catálogo de los 18 reportes, filtros y validación |
# | 2026-11-19 | Arekkazu | M08 RF-104: textos de los valores y de los filtros sin elegir, para el PDF |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Catálogo de reportes de RF-104: qué filtros pide cada uno y cómo se validan.

Cada tipo tiene su recurso RBAC (``reporte_<tipo>``, acción Ejecutar): quién lo genera se decide en
``modulo1.permisos``, no aquí. «Gerencia» no es un rol: sus reportes los genera quien tenga el permiso
(el Productor como dueño de la finca, migración ``a7c3e91f5b20``).

Los nombres de filtro y los valores de las listas son claves estables que el front traduce; el título
y las etiquetas sí se muestran (en el PDF y en los mensajes de validación).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Optional

from src.shared.errors import ValidationError

# Tipos de filtro. Los de referencia (finca, activo…) se validan contra las fincas del usuario.
FECHA, LISTA = "fecha", "lista"
FINCA, ESPECIE, ACTIVO, LOTE, INFRAESTRUCTURA, SENSOR, PERIODO = (
    "finca", "especie", "activo", "lote", "infraestructura", "sensor", "periodo")
_REFERENCIAS = (FINCA, ESPECIE, ACTIVO, LOTE, INFRAESTRUCTURA, SENSOR, PERIODO)

# Hasta 1.000 registros se genera al momento; por encima, en segundo plano (RF-104 Fase 3).
LIMITE_SINCRONO = 1000
# La telemetría crece ~10.000 lecturas por sensor al mes y el reporte se arma en memoria: un mes por reporte.
MAX_DIAS_TELEMETRIA = 31
FILAS_VISTA_PREVIA = 20


@dataclass(frozen=True)
class Filtro:
    """Filtro aceptado por un reporte."""
    nombre: str
    tipo: str
    obligatorio: bool = False
    valores: tuple = ()


@dataclass(frozen=True)
class DefinicionReporte:
    """``periodo_cerrado``: los períodos del reporte deben estar CERRADOS (422 si no).
    ``compara_periodos``: el de comparación debe ser anterior al base (422 si no)."""
    tipo: str
    titulo: str
    filtros: tuple[Filtro, ...]
    periodo_cerrado: bool = False
    compara_periodos: bool = False

    @property
    def recurso(self) -> str:
        """Nombre del recurso RBAC del reporte."""
        return self.tipo.lower()

    def filtro(self, nombre: str) -> Optional[Filtro]:
        """Devuelve el filtro por nombre, o ``None``."""
        return next((f for f in self.filtros if f.nombre == nombre), None)


ETIQUETAS = {
    "fecha_inicio": "Fecha de inicio", "fecha_fin": "Fecha de fin", "fecha_corte": "Fecha de corte",
    "fecha_prediccion_desde": "Predicciones desde", "especie_id": "Especie", "finca_id": "Finca",
    "activo_biologico_id": "Animal o lote", "lote_id": "Lote", "infraestructura_id": "Área",
    "sensor_id": "Sensor", "periodo_contable": "Período contable",
    "periodo_contable_base": "Período base", "periodo_contable_comparacion": "Período de comparación",
    "estado_activo": "Estado", "tipo_suministro": "Tipo de suministro", "tipo_salida": "Tipo de salida",
    "tipo_evento": "Tipo de evento", "nivel_riesgo": "Nivel de riesgo", "tipo_insumo": "Tipo de insumo",
    "variable_ambiental": "Variable", "estado_dispositivo": "Estado del dispositivo",
    "tipo_alerta": "Tipo de alerta", "nivel_severidad": "Severidad",
}

# Cómo se lee cada valor de lista en «Parámetros de selección» del PDF y del Excel.
TEXTO_VALORES = {
    "ACTIVO": "Activo", "VENDIDO": "Vendido", "MUERTO": "Muerto", "ALIMENTACION": "Alimentación",
    "MEDICACION": "Medicación", "OTROS": "Otros", "MUERTE": "Muerte", "VENTA": "Venta", "SACRIFICIO": "Sacrificio",
    "TRASLADO": "Traslado", "DIAGNOSTICO": "Diagnóstico", "VACUNACION": "Vacunación", "TRATAMIENTO": "Tratamiento",
    "ALTO": "Alto", "MEDIO": "Medio", "BAJO": "Bajo", "VACUNA": "Vacuna", "MEDICAMENTO": "Medicamento",
    "ANTIPARASITARIO": "Antiparasitario", "TEMPERATURA": "Temperatura", "HUMEDAD": "Humedad", "PH": "pH",
    "CO2": "CO2", "INACTIVO": "Inactivo", "FALLO": "Falla", "SIN_SEÑAL": "Sin señal",
    "MANTENIMIENTO": "En mantenimiento", "FUERA_DE_RANGO": "Fuera de rango", "DESCONEXION": "Desconexión",
    "FALLO_DISPOSITIVO": "Falla del dispositivo", "CRITICA": "Crítica", "ADVERTENCIA": "Advertencia",
    "INFORMATIVA": "Informativa",
}

# Qué dice un filtro que no se eligió.
SIN_ELEGIR = {"especie_id": "Todas", "finca_id": "Todas", "infraestructura_id": "Todas",
              "fecha_inicio": "Desde el primer registro", "fecha_prediccion_desde": "Últimos 7 días"}

_INICIO, _FIN = Filtro("fecha_inicio", FECHA, True), Filtro("fecha_fin", FECHA, True)
_ESPECIE, _FINCA = Filtro("especie_id", ESPECIE), Filtro("finca_id", FINCA)
_INFRA = Filtro("infraestructura_id", INFRAESTRUCTURA)
_PERIODO = Filtro("periodo_contable", PERIODO, True)
_BASE = Filtro("periodo_contable_base", PERIODO, True)
_COMPARACION = Filtro("periodo_contable_comparacion", PERIODO, True)
_NIVEL_RIESGO = ("ALTO", "MEDIO", "BAJO")


def _d(tipo: str, titulo: str, *filtros: Filtro, cerrado: bool = False, compara: bool = False) -> DefinicionReporte:
    return DefinicionReporte(tipo, titulo, filtros, cerrado, compara)


CATALOGO: dict[str, DefinicionReporte] = {d.tipo: d for d in (
    _d("REPORTE_INVENTARIO_BIOLOGICO", "Inventario biológico", _INICIO, _FIN, _ESPECIE,
       Filtro("estado_activo", LISTA, valores=("ACTIVO", "VENDIDO", "MUERTO", "TODOS")), _FINCA),
    _d("REPORTE_COSTOS_SUMINISTROS", "Costos de suministros", _INICIO, _FIN, _ESPECIE,
       Filtro("tipo_suministro", LISTA, valores=("ALIMENTACION", "MEDICACION", "OTROS")), _FINCA),
    _d("REPORTE_PRODUCTIVIDAD", "Productividad", _INICIO, _FIN, _ESPECIE, _FINCA, Filtro("lote_id", LOTE)),
    _d("REPORTE_BAJAS_Y_SALIDAS", "Bajas y salidas del inventario", _INICIO, _FIN, _ESPECIE,
       Filtro("tipo_salida", LISTA, valores=("MUERTE", "VENTA", "SACRIFICIO", "TRASLADO", "TODOS")), _FINCA),
    _d("REPORTE_VALORACION_NIC41", "Valoración NIC 41", _PERIODO, cerrado=True),
    _d("REPORTE_ESTADO_EXPORTACIONES", "Estado de las exportaciones contables", _PERIODO, cerrado=True),
    _d("REPORTE_VARIACION_PERIODOS", "Variación de la valoración entre períodos", _BASE, _COMPARACION,
       cerrado=True, compara=True),
    _d("REPORTE_HISTORICO_SANITARIO", "Histórico sanitario", _INICIO, _FIN,
       Filtro("activo_biologico_id", ACTIVO), _ESPECIE,
       Filtro("tipo_evento", LISTA, valores=("DIAGNOSTICO", "VACUNACION", "TRATAMIENTO", "TODOS")),
       Filtro("nivel_riesgo", LISTA, valores=_NIVEL_RIESGO)),
    _d("REPORTE_FICHA_ANIMAL", "Ficha del animal", Filtro("activo_biologico_id", ACTIVO, True),
       Filtro("fecha_inicio", FECHA), Filtro("fecha_fin", FECHA)),
    _d("REPORTE_VACUNACION_MEDICAMENTOS", "Vacunación y medicamentos", _INICIO, _FIN, _ESPECIE,
       Filtro("tipo_insumo", LISTA, valores=("VACUNA", "MEDICAMENTO", "ANTIPARASITARIO", "TODOS")),
       Filtro("activo_biologico_id", ACTIVO), _FINCA),
    _d("REPORTE_RIESGO_SANITARIO", "Riesgo sanitario", _ESPECIE,
       Filtro("nivel_riesgo", LISTA, valores=_NIVEL_RIESGO + ("TODOS",)), _FINCA,
       Filtro("fecha_prediccion_desde", FECHA)),
    _d("REPORTE_TELEMETRIA", "Telemetría", _INICIO, _FIN, Filtro("infraestructura_id", INFRAESTRUCTURA, True),
       Filtro("sensor_id", SENSOR),
       Filtro("variable_ambiental", LISTA, valores=("TEMPERATURA", "HUMEDAD", "PH", "CO2", "TODOS"))),
    _d("REPORTE_ESTADO_DISPOSITIVOS", "Estado de los dispositivos", Filtro("fecha_corte", FECHA), _INFRA,
       Filtro("estado_dispositivo", LISTA,
              valores=("ACTIVO", "INACTIVO", "FALLO", "SIN_SEÑAL", "MANTENIMIENTO", "TODOS")), _FINCA),
    _d("REPORTE_CALIBRACION_SENSORES", "Calibración de sensores", _INICIO, _FIN, Filtro("sensor_id", SENSOR),
       _INFRA),
    _d("REPORTE_ALERTAS_SENSORES", "Alertas de sensores", _INICIO, _FIN,
       Filtro("tipo_alerta", LISTA, valores=("FUERA_DE_RANGO", "DESCONEXION", "FALLO_DISPOSITIVO", "TODOS")),
       _INFRA, Filtro("nivel_severidad", LISTA, valores=("CRITICA", "ADVERTENCIA", "INFORMATIVA"))),
    _d("REPORTE_EJECUTIVO_CONSOLIDADO", "Reporte ejecutivo consolidado", _PERIODO, _FINCA),
    _d("REPORTE_RENTABILIDAD_FINCA", "Rentabilidad por finca", _PERIODO, _FINCA, cerrado=True),
    _d("REPORTE_COMPARATIVO_PERIODOS", "Comparativo de períodos", _BASE, _COMPARACION, cerrado=True, compara=True),
)}


def _invalido(nombre: str, mensaje: Optional[str] = None) -> ValidationError:
    etiqueta = ETIQUETAS.get(nombre, nombre)
    return ValidationError(code="VAL_ENTRADA", message=mensaje or f"El valor de «{etiqueta}» no es válido.",
                           field=f"filtros.{nombre}")


def _fecha(nombre: str, valor: Any) -> date:
    if isinstance(valor, date):
        return valor
    try:
        return date.fromisoformat(str(valor))
    except ValueError as exc:
        raise _invalido(nombre, f"«{ETIQUETAS[nombre]}» debe ser una fecha (AAAA-MM-DD).") from exc


def validar_filtros(definicion: DefinicionReporte, crudos: Optional[dict[str, Any]], hoy: date) -> dict[str, Any]:
    """Filtros tipados: fechas como ``date``, referencias como enteros positivos, listas dentro de su catálogo.

    Filtro desconocido, valor fuera de su tipo o lista, u obligatorio ausente → 400 (FA de validación).
    La fecha de corte de dispositivos y el fin de la ficha del animal toman «hoy» si no llegan; un filtro
    de lista ``TODOS`` equivale a no filtrar. Que las referencias sean del usuario lo valida el caso de uso.
    """
    crudos = {k: v for k, v in (crudos or {}).items() if v not in (None, "")}
    desconocidos = set(crudos) - {f.nombre for f in definicion.filtros}
    if desconocidos:
        raise _invalido(sorted(desconocidos)[0], "Uno de los filtros no corresponde a este reporte.")
    limpios: dict[str, Any] = {}
    for filtro in definicion.filtros:
        valor = crudos.get(filtro.nombre)
        if valor is None:
            if filtro.obligatorio:
                raise ValidationError(code="VAL_ENTRADA", field=f"filtros.{filtro.nombre}",
                                      message=f"Falta el filtro «{ETIQUETAS[filtro.nombre]}».")
            continue
        if filtro.tipo == FECHA:
            limpios[filtro.nombre] = _fecha(filtro.nombre, valor)
        elif filtro.tipo in _REFERENCIAS:
            if isinstance(valor, bool) or not isinstance(valor, int) or valor <= 0:
                raise _invalido(filtro.nombre)
            limpios[filtro.nombre] = valor
        elif valor in filtro.valores:
            if valor != "TODOS":
                limpios[filtro.nombre] = valor
        else:
            raise _invalido(filtro.nombre)

    if definicion.tipo == "REPORTE_ESTADO_DISPOSITIVOS":
        limpios.setdefault("fecha_corte", hoy)
    if definicion.tipo == "REPORTE_FICHA_ANIMAL":
        limpios.setdefault("fecha_fin", hoy)
    inicio, fin = limpios.get("fecha_inicio"), limpios.get("fecha_fin")
    if inicio and fin and inicio > fin:
        raise _invalido("fecha_inicio", "La fecha de inicio no puede ser posterior a la fecha de fin.")
    if definicion.tipo == "REPORTE_TELEMETRIA" and inicio and fin and (fin - inicio).days > MAX_DIAS_TELEMETRIA:
        raise _invalido("fecha_inicio", f"El reporte de telemetría cubre como máximo {MAX_DIAS_TELEMETRIA} días. "
                                        "Divida el rango en varios reportes.")
    for nombre in ("fecha_fin", "fecha_corte"):
        if limpios.get(nombre) and limpios[nombre] > hoy:
            raise _invalido(nombre, f"«{ETIQUETAS[nombre]}» no puede ser una fecha futura.")
    return limpios


def filtros_serializables(filtros: dict[str, Any]) -> dict[str, Any]:
    """Los filtros como JSON (fechas en ISO) para guardarlos en la solicitud y en la auditoría."""
    return {k: v.isoformat() if isinstance(v, date) else v for k, v in filtros.items()}
