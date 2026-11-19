# | Fecha      | Nombre   | Que se hizo                                                        |
# |------------|----------|--------------------------------------------------------------------|
# | 2026-11-14 | Arekkazu | M08 RF-103: opciones de widget, semáforo, alcance y fallo aislado    |
"""RF-103 — widgets del dashboard: opciones configurables, regla del semáforo y datos por widget.

Sin BD: el caso de uso se prueba con repositorios falsos; las consultas SQL tienen su propia prueba
de integración.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

import pytest

from src.configuration.application.use_cases.personalizacion.guardar_dashboard_use_case import GuardarDashboardUseCase
from src.configuration.domain.entities.dashboard_layout import DashboardLayout, WidgetConfig
from src.configuration.domain.entities.widget import Widget
from src.configuration.infrastructure.dto.guardar_dashboard_dto import GuardarDashboardDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.reporting.application.use_cases.dashboard.obtener_datos_widget_use_case import ObtenerDatosWidgetUseCase
from src.reporting.application.use_cases.dashboard.obtener_opciones_widget_use_case import ObtenerOpcionesWidgetUseCase
from src.reporting.domain.widgets import (
    DEFINICIONES,
    coincide_variable,
    estado_semaforo,
    resolver_parametros,
    validar_parametros,
)
from src.shared.errors import AuthorizationError, NotFoundError, ValidationError

PRODUCTOR = UsuarioActual(id_usuario=7, id_token=1, id_rol=2, id_estado_cuenta=2)
CONTADOR = UsuarioActual(id_usuario=9, id_token=1, id_rol=5, id_estado_cuenta=2)
AHORA = datetime(2026, 11, 14, 15, 0, tzinfo=timezone.utc)

CATALOGO = [
    Widget(1, "temp_galpon", "Temperatura", "Ambiental", 1, 33),
    Widget(16, "semaforo_areas", "Estado de las áreas", "Alertas", 2, 33),
    Widget(18, "valor_inventario", "Valor del inventario", "Finanzas", 1, 200),
    Widget(28, "precios_por_vencer", "Precios que vencen pronto", "Finanzas", 1, 88),
]
LEGIBLES = {2: {1, 16, 18}, 5: {18, 28}}


class WidgetRepoFake:
    def obtener_activos(self) -> list[Widget]:
        return list(CATALOGO)

    def ids_legibles_por_rol(self, id_rol: int) -> set[int]:
        return set(LEGIBLES.get(id_rol, set()))


class DashboardRepoFake:
    def __init__(self, propio: Optional[list[WidgetConfig]] = None,
                 por_rol: Optional[list[WidgetConfig]] = None) -> None:
        self.propio = propio
        self.por_rol = por_rol
        self.guardados: list[DashboardLayout] = []

    @staticmethod
    def _layout(grid):
        return DashboardLayout(id_usuario=7, grid=grid, active_widget=[], fecha_actualizacion=None)

    def obtener_por_usuario(self, id_usuario):
        return self._layout(self.propio) if self.propio is not None else None

    def obtener_default_de_rol(self, id_usuario, id_rol):
        return self._layout(self.por_rol) if self.por_rol is not None else None

    def version_perfil(self, id_usuario):
        return None

    def guardar(self, entidad):
        self.guardados.append(entidad)
        return entidad


class AlcanceFake:
    def __init__(self, permitidas: Optional[list[int]]) -> None:
        self.permitidas = permitidas

    def listar_ids_fincas_permitidas(self, id_usuario, id_rol):
        return self.permitidas


class DatosFake:
    """Solo lo que piden estas pruebas; registra con qué se consultó."""

    def __init__(self, **respuestas) -> None:
        self.respuestas = respuestas
        self.llamadas: dict[str, tuple] = {}

    def areas_de_finca(self, id_finca):
        return [{"valor": 10, "nombre": "Galpón 1"}, {"valor": 11, "nombre": "Galpón 2"}]

    def especies_de_finca(self, id_finca):
        return [{"valor": 1, "nombre": "Bovino"}]

    def semaforo_areas(self, id_finca, areas):
        self.llamadas["semaforo_areas"] = (id_finca, areas)
        respuesta = self.respuestas.get("semaforo_areas", [])
        if isinstance(respuesta, Exception):
            raise respuesta
        return respuesta

    def lecturas(self, id_finca, id_area):
        self.llamadas["lecturas"] = (id_finca, id_area)
        return [dict(f) for f in self.respuestas.get("lecturas", [])]

    def activos_valorados(self, id_finca):
        self.llamadas["activos_valorados"] = (id_finca,)
        return self.respuestas.get("activos_valorados", [])

    def precios_por_vencer(self, dias, limite):
        self.llamadas["precios_por_vencer"] = (dias, limite)
        return [], 0


def _celda(id_widget: int, parametros: Optional[dict] = None) -> WidgetConfig:
    return WidgetConfig(id_widget=id_widget, posicion_fila=1, posicion_columna=1, span_columnas=1,
                        visible=True, orden=0, parametros=parametros or {})


def _use_case(datos=None, dashboard=None, permitidas=(3,)) -> ObtenerDatosWidgetUseCase:
    return ObtenerDatosWidgetUseCase(
        widget_repo=WidgetRepoFake(),
        dashboard_repo=dashboard or DashboardRepoFake(),
        datos_repo=datos or DatosFake(),
        alcance=AlcanceFake(None if permitidas is None else list(permitidas)),
    )


# ── Opciones del widget ───────────────────────────────────────────────────────

@pytest.mark.parametrize("parametros", [
    {"desconocida": 1},
    {"areas": "10"},
    {"areas": [10, True]},
    {"areas": [0]},
    {"areas": list(range(1, 52))},
    "no-es-un-objeto",
])
def test_opciones_invalidas_del_semaforo_responden_400(parametros):
    with pytest.raises(ValidationError) as exc:
        validar_parametros(DEFINICIONES["semaforo_areas"], parametros)
    assert exc.value.code == "VAL_ENTRADA"
    assert exc.value.field == "parametros"


@pytest.mark.parametrize("valor", [20, "15", None])
def test_lista_solo_acepta_sus_valores_con_su_tipo(valor):
    definicion = DEFINICIONES["precios_por_vencer"]
    if valor is None:
        assert validar_parametros(definicion, {"dias": None}) == {}
        return
    with pytest.raises(ValidationError):
        validar_parametros(definicion, {"dias": valor})


def test_ids_repetidos_se_guardan_una_vez():
    assert validar_parametros(DEFINICIONES["semaforo_areas"], {"areas": [10, 11, 10]}) == {"areas": [10, 11]}


def test_area_unica_rechaza_booleanos():
    with pytest.raises(ValidationError):
        validar_parametros(DEFINICIONES["temp_galpon"], {"area": True})


def test_lo_fijo_del_widget_no_lo_cambia_el_usuario():
    parametros = resolver_parametros(DEFINICIONES["temp_galpon"], {"area": 10})
    assert parametros == {"area": 10, "variable": "temperatura"}


def test_opciones_guardadas_que_ya_no_son_validas_vuelven_al_defecto():
    assert resolver_parametros(DEFINICIONES["precios_por_vencer"], {"dias": 99}) == {"dias": 15}


@pytest.mark.parametrize("variable,nombre,categoria,esperado", [
    ("temperatura", "Temperatura del agua", None, True),
    ("temperatura", "Temperatura Ambiental", "AMBIENTAL", True),
    ("temperatura", "Temperatura Corporal", "ANIMAL", False),
    ("humedad", "Humedad Relativa", "AMBIENTAL", True),
    ("ph", "pH del agua", "HIDRICA", True),
    ("co2", "Dióxido de Carbono (CO2)", "AMBIENTAL", True),
    ("co2", "Amoniaco (NH3)", "AMBIENTAL", False),
])
def test_cada_widget_de_lectura_toma_su_variable(variable, nombre, categoria, esperado):
    assert coincide_variable(variable, nombre, categoria) is esperado


# ── Regla del semáforo (R5) ───────────────────────────────────────────────────

@pytest.mark.parametrize("criticas,advertencias,sin_datos,esperado", [
    (1, 0, False, "ROJO"),
    (1, 3, True, "ROJO"),      # una crítica manda aunque el área esté sin sensores
    (0, 2, False, "AMARILLO"),
    (0, 0, True, "SIN_DATOS"),  # sensores caídos: no es rojo ni amarillo
    (0, 0, False, "VERDE"),
])
def test_regla_de_fusion_del_semaforo(criticas, advertencias, sin_datos, esperado):
    assert estado_semaforo(criticas, advertencias, sin_datos) == esperado


# ── Acceso y finca ────────────────────────────────────────────────────────────

def test_widget_fuera_del_catalogo_responde_404():
    with pytest.raises(NotFoundError):
        _use_case().execute("no_existe", 3, PRODUCTOR, AHORA)


def test_widget_que_el_rol_no_lee_responde_403():
    with pytest.raises(AuthorizationError) as exc:
        _use_case().execute("precios_por_vencer", 3, PRODUCTOR, AHORA)
    assert exc.value.code == "WIDGET_NO_AUTORIZADO"


def test_finca_ajena_responde_403_con_el_mensaje_del_rf():
    with pytest.raises(AuthorizationError) as exc:
        _use_case(permitidas=(3,)).execute("semaforo_areas", 4, PRODUCTOR, AHORA)
    assert exc.value.message == "No tienes permisos para esta finca."


def test_widget_de_finca_sin_finca_responde_400():
    with pytest.raises(ValidationError) as exc:
        _use_case().execute("semaforo_areas", None, PRODUCTOR, AHORA)
    assert exc.value.field == "id_finca"


def test_widget_contable_funciona_sin_finca():
    datos = DatosFake()
    resultado = _use_case(datos=datos, permitidas=()).execute("precios_por_vencer", None, CONTADOR, AHORA)
    assert resultado.estado == "OK"
    assert datos.llamadas["precios_por_vencer"] == (15, 10)


def test_administrador_global_ve_cualquier_finca():
    resultado = _use_case(permitidas=None).execute("semaforo_areas", 99, PRODUCTOR, AHORA)
    assert resultado.estado == "SIN_DATOS"


# ── Datos por widget ──────────────────────────────────────────────────────────

_FILAS_SEMAFORO = [
    {"id_infraestructura": 10, "nombre": "Galpón 1", "criticas": 0, "advertencias": 0, "sin_datos": False},
    {"id_infraestructura": 11, "nombre": "Galpón 2", "criticas": 1, "advertencias": 0, "sin_datos": False},
]


def test_semaforo_con_las_areas_guardadas_por_el_usuario():
    datos = DatosFake(semaforo_areas=_FILAS_SEMAFORO)
    dashboard = DashboardRepoFake(propio=[_celda(16, {"areas": [11]})])
    resultado = _use_case(datos=datos, dashboard=dashboard).execute("semaforo_areas", 3, PRODUCTOR, AHORA)

    assert datos.llamadas["semaforo_areas"] == (3, [11])
    assert resultado.alcance == "seleccion"
    assert [a["estado"] for a in resultado.datos["areas"]] == ["VERDE", "ROJO"]
    assert resultado.datos["resumen"] == {"VERDE": 1, "ROJO": 1}


def test_areas_de_otra_finca_muestran_toda_la_finca_activa():
    datos = DatosFake(semaforo_areas=_FILAS_SEMAFORO)
    dashboard = DashboardRepoFake(propio=[_celda(16, {"areas": [500]})])
    resultado = _use_case(datos=datos, dashboard=dashboard).execute("semaforo_areas", 3, PRODUCTOR, AHORA)

    assert datos.llamadas["semaforo_areas"] == (3, None)
    assert resultado.alcance == "todas"


def test_sin_layout_propio_usa_las_opciones_del_predeterminado_del_rol():
    datos = DatosFake(semaforo_areas=_FILAS_SEMAFORO)
    dashboard = DashboardRepoFake(por_rol=[_celda(16, {"areas": [10]})])
    _use_case(datos=datos, dashboard=dashboard).execute("semaforo_areas", 3, PRODUCTOR, AHORA)
    assert datos.llamadas["semaforo_areas"] == (3, [10])


def test_lecturas_de_temperatura_dejan_fuera_las_demas_variables():
    lecturas = [
        {"id_sensor": 1, "variable": "Temperatura Ambiental", "categoria": "AMBIENTAL", "valor": 31.4},
        {"id_sensor": 2, "variable": "Humedad Relativa", "categoria": "AMBIENTAL", "valor": 70.0},
        {"id_sensor": 3, "variable": "Temperatura Corporal", "categoria": "ANIMAL", "valor": 38.5},
    ]
    resultado = _use_case(datos=DatosFake(lecturas=lecturas)).execute("temp_galpon", 3, PRODUCTOR, AHORA)
    assert [lectura["id_sensor"] for lectura in resultado.datos["lecturas"]] == [1]
    assert "categoria" not in resultado.datos["lecturas"][0]


def test_un_fallo_de_consulta_no_tumba_el_dashboard():
    datos = DatosFake(semaforo_areas=RuntimeError("conexión perdida"))
    resultado = _use_case(datos=datos).execute("semaforo_areas", 3, PRODUCTOR, AHORA)
    assert resultado.estado == "ERROR"
    assert resultado.mensaje
    assert resultado.datos == {}


def test_la_huella_solo_cambia_si_cambian_los_datos():
    uc = _use_case(datos=DatosFake(semaforo_areas=_FILAS_SEMAFORO))
    primera = uc.execute("semaforo_areas", 3, PRODUCTOR, AHORA)
    segunda = uc.execute("semaforo_areas", 3, PRODUCTOR, datetime(2026, 11, 14, 15, 1, tzinfo=timezone.utc))
    otra = _use_case(datos=DatosFake(semaforo_areas=_FILAS_SEMAFORO[:1])).execute("semaforo_areas", 3, PRODUCTOR, AHORA)
    assert primera.huella == segunda.huella
    assert primera.huella != otra.huella


def _valorado(estado="ACTIVO", por_costo=False, valor=Decimal("1000"), cosechado=False, id_finca=3):
    return {"estado": estado, "valorado_por_costo": por_costo, "cosechado_completamente": cosechado,
            "valor_razonable_neto": None if por_costo else valor,
            "valor_contable_por_costo": valor if por_costo else None, "id_finca": id_finca}


def test_valor_del_inventario_solo_cuenta_lo_vivo_y_separa_por_metodo():
    activos = [_valorado(), _valorado(por_costo=True, valor=Decimal("500")),
               _valorado(estado="BAJA", valor=Decimal("9999")), _valorado(cosechado=True, valor=Decimal("7777"))]
    dashboard = DashboardRepoFake(propio=[_celda(18, {"vista": "POR_METODO"})])
    resultado = _use_case(datos=DatosFake(activos_valorados=activos), dashboard=dashboard).execute(
        "valor_inventario", 3, PRODUCTOR, AHORA)

    assert resultado.datos == {"vista": "POR_METODO", "valor_total": 1500.0, "activos": 2, "moneda": "COP",
                               "valor_razonable": 1000.0, "valor_costo": 500.0}


def test_opciones_ofrecen_las_areas_de_la_finca_activa():
    opciones = ObtenerOpcionesWidgetUseCase(_use_case()).execute("semaforo_areas", 3, PRODUCTOR)
    assert opciones == {"areas": [{"valor": 10, "nombre": "Galpón 1"}, {"valor": 11, "nombre": "Galpón 2"}]}


def test_opciones_de_lista_devuelven_sus_valores():
    opciones = ObtenerOpcionesWidgetUseCase(_use_case()).execute("valor_inventario", None, CONTADOR)
    assert opciones == {"vista": [{"valor": "TOTAL"}, {"valor": "POR_METODO"}]}


# ── Guardado de opciones en Personalización (RF-28) ───────────────────────────

class DbFake:
    def commit(self):
        pass

    def rollback(self):
        pass


def _guardar(parametros, frecuencia=None) -> DashboardRepoFake:
    repo = DashboardRepoFake()
    dto = GuardarDashboardDTO(
        layout_config=[{"id_widget": 16, "posicion_fila": 1, "posicion_columna": 1, "span_columnas": 2,
                        "visible": True, "orden": 0, "parametros": parametros}],
        active_widget=["semaforo_areas"],
        frecuencia_actualizacion=frecuencia,
    )
    GuardarDashboardUseCase(db=DbFake(), dashboard_repo=repo, widget_repo=WidgetRepoFake()).execute(dto, PRODUCTOR)
    return repo


def test_guardar_conserva_las_opciones_y_la_frecuencia_en_el_json():
    repo = _guardar({"areas": [10, 10, 11]}, frecuencia=60)
    config = repo.guardados[0].config_jsonb()
    assert config["grid"][0]["parametros"] == {"areas": [10, 11]}
    assert config["frecuencia_actualizacion"] == 60


def test_guardar_sin_frecuencia_usa_30_segundos():
    assert _guardar({}).guardados[0].config_jsonb()["frecuencia_actualizacion"] == 30


def test_guardar_rechaza_una_opcion_que_el_widget_no_tiene():
    with pytest.raises(ValidationError):
        _guardar({"sensores": [1]})


@pytest.mark.parametrize("segundos", [14, 121])
def test_frecuencia_fuera_de_15_a_120_segundos_es_400(segundos):
    with pytest.raises(Exception) as exc:
        _guardar({}, frecuencia=segundos)
    assert "frecuencia_actualizacion" in str(exc.value)


def test_celda_sin_opciones_no_escribe_la_clave_en_el_json():
    celda = _celda(16)
    assert "parametros" not in celda.to_dict()
    assert WidgetConfig.from_dict(celda.to_dict()).parametros == {}
