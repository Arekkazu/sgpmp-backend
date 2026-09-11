"""Pruebas unitarias de la alerta interna por fallo del archivado RF-10."""
import pytest

from src.identity_access.application.use_cases.auditoria.notificar_fallo_archivado_use_case import (
    ACCION_LEER,
    ID_CANAL_INTERNO,
    RECURSO_AUDITORIA,
    TIPO_FALLO_ARCHIVADO,
    NotificarFalloArchivadoUseCase,
)


class DbFake:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


class EventoRepoFake:
    def __init__(self, fallar: bool = False) -> None:
        self.registrados = []
        self.fallar = fallar

    def registrar(self, tipo_evento, exitoso, id_usuario, detalle, id_sesion=None) -> None:
        if self.fallar:
            raise RuntimeError("auditoria caida")
        self.registrados.append((tipo_evento, exitoso, id_usuario, detalle))


class NotificacionRepoFake:
    def __init__(self, id_evento: int = 77) -> None:
        self.id_evento = id_evento
        self.registradas = []

    def buscar_ultimo_evento_id(self, id_usuario, tipo_evento) -> int:
        return self.id_evento

    def registrar(self, id_evento, id_usuario, id_canal, mensaje, estado) -> int:
        self.registradas.append((id_evento, id_usuario, id_canal, mensaje, estado))
        return len(self.registradas)


class UsuarioRepoFake:
    def __init__(self, ids: list[int]) -> None:
        self.ids = ids
        self.consultas = []

    def listar_ids_con_permiso(self, id_recurso, id_accion) -> list[int]:
        self.consultas.append((id_recurso, id_accion))
        return self.ids


def _caso(destinatarios, eventos=None, notificaciones=None, db=None):
    return NotificarFalloArchivadoUseCase(
        eventos_repo=eventos or EventoRepoFake(),
        notificaciones_repo=notificaciones or NotificacionRepoFake(),
        usuarios_repo=UsuarioRepoFake(destinatarios),
        db=db or DbFake(),
    )


def test_alerta_registra_un_evento_y_notifica_a_cada_administrador() -> None:
    eventos = EventoRepoFake()
    notificaciones = NotificacionRepoFake(id_evento=99)
    db = DbFake()

    avisados = _caso([4, 9], eventos, notificaciones, db).execute(causa="OSError: sin espacio")

    assert avisados == 2
    assert len(eventos.registrados) == 1
    tipo, exitoso, id_usuario, detalle = eventos.registrados[0]
    assert tipo == TIPO_FALLO_ARCHIVADO
    assert exitoso is False
    assert id_usuario == 4
    assert detalle == {"proceso": "ARCHIVADO_AUDITORIA", "causa": "OSError: sin espacio"}
    assert [n[1] for n in notificaciones.registradas] == [4, 9]
    assert {n[0] for n in notificaciones.registradas} == {99}
    assert {n[2] for n in notificaciones.registradas} == {ID_CANAL_INTERNO}
    assert all("Fallo en política de retención" in n[3] for n in notificaciones.registradas)
    assert all("sin espacio" in n[3] for n in notificaciones.registradas)
    assert db.commits == 1
    assert db.rollbacks == 0


def test_destinatarios_se_resuelven_por_permiso_no_por_rol_fijo() -> None:
    usuarios = UsuarioRepoFake([1])
    NotificarFalloArchivadoUseCase(
        eventos_repo=EventoRepoFake(),
        notificaciones_repo=NotificacionRepoFake(),
        usuarios_repo=usuarios,
        db=DbFake(),
    ).execute(causa="x")

    assert usuarios.consultas == [(RECURSO_AUDITORIA, ACCION_LEER)]


def test_sin_administradores_no_registra_nada_y_no_rompe() -> None:
    eventos = EventoRepoFake()
    notificaciones = NotificacionRepoFake()
    db = DbFake()

    avisados = _caso([], eventos, notificaciones, db).execute(causa="x")

    assert avisados == 0
    assert eventos.registrados == []
    assert notificaciones.registradas == []
    assert db.commits == 0


def test_fallo_al_registrar_la_alerta_revierte_la_transaccion() -> None:
    db = DbFake()

    with pytest.raises(RuntimeError, match="auditoria caida"):
        _caso([1], EventoRepoFake(fallar=True), db=db).execute(causa="x")

    assert db.commits == 0
    assert db.rollbacks == 1
