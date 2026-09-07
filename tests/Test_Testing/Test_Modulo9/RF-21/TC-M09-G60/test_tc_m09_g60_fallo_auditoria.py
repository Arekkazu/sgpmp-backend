"""
TC-M09-G60 (TC-M09-115) - Rollback del registro de dispositivo IoT ante
fallo del proceso de auditoria.

RF relacionado: RF-21, CU-05 Gestionar Dispositivos IoT
Categoria: Integracion (RESILIENCIA / integridad transaccional)

Criterio de aceptacion (segun la ficha):
    "Verificar que el registro del dispositivo se revierta cuando falle
    el proceso obligatorio de auditoria." Dato de prueba: registro
    valido con simulacion de fallo en el proceso de auditoria.
    Resultado esperado: el dispositivo no debe permanecer almacenado
    despues del fallo (debe aplicarse rollback).

Por que local (mismo criterio que test_tc_m01_044_fallo_smtp.py): no
hace falta un fallo real de base de datos para probar esto. El propio
codigo de RegistrarDispositivoIotUseCase.execute()
(src/configuration/application/use_cases/dispositivos_iot/
registrar_dispositivo_iot_use_case.py) ya envuelve el flush del
dispositivo + el registro de auditoria en un unico bloque
try/except que hace rollback() y relanza la excepcion:

    try:
        dispositivo_guardado = self.dispositivo_repo.guardar(dispositivo)
        self.auditoria_repo.registrar(...)
        self.db.commit()
    except Exception:
        self.db.rollback()
        raise

Para esta prueba basta con simular ESE resultado final (el paso de
auditoria revienta) parcheando auditoria_repo.registrar en el punto
donde lo usa el use case, sin necesitar una base de datos real: como
el repositorio solo hizo flush() (no commit()) antes de fallar, el
rollback() deshace exactamente esa fila todavia no confirmada. Se
verifica el mismo contrato en dos niveles: (1) el use case en
aislamiento, con dobles de prueba, y (2) el endpoint completo via
TestClient, confirmando que rollback() se invoca sobre la sesion real
que uso el request y que el commit() nunca llega a ejecutarse.

Como correrlo (desde la raiz del repo, con las env vars seteadas):
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    python -m pytest <ruta>\\test_tc_m09_g60_fallo_auditoria.py -v \
        --html=Resultados/reporte-TC-M09-G60.html --self-contained-html
"""
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.configuration.application.use_cases.dispositivos_iot.registrar_dispositivo_iot_use_case import (
    RegistrarDispositivoIotUseCase,
)
from src.configuration.domain.entities.dispositivo_iot import DispositivoIot
from src.configuration.domain.value_objects.serial_dispositivo import SerialDispositivo
from src.configuration.infrastructure.dto.registrar_dispositivo_iot_dto import (
    RegistrarDispositivoIotDTO,
)
from src.identity_access.infrastructure.dependencies import UsuarioActual

SERIAL_PRUEBA = "TC-M09-G60-FALLO-AUDITORIA"
MENSAJE_FALLO_AUDITORIA = "Fallo simulado en el proceso de auditoria (TC-M09-G60)"


def _falla_auditoria_simulada() -> RuntimeError:
    """Excepcion generica: RegistrarDispositivoIotUseCase captura 'Exception'
    a secas en su bloque de rollback, no un tipo de error especifico de BD,
    asi que cualquier fallo del paso de auditoria debe activar el mismo
    camino de reversion."""
    return RuntimeError(MENSAJE_FALLO_AUDITORIA)


def _construir_use_case_con_dobles():
    """Dobles de prueba: area activa, tipo de dispositivo valido, serial no
    duplicado -- llega exactamente al punto donde el use case guarda el
    dispositivo (flush) y luego intenta auditar (paso que se hara fallar)."""
    area = MagicMock()
    area.es_activo = True

    infra_repo = MagicMock()
    infra_repo.obtener_por_id.return_value = area

    tipo_repo = MagicMock()
    tipo_repo.obtener_por_id.return_value = MagicMock()  # no None => tipo valido

    dispositivo_guardado = DispositivoIot.crear(
        serial=SerialDispositivo(SERIAL_PRUEBA),
        descripcion="Registro valido antes del fallo de auditoria",
        id_infraestructura=1,
        id_tipo_dispositivo=1,
        es_activo=True,
    )
    dispositivo_guardado.id_dispositivo_iot = 999  # simula el ID asignado por el flush

    dispositivo_repo = MagicMock()
    dispositivo_repo.obtener_por_serial.return_value = None  # sin duplicado
    dispositivo_repo.guardar.return_value = dispositivo_guardado

    auditoria_repo = MagicMock()
    auditoria_repo.registrar.side_effect = _falla_auditoria_simulada()

    db = MagicMock()

    use_case = RegistrarDispositivoIotUseCase(
        db=db,
        dispositivo_repo=dispositivo_repo,
        infra_repo=infra_repo,
        tipo_repo=tipo_repo,
        auditoria_repo=auditoria_repo,
    )
    return use_case, dispositivo_repo, auditoria_repo, db


