# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-23 | Arekkazu | PR-667: fechas en UTC y día calendario en la zona del usuario (X-Zona-Horaria) |
# | 2026-10-25 | DanielRuiz | PR-706: une fixtures de dev (en_colombia) y del sandbox de test |
"""Aislamiento compartido por toda la suite."""
from __future__ import annotations

import os
import uuid
from typing import Generator
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

import src.shared.fechas as fechas
from src.biological_assets.application.use_cases import _registrar_evento_bitacora as bitacora


@pytest.fixture(autouse=True)
def _buffer_auditoria_m02_aislado(tmp_path, monkeypatch) -> None:
    """RF-52 E1/E3: el buffer de auditoría de M02 y el control de carga son estado
    de proceso. Con el `logs/` real, el fallo simulado de una prueba se
    "recuperaría" dentro del repositorio falso de la siguiente; con un solo
    ControlCarga, las ráfagas de una prueba contarían para la siguiente.
    """
    monkeypatch.setattr(bitacora, '_DIR', tmp_path / 'logs')
    monkeypatch.setattr(bitacora, '_control', bitacora.ControlCarga())


@pytest.fixture
def en_colombia():
    """El request trae ``X-Zona-Horaria: America/Bogota`` (sin ella el día es el de UTC)."""
    token = fechas.establecer_zona_usuario('America/Bogota')
    yield ZoneInfo('America/Bogota')
    fechas._zona.reset(token)


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
    # Import diferido: `main` exige DATABASE_URL al importarse y las pruebas
    # unitarias que no usan esta fixture no deben depender de esa variable.
    from main import app

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
