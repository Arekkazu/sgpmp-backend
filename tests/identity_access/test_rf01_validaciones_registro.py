"""Pruebas unitarias de validaciones y correo asíncrono de RF-01."""
from __future__ import annotations

import asyncio
from datetime import date

import pytest
from fastapi import BackgroundTasks
from pydantic import ValidationError as PydanticValidationError

from src.identity_access.domain.entities.usuario import Usuario
from src.identity_access.domain.value_objects.identificacion import (
    identificacion_valida,
)
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
        "captcha_token": "captcha-prueba-valido",
    }
    datos.update(cambios)
    return datos


def test_registro_exige_confirmacion_de_contrasena() -> None:
    datos = _registro()
    datos.pop("confirmar_contrasena")

    with pytest.raises(PydanticValidationError) as error:
        UsuarioCreateDTO(**datos)

    assert error.value.errors()[0]["loc"] == ("confirmar_contrasena",)


def test_registro_exige_token_captcha() -> None:
    datos = _registro()
    datos.pop("captcha_token")

    with pytest.raises(PydanticValidationError) as error:
        UsuarioCreateDTO(**datos)

    assert error.value.errors()[0]["loc"] == ("captcha_token",)


def test_registro_acepta_telefono_y_direccion_ausentes() -> None:
    """Ambas columnas son nullable y la entidad los declara opcionales."""
    datos = _registro()
    datos.pop("telefono")
    datos.pop("direccion")

    dto = UsuarioCreateDTO(**datos)

    assert dto.telefono is None
    assert dto.direccion is None


def test_registro_rechaza_contrasenas_que_no_coinciden() -> None:
    with pytest.raises(PydanticValidationError) as error:
        UsuarioCreateDTO(**_registro(confirmar_contrasena="OtraClave1!"))

    assert error.value.errors()[0]["loc"] == ("confirmar_contrasena",)
    assert "Las contraseñas ingresadas no coinciden" in str(error.value)


# RF-01 admite CC, CE y Pasaporte. La exigencia de "solo dígitos" solo puede
# aplicarse a los documentos colombianos: un pasaporte es alfanumérico.
@pytest.mark.parametrize("tipo", ["CC", "CE"])
@pytest.mark.parametrize("numero", ["123A", "12-34", "12 34", "１２３４", ""])
def test_registro_rechaza_identificacion_no_numerica_en_cc_y_ce(
    tipo: str,
    numero: str,
) -> None:
    with pytest.raises(PydanticValidationError):
        UsuarioCreateDTO(
            **_registro(tipo_identificacion=tipo, numero_identificacion=numero)
        )


def test_registro_acepta_pasaporte_alfanumerico() -> None:
    dto = UsuarioCreateDTO(
        **_registro(tipo_identificacion="Pasaporte", numero_identificacion="AB123456")
    )

    assert dto.numero_identificacion == "AB123456"


@pytest.mark.parametrize("numero", ["AB-123", "AB 123", "１２３４", ""])
def test_registro_rechaza_pasaporte_con_signos_o_espacios(numero: str) -> None:
    with pytest.raises(PydanticValidationError):
        UsuarioCreateDTO(
            **_registro(
                tipo_identificacion="Pasaporte",
                numero_identificacion=numero,
            )
        )


def test_registro_rechaza_tipo_de_identificacion_desconocido() -> None:
    with pytest.raises(PydanticValidationError) as error:
        UsuarioCreateDTO(**_registro(tipo_identificacion="NIT"))

    assert error.value.errors()[0]["loc"] == ("tipo_identificacion",)


def test_el_error_de_identificacion_apunta_al_campo() -> None:
    """El contrato de error del proyecto expone `field`; el frontend lo usa
    para marcar el input, así que la validación debe ser de campo."""
    with pytest.raises(PydanticValidationError) as error:
        UsuarioCreateDTO(**_registro(numero_identificacion="123ABC"))

    assert error.value.errors()[0]["loc"] == ("numero_identificacion",)


def test_registro_conserva_ceros_iniciales_de_identificacion() -> None:
    dto = UsuarioCreateDTO(**_registro(numero_identificacion="00123"))

    assert dto.numero_identificacion == "00123"


@pytest.mark.parametrize(
    ("tipo", "numero"),
    [("CC", "123A"), ("CE", "12-34"), ("Pasaporte", "AB-123")],
)
def test_dominio_rechaza_identificacion_con_formato_invalido(
    tipo: str,
    numero: str,
) -> None:
    with pytest.raises(ValidationError) as error:
        Usuario.registrar_nuevo(
            correo=object(),
            contrasena=object(),
            nombre="Ana",
            apellidos="Pérez",
            fecha_nacimiento=date(1990, 5, 15),
            genero="F",
            tipo_identificacion=tipo,
            numero_identificacion=numero,
        )

    assert error.value.code == "NUMERO_IDENTIFICACION_INVALIDO"


def test_dominio_acepta_pasaporte_alfanumerico() -> None:
    usuario = Usuario.registrar_nuevo(
        correo=object(),
        contrasena=object(),
        nombre="Ana",
        apellidos="Pérez",
        fecha_nacimiento=date(1990, 5, 15),
        genero="F",
        tipo_identificacion="Pasaporte",
        numero_identificacion="AB123456",
    )

    assert usuario.numero_identificacion == "AB123456"


def test_agrofusion_reutiliza_la_misma_regla_por_tipo() -> None:
    def crear(tipo: str, numero: str) -> AgroFusionCreateUserDTO:
        return AgroFusionCreateUserDTO(
            client_id="cliente",
            client_secret="secreto",
            correo_electronico="ana@example.com",
            nombre="Ana",
            apellidos="Pérez",
            tipo_identificacion=tipo,
            numero_identificacion=numero,
            fecha_nacimiento="1990-05-15",
            genero="F",
        )

    with pytest.raises(PydanticValidationError):
        crear("CC", "123-A")

    assert crear("Pasaporte", "AB123456").numero_identificacion == "AB123456"


def test_perfil_delega_el_formato_al_use_case() -> None:
    """El DTO de perfil no valida el formato: en una edición parcial puede
    llegar el número sin el tipo. La regla se aplica sobre el par ya fusionado
    en ``EditarPerfilUseCase``."""
    dto = EditarPerfilDTO(
        nombre="Ana",
        apellidos="Pérez",
        numero_identificacion="123-A",
        version=1,
    )

    assert dto.numero_identificacion == "123-A"
    assert not identificacion_valida(
        dto.tipo_identificacion,
        dto.numero_identificacion,
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
