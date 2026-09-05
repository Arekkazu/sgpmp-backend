"""Integración RF-14: generación central y bandeja de notificaciones."""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.identity_access.infrastructure.repositories.notificacion_repository import (
    SqlAlchemyNotificacionRepository,
)

pytestmark = pytest.mark.integration


def test_seed_indice_bandeja_es_idempotente(
    db_session: Session,
    ejecutar_sql_anotacion,
) -> None:
    ejecutar_sql_anotacion("rf14_bandeja_notificaciones.sql")
    ejecutar_sql_anotacion("rf14_bandeja_notificaciones.sql")

    indice = db_session.execute(
        text(
            """
            SELECT indexdef
            FROM pg_indexes
            WHERE schemaname='modulo1'
              AND tablename='notificaciones'
              AND indexname='ix_notificaciones_bandeja_usuario'
            """
        )
    ).scalar_one()

    assert "id_usuario" in indice
    assert "id_notificacion_canal = 2" in indice


def _override_usuario(integration_app, usuario: dict) -> None:
    integration_app.dependency_overrides[get_current_user] = lambda: UsuarioActual(
        id_usuario=usuario["id_usuario"],
        id_token=1,
        id_rol=usuario["id_rol"],
    )


def test_bandeja_filtra_canal_propietario_y_marca_lectura(
    client,
    integration_app,
    db_session: Session,
    crear_usuario_db,
    crear_evento_db,
) -> None:
    usuario = crear_usuario_db()
    otro = crear_usuario_db()
    repo = SqlAlchemyNotificacionRepository(db_session)

    evento_uno = crear_evento_db(
        id_usuario=usuario["id_usuario"],
        tipo_evento=1,
        categoria="AUTENTICACION",
    )
    evento_dos = crear_evento_db(
        id_usuario=usuario["id_usuario"],
        tipo_evento=2,
        categoria="AUTENTICACION",
    )
    evento_otro = crear_evento_db(
        id_usuario=otro["id_usuario"],
        tipo_evento=2,
        categoria="AUTENTICACION",
    )

    leida = repo.registrar(evento_uno, usuario["id_usuario"], 2, "Registro", "en_cola")
    pendiente = repo.registrar(evento_dos, usuario["id_usuario"], 2, "Activación", "en_cola")
    solo_correo = repo.registrar(
        evento_dos,
        usuario["id_usuario"],
        1,
        "Solo correo",
        "en_cola",
    )
    ajena = repo.registrar(evento_otro, otro["id_usuario"], 2, "Ajena", "en_cola")
    db_session.execute(
        text("UPDATE modulo1.notificaciones SET es_leido=TRUE WHERE id_notificacion=:id"),
        {"id": leida},
    )
    db_session.commit()
    _override_usuario(integration_app, usuario)

    listado = client.get("/notificaciones")
    assert listado.status_code == 200, listado.text
    cuerpo = listado.json()
    assert cuerpo["total"] == 2
    assert cuerpo["no_leidas"] == 1
    assert {item["id_notificacion"] for item in cuerpo["items"]} == {leida, pendiente}

    no_leidas = client.get("/notificaciones?solo_no_leidas=true")
    assert no_leidas.status_code == 200
    assert [item["id_notificacion"] for item in no_leidas.json()["items"]] == [pendiente]

    marcada = client.patch(f"/notificaciones/{pendiente}/leida")
    assert marcada.status_code == 200
    assert marcada.json()["es_leido"] is True
    assert client.patch(f"/notificaciones/{pendiente}/leida").status_code == 200

    ajena_respuesta = client.patch(f"/notificaciones/{ajena}/leida")
    assert ajena_respuesta.status_code == 404
    assert ajena_respuesta.json()["error_code"] == "NOTIFICACION_NO_ENCONTRADA"

    correo_respuesta = client.patch(f"/notificaciones/{solo_correo}/leida")
    assert correo_respuesta.status_code == 404
    assert correo_respuesta.json()["error_code"] == "NOTIFICACION_NO_ENCONTRADA"


def test_registro_y_activacion_usan_servicio_central_sin_guardar_token(
    client,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.identity_access.application.use_cases.registro import crear_usuario_use_case
    from src.shared import notificacion_service

    token = "token-rf14-no-persistir"
    correos = []
    monkeypatch.setattr(crear_usuario_use_case.secrets, "token_urlsafe", lambda _n: token)
    monkeypatch.setattr(
        notificacion_service,
        "send_email",
        lambda **datos: correos.append(datos),
    )

    sufijo = uuid.uuid4().hex
    correo = f"rf14-{sufijo}@example.com"
    respuesta = client.post(
        "/usuarios/",
        json={
            "correo_electronico": correo,
            "telefono": "3001234567",
            "tipo_identificacion": "CC",
            "numero_identificacion": str(uuid.uuid4().int % 10**15).zfill(15),
            "nombre": "Notificaciones",
            "apellidos": "RF Catorce",
            "fecha_nacimiento": "1990-01-01",
            "genero": "M",
            "contrasena": "Segura1!",
            "confirmar_contrasena": "Segura1!",
            "direccion": "Dirección de prueba",
            "captcha_token": "captcha-prueba-valido",
        },
    )
    assert respuesta.status_code == 201, respuesta.text

    id_usuario = db_session.execute(
        text(
            "SELECT id_usuario FROM modulo1.usuarios WHERE correo_electronico=:correo"
        ),
        {"correo": correo},
    ).scalar_one()

    activacion = client.get(f"/usuarios/activar/{token}")
    assert activacion.status_code == 200, activacion.text

    filas = db_session.execute(
        text(
            """
            SELECT e.tipo_evento, n.id_notificacion_canal, n.mensaje,
                   n.estado_envio::text AS estado_envio
            FROM modulo1.notificaciones n
            JOIN modulo1.eventos e USING (id_evento)
            WHERE n.id_usuario=:usuario AND e.tipo_evento IN (1, 2)
            ORDER BY e.tipo_evento, n.id_notificacion_canal
            """
        ),
        {"usuario": id_usuario},
    ).all()

    assert [(f.tipo_evento, f.id_notificacion_canal) for f in filas] == [
        (1, 1),
        (1, 2),
        (2, 1),
        (2, 2),
    ]
    assert all(token not in fila.mensaje for fila in filas)
    assert all(fila.estado_envio == "enviado" for fila in filas)
    assert len(correos) == 2
    assert token in correos[0]["html_body"]
    assert token not in correos[1]["html_body"]
