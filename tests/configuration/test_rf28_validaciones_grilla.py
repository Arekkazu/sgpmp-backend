"""RF-28 — validaciones de la grilla del dashboard, catálogo de widgets y restauración.

El estado de módulo 9 daba por ausentes el límite de 12 widgets, la detección de
solapamiento y la regla del span en la última columna. Las tres existían; lo que
no cumplía el RF era el código HTTP del límite (422 donde el flujo alterno pide
400), el texto de los mensajes, que ``active_widget`` no se validaba contra nada,
que un widget oculto seguía ocupando su celda, y que no existían ni el catálogo
de widgets (403 por rol), ni la detección de perfil modificado (409), ni el
layout base por rol (500 al restaurar).

Verifica con fakes (sin BD; modulo9 no existe en la BD `pruebas`).
"""
from __future__ import annotations

from typing import Optional

import pytest

from src.configuration.application.use_cases.personalizacion.guardar_dashboard_use_case import (
    GuardarDashboardUseCase,
)
from src.configuration.application.use_cases.personalizacion.obtener_catalogo_widgets_use_case import (
    ObtenerCatalogoWidgetsUseCase,
)
from src.configuration.application.use_cases.personalizacion.obtener_datos_dashboard_use_case import (
    ObtenerDatosDashboardUseCase,
)
from src.configuration.application.use_cases.personalizacion.restaurar_dashboard_use_case import (
    RestaurarDashboardUseCase,
)
from src.configuration.domain.entities.dashboard_layout import DashboardLayout, WidgetConfig
from src.configuration.domain.entities.widget import MENSAJE_SIN_DATOS, Widget
from src.configuration.infrastructure.dto.guardar_dashboard_dto import GuardarDashboardDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import (
    AuthorizationError,
    ConflictError,
    InfrastructureError,
    ValidationError,
)

PRODUCTOR = UsuarioActual(id_usuario=7, id_token=1, id_rol=2, id_estado_cuenta=2)
VETERINARIO = UsuarioActual(id_usuario=8, id_token=1, id_rol=3, id_estado_cuenta=2)
ROL_SIN_DEFAULT = UsuarioActual(id_usuario=9, id_token=1, id_rol=99, id_estado_cuenta=2)

# Recorte del catálogo sembrado por la migración a7f3c92e4d18.
CATALOGO = [
    Widget(1, "temp_galpon", "Temperatura Galpon", "Ambiental", 1, 33),
    Widget(2, "hum_galpon", "Humedad Galpon", "Ambiental", 1, 33),
    Widget(3, "ph_estanque", "pH Estanque", "Ambiental", 1, 33),
    Widget(4, "co2_galpon", "CO2 Ambiente", "Ambiental", 1, 33),
    Widget(5, "temp_corral", "Temperatura Corral", "Ambiental", 1, 33),
    Widget(6, "estado_iot", "Estado Dispositivos IoT", "IoT", 2, 35,
           "vw_rf28_widget_estado_dispositivos"),
    Widget(7, "cal_sensores", "Calibraciones Recientes", "IoT", 1, 11,
           "vw_rf28_widget_estado_dispositivos"),
    Widget(8, "alertas", "Alertas Ambientales", "Alertas", 1, 32),
    Widget(9, "alertas_crit", "Alertas Criticas", "Alertas", 1, 32),
    Widget(10, "hist_temp", "Historico Temperatura", "Historico", 2, 34),
    Widget(11, "hist_hum", "Historico Humedad", "Historico", 2, 34),
    Widget(12, "prod_aves", "Indicadores Avicultura", "Produccion", 1, 19),
]

# Matriz real de modulo1.permisos: el Productor (2) no lee metricas_produccion
# (recurso 19) y el Veterinario (3) no lee dispositivos_iot (recurso 11).
LEGIBLES_POR_ROL = {
    2: {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11},
    3: {1, 2, 3, 4, 5, 6, 8, 9, 10, 11, 12},
}


class DbFake:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


