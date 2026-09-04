"""RF-44: ``aplicar_cambio_estado`` es el punto único de cambio de estado.

Muta la entidad (que valida BAJA irreversible, redundancia y matriz de
transiciones) y registra el histórico con el ``modulo_origen`` correcto.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.biological_assets.application.use_cases.gestion._cambio_estado import aplicar_cambio_estado
from src.biological_assets.domain.entities.activo_biologico import ActivoBiologico, HistoricoEstado
from src.shared.errors import ConflictError


class HistoricoRepoFake:
    def __init__(self) -> None:
        self.registros: list[dict] = []

    def registrar(self, **kwargs) -> HistoricoEstado:
        self.registros.append(kwargs)
        return HistoricoEstado(
            id_activo_biologico=kwargs['id_activo'],
            id_estado_anterior=kwargs['id_estado_anterior'],
            id_estado_nuevo=kwargs['id_estado_nuevo'],
            fecha_cambio=kwargs['fecha'],
            modulo_origen=kwargs['modulo_origen'],
            id_usuario=kwargs['usuario_id'],
            motivo_cambio=kwargs['motivo'],
        )


def _activo(id_estado: int) -> ActivoBiologico:
    return ActivoBiologico(
        id_especie=1,
        tipo='INDIVIDUAL',
        origen_financiero='compra',
        id_infraestructura=1,
        id_estado=id_estado,
        id_usuario=1,
        id_activo_biologico=10,
    )


def test_muta_entidad_y_registra_historico_con_origen() -> None:
    repo = HistoricoRepoFake()
    activo = _activo(id_estado=1)
    fecha = datetime(2026, 5, 10, tzinfo=timezone.utc)

    aplicar_cambio_estado(
        activo=activo,
        id_estado_nuevo=2,
        fecha=fecha,
        motivo='motivo',
        usuario_id=7,
        historico_repo=repo,
        modulo_origen='MANUAL',
    )

    assert activo.id_estado == 2
    assert len(repo.registros) == 1
    reg = repo.registros[0]
    assert reg['id_activo'] == 10
    assert reg['id_estado_anterior'] == 1
    assert reg['id_estado_nuevo'] == 2
    assert reg['modulo_origen'] == 'MANUAL'
    assert reg['usuario_id'] == 7
    assert reg['motivo'] == 'motivo'


def test_no_registra_historico_si_la_transicion_es_invalida() -> None:
    repo = HistoricoRepoFake()
    activo = _activo(id_estado=6)  # BAJA: irreversible

    with pytest.raises(ConflictError):
        aplicar_cambio_estado(
            activo=activo,
            id_estado_nuevo=2,
            fecha=datetime.now(timezone.utc),
            motivo='x',
            usuario_id=1,
            historico_repo=repo,
            modulo_origen='MANUAL',
        )

    assert repo.registros == []
    assert activo.id_estado == 6
