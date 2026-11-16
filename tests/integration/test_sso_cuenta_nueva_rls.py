# | Fecha      | Nombre   | Que se hizo                                                   |
# |------------|----------|---------------------------------------------------------------|
# | 2026-11-16 | Arekkazu | SSO AgroFusion: el alta del Administrador no choca con la RLS |
"""SSO AgroFusion: un correo que no existe en SIGAB entra y queda pendiente de datos.

La cuenta nace Administrador (rol protegido) y la RLS de `modulo1.usuarios` no
deja que un anónimo inserte un rol protegido: el alta respondía 500. Corre como
`sgpmp_app`, el rol de la API; como superusuario pasaría en verde con la base
abierta, así que la prueba lo comprueba antes.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

from src.identity_access.application.use_cases.sesiones.sso_login_use_case import SsoLoginUseCase
from src.identity_access.domain.repositories.sso_provider_port import SsoProviderPort
from src.identity_access.domain.value_objects.email import Email
from src.identity_access.domain.value_objects.identidad_federada import IdentidadFederada
from src.identity_access.infrastructure.dto.usuario_dto import SsoLoginDTO
from src.identity_access.infrastructure.repositories.cuenta_repository import SqlAlchemyCuentaRepository
from src.identity_access.infrastructure.repositories.evento_repository import SqlAlchemyEventoRepository
from src.identity_access.infrastructure.repositories.rol_repository import SqlAlchemyRolRepository
from src.identity_access.infrastructure.repositories.sesion_repository import SqlAlchemySesionRepository
from src.identity_access.infrastructure.repositories.usuario_repository import SqlAlchemyUsuarioRepository
from src.shared import jwt as jwt_module
from tests.integration.conftest import JWT_SECRET_INTEGRACION

pytestmark = pytest.mark.integration


class _AgroFusion(SsoProviderPort):
    def __init__(self, correo: str) -> None:
        self.identidad = IdentidadFederada("sub-agrofusion", Email(correo), "agrofusion-auth")

    def verificar(self, token: str) -> IdentidadFederada:
        return self.identidad


def test_correo_nuevo_entra_por_sso_como_administrador_pendiente_de_datos(db_session, monkeypatch) -> None:
    if db_session.execute(text("SELECT to_regrole('sgpmp_app')")).scalar() is None:
        pytest.skip("La base de pruebas no tiene el rol sgpmp_app.")
    monkeypatch.setattr(jwt_module, "_SECRET_KEY", JWT_SECRET_INTEGRACION)
    correo = f"sso-{uuid.uuid4().hex}@example.com"

    db_session.execute(text("SET LOCAL ROLE sgpmp_app"))
    assert db_session.execute(
        text("SELECT rolsuper OR rolbypassrls FROM pg_roles WHERE rolname = current_user")
    ).scalar() is False

    use_case = SsoLoginUseCase(
        sso_provider=_AgroFusion(correo),
        usuarios_repo=SqlAlchemyUsuarioRepository(db_session),
        cuentas_repo=SqlAlchemyCuentaRepository(db_session),
        sesiones_repo=SqlAlchemySesionRepository(db_session),
        eventos_repo=SqlAlchemyEventoRepository(db_session),
        roles_repo=SqlAlchemyRolRepository(db_session),
        db=db_session,
    )
    _, _, _, id_usuario, perfil_incompleto, _, _ = use_case.execute(
        SsoLoginDTO(sso_token="handoff"), "127.0.0.1", "pytest"
    )

    db_session.execute(text("RESET ROLE"))
    assert perfil_incompleto is True
    assert db_session.execute(
        text(
            "SELECT r.es_protegido FROM modulo1.usuarios u JOIN modulo1.roles r USING (id_rol) "
            "WHERE u.id_usuario = :id AND u.correo_electronico = :correo"
        ),
        {"id": id_usuario, "correo": correo},
    ).scalar() is True
