"""RF-47 — Ficha integral: densidad real (Sección 7), accesos directos
filtrados por permisos (Sección 8) y fallo parcial de la vista base (E-03).
"""
from __future__ import annotations

import contextlib
from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy.exc import ProgrammingError

from src.biological_assets.application.use_cases.gestion.consultar_ficha_integral_use_case import (
    ConsultarFichaIntegralUseCase,
)
from src.biological_assets.domain.entities.activo_biologico import ActivoBiologico, DetallePoblacional
from src.biological_assets.infrastructure.routers import activo_biologico_router as modulo_router
from src.biological_assets.infrastructure.routers.activo_biologico_router import (
    _ACCESOS_DIRECTOS_FICHA,
    _RECURSO,
    _accesos_directos_ficha,
    router,
)
from src.identity_access.infrastructure.dependencies import UsuarioActual

USUARIO = UsuarioActual(id_usuario=7, id_token=1, id_rol=2)


def _activo(tipo: str = 'INDIVIDUAL', densidad: Decimal | None = None) -> ActivoBiologico:
    return ActivoBiologico(
        id_especie=1,
        tipo=tipo,
        origen_financiero='compra',
        id_infraestructura=1,
        id_estado=1,
        id_usuario=1,
        id_activo_biologico=10,
        fecha_inicio_ciclo=date(2026, 1, 1),
        fecha_creacion=datetime(2026, 1, 1, tzinfo=timezone.utc),
        detalle_poblacional=(
            DetallePoblacional(cantidad_inicial=100, cantidad_actual=80, densidad=densidad)
            if tipo == 'POBLACIONAL' else None
        ),
    )


class _ActivoRepo:
    def __init__(self, activo: ActivoBiologico) -> None:
        self.activo = activo

    def obtener_por_id(self, _id: int, *, ids_fincas_permitidas=None):
        return self.activo


def _fila_base(tipo: str = 'INDIVIDUAL') -> SimpleNamespace:
    return SimpleNamespace(
        codigo='A-10', tipo=tipo, especie='Bovino', fecha_registro=None, dias_en_sistema=1,
        estado_actual='ACTIVO', infraestructura_asociada=None, fase_productiva_activa=None, raza=None,
        sexo=None, fecha_nacimiento=None, peso_actual=None, unidad_peso=None, fecha_ultimo_peso=None,
        cantidad_actual=80 if tipo == 'POBLACIONAL' else None, biomasa_total=None,
    )


class _Db:
    """Vista base configurable; las vistas de secciones responden vacío salvo las que fallan."""

    def __init__(self, fila_base=None, vistas_caidas: tuple[str, ...] = ()) -> None:
        self.fila_base = fila_base
        self.vistas_caidas = vistas_caidas

    def begin_nested(self):
        return contextlib.nullcontext()

    def execute(self, sentencia, _params=None):
        sql = str(sentencia)
        for vista in self.vistas_caidas:
            if vista in sql:
                raise ProgrammingError(sql, {}, Exception('relation does not exist'))
        if 'vw_rf47_ficha_integral_activo' in sql:
            return SimpleNamespace(fetchone=lambda: self.fila_base)
        return SimpleNamespace(fetchall=lambda: [])


def _ficha(activo: ActivoBiologico, db: _Db):
    return ConsultarFichaIntegralUseCase(db=db, activo_repo=_ActivoRepo(activo)).execute(10, USUARIO)


# ── Sección 7: densidad ──────────────────────────────────────────────────────

def test_lote_expone_la_densidad_del_detalle_poblacional() -> None:
    ficha = _ficha(_activo('POBLACIONAL', Decimal('2.5000')), _Db(_fila_base('POBLACIONAL')))

    assert ficha.densidad == Decimal('2.5000')
    assert ficha.cantidad_actual == 80


def test_activo_individual_no_tiene_densidad() -> None:
    ficha = _ficha(_activo('INDIVIDUAL'), _Db(_fila_base()))

    assert ficha.densidad is None


# ── E-03: la vista base también es una sección que puede fallar sola ────────

