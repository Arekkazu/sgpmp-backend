"""Smoke check del TC-M04-G099: verifica db_session + import del repo."""
from src.prediction.infrastructure.repositories import evento_auditoria_m04_repository
from src.prediction.infrastructure.repositories.evento_auditoria_m04_repository import (
    SqlAlchemyEventoAuditoriaM04Repository,
)


def test_smoke_import_y_db(db_session):
    assert evento_auditoria_m04_repository.datetime is not None
    repo = SqlAlchemyEventoAuditoriaM04Repository(db_session)
    assert repo is not None
    print("[SMOKE_OK] import y db_session OK")
