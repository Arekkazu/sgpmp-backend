"""
TC-M01-038 (RETEST 2026-09-12) - Fallo simulado en limpieza de sesiones/
blacklist durante el cambio de contrasena.

RF relacionado: RF-07
Categoria: Manejo de errores (RESILIENCIA)

Este archivo es la version corregida del test original
(test_tc_m01_038_fallo_blacklist.py) para verificar la version de
cambiar_contrasena_use_case.py que existe en origin/test (rama remota),
la cual introduce un SAVEPOINT (`self.db.begin_nested()`) alrededor de
`sesiones_repo.invalidar_todas_sesiones()`.

Por que el test original NO sirve para verificar esta version del codigo:
el test original usaba `db = MagicMock()` sin configurar el protocolo de
context manager de `db.begin_nested()`. Un MagicMock generico, al usarse
en un `with ...:`, devuelve un `__exit__` que por defecto es "truthy" -
eso SUPRIME cualquier excepcion lanzada dentro del bloque `with`, en vez
de dejarla propagar como lo hace un SAVEPOINT real de SQLAlchemy. Con esa
configuracion por defecto, el test original habria dado un resultado
enganoso contra el codigo nuevo (ni lo confirma ni lo refuta realmente).

Este archivo configura explicitamente `db.begin_nested.return_value` como
un context manager que NO suprime excepciones (`__exit__` devuelve
`False`), replicando el comportamiento real de un SAVEPOINT.

Criterio de aceptacion (segun la ficha, flujo alterno "Fallo en la
invalidacion masiva de sesiones"):
    "El sistema actualiza la contraseña con exito, pero falla al intentar
    registrar los tokens previos en la blacklist o al limpiar la tabla de
    sesiones activas. El sistema responde con HTTP 500: Internal Server
    Error. Mensaje: 'Contraseña actualizada, pero ocurrió un error al
    cerrar las sesiones en otros dispositivos. Se recomienda cerrar
    sesión manualmente en todos sus equipos para garantizar la
    seguridad.'"

Como correrlo (desde la raiz del repo):
    1. Traer SOLO este archivo del backend desde origin/test (no es un
       merge, no toca nada mas de tu rama actual):
           git checkout origin/test -- src/identity_access/application/use_cases/contrasena/cambiar_contrasena_use_case.py
    2. Correr el test:
           python -m pytest tests/Test_Testing/Test_Modulo1/RF-07/TC-M01-38/test_tc_m01_038_retest.py -v --html=reporte-TC-M01-038-retest.html --self-contained-html
    3. Revertir el archivo a tu version original (importante, para no
       dejarte con codigo "prestado" de otra rama en tu working tree):
           git checkout daniela/qa-pruebas -- src/identity_access/application/use_cases/contrasena/cambiar_contrasena_use_case.py
       (o `git restore <esa misma ruta>`, equivalente estando parada en
       daniela/qa-pruebas)
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
    cuenta activa y sin bloqueos, nueva contraseña distinta a la actual,
    para llegar directo al bloque que aplica el cambio e invalida
    sesiones.

    A diferencia del test original, aqui `db.begin_nested()` se configura
    explicitamente como un context manager que NO suprime excepciones,
    replicando un SAVEPOINT real de SQLAlchemy.
    """
    usuario = MagicMock()
    usuario.contrasena.verificar.side_effect = lambda valor: valor == "Actual1234!"

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
    # Clave: replicar un SAVEPOINT real (no debe suprimir excepciones).
    db.begin_nested.return_value.__enter__.return_value = None
    db.begin_nested.return_value.__exit__.return_value = False

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


class TestTCM01038RetestFalloBlacklist:
    """Suite de retest para TC-M01-038 contra la version de origin/test."""

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
            "la invalidacion de sesiones; db.rollback() no deberia haberse "
            "llamado sobre la transaccion principal (solo el SAVEPOINT de "
            "sesiones deberia verse afectado)."
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
            f"controlado."
        )
        assert getattr(excepcion_lanzada, "message", None) == MENSAJE_ESPERADO_FICHA, (
            f"RF-07 exige el mensaje exacto: {MENSAJE_ESPERADO_FICHA!r}. "
            f"Se obtuvo: {getattr(excepcion_lanzada, 'message', str(excepcion_lanzada))!r}"
        )

    def test_contrasena_reutilizada_sigue_rechazada_con_409(self):
        """
        Verificacion adicional (no rompe nada de RF-07): confirma que la
        version de origin/test conserva tambien el chequeo de no-reuso de
        contraseña (TC-M01-035) al usar `usuario.contrasena.verificar`
        contra la nueva contraseña propuesta.
        """
        sesiones_repo = MagicMock()
        use_case, usuarios_repo, db = _construir_use_case(sesiones_repo)
        usuario_actual = UsuarioActual(id_usuario=ID_USUARIO, id_token=1, id_rol=2)

        dto_reutilizada = CambiarContrasenaDTO(
            contrasena_actual="Actual1234!",
            nueva_contrasena="Actual1234!",
            confirmar_nueva_contrasena="Actual1234!",
        )

        excepcion_lanzada = None
        try:
            use_case.execute(ID_USUARIO, dto_reutilizada, usuario_actual)
        except Exception as exc:
            excepcion_lanzada = exc

        assert excepcion_lanzada is not None
        assert getattr(excepcion_lanzada, "status_code", None) == 409
        assert getattr(excepcion_lanzada, "code", None) == "CONTRASENA_REUTILIZADA"