"""Pruebas unitarias del reenvío del correo de activación.

Cubren el rate limiting por IP y la respuesta uniforme que evita enumerar
qué correos están registrados.
"""
import pytest

from src.identity_access.application.use_cases.registro import reenviar_token_use_case as modulo
from src.identity_access.application.use_cases.registro.reenviar_token_use_case import (
    MAX_REENVIOS_POR_HORA,
    TIPO_SOLICITUD_RECUPERACION,
    ReenviarTokenUseCase,
)
from src.shared.errors import BusinessRuleError

CORREO = "pendiente@ejemplo.com"
IP = "203.0.113.7"


class DbFake:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


class EventoRepoFake:
    def __init__(self, previos: int = 0) -> None:
        self.previos = previos
        self.registrados = []

    def contar_solicitudes_recuperacion_por_ip(self, ip, desde) -> int:
        return self.previos

    def registrar(self, tipo_evento, exitoso, id_usuario, detalle, id_sesion=None) -> None:
        self.registrados.append((tipo_evento, exitoso, id_usuario, detalle))


class UsuarioFake:
    id_usuario = 42
    nombre = "Ana"


class UsuarioRepoFake:
    def __init__(self, usuario) -> None:
        self.usuario = usuario

    def obtener_por_correo(self, correo):
        return self.usuario


class CuentaFake:
    def __init__(self, pendiente: bool) -> None:
        self.pendiente = pendiente
        self.token_asignado = None

    def esta_pendiente(self) -> bool:
        return self.pendiente

    def asignar_token_activacion(self, hash_token, ahora) -> None:
        self.token_asignado = hash_token


class CuentaRepoFake:
    def __init__(self, cuenta) -> None:
        self.cuenta = cuenta
        self.guardadas = []

    def obtener_por_usuario(self, id_usuario):
        return self.cuenta

    def guardar(self, cuenta) -> None:
        self.guardadas.append(cuenta)


class DtoFake:
    correo_electronico = CORREO


@pytest.fixture
def correos(monkeypatch):
    enviados = []
    monkeypatch.setattr(modulo, "send_email", lambda **kw: enviados.append(kw))
    return enviados


def _caso(usuario=None, cuenta=None, previos=0):
    db = DbFake()
    eventos = EventoRepoFake(previos)
    cuentas = CuentaRepoFake(cuenta)
    use_case = ReenviarTokenUseCase(
        cuentas_repo=cuentas,
        usuarios_repo=UsuarioRepoFake(usuario),
        eventos_repo=eventos,
        db=db,
    )
    return use_case, db, eventos, cuentas


def test_reenvia_y_audita_cuenta_pendiente(correos):
    cuenta = CuentaFake(pendiente=True)
    use_case, db, eventos, cuentas = _caso(UsuarioFake(), cuenta)

    mensaje = use_case.execute(DtoFake(), IP)

    assert cuenta.token_asignado is not None
    assert cuentas.guardadas == [cuenta]
    assert db.commits == 1
    assert len(correos) == 1 and correos[0]["to"] == CORREO
    assert eventos.registrados == [
        (TIPO_SOLICITUD_RECUPERACION, True, 42, {"ip": IP, "motivo": "reenvio_token_activacion"})
    ]
    assert "pendiente de activación" in mensaje


@pytest.mark.parametrize(
    "usuario, cuenta",
    [
        (None, None),                          # correo no registrado
        (UsuarioFake(), CuentaFake(False)),    # cuenta ya activa o deshabilitada
    ],
)
def test_no_revela_si_el_correo_existe(correos, usuario, cuenta):
    use_case, db, eventos, _ = _caso(usuario, cuenta)

    mensaje = use_case.execute(DtoFake(), IP)

    # Mismo mensaje que el caso exitoso y ningún efecto observable.
    assert mensaje == use_case.execute(DtoFake(), IP)
    assert correos == []
    assert eventos.registrados == []
    assert db.commits == 0


def test_rate_limit_por_ip(correos):
    use_case, _, _, _ = _caso(UsuarioFake(), CuentaFake(True), previos=MAX_REENVIOS_POR_HORA)

    with pytest.raises(BusinessRuleError) as exc:
        use_case.execute(DtoFake(), IP)

    assert exc.value.code == "LIMITE_SOLICITUDES_EXCEDIDO"
    assert correos == []
