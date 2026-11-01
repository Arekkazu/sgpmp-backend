# | Fecha      | Nombre   | Que se hizo                                                        |
# |------------|----------|--------------------------------------------------------------------|
# | 2026-10-31 | Arekkazu | RFC-010 RF-69: versión por animal, estado SOMBRA y fuente de datos |
"""RFC-010 (§C1 puntos 1 y 2): llave (tipo_modelo, componente, id_activo_biologico) y SOMBRA.

Fakes en memoria. La unicidad y el CHECK de la BD se prueban contra Postgres real en
tests/integration/test_rf69_registro_activacion_version_e2e.py.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import Mock

import pytest

from src.prediction.application.use_cases.inferencia.registrar_resultado_inferencia_use_case import (
    RegistrarResultadoInferenciaUseCase,
)
from src.prediction.application.use_cases.versiones_modelo.activar_version_modelo_use_case import (
    ActivarVersionModeloUseCase,
)
from src.prediction.application.use_cases.versiones_modelo.registrar_version_modelo_use_case import (
    RegistrarVersionModeloUseCase,
)
from src.prediction.domain.entities.version_modelo import VersionModelo
from src.prediction.domain.services.validacion_auditoria_m04 import campos_requeridos
from src.prediction.infrastructure.dto.registrar_resultado_inferencia_dto import RegistrarResultadoInferenciaDTO
from src.shared.errors import BusinessRuleError, ConflictError


def _version(*, id_activo=885, fuente="REAL", estado="APROBADO", notas="Validada", id_version=7):
    v = VersionModelo.crear(
        tipo_modelo="MODELO_ESPECIES_MEDIANAS",
        formato_artefacto="ONNX",
        ruta_artefacto="/tmp/x.onnx",
        tamanio_artefacto_bytes=10,
        hash_artefacto_sha256="a" * 64,
        dataset_entrenamiento_hash="b" * 64,
        id_proceso_rf71=uuid.UUID("12345678-0000-0000-0000-000000000000"),
        f1_score=Decimal("0.9"), recall_clase_riesgo_alto=Decimal("0.9"), precision_modelo=None,
        accuracy=None, roc_auc_score=None, recall_por_clase=None, matriz_confusion=None,
        compatibilidad_variables=[], fecha_entrenamiento=datetime(2026, 10, 31, tzinfo=timezone.utc),
        id_activo_biologico=id_activo, fuente_datos=fuente,
    )
    v.id_version_modelo, v.estado_version, v.notas_validacion = id_version, estado, notas
    return v


# ── Entidad ───────────────────────────────────────────────────────────────

def test_nombre_version_lleva_el_animal_y_cabe_en_varchar_40():
    v = _version(id_activo=999999)
    assert v.nombre_version == "ESPECIES_MEDIANAS_999999_261031_12345678"
    assert len(v.nombre_version) <= 40


def test_sombra_desde_aprobado_sin_notas_y_fuera_de_produccion():
    v = _version(notas=None, fuente="SINTETICA")
    v.poner_en_sombra()
    assert (v.estado_version, v.esta_produccion) == ("SOMBRA", False)


@pytest.mark.parametrize("estado", ["EN_VALIDACION", "SOMBRA", "ACTIVO"])
def test_sombra_solo_desde_aprobado(estado):
    with pytest.raises(ConflictError) as e:
        _version(estado=estado).poner_en_sombra()
    assert e.value.code == "VERSION_NO_APROBADA"


def test_sombra_se_promueve_a_activo_con_notas():
    v = _version(estado="SOMBRA")
    v.activar()
    assert (v.estado_version, v.esta_produccion) == ("ACTIVO", True)


def test_modelo_sintetico_no_se_activa_ni_desde_sombra():
    with pytest.raises(BusinessRuleError) as e:
        _version(estado="SOMBRA", fuente="SINTETICA").activar()
    assert e.value.code == "MODELO_SINTETICO_SOLO_SOMBRA"


def test_sombra_se_depreca():
    v = _version(estado="SOMBRA")
    v.deprecar()
    assert v.estado_version == "DEPRECADO"


def test_rf73_version_en_sombra_tiene_sus_campos_minimos():
    snapshot = _version(estado="SOMBRA")._snapshot()
    assert campos_requeridos("VERSION_EN_SOMBRA", snapshot) == ["tipo_modelo", "id_version"]
    assert all(snapshot.get(c) is not None for c in campos_requeridos("VERSION_EN_SOMBRA", snapshot))
    assert snapshot["id_activo_biologico"] == 885 and snapshot["fuente_datos"] == "REAL"


# ── Activar / poner en sombra ─────────────────────────────────────────────

class _Repo:
    def __init__(self, entidad, previa=None):
        self.entidad, self.previa, self.consulta, self.historial = entidad, previa, None, []

    def obtener_por_id(self, _id):
        return self.entidad

    def obtener_activo_por_tipo(self, tipo_modelo, componente=None, id_activo_biologico=None, estado="ACTIVO"):
        self.consulta = (tipo_modelo, componente, id_activo_biologico, estado)
        return self.previa

    def actualizar(self, v):
        return v

    def registrar_historial(self, **kw):
        self.historial.append((kw["estado_anterior"], kw["estado_nuevo"]))


def _activar(repo, en_sombra):
    auditoria = Mock()
    ActivarVersionModeloUseCase(db=Mock(), repo=repo, auditoria_repo=auditoria).execute(
        7, id_usuario=1, en_sombra=en_sombra
    )
    return [c.kwargs["tipo_evento"] for c in auditoria.registrar.call_args_list]


def test_poner_en_sombra_depreca_la_sombra_previa_del_mismo_animal():
    previa = _version(estado="SOMBRA", id_version=3)
    repo = _Repo(_version(), previa)

    eventos = _activar(repo, en_sombra=True)

    assert repo.consulta == ("MODELO_ESPECIES_MEDIANAS", None, 885, "SOMBRA")
    assert previa.estado_version == "DEPRECADO"
    assert repo.historial == [("SOMBRA", "DEPRECADO"), ("APROBADO", "SOMBRA")]
    assert eventos == ["VERSION_EN_SOMBRA", "VERSION_DEPRECADA"]


def test_promover_de_sombra_registra_el_estado_real_de_origen():
    repo = _Repo(_version(estado="SOMBRA"))

    eventos = _activar(repo, en_sombra=False)

    assert repo.consulta == ("MODELO_ESPECIES_MEDIANAS", None, 885, "ACTIVO")
    assert repo.historial == [("SOMBRA", "ACTIVO")]
    assert eventos == ["VERSION_ACTIVADA"]


# ── Registro (RF-71 → RF-69) ──────────────────────────────────────────────

def _registrador():
    return RegistrarVersionModeloUseCase(
        db=Mock(), repo=Mock(), auditoria_repo=Mock(), variable_port=Mock(), aviso_port=Mock()
    )


@pytest.mark.parametrize(
    ("tipo_modelo", "id_activo", "codigo"),
    [
        ("MODELO_ESPECIES_GRANDES", None, "ACTIVO_BIOLOGICO_REQUERIDO"),
        ("MODELO_AVES", 885, "ACTIVO_BIOLOGICO_NO_APLICA"),
        ("MODELO_RIESGO_CONTAGIO", 885, "ACTIVO_BIOLOGICO_NO_APLICA"),
    ],
)
def test_registro_exige_animal_solo_a_individual(tipo_modelo, id_activo, codigo):
    with pytest.raises(BusinessRuleError) as e:
        _registrador()._validar_activo_biologico(tipo_modelo, id_activo)
    assert (e.value.code, e.value.field) == (codigo, "id_activo_biologico")


# ── RF-66: resultados del motor ───────────────────────────────────────────

def test_resultado_con_modelo_de_otro_animal_se_rechaza():
    version = Mock()
    version.obtener_llave.return_value = ("SOMBRA", "MODELO_ESPECIES_GRANDES", None, 886)
    repo = Mock()
    repo.obtener.return_value = None
    uc = RegistrarResultadoInferenciaUseCase(
        db=Mock(), repo=repo, version_port=version, activo_port=Mock(), auditoria_repo=Mock(),
        patologia_repo=Mock(),
    )
    dto = RegistrarResultadoInferenciaDTO(
        id_resultado_inferencia=str(uuid.uuid4()), id_activo_biologico=885,
        tipo_modelo="MODELO_ESPECIES_GRANDES", id_version_modelo=12, nivel_riesgo=0,
        probabilidad_riesgo={"0": 1.0}, probabilidad_enfermedad={"0": 1.0}, confianza_global="1",
        contexto_incompleto=False, modo_ejecucion="SERVIDOR", latencia_ms=50,
        fecha_inicio_ventana="2026-09-20T14:50:00+00:00", fecha_fin_ventana="2026-09-20T15:00:00+00:00",
        fecha_inferencia="2026-10-25T20:30:49+00:00", modo_sombra=True,
    )
    with pytest.raises(BusinessRuleError) as e:
        uc.execute(dto)
    assert e.value.code == "VERSION_DE_OTRO_ACTIVO"
    repo.guardar.assert_not_called()