class WidgetRepoFake:
    def __init__(self, catalogo=None, legibles=None) -> None:
        self.catalogo = CATALOGO if catalogo is None else catalogo
        self.legibles = LEGIBLES_POR_ROL if legibles is None else legibles

    def obtener_activos(self) -> list[Widget]:
        return list(self.catalogo)

    def ids_legibles_por_rol(self, id_rol: int) -> set[int]:
        return set(self.legibles.get(id_rol, set()))


class DashboardRepoFake:
    def __init__(self, existente=None, defaults=None, version=1, nombres=None) -> None:
        self.existente = existente
        self.defaults = defaults or {}
        self.version = version
        self.nombres = nombres or {2: "Productor", 3: "Veterinario", 99: "Supervisor"}
        self.guardados: list[DashboardLayout] = []
        self.actualizados: list[DashboardLayout] = []

    def obtener_por_usuario(self, id_usuario: int) -> Optional[DashboardLayout]:
        return self.existente

    def obtener_default_de_rol(self, id_usuario: int, id_rol: int) -> Optional[DashboardLayout]:
        grid = self.defaults.get(id_rol)
        if grid is None:
            return None
        return DashboardLayout(
            id_usuario=id_usuario,
            grid=list(grid),
            active_widget=[],
            fecha_actualizacion=None,
        )

    def nombre_de_rol(self, id_rol: int) -> Optional[str]:
        return self.nombres.get(id_rol)

    def version_perfil(self, id_usuario: int) -> Optional[int]:
        return self.version

    def guardar(self, entidad: DashboardLayout) -> DashboardLayout:
        self.guardados.append(entidad)
        return entidad

    def actualizar(self, entidad: DashboardLayout) -> DashboardLayout:
        self.actualizados.append(entidad)
        return entidad


class DatosRepoFake:
    def __init__(self, filas_por_fuente=None) -> None:
        self.filas_por_fuente = filas_por_fuente or {}

    def obtener(self, fuente_datos: str) -> list[dict]:
        return list(self.filas_por_fuente.get(fuente_datos, []))


def _celda(id_widget: int, fila: int, columna: int, span: int = 1, visible: bool = True,
           orden: int = 0) -> dict:
    return {
        "id_widget": id_widget,
        "posicion_fila": fila,
        "posicion_columna": columna,
        "span_columnas": span,
        "visible": visible,
        "orden": orden,
    }


def _dto(grid: list[dict], active=None, version_perfil=None) -> GuardarDashboardDTO:
    return GuardarDashboardDTO(
        layout_config=grid,
        active_widget=[] if active is None else active,
        version_perfil=version_perfil,
    )


def _use_case(db=None, dashboard_repo=None, widget_repo=None) -> GuardarDashboardUseCase:
    return GuardarDashboardUseCase(
        db=db or DbFake(),
        dashboard_repo=dashboard_repo or DashboardRepoFake(),
        widget_repo=widget_repo or WidgetRepoFake(),
    )


# ── Límite de 12 widgets activos (flujo alterno: 400) ─────────────────────────

def test_mas_de_doce_widgets_visibles_es_400_y_no_persiste() -> None:
    # 13 widgets visibles, todos en la misma celda: el límite se evalúa antes que
    # el solapamiento, así que el error que llega es el del límite.
    grid = [_celda(1, 1, 1, orden=i) for i in range(13)]
    db = DbFake()

    with pytest.raises(ValidationError) as error:
        _use_case(db=db).execute(_dto(grid), PRODUCTOR)

    assert error.value.code == "LIMITE_WIDGETS_ALCANZADO"
    assert error.value.status_code == 400
    assert "máximo de 12 elementos activos" in error.value.message
    assert "desactive un widget antes de agregar uno nuevo" in error.value.message
    assert db.commits == 0


