"""RF-35 (tarea Taiga "RBAC Veterinario, validar eventos pendientes,
concurrencia optimista" -- issue histórico #30): tres gaps sobre
PATCH /activos-biologicos/{id}:

1. Veterinario, listado explícitamente como actor de RF-35, no tenía
   permiso de Actualizar (U) sobre el recurso 29 -- cubierto por la
   migración `e5ce9d42b2ec` (RBAC, no testeable a nivel de use case; ver
   verificación en vivo documentada en el PR).
2. No se validaban "eventos pendientes sin cerrar" ni "inconsistencias en
   el historial" antes de aceptar una edición, pese a que el RF lo exige
   explícitamente en su Proceso.
3. Faltaba concurrencia optimista (412) en el PATCH, a diferencia del
   patrón estándar del proyecto (CLAUDE.md).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

import pytest

from src.biological_assets.application.use_cases.gestion._event_validations import (
    validar_historial_consistente,
    validar_sin_eventos_pendientes,
)
from src.biological_assets.application.use_cases.gestion.actualizar_activo_individual_use_case import (
    ActualizarActivoIndividualUseCase,
)
from src.biological_assets.domain.entities.activo_biologico import HistoricoEstado
from src.biological_assets.infrastructure.dto.actualizar_activo_individual_dto import (
    ActualizarActivoIndividualDTO,
)
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import BusinessRuleError, PreconditionFailedError


# ── _event_validations.py (unitario, sin use case) ───────────────────────────

@dataclass
class _ActivoIdEstado:
    id_activo_biologico: int = 1
    id_estado: int = 1  # ACTIVO


class _HistoricoRepoFake:
    def __init__(self, ultimo: HistoricoEstado | None) -> None:
        self.ultimo = ultimo

    def obtener_ultimo_cambio(self, _id_activo: int):
        return self.ultimo


def _historico(id_estado_nuevo: int) -> HistoricoEstado:
    return HistoricoEstado(
        id_activo_biologico=1,
        id_estado_anterior=1,
        id_estado_nuevo=id_estado_nuevo,
        fecha_cambio=datetime.now(timezone.utc),
        modulo_origen='modulo2',
        id_usuario=1,
    )


@pytest.mark.parametrize('id_estado', [3, 4])  # EN_TRATAMIENTO, AISLADO
def test_validar_sin_eventos_pendientes_bloquea_estados_con_evento_abierto(id_estado):
    with pytest.raises(BusinessRuleError) as exc:
        validar_sin_eventos_pendientes(_ActivoIdEstado(id_estado=id_estado))
    assert exc.value.code == 'EVENTO_PENDIENTE_SIN_CERRAR'


@pytest.mark.parametrize('id_estado', [1, 2, 5, 6])  # ACTIVO, INACTIVO, CERRADO, BAJA
def test_validar_sin_eventos_pendientes_permite_otros_estados(id_estado):
    validar_sin_eventos_pendientes(_ActivoIdEstado(id_estado=id_estado))  # no lanza


def test_validar_historial_consistente_bloquea_cuando_no_coincide():
    activo = _ActivoIdEstado(id_estado=1)  # ACTIVO en la entidad
    historico_repo = _HistoricoRepoFake(_historico(id_estado_nuevo=3))  # último registro: EN_TRATAMIENTO

    with pytest.raises(BusinessRuleError) as exc:
        validar_historial_consistente(activo, historico_repo)

    assert exc.value.code == 'HISTORIAL_INCONSISTENTE'


def test_validar_historial_consistente_permite_cuando_coincide():
    activo = _ActivoIdEstado(id_estado=1)
    historico_repo = _HistoricoRepoFake(_historico(id_estado_nuevo=1))

    validar_historial_consistente(activo, historico_repo)  # no lanza


def test_validar_historial_consistente_permite_sin_historial_previo():
    activo = _ActivoIdEstado(id_estado=1)
    historico_repo = _HistoricoRepoFake(None)  # activo nunca cambió de estado

    validar_historial_consistente(activo, historico_repo)  # no lanza


# ── ActualizarActivoIndividualUseCase (integración de las 3 validaciones) ────

@dataclass
class _ActivoFake:
    tipo: str = 'INDIVIDUAL'
    id_activo_biologico: int = 350
    id_estado: int = 1  # ACTIVO
    fecha_actualizacion: object = None
    mutado: bool = field(default=False)

    def actualizar_detalle_individual(self, **_kwargs) -> None:
        self.mutado = True


class _DbFake:
    def commit(self) -> None:
        pass

    def rollback(self) -> None:
        pass


class _ActivoRepoFake:
    def __init__(self, activo) -> None:
        self.activo = activo
        self.actualizado_con = None

    def obtener_por_id(self, _id, *, ids_fincas_permitidas=None):
        return self.activo

    def actualizar_detalle_individual(self, activo):
        self.actualizado_con = activo
        return activo


def _use_case(activo, historico_repo=None):
    repo = _ActivoRepoFake(activo)
    return ActualizarActivoIndividualUseCase(
        db=_DbFake(),
        repo=repo,
        historico_repo=historico_repo or _HistoricoRepoFake(None),
        bitacora_repo=None,
    ), repo


def _usuario() -> UsuarioActual:
    return UsuarioActual(id_usuario=7, id_token=1, id_rol=3)  # Veterinario


def test_concurrencia_optimista_rechaza_cuando_fecha_no_coincide():
    ts_bd = datetime(2026, 9, 1, tzinfo=timezone.utc)
    activo = _ActivoFake(fecha_actualizacion=ts_bd)
    uc, repo = _use_case(activo)
    dto = ActualizarActivoIndividualDTO(raza='Nueva', fecha_actualizacion=datetime(2026, 8, 1, tzinfo=timezone.utc))

    with pytest.raises(PreconditionFailedError) as exc:
        uc.execute(350, dto, _usuario())

    assert exc.value.code == 'CONFLICTO_CONCURRENCIA'
    assert repo.actualizado_con is None


def test_concurrencia_optimista_rechaza_cuando_bd_tiene_valor_y_dto_no_lo_envia():
    activo = _ActivoFake(fecha_actualizacion=datetime(2026, 9, 1, tzinfo=timezone.utc))
    uc, repo = _use_case(activo)
    dto = ActualizarActivoIndividualDTO(raza='Nueva')  # fecha_actualizacion=None

    with pytest.raises(PreconditionFailedError):
        uc.execute(350, dto, _usuario())


def test_concurrencia_optimista_permite_cuando_coincide():
    ts = datetime(2026, 9, 1, tzinfo=timezone.utc)
    activo = _ActivoFake(fecha_actualizacion=ts)
    uc, repo = _use_case(activo)
    dto = ActualizarActivoIndividualDTO(raza='Nueva', fecha_actualizacion=ts)

    resultado = uc.execute(350, dto, _usuario())

    assert resultado is activo
    assert repo.actualizado_con is activo


def test_concurrencia_optimista_permite_cuando_nunca_fue_editado():
    # Activo nunca editado (fecha_actualizacion=None en BD) y el cliente
    # tampoco la envía -- la doble rama None/None documentada en CLAUDE.md.
    activo = _ActivoFake(fecha_actualizacion=None)
    uc, repo = _use_case(activo)
    dto = ActualizarActivoIndividualDTO(raza='Nueva')

    resultado = uc.execute(350, dto, _usuario())

    assert resultado is activo


def test_edicion_exitosa_establece_fecha_actualizacion():
    activo = _ActivoFake(fecha_actualizacion=None)
    uc, repo = _use_case(activo)
    dto = ActualizarActivoIndividualDTO(raza='Nueva')

    uc.execute(350, dto, _usuario())

    assert activo.fecha_actualizacion is not None


@pytest.mark.parametrize('id_estado', [3, 4])
def test_evento_pendiente_bloquea_edicion_con_422(id_estado):
    activo = _ActivoFake(id_estado=id_estado)
    uc, repo = _use_case(activo)
    dto = ActualizarActivoIndividualDTO(raza='Nueva')

    with pytest.raises(BusinessRuleError) as exc:
        uc.execute(350, dto, _usuario())

    assert exc.value.code == 'EVENTO_PENDIENTE_SIN_CERRAR'
    assert repo.actualizado_con is None


def test_historial_inconsistente_bloquea_edicion_con_422():
    activo = _ActivoFake(id_estado=1)
    historico_repo = _HistoricoRepoFake(_historico(id_estado_nuevo=3))  # no coincide con id_estado=1
    uc, repo = _use_case(activo, historico_repo)
    dto = ActualizarActivoIndividualDTO(raza='Nueva')

    with pytest.raises(BusinessRuleError) as exc:
        uc.execute(350, dto, _usuario())

    assert exc.value.code == 'HISTORIAL_INCONSISTENTE'
    assert repo.actualizado_con is None


def test_veterinario_puede_editar_cuando_todo_es_consistente():
    """Veterinario (id_rol=3, ver _usuario()) ya no está bloqueado por RBAC
    a nivel de router (migración e5ce9d42b2ec); a nivel de use case, este
    test confirma que nada más lo bloquea cuando el activo está en un
    estado válido y el historial es consistente."""
    activo = _ActivoFake(id_estado=1, fecha_actualizacion=None)
    historico_repo = _HistoricoRepoFake(_historico(id_estado_nuevo=1))
    uc, repo = _use_case(activo, historico_repo)
    dto = ActualizarActivoIndividualDTO(raza='Nueva')

    resultado = uc.execute(350, dto, _usuario())

    assert resultado is activo
    assert repo.actualizado_con is activo
