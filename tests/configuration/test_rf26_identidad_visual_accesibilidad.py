"""RF-26 — la respuesta de identidad visual avisa del contraste y no rechaza por él.

El flujo alterno de RF-27 *Incompatibilidad de contraste con Identidad Visual (RF-26)*
pide **advertencia**, no error: "Se aplicará una variante aclarada/oscurecida
automáticamente para garantizar la legibilidad". Las restricciones de RF-26 enumeran
formato de imagen, tamaño, hexadecimal de 6 dígitos y longitud del nombre — el contraste
no está entre ellas. Guardar un color de bajo contraste tiene que seguir devolviendo
201/200 y persistir el color elegido por el administrador.

Se cubre además el almacenamiento del logotipo, que estaba roto de una forma que no daba
error: el archivo se escribía en `uploads/logos/<uuid>.ext` y se devolvía esa ruta
relativa, pero `main.py` no montaba nada estático, así que el `logo_path` no era
alcanzable por HTTP y ningún cliente podía pintar la marca.

Verifica con fakes (sin BD; modulo9 no existe en la BD `pruebas`).
"""
from __future__ import annotations

import os
from collections.abc import Generator
from typing import Optional

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.configuration.application.use_cases.personalizacion.guardar_identidad_visual_use_case import (
    GuardarIdentidadVisualUseCase,
)
from src.configuration.domain.entities.identidad_visual import IdentidadVisual
from src.configuration.infrastructure.dto.guardar_identidad_visual_dto import (
    GuardarIdentidadVisualDTO,
)
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared import almacen_logos
from src.shared.errors import ValidationError

ADMIN = UsuarioActual(id_usuario=1, id_token=1, id_rol=1, id_estado_cuenta=2)

PNG_MINIMO = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


class DbFake:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


class IdentidadRepoFake:
    def __init__(self, existente: Optional[IdentidadVisual] = None) -> None:
        self.existente = existente
        self.guardados: list[IdentidadVisual] = []

    def obtener_por_finca(self, id_finca: int) -> Optional[IdentidadVisual]:
        return self.existente

    def guardar(self, entidad: IdentidadVisual) -> IdentidadVisual:
        entidad.id_identidad_visual = 1
        self.guardados.append(entidad)
        return entidad

    def actualizar(self, entidad: IdentidadVisual) -> IdentidadVisual:  # pragma: no cover
        return entidad


class AuditoriaRepoFake:
    def __init__(self) -> None:
        self.registros: list[tuple[dict, dict]] = []

    def registrar(self, id_usuario: int, valor_anterior: dict, valor_nuevo: dict) -> None:
        self.registros.append((valor_anterior, valor_nuevo))


def _dto(primary: str = "#FFFFFF", secondary: str = "#FEFEFE") -> GuardarIdentidadVisualDTO:
    return GuardarIdentidadVisualDTO(
        id_finca=1,
        primary_color=primary,
        secondary_color=secondary,
        org_display_name="Acuicola El Remanso",
    )


def _caso(repo: IdentidadRepoFake, db: DbFake) -> GuardarIdentidadVisualUseCase:
    return GuardarIdentidadVisualUseCase(
        db=db, identidad_repo=repo, auditoria_repo=AuditoriaRepoFake()
    )


# ---- El contraste avisa, no bloquea ---- #

def test_un_color_de_bajo_contraste_se_guarda_igual() -> None:
    """Blanco puro es ilegible sobre el fondo claro y aun asi el RF no autoriza rechazarlo."""
    db, repo = DbFake(), IdentidadRepoFake()

    guardada = _caso(repo, db).execute(_dto("#FFFFFF"), None, None, ADMIN)

    assert db.commits == 1
    assert db.rollbacks == 0
    assert str(guardada.primary_color) == "#FFFFFF"


def test_la_respuesta_del_endpoint_lleva_el_bloque_de_accesibilidad() -> None:
    """El administrador tiene que ver el aviso en el momento de guardar, no despues."""
    from src.configuration.infrastructure.schema.identidad_visual_schema import (
        IdentidadVisualResponse,
    )

    db, repo = DbFake(), IdentidadRepoFake()
    guardada = _caso(repo, db).execute(_dto("#FFFFFF"), None, None, ADMIN)

    cuerpo = IdentidadVisualResponse.from_entity(guardada).model_dump()

    assert cuerpo["accesibilidad"]["primary_color"]["claro"]["cumple_aa"] is False
    assert cuerpo["accesibilidad"]["primary_color"]["claro"]["aviso"].startswith(
        "Aviso de accesibilidad:"
    )
    assert cuerpo["accesibilidad"]["primary_color"]["claro"]["color_ajustado"] != "#FFFFFF"


