"""
TC-M01-059 - Fallo simulado del servicio de invalidacion de sesiones justo
despues de un restablecimiento de contrasena exitoso (via token).

RF relacionado: RF-09, RF-02
Categoria: Manejo de errores (RESILIENCIA)

Criterio de aceptacion (segun la ficha / evidencia previa de este caso):
    "Rollback y respuesta HTTP 500 cuando falla la invalidacion de
    sesiones activas previas tras un restablecimiento exitoso." Es decir,
    si el servicio de sesiones falla, TODA la operacion debe revertirse
    (no debe quedar la contrasena cambiada con sesiones viejas todavia
    activas -- eso seria un hueco de seguridad) y responder 500.

Por que local (sin coordinar con Implementacion ni tocar el backend TEST
desplegado): RestablecerContrasenaUseCase.execute() recibe `sesiones_repo`
como dependencia inyectada (puerto de dominio, domain/repositories/
sesion_repository.py). El "servicio de sesiones caido" de la ficha se
simula reemplazando ese puerto por un mock que lanza una excepcion al
invalidar sesiones -- se prueba exactamente el mismo codigo
(restablecer_contrasena_use_case.py) que corre en el backend desplegado.

Estado conocido al escribir este archivo -- IMPORTANTE, es distinto al
patron de TC-M01-038:
src/identity_access/application/use_cases/contrasena/
restablecer_contrasena_use_case.py (paso 5-6, lineas ~114-131) tambien
envuelve el cambio de contrasena (usuarios_repo.cambiar_contrasena) Y la
invalidacion de sesiones (sesiones_repo.invalidar_todas_sesiones) en el
MISMO try/except con `self.db.rollback()` + `raise` desnudo. En
TC-M01-038 (RF-07, cambiar_contrasena_use_case.py) esa MISMA estructura
es un defecto, porque la ficha de ESE caso exige que la contrasena NO se
revierta. Aqui es al reves: la ficha de TC-M01-059 exige que SI se
revierta todo. Ademas, ni usuarios_repo.cambiar_contrasena() (usa
self.db.flush(), no commit) ni cuentas_repo.guardar() comitean nada antes
de invalidar_todas_sesiones(), asi que el rollback deshace realmente todo
el trabajo pendiente. Y la excepcion cruda que se propaga SI es
interceptada por el handler global de FastAPI
(`error_no_controlado_handler` en src/shared/error_handlers.py), que
responde 500. Por lo tanto, a diferencia de TC-M01-038 y TC-M01-044, la
lectura de codigo sugiere que este caso SI cumple su ficha: se espera que
AMBAS pruebas de este archivo PASEN. Esto no esta confirmado hasta
correrlas -- si alguna falla, el mensaje de assert explica exactamente
que se rompio.

Dato de prueba: se usa un token de recuperacion valido simulado (no
expirado, sin bloqueo previo) para llegar directo al paso donde se aplica
la nueva contrasena y se invalidan las sesiones.

Como correrlo (desde la raiz del repo, con las env vars seteadas):
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    $env:SECRET_KEY = "test"
    python -m pytest <ruta>\\test_tc_m01_059_fallo_invalidacion_sesiones.py -v `
        --html=reporte-TC-M01-059.html --self-contained-html
"""
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.identity_access.application.use_cases.contrasena.restablecer_contrasena_use_case import (
    RestablecerContrasenaUseCase,
)
from src.identity_access.infrastructure.dto.contrasena_dto import RestablecerContrasenaDTO

TOKEN_VALIDO = "token-de-prueba-valido-000000000000000000000000"
FALLO_SESIONES_SIMULADO = "servicio de invalidacion de sesiones caido (simulado)"


def _construir_use_case(sesiones_repo):
    """Arma el use case con dobles de prueba: token valido, sin bloqueo,
    no expirado, para llegar directo al bloque que aplica el cambio de
    contrasena e invalida sesiones."""
    usuario = MagicMock()
    usuario.id_usuario = 74
    usuario.correo = "ana.martinez.qa1@sgpmp-test.com"

    cuenta = MagicMock()
    cuenta.bloqueado_hasta = None
    cuenta.fecha_cambio_estado = datetime.now(timezone.utc)  # recien generado, no expirado
    cuenta.id_usuario = 74
    cuenta.id_cuenta_usuario = 501

    usuarios_repo = MagicMock()
    usuarios_repo.obtener_por_id.return_value = usuario

    cuentas_repo = MagicMock()
    cuentas_repo.obtener_por_hash_token.return_value = cuenta

    eventos_repo = MagicMock()
    db = MagicMock()

    use_case = RestablecerContrasenaUseCase(
        usuarios_repo=usuarios_repo,
        cuentas_repo=cuentas_repo,
        sesiones_repo=sesiones_repo,
        eventos_repo=eventos_repo,
        db=db,
    )
    return use_case, usuarios_repo, db


