"""Integración HTTP/BD del manejo de fallo SMTP de RF-08."""
from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.identity_access.domain.value_objects.token_un_solo_uso import calcular_hash_token
from src.shared.errors import ServiceUnavailableError

pytestmark = pytest.mark.integration


MENSAJE_GENERICO = (
    "Si el correo está registrado, recibirás instrucciones para recuperar "
    "tu contraseña en unos minutos."
)


def test_fallo_smtp_conserva_token_y_crea_alerta_interna_para_destinatarios_rbac(
    client,
    db_session: Session,
    crear_usuario_db,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.identity_access.application.use_cases.contrasena import (
        solicitar_recuperacion_use_case,
    )

    rol_destinatario = db_session.execute(
        text(
            """
            SELECT p.id_rol
            FROM modulo1.permisos p
            WHERE p.id_recurso = 6
              AND p.id_accion = 2
              AND p.es_activo IS TRUE
            ORDER BY p.id_rol
            LIMIT 1
            """
        )
    ).scalar_one()
    crear_usuario_db(id_rol=rol_destinatario, estado=2)
    solicitante = crear_usuario_db(id_rol=2, estado=2)
    token = "token-rf08-smtp-integracion"

    monkeypatch.setattr(
        solicitar_recuperacion_use_case.secrets,
        "token_urlsafe",
        lambda _bytes: token,
    )

    def smtp_caido(**_kwargs):
        raise ServiceUnavailableError(
            code="EMAIL_NO_DISPONIBLE",
            message="El servicio SMTP no está disponible.",
        )

    monkeypatch.setattr(solicitar_recuperacion_use_case, "send_email", smtp_caido)

    destinatarios_esperados = set(
        db_session.execute(
            text(
                """
                SELECT DISTINCT u.id_usuario
                FROM modulo1.usuarios u
                JOIN modulo1.permisos p ON p.id_rol = u.id_rol
                JOIN modulo1.cuentas_usuarios c ON c.id_usuario = u.id_usuario
                JOIN modulo1.estados_cuentas ec
                  ON ec.id_estado_cuenta = c.id_estado_cuenta
                WHERE p.id_recurso = 6
                  AND p.id_accion = 2
                  AND p.es_activo IS TRUE
                  AND lower(ec.nombre) = 'activo'
                """
            )
        ).scalars()
    )
    assert destinatarios_esperados

    respuesta = client.post(
        "/contrasena/recuperar",
        json={"correo_electronico": solicitante["correo"]},
    )

    assert respuesta.status_code == 202, respuesta.text
    assert respuesta.json() == {"message": MENSAJE_GENERICO}

    token_guardado = db_session.execute(
        text(
            """
            SELECT token_activacion_actual
            FROM modulo1.cuentas_usuarios
            WHERE id_usuario = :usuario
            """
        ),
        {"usuario": solicitante["id_usuario"]},
    ).scalar_one()
    assert token_guardado == calcular_hash_token(token)

    eventos = db_session.execute(
        text(
            """
            SELECT id_evento, resultado::text AS resultado, detalle
            FROM modulo1.eventos
            WHERE id_usuario = :usuario AND tipo_evento = 7
            ORDER BY id_evento
            """
        ),
        {"usuario": solicitante["id_usuario"]},
    ).mappings().all()
    assert len(eventos) == 1
    assert eventos[0]["resultado"] == "exitoso"
    assert eventos[0]["detalle"]["motivo"] == "token_generado"

    alertas = db_session.execute(
        text(
            """
            SELECT id_usuario, id_notificacion_canal, mensaje,
                   estado_envio::text AS estado
            FROM modulo1.notificaciones
            WHERE id_evento = :evento
              AND id_notificacion_canal = 2
            ORDER BY id_usuario
            """
        ),
        {"evento": eventos[0]["id_evento"]},
    ).mappings().all()

    assert {alerta["id_usuario"] for alerta in alertas} == destinatarios_esperados
    assert all(alerta["estado"] == "enviado" for alerta in alertas)
    assert all("Fallo crítico del servicio SMTP" in alerta["mensaje"] for alerta in alertas)
    assert all("EMAIL_NO_DISPONIBLE" in alerta["mensaje"] for alerta in alertas)
    assert all(solicitante["correo"] not in alerta["mensaje"] for alerta in alertas)
    assert all(token not in alerta["mensaje"] for alerta in alertas)
