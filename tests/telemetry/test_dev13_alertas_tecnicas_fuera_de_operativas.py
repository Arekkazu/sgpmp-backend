"""DEV-13 (RF-60, Restricción 5 — D-09): alertas técnicas fuera de /iot/alertas.

Las alertas técnicas (batería, conectividad, sobrecalentamiento) viven en
``modulo3.alertas`` junto con las operativas. ``/iot/alertas`` usa el recurso 32,
que el Productor tiene con R y U, y no filtraba ``tipo_alerta = 'TECNICA'``: el
Productor las veía y podía resolverlas. Ahora cada endpoint solo atiende su
ámbito; una alerta del otro ámbito no existe para él (404). Fakes en memoria.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.shared.errors import NotFoundError
from src.telemetry.application.use_cases.alertas.actualizar_estado_alerta_use_case import ActualizarEstadoAlertaUseCase
from src.telemetry.application.use_cases.alertas.consultar_alertas_use_case import ConsultarAlertasUseCase
from src.telemetry.domain.entities.alerta import TIPO_ALERTA_TECNICA, Alerta, AmbitoAlerta
from src.telemetry.infrastructure.dto.actualizar_estado_alerta_dto import ActualizarEstadoAlertaDTO

ID_TECNICA = 1
ID_OPERATIVA = 2


def _alerta(id_alerta: int, tipo_alerta: str) -> Alerta:
    ahora = datetime.now(timezone.utc)
    return Alerta(
        id_alerta=id_alerta, tipo_alerta=tipo_alerta, severidad="MODERADO", estado_alerta="ACTIVA",
        origen_evento="HEARTBEAT", tipo_variable="BATERIA", fecha_evento=ahora, fecha_generacion=ahora,
    )


class _AlertaRepo:
    def __init__(self):
        self.alertas = {
            ID_TECNICA: _alerta(ID_TECNICA, TIPO_ALERTA_TECNICA),
            ID_OPERATIVA: _alerta(ID_OPERATIVA, "ESTRES_TERMICO"),
        }
        self.filtros_listar: dict = {}
        self.estados_actualizados: list[int] = []

    def obtener_por_id(self, id_alerta, *, ids_fincas_permitidas=None):
        return self.alertas.get(id_alerta)

    def listar(self, **filtros):
        self.filtros_listar = filtros
        return [], 0

    def actualizar_estado(self, *, id_alerta, nuevo_estado, **_kw):
        self.estados_actualizados.append(id_alerta)
        alerta = self.alertas[id_alerta]
        alerta.estado_alerta = nuevo_estado
        return alerta


class _HistoricoRepo:
    def obtener_por_alerta(self, _id): return []
    def registrar(self, **_kw): pass


class _Db:
    def commit(self): pass
    def rollback(self): pass


# ── El ámbito ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "ambito, tipo_alerta, admite",
    [
        (AmbitoAlerta.OPERATIVA, "ESTRES_TERMICO", True),
        (AmbitoAlerta.OPERATIVA, TIPO_ALERTA_TECNICA, False),
        (AmbitoAlerta.TECNICA, TIPO_ALERTA_TECNICA, True),
        (AmbitoAlerta.TECNICA, "ESTRES_TERMICO", False),
    ],
)
def test_cada_ambito_admite_solo_sus_alertas(ambito, tipo_alerta, admite):
    assert ambito.admite(tipo_alerta) is admite


# ── GET /iot/alertas y GET /iot/alertas-tecnicas ───────────────────────────

def _consultar(repo: _AlertaRepo) -> ConsultarAlertasUseCase:
    return ConsultarAlertasUseCase(alerta_repo=repo, historico_repo=_HistoricoRepo())


def test_listado_operativo_excluye_las_tecnicas():
    repo = _AlertaRepo()
    _consultar(repo).listar(ambito=AmbitoAlerta.OPERATIVA)
    assert repo.filtros_listar["excluir_tipo_alerta"] == TIPO_ALERTA_TECNICA


def test_listado_operativo_filtrando_por_tecnica_no_las_trae():
    """Pedir tipo_alerta=TECNICA en /iot/alertas cruza ``== TECNICA`` con ``!= TECNICA``: página vacía."""
    repo = _AlertaRepo()
    _consultar(repo).listar(tipo_alerta=TIPO_ALERTA_TECNICA, ambito=AmbitoAlerta.OPERATIVA)
    assert repo.filtros_listar["tipo_alerta"] == TIPO_ALERTA_TECNICA
    assert repo.filtros_listar["excluir_tipo_alerta"] == TIPO_ALERTA_TECNICA


def test_listado_tecnico_solo_trae_tecnicas_aunque_pidan_otro_tipo():
    repo = _AlertaRepo()
    _consultar(repo).listar(tipo_alerta="ESTRES_TERMICO", ambito=AmbitoAlerta.TECNICA)
    assert repo.filtros_listar["tipo_alerta"] == TIPO_ALERTA_TECNICA
    assert repo.filtros_listar["excluir_tipo_alerta"] is None


def test_detalle_operativo_de_una_tecnica_es_404():
    with pytest.raises(NotFoundError):
        _consultar(_AlertaRepo()).obtener_detalle(ID_TECNICA, ambito=AmbitoAlerta.OPERATIVA)


def test_detalle_operativo_de_una_operativa_responde():
    alerta, _ = _consultar(_AlertaRepo()).obtener_detalle(ID_OPERATIVA, ambito=AmbitoAlerta.OPERATIVA)
    assert alerta.id_alerta == ID_OPERATIVA


# ── PATCH de estado ────────────────────────────────────────────────────────

def _actualizar(repo: _AlertaRepo, ambito: AmbitoAlerta, id_alerta: int):
    return ActualizarEstadoAlertaUseCase(
        db=_Db(), alerta_repo=repo, historico_repo=_HistoricoRepo(), ambito=ambito,
    ).execute(id_alerta=id_alerta, dto=ActualizarEstadoAlertaDTO(nuevo_estado="EN_ATENCION"), id_usuario=7)


def test_productor_no_cambia_el_estado_de_una_tecnica_por_iot_alertas():
    repo = _AlertaRepo()
    with pytest.raises(NotFoundError):
        _actualizar(repo, AmbitoAlerta.OPERATIVA, ID_TECNICA)
    assert repo.estados_actualizados == []
    assert repo.alertas[ID_TECNICA].estado_alerta == "ACTIVA"


def test_ingeniero_no_cambia_el_estado_de_una_operativa_por_alertas_tecnicas():
    repo = _AlertaRepo()
    with pytest.raises(NotFoundError):
        _actualizar(repo, AmbitoAlerta.TECNICA, ID_OPERATIVA)
    assert repo.estados_actualizados == []


def test_cada_endpoint_cambia_el_estado_de_su_ambito():
    repo = _AlertaRepo()
    assert _actualizar(repo, AmbitoAlerta.OPERATIVA, ID_OPERATIVA).estado_alerta == "EN_ATENCION"
    assert _actualizar(repo, AmbitoAlerta.TECNICA, ID_TECNICA).estado_alerta == "EN_ATENCION"
    assert repo.estados_actualizados == [ID_OPERATIVA, ID_TECNICA]
