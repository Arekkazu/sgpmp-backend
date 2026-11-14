# | Fecha      | Nombre   | Que se hizo                                                 |
# |------------|----------|-------------------------------------------------------------|
# | 2026-11-13 | Arekkazu | SSO AgroFusion: la cuenta creada por SSO nace Administrador |
"""SSO AgroFusion: quien entra por primera vez desde AgroFusion queda Administrador.

El rol se resuelve por ``es_protegido`` (así se identifica al Administrador en
este módulo), no por ``id_rol``: aquí el protegido es el 7 a propósito.
"""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from src.identity_access.application.use_cases.sesiones.sso_login_use_case import SsoLoginUseCase
from src.identity_access.domain.entities.cuenta import Cuenta
from src.identity_access.domain.entities.rol import Rol
from src.identity_access.domain.value_objects.email import Email


class _Usuarios:
    def guardar(self, usuario):
        self.guardado = usuario
        return usuario


class _Cuentas:
    def crear(self, id_usuario, token, id_estado_cuenta):
        self.estado = id_estado_cuenta
        return SimpleNamespace(id_estado_cuenta=id_estado_cuenta)


class _Roles:
    def listar(self):
        return [Rol(nombre_rol="Productor", es_protegido=False, id_rol=2),
                Rol(nombre_rol="Administrador", es_protegido=True, id_rol=7)]


class _Db:
    def commit(self):
        pass

    def rollback(self):
        pass


def test_cuenta_nueva_por_sso_queda_administrador_y_pendiente_de_datos() -> None:
    usuarios, cuentas = _Usuarios(), _Cuentas()
    use_case = SsoLoginUseCase(
        sso_provider=None, usuarios_repo=usuarios, cuentas_repo=cuentas, sesiones_repo=None,
        eventos_repo=SimpleNamespace(registrar=lambda **_: None), roles_repo=_Roles(), db=_Db(),
    )
    identidad = SimpleNamespace(email=Email("nuevo.agrofusion@example.com"), emisor="agrofusion-auth", sub_externo="abc")

    use_case._provisionar_minimo(identidad, "127.0.0.1", datetime.now(timezone.utc))

    assert usuarios.guardado.id_rol == 7
    assert cuentas.estado == Cuenta.ESTADO_PENDIENTE_DATOS
