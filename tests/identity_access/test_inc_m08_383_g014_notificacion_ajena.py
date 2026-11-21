# | Fecha      | Nombre       | Que se hizo                                                          |
# |------------|--------------|----------------------------------------------------------------------|
# | 2026-11-21 | destroyerban | INC-M08-383-G014 RF-105: notificación ajena → 403 con el mensaje del RF |
"""INC-M08-383-G014 (#1199): marcar leída, atender o descartar una notificación de otro usuario.

RF-105 restricción 4 / CU03 FA3: se rechaza con «No tiene permisos para modificar notificaciones de otros
usuarios» (403) y no cambia nada. Una notificación que no existe sigue respondiendo 404.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import pytest

from src.identity_access.application.use_cases.notificaciones.marcar_notificacion_leida_use_case import (
    AtenderNotificacionUseCase,
    DescartarNotificacionUseCase,
    MarcarNotificacionLeidaUseCase,
)
from src.identity_access.domain.entities.notificacion import Notificacion
from src.shared.errors import AuthorizationError, NotFoundError

PRODUCTOR, ADMINISTRADOR = 176, 1
AHORA = datetime(2026, 11, 21, 12, 0, tzinfo=timezone.utc)
ACCION = "Revisé el bebedero del galpón y quedó funcionando"


def _notificacion(id_notificacion: int, id_usuario: int) -> Notificacion:
    return Notificacion(id_notificacion=id_notificacion, id_evento=10, tipo_evento=32, id_usuario=id_usuario,
                        mensaje="Temperatura alta en el galpón", fecha_envio=AHORA, es_leido=False,
                        estado_envio="enviado", nivel="ADVERTENCIA", estado="NUEVA")


class RepoFake:
    """Como la BD con RLS: ``obtener_interna`` solo ve las propias; ``existe_interna`` ve todas."""

    def __init__(self, *notificaciones: Notificacion) -> None:
        self.todas = {n.id_notificacion: n for n in notificaciones}
        self.guardadas: list[Notificacion] = []

    def obtener_interna(self, id_notificacion: int, id_usuario: int) -> Optional[Notificacion]:
        n = self.todas.get(id_notificacion)
        return n if n is not None and n.id_usuario == id_usuario else None

    def existe_interna(self, id_notificacion: int) -> bool:
        return id_notificacion in self.todas

    def guardar(self, notificacion: Notificacion) -> None:
        self.guardadas.append(notificacion)


class DbFake:
    def __init__(self) -> None:
        self.commits = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        pass


ACCIONES = {
    "leida": lambda repo, db, i, u: MarcarNotificacionLeidaUseCase(repo, db).execute(i, u),
    "atendida": lambda repo, db, i, u: AtenderNotificacionUseCase(repo, db).execute(i, u, ACCION),
    "descartada": lambda repo, db, i, u: DescartarNotificacionUseCase(repo, db).execute(i, u),
}


@pytest.mark.parametrize("accion", ACCIONES)
def test_la_notificacion_de_otro_usuario_responde_403_con_el_mensaje_del_rf(accion):
    ajena = _notificacion(50, ADMINISTRADOR)
    repo, db = RepoFake(ajena), DbFake()

    with pytest.raises(AuthorizationError) as exc:
        ACCIONES[accion](repo, db, 50, PRODUCTOR)

    assert exc.value.code == "NOTIFICACION_AJENA"
    assert exc.value.message == "No tiene permisos para modificar notificaciones de otros usuarios."
    assert repo.guardadas == [] and db.commits == 0
    assert ajena.estado == "NUEVA" and not ajena.es_leido


@pytest.mark.parametrize("accion", ACCIONES)
def test_la_que_no_existe_sigue_respondiendo_404(accion):
    repo, db = RepoFake(_notificacion(50, ADMINISTRADOR)), DbFake()

    with pytest.raises(NotFoundError) as exc:
        ACCIONES[accion](repo, db, 999, PRODUCTOR)

    assert exc.value.code == "NOTIFICACION_NO_ENCONTRADA"
    assert repo.guardadas == [] and db.commits == 0


@pytest.mark.parametrize("accion, estado", [("leida", "LEIDA"), ("atendida", "ATENDIDA"), ("descartada", "DESCARTADA")])
def test_la_propia_se_sigue_modificando(accion, estado):
    propia = _notificacion(60, PRODUCTOR)
    repo, db = RepoFake(propia), DbFake()

    resultado = ACCIONES[accion](repo, db, 60, PRODUCTOR)

    assert resultado.estado == estado
    assert repo.guardadas == [propia] and db.commits == 1