def test_el_color_ajustado_no_reemplaza_al_guardado() -> None:
    """La variante es de presentacion: la marca de la organizacion no se altera en BD."""
    db, repo = DbFake(), IdentidadRepoFake()

    guardada = _caso(repo, db).execute(_dto("#A8D5B5"), None, None, ADMIN)

    assert repo.guardados[0].primary_color.valor == "#A8D5B5"
    assert guardada._snapshot()["primary_color"] == "#A8D5B5"


# ---- El logotipo ---- #

def test_el_logo_se_guarda_bajo_la_ruta_publica_montada(tmp_path, monkeypatch) -> None:
    """La ruta persistida tiene que coincidir con lo que `main.py` sirve como estatico."""
    monkeypatch.chdir(tmp_path)
    db, repo = DbFake(), IdentidadRepoFake()

    guardada = _caso(repo, db).execute(_dto("#1A6B3C"), PNG_MINIMO, "image/png", ADMIN)

    assert guardada.logo_path.startswith(almacen_logos.RUTA_PUBLICA_LOGOS + "/")
    assert guardada.logo_path.endswith(".png")
    # Y el archivo existe donde el montaje lo va a buscar.
    relativa = guardada.logo_path[len(almacen_logos.RUTA_PUBLICA_BASE) + 1:]
    assert os.path.isfile(os.path.join(almacen_logos.DIRECTORIO_BASE, relativa))


@pytest.mark.parametrize("tipo", ["image/gif", "application/pdf", "image/webp", None])
def test_formato_no_admitido_se_rechaza_con_el_mensaje_del_flujo_alterno(tipo) -> None:
    with pytest.raises(ValidationError) as error:
        almacen_logos.guardar_logo(PNG_MINIMO, tipo)

    assert error.value.code == "FORMATO_IMAGEN_NO_PERMITIDO"
    assert error.value.status_code == 400
    assert error.value.field == "logo"
    assert "PNG, JPEG o SVG" in error.value.message


def test_archivo_de_mas_de_2mb_se_rechaza_citando_el_limite() -> None:
    with pytest.raises(ValidationError) as error:
        almacen_logos.guardar_logo(b"\x00" * (almacen_logos.TAMANO_MAX + 1), "image/png")

    assert error.value.code == "TAMANO_IMAGEN_EXCEDIDO"
    assert error.value.status_code == 400
    assert "2 MB" in error.value.message


def test_los_dos_flujos_de_escritura_comparten_el_mismo_almacen() -> None:
    """La deduplicacion es la garantia de que las dos rutas no diverjan de formato.

    Estaba copiado literal en crear y en actualizar, con mensajes distintos para la misma
    condicion. Si vuelve a duplicarse, un logo subido al actualizar podria quedar con una
    ruta que el montaje estatico no resuelve.
    """
    from src.configuration.application.use_cases.personalizacion import (
        actualizar_identidad_visual_use_case as actualizar,
        guardar_identidad_visual_use_case as crear,
    )

    assert crear.guardar_logo is almacen_logos.guardar_logo
    assert actualizar.guardar_logo is almacen_logos.guardar_logo
    assert not hasattr(crear.GuardarIdentidadVisualUseCase, "_guardar_logo")
    assert not hasattr(actualizar.ActualizarIdentidadVisualUseCase, "_guardar_logo")


# ---- El montaje estatico ---- #

def test_la_aplicacion_sirve_el_directorio_de_logotipos() -> None:
    """Sin este montaje el `logo_path` que devuelve la API no es alcanzable por HTTP."""
    import main

    montajes = {ruta.path for ruta in main.app.routes if hasattr(ruta, "app")}
    assert almacen_logos.RUTA_PUBLICA_BASE in montajes


def test_el_logotipo_subido_se_descarga_por_su_ruta(tmp_path, monkeypatch) -> None:
    """Prueba de extremo a extremo del contrato: lo que se guarda, se sirve."""
    from fastapi.staticfiles import StaticFiles

    monkeypatch.chdir(tmp_path)
    ruta = almacen_logos.guardar_logo(PNG_MINIMO, "image/png")

    app = FastAPI()
    app.mount(
        almacen_logos.RUTA_PUBLICA_BASE,
        StaticFiles(directory=almacen_logos.DIRECTORIO_BASE, check_dir=False),
        name="uploads",
    )
    with TestClient(app) as cliente:
        respuesta = cliente.get(ruta)

    assert respuesta.status_code == 200
    assert respuesta.content == PNG_MINIMO
