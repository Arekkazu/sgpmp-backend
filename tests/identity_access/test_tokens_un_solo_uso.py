"""Pruebas de regresión para el hashing de tokens de un solo uso."""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from types import SimpleNamespace

from src.identity_access.application.use_cases.contrasena import (
    restablecer_contrasena_use_case as restablecer_module,
)
from src.identity_access.application.use_cases.contrasena import (
    solicitar_recuperacion_use_case as recuperar_module,
)
from src.identity_access.application.use_cases.registro import (
    crear_usuario_use_case as crear_module,
)
from src.identity_access.application.use_cases.registro.activar_cuenta_use_case import (
    ActivarCuentaUseCase,
)
from src.identity_access.domain.entities.cuenta import Cuenta
from src.identity_access.domain.value_objects.token_un_solo_uso import (
    calcular_hash_token,
)


TOKEN_CRUDO = "token-crudo-solo-para-el-usuario"
TOKEN_HASH = hashlib.sha256(TOKEN_CRUDO.encode("utf-8")).hexdigest()


class DbFake:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


class CuentaRepoFake:
    def __init__(self, cuenta: Cuenta) -> None:
        self.cuenta = cuenta
        self.hash_consultado = None
        self.guardada = None

    def obtener_por_hash_token(self, token_hash: str):
        self.hash_consultado = token_hash
        return self.cuenta

    def obtener_por_usuario(self, _id_usuario: int):
        return self.cuenta

    def guardar(self, cuenta: Cuenta):
        self.guardada = cuenta
        return cuenta


class EventoRepoFake:
    def __init__(self) -> None:
        self.eventos = []

    def contar_solicitudes_recuperacion_por_ip(self, _ip, _desde):
        return 0

    def registrar(self, **evento):
        self.eventos.append(evento)


class UsuarioRepoFake:
    def __init__(self, usuario) -> None:
        self.usuario = usuario
        self.actualizado = None

    def obtener_por_correo(self, _correo):
        return self.usuario

    def obtener_por_id(self, _id_usuario):
        return self.usuario

    def cambiar_contrasena(self, usuario):
        self.actualizado = usuario


class SesionRepoFake:
    def __init__(self) -> None:
        self.cuenta_invalidada = None

    def invalidar_todas_sesiones(self, id_cuenta_usuario: int) -> None:
        self.cuenta_invalidada = id_cuenta_usuario


class UsuarioFake:
    id_usuario = 7
    nombre = "Ana"
    correo = "ana@example.com"

    def __init__(self) -> None:
        self.nueva_contrasena = None

    def cambiar_contrasena(self, contrasena) -> None:
        self.nueva_contrasena = contrasena


class CuentaCrearRepoFake:
    def __init__(self) -> None:
        self.id_usuario = None
        self.token_hash = None

    def crear(
        self,
        id_usuario: int,
        token_hash: str,
        id_estado_cuenta=None,
    ) -> None:
        self.id_usuario = id_usuario
        self.token_hash = token_hash


class UsuarioCrearRepoFake:
    def __init__(self, usuario) -> None:
        self.usuario = usuario

    def guardar(self, _usuario):
        return self.usuario


class CorreoActivacionPortFake:
    def __init__(self, db: DbFake) -> None:
        self.db = db
        self.llamadas = []

    def programar_envio(self, **datos) -> None:
        assert self.db.commits == 1
        self.llamadas.append(datos)


class CaptchaVerifierFake:
    def __init__(self) -> None:
        self.llamadas = []

    def verificar(self, token: str, ip: str | None = None) -> bool:
        self.llamadas.append((token, ip))
        return True


def nueva_cuenta(estado: int) -> Cuenta:
    return Cuenta(
        id_cuenta_usuario=11,
        id_usuario=7,
        id_estado_cuenta=estado,
        token_activacion_actual="hash-anterior",
        fecha_cambio_estado=datetime.now(timezone.utc),
    )


def test_calcular_hash_token_no_conserva_el_valor_crudo() -> None:
    assert calcular_hash_token(TOKEN_CRUDO) == TOKEN_HASH
    assert calcular_hash_token(TOKEN_CRUDO) != TOKEN_CRUDO


def test_registro_persiste_hash_y_envia_el_token_crudo(monkeypatch) -> None:
    usuario = SimpleNamespace(
        id_usuario=7,
        id_rol=2,
        correo="ana@example.com",
        nombre="Ana",
        es_mayor_de_edad=lambda: True,
    )

    cuentas_repo = CuentaCrearRepoFake()
    db = DbFake()
    correos = CorreoActivacionPortFake(db)
    captcha = CaptchaVerifierFake()

    monkeypatch.setattr(
        crear_module.secrets,
        "token_urlsafe",
        lambda _bytes: TOKEN_CRUDO,
    )

    monkeypatch.setattr(
        crear_module.Contrasena,
        "desde_texto_plano",
        lambda _texto: object(),
    )

    monkeypatch.setattr(
        crear_module.Usuario,
        "registrar_nuevo",
        lambda **_datos: usuario,
    )

    crear_module.CrearUsuarioUseCase(
        usuarios_repo=UsuarioCrearRepoFake(usuario),
        cuentas_repo=cuentas_repo,
        eventos_repo=EventoRepoFake(),
        correo_activacion_port=correos,
        captcha_verifier=captcha,
        db=db,
    ).execute(
        SimpleNamespace(
            correo_electronico=usuario.correo,
            contrasena="Clave1!x",
            nombre="Ana",
            apellidos="Prueba",
            fecha_nacimiento=None,
            genero=SimpleNamespace(value="F"),
            tipo_identificacion="CC",
            numero_identificacion="123",
            telefono=None,
            direccion=None,
            confirmar_contrasena="Clave1!x",
            captcha_token="captcha-valido",
        ),
        "127.0.0.1",
        "pytest",
    )

    assert cuentas_repo.token_hash == TOKEN_HASH
    assert captcha.llamadas == [("captcha-valido", "127.0.0.1")]

    assert correos.llamadas
    assert correos.llamadas[0]["token"] == TOKEN_CRUDO
    assert correos.llamadas[0]["token"] != TOKEN_HASH


