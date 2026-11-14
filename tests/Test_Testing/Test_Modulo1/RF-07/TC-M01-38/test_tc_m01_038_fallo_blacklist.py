"""
TC-M01-038 - Fallo simulado en limpieza de sesiones/blacklist durante el
cambio de contraseña.

RF relacionado: RF-07
Categoria: Manejo de errores (RESILIENCIA)

Criterio de aceptacion (segun la ficha, flujo alterno "Fallo en la
invalidacion masiva de sesiones"):
    "El sistema actualiza la contraseña con exito, pero falla al intentar
    registrar los tokens previos en la blacklist o al limpiar la tabla de
    sesiones activas. El sistema responde con HTTP 500: Internal Server
    Error. Mensaje: 'Contraseña actualizada, pero ocurrió un error al
    cerrar las sesiones en otros dispositivos. Se recomienda cerrar
    sesión manualmente en todos sus equipos para garantizar la
    seguridad.'"

Por que local (sin coordinar con Implementacion ni tocar el backend TEST
desplegado): CambiarContrasenaUseCase.execute() recibe `sesiones_repo`
como dependencia inyectada (puerto de dominio, domain/repositories/
sesion_repository.py). El "servicio de blacklist/sesiones caido" de la
ficha se simula reemplazando ese puerto por un mock que lanza una
excepcion al invalidar sesiones -- no hace falta tumbar ningun servicio
real ni coordinar una ventana con Implementacion, y se prueba exactamente
el mismo codigo (cambiar_contrasena_use_case.py) que corre en el backend
desplegado.

Estado conocido al escribir este archivo:
src/identity_access/application/use_cases/contrasena/
cambiar_contrasena_use_case.py (lineas 157-171) envuelve el cambio de
contraseña (usuarios_repo.cambiar_contrasena) Y la invalidacion de
sesiones (sesiones_repo.invalidar_todas_sesiones) en el MISMO
try/except, que hace `self.db.rollback()` y `raise` desnudo ante
cualquier fallo. Por lo tanto se espera que AMBAS pruebas de este
archivo FALLEN hoy:
1. El rollback deshace tambien el cambio de contraseña ya aplicado,
   contradiciendo la postcondicion de la ficha ("el sistema actualiza la
   contraseña con exito").
2. La excepcion que se propaga es la cruda de sesiones_repo, no un error
   controlado 500 con el mensaje especifico de la ficha.

Como correrlo (desde la raiz del repo, con las env vars seteadas):
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    $env:SECRET_KEY = "test"
    python -m pytest <ruta>\\test_tc_m01_038_fallo_blacklist.py -v \
        --html=reporte-TC-M01-038.html --self-contained-html
"""
from unittest.mock import MagicMock

from src.identity_access.application.use_cases.contrasena.cambiar_contrasena_use_case import (
    CambiarContrasenaUseCase,
)
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.identity_access.infrastructure.dto.contrasena_dto import CambiarContrasenaDTO

ID_USUARIO = 74
MENSAJE_ESPERADO_FICHA = (
    "Contraseña actualizada, pero ocurrió un error al cerrar las sesiones "
    "en otros dispositivos. Se recomienda cerrar sesión manualmente en "
    "todos sus equipos para garantizar la seguridad."
)


def _construir_use_case(sesiones_repo):
    """Arma el use case con dobles de prueba: contraseña actual valida,
    cuenta activa y sin bloqueos, para llegar directo al bloque que
    aplica el cambio e invalida sesiones."""
    usuario = MagicMock()
    usuario.contrasena.verificar.return_value = True

    cuenta = MagicMock()
    cuenta.esta_activa.return_value = True
    cuenta.bloqueado_hasta = None
    cuenta.id_cuenta_usuario = 501

    usuarios_repo = MagicMock()
    usuarios_repo.obtener_por_id.return_value = usuario

    cuentas_repo = MagicMock()
    cuentas_repo.obtener_por_usuario.return_value = cuenta

    eventos_repo = MagicMock()
    db = MagicMock()

    use_case = CambiarContrasenaUseCase(
        usuarios_repo=usuarios_repo,
        cuentas_repo=cuentas_repo,
        sesiones_repo=sesiones_repo,
        eventos_repo=eventos_repo,
        db=db,
    )
    return use_case, usuarios_repo, db


