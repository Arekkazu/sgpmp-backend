"""RF-25 — el contexto de interfaz entrega la identidad visual y su contraste.

RF-26 exige que "los usuarios visualizarán la identidad visual actualizada en sus
sesiones activas o al iniciar sesión nuevamente" y que los cambios se apliquen "de forma
consistente en todos los componentes de la interfaz". Eso no era posible: la identidad
visual vive en el recurso 23, que en `modulo1.permisos` solo tiene permisos para el rol
Administrador (ids 122-124), y está claveada por `id_finca`, que ningún endpoint le
revelaba a un usuario no administrador. Un Productor no tenía forma de leer su propia
marca institucional.

El contexto de RF-25 (recurso 22) es el único endpoint de los tres RF que **todos** los
roles pueden leer y el único que resuelve usuario -> finca, así que la marca y su
evaluación de contraste WCAG (RF-27) viajan ahí. No se añadió ningún permiso: la
autorización de escritura sigue siendo exclusiva del recurso 23.

Verifica con fakes (sin BD; modulo9 no existe en la BD `pruebas`).
"""
from __future__ import annotations

from collections.abc import Generator
from typing import Optional

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.configuration.application.use_cases.personalizacion.obtener_contexto_use_case import (
    ObtenerContextoUseCase,
)
from src.configuration.domain.entities.contexto_interfaz import ContextoInterfaz
from src.configuration.domain.entities.identidad_visual import IdentidadVisual
from src.configuration.domain.value_objects.color_hex import ColorHex
from src.configuration.domain.value_objects.nombre_organizacion import NombreOrganizacion
from src.configuration.infrastructure.routers.contexto_interfaz_router import router
from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.shared.database import get_db
from src.shared.error_handlers import register_error_handlers

ADMIN = UsuarioActual(id_usuario=1, id_token=1, id_rol=1, id_estado_cuenta=2)
PRODUCTOR = UsuarioActual(id_usuario=7, id_token=1, id_rol=2, id_estado_cuenta=2)
CONTADOR = UsuarioActual(id_usuario=9, id_token=1, id_rol=5, id_estado_cuenta=2)
SIN_PERMISO = UsuarioActual(id_usuario=10, id_token=1, id_rol=6, id_estado_cuenta=2)
CUENTA_PENDIENTE = UsuarioActual(id_usuario=11, id_token=1, id_rol=2, id_estado_cuenta=1)

# (id_rol, id_recurso, id_accion) activos, copiados de modulo1.permisos: el recurso 22
# lo leen los roles 1-5; el rol 6 (Supervisor) no tiene ninguna fila.
PERMISOS_REALES = {(rol, 22, 2) for rol in (1, 2, 3, 4, 5)}


def _identidad(
    primary: Optional[str] = "#1A6B3C",
    secondary: Optional[str] = "#A8D5B5",
    nombre: Optional[str] = "Acuicola El Remanso",
) -> IdentidadVisual:
    return IdentidadVisual(
        id_identidad_visual=1,
        id_finca=1,
        id_usuario=1,
        logo_path="/uploads/logos/remanso.png",
        primary_color=ColorHex(primary) if primary else None,
        secondary_color=ColorHex(secondary) if secondary else None,
        org_display_name=NombreOrganizacion(nombre) if nombre else None,
        version=2,
        fecha_creacion=None,
    )


def _contexto(id_finca: Optional[int] = 1) -> ContextoInterfaz:
    return ContextoInterfaz(
        id_usuario=7,
        nombre_completo="Ana Garcia",
        id_rol=2,
        nombre_rol="Productor",
        id_finca=id_finca,
        finca_activa="Finca El Remanso" if id_finca else None,
        departamento="Cundinamarca" if id_finca else None,
        especies_configuradas=["Tilapia"] if id_finca else [],
        modulos_autorizados=["fincas", "contexto_interfaz"],
    )


class ContextoRepoFake:
    def __init__(self, contexto: ContextoInterfaz) -> None:
        self.contexto = contexto

    def obtener_por_usuario(self, id_usuario: int, id_rol: int) -> ContextoInterfaz:
        return self.contexto