def test_doce_widgets_visibles_es_valido() -> None:
    # La grilla 4×3 completa: 12 celdas de span 1, sin solapes. El id_widget se
    # repite a propósito — lo que se prueba es el borde del límite, no la unicidad.
    grid = [
        _celda(1, fila, columna, orden=i)
        for i, (fila, columna) in enumerate(
            [(f, c) for f in (1, 2, 3) for c in (1, 2, 3, 4)]
        )
    ]
    db = DbFake()
    repo = DashboardRepoFake()

    _use_case(db=db, dashboard_repo=repo).execute(_dto(grid), PRODUCTOR)

    assert db.commits == 1
    assert len(repo.guardados) == 1


def test_widget_oculto_no_cuenta_para_el_limite() -> None:
    grid = [_celda(1, 1, 1, visible=False, orden=i) for i in range(12)]
    grid += [_celda(2, 1, 1, orden=99)]
    db = DbFake()

    _use_case(db=db).execute(_dto(grid), PRODUCTOR)

    assert db.commits == 1


def test_active_widget_con_mas_de_doce_claves_es_400() -> None:
    # El agujero real del límite: sin grid, `active_widget` pasaba sin tope.
    claves = [w.clave for w in CATALOGO] + ["hist_hum"]
    db = DbFake()

    with pytest.raises(ValidationError) as error:
        _use_case(db=db).execute(_dto([], active=claves[:13]), PRODUCTOR)

    assert error.value.code in {"LIMITE_WIDGETS_ALCANZADO", "ACTIVE_WIDGET_DUPLICADO"}
    assert error.value.status_code == 400
    assert db.commits == 0


def test_active_widget_con_claves_repetidas_es_400() -> None:
    db = DbFake()

    with pytest.raises(ValidationError) as error:
        _use_case(db=db).execute(_dto([], active=["temp_galpon", "temp_galpon"]), PRODUCTOR)

    assert error.value.code == "ACTIVE_WIDGET_DUPLICADO"
    assert error.value.status_code == 400
    assert error.value.field == "active_widget"
    assert db.commits == 0


# ── Solapamiento de posiciones (flujo alterno: 409) ───────────────────────────

def test_dos_widgets_en_la_misma_celda_es_409() -> None:
    grid = [_celda(1, 2, 3, orden=0), _celda(2, 2, 3, orden=1)]
    db = DbFake()

    with pytest.raises(ConflictError) as error:
        _use_case(db=db).execute(_dto(grid), PRODUCTOR)

    assert error.value.code == "SOLAPAMIENTO_WIDGETS"
    assert error.value.status_code == 409
    assert "fila 2 y columna 3" in error.value.message
    assert db.commits == 0


def test_widget_dentro_del_rango_de_expansion_de_otro_es_409() -> None:
    # El widget 6 ocupa (1,1) y (1,2) por su span 2; el 2 cae dentro de ese rango.
    grid = [_celda(6, 1, 1, span=2, orden=0), _celda(2, 1, 2, orden=1)]

    with pytest.raises(ConflictError) as error:
        _use_case().execute(_dto(grid), PRODUCTOR)

    assert error.value.code == "SOLAPAMIENTO_WIDGETS"
    assert "rango de expansión de un widget adyacente" in error.value.message


def test_widget_oculto_libera_su_celda() -> None:
    # El remedio que el propio RF ofrece ("desactive un widget antes de agregar
    # uno nuevo") tiene que funcionar: apagar el de (1,1) deja poner otro ahí.
    grid = [_celda(1, 1, 1, visible=False, orden=0), _celda(2, 1, 1, orden=1)]
    db = DbFake()

    _use_case(db=db).execute(_dto(grid), PRODUCTOR)

    assert db.commits == 1


# ── Desborde horizontal por span (flujo alterno: 400) ─────────────────────────

def test_span_dos_en_la_ultima_columna_es_400() -> None:
    grid = [_celda(6, 1, 4, span=2, orden=0)]
    db = DbFake()

    with pytest.raises(ValidationError) as error:
        _use_case(db=db).execute(_dto(grid), PRODUCTOR)

    assert error.value.code == "DESBORDE_HORIZONTAL"
    assert error.value.status_code == 400
    assert error.value.field == "posicion_columna"
    assert "extensión de 2 columnas" in error.value.message
    assert "última columna (columna 4)" in error.value.message
    assert db.commits == 0


