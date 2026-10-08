from __future__ import annotations
import os
import uuid
from typing import Generator
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from main import app
from src.biological_assets.application.use_cases import _registrar_evento_bitacora as bitacora


@pytest.fixture(autouse=True)
def _buffer_auditoria_m02_aislado(tmp_path, monkeypatch) -> None:
    """Aísla el buffer de auditoría del módulo 2 en un directorio temporal por test."""
    monkeypatch.setattr(bitacora, "_DIR", tmp_path / "logs")
    monkeypatch.setattr(bitacora, "_control", bitacora.ControlCarga())


@pytest.fixture(scope="session")
def engine_test():
    test_db_url = os.getenv("TEST_DATABASE_URL")
    if not test_db_url:
        raise RuntimeError(
            "Falta la variable de entorno TEST_DATABASE_URL. Revisa el .env.test "
            "(o la configuración del despliegue) antes de ejecutar los tests."
        )
    engine = create_engine(test_db_url)
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def SessionLocalTest(engine_test):
    """Fábrica de sesiones vinculada al motor de pruebas."""
    return sessionmaker(autocommit=False, autoflush=False, bind=engine_test)


@pytest.fixture
def db_session(engine_test, SessionLocalTest) -> Generator[Session, None, None]:
    """
    Fixture de BD pura para pruebas unitarias de repositorios o casos de uso
    que no pasan por la red HTTP. Única definición en todo el proyecto.
    """
    connection = engine_test.connect()
    transaction = connection.begin()

    session = SessionLocalTest(bind=connection)
    session.begin_nested()  # SAVEPOINT

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def test_run_id() -> str:
    """Genera un ID de corrida único para cada prueba individual."""
    return f"pytest-{uuid.uuid4()}"


@pytest.fixture
def sandbox_client(test_run_id, monkeypatch) -> Generator[TestClient, None, None]:
    """
    Cliente HTTP que inyecta automáticamente los headers del sandbox, para
    que el middleware real controle la transacción vía HTTP.
    """
    monkeypatch.setenv("ENABLE_TEST_SANDBOX", "true")

    secret = os.getenv("TEST_SANDBOX_SECRET")
    if not secret:
        raise RuntimeError(
            "Falta la variable de entorno TEST_SANDBOX_SECRET. Debe compartirse "
            "con QA por un canal seguro antes de usar sandbox_client."
        )

    client = TestClient(app)
    client.headers.update({
        "X-Test-Run-Id": test_run_id,
        "X-Sandbox-Secret": secret,
    })

    yield client

    client.delete(
        f"/test-control/runs/{test_run_id}",
        headers={"X-Sandbox-Secret": secret},
    )