"""Regresiones del permiso especial de identificación completa de RF-12."""
from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.identity_access.application.use_cases.usuarios.consultar_detalle_usuario_use_case import (
    ConsultarDetalleUsuarioUseCase,
)


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
    def __init__(self, concedido: bool) -> None:
        self.concedido = concedido
        self.consulta = None

    def buscar(self, **filtros):
        self.consulta = filtros
        return object() if self.concedido else None


class EventoRepoFake:
    def __init__(self) -> None:
        self.eventos = []

    def registrar(self, **evento) -> None:
        self.eventos.append(evento)


class UnidadTrabajoFake:
    def __init__(self) -> None:
        self.commits = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        raise AssertionError("No se esperaba rollback")


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
    use_case = ConsultarDetalleUsuarioUseCase(
        usuarios_repo=UsuarioRepoFake(),
        permisos_repo=permisos,
        eventos_repo=eventos,
        db=db,
    )

    resultado = use_case.execute(
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


def test_migracion_es_idempotente_y_exclusiva_del_administrador() -> None:
    contenido = " ".join(MIGRACION.read_text(encoding="utf-8").split())

    assert "revision: str = \"f2c84d91a6e7\"" in contenido
    assert "down_revision: Union[str, Sequence[str], None] = \"d4e2f8a15c9b\"" in contenido
    assert "'admin_ejecutar_identificacion_completa'" in contenido
    assert "WHERE id_rol = 1 AND id_recurso = 1 AND id_accion = 5" in contenido
    assert "ON CONFLICT (id_rol, id_recurso, id_accion) DO NOTHING" in contenido