def test_span_dos_en_la_columna_tres_es_valido() -> None:
    db = DbFake()

    _use_case(db=db).execute(_dto([_celda(6, 1, 3, span=2, orden=0)]), PRODUCTOR)

    assert db.commits == 1


@pytest.mark.parametrize(
    "celda, code",
    [
        (_celda(1, 0, 1), "POSICION_FILA_INVALIDA"),
        (_celda(1, 4, 1), "POSICION_FILA_INVALIDA"),
        (_celda(1, 1, 0), "POSICION_COLUMNA_INVALIDA"),
        (_celda(1, 1, 5), "POSICION_COLUMNA_INVALIDA"),
        (_celda(1, 1, 1, span=3), "SPAN_INVALIDO"),
    ],
)
def test_el_dominio_valida_los_rangos_aunque_el_dto_ya_los_filtre(celda, code) -> None:
    # Defensa en profundidad: el DTO recorta con Field(ge/le), pero la entidad no
    # puede confiar en que siempre entre por HTTP.
    with pytest.raises(ValidationError) as error:
        DashboardLayout.crear(
            id_usuario=1,
            grid=[WidgetConfig(**celda)],
            active_widget=[],
        )

    assert error.value.code == code
    assert error.value.status_code == 400


# ── Catálogo de widgets: inexistente (400) y fuera del rol (403) ──────────────

def test_id_widget_fuera_del_catalogo_es_400() -> None:
    db = DbFake()

    with pytest.raises(ValidationError) as error:
        _use_case(db=db).execute(_dto([_celda(999, 1, 1)]), PRODUCTOR)

    assert error.value.code == "WIDGET_INEXISTENTE"
    assert error.value.status_code == 400
    assert db.commits == 0


def test_widget_que_el_rol_no_puede_leer_es_403() -> None:
    # El widget 12 (Indicadores Avicultura) vive sobre metricas_produccion, que el
    # Productor no lee.
    db = DbFake()

    with pytest.raises(AuthorizationError) as error:
        _use_case(db=db).execute(_dto([_celda(12, 1, 1)]), PRODUCTOR)

    assert error.value.code == "WIDGET_NO_AUTORIZADO"
    assert error.value.status_code == 403
    assert "no está disponible para su nivel de permisos o rol asignado" in error.value.message
    assert db.commits == 0


def test_el_mismo_widget_si_es_valido_para_un_rol_que_lo_lee() -> None:
    db = DbFake()

    _use_case(db=db).execute(_dto([_celda(12, 1, 1)]), VETERINARIO)

    assert db.commits == 1


def test_clave_de_active_widget_fuera_del_catalogo_es_400() -> None:
    db = DbFake()

    with pytest.raises(ValidationError) as error:
        _use_case(db=db).execute(_dto([], active=["widget_que_no_existe"]), PRODUCTOR)

    assert error.value.code == "ACTIVE_WIDGET_INEXISTENTE"
    assert error.value.status_code == 400
    assert db.commits == 0


def test_el_catalogo_se_filtra_por_rol() -> None:
    use_case = ObtenerCatalogoWidgetsUseCase(widget_repo=WidgetRepoFake())

    ids_productor = {w.id_widget for w in use_case.execute(PRODUCTOR)}
    ids_veterinario = {w.id_widget for w in use_case.execute(VETERINARIO)}

    assert 12 not in ids_productor and 7 in ids_productor
    assert 12 in ids_veterinario and 7 not in ids_veterinario


# ── Perfil modificado durante la edición (flujo alterno: 409) ─────────────────

def test_version_de_perfil_desfasada_es_409() -> None:
    db = DbFake()
    repo = DashboardRepoFake(version=5)

    with pytest.raises(ConflictError) as error:
        _use_case(db=db, dashboard_repo=repo).execute(
            _dto([_celda(1, 1, 1)], version_perfil=4), PRODUCTOR
        )

    assert error.value.code == "CONFLICTO_PERFIL_MODIFICADO"
    assert error.value.status_code == 409
    assert "refresque la interfaz" in error.value.message
    assert db.commits == 0


