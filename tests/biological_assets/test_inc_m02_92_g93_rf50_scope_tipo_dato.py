"""[INC-M02-92-G93][RF-50][TC-M02-155] No existía forma de representar un
consumidor de módulo con credencial válida pero sin scope para un
`tipo_dato` específico de `datos-consolidados` — el RBAC de este proyecto
es por (recurso, acción) a nivel de endpoint completo, no por parámetro de
query.

Se extiende con 4 recursos RBAC granulares (uno por `tipo_dato`:
eventos/fases/estado/metricas en `modulo1.recursos`, resueltos por nombre —
ver el comentario en el router sobre por qué no por id numérico) verificados
además del permiso base del endpoint. Detalle completo de la decisión en
`anotaciones/modulo_2/inc_m02_92_g93_rf50_scope_tipo_dato.md`.
"""
from __future__ import annotations

import pytest

from src.biological_assets.infrastructure.routers.activo_biologico_router import (
    _TIPOS_DATO_CON_SCOPE,
    _verificar_scope_tipo_dato,
)
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import AuthorizationError

_ID_RECURSO_FAKE = {'eventos': 1001, 'fases': 1002, 'estado': 1003, 'metricas': 1004}


class DbFake:
    """No se usa directamente: tanto la resolución de `id_recurso` por
    nombre como `tiene_permiso` se monkeypatchean en cada prueba."""


def _usuario(id_rol: int = 99) -> UsuarioActual:
    return UsuarioActual(id_usuario=1, id_token=1, id_rol=id_rol)


def _parchear_resolucion_de_recurso(monkeypatch: pytest.MonkeyPatch, router_mod) -> None:
    monkeypatch.setattr(
        router_mod, '_id_recurso_datos_consolidados',
        lambda _db, tipo: _ID_RECURSO_FAKE[tipo],
    )


def test_tipos_dato_con_scope_cubre_los_valores_del_dto_menos_todos() -> None:
    from src.biological_assets.infrastructure.dto.datos_consolidados_dto import _TIPOS_DATO

    assert set(_TIPOS_DATO_CON_SCOPE) == _TIPOS_DATO - {'todos'}


def test_con_scope_completo_no_rechaza(monkeypatch: pytest.MonkeyPatch) -> None:
    import src.biological_assets.infrastructure.routers.activo_biologico_router as router_mod

    _parchear_resolucion_de_recurso(monkeypatch, router_mod)
    monkeypatch.setattr(router_mod, 'tiene_permiso', lambda *a, **k: True)

    _verificar_scope_tipo_dato(DbFake(), _usuario(), 'todos')  # no debe lanzar


def test_sin_scope_de_un_tipo_especifico_responde_403(monkeypatch: pytest.MonkeyPatch) -> None:
    import src.biological_assets.infrastructure.routers.activo_biologico_router as router_mod

    _parchear_resolucion_de_recurso(monkeypatch, router_mod)
    monkeypatch.setattr(router_mod, 'tiene_permiso', lambda *a, **k: False)

    with pytest.raises(AuthorizationError) as exc:
        _verificar_scope_tipo_dato(DbFake(), _usuario(), 'metricas')

    assert exc.value.code == 'SCOPE_TIPO_DATO_NO_AUTORIZADO'
    assert 'metricas' in exc.value.message


def test_recurso_inexistente_se_trata_como_sin_permiso(monkeypatch: pytest.MonkeyPatch) -> None:
    """Si el recurso granular no está sembrado en esta base, no se debe fallar
    abierto — se trata igual que no tener el permiso (403), nunca como 200."""
    import src.biological_assets.infrastructure.routers.activo_biologico_router as router_mod

    monkeypatch.setattr(router_mod, '_id_recurso_datos_consolidados', lambda _db, _tipo: None)
    monkeypatch.setattr(router_mod, 'tiene_permiso', lambda *a, **k: True)

    with pytest.raises(AuthorizationError) as exc:
        _verificar_scope_tipo_dato(DbFake(), _usuario(), 'eventos')

    assert exc.value.code == 'SCOPE_TIPO_DATO_NO_AUTORIZADO'


def test_scope_parcial_para_todos_rechaza_en_la_primera_seccion_sin_permiso(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Simula el caso real de M06: tiene 'metricas' pero no el resto — pedir
    tipo_dato='todos' debe rechazarse igual que pedir una sección puntual sin
    scope, no degradarse silenciosamente a lo que sí tiene permitido."""
    import src.biological_assets.infrastructure.routers.activo_biologico_router as router_mod

    _parchear_resolucion_de_recurso(monkeypatch, router_mod)
    id_recurso_metricas = _ID_RECURSO_FAKE['metricas']
    monkeypatch.setattr(
        router_mod, 'tiene_permiso',
        lambda _db, _id_rol, id_recurso, _id_accion: id_recurso == id_recurso_metricas,
    )

    with pytest.raises(AuthorizationError) as exc:
        _verificar_scope_tipo_dato(DbFake(), _usuario(), 'todos')

    assert exc.value.code == 'SCOPE_TIPO_DATO_NO_AUTORIZADO'


def test_scope_de_metricas_solo_no_afecta_pedir_solo_metricas(monkeypatch: pytest.MonkeyPatch) -> None:
    import src.biological_assets.infrastructure.routers.activo_biologico_router as router_mod

    _parchear_resolucion_de_recurso(monkeypatch, router_mod)
    id_recurso_metricas = _ID_RECURSO_FAKE['metricas']
    monkeypatch.setattr(
        router_mod, 'tiene_permiso',
        lambda _db, _id_rol, id_recurso, _id_accion: id_recurso == id_recurso_metricas,
    )

    _verificar_scope_tipo_dato(DbFake(), _usuario(), 'metricas')  # no debe lanzar