class IdentidadRepoFake:
    """Fake del puerto. Registra las fincas consultadas para verificar que no se lee de más."""

    def __init__(self, identidad: Optional[IdentidadVisual] = None) -> None:
        self.identidad = identidad
        self.consultas: list[int] = []

    def obtener_por_finca(self, id_finca: int) -> Optional[IdentidadVisual]:
        self.consultas.append(id_finca)
        return self.identidad

    def guardar(self, entidad):  # pragma: no cover - no se usa en lectura
        raise AssertionError("el contexto no debe escribir identidad visual")

    def actualizar(self, entidad):  # pragma: no cover - no se usa en lectura
        raise AssertionError("el contexto no debe escribir identidad visual")


# ---- El caso de uso ---- #

def test_el_contexto_resuelve_la_identidad_de_la_finca_activa() -> None:
    identidad_repo = IdentidadRepoFake(_identidad())
    caso = ObtenerContextoUseCase(ContextoRepoFake(_contexto()), identidad_repo)

    contexto = caso.execute(PRODUCTOR)

    assert identidad_repo.consultas == [1]
    assert contexto.identidad_visual is identidad_repo.identidad
    assert contexto.accesibilidad is not None


def test_el_contexto_evalua_el_contraste_de_los_dos_colores() -> None:
    """El cliente necesita la variante accesible para pintar, no solo el color guardado."""
    caso = ObtenerContextoUseCase(ContextoRepoFake(_contexto()), IdentidadRepoFake(_identidad()))

    accesibilidad = caso.execute(PRODUCTOR).accesibilidad

    assert accesibilidad.primary_color.oscuro.cumple_aa is False
    assert accesibilidad.primary_color.oscuro.color_ajustado != "#1A6B3C"
    assert accesibilidad.secondary_color.claro.cumple_aa is False


def test_usuario_sin_finca_no_consulta_identidad_visual() -> None:
    """Flujo alterno "Usuario sin finca asociada": 200 con contexto vacio, no un error."""
    identidad_repo = IdentidadRepoFake(_identidad())
    caso = ObtenerContextoUseCase(ContextoRepoFake(_contexto(id_finca=None)), identidad_repo)

    contexto = caso.execute(PRODUCTOR)

    assert identidad_repo.consultas == []
    assert contexto.identidad_visual is None
    assert contexto.accesibilidad is None


def test_finca_sin_identidad_configurada_devuelve_nulos() -> None:
    """La finca existe pero nadie configuro su marca: el cliente cae a la suya por defecto."""
    caso = ObtenerContextoUseCase(ContextoRepoFake(_contexto()), IdentidadRepoFake(None))

    contexto = caso.execute(PRODUCTOR)

    assert contexto.identidad_visual is None
    assert contexto.accesibilidad is None


def test_identidad_solo_con_logotipo_no_rompe_el_contexto() -> None:
    """Las tres columnas de color y nombre son nullable en modulo9.identidad_visuales."""
    identidad = _identidad(primary=None, secondary=None, nombre=None)
    caso = ObtenerContextoUseCase(ContextoRepoFake(_contexto()), IdentidadRepoFake(identidad))

    contexto = caso.execute(PRODUCTOR)

    assert contexto.identidad_visual.logo_path == "/uploads/logos/remanso.png"
    assert contexto.accesibilidad.primary_color is None


# ---- La consulta contra la vista ---- #

class _Resultado:
    def __init__(self, fila: Optional[dict]) -> None:
        self._fila = fila

    def mappings(self):
        return self

    def first(self):
        return self._fila

    def all(self):
        return []


class SesionFake:
    """Captura el SQL emitido, para fijar las dos roturas que tenia esta consulta."""

    def __init__(self, fila: Optional[dict]) -> None:
        self.fila = fila
        self.sentencias: list[str] = []

    def execute(self, sentencia, parametros=None):
        texto = str(sentencia)
        self.sentencias.append(texto)
        # La primera consulta es la de la vista; la segunda, la de modulos autorizados.
        return _Resultado(self.fila if "vw_rf25_contexto_usuario" in texto else None)


