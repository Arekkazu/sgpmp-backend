"""
TC-M01-047 - Fallo simulado del servicio de cifrado/hash durante la
generacion del token de recuperacion.

RF relacionado: RF-08
Categoria: Manejo de errores (RESILIENCIA)

Criterio de aceptacion (segun la ficha / evidencia previa de este caso):
    "Respuesta HTTP 500 con rollback de la transaccion ante un fallo
    interno en la generacion o cifrado del token de recuperacion."

Por que local (sin coordinar con Implementacion ni tocar el backend TEST
desplegado): no existe un "servicio de cifrado" como componente externo
inyectable -- lo que la ficha llama cifrado es la funcion de dominio
`calcular_hash_token` (src/identity_access/domain/value_objects/
token_un_solo_uso.py), un hash SHA-256 puro (hashlib). El "fallo del
servicio de cifrado" de la ficha se simula parcheando esa funcion en el
punto donde la usa el use case para que lance una excepcion -- no hace
falta tumbar ningun servicio real.

Estado conocido al escribir este archivo:
src/identity_access/application/use_cases/contrasena/
solicitar_recuperacion_use_case.py (paso 4, lineas ~123-133) envuelve
`calcular_hash_token(token)` DENTRO del mismo try/except que hace
`self.db.rollback()` y `raise` desnudo ante cualquier fallo, y ese except
esta ANTES de cualquier `send_email`. A diferencia de TC-M01-038 y
TC-M01-044, aqui no hay nada legitimo que debiera sobrevivir al rollback
(todavia no se guardo el token ni se envio el correo), y la excepcion
cruda que se propaga SI es interceptada por el handler global de FastAPI
(`error_no_controlado_handler`, registrado sobre `Exception` en
src/shared/error_handlers.py), que responde 500 con `error_code:
ERROR_INTERNO`. Por lo tanto, a diferencia de los otros tres casos de
este grupo (038, 044, 059-por-verificar), la lectura de codigo sugiere
que este caso SI cumple la ficha: se espera que AMBAS pruebas de este
archivo PASEN. Esto no esta confirmado hasta correrlas -- si alguna
falla, el mensaje de assert explica exactamente que se rompio.

Como correrlo (desde la raiz del repo, con las env vars seteadas):
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    $env:SECRET_KEY = "test"
    python -m pytest <ruta>\\test_tc_m01_047_fallo_cifrado.py -v `
        --html=reporte-TC-M01-047.html --self-contained-html
"""
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.identity_access.application.use_cases.contrasena.solicitar_recuperacion_use_case import (
    SolicitarRecuperacionUseCase,
)
from src.identity_access.infrastructure.dto.contrasena_dto import SolicitarRecuperacionDTO

CORREO_PRUEBA = "ana.martinez.qa1@sgpmp-test.com"
FALLO_CIFRADO_SIMULADO = "servicio de cifrado/hash caido (simulado)"


def _construir_use_case():
    """Doble de prueba: cuenta activa, verificada, sin bloqueo por limite
    de solicitudes -- llega directo al paso 4 (generar y guardar el
    token de recuperacion), que es donde se invoca el hash."""
    usuario = MagicMock()
    usuario.id_usuario = 74
    usuario.nombre = "Ana Martinez"

    cuenta = MagicMock()
    cuenta.id_estado_cuenta = 2  # activa, distinta de ESTADO_ELIMINADO (5)
    cuenta.esta_pendiente.return_value = False

    usuarios_repo = MagicMock()
    usuarios_repo.obtener_por_correo.return_value = usuario

    cuentas_repo = MagicMock()
    cuentas_repo.obtener_por_usuario.return_value = cuenta

    eventos_repo = MagicMock()
    eventos_repo.contar_solicitudes_recuperacion_por_ip.return_value = 0

    db = MagicMock()

    use_case = SolicitarRecuperacionUseCase(
        usuarios_repo=usuarios_repo,
        cuentas_repo=cuentas_repo,
        eventos_repo=eventos_repo,
        db=db,
    )
    return use_case, db


