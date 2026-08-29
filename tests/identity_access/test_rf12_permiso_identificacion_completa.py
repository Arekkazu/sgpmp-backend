"""Regresiones del permiso especial de identificación completa de RF-12."""
from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.identity_access.application.use_cases.usuarios.consultar_detalle_usuario_use_case import (
    MAX_CONSULTAS_DETALLE_POR_VENTANA,
    ConsultarDetalleUsuarioUseCase,
)
from src.shared.errors import InfrastructureError, TooManyRequestsError


MIGRACION = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "f2c84d91a6e7_rf12_permiso_identificacion_completa.py"
)


class UsuarioRepoFake:
    def obtener_detalle(self, id_usuario: int):
        return SimpleNamespace(
            id_usuario=id_usuario,
            nombre="Ana",
            apellidos="Pérez",
            correo_electronico="ana@example.com",
            tipo_identificacion="CC",
            numero_identificacion="1075123456",
            fecha_nacimiento=date(1990, 1, 1),
            fecha_registro=datetime(2026, 1, 1),
            nombre_rol="Productor",
            estado_cuenta="Activo",
            version=1,
        )


class PermisoRepoFake:
    """Devuelve un permiso, ninguno, o revienta — los tres caminos de RF-12."""

    def __init__(self, concedido: bool, es_activo: bool = True, falla: bool = False) -> None:
        self.concedido = concedido
        self.es_activo = es_activo
        self.falla = falla
        self.consulta = None

    def buscar(self, **filtros):
        self.consulta = filtros
        if self.falla:
            raise RuntimeError("servicio de permisos caído")
        return SimpleNamespace(es_activo=self.es_activo) if self.concedido else None


class EventoRepoFake:
    def __init__(self, consultas_previas: int = 0, falla_al_registrar: bool = False) -> None:
        self.eventos = []
        self.consultas_previas = consultas_previas
        self.falla_al_registrar = falla_al_registrar
        self.conteo = None

    def registrar(self, **evento) -> None:
        if self.falla_al_registrar:
            raise RuntimeError("auditoría no disponible")
        self.eventos.append(evento)

    def contar_consultas_detalle_usuario(self, id_usuario: int, desde) -> int:
        self.conteo = {"id_usuario": id_usuario, "desde": desde}
        return self.consultas_previas


class UnidadTrabajoFake:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


def _use_case(permisos: PermisoRepoFake, eventos: EventoRepoFake, db: UnidadTrabajoFake):
    return ConsultarDetalleUsuarioUseCase(
        usuarios_repo=UsuarioRepoFake(),
        permisos_repo=permisos,
        eventos_repo=eventos,
        db=db,
    )


@pytest.mark.parametrize(
    ("concedido", "identificacion_esperada"),
    [
        (True, "1075123456"),
        (False, "1075******"),
    ],
)
def test_identificacion_depende_de_ejecutar_sobre_usuarios(
    concedido: bool,
    identificacion_esperada: str,
) -> None:
    permisos = PermisoRepoFake(concedido)
    eventos = EventoRepoFake()
    db = UnidadTrabajoFake()

    resultado = _use_case(permisos, eventos, db).execute(
        id_usuario=7,
        usuario_actual=SimpleNamespace(id_usuario=1, id_rol=1),
    )

    assert permisos.consulta == {
        "id_rol": 1,
        "id_recurso": 1,
        "id_accion": 5,
    }
    assert resultado["numero_identificacion"] == identificacion_esperada
    assert eventos.eventos[0]["detalle"]["tiene_id_completo"] is concedido
    assert db.commits == 1


def test_permiso_inactivo_no_concede_identificacion_completa() -> None:
    """`buscar` no filtra `es_activo`; el use case sí debe exigirlo."""
    permisos = PermisoRepoFake(concedido=True, es_activo=False)
    eventos = EventoRepoFake()

    resultado = _use_case(permisos, eventos, UnidadTrabajoFake()).execute(
        id_usuario=7,
        usuario_actual=SimpleNamespace(id_usuario=1, id_rol=1),
    )

    assert resultado["numero_identificacion"] == "1075******"
    assert eventos.eventos[0]["detalle"]["tiene_id_completo"] is False


def test_fallo_al_verificar_permiso_enmascara_en_vez_de_propagar() -> None:
    """FA de RF-12: privacidad sobre visualización, no un 500."""
    permisos = PermisoRepoFake(concedido=True, falla=True)
    eventos = EventoRepoFake()
    db = UnidadTrabajoFake()

    resultado = _use_case(permisos, eventos, db).execute(
        id_usuario=7,
        usuario_actual=SimpleNamespace(id_usuario=1, id_rol=1),
    )

    assert resultado["numero_identificacion"] == "1075******"
    assert eventos.eventos[0]["detalle"]["tiene_id_completo"] is False
    assert db.commits == 1


def test_patron_de_consulta_inusual_responde_429_y_deja_alerta() -> None:
    permisos = PermisoRepoFake(concedido=True)
    eventos = EventoRepoFake(consultas_previas=MAX_CONSULTAS_DETALLE_POR_VENTANA)
    db = UnidadTrabajoFake()

    with pytest.raises(TooManyRequestsError) as exc:
        _use_case(permisos, eventos, db).execute(
            id_usuario=7,
            usuario_actual=SimpleNamespace(id_usuario=1, id_rol=1),
        )

    assert exc.value.status_code == 429
    assert exc.value.code == "PATRON_CONSULTA_INUSUAL"
    # La alerta queda confirmada en auditoría antes de cortar la petición.
    assert eventos.eventos[0]["exitoso"] is False
    assert eventos.eventos[0]["detalle"]["motivo"] == "PATRON_CONSULTA_INUSUAL"
    assert db.commits == 1
    # El bloqueo se decide sobre el actor, no sobre el usuario consultado.
    assert eventos.conteo["id_usuario"] == 1


def test_justo_bajo_el_umbral_todavia_responde() -> None:
    eventos = EventoRepoFake(consultas_previas=MAX_CONSULTAS_DETALLE_POR_VENTANA - 1)

    resultado = _use_case(PermisoRepoFake(True), eventos, UnidadTrabajoFake()).execute(
        id_usuario=7,
        usuario_actual=SimpleNamespace(id_usuario=1, id_rol=1),
    )

    assert resultado["numero_identificacion"] == "1075123456"


def test_migracion_es_idempotente_y_exclusiva_del_administrador() -> None:
    contenido = " ".join(MIGRACION.read_text(encoding="utf-8").split())

    assert "revision: str = \"f2c84d91a6e7\"" in contenido
    assert "'admin_ejecutar_identificacion_completa'" in contenido
    assert "WHERE id_rol = 1 AND id_recurso = 1 AND id_accion = 5" in contenido
    assert "ON CONFLICT (id_rol, id_recurso, id_accion) DO NOTHING" in contenido


def test_sin_auditoria_no_se_entregan_los_datos() -> None:
    """FA de RF-12: sin trazabilidad, la visualización se bloquea."""
    eventos = EventoRepoFake(falla_al_registrar=True)
    db = UnidadTrabajoFake()

    with pytest.raises(InfrastructureError) as exc:
        _use_case(PermisoRepoFake(True), eventos, db).execute(
            id_usuario=7,
            usuario_actual=SimpleNamespace(id_usuario=1, id_rol=1),
        )

    assert exc.value.status_code == 500
    assert exc.value.code == "AUDITORIA_NO_DISPONIBLE"
    assert db.commits == 0
    assert db.rollbacks == 1
