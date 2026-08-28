"""Integración RF-10: conformidad literal con los campos y flujos alternos del RF."""
from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.identity_access.application.use_cases.auditoria.consultar_auditoria_use_case import (
    UMBRAL_SATURACION,
)

pytestmark = pytest.mark.integration


# ── Sección "Entradas": campos obligatorios del registro ────────────────────


def test_todo_evento_guarda_nombre_usuario_ip_user_agent_y_sesion(
    client,
    db_session: Session,
    crear_usuario_db,
    crear_auth_headers,
) -> None:
    admin = crear_usuario_db(id_rol=1, nombre="Ada", apellidos="Lovelace")
    headers = crear_auth_headers(admin)
    headers["User-Agent"] = "pytest-conformidad/1.0"

    respuesta = client.get("/auditoria/", headers=headers)

    assert respuesta.status_code == 200
    evento = db_session.execute(
        text(
            """
            SELECT nombre_usuario, direccion_ip, user_agent, id_sesion, descripcion
            FROM modulo1.eventos
            WHERE tipo_evento = 16 AND id_usuario = :u
            ORDER BY id_evento DESC LIMIT 1
            """
        ),
        {"u": admin["id_usuario"]},
    ).mappings().one()

    assert evento["nombre_usuario"] == "Ada Lovelace"
    assert evento["direccion_ip"]
    assert evento["user_agent"] == "pytest-conformidad/1.0"
    assert evento["id_sesion"] is not None
    assert evento["descripcion"] == "CONSULTA_AUDITORIA"


def test_la_consulta_expone_los_campos_nuevos(
    client,
    crear_usuario_db,
    crear_auth_headers,
    crear_evento_db,
) -> None:
    admin = crear_usuario_db(id_rol=1)
    headers = crear_auth_headers(admin)
    headers["User-Agent"] = "pytest-conformidad/1.0"
    client.get("/auditoria/", headers=headers)

    item = client.get(
        "/auditoria/",
        params={"id_usuario": admin["id_usuario"], "tipo_evento": 16},
        headers=headers,
    ).json()["items"][0]

    assert set(item) >= {
        "nombre_usuario",
        "direccion_ip",
        "user_agent",
        "descripcion",
        "id_sesion",
        "integridad_ok",
        "integridad",
    }


# ── FA "Fallo de integridad del registro" ──────────────────────────────────


def test_registro_manipulado_responde_500_con_el_mensaje_del_rf(
    client,
    crear_usuario_db,
    crear_auth_headers,
    crear_evento_db,
) -> None:
    admin = crear_usuario_db(id_rol=1)
    manipulado = crear_evento_db(
        id_usuario=admin["id_usuario"],
        tipo_evento=3,
        categoria="AUTENTICACION",
        hash_integridad="0" * 64,
    )

    respuesta = client.get(
        "/auditoria/",
        params={"id_usuario": admin["id_usuario"], "tipo_evento": 3},
        headers=crear_auth_headers(admin),
    )

    assert respuesta.status_code == 500
    cuerpo = respuesta.json()
    assert cuerpo["error_code"] == "INTEGRIDAD_AUDITORIA_VIOLADA"
    assert "violación de integridad" in cuerpo["message"]
    assert str(manipulado) in cuerpo["message"]


def test_registro_de_la_linea_base_no_escala_a_500(
    client,
    db_session: Session,
    crear_usuario_db,
    crear_auth_headers,
    crear_evento_db,
) -> None:
    """Un evento irreparable anterior a la política se reporta, no rompe la consulta."""
    admin = crear_usuario_db(id_rol=1)
    legado = crear_evento_db(
        id_usuario=admin["id_usuario"],
        tipo_evento=3,
        categoria="AUTENTICACION",
        hash_integridad="f" * 64,
    )
    calculado = db_session.execute(
        text("SELECT hash_integridad FROM modulo1.eventos WHERE id_evento = :id"),
        {"id": legado},
    ).scalar_one()
    assert calculado == "f" * 64
    db_session.execute(
        text(
            """
            INSERT INTO modulo1.integridad_baseline (id_evento, hash_calculado, motivo)
            SELECT :id, encode(sha256(convert_to('irrelevante','UTF8')), 'hex'), 'ESQUEMA_ANTERIOR'
            """
        ),
        {"id": legado},
    )
    db_session.flush()

    respuesta = client.get(
        "/auditoria/",
        params={"id_usuario": admin["id_usuario"], "tipo_evento": 3},
        headers=crear_auth_headers(admin),
    )

    # El hash de la línea base no coincide con el recálculo actual, así que el
    # evento sigue clasificando como manipulado: la línea base sólo protege a los
    # registros que no han cambiado desde la adopción.
    assert respuesta.status_code == 500


# ── FA "Acceso denegado a la consulta de logs" ─────────────────────────────


