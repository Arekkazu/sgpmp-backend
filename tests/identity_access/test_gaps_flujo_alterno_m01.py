"""Regresión de los gaps de flujo alterno del Módulo 1.

Un caso por cada ❌ de `anotaciones/modulo_1/gaps_flujo_alterno_modulo1.md`:
el código de respuesta que el RF pide y que el módulo no devolvía.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.identity_access.application.use_cases.registro.crear_usuario_use_case import (
    CrearUsuarioUseCase,
)
from src.shared.errors import ServiceUnavailableError


class _DbFake:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


class _NotificacionServiceFake:
    """Reproduce el contrato de ``NotificacionService.notificar``.

    Devuelve ``False`` cuando el canal EMAIL se intentó y el SMTP falló tras
    sus 3 reintentos internos.
    """

    def __init__(self, resultado_email) -> None:
        self.resultado_email = resultado_email
        self.llamadas: list[dict] = []

    def notificar(self, **datos):
        self.llamadas.append(datos)
        return self.resultado_email


def _ejecutar_registro(notificacion_service) -> _DbFake:
    usuario = SimpleNamespace(
        id_usuario=7,
        id_rol=2,
        correo="ana@example.com",
        nombre="Ana",
        es_mayor_de_edad=lambda: True,
    )
    db = _DbFake()

    use_case = CrearUsuarioUseCase(
        usuarios_repo=SimpleNamespace(guardar=lambda _u: usuario),
        cuentas_repo=SimpleNamespace(crear=lambda *_a, **_k: None),
        eventos_repo=SimpleNamespace(registrar=lambda **_k: None),
        captcha_verifier=SimpleNamespace(verificar=lambda *_a, **_k: True),
        db=db,
        notificacion_service=notificacion_service,
    )

    dto = SimpleNamespace(
        correo_electronico="ana@example.com",
        contrasena="Contrasena1!",
        confirmar_contrasena="Contrasena1!",
        nombre="Ana",
        apellidos="Pérez",
        fecha_nacimiento=None,
        genero=SimpleNamespace(value="F"),
        tipo_identificacion="CC",
        numero_identificacion="0012345678",
        telefono=None,
        direccion=None,
        captcha_token="captcha-valido",
    )

    use_case.execute(dto, "127.0.0.1", "pytest")
    return db


def test_rf01_smtp_agotado_responde_503_sin_perder_el_registro(monkeypatch) -> None:
    """RF-01: "Fallo crítico en el servicio de correo (SMTP)" → HTTP 503.

    El correo se envía dentro del request justamente para poder responderlo;
    con `BackgroundTasks` el 201 ya había salido y el caso era irreproducible.
    """
    from src.identity_access.application.use_cases.registro import (
        crear_usuario_use_case as modulo,
    )

    monkeypatch.setattr(modulo.Usuario, "registrar_nuevo", lambda **_d: SimpleNamespace(
        id_usuario=7,
        id_rol=2,
        correo="ana@example.com",
        nombre="Ana",
        es_mayor_de_edad=lambda: True,
    ))
    monkeypatch.setattr(modulo.Contrasena, "desde_texto_plano", lambda _t: object())

    servicio = _NotificacionServiceFake(resultado_email=False)

    with pytest.raises(ServiceUnavailableError) as error:
        _ejecutar_registro(servicio)

    assert error.value.status_code == 503
    assert error.value.code == "EMAIL_NO_DISPONIBLE"
    assert error.value.message.startswith("Registro exitoso")
    assert servicio.llamadas, "el correo debe intentarse dentro del request"


def test_rf01_registro_exitoso_no_lanza_cuando_el_correo_sale(monkeypatch) -> None:
    from src.identity_access.application.use_cases.registro import (
        crear_usuario_use_case as modulo,
    )

    monkeypatch.setattr(modulo.Usuario, "registrar_nuevo", lambda **_d: SimpleNamespace(
        id_usuario=7,
        id_rol=2,
        correo="ana@example.com",
        nombre="Ana",
        es_mayor_de_edad=lambda: True,
    ))
    monkeypatch.setattr(modulo.Contrasena, "desde_texto_plano", lambda _t: object())

    db = _ejecutar_registro(_NotificacionServiceFake(resultado_email=True))

    assert db.commits == 1
    assert db.rollbacks == 0


def test_rf03_renombrar_el_rol_protegido_responde_403() -> None:
    """RF-03: "Intento de modificación o eliminación de rol protegido" → 403.

    El DELETE ya daba 403; el PUT dependía del trigger P0004 y terminaba en
    422 `BusinessRuleError`.
    """
    from src.identity_access.application.use_cases.roles.editar_rol_use_case import (
        EditarRolUseCase,
    )
    from src.shared.errors import AuthorizationError

    rol = SimpleNamespace(
        id_rol=1,
        nombre_rol="Administrador",
        descripcion="Rol raíz",
        es_protegido=True,
    )
    db = _DbFake()
    use_case = EditarRolUseCase(
        roles_repo=SimpleNamespace(obtener_por_id=lambda _id: rol),
        eventos_repo=SimpleNamespace(registrar=lambda **_k: None),
        db=db,
    )

    with pytest.raises(AuthorizationError) as error:
        use_case.execute(
            id_rol=1,
            dto=SimpleNamespace(nombre_rol="Superadmin", descripcion=None),
            usuario_actual=SimpleNamespace(id_usuario=9),
        )

    assert error.value.status_code == 403
    assert error.value.code == "ROL_PROTEGIDO"
    assert db.commits == 0


def test_rf03_el_rol_protegido_conserva_su_descripcion_editable() -> None:
    """El trigger P0004 solo protege el nombre: la descripción sigue editable."""
    from src.identity_access.application.use_cases.roles.editar_rol_use_case import (
        EditarRolUseCase,
    )

    rol = SimpleNamespace(
        id_rol=1,
        nombre_rol="Administrador",
        descripcion="Rol raíz",
        es_protegido=True,
        editar=lambda _n, _d: None,
    )
    db = _DbFake()
    EditarRolUseCase(
        roles_repo=SimpleNamespace(
            obtener_por_id=lambda _id: rol,
            guardar=lambda _rol: rol,
        ),
        eventos_repo=SimpleNamespace(registrar=lambda **_k: None),
        db=db,
    ).execute(
        id_rol=1,
        dto=SimpleNamespace(nombre_rol=None, descripcion="Nueva descripción"),
        usuario_actual=SimpleNamespace(id_usuario=9),
    )

    assert db.commits == 1


def _use_case_permisos(es_proceso_especial: bool, db: _DbFake):
    from src.identity_access.application.use_cases.permisos.asignar_permiso_use_case import (
        AsignarPermisoUseCase,
    )

    permisos_repo = SimpleNamespace(
        existe_recurso=lambda _id: True,
        existe_accion=lambda _id: True,
        es_proceso_especial=lambda _id: es_proceso_especial,
        buscar=lambda *_a: None,
        asignar=lambda *_a: SimpleNamespace(id_permiso=1),
    )
    return AsignarPermisoUseCase(
        roles_repo=SimpleNamespace(
            obtener_por_id=lambda _id: SimpleNamespace(id_rol=2, nombre_rol="Productor")
        ),
        permisos_repo=permisos_repo,
        eventos_repo=SimpleNamespace(registrar=lambda **_k: None),
        db=db,
    )


def test_rf04_ejecutar_sobre_recurso_comun_responde_400() -> None:
    """RF-04: "Acción no permitida para el recurso" → HTTP 400.

    `existe_accion()` solo miraba el catálogo genérico C/R/U/D/E, así que
    cualquier combinación rol+recurso+acción se aceptaba.
    """
    from src.shared.errors import ValidationError

    db = _DbFake()

    with pytest.raises(ValidationError) as error:
        _use_case_permisos(es_proceso_especial=False, db=db).execute(
            id_rol=2,
            dto=SimpleNamespace(id_recurso=1, id_accion=5),
            usuario_actual=SimpleNamespace(id_usuario=9),
        )

    assert error.value.status_code == 400
    assert error.value.code == "ACCION_NO_PERMITIDA_PARA_RECURSO"
    assert db.commits == 0


def test_rf04_ejecutar_sobre_proceso_especial_sigue_permitido() -> None:
    db = _DbFake()
    _use_case_permisos(es_proceso_especial=True, db=db).execute(
        id_rol=2,
        dto=SimpleNamespace(id_recurso=13, id_accion=5),
        usuario_actual=SimpleNamespace(id_usuario=9),
    )

    assert db.commits == 1


def _use_case_perfil(db: _DbFake, eventos):
    from src.identity_access.application.use_cases.perfil.editar_perfil_use_case import (
        EditarPerfilUseCase,
    )

    return EditarPerfilUseCase(
        usuarios_repo=SimpleNamespace(obtener_por_id=lambda _id: None),
        cuentas_repo=SimpleNamespace(),
        sesiones_repo=SimpleNamespace(),
        eventos_repo=eventos,
        roles_repo=SimpleNamespace(),
        db=db,
    )


def test_rf05_escalada_de_privilegios_responde_403_y_queda_auditada() -> None:
    """RF-05: "Intento de escalada de privilegios" → 403 + auditoría.

    `extra="forbid"` rechazaba `id_rol` con un 400 genérico de Pydantic antes
    de que el caso de uso pudiera registrar el intento.
    """
    from src.identity_access.infrastructure.dto.perfil_dto import EditarPerfilDTO
    from src.shared.errors import AuthorizationError

    registros: list[dict] = []
    db = _DbFake()
    dto = EditarPerfilDTO(nombre="Ana", apellidos="Pérez", version=1, id_rol=1)

    with pytest.raises(AuthorizationError) as error:
        _use_case_perfil(db, SimpleNamespace(registrar=lambda **k: registros.append(k))).execute(
            id_usuario=7,
            dto=dto,
            usuario_actual=SimpleNamespace(id_usuario=7, id_rol=2),
        )

    assert error.value.status_code == 403
    assert error.value.code == "ESCALADA_PRIVILEGIOS"
    assert registros, "el intento debe quedar en la bitácora antes del 403"
    assert registros[0]["exitoso"] is False
    assert registros[0]["detalle"]["campos_rechazados"] == ["id_rol"]
    assert db.commits == 1, "la auditoría se confirma aunque la edición se rechace"


def test_rf05_el_403_se_devuelve_aunque_falle_la_auditoria() -> None:
    """Perder la bitácora no debe convertir la denegación en un 500."""
    from src.identity_access.infrastructure.dto.perfil_dto import EditarPerfilDTO
    from src.shared.errors import AuthorizationError

    def _explota(**_k):
        raise RuntimeError("bitácora caída")

    db = _DbFake()

    with pytest.raises(AuthorizationError):
        _use_case_perfil(db, SimpleNamespace(registrar=_explota)).execute(
            id_usuario=7,
            dto=EditarPerfilDTO(
                nombre="Ana", apellidos="Pérez", version=1, estado_usuario="Activo"
            ),
            usuario_actual=SimpleNamespace(id_usuario=7, id_rol=2),
        )

    assert db.rollbacks == 1
