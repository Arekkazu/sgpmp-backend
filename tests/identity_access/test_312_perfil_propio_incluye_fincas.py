"""Arekkazu/SGPMP-FRONT-END-PWA#312: `GET /usuarios/me` respondía `fincas: []`
para todo usuario, porque el perfil propio nunca las consultaba. Con eso QA
concluyó que un usuario con finca no la tenía.
"""
from __future__ import annotations

from datetime import date, datetime
from types import SimpleNamespace

from src.identity_access.application.use_cases.perfil.consultar_perfil_use_case import ConsultarPerfilUseCase


class _UsuarioRepoFake:
    def obtener_detalle(self, id_usuario: int):
        return SimpleNamespace(
            id_usuario=id_usuario, nombre="Miguel", apellidos="Vargas",
            correo_electronico="contador@pecuaria.co", tipo_identificacion="CC",
            numero_identificacion="1075123456", fecha_nacimiento=date(1990, 1, 1),
            fecha_registro=datetime(2026, 1, 1), nombre_rol="Contador",
            estado_cuenta="Activo", version=1,
        )


class _EventoRepoFake:
    def registrar(self, **_evento) -> None:
        pass


class _DbFake:
    def __init__(self) -> None:
        self.params = None

    def execute(self, _sql, params=None):
        self.params = params
        return SimpleNamespace(mappings=lambda: SimpleNamespace(
            all=lambda: [{"id_finca": 15, "nombre": "Finca Contador"}]
        ))

    def commit(self) -> None:
        pass

    def rollback(self) -> None:
        pass


def test_perfil_propio_incluye_las_fincas_asignadas_del_usuario_autenticado():
    db = _DbFake()
    use_case = ConsultarPerfilUseCase(usuarios_repo=_UsuarioRepoFake(), eventos_repo=_EventoRepoFake(), db=db)

    perfil = use_case.execute(SimpleNamespace(id_usuario=5, id_rol=5))

    assert perfil["fincas"] == [{"id_finca": 15, "nombre": "Finca Contador"}]
    assert db.params == {"id_usuario": 5}