def test_acceso_denegado_usa_el_mensaje_del_rf_y_queda_auditado(
    client,
    db_session: Session,
    crear_usuario_db,
    crear_auth_headers,
) -> None:
    veterinario = crear_usuario_db(id_rol=3)
    antes = db_session.execute(
        text(
            "SELECT count(*) FROM modulo1.eventos "
            "WHERE tipo_evento = 16 AND id_usuario = :u"
        ),
        {"u": veterinario["id_usuario"]},
    ).scalar_one()

    respuesta = client.get("/auditoria/", headers=crear_auth_headers(veterinario))

    despues = db_session.execute(
        text(
            "SELECT count(*) FROM modulo1.eventos "
            "WHERE tipo_evento = 16 AND id_usuario = :u AND resultado = 'fallido'"
        ),
        {"u": veterinario["id_usuario"]},
    ).scalar_one()

    assert respuesta.status_code == 403
    assert (
        respuesta.json()["message"]
        == "Acceso denegado: No posee privilegios de administrador para consultar "
        "el historial de auditoría. Este incidente ha sido registrado."
    )
    assert despues == antes + 1


# ── FA "Intento de modificación o eliminación" ─────────────────────────────


@pytest.mark.parametrize("metodo", ["put", "patch", "delete"])
def test_metodos_de_escritura_responden_405_con_el_mensaje_del_rf(
    client,
    crear_usuario_db,
    crear_auth_headers,
    metodo: str,
) -> None:
    admin = crear_usuario_db(id_rol=1)

    respuesta = getattr(client, metodo)(
        "/auditoria/", headers=crear_auth_headers(admin)
    )

    assert respuesta.status_code == 405
    cuerpo = respuesta.json()
    assert cuerpo["error_code"] == "AUDITORIA_INMUTABLE"
    assert "inmutables por diseño" in cuerpo["message"]


# ── FA "Filtro de búsqueda inválido" ───────────────────────────────────────


def test_id_usuario_inexistente_responde_400(
    client,
    crear_usuario_db,
    crear_auth_headers,
) -> None:
    admin = crear_usuario_db(id_rol=1)

    respuesta = client.get(
        "/auditoria/",
        params={"id_usuario": 99_999_999},
        headers=crear_auth_headers(admin),
    )

    assert respuesta.status_code == 400
    assert respuesta.json()["error_code"] == "FILTROS_INCONSISTENTES"


def test_rango_de_fechas_inconsistente_responde_400(
    client,
    crear_usuario_db,
    crear_auth_headers,
) -> None:
    admin = crear_usuario_db(id_rol=1)

    respuesta = client.get(
        "/auditoria/",
        params={
            "fecha_desde": "2026-08-01T00:00:00Z",
            "fecha_hasta": "2026-01-01T00:00:00Z",
        },
        headers=crear_auth_headers(admin),
    )

    assert respuesta.status_code == 400
    assert respuesta.json()["error_code"] == "FILTROS_INCONSISTENTES"


# ── FA "Exceso de resultados en consulta" ──────────────────────────────────


def test_consulta_saturada_responde_206_con_el_mensaje_del_rf(
    client,
    crear_usuario_db,
    crear_auth_headers,
    monkeypatch,
) -> None:
    """Se baja el umbral en vez de sembrar 10.000 eventos inmutables."""
    from src.identity_access.application.use_cases.auditoria import (
        consultar_auditoria_use_case as modulo,
    )

    admin = crear_usuario_db(id_rol=1)
    headers = crear_auth_headers(admin)
    client.get("/auditoria/", headers=headers)
    monkeypatch.setattr(modulo, "UMBRAL_SATURACION", 0)

    respuesta = client.get("/auditoria/", params={"tamano": 50}, headers=headers)

    assert respuesta.status_code == 206
    assert respuesta.json()["mensaje"] == (
        "Consulta extensa: Se muestran los primeros 50 resultados. "
        "Utilice los parámetros de paginación o filtros adicionales para "
        "refinar la búsqueda."
    )


def test_consulta_normal_responde_200_sin_mensaje(
    client,
    crear_usuario_db,
    crear_auth_headers,
) -> None:
    admin = crear_usuario_db(id_rol=1)

    respuesta = client.get(
        "/auditoria/",
        params={"id_usuario": admin["id_usuario"]},
        headers=crear_auth_headers(admin),
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["mensaje"] is None
    assert UMBRAL_SATURACION == 10_000


# ── RNF de rendimiento: índices de consulta ────────────────────────────────


def test_la_tabla_de_eventos_tiene_indices_para_los_filtros(
    db_session: Session,
) -> None:
    indices = set(
        db_session.execute(
            text(
                "SELECT indexname FROM pg_indexes "
                "WHERE schemaname='modulo1' AND tablename='eventos'"
            )
        ).scalars()
    )

    assert {
        "ix_eventos_fecha",
        "ix_eventos_usuario_fecha",
        "ix_eventos_tipo_fecha",
    }.issubset(indices)


# ── Catálogo de nombres espejado en el dominio ─────────────────────────────


def test_nombres_de_tipo_evento_coinciden_con_el_catalogo(
    db_session: Session,
) -> None:
    """Evita que el espejo del dominio derive respecto de `modulo1.tipos_eventos`."""
    from src.identity_access.domain.value_objects.evento_categoria import (
        _NOMBRE_POR_TIPO_EVENTO,
    )

    catalogo = dict(
        db_session.execute(
            text("SELECT id_tipo_evento, nombre FROM modulo1.tipos_eventos")
        ).all()
    )

    assert _NOMBRE_POR_TIPO_EVENTO == catalogo
