# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-20 | Arekkazu | DEV-18 RF-01: rango de edad [18, 100) en registro y perfil |
"""DEV-18 (RFC-013): la edad válida es [18, 100), en el registro (403) y en la
edición de perfil (400), con una sola guarda en la entidad ``Usuario``."""
from __future__ import annotations

from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from src.identity_access.application.use_cases.registro import crear_usuario_use_case as modulo
from src.identity_access.domain.entities.usuario import Usuario
from src.shared.errors import AuthorizationError

HOY = date(2026, 10, 20)


def _hace(anios: int, dias: int = 0) -> date:
    return HOY.replace(year=HOY.year - anios) - timedelta(days=dias)


@pytest.mark.parametrize(
    ("nacimiento", "esperado"),
    [
        (_hace(17), "MINIMA"),
        (_hace(18), None),            # cumple 18 hoy
        (_hace(99), None),
        (_hace(100, -1), None),       # cumple 100 mañana: todavía tiene 99
        (_hace(100), "MAXIMA"),       # cumple 100 hoy
        (_hace(101), "MAXIMA"),
        (HOY + timedelta(days=1), "MINIMA"),  # fecha futura
    ],
    ids=["17", "18-hoy", "99", "99-vispera-de-100", "100-hoy", "101", "futura"],
)
def test_limite_edad_incumplido(nacimiento, esperado):
    assert Usuario.limite_edad_incumplido(nacimiento, HOY) == esperado


class _Db:
    commits = 0

    def commit(self):
        self.commits += 1

    def rollback(self):
        pass


def _registrar(fecha_nacimiento: date):
    db = _Db()
    uc = modulo.CrearUsuarioUseCase(
        usuarios_repo=SimpleNamespace(guardar=lambda u: u),
        cuentas_repo=SimpleNamespace(crear=lambda *_a, **_k: None),
        eventos_repo=SimpleNamespace(registrar=lambda **_k: None),
        captcha_verifier=SimpleNamespace(verificar=lambda *_a, **_k: True),
        db=db,
        notificacion_service=SimpleNamespace(notificar=lambda **_k: True),
    )
    dto = SimpleNamespace(
        correo_electronico="ana@example.com", contrasena="Contrasena1!", confirmar_contrasena="Contrasena1!",
        nombre="Ana", apellidos="Pérez", fecha_nacimiento=fecha_nacimiento, genero=SimpleNamespace(value="F"),
        tipo_identificacion="CC", numero_identificacion="0012345678", telefono=None, direccion=None,
        captcha_token="ok",
    )
    uc.execute(dto, "127.0.0.1", "pytest")
    return db


@pytest.mark.parametrize(
    ("anios", "codigo"),
    [(17, "EDAD_MINIMA_REQUERIDA"), (100, "EDAD_FUERA_DE_RANGO")],
)
def test_registro_fuera_de_rango_es_403_sin_guardar(monkeypatch, anios, codigo):
    from src.shared.fechas import hoy_colombia

    monkeypatch.setattr(modulo.Usuario, "registrar_nuevo", lambda **d: SimpleNamespace(**d))
    hoy = hoy_colombia()
    with pytest.raises(AuthorizationError) as exc:
        _registrar(hoy.replace(year=hoy.year - anios))
    assert exc.value.status_code == 403
    assert exc.value.code == codigo
    assert exc.value.field == "fecha_nacimiento"
    if codigo == "EDAD_FUERA_DE_RANGO":
        assert "(18 a 99 años)" in exc.value.message


def test_perfil_con_100_anios_es_400(monkeypatch):
    from src.identity_access.application.use_cases.perfil.editar_perfil_use_case import EditarPerfilUseCase
    from src.identity_access.domain.entities.cuenta import Cuenta
    from src.identity_access.infrastructure.dto.perfil_dto import EditarPerfilDTO
    from src.shared.errors import ValidationError
    from src.shared.fechas import hoy_colombia

    hoy = hoy_colombia()
    usuario = SimpleNamespace(id_usuario=7, id_rol=2, nombre="Ana", apellidos="Pérez",
                              correo="ana@example.com", fecha_nacimiento=None, version=1)
    cuenta = Cuenta(id_cuenta_usuario=8, id_usuario=7, id_estado_cuenta=Cuenta.ESTADO_PENDIENTE_DATOS)
    db = _Db()
    uc = EditarPerfilUseCase(
        usuarios_repo=SimpleNamespace(obtener_por_id=lambda _i: usuario),
        cuentas_repo=SimpleNamespace(obtener_por_usuario=lambda _i: cuenta),
        sesiones_repo=SimpleNamespace(), eventos_repo=SimpleNamespace(registrar=lambda **_k: None),
        roles_repo=SimpleNamespace(), db=db,
    )
    dto = EditarPerfilDTO(nombre="Ana", apellidos="Pérez", version=1,
                          fecha_nacimiento=hoy.replace(year=hoy.year - 100))
    with pytest.raises(ValidationError) as exc:
        uc.execute(id_usuario=7, dto=dto, usuario_actual=SimpleNamespace(id_usuario=7, id_rol=2))
    assert exc.value.code == "EDAD_FUERA_DE_RANGO"
    assert db.commits == 0
