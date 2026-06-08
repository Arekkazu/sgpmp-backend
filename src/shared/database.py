"""Configuración del engine SQLAlchemy y generador de sesiones de base de datos.

Exporta `get_db`, el generador FastAPI/Depends que provee una sesión por request
y la cierra al finalizar, y `SessionLocal` para usos fuera del contexto web.
"""
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    """Generador de sesiones SQLAlchemy para inyección de dependencias FastAPI.

    Yields:
        Session: Sesión de base de datos activa para el request actual.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
