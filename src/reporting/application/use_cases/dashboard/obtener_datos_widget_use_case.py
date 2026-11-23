# | Fecha      | Nombre   | Que se hizo                                                |
# |------------|----------|------------------------------------------------------------|
# | 2026-11-14 | Arekkazu | M08 RF-103: datos de un widget con las opciones del usuario |
# | 2026-11-21 | destroyerban | INC-M08-380-G002 RF-103: el valor del inventario se acota a las fincas permitidas |
# | 2026-11-22 | Arekkazu | A11Y2-M08 TC-DIS-278 RF-103: el semáforo trae el total de alertas por área |
"""Caso de uso: datos de un widget del dashboard para la finca activa (RF-103).

Cada widget se pide por separado: si uno falla o tarda, los demás siguen (CA-5, CA-8, CA-9). El
widget se consulta con las opciones que el usuario guardó en su layout (o las del predeterminado de
su rol). Un fallo de la consulta no sale como 500: el widget responde ``ERROR`` con un mensaje y el
front conserva lo último que mostraba.

La ``huella`` resume los datos: si no cambió entre dos refrescos, el front no redibuja (RNF-05).
"""
from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Callable, Optional

from src.configuration.domain.repositories.dashboard_layout_repository import DashboardLayoutRepository
from src.configuration.domain.repositories.widget_repository import WidgetRepository
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.reporting.domain.repositories.datos_widget_repository import DatosWidgetRepository
from src.reporting.domain.widgets import (
    DEFINICIONES,
    MENSAJE_ERROR,
    MENSAJES_SIN_DATOS,
    DefinicionWidget,
    coincide_variable,
    estado_semaforo,
    patron_variable,
    resolver_parametros,
)
from src.shared.alcance_finca_port import AlcanceFincaPort
from src.shared.errors import AuthorizationError, NotFoundError, ValidationError

logger = logging.getLogger(__name__)

OK, SIN_DATOS, ERROR = "OK", "SIN_DATOS", "ERROR"
_LIMITE_LISTA = 10
_RETRO_ANTIGUEDAD = timedelta(hours=48)
_HORAS_PERIODO = {"24h": 24, "7d": 24 * 7, "30d": 24 * 30}
# Rango del histórico → (desde cuánto, ancho de cada punto): a lo sumo ~60 puntos por sensor.
_RANGOS = {"6h": (timedelta(hours=6), "10 minutes"), "24h": (timedelta(hours=24), "30 minutes"),
           "7d": (timedelta(days=7), "3 hours")}
_ESTADOS_SIN_SENAL = ("SIN_SEÑAL", "INACTIVO")


@dataclass
class Resultado:
    """Lo que arma cada fuente: los datos y, si aplica, si faltan o si se mostró toda la finca."""
    datos: dict[str, Any]
    sin_datos: bool = False
    alcance: Optional[str] = None


@dataclass
class DatosWidget:
    clave: str
    estado: str
    mensaje: Optional[str]
    actualizado_en: datetime
    huella: str
    alcance: Optional[str] = None
    datos: dict[str, Any] = field(default_factory=dict)


def _huella(datos: dict[str, Any]) -> str:
    def _plano(v: Any) -> Any:
        return float(v) if isinstance(v, Decimal) else str(v)
    return hashlib.sha256(json.dumps(datos, sort_keys=True, default=_plano).encode()).hexdigest()[:16]


