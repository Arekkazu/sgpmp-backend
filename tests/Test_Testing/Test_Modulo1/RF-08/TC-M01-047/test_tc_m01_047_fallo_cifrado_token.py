"""
TC-M01-047 - Respuesta HTTP 500 con rollback de la transaccion ante un
fallo interno en la generacion o cifrado del token de recuperacion.

RF relacionado: RF-08
Categoria: Manejo de errores (RESILIENCIA)

Este test mockea calcular_hash_token() para que falle (simulando un
error del servicio de cifrado/hash), y verifica:
1. La excepcion se propaga (para que el handler global de FastAPI
   la convierta en 500).
2. Se llamo a db.rollback() exactamente una vez.
3. NO se llamo a db.commit() (nunca se confirmo una transaccion
   parcial).
4. NO se envio el correo de recuperacion (el flujo nunca debio
   llegar tan lejos).
5. El registro del evento de auditoria tampoco quedo confirmado
   (esta dentro del mismo bloque transaccional).

Ajusta el import de SolicitarRecuperacionUseCase segun el nombre
real del archivo si difiere de solicitar_recuperacion_use_case.py.

Como correrlo:
    pytest test_tc_m01_047_fallo_cifrado_token.py -v \
        --html=reporte-TC-M01-047.html --self-contained-html
"""
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.identity_access.application.use_cases.contrasena.solicitar_recuperacion_use_case import (
    SolicitarRecuperacionUseCase,
)
from src.identity_access.domain.entities.cuenta import Cuenta


class FalloCifradoSimulado(Exception):
    """Excepcion generica que representa un fallo del servicio de cifrado/hash."""


@pytest.fixture
def mocks():
    """Arma un conjunto de mocks minimos para ejecutar el use case
    hasta el punto donde se genera el token de recuperacion."""
    usuarios_repo = MagicMock()
    cuentas_repo = MagicMock()
    eventos_repo = MagicMock()
    db = MagicMock()

    # Usuario existente, cuenta activa (no pendiente, no eliminada) -
    # para que el flujo llegue hasta la generacion del token de
    # RECUPERACION (no el de activacion).
    usuario_mock = MagicMock()
    usuario_mock.id_usuario = 999
    usuario_mock.nombre = "Usuario De Prueba"
    usuarios_repo.obtener_por_correo.return_value = usuario_mock

    cuenta_mock = MagicMock()
    cuenta_mock.id_estado_cuenta = 2  # Activo, no Eliminado
    cuenta_mock.esta_pendiente.return_value = False
    cuentas_repo.obtener_por_usuario.return_value = cuenta_mock

    # Rate limiting: 0 solicitudes previas, no bloquea.
    eventos_repo.contar_solicitudes_recuperacion_por_ip.return_value = 0

    return {
        "usuarios_repo": usuarios_repo,
        "cuentas_repo": cuentas_repo,
        "eventos_repo": eventos_repo,
        "db": db,
        "usuario_mock": usuario_mock,
        "cuenta_mock": cuenta_mock,
    }


@pytest.fixture
def dto():
    d = MagicMock()
    d.correo_electronico = "usuario.prueba@sgpmp-test.com"
    return d


class TestTCM01047FalloCifradoTokenRecuperacion:
    """Suite de pruebas para TC-M01-047."""

    @patch(
        "src.identity_access.application.use_cases.contrasena.solicitar_recuperacion_use_case.calcular_hash_token"
    )
    @patch(
        "src.identity_access.application.use_cases.contrasena.solicitar_recuperacion_use_case.send_email"
    )
    def test_fallo_de_cifrado_propaga_excepcion_y_hace_rollback(
        self, mock_send_email, mock_calcular_hash, mocks, dto
    ):
        mock_calcular_hash.side_effect = FalloCifradoSimulado(
            "Servicio de cifrado no disponible (simulado)"
        )

        use_case = SolicitarRecuperacionUseCase(
            usuarios_repo=mocks["usuarios_repo"],
            cuentas_repo=mocks["cuentas_repo"],
            eventos_repo=mocks["eventos_repo"],
            db=mocks["db"],
        )

        with pytest.raises(FalloCifradoSimulado):
            use_case.execute(dto, ip="10.0.0.1")

        # 1. Rollback SI se llamo.
        mocks["db"].rollback.assert_called_once()

        # 2. Commit NUNCA se llamo (no quedo nada confirmado a medias).
        mocks["db"].commit.assert_not_called()

        # 3. El correo de recuperacion nunca se envio (el flujo no
        #    llego tan lejos, fallo antes).
        mock_send_email.assert_not_called()

    @patch(
        "src.identity_access.application.use_cases.contrasena.solicitar_recuperacion_use_case.calcular_hash_token"
    )
    @patch(
        "src.identity_access.application.use_cases.contrasena.solicitar_recuperacion_use_case.send_email"
    )
    def test_el_guardado_de_cuenta_no_persiste_datos_de_un_token_a_medio_generar(
        self, mock_send_email, mock_calcular_hash, mocks, dto
    ):
        """
        Verifica que cuentas_repo.guardar() nunca se haya llamado con
        exito de forma que quedara persistido un token invalido/vacio.
        Como el fallo ocurre en calcular_hash_token(), que se llama
        ANTES de cuenta.asignar_token_recuperacion(), guardar() no
        deberia ni siquiera intentarse.
        """
        mock_calcular_hash.side_effect = FalloCifradoSimulado("Fallo simulado")

        use_case = SolicitarRecuperacionUseCase(
            usuarios_repo=mocks["usuarios_repo"],
            cuentas_repo=mocks["cuentas_repo"],
            eventos_repo=mocks["eventos_repo"],
            db=mocks["db"],
        )

        with pytest.raises(FalloCifradoSimulado):
            use_case.execute(dto, ip="10.0.0.1")

        mocks["cuentas_repo"].guardar.assert_not_called()
        mocks["eventos_repo"].registrar.assert_not_called()

    @patch(
        "src.identity_access.application.use_cases.contrasena.solicitar_recuperacion_use_case.calcular_hash_token"
    )
    @patch(
        "src.identity_access.application.use_cases.contrasena.solicitar_recuperacion_use_case.send_email"
    )
    def test_caso_control_sin_fallo_si_completa_el_flujo_normalmente(
        self, mock_send_email, mock_calcular_hash, mocks, dto
    ):
        """Control positivo: sin mockear el fallo, el flujo debe
        completarse con normalidad (commit si se llama, no rollback)."""
        mock_calcular_hash.return_value = "hash-simulado-valido"

        use_case = SolicitarRecuperacionUseCase(
            usuarios_repo=mocks["usuarios_repo"],
            cuentas_repo=mocks["cuentas_repo"],
            eventos_repo=mocks["eventos_repo"],
            db=mocks["db"],
        )

        resultado = use_case.execute(dto, ip="10.0.0.1")

        mocks["db"].commit.assert_called_once()
        mocks["db"].rollback.assert_not_called()
        mock_send_email.assert_called_once()
        assert "recibirás instrucciones" in resultado