def _dto() -> RestablecerContrasenaDTO:
    return RestablecerContrasenaDTO(
        token=TOKEN_VALIDO,
        nueva_contrasena="Nueva5678#",
        confirmar_contrasena="Nueva5678#",
    )


class TestTCM01059FalloInvalidacionSesiones:
    """Suite de pruebas para TC-M01-059."""

    def test_fallo_de_invalidacion_debe_revertir_tambien_la_contrasena(self):
        """
        RF-09/RF-02: si sesiones_repo.invalidar_todas_sesiones() falla
        (servicio de sesiones caido), la contrasena YA aplicada en esta
        misma transaccion debe revertirse -- no debe quedar la contrasena
        cambiada con sesiones viejas todavia activas.
        """
        sesiones_repo = MagicMock()
        sesiones_repo.invalidar_todas_sesiones.side_effect = Exception(
            FALLO_SESIONES_SIMULADO
        )
        use_case, usuarios_repo, db = _construir_use_case(sesiones_repo)

        try:
            use_case.execute(_dto(), ip="203.0.113.10")
        except Exception:
            pass

        assert usuarios_repo.cambiar_contrasena.called, (
            "El caso de uso deberia haber intentado aplicar el cambio de "
            "contrasena antes de invalidar sesiones."
        )
        assert db.rollback.called, (
            "La ficha TC-M01-059 exige que, si falla la invalidacion de "
            "sesiones, TODA la operacion se revierta (incluida la "
            "contrasena recien aplicada) -- pero self.db.rollback() no se "
            "llamo. Dejar la contrasena cambiada con sesiones viejas "
            "todavia activas seria un hueco de seguridad."
        )
        assert not db.commit.called, (
            "No deberia haberse llegado a self.db.commit() si la "
            "invalidacion de sesiones fallo antes."
        )

    @patch(
        "src.identity_access.application.use_cases.contrasena."
        "restablecer_contrasena_use_case.calcular_hash_token"
    )
    def test_endpoint_responde_500_cuando_falla_la_invalidacion_de_sesiones(
        self, mock_hash
    ):
        """
        RF-09/RF-02: POST /contrasena/restablecer debe responder HTTP 500
        (error controlado generico) cuando el servicio de invalidacion de
        sesiones falla tras un cambio de contrasena que, por eso mismo,
        no debe quedar aplicado.
        """
        from src.identity_access.infrastructure.repositories.cuenta_repository import (
            SqlAlchemyCuentaRepository,
        )
        from src.identity_access.infrastructure.repositories.evento_repository import (
            SqlAlchemyEventoRepository,
        )
        from src.identity_access.infrastructure.repositories.sesion_repository import (
            SqlAlchemySesionRepository,
        )
        from src.identity_access.infrastructure.repositories.usuario_repository import (
            SqlAlchemyUsuarioRepository,
        )
        from src.identity_access.infrastructure.routers.contrasena_routers import (
            router as contrasena_router,
        )
        from src.shared.database import get_db
        from src.shared.error_handlers import register_error_handlers

        mock_hash.return_value = "hash-fijo-de-prueba"

        usuario = MagicMock()
        usuario.id_usuario = 74
        usuario.correo = "ana.martinez.qa1@sgpmp-test.com"

        cuenta = MagicMock()
        cuenta.bloqueado_hasta = None
        cuenta.fecha_cambio_estado = datetime.now(timezone.utc)
        cuenta.id_usuario = 74
        cuenta.id_cuenta_usuario = 501

        app = FastAPI()
        register_error_handlers(app)
        app.include_router(contrasena_router)

        def _fake_db():
            yield MagicMock()

        app.dependency_overrides[get_db] = _fake_db

        with (
            patch.object(SqlAlchemyUsuarioRepository, "obtener_por_id", return_value=usuario),
            patch.object(
                SqlAlchemyCuentaRepository, "obtener_por_hash_token", return_value=cuenta
            ),
            patch.object(SqlAlchemyUsuarioRepository, "cambiar_contrasena", return_value=None),
            patch.object(SqlAlchemyCuentaRepository, "guardar", return_value=None),
            patch.object(SqlAlchemyEventoRepository, "registrar", return_value=None),
            patch.object(
                SqlAlchemySesionRepository,
                "invalidar_todas_sesiones",
                side_effect=Exception(FALLO_SESIONES_SIMULADO),
            ),
        ):
            client = TestClient(app, raise_server_exceptions=False)
            response = client.post(
                "/contrasena/restablecer",
                json={
                    "token": TOKEN_VALIDO,
                    "nueva_contrasena": "Nueva5678#",
                    "confirmar_contrasena": "Nueva5678#",
                },
            )

        assert response.status_code == 500, (
            f"RF-09/RF-02 / ficha TC-M01-059 exige HTTP 500 ante un fallo "
            f"del servicio de invalidacion de sesiones; el endpoint "
            f"respondio {response.status_code}. Cuerpo: {response.text}"
        )
        if response.status_code == 500:
            assert response.json().get("error_code") == "ERROR_INTERNO"