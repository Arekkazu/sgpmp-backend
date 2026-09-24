"""TC-M02-G15 / issue #326 (RF-35): PATCH /activos-biologicos/{id_activo} no
aplicaba el mismo alcance de finca que ya aplica el GET del mismo activo --
un usuario de la Finca 57 podia modificar (200 + persistencia) un activo de
la Finca 65, un BOLA (OWASP API1:2023).

GET (`ConsultarActivoUseCase`) ya filtraba correctamente desde INC-M02-39-G27
(ver test_consultar_activo_use_case_alcance_finca.py, mismo patron de test).
El PATCH nunca calculaba ni pasaba `ids_fincas_permitidas` -- ni el router lo
hacia, ni el use case lo aceptaba -- asi que `obtener_por_id` cargaba
cualquier activo sin filtrar y la mutacion se persistia igual. Se reutiliza
el mismo mecanismo que ya usa el GET (mismo repo method, mismo kwarg).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from src.biological_assets.application.use_cases.gestion.actualizar_activo_individual_use_case import (
    ActualizarActivoIndividualUseCase,
)
from src.biological_assets.infrastructure.dto.actualizar_activo_individual_dto import (
    ActualizarActivoIndividualDTO,
)
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import NotFoundError


@dataclass
class _ActivoFake:
    tipo: str = 'INDIVIDUAL'
    mutado: bool = field(default=False)
    id_activo_biologico: int = 350
    id_estado: int = 1  # ACTIVO -- no bloquea por "evento pendiente" (RF-35)
    fecha_actualizacion: object = None

    def actualizar_detalle_individual(self, **_kwargs) -> None:
        self.mutado = True


class HistoricoRepoFake:
    """Sin registros de histórico -> `validar_historial_consistente` no rechaza."""

    def obtener_ultimo_cambio(self, _id_activo):
        return None


class DbFake:
    def commit(self) -> None:
        pass

    def rollback(self) -> None:
        pass


class ActivoRepoFake:
    """Simula el filtrado real del repository SQL: el activo pertenece a
    `id_finca_del_activo`, y solo se devuelve si esa finca está dentro de
    `ids_fincas_permitidas` (o si el alcance es global, `None`)."""

    def __init__(self, activo, id_finca_del_activo: int = 65) -> None:
        self.activo = activo
        self.id_finca_del_activo = id_finca_del_activo
        self.actualizado_con = None

    def obtener_por_id(self, _id: int, *, ids_fincas_permitidas=None):
        if ids_fincas_permitidas is not None and self.id_finca_del_activo not in ids_fincas_permitidas:
            return None
        return self.activo

    def actualizar_detalle_individual(self, activo):
        self.actualizado_con = activo
        return activo


def _use_case(repo):
    return ActualizarActivoIndividualUseCase(
        db=DbFake(), repo=repo, historico_repo=HistoricoRepoFake(), bitacora_repo=None,
    )


def _dto():
    return ActualizarActivoIndividualDTO(raza='QA-G15-R2-BOLA-MARKER')


def test_activo_de_otra_finca_responde_404_no_200_ni_persiste():
    """Caso reportado: usuario de Finca 57 hace PATCH sobre el activo 350, de Finca 65."""
    repo = ActivoRepoFake(activo=_ActivoFake(), id_finca_del_activo=65)
    uc = _use_case(repo)
    usuario = UsuarioActual(id_usuario=35, id_token=1, id_rol=2)

    with pytest.raises(NotFoundError) as exc:
        uc.execute(350, _dto(), usuario, ids_fincas_permitidas=[57])

    assert exc.value.code == 'ACTIVO_NO_ENCONTRADO'
    assert repo.actualizado_con is None  # nunca llega a persistir


def test_activo_de_la_propia_finca_se_actualiza_normalmente():
    activo = _ActivoFake()
    repo = ActivoRepoFake(activo=activo, id_finca_del_activo=57)
    uc = _use_case(repo)
    usuario = UsuarioActual(id_usuario=35, id_token=1, id_rol=2)

    resultado = uc.execute(350, _dto(), usuario, ids_fincas_permitidas=[57, 65])

    assert resultado is activo
    assert activo.mutado is True
    assert repo.actualizado_con is activo


def test_alcance_global_no_filtra():
    """Un rol con alcance global (ej. Administrador) recibe
    ids_fincas_permitidas=None y no se filtra por finca."""
    activo = _ActivoFake()
    repo = ActivoRepoFake(activo=activo, id_finca_del_activo=999)
    uc = _use_case(repo)
    usuario = UsuarioActual(id_usuario=1, id_token=1, id_rol=1)

    resultado = uc.execute(350, _dto(), usuario, ids_fincas_permitidas=None)

    assert resultado is activo
    assert activo.mutado is True