class ObtenerDatosWidgetUseCase:
    """Datos de un widget visible para el rol, acotados a una finca del usuario."""

    def __init__(
        self,
        widget_repo: WidgetRepository,
        dashboard_repo: DashboardLayoutRepository,
        datos_repo: DatosWidgetRepository,
        alcance: AlcanceFincaPort,
    ) -> None:
        self.widget_repo = widget_repo
        self.dashboard_repo = dashboard_repo
        self.datos = datos_repo
        self.alcance = alcance
        self._fuentes: dict[str, Callable[..., Resultado]] = {
            "semaforo": self._semaforo,
            "lecturas": self._lecturas,
            "historico": self._historico,
            "alertas_activas": self._alertas_activas,
            "alertas_sanitarias": self._alertas_sanitarias,
            "riesgo_alto": self._riesgo_alto,
            "distribucion_riesgo": self._distribucion_riesgo,
            "retroalimentacion_pendiente": self._retroalimentacion_pendiente,
            "inventario": self._inventario,
            "eventos": self._eventos,
            "conversion": self._conversion,
            "valor_inventario": self._valor_inventario,
            "periodos": self._periodos,
            "reconocimientos": self._reconocimientos,
            "integraciones": self._integraciones,
            "precios": self._precios,
            "estado_dispositivos": self._estado_dispositivos,
            "sin_senal": self._sin_senal,
            "calibraciones": self._calibraciones,
            "configuracion_pendiente": self._configuracion_pendiente,
            "estado_fincas": self._estado_fincas,
        }

    def execute(self, clave: str, id_finca: Optional[int], usuario: UsuarioActual,
                ahora: Optional[datetime] = None) -> DatosWidget:
        ahora = ahora or datetime.now(timezone.utc)
        definicion, id_widget = self.autorizar(clave, usuario)
        permitidas = self.validar_finca(id_finca, definicion, usuario)
        parametros = resolver_parametros(definicion, self._guardados(usuario, id_widget))

        # Acceso y finca ya se validaron: lo que falle desde aquí (una consulta, un parámetro del
        # módulo fuente sin configurar) deja solo este widget sin datos.
        try:
            resultado = self._fuentes[definicion.fuente](
                id_finca=id_finca, parametros=parametros, usuario=usuario, permitidas=permitidas, ahora=ahora)
        except Exception:
            logger.exception("Dashboard: falló el widget %s (finca %s)", clave, id_finca)
            return DatosWidget(clave=clave, estado=ERROR, mensaje=MENSAJE_ERROR, actualizado_en=ahora, huella="")

        estado = SIN_DATOS if resultado.sin_datos else OK
        return DatosWidget(
            clave=clave,
            estado=estado,
            mensaje=MENSAJES_SIN_DATOS.get(definicion.fuente) if estado == SIN_DATOS else None,
            actualizado_en=ahora,
            huella=_huella(resultado.datos),
            alcance=resultado.alcance,
            datos=resultado.datos,
        )

    # --- Validaciones compartidas con el caso de uso de opciones ---------------------------------

    def autorizar(self, clave: str, usuario: UsuarioActual) -> tuple[DefinicionWidget, int]:
        definicion = DEFINICIONES.get(clave)
        widget = next((w for w in self.widget_repo.obtener_activos() if w.clave == clave), None)
        if definicion is None or widget is None:
            raise NotFoundError(code="WIDGET_INEXISTENTE", message="Ese indicador no existe en el dashboard.",
                                field="clave")
        if widget.id_widget not in self.widget_repo.ids_legibles_por_rol(usuario.id_rol):
            raise AuthorizationError(
                code="WIDGET_NO_AUTORIZADO",
                message="Este indicador no está disponible para tu rol.",
                field="clave",
            )
        return definicion, widget.id_widget

    def validar_finca(self, id_finca: Optional[int], definicion: DefinicionWidget,
                      usuario: UsuarioActual) -> Optional[list[int]]:
        """Fincas permitidas (``None`` = alcance global). Fase 1.1: finca ajena → 403."""
        permitidas = self.alcance.listar_ids_fincas_permitidas(usuario.id_usuario, usuario.id_rol)
        if id_finca is not None and permitidas is not None and id_finca not in permitidas:
            raise AuthorizationError(code="FINCA_NO_AUTORIZADA", message="No tienes permisos para esta finca.",
                                     field="id_finca")
        if id_finca is None and definicion.requiere_finca:
            raise ValidationError(code="VAL_ENTRADA", message="Elige una finca para ver este indicador.",
                                  field="id_finca")
        return permitidas

    def _guardados(self, usuario: UsuarioActual, id_widget: int) -> Any:
        layout = (self.dashboard_repo.obtener_por_usuario(usuario.id_usuario)
                  or self.dashboard_repo.obtener_default_de_rol(id_usuario=usuario.id_usuario, id_rol=usuario.id_rol))
        celda = next((c for c in (layout.grid if layout else []) if c.id_widget == id_widget), None)
        return celda.parametros if celda else None

    def _acotar(self, elegidas: list[int] | Optional[int], disponibles: set[int]) -> tuple[Optional[list[int]], str]:
        """Áreas elegidas que son de la finca activa. Si ninguna lo es (o no se eligió), toda la finca."""
        lista = [elegidas] if isinstance(elegidas, int) else list(elegidas or [])
        validas = [a for a in lista if a in disponibles]
        return (validas, "seleccion") if validas else (None, "todas")

    def _areas(self, id_finca: int, parametros: dict[str, Any], nombre: str) -> tuple[Optional[list[int]], str]:
        disponibles = {a["valor"] for a in self.datos.areas_de_finca(id_finca)}
        return self._acotar(parametros.get(nombre), disponibles)

    # --- Fuentes ---------------------------------------------------------------------------------

    def _semaforo(self, id_finca, parametros, **_) -> Resultado:
        areas, alcance = self._areas(id_finca, parametros, "areas")
        filas = self.datos.semaforo_areas(id_finca, areas)
        items = [{"id_infraestructura": f["id_infraestructura"], "nombre": f["nombre"],
                  "estado": estado_semaforo(f["criticas"], f["advertencias"], f["sin_datos"]),
                  "criticas": f["criticas"], "advertencias": f["advertencias"],
                  "alertas": f["criticas"] + f["advertencias"]} for f in filas]  # TC-DIS-278: total en texto
        resumen: dict[str, int] = {}
        for item in items:
            resumen[item["estado"]] = resumen.get(item["estado"], 0) + 1
        return Resultado({"areas": items, "resumen": resumen}, sin_datos=not items, alcance=alcance)

    def _lecturas(self, id_finca, parametros, **_) -> Resultado:
        areas, alcance = self._areas(id_finca, parametros, "area")
        filas = self.datos.lecturas(id_finca, areas[0] if areas else None)
        variable = parametros.get("variable")
        sensores = set(parametros.get("sensores") or [])
        items = [f for f in filas
                 if coincide_variable(variable, f["variable"], f.pop("categoria"))
                 and (not sensores or f["id_sensor"] in sensores)]
        return Resultado({"lecturas": items}, sin_datos=not items, alcance=alcance)

    def _historico(self, id_finca, parametros, ahora, **_) -> Resultado:
        areas, alcance = self._areas(id_finca, parametros, "area")
        rango, paso = _RANGOS[parametros["rango"]]
        filas = self.datos.historico(id_finca, areas[0] if areas else None,
                                     patron_variable(parametros["variable"]), ahora - rango, paso)
        series: dict[tuple[str, str], dict[str, Any]] = {}
        for f in filas:
            serie = series.setdefault((f["sensor"], f["variable"]), {
                "sensor": f["sensor"], "variable": f["variable"], "unidad": f["unidad"], "puntos": []})
            serie["puntos"].append({"t": f["instante"], "v": float(f["valor"]) if f["valor"] is not None else None})
        return Resultado({"rango": parametros["rango"], "series": list(series.values())},
                         sin_datos=not series, alcance=alcance)

    def _alertas_activas(self, id_finca, parametros, **_) -> Resultado:
        areas, alcance = self._areas(id_finca, parametros, "areas")
        items, total = self.datos.alertas_activas(id_finca, areas, bool(parametros.get("solo_criticas")),
                                                  _LIMITE_LISTA)
        return Resultado({"items": items, "total": total}, alcance=alcance)

    def _alertas_sanitarias(self, id_finca, **_) -> Resultado:
        return Resultado({"tipos": self.datos.alertas_sanitarias(id_finca)})

    def _riesgo_alto(self, id_finca, parametros, **_) -> Resultado:
        items, total = self.datos.riesgo_alto(id_finca, parametros["especies"] or None, _LIMITE_LISTA)
        return Resultado({"items": items, "total": total})

    def _distribucion_riesgo(self, id_finca, parametros, **_) -> Resultado:
        filas = self.datos.distribucion_riesgo(id_finca, parametros["especies"] or None,
                                               _HORAS_PERIODO[parametros["periodo"]])
        return Resultado({"especies": filas}, sin_datos=not filas)

    def _retroalimentacion_pendiente(self, id_finca, usuario, ahora, **_) -> Resultado:
        items, total = self.datos.retroalimentacion_pendiente(id_finca, usuario.id_usuario,
                                                              ahora - _RETRO_ANTIGUEDAD, _LIMITE_LISTA)
        return Resultado({"items": items, "total": total})

    def _inventario(self, id_finca, parametros, **_) -> Resultado:
        filas = self.datos.inventario(id_finca, parametros["especies"] or None)
        return Resultado({"especies": filas}, sin_datos=not filas)

    def _eventos(self, id_finca, parametros, **_) -> Resultado:
        filas = self.datos.eventos(id_finca, parametros["cantidad"])
        return Resultado({"items": filas}, sin_datos=not filas)

    def _conversion(self, id_finca, parametros, **_) -> Resultado:
        filas = self.datos.conversion(id_finca, parametros["especies"] or None)
        return Resultado({"especies": filas}, sin_datos=not filas)

    def _valor_inventario(self, id_finca, parametros, permitidas, **_) -> Resultado:
        # El inventario es lo vivo: sin bajas, cierres ni lo ya cosechado por completo.
        vivos = [f for f in self.datos.activos_valorados(id_finca, permitidas)
                 if f["estado"] not in ("BAJA", "CERRADO") and not f["cosechado_completamente"]]
        razonable = sum((f["valor_razonable_neto"] or 0 for f in vivos if not f["valorado_por_costo"]), Decimal(0))
        costo = sum((f["valor_contable_por_costo"] or 0 for f in vivos if f["valorado_por_costo"]), Decimal(0))
        datos: dict[str, Any] = {"vista": parametros["vista"], "valor_total": float(razonable + costo),
                                 "activos": len(vivos), "moneda": "COP"}
        if parametros["vista"] == "POR_METODO":
            datos["valor_razonable"] = float(razonable)
            datos["valor_costo"] = float(costo)
        return Resultado(datos, sin_datos=not vivos)

    def _periodos(self, id_finca, **_) -> Resultado:
        filas = self.datos.periodos_abiertos(id_finca)
        return Resultado({"items": filas[:_LIMITE_LISTA], "total": len(filas)})

    def _reconocimientos(self, id_finca, **_) -> Resultado:
        filas = self.datos.sin_reconocimiento(id_finca)
        return Resultado({"items": filas[:_LIMITE_LISTA], "total": len(filas)})

    def _integraciones(self, parametros, **_) -> Resultado:
        items, total = self.datos.integraciones_fallidas(parametros["dias"], _LIMITE_LISTA)
        return Resultado({"items": items, "total": total})

    def _precios(self, parametros, **_) -> Resultado:
        items, total = self.datos.precios_por_vencer(parametros["dias"], _LIMITE_LISTA)
        return Resultado({"items": items, "total": total})

    def _dispositivos(self, id_finca, parametros) -> tuple[list[dict[str, Any]], str]:
        areas, alcance = self._areas(id_finca, parametros, "areas")
        return self.datos.dispositivos(id_finca, areas), alcance

    def _estado_dispositivos(self, id_finca, parametros, **_) -> Resultado:
        filas, alcance = self._dispositivos(id_finca, parametros)
        conteo: dict[str, int] = {}
        for f in filas:
            conteo[f["estado"]] = conteo.get(f["estado"], 0) + 1
        fuera = [f for f in filas if f["estado"] != "ACTIVO"]
        return Resultado({"conteo": conteo, "total": len(filas), "items": fuera[:_LIMITE_LISTA]},
                         sin_datos=not filas, alcance=alcance)

    def _sin_senal(self, id_finca, parametros, **_) -> Resultado:
        filas, alcance = self._dispositivos(id_finca, parametros)
        caidos = sorted((f for f in filas if f["estado"] in _ESTADOS_SIN_SENAL),
                        key=lambda f: (f["fecha_ultimo_contacto"] is not None,
                                       f["fecha_ultimo_contacto"] or datetime.min.replace(tzinfo=timezone.utc)))
        return Resultado({"items": caidos[:_LIMITE_LISTA], "total": len(caidos)}, alcance=alcance)

    def _calibraciones(self, id_finca, parametros, **_) -> Resultado:
        filas, alcance = self._dispositivos(id_finca, parametros)
        recientes = sorted((f for f in filas if f["ultima_calibracion"] is not None),
                           key=lambda f: f["ultima_calibracion"], reverse=True)
        return Resultado({"items": recientes[:_LIMITE_LISTA], "total": len(filas)},
                         sin_datos=not filas, alcance=alcance)

    def _configuracion_pendiente(self, id_finca, parametros, **_) -> Resultado:
        areas, alcance = self._areas(id_finca, parametros, "areas")
        filas = self.datos.configuracion_pendiente(id_finca, areas)
        return Resultado({"items": filas[:_LIMITE_LISTA], "total": len(filas)}, alcance=alcance)

    def _estado_fincas(self, permitidas, **_) -> Resultado:
        filas = self.datos.estado_fincas(permitidas)
        return Resultado({"items": filas}, sin_datos=not filas)
