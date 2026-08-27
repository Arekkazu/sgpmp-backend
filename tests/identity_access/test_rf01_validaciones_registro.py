"""Pruebas unitarias de validaciones y correo asíncrono de RF-01."""
from __future__ import annotations

import asyncio
from datetime import date

import pytest
from fastapi import BackgroundTasks
from pydantic import ValidationError as PydanticValidationError

from src.identity_access.domain.entities.usuario import Usuario
from src.identity_access.infrastructure.adapters import (
    correo_activacion_background_adapter as correo_adapter,
)
from src.identity_access.infrastructure.adapters.correo_activacion_background_adapter import (
    CorreoActivacionBackgroundAdapter,
)
from src.identity_access.infrastructure.dto.agrofusion_dto import (
    AgroFusionCreateUserDTO,
)
from src.identity_access.infrastructure.dto.perfil_dto import EditarPerfilDTO
from src.identity_access.infrastructure.dto.usuario_dto import UsuarioCreateDTO
from src.shared import email as email_module
from src.shared.errors import ServiceUnavailableError, ValidationError


def _registro(**cambios) -> dict:
    datos = {
        "correo_electronico": "ana@example.com",
        "telefono": "3001234567",
        "tipo_identificacion": "CC",
        "numero_identificacion": "0012345678",
        "nombre": "Ana",
        "apellidos": "Pérez",
        "fecha_nacimiento": "1990-05-15",
        "genero": "F",
        "contrasena": "Contrasena1!",
        "confirmar_contrasena": "Contrasena1!",
        "direccion": "Calle 1",
    }
    datos.update(cambios)
    return datos


def test_registro_exige_confirmacion_de_contrasena() -> None:
    datos = _registro()
    datos.pop("confirmar_contrasena")

    with pytest.raises(PydanticValidationError) as error:
        UsuarioCreateDTO(**datos)

    assert error.value.errors()[0]["loc"] == ("confirmar_contrasena",)


def test_registro_rechaza_contrasenas_que_no_coinciden() -> None:
    with pytest.raises(PydanticValidationError) as error:
        UsuarioCreateDTO(**_registro(confirmar_contrasena="OtraClave1!"))

    assert error.value.errors()[0]["loc"] == ("confirmar_contrasena",)
    assert "Las contraseñas ingresadas no coinciden" in str(error.value)


@pytest.mark.parametrize("numero", ["123A", "12-34", "12 34", "１２３４", ""])
def test_registro_rechaza_identificacion_no_ascii_numerica(numero: str) -> None:
    with pytest.raises(PydanticValidationError):
        UsuarioCreateDTO(**_registro(numero_identificacion=numero))


def test_registro_conserva_ceros_iniciales_de_identificacion() -> None:
    dto = UsuarioCreateDTO(**_registro(numero_identificacion="00123"))

    assert dto.numero_identificacion == "00123"


def test_dominio_rechaza_identificacion_no_numerica() -> None:
    with pytest.raises(ValidationError) as error:
        Usuario.registrar_nuevo(
            correo=object(),
            contrasena=object(),
            nombre="Ana",
            apellidos="Pérez",
            fecha_nacimiento=date(1990, 5, 15),
            genero="F",
            tipo_identificacion="CC",
            numero_identificacion="123A",
        )

    assert error.value.code == "NUMERO_IDENTIFICACION_INVALIDO"


def test_otros_flujos_de_usuario_reutilizan_validacion_numerica() -> None:
    with pytest.raises(PydanticValidationError):
        EditarPerfilDTO(
            nombre="Ana",
            apellidos="Pérez",
            numero_identificacion="123-A",
            version=1,
        )

    with pytest.raises(PydanticValidationError):
        AgroFusionCreateUserDTO(
            client_id="cliente",
            client_secret="secreto",
            correo_electronico="ana@example.com",
            nombre="Ana",
            apellidos="Pérez",
            tipo_identificacion="CC",
            numero_identificacion="123-A",
            fecha_nacimiento="1990-05-15",
            genero="F",
        )


def test_adaptador_programa_correo_sin_ejecutarlo_en_el_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tareas = BackgroundTasks()
    llamadas = []
    monkeypatch.setattr(
        correo_adapter,
        "procesar_correo_activacion_background",
        lambda **datos: llamadas.append(datos),
    )

    CorreoActivacionBackgroundAdapter(tareas).programar_envio(
        correo="ana@example.com",
        nombre="Ana",
        token="token-crudo",
        id_usuario=7,
    )

    assert llamadas == []
    assert len(tareas.tasks) == 1

    asyncio.run(tareas())

    assert llamadas == [
        {
            "correo": "ana@example.com",
            "nombre": "Ana",
            "token": "token-crudo",
            "id_usuario": 7,
        }
    ]


def test_smtp_conserva_tres_intentos_y_dos_pausas_de_cinco_segundos(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    intentos = []
    pausas = []

    def smtp_fallido(*_args, **_kwargs):
        intentos.append(True)
        raise OSError("SMTP temporalmente no disponible")

    monkeypatch.setattr(email_module.smtplib, "SMTP", smtp_fallido)
    monkeypatch.setattr(email_module.time, "sleep", pausas.append)

    with pytest.raises(ServiceUnavailableError):
        email_module.send_email(
            to="ana@example.com",
            subject="Activación",
            html_body="<p>Activa tu cuenta</p>",
        )

    assert len(intentos) == 3
    assert pausas == [5, 5]