def test_activar_cuenta_consulta_por_hash_y_consume_el_token() -> None:
    cuenta = nueva_cuenta(Cuenta.ESTADO_PENDIENTE)
    repo = CuentaRepoFake(cuenta)
    db = DbFake()

    ActivarCuentaUseCase(
        cuentas_repo=repo,
        eventos_repo=EventoRepoFake(),
        db=db,
    ).execute(TOKEN_CRUDO, "127.0.0.1", "pytest")

    assert repo.hash_consultado == TOKEN_HASH
    assert repo.guardada is not None
    assert repo.guardada.token_activacion_actual is None
    assert repo.guardada.esta_activa()
    assert db.commits == 1


def test_recuperacion_guarda_hash_y_envia_solo_el_token_crudo(
    monkeypatch,
) -> None:
    cuenta = nueva_cuenta(Cuenta.ESTADO_ACTIVO)
    cuentas_repo = CuentaRepoFake(cuenta)
    usuario = UsuarioFake()
    correos = []

    monkeypatch.setattr(
        recuperar_module.secrets,
        "token_urlsafe",
        lambda _bytes: TOKEN_CRUDO,
    )

    monkeypatch.setattr(
        recuperar_module,
        "send_email",
        lambda **correo: correos.append(correo),
    )

    recuperar_module.SolicitarRecuperacionUseCase(
        usuarios_repo=UsuarioRepoFake(usuario),
        cuentas_repo=cuentas_repo,
        eventos_repo=EventoRepoFake(),
        db=DbFake(),
    ).execute(
        SimpleNamespace(
            correo_electronico=usuario.correo,
        ),
        "127.0.0.1",
    )

    assert cuentas_repo.guardada is not None
    assert cuentas_repo.guardada.token_activacion_actual == TOKEN_HASH

    assert correos
    assert TOKEN_CRUDO in correos[0]["html_body"]
    assert TOKEN_HASH not in correos[0]["html_body"]


def test_recuperacion_de_cuenta_pendiente_rota_el_token(
    monkeypatch,
) -> None:
    cuenta = nueva_cuenta(Cuenta.ESTADO_PENDIENTE)
    cuentas_repo = CuentaRepoFake(cuenta)
    usuario = UsuarioFake()
    correos = []

    monkeypatch.setattr(
        recuperar_module.secrets,
        "token_urlsafe",
        lambda _bytes: TOKEN_CRUDO,
    )

    monkeypatch.setattr(
        recuperar_module,
        "send_email",
        lambda **correo: correos.append(correo),
    )

    recuperar_module.SolicitarRecuperacionUseCase(
        usuarios_repo=UsuarioRepoFake(usuario),
        cuentas_repo=cuentas_repo,
        eventos_repo=EventoRepoFake(),
        db=DbFake(),
    ).execute(
        SimpleNamespace(
            correo_electronico=usuario.correo,
        ),
        "127.0.0.1",
    )

    assert cuentas_repo.guardada is not None
    assert cuentas_repo.guardada.token_activacion_actual == TOKEN_HASH

    assert correos
    assert TOKEN_CRUDO in correos[0]["html_body"]
    assert TOKEN_HASH not in correos[0]["html_body"]


def test_restablecimiento_consulta_hash_y_marca_token_usado(
    monkeypatch,
) -> None:
    cuenta = nueva_cuenta(Cuenta.ESTADO_ACTIVO)
    cuentas_repo = CuentaRepoFake(cuenta)
    usuario = UsuarioFake()
    sesiones_repo = SesionRepoFake()
    nueva_contrasena = object()

    monkeypatch.setattr(
        restablecer_module.Contrasena,
        "cifrar",
        staticmethod(lambda _texto: nueva_contrasena),
    )

    restablecer_module.RestablecerContrasenaUseCase(
        usuarios_repo=UsuarioRepoFake(usuario),
        cuentas_repo=cuentas_repo,
        sesiones_repo=sesiones_repo,
        eventos_repo=EventoRepoFake(),
        intentos_anonimos_repo=SimpleNamespace(),
        db=DbFake(),
    ).execute(
        SimpleNamespace(
            token=TOKEN_CRUDO,
            nueva_contrasena="NuevaClave1!",
        ),
        "127.0.0.1",
    )

    assert cuentas_repo.hash_consultado == TOKEN_HASH

    assert cuentas_repo.guardada is not None
    # El hash se conserva (no se limpia) tras un uso exitoso: permite distinguir
    # "token ya utilizado" (409) de "token nunca existió" (401) en un reintento.
    assert cuentas_repo.guardada.token_activacion_actual == "hash-anterior"
    assert cuentas_repo.guardada.token_usado is True

    assert usuario.nueva_contrasena is nueva_contrasena
    assert sesiones_repo.cuenta_invalidada == cuenta.id_cuenta_usuario
