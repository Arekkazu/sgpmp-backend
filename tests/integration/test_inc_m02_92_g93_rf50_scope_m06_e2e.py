"""[INC-M02-92-G93][RF-50][TC-M02-155] Verifica contra la base real que el
rol 'Integración M06' (ver INC-M02-93-G93 / #391) tiene exactamente el scope
que QA necesitaba para poder construir el escenario bloqueado:

    módulo autenticado = Sí
    scope general válido = Sí (recurso 29, acción R)
    scope para tipo_dato='metricas' = Sí
    scope para tipo_dato en {eventos, fases, estado} = No -> 403 esperado

Antes de este PR era imposible construir esta precondición con el modelo
RBAC existente (solo (recurso, acción) por endpoint completo).
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.biological_assets.infrastructure.routers.activo_biologico_router import (
    _TIPOS_DATO_CON_SCOPE,
    _verificar_scope_tipo_dato,
)
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import AuthorizationError


def _rol_m06(db_session: Session) -> int:
    id_rol = db_session.execute(
        text("SELECT id_rol FROM modulo1.roles WHERE nombre_rol = 'Integración M06'")
    ).scalar_one_or_none()
    assert id_rol is not None, "Falta el rol 'Integración M06' (ver INC-M02-93-G93 / #391)"
    return id_rol


def test_m06_tiene_scope_de_metricas(db_session: Session) -> None:
    usuario = UsuarioActual(id_usuario=1, id_token=1, id_rol=_rol_m06(db_session))

    _verificar_scope_tipo_dato(db_session, usuario, 'metricas')  # no debe lanzar


def test_m06_no_tiene_scope_de_eventos_fases_ni_estado(db_session: Session) -> None:
    usuario = UsuarioActual(id_usuario=1, id_token=1, id_rol=_rol_m06(db_session))

    for tipo in ('eventos', 'fases', 'estado'):
        try:
            _verificar_scope_tipo_dato(db_session, usuario, tipo)
        except AuthorizationError as exc:
            assert exc.code == 'SCOPE_TIPO_DATO_NO_AUTORIZADO'
            assert tipo in exc.message
        else:
            raise AssertionError(f"Se esperaba 403 para tipo_dato={tipo!r}")


def test_m06_pedir_todos_rechaza_por_scope_incompleto(db_session: Session) -> None:
    usuario = UsuarioActual(id_usuario=1, id_token=1, id_rol=_rol_m06(db_session))

    try:
        _verificar_scope_tipo_dato(db_session, usuario, 'todos')
    except AuthorizationError as exc:
        assert exc.code == 'SCOPE_TIPO_DATO_NO_AUTORIZADO'
    else:
        raise AssertionError("Se esperaba 403: M06 no tiene los 4 scopes que exige tipo_dato='todos'")


def test_recursos_granulares_existen_en_modulo1_recursos(db_session: Session) -> None:
    for tipo in _TIPOS_DATO_CON_SCOPE:
        id_recurso = db_session.execute(
            text("SELECT id_recurso FROM modulo1.recursos WHERE nombre_recurso = :nombre"),
            {"nombre": f"datos_consolidados_{tipo}"},
        ).scalar_one_or_none()
        assert id_recurso is not None, f"Falta el recurso 'datos_consolidados_{tipo}'"
