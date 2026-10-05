"""Aislamiento compartido por toda la suite."""
from __future__ import annotations

import os
import uuid
import pytest
from typing import Generator
from fastapi.testclient import TestClient
from src.biological_assets.application.use_cases import _registrar_evento_bitacora as bitacora
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from main import app 

@pytest.fixture(autouse=True)
def _buffer_auditoria_m02_aislado(tmp_path, monkeypatch) -> None:
    """RF-52 E1/E3: el buffer de auditoría de M02 y el control de carga son estado
    de proceso. Con el `logs/` real, el fallo simulado de una prueba se
    "recuperaría" dentro del repositorio falso de la siguiente; con un solo
    ControlCarga, las ráfagas de una prueba contarían para la siguiente.
    """
    monkeypatch.setattr(bitacora, '_DIR', tmp_path / 'logs')
    monkeypatch.setattr(bitacora, '_control', bitacora.ControlCarga())


@pytest.fixture(scope="session")
def engine_test():
    """Crea el motor de base de datos tomando credenciales del entorno (Punto 11)."""
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5432")
    user = os.getenv("DB_USER", "postgres")
    password = os.getenv("DB_PASSWORD", "postgres")
    db_name = os.getenv("DB_NAME", "sgpmp_test")
    
    test_db_url = f"postgresql://{user}:{password}@{host}:{port}/{db_name}"
    
    engine = create_engine(test_db_url)
    yield engine
    engine.dispose()

@pytest.fixture(scope="session")
def SessionLocalTest(engine_test):
    """Fábrica de sesiones vinculada al motor de pruebas."""
    return sessionmaker(autocommit=False, autoflush=False, bind=engine_test)

@pytest.fixture
def test_run_id() -> str:
    """Genera un ID de corrida único para cada prueba individual."""
    return f"pytest-{uuid.uuid4()}"

@pytest.fixture
def db_session(engine_test, SessionLocalTest) -> Generator[Session, None, None]:
    """
    Fixture de BD pura (Punto 3).
    Otorga una sesión aislada con ROLLBACK al final, diseñada para pruebas unitarias
    de repositorios o casos de uso que no pasan por la red HTTP.
    """
    connection = engine_test.connect()
    transaction = connection.begin()
    
    session = SessionLocalTest(bind=connection)
    session.begin_nested() # SAVEPOINT
    
    yield session
    
    session.close()
    transaction.rollback()
    connection.close()

@pytest.fixture
def sandbox_client(test_run_id, monkeypatch) -> Generator[TestClient, None, None]:
    """
    Cliente HTTP inteligente (Punto 12).
    Inyecta automáticamente el header del sandbox para que el middleware 
    real asuma el control de la transacción sin tener que 'hackear' `get_db`.
    """
    # 1. Habilitar la variable de entorno obligatoria para el middleware
    monkeypatch.setenv("ENABLE_TEST_SANDBOX", "true")
    
    # 2. Inicializar el cliente con el header mágico
    client = TestClient(app)
    client.headers.update({"X-Test-Run-Id": test_run_id})
    
    yield client
    

    client.delete(f"/test-control/runs/{test_run_id}")