def test_vista_base_caida_no_tumba_la_ficha() -> None:
    db = _Db(vistas_caidas=('vw_rf47_ficha_integral_activo',))
    activo = _activo('POBLACIONAL', Decimal('2.5000'))

    ficha = _ficha(activo, db)

    assert ficha.identificador == activo.identificador
    assert ficha.tipo == 'POBLACIONAL'
    assert ficha.densidad == Decimal('2.5000')
    assert ficha.advertencias == ['La sección Datos generales no pudo cargarse en este momento.']


def test_vista_base_sin_fila_conserva_el_aviso_generico_junto_a_otras_secciones_caidas() -> None:
    db = _Db(fila_base=None, vistas_caidas=('vw_rf46_eventos_sanitarios',))

    ficha = _ficha(_activo(), db)

    assert ficha.advertencias == [
        'La sección Eventos sanitarios no pudo cargarse en este momento.',
        'No se pudo cargar la información completa del activo.',
    ]


# ── Sección 8: accesos directos filtrados por permisos ──────────────────────

@pytest.fixture
def permisos(monkeypatch):
    concedidos: set[int] = set()

    def _tiene_permiso(_db, _id_rol, id_recurso, id_accion):
        return id_recurso == _RECURSO and id_accion in concedidos

    monkeypatch.setattr(modulo_router, 'tiene_permiso', _tiene_permiso)
    return concedidos


def _codigos(accesos) -> list[str]:
    return [a.codigo for a in accesos]


def test_rol_con_todos_los_permisos_ve_los_cuatro_accesos(permisos) -> None:
    permisos.update({1, 2, 5})

    accesos = _accesos_directos_ficha(None, USUARIO, 10)

    assert _codigos(accesos) == ['historial', 'registrar_evento', 'cambiar_estado', 'registrar_baja']


def test_rol_solo_lectura_solo_ve_el_historial(permisos) -> None:
    permisos.add(2)

    assert _codigos(_accesos_directos_ficha(None, USUARIO, 10)) == ['historial']


def test_rol_sin_ejecutar_no_ve_cambiar_estado(permisos) -> None:
    permisos.update({1, 2})

    assert 'cambiar_estado' not in _codigos(_accesos_directos_ficha(None, USUARIO, 10))


def test_rutas_del_acceso_apuntan_al_activo_consultado(permisos) -> None:
    permisos.update({1, 2, 5})

    accesos = {a.codigo: a for a in _accesos_directos_ficha(None, USUARIO, 42)}

    assert accesos['historial'].ruta == '/activos-biologicos/42/historial'
    assert accesos['registrar_baja'].ruta == '/activos-biologicos/42/eventos/baja'
    assert accesos['registrar_evento'].ruta == '/activos-biologicos/42/eventos/{tipo_evento}'
    assert accesos['registrar_evento'].tipos_evento == ['crecimiento', 'sanitario', 'reproductivo', 'productivo']


def _permiso_de_ruta(metodo: str, ruta: str) -> tuple[int, int]:
    ruta_router = next(
        r for r in router.routes
        if getattr(r, 'path', None) == ruta and metodo in getattr(r, 'methods', set())
    )
    dep = next(d.call for d in ruta_router.dependant.dependencies if hasattr(d.call, 'id_accion'))
    return dep.id_recurso, dep.id_accion


def test_cada_acceso_exige_el_mismo_permiso_que_su_endpoint() -> None:
    """Si alguien cambia el permiso de un endpoint, la Sección 8 no puede quedar ofreciendo un 403."""
    for codigo, _nombre, metodo, ruta, _rf, id_accion, tipos_evento in _ACCESOS_DIRECTOS_FICHA:
        plantilla = ruta.replace('{id}', '{id_activo}')
        rutas = [plantilla.replace('{tipo_evento}', t) for t in tipos_evento] if tipos_evento else [plantilla]
        for r in rutas:
            assert _permiso_de_ruta(metodo, r) == (_RECURSO, id_accion), f'{codigo}: {metodo} {r}'


def test_la_ficha_declara_la_seccion_8_en_su_respuesta() -> None:
    ruta = next(r for r in router.routes if getattr(r, 'path', None) == '/activos-biologicos/{id_activo}/ficha-integral')
    assert 'accesos_directos' in ruta.response_model.model_fields