def test_sin_version_de_perfil_el_guardado_sigue_funcionando() -> None:
    db = DbFake()

    _use_case(db=db, dashboard_repo=DashboardRepoFake(version=5)).execute(
        _dto([_celda(1, 1, 1)]), PRODUCTOR
    )

    assert db.commits == 1


# ── Restaurar configuración predeterminada (flujo alterno: 500) ───────────────

def test_restaurar_sin_layout_base_del_rol_es_500_y_no_toca_la_configuracion() -> None:
    db = DbFake()
    repo = DashboardRepoFake(defaults={2: []})

    with pytest.raises(InfrastructureError) as error:
        RestaurarDashboardUseCase(db=db, dashboard_repo=repo).execute(ROL_SIN_DEFAULT)

    assert error.value.code == "RESTAURACION_SIN_DEFAULT"
    assert error.value.status_code == 500
    assert "para el rol Supervisor" in error.value.message
    assert db.commits == 0
    assert repo.guardados == [] and repo.actualizados == []


def test_restaurar_aplica_el_layout_base_del_rol() -> None:
    base = [WidgetConfig(**_celda(1, 1, 1, orden=0)), WidgetConfig(**_celda(2, 1, 2, orden=1))]
    db = DbFake()
    repo = DashboardRepoFake(defaults={2: base})

    resultado = RestaurarDashboardUseCase(db=db, dashboard_repo=repo).execute(PRODUCTOR)

    assert [w.id_widget for w in resultado.grid] == [1, 2]
    assert db.commits == 1
    assert len(repo.guardados) == 1


# ── Widget sin datos operativos (flujo alterno: fallback visual) ──────────────

def test_widget_sin_fuente_de_datos_se_marca_sin_datos_y_conserva_su_posicion() -> None:
    layout = DashboardLayout(
        id_usuario=7,
        grid=[
            WidgetConfig(**_celda(6, 1, 1, span=2, orden=0)),
            WidgetConfig(**_celda(1, 2, 1, orden=1)),
        ],
        active_widget=[],
        fecha_actualizacion=None,
    )
    use_case = ObtenerDatosDashboardUseCase(
        dashboard_repo=DashboardRepoFake(existente=layout),
        widget_repo=WidgetRepoFake(),
        datos_repo=DatosRepoFake(
            {"vw_rf28_widget_estado_dispositivos": [{"serial": "IOT-001"}]}
        ),
    )

    resultado = use_case.execute(PRODUCTOR)

    con_fuente, sin_fuente = resultado[0], resultado[1]
    assert con_fuente.clave == "estado_iot"
    assert con_fuente.sin_datos is False and con_fuente.mensaje is None
    # El widget sin fuente no desaparece ni rompe al de al lado: sigue en su celda.
    assert sin_fuente.clave == "temp_galpon"
    assert sin_fuente.sin_datos is True
    assert sin_fuente.mensaje == MENSAJE_SIN_DATOS
    assert (sin_fuente.posicion_fila, sin_fuente.posicion_columna) == (2, 1)


def test_los_widgets_ocultos_no_llegan_al_dashboard() -> None:
    layout = DashboardLayout(
        id_usuario=7,
        grid=[
            WidgetConfig(**_celda(1, 1, 1, visible=False, orden=0)),
            WidgetConfig(**_celda(2, 1, 2, orden=1)),
        ],
        active_widget=[],
        fecha_actualizacion=None,
    )
    use_case = ObtenerDatosDashboardUseCase(
        dashboard_repo=DashboardRepoFake(existente=layout),
        widget_repo=WidgetRepoFake(),
        datos_repo=DatosRepoFake(),
    )

    assert [w.clave for w in use_case.execute(PRODUCTOR)] == ["hum_galpon"]
