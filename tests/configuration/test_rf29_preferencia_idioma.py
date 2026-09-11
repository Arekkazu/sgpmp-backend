"""RF-29 — preferencia de idioma: lista blanca, flujos alternos y resolución jerárquica.

El estado de módulo 9 daba por ausente la validación de ``locale_code`` contra
lista blanca. Sí existía, en la entidad de dominio, y ya devolvía 400 — lo que no
cumplía el RF era el texto literal del mensaje, y que faltaban tres de los cuatro
flujos alternos: el 500 tipado de fallo de persistencia, el 409 de perfil
modificado y el 403 con el mensaje propio del idioma global (este último se
verifica en `tests/integration/test_rf29_idioma_rbac.py`, porque vive en la
compuerta RBAC del router).

El desajuste real que rompía el requerimiento estaba en el otro extremo: el
frontend enviaba ``'es'`` / ``'en'`` y el dominio solo acepta ``'es-CO'`` /
``'en-US'``, así que todo guardado respondía 400. El caso 2 fija ese contrato.

Verifica con fakes (sin BD; modulo9 no existe en la BD `pruebas`).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import pytest

from src.configuration.application.use_cases.personalizacion.guardar_idioma_global_use_case import (
    GuardarIdiomaGlobalUseCase,
)
from src.configuration.application.use_cases.personalizacion.guardar_idioma_personal_use_case import (
    GuardarIdiomaPersonalUseCase,
)
from src.configuration.application.use_cases.personalizacion.obtener_idioma_resuelto_use_case import (
    ObtenerIdiomaResueltoUseCase,
)
from src.configuration.domain.entities.preferencia_idioma import (
    LOCALE_DEFAULT,
    LOCALES_PERMITIDOS,
    PreferenciaIdioma,
)
from src.configuration.infrastructure.dto.guardar_idioma_dto import GuardarIdiomaDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import (
    ConflictError,
    InfrastructureError,
    NotFoundError,
    ValidationError,
)

PRODUCTOR = UsuarioActual(id_usuario=7, id_token=1, id_rol=2, id_estado_cuenta=2)
ADMIN = UsuarioActual(id_usuario=1, id_token=1, id_rol=1, id_estado_cuenta=2)

VERSION_PERFIL = 4


class DbFake:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


class IdiomaRepoFake:
    """Fake del puerto. ``falla_al_escribir`` simula el fallo de infraestructura."""

    def __init__(
        self,
        personal: Optional[PreferenciaIdioma] = None,
        global_: Optional[PreferenciaIdioma] = None,
        version: Optional[int] = VERSION_PERFIL,
        falla_al_escribir: Optional[BaseException] = None,
    ) -> None:
        self.personal = personal
        self.global_ = global_
        self.version = version
        self.falla_al_escribir = falla_al_escribir
        self.guardados: list[PreferenciaIdioma] = []
        self.actualizados: list[PreferenciaIdioma] = []

    def obtener_por_usuario(self, id_usuario: int) -> Optional[PreferenciaIdioma]:
        return self.personal

    def obtener_global(self) -> Optional[PreferenciaIdioma]:
        return self.global_

    def version_perfil(self, id_usuario: int) -> Optional[int]:
        return self.version

    def guardar(self, entidad: PreferenciaIdioma) -> PreferenciaIdioma:
        if self.falla_al_escribir is not None:
            raise self.falla_al_escribir
        self.guardados.append(entidad)
        return entidad

    def actualizar(self, entidad: PreferenciaIdioma) -> PreferenciaIdioma:
        if self.falla_al_escribir is not None:
            raise self.falla_al_escribir
        self.actualizados.append(entidad)
        return entidad


def _preferencia(locale: str = "es-CO", *, global_: bool = False) -> PreferenciaIdioma:
    return PreferenciaIdioma(
        id_preferencia_idioma=99 if global_ else 42,
        id_usuario=1 if global_ else 7,
        locale_code=locale,
        es_por_defecto=global_,
        fecha_actualizacion=datetime(2026, 9, 1, tzinfo=timezone.utc),
    )


def _dto(locale: str, version_perfil: Optional[int] = None) -> GuardarIdiomaDTO:
    return GuardarIdiomaDTO(locale_code=locale, version_perfil=version_perfil)


# --------------------------------------------------------------------------- #
# FA "Código de idioma no soportado" — 400                                     #
# --------------------------------------------------------------------------- #

def test_locale_no_soportado_es_400_con_el_mensaje_del_rf() -> None:
    db = DbFake()
    repo = IdiomaRepoFake()

    with pytest.raises(ValidationError) as error:
        GuardarIdiomaPersonalUseCase(db=db, idioma_repo=repo).execute(_dto("fr-FR"), PRODUCTOR)

    assert error.value.code == "IDIOMA_NO_DISPONIBLE"
    assert error.value.status_code == 400
    assert error.value.field == "locale_code"
    assert "Idioma no disponible" in error.value.message
    assert "'fr-FR' no está soportado actualmente" in error.value.message
    assert "Español (es-CO) e Inglés (en-US)" in error.value.message


def test_locale_de_dos_letras_es_400() -> None:
    """El valor que el frontend enviaba: 'es'/'en' en vez de 'es-CO'/'en-US'."""
    db = DbFake()

    for locale in ("es", "en"):
        with pytest.raises(ValidationError) as error:
            GuardarIdiomaPersonalUseCase(db=db, idioma_repo=IdiomaRepoFake()).execute(
                _dto(locale), PRODUCTOR
            )
        assert error.value.code == "IDIOMA_NO_DISPONIBLE"
        assert error.value.status_code == 400


@pytest.mark.parametrize("locale", sorted(LOCALES_PERMITIDOS))
def test_es_co_y_en_us_son_los_unicos_aceptados(locale: str) -> None:
    db = DbFake()
    repo = IdiomaRepoFake()

    resultado = GuardarIdiomaPersonalUseCase(db=db, idioma_repo=repo).execute(
        _dto(locale), PRODUCTOR
    )

    assert resultado.locale_code == locale
    assert resultado.es_por_defecto is False
    assert db.commits == 1
    assert len(repo.guardados) == 1


def test_locale_invalido_no_persiste() -> None:
    db = DbFake()
    repo = IdiomaRepoFake(personal=_preferencia("es-CO"))

    with pytest.raises(ValidationError):
        GuardarIdiomaPersonalUseCase(db=db, idioma_repo=repo).execute(_dto("it-IT"), PRODUCTOR)

    assert db.commits == 0
    assert repo.guardados == []
    assert repo.actualizados == []
    # La entidad en memoria tampoco queda mutada a medias.
    assert repo.personal.locale_code == "es-CO"


# --------------------------------------------------------------------------- #
# FA "Fallo en la persistencia de la preferencia" — 500                        #
# --------------------------------------------------------------------------- #

def test_fallo_de_persistencia_es_500_con_el_mensaje_del_rf() -> None:
    db = DbFake()
    repo = IdiomaRepoFake(falla_al_escribir=RuntimeError("conexión perdida"))

    with pytest.raises(InfrastructureError) as error:
        GuardarIdiomaPersonalUseCase(db=db, idioma_repo=repo).execute(_dto("en-US"), PRODUCTOR)

    assert error.value.code == "ERROR_PERSISTENCIA_IDIOMA"
    assert error.value.status_code == 500
    assert "Error de persistencia" in error.value.message
    assert "se aplicará temporalmente en esta sesión" in error.value.message
    assert isinstance(error.value.original_error, RuntimeError)
    assert db.commits == 0
    assert db.rollbacks == 1


def test_el_500_de_persistencia_no_traga_el_400_de_dominio() -> None:
    """Un AppError de dominio debe atravesar el except, no volverse un 500."""
    db = DbFake()
    repo = IdiomaRepoFake(
        personal=_preferencia("es-CO"),
        falla_al_escribir=RuntimeError("no debería llegar aquí"),
    )

    with pytest.raises(ValidationError) as error:
        GuardarIdiomaPersonalUseCase(db=db, idioma_repo=repo).execute(_dto("de-DE"), PRODUCTOR)

    assert error.value.status_code == 400


def test_el_500_de_persistencia_no_traga_el_404_del_repositorio() -> None:
    db = DbFake()
    repo = IdiomaRepoFake(
        personal=_preferencia("es-CO"),
        falla_al_escribir=NotFoundError(
            code="PREFERENCIA_IDIOMA_NO_ENCONTRADA",
            message="La preferencia de idioma que intenta actualizar ya no existe.",
        ),
    )

    with pytest.raises(NotFoundError) as error:
        GuardarIdiomaPersonalUseCase(db=db, idioma_repo=repo).execute(_dto("en-US"), PRODUCTOR)

    assert error.value.status_code == 404
    assert db.rollbacks == 1


# --------------------------------------------------------------------------- #
# FA "Conflicto de actualización de perfil" — 409                              #
# --------------------------------------------------------------------------- #

def test_version_de_perfil_desfasada_es_409() -> None:
    db = DbFake()
    repo = IdiomaRepoFake(personal=_preferencia("es-CO"), version=VERSION_PERFIL)

    with pytest.raises(ConflictError) as error:
        GuardarIdiomaPersonalUseCase(db=db, idioma_repo=repo).execute(
            _dto("en-US", version_perfil=VERSION_PERFIL - 1), PRODUCTOR
        )

    assert error.value.code == "CONFLICTO_PERFIL_MODIFICADO"
    assert error.value.status_code == 409
    assert error.value.field == "version_perfil"
    assert "Conflicto de datos" in error.value.message
    assert "su perfil está siendo modificado en este momento" in error.value.message
    assert db.commits == 0
    assert repo.actualizados == []


def test_version_de_perfil_vigente_deja_guardar() -> None:
    db = DbFake()
    repo = IdiomaRepoFake(personal=_preferencia("es-CO"), version=VERSION_PERFIL)

    resultado = GuardarIdiomaPersonalUseCase(db=db, idioma_repo=repo).execute(
        _dto("en-US", version_perfil=VERSION_PERFIL), PRODUCTOR
    )

    assert resultado.locale_code == "en-US"
    assert db.commits == 1
    assert len(repo.actualizados) == 1


def test_sin_version_de_perfil_el_guardado_sigue_funcionando() -> None:
    """Retrocompatibilidad: un cliente que no envía version_perfil no se rompe."""
    db = DbFake()
    repo = IdiomaRepoFake(personal=_preferencia("es-CO"), version=VERSION_PERFIL)

    resultado = GuardarIdiomaPersonalUseCase(db=db, idioma_repo=repo).execute(
        _dto("en-US"), PRODUCTOR
    )

    assert resultado.locale_code == "en-US"
    assert db.commits == 1


def test_usuario_sin_version_en_bd_no_bloquea_el_guardado() -> None:
    db = DbFake()
    repo = IdiomaRepoFake(personal=_preferencia("es-CO"), version=None)

    resultado = GuardarIdiomaPersonalUseCase(db=db, idioma_repo=repo).execute(
        _dto("en-US", version_perfil=1), PRODUCTOR
    )

    assert resultado.locale_code == "en-US"
    assert db.commits == 1


# --------------------------------------------------------------------------- #
# Idioma global (Admin)                                                        #
# --------------------------------------------------------------------------- #

def test_guardar_global_valida_el_locale_igual_que_el_personal() -> None:
    db = DbFake()
    repo = IdiomaRepoFake()

    with pytest.raises(ValidationError) as error:
        GuardarIdiomaGlobalUseCase(db=db, idioma_repo=repo).execute(_dto("pt-BR"), ADMIN)

    assert error.value.code == "IDIOMA_NO_DISPONIBLE"
    assert error.value.status_code == 400
    assert db.commits == 0


def test_guardar_global_tambien_verifica_la_version_de_perfil() -> None:
    db = DbFake()
    repo = IdiomaRepoFake(global_=_preferencia("es-CO", global_=True), version=VERSION_PERFIL)

    with pytest.raises(ConflictError) as error:
        GuardarIdiomaGlobalUseCase(db=db, idioma_repo=repo).execute(
            _dto("en-US", version_perfil=99), ADMIN
        )

    assert error.value.code == "CONFLICTO_PERFIL_MODIFICADO"
    assert error.value.status_code == 409
    assert db.commits == 0


def test_guardar_global_crea_la_fila_marcada_como_por_defecto() -> None:
    db = DbFake()
    repo = IdiomaRepoFake()

    resultado = GuardarIdiomaGlobalUseCase(db=db, idioma_repo=repo).execute(_dto("en-US"), ADMIN)

    assert resultado.es_por_defecto is True
    assert resultado.id_usuario == ADMIN.id_usuario
    assert db.commits == 1


def test_fallo_de_persistencia_del_global_tambien_es_500_tipado() -> None:
    db = DbFake()
    repo = IdiomaRepoFake(falla_al_escribir=RuntimeError("deadlock"))

    with pytest.raises(InfrastructureError) as error:
        GuardarIdiomaGlobalUseCase(db=db, idioma_repo=repo).execute(_dto("en-US"), ADMIN)

    assert error.value.code == "ERROR_PERSISTENCIA_IDIOMA"
    assert error.value.status_code == 500
    assert db.rollbacks == 1


# --------------------------------------------------------------------------- #
# Resolución jerárquica: personal -> global -> es-CO                           #
# --------------------------------------------------------------------------- #

def test_resolucion_personal_gana_sobre_global() -> None:
    repo = IdiomaRepoFake(
        personal=_preferencia("en-US"),
        global_=_preferencia("es-CO", global_=True),
    )

    resuelto = ObtenerIdiomaResueltoUseCase(idioma_repo=repo).execute(PRODUCTOR)

    assert resuelto["locale_code"] == "en-US"
    assert resuelto["fuente"] == "personal"
    assert resuelto["id_preferencia_idioma"] == 42
    assert resuelto["version_perfil"] == VERSION_PERFIL


def test_resolucion_global_cuando_no_hay_personal() -> None:
    repo = IdiomaRepoFake(personal=None, global_=_preferencia("en-US", global_=True))

    resuelto = ObtenerIdiomaResueltoUseCase(idioma_repo=repo).execute(PRODUCTOR)

    assert resuelto["locale_code"] == "en-US"
    assert resuelto["fuente"] == "global"
    assert resuelto["id_preferencia_idioma"] == 99


def test_resolucion_cae_a_es_co_cuando_no_hay_ninguna() -> None:
    repo = IdiomaRepoFake(personal=None, global_=None)

    resuelto = ObtenerIdiomaResueltoUseCase(idioma_repo=repo).execute(PRODUCTOR)

    assert resuelto["locale_code"] == LOCALE_DEFAULT == "es-CO"
    assert resuelto["fuente"] == "defecto"
    assert resuelto["id_preferencia_idioma"] is None


def test_la_resolucion_expone_la_version_de_perfil_para_el_siguiente_patch() -> None:
    """Sin esto el cliente no tiene de dónde sacar la version_perfil que reenvía."""
    repo = IdiomaRepoFake(personal=None, global_=None, version=11)

    resuelto = ObtenerIdiomaResueltoUseCase(idioma_repo=repo).execute(PRODUCTOR)

    assert resuelto["version_perfil"] == 11
