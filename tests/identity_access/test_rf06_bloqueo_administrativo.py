"""RF-06 / RF-02: el bloqueo administrativo no vence y el de login reinicia el contador.

Antes, ``verificar_estado_cuenta`` trataba ``bloqueado_hasta is None`` como
"bloqueo vencido": una cuenta bloqueada por un administrador (que no tiene
``bloqueado_hasta``) se reactivaba en el siguiente login. Y al vencer el
bloqueo por intentos fallidos, el contador seguía en 5, así que el primer
fallo volvía a bloquear la cuenta.
"""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any

import pytest

from src.identity_access.application.use_cases.sesiones.sesion_comun import verificar_estado_cuenta
from src.identity_access.domain.entities.cuenta import Cuenta
from src.shared.errors import AuthorizationError, LockedError

AHORA = datetime(2026, 10, 11, 17, 25, tzinfo=timezone.utc)


def _cuenta(**kw: Any) -> Cuenta:
    return Cuenta(id_usuario=37, id_estado_cuenta=Cuenta.ESTADO_ACTIVO, id_cuenta_usuario=23, **kw)


class _CuentasRepoFake:
    def __init__(self) -> None:
        self.guardadas: list[Cuenta] = []

    def guardar(self, cuenta: Cuenta) -> Cuenta:
        self.guardadas.append(cuenta)
        return cuenta


class _DbFake:
    def commit(self) -> None:
        pass

    def rollback(self) -> None:
        pass


USUARIO: Any = SimpleNamespace(correo="a@b.co")


def _verificar(cuenta: Cuenta) -> _CuentasRepoFake:
    repo = _CuentasRepoFake()
    verificar_estado_cuenta(cuenta, USUARIO, repo, _DbFake(), AHORA)
    return repo


def test_bloqueo_administrativo_no_se_levanta_en_el_login() -> None:
    cuenta = _cuenta()
    cuenta.cambiar_estado(Cuenta.ESTADO_BLOQUEADO, "mal uso de la app")

    repo = _CuentasRepoFake()
    with pytest.raises(AuthorizationError) as exc:
        verificar_estado_cuenta(cuenta, USUARIO, repo, _DbFake(), AHORA)

    assert exc.value.code == "CUENTA_DESHABILITADA"
    assert exc.value.status_code == 403
    assert cuenta.id_estado_cuenta == Cuenta.ESTADO_BLOQUEADO
    assert repo.guardadas == [], "no debe persistirse ningún desbloqueo"


def test_bloqueo_administrativo_borra_un_bloqueado_hasta_viejo() -> None:
    """Un `bloqueado_hasta` vencido de un bloqueo de login anterior hacía que el
    bloqueo del administrador se tomara como vencido."""
    cuenta = _cuenta(bloqueado_hasta=AHORA - timedelta(days=30))

    cuenta.cambiar_estado(Cuenta.ESTADO_BLOQUEADO, "mal uso de la app")

    assert cuenta.bloqueado_hasta is None
    with pytest.raises(AuthorizationError):
        _verificar(cuenta)


def test_bloqueo_por_intentos_vigente_responde_423() -> None:
    cuenta = _cuenta(intentos_fallidos=5)
    cuenta.bloquear(AHORA - timedelta(minutes=5))

    with pytest.raises(LockedError) as exc:
        _verificar(cuenta)

    assert exc.value.code == "CUENTA_BLOQUEADA"
    assert cuenta.esta_bloqueada()


def test_bloqueo_por_intentos_vencido_reactiva_con_contador_en_cero() -> None:
    cuenta = _cuenta(intentos_fallidos=5, ultimo_intento_fallido=AHORA - timedelta(minutes=20))
    cuenta.bloquear(AHORA - timedelta(minutes=20))

    repo = _verificar(cuenta)

    assert cuenta.id_estado_cuenta == Cuenta.ESTADO_ACTIVO
    assert cuenta.bloqueado_hasta is None
    assert cuenta.intentos_fallidos == 0
    assert repo.guardadas == [cuenta]


def test_tras_vencer_el_bloqueo_un_fallo_no_vuelve_a_bloquear() -> None:
    """Antes el contador seguía en 5: el primer fallo lo llevaba a 6 y bloqueaba otra vez."""
    cuenta = _cuenta(intentos_fallidos=5)
    cuenta.bloquear(AHORA - timedelta(minutes=20))
    _verificar(cuenta)

    cuenta.incrementar_intentos(AHORA)

    assert cuenta.intentos_fallidos == 1


def test_activar_una_cuenta_bloqueada_por_intentos_limpia_el_bloqueo() -> None:
    cuenta = _cuenta(intentos_fallidos=5)
    cuenta.bloquear(AHORA)

    cuenta.cambiar_estado(Cuenta.ESTADO_ACTIVO, "desbloqueo manual")

    assert cuenta.bloqueado_hasta is None
    _verificar(cuenta)  # no lanza
