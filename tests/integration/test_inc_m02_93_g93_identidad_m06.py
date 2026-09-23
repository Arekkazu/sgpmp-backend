"""[INC-M02-93-G93][RF-50][TC-M02-157] M06 no estaba disponible como
consumidor autenticable de los endpoints analíticos de M02 — el mecanismo de
autorización es JWT de usuario + rol, no identidad de módulo, y no existía
ningún principal que representara a M06.

Mismo patrón ya usado para M04 (INC-M02-90-G92): en vez de construir un
mecanismo M2M nuevo, se reutiliza RBAC con un rol técnico dedicado
('Integración M06') y un usuario técnico de solo lectura sobre el recurso
que protege `datos-consolidados` (29, acción 2 = Leer). Detalle completo en
`anotaciones/modulo_2/inc_m02_93_g93_rf50_identidad_m06.md`.

Esta prueba verifica el hecho nuevo (la identidad existe y tiene el permiso
correcto) contra la base real, sin reconstruir el flujo de login/JWT/HTTP,
que ya está cubierto por las pruebas de `identity_access`.
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.shared.rbac import tiene_permiso

_RECURSO_ACTIVOS_BIOLOGICOS = 29
_ACCION_LEER = 2


def test_rol_integracion_m06_existe_y_no_es_protegido(db_session: Session) -> None:
    fila = db_session.execute(
        text("SELECT id_rol, es_protegido FROM modulo1.roles WHERE nombre_rol = 'Integración M06'")
    ).mappings().first()

    assert fila is not None, "Falta el rol 'Integración M06' (INC-M02-93-G93)"
    assert fila["es_protegido"] is False


def test_rol_integracion_m06_puede_leer_datos_consolidados(db_session: Session) -> None:
    id_rol = db_session.execute(
        text("SELECT id_rol FROM modulo1.roles WHERE nombre_rol = 'Integración M06'")
    ).scalar_one()

    assert tiene_permiso(db_session, id_rol, _RECURSO_ACTIVOS_BIOLOGICOS, _ACCION_LEER) is True


def test_usuario_tecnico_m06_existe_y_tiene_cuenta_activa(db_session: Session) -> None:
    fila = db_session.execute(
        text(
            "SELECT u.id_rol, c.id_estado_cuenta, c.tiene_correo_verificado, r.nombre_rol "
            "FROM modulo1.usuarios u "
            "JOIN modulo1.cuentas_usuarios c ON c.id_usuario = u.id_usuario "
            "JOIN modulo1.roles r ON r.id_rol = u.id_rol "
            "WHERE u.correo_electronico = 'integracion.m06.test@pecuaria.co'"
        )
    ).mappings().first()

    assert fila is not None, "Falta el usuario técnico integracion.m06.test@pecuaria.co"
    assert fila["nombre_rol"] == 'Integración M06'
    assert fila["id_estado_cuenta"] == 2  # activa — sin esto el login falla (RF-02)
    assert fila["tiene_correo_verificado"] is True
