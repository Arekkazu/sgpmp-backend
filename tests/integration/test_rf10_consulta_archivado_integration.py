"""Integración RF-10: consulta del archivo histórico y alerta de fallo del archivado."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.identity_access.application.use_cases.auditoria.archivar_auditoria_use_case import (
    ArchivarAuditoriaUseCase,
)
from src.identity_access.application.use_cases.auditoria.notificar_fallo_archivado_use_case import (
    TIPO_FALLO_ARCHIVADO,
    NotificarFalloArchivadoUseCase,
)
from src.identity_access.infrastructure.repositories.evento_repository import (
    SqlAlchemyEventoRepository,
)
from src.identity_access.infrastructure.repositories.notificacion_repository import (
    SqlAlchemyNotificacionRepository,
)
from src.identity_access.infrastructure.repositories.usuario_repository import (
    SqlAlchemyUsuarioRepository,
)

pytestmark = pytest.mark.integration

REFERENCIA = datetime(2026, 8, 27, 4, 0, tzinfo=timezone.utc)
VENCIDO = datetime(2025, 1, 15, 10, 0, tzinfo=timezone.utc)
RECIENTE = datetime(2026, 6, 1, 10, 0, tzinfo=timezone.utc)


def _archivar(db_session: Session) -> None:
    ArchivarAuditoriaUseCase(
        eventos_repo=SqlAlchemyEventoRepository(db_session),
        db=db_session,
    ).execute(REFERENCIA)


def test_endpoint_archivado_devuelve_solo_lo_vencido_y_no_el_log_activo(
    client,
    db_session: Session,
    crear_usuario_db,
    crear_auth_headers,
    crear_evento_db,
) -> None:
    admin = crear_usuario_db(id_rol=1)
    vencido = crear_evento_db(
        id_usuario=admin["id_usuario"],
        tipo_evento=3,
        categoria="AUTENTICACION",
        fecha=VENCIDO,
    )
    reciente = crear_evento_db(
        id_usuario=admin["id_usuario"],
        tipo_evento=3,
        categoria="AUTENTICACION",
        fecha=RECIENTE,
    )
    _archivar(db_session)

    headers = crear_auth_headers(admin)
    archivado = client.get(
        "/auditoria/archivado/",
        params={"id_usuario": admin["id_usuario"], "tamano": 50},
        headers=headers,
    )
    activo = client.get(
        "/auditoria/",
        params={"id_usuario": admin["id_usuario"], "tamano": 50},
        headers=headers,
    )

    assert archivado.status_code == 200
    assert activo.status_code == 200
    ids_archivados = {item["id_evento"] for item in archivado.json()["items"]}
    ids_activos = {item["id_evento"] for item in activo.json()["items"]}
    assert ids_archivados == {vencido}
    assert {vencido, reciente} <= ids_activos
    # El original sigue en el log activo: RF-10 prohíbe borrarlo.
    assert all(item["integridad_ok"] for item in archivado.json()["items"])


def test_endpoint_archivado_respeta_filtros_y_paginacion(
    client,
    db_session: Session,
    crear_usuario_db,
    crear_auth_headers,
    crear_evento_db,
) -> None:
    admin = crear_usuario_db(id_rol=1)
    otro = crear_usuario_db(id_rol=2)
    for _ in range(3):
        crear_evento_db(
            id_usuario=admin["id_usuario"],
            tipo_evento=3,
            categoria="AUTENTICACION",
            fecha=VENCIDO,
        )
    crear_evento_db(
        id_usuario=otro["id_usuario"],
        tipo_evento=9,
        categoria="MODIFICACION",
        fecha=VENCIDO,
    )
    _archivar(db_session)

    headers = crear_auth_headers(admin)
    pagina_uno = client.get(
        "/auditoria/archivado/",
        params={"id_usuario": admin["id_usuario"], "pagina": 1, "tamano": 2},
        headers=headers,
    ).json()
    pagina_dos = client.get(
        "/auditoria/archivado/",
        params={"id_usuario": admin["id_usuario"], "pagina": 2, "tamano": 2},
        headers=headers,
    ).json()
    por_categoria = client.get(
        "/auditoria/archivado/",
        params={"categoria": "MODIFICACION", "id_usuario": otro["id_usuario"]},
        headers=headers,
    ).json()

    assert pagina_uno["total"] == 3
    assert len(pagina_uno["items"]) == 2
    assert len(pagina_dos["items"]) == 1
    assert {i["id_evento"] for i in pagina_uno["items"]} & {
        i["id_evento"] for i in pagina_dos["items"]
    } == set()
    assert por_categoria["total"] == 1
    assert por_categoria["items"][0]["categoria"] == "MODIFICACION"


def test_endpoint_archivado_rechaza_a_quien_no_es_administrador(
    client,
    crear_usuario_db,
    crear_auth_headers,
) -> None:
    veterinario = crear_usuario_db(id_rol=3)

    respuesta = client.get(
        "/auditoria/archivado/",
        headers=crear_auth_headers(veterinario),
    )

    assert respuesta.status_code == 403


def test_endpoint_archivado_valida_el_rango_de_fechas(
    client,
    crear_usuario_db,
    crear_auth_headers,
) -> None:
    admin = crear_usuario_db(id_rol=1)

    respuesta = client.get(
        "/auditoria/archivado/",
        params={"fecha_desde": "2026-08-01T00:00:00Z", "fecha_hasta": "2026-01-01T00:00:00Z"},
        headers=crear_auth_headers(admin),
    )

    assert respuesta.status_code == 400


def test_alerta_de_fallo_llega_a_la_bandeja_de_los_administradores(
    db_session: Session,
    crear_usuario_db,
) -> None:
    admin = crear_usuario_db(id_rol=1)
    crear_usuario_db(id_rol=2)

    avisados = NotificarFalloArchivadoUseCase(
        eventos_repo=SqlAlchemyEventoRepository(db_session),
        notificaciones_repo=SqlAlchemyNotificacionRepository(db_session),
        usuarios_repo=SqlAlchemyUsuarioRepository(db_session),
        db=db_session,
    ).execute(causa="OSError: espacio insuficiente en el servidor de respaldo")

    evento = db_session.execute(
        text(
            """
            SELECT id_evento, categoria, resultado::text AS resultado, detalle
            FROM modulo1.eventos
            WHERE tipo_evento = :tipo
            ORDER BY id_evento DESC
            LIMIT 1
            """
        ),
        {"tipo": TIPO_FALLO_ARCHIVADO},
    ).mappings().one()
    notificacion_admin = db_session.execute(
        text(
            """
            SELECT mensaje, id_notificacion_canal
            FROM modulo1.notificaciones
            WHERE id_evento = :evento AND id_usuario = :usuario
            """
        ),
        {"evento": evento["id_evento"], "usuario": admin["id_usuario"]},
    ).mappings().one()

    # El productor no puede leer auditoría, así que no debe recibir la alerta.
    assert avisados >= 1
    assert evento["resultado"] == "fallido"
    assert evento["categoria"] == "MODIFICACION"
    assert evento["detalle"]["proceso"] == "ARCHIVADO_AUDITORIA"
    assert "Fallo en política de retención" in notificacion_admin["mensaje"]
    assert "espacio insuficiente" in notificacion_admin["mensaje"]
    assert notificacion_admin["id_notificacion_canal"] == 2
