"""Validación HTTP/BD de la expiración del límite de recuperación RF-08."""
from datetime import datetime, timedelta, timezone

import pytest

from src.identity_access.application.use_cases.contrasena import (
    solicitar_recuperacion_use_case as modulo,
)


pytestmark = pytest.mark.integration


class FechaHoraFija(datetime):
    ahora = datetime(2026, 9, 5, 15, 0, 0, tzinfo=timezone.utc)

    @classmethod
    def now(cls, tz=None):
        return cls.ahora if tz is not None else cls.ahora.replace(tzinfo=None)


def test_endpoint_informa_expiracion_de_la_solicitud_mas_antigua(
    client,
    crear_usuario_db,
    crear_evento_db,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    usuario = crear_usuario_db(id_rol=2, estado=2)
    ip = "sgpmp-integration-tests"
    ahora = FechaHoraFija.ahora

    # Estos tres eventos consumen el cupo vigente; el primero expira a las 15:12:34.
    for antiguedad in (
        timedelta(minutes=47, seconds=26),
        timedelta(minutes=30),
        timedelta(minutes=10),
    ):
        crear_evento_db(
            id_usuario=usuario["id_usuario"],
            tipo_evento=7,
            categoria="AUTENTICACION",
            detalle={"ip": ip, "motivo": "token_generado"},
            fecha=ahora - antiguedad,
        )

    # No deben influir ni otra IP ni un evento fuera de la ventana de una hora.
    crear_evento_db(
        id_usuario=usuario["id_usuario"],
        tipo_evento=7,
        categoria="AUTENTICACION",
        detalle={"ip": "198.51.100.7"},
        fecha=ahora - timedelta(minutes=55),
    )
    crear_evento_db(
        id_usuario=usuario["id_usuario"],
        tipo_evento=7,
        categoria="AUTENTICACION",
        detalle={"ip": ip},
        fecha=ahora - timedelta(hours=1, seconds=1),
    )

    monkeypatch.setattr(modulo, "datetime", FechaHoraFija)
    respuesta = client.post(
        "/contrasena/recuperar",
        json={"correo_electronico": usuario["correo"]},
    )

    assert respuesta.status_code == 422, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["error_code"] == "LIMITE_SOLICITUDES_EXCEDIDO"
    assert "15:12:34" in cuerpo["message"]
    assert "15:00:00" not in cuerpo["message"]