class TestTCM09G60FalloAuditoria:
    """Suite de pruebas para TC-M09-G60 / TC-M09-115."""

    def test_fallo_auditoria_debe_revertir_la_transaccion(self):
        """
        RF-21: si el registro obligatorio de auditoria falla luego de que el
        dispositivo ya fue guardado (flush), el use case debe:
          1. Propagar la excepcion (no debe tragarsela ni responder como si
             el registro hubiera tenido exito).
          2. Ejecutar db.rollback() -- deshace el flush del dispositivo.
          3. NO ejecutar db.commit() bajo ninguna circunstancia.
        """
        use_case, dispositivo_repo, auditoria_repo, db = _construir_use_case_con_dobles()
        dto = RegistrarDispositivoIotDTO(
            serial=SERIAL_PRUEBA,
            descripcion="Registro valido antes del fallo de auditoria",
            id_infraestructura=1,
            id_tipo_dispositivo=1,
            es_activo=True,
        )
        usuario_actual = UsuarioActual(id_usuario=1, id_token=1, id_rol=1, id_estado_cuenta=2)

        excepcion_lanzada = None
        try:
            use_case.execute(dto, usuario_actual)
        except Exception as exc:
            excepcion_lanzada = exc

        assert excepcion_lanzada is not None, (
            "RF-21 exige que un fallo del proceso de auditoria se propague "
            "(no puede reportarse como registro exitoso); el use case no "
            "lanzo ninguna excepcion."
        )
        assert MENSAJE_FALLO_AUDITORIA in str(excepcion_lanzada)

        dispositivo_repo.guardar.assert_called_once()
        auditoria_repo.registrar.assert_called_once()

        db.rollback.assert_called_once()
        db.commit.assert_not_called()

    def test_endpoint_no_persiste_el_dispositivo_cuando_falla_la_auditoria(self):
        """
        RF-21: POST /configuracion/dispositivos-iot debe responder con un
        error (nunca 201) cuando el proceso de auditoria falla, y la sesion
        de BD real que uso el request debe haber recibido rollback() -- el
        dispositivo no debe quedar almacenado tras el fallo.
        """
        from src.configuration.infrastructure.repositories.auditoria_dispositivo_iot_repository import (
            SqlAlchemyAuditoriaDispositivoIotRepository,
        )
        from src.configuration.infrastructure.repositories.dispositivo_iot_repository import (
            SqlAlchemyDispositivoIotRepository,
        )
        from src.configuration.infrastructure.repositories.infraestructura_repository import (
            SqlAlchemyInfraestructuraRepository,
        )
        from src.configuration.infrastructure.repositories.tipo_dispositivo_iot_repository import (
            SqlAlchemyTipoDispositivoIotRepository,
        )
        from src.configuration.infrastructure.routers.dispositivo_iot_router import (
            router as dispositivo_iot_router,
        )
        from src.identity_access.infrastructure.dependencies import get_current_user
        from src.shared.database import get_db
        from src.shared.error_handlers import register_error_handlers

        area = MagicMock()
        area.es_activo = True

        dispositivo_guardado = DispositivoIot.crear(
            serial=SerialDispositivo(SERIAL_PRUEBA + "-HTTP"),
            descripcion="Registro valido antes del fallo de auditoria (HTTP)",
            id_infraestructura=1,
            id_tipo_dispositivo=1,
            es_activo=True,
        )
        dispositivo_guardado.id_dispositivo_iot = 998

        fake_db = MagicMock()

        app = FastAPI()
        register_error_handlers(app)
        app.include_router(dispositivo_iot_router)

        def _fake_db():
            yield fake_db

        def _fake_usuario_actual():
            return UsuarioActual(id_usuario=1, id_token=1, id_rol=1, id_estado_cuenta=2)

        app.dependency_overrides[get_db] = _fake_db
        app.dependency_overrides[get_current_user] = _fake_usuario_actual

        with (
            patch.object(SqlAlchemyInfraestructuraRepository, "obtener_por_id", return_value=area),
            patch.object(SqlAlchemyTipoDispositivoIotRepository, "obtener_por_id", return_value=MagicMock()),
            patch.object(SqlAlchemyDispositivoIotRepository, "obtener_por_serial", return_value=None),
            patch.object(SqlAlchemyDispositivoIotRepository, "guardar", return_value=dispositivo_guardado),
            patch.object(
                SqlAlchemyAuditoriaDispositivoIotRepository,
                "registrar",
                side_effect=_falla_auditoria_simulada(),
            ),
        ):
            client = TestClient(app, raise_server_exceptions=False)
            response = client.post(
                "/configuracion/dispositivos-iot",
                json={
                    "serial": SERIAL_PRUEBA + "-HTTP",
                    "descripcion": "Registro valido antes del fallo de auditoria (HTTP)",
                    "id_infraestructura": 1,
                    "id_tipo_dispositivo": 1,
                    "es_activo": True,
                },
            )

        assert response.status_code != 201, (
            "RF-21 exige que un fallo del proceso de auditoria NO resulte "
            f"en un registro exitoso; el endpoint respondio 201. Cuerpo: {response.text}"
        )
        assert response.status_code >= 500, (
            "Se esperaba que el fallo interno de auditoria escalara como un "
            f"error de servidor; el endpoint respondio {response.status_code}. "
            f"Cuerpo: {response.text}"
        )

        fake_db.rollback.assert_called_once()
        fake_db.commit.assert_not_called()

        app.dependency_overrides.clear()
