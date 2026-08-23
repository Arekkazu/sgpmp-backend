"""Integración RF-10: persistencia y consulta de categorías canónicas."""
from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.identity_access.domain.value_objects.evento_categoria import EventoCategoria
from src.identity_access.infrastructure.repositories.evento_repository import (
    SqlAlchemyEventoRepository,
)

pytestmark = pytest.mark.integration


@pytest.mark.parametrize(
    ("tipo_evento", "categoria_esperada"),
    [
        (3, "AUTENTICACION"),
        (12, "MODIFICACION"),
        (17, "CONSULTA"),
        (20, "AUTENTICACION"),
    ],
)
def test_repositorio_persiste_categoria_canonica_en_postgresql(
    db_session: Session,
    crear_usuario_db,
    tipo_evento: int,
    categoria_esperada: str,
) -> None:
    usuario = crear_usuario_db()
    repo = SqlAlchemyEventoRepository(db_session)

    repo.registrar(
        tipo_evento=tipo_evento,
        exitoso=True,
        id_usuario=usuario["id_usuario"],
        detalle={"origen": "pytest"},
    )

    categoria = db_session.execute(
        text(
            """
            SELECT categoria
            FROM modulo1.eventos
            WHERE id_usuario = :id_usuario AND tipo_evento = :tipo_evento
            ORDER BY id_evento DESC
            LIMIT 1
            """
        ),
        {
            "id_usuario": usuario["id_usuario"],
            "tipo_evento": tipo_evento,
        },
    ).scalar_one()

    assert categoria == categoria_esperada


def test_filtro_por_categoria_incluye_historicos_mal_clasificados(
    db_session: Session,
    crear_usuario_db,
    crear_evento_db,
) -> None:
    usuario = crear_usuario_db()
    id_evento = crear_evento_db(
        id_usuario=usuario["id_usuario"],
        tipo_evento=12,
        categoria="AUTENTICACION",
        detalle={"origen": "historico"},
    )
    repo = SqlAlchemyEventoRepository(db_session)

    eventos = repo.listar_eventos(
        id_usuario=usuario["id_usuario"],
        tipo_evento=None,
        fecha_desde=None,
        fecha_hasta=None,
        offset=0,
        limit=20,
        categoria=EventoCategoria.MODIFICACION,
    )

    assert len(eventos) == 1
    evento, integridad_ok = eventos[0]
    assert evento.id_evento == id_evento
    assert evento.categoria == "MODIFICACION"
    assert integridad_ok is True