FILA_VISTA = {
    "id_usuario": 2,
    "nombre_completo": "Laura Gomez Torres",
    "id_rol": 2,
    "nombre_rol": "Productor",
    "id_finca": 1,
    "finca_activa": "Finca Acuicola El Remanso",
    "departamento": "Huila",
    "especies_configuradas": ["Cachama Blanca", "Trucha Arcoiris"],
}


def _sql_de_la_vista(sesion: SesionFake) -> str:
    return next(s for s in sesion.sentencias if "vw_rf25_contexto_usuario" in s)


def test_la_consulta_usa_el_nombre_real_de_la_columna_de_especies() -> None:
    """El endpoint respondia 500: la vista expone `especies_en_finca`, no el alias.

    `modulo9.vw_rf25_contexto_usuario` nunca tuvo una columna `especies_configuradas`,
    asi que la consulta fallaba con ProgrammingError contra la base real. Los fakes de
    las demas pruebas no lo detectaban porque nadie ejecutaba el SQL de verdad.
    """
    from src.configuration.infrastructure.repositories.contexto_interfaz_repository import (
        SqlAlchemyContextoInterfazRepository,
    )

    sesion = SesionFake(FILA_VISTA)
    SqlAlchemyContextoInterfazRepository(sesion).obtener_por_usuario(id_usuario=2, id_rol=2)

    sql = _sql_de_la_vista(sesion)
    assert "especies_en_finca AS especies_configuradas" in sql


def test_la_consulta_fija_un_orden_deterministico() -> None:
    """La vista emite una fila por finca activa del usuario.

    Sin ORDER BY, `.first()` devolvia la que Postgres quisiera: la "finca activa" podia
    cambiar entre dos peticiones seguidas y con ella la marca institucional de RF-26.
    """
    from src.configuration.infrastructure.repositories.contexto_interfaz_repository import (
        SqlAlchemyContextoInterfazRepository,
    )

    sesion = SesionFake(FILA_VISTA)
    SqlAlchemyContextoInterfazRepository(sesion).obtener_por_usuario(id_usuario=2, id_rol=2)

    assert "ORDER BY id_finca" in _sql_de_la_vista(sesion)


def test_la_fila_de_la_vista_se_mapea_al_read_model() -> None:
    from src.configuration.infrastructure.repositories.contexto_interfaz_repository import (
        SqlAlchemyContextoInterfazRepository,
    )

    sesion = SesionFake(FILA_VISTA)
    contexto = SqlAlchemyContextoInterfazRepository(sesion).obtener_por_usuario(
        id_usuario=2, id_rol=2
    )

    assert contexto.id_finca == 1
    assert contexto.finca_activa == "Finca Acuicola El Remanso"
    assert contexto.especies_configuradas == ["Cachama Blanca", "Trucha Arcoiris"]


# ---- El endpoint, con la compuerta RBAC real ---- #

class _Query:
    """Reproduce `db.query(Permisos).filter(...).first()` sobre la matriz fake."""

    def __init__(self, usuario: UsuarioActual) -> None:
        self.usuario = usuario
        self.criterios: list = []

    def filter(self, *criterios):
        self.criterios.extend(criterios)
        return self

    def first(self):
        # require_permission filtra por id_rol, id_recurso, id_accion y es_activo.
        # Solo los tres primeros llevan un literal entero al lado derecho.
        valores = [
            c.right.value
            for c in self.criterios
            if getattr(getattr(c, "right", None), "value", None) is not None
        ]
        _rol, recurso, accion = valores[-3:]
        return object() if (self.usuario.id_rol, recurso, accion) in PERMISOS_REALES else None


class DbFake:
    def __init__(self, usuario: UsuarioActual) -> None:
        self.usuario = usuario

    def query(self, *_args):
        return _Query(self.usuario)


