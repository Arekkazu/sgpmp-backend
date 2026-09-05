"""INC-M01-08-38: límites transaccionales y error controlado de RF-07."""
from unittest.mock import MagicMock, patch

import pytest

from src.identity_access.application.use_cases.contrasena.cambiar_contrasena_use_case import CambiarContrasenaUseCase
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.identity_access.infrastructure.dto.contrasena_dto import CambiarContrasenaDTO
from src.shared.errors import InfrastructureError

MENSAJE = (
    "Contraseña actualizada, pero ocurrió un error al cerrar las sesiones "
    "en otros dispositivos. Se recomienda cerrar sesión manualmente en "
    "todos sus equipos para garantizar la seguridad."
)


@pytest.fixture
def escenario():
    deps = [MagicMock() for _ in range(6)]
    usuarios, cuentas, sesiones, eventos, db, notificacion = deps
    cuentas.obtener_por_usuario.return_value.bloqueado_hasta = None
    usuarios.obtener_por_id.return_value.contrasena.verificar.return_value = True
    uc = CambiarContrasenaUseCase(*deps)
    dto = CambiarContrasenaDTO(contrasena_actual="Actual123!", nueva_contrasena="Nueva123!", confirmar_nueva_contrasena="Nueva123!")
    actor = UsuarioActual(id_usuario=74, id_token=1, id_rol=2)
    with patch("src.identity_access.application.use_cases.contrasena.cambiar_contrasena_use_case.Contrasena.cifrar"):
        yield uc, dto, actor, deps


@pytest.mark.parametrize("fallo", ["invalidar", "commit"])
def test_fallo_sesiones_ocurre_despues_del_commit_y_notifica(escenario, fallo):
    uc, dto, actor, (_, _, sesiones, eventos, db, notificacion) = escenario
    causa = RuntimeError("fallo simulado privado")
    if fallo == "invalidar":
        def invalidar(_):
            db.commit.assert_called_once()
            eventos.registrar.assert_called_once()
            raise causa
        sesiones.invalidar_todas_sesiones.side_effect = invalidar
    else:
        db.commit.side_effect = [None, causa]
    with pytest.raises(InfrastructureError) as error:
        uc.execute(74, dto, actor)
    assert error.value.status_code == 500
    assert error.value.message == MENSAJE
    assert error.value.original_error is causa
    db.rollback.assert_called_once()
    notificacion.notificar.assert_called_once()


@pytest.mark.parametrize("fallo", ["guardar", "auditoria", "commit"])
def test_fallo_primera_transaccion_no_intenta_cerrar_ni_notifica(escenario, fallo):
    uc, dto, actor, (usuarios, _, sesiones, eventos, db, notificacion) = escenario
    operacion = {"guardar": usuarios.cambiar_contrasena, "auditoria": eventos.registrar, "commit": db.commit}[fallo]
    operacion.side_effect = RuntimeError("fallo inicial")
    with pytest.raises(RuntimeError):
        uc.execute(74, dto, actor)
    db.rollback.assert_called_once()
    sesiones.invalidar_todas_sesiones.assert_not_called()
    notificacion.notificar.assert_not_called()


def test_exito_confirma_ambas_transacciones_antes_de_notificar(escenario):
    uc, dto, actor, (_, _, sesiones, _, db, notificacion) = escenario
    notificacion.notificar.side_effect = lambda **_: assert_dos_commits(db)
    uc.execute(74, dto, actor)
    sesiones.invalidar_todas_sesiones.assert_called_once()
    db.rollback.assert_not_called()


def assert_dos_commits(db):
    assert db.commit.call_count == 2