def _dto() -> CambiarContrasenaDTO:
    return CambiarContrasenaDTO(
        contrasena_actual="Actual1234!",
        nueva_contrasena="Nueva5678#",
        confirmar_nueva_contrasena="Nueva5678#",
    )


class TestTCM01038FalloBlacklist:
    """Suite de pruebas para TC-M01-038."""

    def test_fallo_de_invalidacion_no_debe_revertir_la_contrasena_ya_cambiada(self):
        """
        RF-07: si sesiones_repo.invalidar_todas_sesiones() falla (servicio
        de blacklist/sesiones caido), la contraseña YA cambiada no debe
        revertirse.
        """
        sesiones_repo = MagicMock()
        sesiones_repo.invalidar_todas_sesiones.side_effect = Exception(
            "servicio de blacklist/sesiones caido (simulado)"
        )
        use_case, usuarios_repo, db = _construir_use_case(sesiones_repo)
        usuario_actual = UsuarioActual(id_usuario=ID_USUARIO, id_token=1, id_rol=2)

        try:
            use_case.execute(ID_USUARIO, _dto(), usuario_actual)
        except Exception:
            pass

        assert usuarios_repo.cambiar_contrasena.called, (
            "El caso de uso deberia haber intentado aplicar el cambio de "
            "contraseña antes de invalidar sesiones."
        )
        assert not db.rollback.called, (
            "RF-07 exige que la contraseña quede actualizada aunque falle "
            "la invalidacion de sesiones; pero el use case ejecuto "
            "db.rollback() de la MISMA transaccion donde se guardo la "
            "nueva contraseña, deshaciendola tambien. El cambio de "
            "contraseña y la invalidacion de sesiones deben quedar en "
            "pasos independientes (comitear la contraseña antes de "
            "intentar invalidar sesiones, y manejar el fallo de "
            "invalidacion aparte)."
        )

    def test_fallo_de_invalidacion_debe_responder_500_con_mensaje_especifico(self):
        """
        RF-07: ante el fallo de invalidacion de sesiones se espera un
        error controlado (HTTP 500) con el mensaje exacto de la ficha, no
        la excepcion cruda del servicio de sesiones/blacklist.
        """
        sesiones_repo = MagicMock()
        sesiones_repo.invalidar_todas_sesiones.side_effect = Exception(
            "servicio de blacklist/sesiones caido (simulado)"
        )
        use_case, *_ = _construir_use_case(sesiones_repo)
        usuario_actual = UsuarioActual(id_usuario=ID_USUARIO, id_token=1, id_rol=2)

        excepcion_lanzada = None
        try:
            use_case.execute(ID_USUARIO, _dto(), usuario_actual)
        except Exception as exc:
            excepcion_lanzada = exc

        assert excepcion_lanzada is not None, (
            "Se esperaba que el fallo de invalidacion de sesiones generara "
            "una excepcion."
        )
        assert getattr(excepcion_lanzada, "status_code", None) == 500, (
            f"RF-07 exige HTTP 500 ante este fallo; la excepcion propagada "
            f"fue {type(excepcion_lanzada).__name__} sin status_code 500 "
            f"controlado (probablemente la excepcion cruda del servicio de "
            f"sesiones, sin traducir)."
        )
        assert getattr(excepcion_lanzada, "message", None) == MENSAJE_ESPERADO_FICHA, (
            f"RF-07 exige el mensaje exacto: {MENSAJE_ESPERADO_FICHA!r}. "
            f"Se obtuvo: {getattr(excepcion_lanzada, 'message', str(excepcion_lanzada))!r}"
        )
