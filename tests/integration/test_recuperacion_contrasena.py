"""Flujo HTTP/BD de recuperación y restablecimiento de contraseña."""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

import bcrypt
import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.identity_access.domain.value_objects.token_un_solo_uso import calcular_hash_token

pytestmark = pytest.mark.integration


def test_recuperacion_guarda_hash_y_restablecimiento_consume_token(
    client,
    db_session: Session,
    crear_usuario_db,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.identity_access.application.use_cases.contrasena import (
        solicitar_recuperacion_use_case,
    )
    from src.shared import notificacion_service

    usuario = crear_usuario_db(id_rol=2, estado=2)
    token_crudo = "token-integracion-recuperacion"
    correos: list[dict] = []
    monkeypatch.setattr(
        solicitar_recuperacion_use_case.secrets,
        "token_urlsafe",
        lambda _bytes: token_crudo,
    )
    monkeypatch.setattr(
        solicitar_recuperacion_use_case,
        "send_email",
        lambda **kwargs: correos.append(kwargs),
    )
    monkeypatch.setattr(notificacion_service, "send_email", lambda **_kwargs: None)
    monkeypatch.setattr(notificacion_service, "send_push", lambda **_kwargs: True)

    respuesta = client.post(
        "/contrasena/recuperar",
        json={"correo_electronico": usuario["correo"]},
    )
    assert respuesta.status_code == 202, respuesta.text

    hash_guardado = db_session.execute(
        text(
            """
            SELECT token_activacion_actual
            FROM modulo1.cuentas_usuarios
            WHERE id_usuario = :usuario
            """
        ),
        {"usuario": usuario["id_usuario"]},
    ).scalar_one()
    assert hash_guardado == calcular_hash_token(token_crudo)
    assert hash_guardado != token_crudo
    assert correos and token_crudo in correos[0]["html_body"]

    nueva = "NuevaSegura2!"
    restablecer = client.post(
        "/contrasena/restablecer",
        json={
            "token": token_crudo,
            "nueva_contrasena": nueva,
            "confirmar_contrasena": nueva,
        },
    )
    assert restablecer.status_code == 200, restablecer.text

    resultado = db_session.execute(
        text(
            """
            SELECT u.contrasena_cifrada, c.token_activacion_actual, c.es_token_usado AS token_usado
            FROM modulo1.usuarios u
            JOIN modulo1.cuentas_usuarios c USING (id_usuario)
            WHERE u.id_usuario = :usuario
            """
        ),
        {"usuario": usuario["id_usuario"]},
    ).mappings().one()
    # El hash se conserva (no se limpia) tras un uso exitoso: es lo que permite
    # distinguir "token ya utilizado" (409) de "token nunca existió" (401) en
    # un reintento — ver INC-M01-15-054 (#100).
    assert resultado["token_activacion_actual"] == calcular_hash_token(token_crudo)
    assert resultado["token_usado"] is True
    assert bcrypt.checkpw(
        nueva.encode("utf-8"),
        resultado["contrasena_cifrada"].encode("utf-8"),
    )
    evento = db_session.execute(
        text(
            """
            SELECT categoria
            FROM modulo1.eventos
            WHERE id_usuario = :usuario AND tipo_evento = 8
            ORDER BY id_evento DESC LIMIT 1
            """
        ),
        {"usuario": usuario["id_usuario"]},
    ).scalar_one()
    assert evento == "AUTENTICACION"


def test_recuperacion_de_cuenta_pendiente_rota_token_y_envia_activacion(
    client,
    db_session: Session,
    crear_usuario_db,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.identity_access.application.use_cases.contrasena import (
        solicitar_recuperacion_use_case,
    )

    usuario = crear_usuario_db(id_rol=2, estado=1)
    token_anterior = "token-activacion-anterior"
    token_nuevo = "token-activacion-renovado"
    db_session.execute(
        text(
            """
            UPDATE modulo1.cuentas_usuarios
            SET token_activacion_actual = :token_hash,
                fecha_cambio_estado = now()
            WHERE id_usuario = :usuario
            """
        ),
        {
            "token_hash": calcular_hash_token(token_anterior),
            "usuario": usuario["id_usuario"],
        },
    )
    correos: list[dict] = []
    monkeypatch.setattr(
        solicitar_recuperacion_use_case.secrets,
        "token_urlsafe",
        lambda _bytes: token_nuevo,
    )
    monkeypatch.setattr(
        solicitar_recuperacion_use_case,
        "send_email",
        lambda **kwargs: correos.append(kwargs),
    )

    respuesta = client.post(
        "/contrasena/recuperar",
        json={"correo_electronico": usuario["correo"]},
    )

    assert respuesta.status_code == 202, respuesta.text
    token_guardado = db_session.execute(
        text(
            """
            SELECT token_activacion_actual
            FROM modulo1.cuentas_usuarios
            WHERE id_usuario = :usuario
            """
        ),
        {"usuario": usuario["id_usuario"]},
    ).scalar_one()
    assert token_guardado == calcular_hash_token(token_nuevo)
    assert token_guardado not in {token_nuevo, calcular_hash_token(token_anterior)}
    assert correos and correos[0]["subject"] == "Activa tu cuenta en SGPMP"
    assert token_nuevo in correos[0]["html_body"]
    assert token_anterior not in correos[0]["html_body"]


def test_reenvio_de_activacion_guarda_hash_y_envia_token_crudo(
    client,
    db_session: Session,
    crear_usuario_db,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.identity_access.application.use_cases.registro import reenviar_token_use_case

    usuario = crear_usuario_db(id_rol=2, estado=1)
    token_crudo = "token-reenvio-integracion"
    correos: list[dict] = []
    monkeypatch.setattr(
        reenviar_token_use_case.secrets,
        "token_urlsafe",
        lambda _bytes: token_crudo,
    )
    monkeypatch.setattr(
        reenviar_token_use_case,
        "send_email",
        lambda **kwargs: correos.append(kwargs),
    )

    respuesta = client.post(
        "/usuarios/activar/reenviar",
        json={"correo_electronico": usuario["correo"]},
    )

    assert respuesta.status_code == 200, respuesta.text
    token_guardado = db_session.execute(
        text(
            """
            SELECT token_activacion_actual
            FROM modulo1.cuentas_usuarios
            WHERE id_usuario = :usuario
            """
        ),
        {"usuario": usuario["id_usuario"]},
    ).scalar_one()
    assert token_guardado == calcular_hash_token(token_crudo)
    assert token_guardado != token_crudo
    assert correos and token_crudo in correos[0]["html_body"]


def test_restablecer_con_token_ya_usado_responde_409(
    client,
    db_session: Session,
    crear_usuario_db,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """INC-M01-15-054 (#100): reutilizar un token que YA se consumió con éxito
    debe responder 409 (no 401, que es para tokens que nunca existieron)."""
    from src.identity_access.application.use_cases.contrasena import (
        solicitar_recuperacion_use_case,
    )
    from src.shared import notificacion_service

    usuario = crear_usuario_db(id_rol=2, estado=2)
    token_crudo = "token-reutilizado-tc054"
    monkeypatch.setattr(
        solicitar_recuperacion_use_case.secrets, "token_urlsafe", lambda _bytes: token_crudo
    )
    monkeypatch.setattr(solicitar_recuperacion_use_case, "send_email", lambda **_k: None)
    monkeypatch.setattr(notificacion_service, "send_email", lambda **_k: None)
    monkeypatch.setattr(notificacion_service, "send_push", lambda **_k: True)

    solicitar = client.post(
        "/contrasena/recuperar", json={"correo_electronico": usuario["correo"]}
    )
    assert solicitar.status_code == 202, solicitar.text

    cuerpo_restablecer = {
        "token": token_crudo,
        "nueva_contrasena": "PrimerUso1!",
        "confirmar_contrasena": "PrimerUso1!",
    }
    primer_uso = client.post("/contrasena/restablecer", json=cuerpo_restablecer)
    assert primer_uso.status_code == 200, primer_uso.text

    segundo_uso = client.post(
        "/contrasena/restablecer",
        json={**cuerpo_restablecer, "nueva_contrasena": "SegundoUso1!", "confirmar_contrasena": "SegundoUso1!"},
    )

    assert segundo_uso.status_code == 409, segundo_uso.text
    assert segundo_uso.json()["error_code"] == "TOKEN_YA_UTILIZADO"


def test_restablecer_con_tokens_invalidos_repetidos_bloquea_por_ip(client) -> None:
    """INC-M01-17-058 (#102): 5 intentos consecutivos con token inválido desde
    la misma IP deben bloquear con 423 (antes: intentos ilimitados)."""
    cuerpo = {
        "nueva_contrasena": "Valida#123",
        "confirmar_contrasena": "Valida#123",
    }
    for numero in range(1, 5):
        respuesta = client.post(
            "/contrasena/restablecer",
            json={**cuerpo, "token": f"token-invalido-tc058-{numero}"},
        )
        assert respuesta.status_code == 401, f"intento {numero}: {respuesta.text}"

    quinto = client.post(
        "/contrasena/restablecer",
        json={**cuerpo, "token": "token-invalido-tc058-5"},
    )
    assert quinto.status_code == 423, quinto.text
    assert quinto.json()["error_code"] == "RESTABLECIMIENTO_BLOQUEADO"


def _insertar_intento_anonimo(db_session, tipo: str, ip: str, hace: timedelta) -> None:
    """Inserta un intento con fecha pasada en la tabla de rate limiting por IP,
    para simular solicitudes previas dentro de la ventana sin depender de
    tiempo real de ejecución del test."""
    db_session.execute(
        text(
            "INSERT INTO modulo1.intentos_anonimos_ip (tipo, ip, fecha_intento) VALUES (:tipo, :ip, now() - :hace)"
        ),
        {"tipo": tipo, "ip": ip, "hace": hace},
    )
    db_session.commit()


def test_recuperacion_excede_limite_responde_429_con_hora_real_de_reintento(
    client,
    db_session: Session,
    crear_usuario_db,
) -> None:
    """INC-M01-07-43 / INC-M01-19-112 / INC-M01-20-112 (RF-08): el límite de 3
    solicitudes/hora por IP debe responder 429 (no 422) y anunciar la hora en
    que la solicitud más antigua de la ventana cumple una hora (no la hora
    actual de la respuesta)."""
    usuario = crear_usuario_db()
    ip = "sgpmp-integration-tests"  # host simulado por el fixture `client` (conftest)
    mas_antigua = timedelta(minutes=50)
    for hace in (mas_antigua, timedelta(minutes=40), timedelta(minutes=30)):
        _insertar_intento_anonimo(db_session, "SOLICITUD_RECUPERACION", ip, hace)

    respuesta = client.post(
        "/contrasena/recuperar",
        json={"correo_electronico": usuario["correo"]},
    )

    assert respuesta.status_code == 429, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["error_code"] == "LIMITE_SOLICITUDES_EXCEDIDO"

    esperado = datetime.now(timezone.utc) - mas_antigua + timedelta(hours=1)
    hora_reportada = re.search(r"(\d{2}:\d{2}):\d{2}", cuerpo["message"]).group(1)
    # Tolerancia de 1 minuto por el tiempo real transcurrido en el test.
    assert hora_reportada in {
        (esperado + timedelta(minutes=d)).strftime("%H:%M") for d in (-1, 0, 1)
    }
    # La hora de reintento NO puede ser "ahora": ese era exactamente el bug.
    ahora = datetime.now(timezone.utc).strftime("%H:%M")
    assert hora_reportada != ahora


def test_recuperacion_aplica_limite_a_correo_inexistente(client) -> None:
    """INC-M01-09-043 (#86): el límite de 3/hora por IP debe aplicarse también
    cuando el correo no está registrado — antes, ese caso retornaba el mensaje
    genérico sin registrar ningún evento, así que el contador nunca subía y
    permitía solicitudes ilimitadas contra correos inexistentes."""
    correo_inexistente = "no-existe-tc043@example.com"
    for numero in range(1, 4):
        respuesta = client.post(
            "/contrasena/recuperar",
            json={"correo_electronico": correo_inexistente},
        )
        assert respuesta.status_code == 202, f"solicitud {numero}: {respuesta.text}"

    cuarta = client.post(
        "/contrasena/recuperar",
        json={"correo_electronico": correo_inexistente},
    )

    assert cuarta.status_code == 429, cuarta.text
    assert cuarta.json()["error_code"] == "LIMITE_SOLICITUDES_EXCEDIDO"