class TestTCM01047FalloCifrado:
    """Suite de pruebas para TC-M01-047."""

    @patch(
        "src.identity_access.application.use_cases.contrasena."
        "solicitar_recuperacion_use_case.calcular_hash_token"
    )
    def test_fallo_de_hash_debe_revertir_la_transaccion(self, mock_hash):
        """
        RF-08: si calcular_hash_token() falla (servicio de cifrado
        caido) al generar el token de recuperacion, la transaccion debe
        revertirse por completo (rollback) -- no debe quedar ningun
        registro a medias en la base de datos.
        """
        mock_hash.side_effect = Exception(FALLO_CIFRADO_SIMULADO)
        use_case, db = _construir_use_case()
        dto = SolicitarRecuperacionDTO(correo_electronico=CORREO_PRUEBA)

        try:
            use_case.execute(dto, ip="203.0.113.10")
        except Exception:
            pass

        assert db.rollback.called, (
            "Se esperaba que el fallo del hash disparara self.db.rollback() "
            "dentro del bloque try/except del paso 4 (generar token de "
            "recuperacion), pero no se llamo. Revisar si el codigo cambio "
            "de estructura respecto a la version leida al escribir esta "
            "prueba."
        )
        assert not db.commit.called, (
            "No deberia haberse llegado a self.db.commit() si el hash del "
            "token fallo antes."
        )

    @patch(
        "src.identity_access.application.use_cases.contrasena."
        "solicitar_recuperacion_use_case.calcular_hash_token"
    )
    def test_endpoint_responde_500_cuando_falla_el_hash(self, mock_hash):
        """
        RF-08: POST /contrasena/recuperar debe responder HTTP 500 (error
        controlado generico) cuando el servicio de cifrado del token
        falla, tal como exige la ficha de TC-M01-047.
        """
        from src.identity_access.infrastructure.repositories.cuenta_repository import (
            SqlAlchemyCuentaRepository,
        )
        from src.identity_access.infrastructure.repositories.evento_repository import (
            SqlAlchemyEventoRepository,
        )
        from src.identity_access.infrastructure.repositories.usuario_repository import (
            SqlAlchemyUsuarioRepository,
        )
        from src.identity_access.infrastructure.routers.contrasena_routers import (
            router as contrasena_router,
        )
        from src.shared.database import get_db
        from src.shared.error_handlers import register_error_handlers

        mock_hash.side_effect = Exception(FALLO_CIFRADO_SIMULADO)

        usuario = MagicMock()
        usuario.id_usuario = 74
        usuario.nombre = "Ana Martinez"
        cuenta = MagicMock()
        cuenta.id_estado_cuenta = 2
        cuenta.esta_pendiente.return_value = False

        app = FastAPI()
        register_error_handlers(app)
        app.include_router(contrasena_router)

        def _fake_db():
            yield MagicMock()

        app.dependency_overrides[get_db] = _fake_db

        with (
            patch.object(SqlAlchemyUsuarioRepository, "obtener_por_correo", return_value=usuario),
            patch.object(SqlAlchemyCuentaRepository, "obtener_por_usuario", return_value=cuenta),
            patch.object(
                SqlAlchemyEventoRepository,
                "contar_solicitudes_recuperacion_por_ip",
                return_value=0,
            ),
            patch.object(SqlAlchemyEventoRepository, "registrar", return_value=None),
            patch(
                "src.identity_access.application.use_cases.contrasena."
                "solicitar_recuperacion_use_case.calcular_hash_token",
                side_effect=Exception(FALLO_CIFRADO_SIMULADO),
            ),
        ):
            client = TestClient(app, raise_server_exceptions=False)
            response = client.post(
                "/contrasena/recuperar",
                json={"correo_electronico": CORREO_PRUEBA},
            )

        assert response.status_code == 500, (
            f"RF-08 / ficha TC-M01-047 exige HTTP 500 ante un fallo del "
            f"servicio de cifrado del token; el endpoint respondio "
            f"{response.status_code}. Cuerpo: {response.text}"
        )
        if response.status_code == 500:
            assert response.json().get("error_code") == "ERROR_INTERNO"