def _client(
    usuario: Optional[UsuarioActual],
    identidad: Optional[IdentidadVisual] = None,
    id_finca: Optional[int] = 1,
) -> Generator[TestClient, None, None]:
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(router)

    if usuario is not None:
        app.dependency_overrides[get_current_user] = lambda: usuario
        app.dependency_overrides[get_db] = lambda: DbFake(usuario)

    # El router construye los repositorios concretos con la sesión; aquí se sustituye el
    # caso de uso completo para que la prueba no toque SQLAlchemy.
    import src.configuration.infrastructure.routers.contexto_interfaz_router as modulo

    original = modulo.ObtenerContextoUseCase
    modulo.ObtenerContextoUseCase = lambda **_kwargs: ObtenerContextoUseCase(
        ContextoRepoFake(_contexto(id_finca=id_finca)), IdentidadRepoFake(identidad)
    )
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            yield client
    finally:
        modulo.ObtenerContextoUseCase = original
        app.dependency_overrides.clear()


@pytest.fixture
def cliente_productor() -> Generator[TestClient, None, None]:
    yield from _client(PRODUCTOR, _identidad())


def test_el_productor_recibe_la_marca_institucional_de_su_finca(
    cliente_productor: TestClient,
) -> None:
    """El motivo de haber puesto la marca aquí y no en el recurso 23, que es solo de admin."""
    cuerpo = cliente_productor.get("/configuracion/interfaz/contexto").json()

    assert cuerpo["identidad_visual"] == {
        "logo_path": "/uploads/logos/remanso.png",
        "primary_color": "#1A6B3C",
        "secondary_color": "#A8D5B5",
        "org_display_name": "Acuicola El Remanso",
    }


def test_la_respuesta_trae_las_variantes_de_los_dos_temas(
    cliente_productor: TestClient,
) -> None:
    """Con theme_mode=3 (Sistema) el tema efectivo cambia en el cliente sin nueva petición."""
    accesibilidad = cliente_productor.get("/configuracion/interfaz/contexto").json()["accesibilidad"]

    assert accesibilidad["minimo_aa"] == 4.5
    assert set(accesibilidad["primary_color"]) == {"claro", "oscuro"}
    assert accesibilidad["primary_color"]["oscuro"]["cumple_aa"] is False
    assert accesibilidad["primary_color"]["oscuro"]["aviso"].startswith("Aviso de accesibilidad:")
    assert accesibilidad["primary_color"]["claro"]["aviso"] is None


def test_el_contexto_no_expone_ids_internos_de_la_identidad(
    cliente_productor: TestClient,
) -> None:
    """Quien lee el contexto pinta la interfaz; administrar el registro sigue en el recurso 23."""
    identidad = cliente_productor.get("/configuracion/interfaz/contexto").json()["identidad_visual"]

    assert "id_identidad_visual" not in identidad
    assert "version" not in identidad


@pytest.mark.parametrize("usuario", [ADMIN, PRODUCTOR, CONTADOR])
def test_todos_los_roles_con_permiso_r_pasan_la_compuerta(usuario: UsuarioActual) -> None:
    for cliente in _client(usuario, _identidad()):
        assert cliente.get("/configuracion/interfaz/contexto").status_code == 200


def test_rol_sin_permiso_sobre_el_recurso_22_es_403() -> None:
    """Exponer la marca aquí no puede abrir el endpoint a quien no lo tenía."""
    for cliente in _client(SIN_PERMISO, _identidad()):
        respuesta = cliente.get("/configuracion/interfaz/contexto")
        assert respuesta.status_code == 403
        assert respuesta.json()["error_code"] == "ACCESO_DENEGADO"


def test_cuenta_no_activa_es_403_antes_de_mirar_permisos() -> None:
    for cliente in _client(CUENTA_PENDIENTE, _identidad()):
        respuesta = cliente.get("/configuracion/interfaz/contexto")
        assert respuesta.status_code == 403
        assert respuesta.json()["error_code"] == "CUENTA_NO_ACTIVA"


def test_sin_token_es_401() -> None:
    for cliente in _client(None):
        assert cliente.get("/configuracion/interfaz/contexto").status_code == 401


def test_usuario_sin_finca_responde_200_con_la_marca_en_nulo() -> None:
    """La vista de bienvenida del RF-25 se decide en el cliente, no con un error HTTP."""
    for cliente in _client(PRODUCTOR, _identidad(), id_finca=None):
        cuerpo = cliente.get("/configuracion/interfaz/contexto").json()
        assert cuerpo["id_finca"] is None
        assert cuerpo["identidad_visual"] is None
        assert cuerpo["accesibilidad"] is None
