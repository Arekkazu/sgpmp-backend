# | Fecha      | Nombre       | Que se hizo                                                          |
# |------------|--------------|----------------------------------------------------------------------|
# | 2026-11-21 | destroyerban | INC-M08-383-G014 RF-105: notificación ajena → 403 con RLS real       |
"""INC-M08-383-G014 (#1199) contra PostgreSQL con RLS (rol ``sgpmp_app``).

Con la sesión del Productor, la RLS de ``modulo1.notificaciones`` le oculta la del otro usuario. El
caso de uso pregunta como sistema solo si existe, responde 403 con el mensaje de RF-105 restricción 4
y no cambia nada; luego la sesión sigue con la identidad del Productor.
"""
from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.identity_access.application.use_cases.notificaciones.marcar_notificacion_leida_use_case import (
    AtenderNotificacionUseCase,
    DescartarNotificacionUseCase,
    MarcarNotificacionLeidaUseCase,
)
from src.identity_access.infrastructure.repositories.notificacion_repository import SqlAlchemyNotificacionRepository
from src.shared.database import declarar_identidad
from src.shared.errors import AuthorizationError, NotFoundError

pytestmark = pytest.mark.integration

CANAL_INTERNO = 2


def _como(db: Session, usuario: dict, rol: str) -> None:
    db.execute(text("SET LOCAL ROLE sgpmp_app"))
    declarar_identidad(db, usuario["id_usuario"], rol)
    db.connection().execute(text("SELECT set_config('app.current_user_id', :u, true), "
                                 "set_config('app.current_role', :r, true)"),
                            {"u": str(usuario["id_usuario"]), "r": rol})


def _estado(db: Session, id_notificacion: int) -> tuple[str, bool]:
    return db.execute(text("SELECT estado::text, es_leido FROM modulo1.notificaciones WHERE id_notificacion = :n"),
                      {"n": id_notificacion}).one()


def test_productor_recibe_403_sobre_la_notificacion_de_otro_y_nada_cambia(
        db_session: Session, crear_usuario_db, crear_evento_db):
    productor, otro = crear_usuario_db(id_rol=2), crear_usuario_db(id_rol=3)
    repo = SqlAlchemyNotificacionRepository(db_session)
    evento = crear_evento_db(id_usuario=otro["id_usuario"], tipo_evento=2, categoria="AUTENTICACION")
    ajena = repo.registrar(evento, otro["id_usuario"], CANAL_INTERNO, "Aviso del otro usuario", "en_cola")
    db_session.flush()

    _como(db_session, productor, "Productor")
    # La premisa: con su sesión no la ve, pero existe.
    assert repo.obtener_interna(ajena, productor["id_usuario"]) is None
    assert repo.existe_interna(ajena) is True
    assert repo.existe_interna(ajena + 10_000) is False

    accion = "Revisé el galpón y la temperatura volvió a lo normal"
    for ejecutar in (
        lambda: MarcarNotificacionLeidaUseCase(repo, db_session).execute(ajena, productor["id_usuario"]),
        lambda: AtenderNotificacionUseCase(repo, db_session).execute(ajena, productor["id_usuario"], accion),
        lambda: DescartarNotificacionUseCase(repo, db_session).execute(ajena, productor["id_usuario"]),
    ):
        with pytest.raises(AuthorizationError) as exc:
            ejecutar()
        assert exc.value.code == "NOTIFICACION_AJENA"
        assert exc.value.message == "No tiene permisos para modificar notificaciones de otros usuarios."

    with pytest.raises(NotFoundError):
        MarcarNotificacionLeidaUseCase(repo, db_session).execute(ajena + 10_000, productor["id_usuario"])

    # Después de preguntar como sistema, la sesión vuelve a ser la del Productor.
    assert db_session.execute(text("SELECT current_setting('app.current_user_id', true)")).scalar() == \
        str(productor["id_usuario"])
    assert repo.obtener_interna(ajena, productor["id_usuario"]) is None
    db_session.execute(text("RESET ROLE"))
    assert _estado(db_session, ajena) == ("NUEVA", False)
