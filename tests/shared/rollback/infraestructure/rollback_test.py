import os
import pytest
from dotenv import load_dotenv
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

# Carga las variables definidas en el .env
load_dotenv()

POSTGRES_USER = os.getenv("POSTGRES_USER")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")
POSTGRES_DB = os.getenv("POSTGRES_DB")
POSTGRES_HOST = "158.69.200.27"
POSTGRES_PORT = 5448

DATABASE_URL = (
    f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}"
    f"@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
)

engine = create_engine(DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session():
    """
    Fixture que provee una sesión de BD envuelta en una transacción.
    Al terminar la prueba, se hace ROLLBACK automático, incluso si el
    código bajo prueba ejecuta session.commit() internamente.
    """
    connection = engine.connect()
    transaction = connection.begin()  # transacción externa (nunca se confirma)

    session = TestingSessionLocal(bind=connection)
    session.begin_nested()  # SAVEPOINT

    @event.listens_for(session, "after_transaction_end")
    def restart_savepoint(sess, trans):
        if trans.nested and not trans._parent.nested:
            sess.begin_nested()

    yield session  # se entrega la sesión a la prueba

    session.close()
    transaction.rollback()  # revierte TODO lo ocurrido en la prueba
    connection.close()