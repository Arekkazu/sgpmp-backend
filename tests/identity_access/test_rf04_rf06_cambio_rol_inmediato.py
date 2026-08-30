"""Pruebas unitarias del cambio de rol sin relogin de RF-04/06."""
from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from src.identity_access.application.use_cases.perfil import (
    editar_perfil_use_case as editar_module,
)
from src.identity_access.application.use_cases.perfil.editar_perfil_use_case import (
    EditarPerfilUseCase,
)
from src.identity_access.domain.entities.cuenta import Cuenta
from src.identity_access.domain.value_objects.email import Email
from src.identity_access.infrastructure.dto.perfil_dto import EditarPerfilAdminDTO


class UsuarioRepoFake:
    def __init__(self) -> None:
        self.usuario = SimpleNamespace(
            id_usuario=7,
            id_rol=2,
            correo=Email("usuario@example.com"),
            nombre="Usuario",
            apellidos="Prueba",
            telefono="3001234567",
            direccion="Calle 1",
            tipo_identificacion="CC",
            numero_identificacion="1234567890",
            fecha_nacimiento=date(1990, 1, 1),
            genero="M",
            version=1,
        )

    def obtener_por_id(self, id_usuario: int):
        assert id_usuario == self.usuario.id_usuario
        return self.usuario

    def actualizar(self, usuario, version_cliente: int):
        assert version_cliente == 1
        return usuario


class CuentaRepoFake:
    def __init__(self) -> None:
        self.cuenta = Cuenta(
            id_cuenta_usuario=8,
            id_usuario=7,
            id_estado_cuenta=Cuenta.ESTADO_ACTIVO,
        )

    def obtener_por_usuario(self, id_usuario: int) -> Cuenta:
        assert id_usuario == 7
        return self.cuenta

    def contar_usuarios_activos_por_rol(self, _id_rol: int) -> int:
        return 2

    def guardar(self, cuenta: Cuenta) -> Cuenta:
        self.cuenta = cuenta
        return cuenta


class SesionRepoFake:
    def __init__(self) -> None:
        self.invalidaciones = []

    def invalidar_todas_sesiones(self, id_cuenta_usuario: int) -> None:
        self.invalidaciones.append(id_cuenta_usuario)


class EventoRepoFake:
    def registrar(self, **_evento) -> None:
        pass


class RolRepoFake:
    def obtener_por_id(self, id_rol: int):
        return SimpleNamespace(id_rol=id_rol, es_protegido=False)


class DbFake:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


def _crear_use_case():
    usuarios = UsuarioRepoFake()
    cuentas = CuentaRepoFake()
    sesiones = SesionRepoFake()
    db = DbFake()
    return (
        EditarPerfilUseCase(
            usuarios_repo=usuarios,
            cuentas_repo=cuentas,
            sesiones_repo=sesiones,
            eventos_repo=EventoRepoFake(),
            roles_repo=RolRepoFake(),
            db=db,
        ),
        usuarios,
        sesiones,
        db,
    )


def test_cambiar_solo_el_rol_conserva_la_sesion_activa() -> None:
    use_case, usuarios, sesiones, db = _crear_use_case()

    resultado = use_case.execute(
        id_usuario=7,
        dto=EditarPerfilAdminDTO(
            nombre="Usuario",
            apellidos="Prueba",
            id_rol=3,
            version=1,
        ),
        usuario_actual=SimpleNamespace(id_usuario=99, id_rol=1),
    )

    assert resultado.id_rol == 3
    assert usuarios.usuario.id_rol == 3
    assert sesiones.invalidaciones == []
    assert db.commits == 1
    assert db.rollbacks == 0


def test_cambiar_correo_conserva_la_revocacion_de_sesiones(monkeypatch) -> None:
    use_case, _, sesiones, db = _crear_use_case()
    monkeypatch.setattr(editar_module, "send_email", lambda **_datos: None)

    use_case.execute(
        id_usuario=7,
        dto=EditarPerfilAdminDTO(
            nombre="Usuario",
            apellidos="Prueba",
            correo_electronico="nuevo@example.com",
            version=1,
        ),
        usuario_actual=SimpleNamespace(id_usuario=99, id_rol=1),
    )

    assert sesiones.invalidaciones == [8]
    assert db.commits == 1
    assert db.rollbacks == 0

