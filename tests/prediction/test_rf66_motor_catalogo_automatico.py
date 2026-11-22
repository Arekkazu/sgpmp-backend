# | Fecha      | Nombre   | Que se hizo                                                     |
# |------------|----------|-----------------------------------------------------------------|
# | 2026-11-02 | Arekkazu | RF-66/RF-69: el motor IA arma su catálogo y copia versiones solo |
"""El motor IA atiende un animal individual nuevo sin registro manual (RFC-010 se respeta).

Fakes en memoria; la consulta del catálogo se verificó contra DEV.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import Mock

import pytest

from src.prediction.application.use_cases.motor.asignar_version_animal_use_case import AsignarVersionAnimalUseCase
from src.prediction.application.use_cases.motor.obtener_artefacto_version_use_case import (
    ObtenerArtefactoVersionUseCase,
)
from src.prediction.domain.entities.animal_motor import AnimalMotor
from src.prediction.domain.entities.version_modelo import VersionModelo
from src.shared.errors import NotFoundError

PROCESO = uuid.UUID("ed219d41-eca2-4b09-8d86-9acb1b7a8cac")


def _original(estado="SOMBRA") -> VersionModelo:
    v = VersionModelo.crear(
        tipo_modelo="MODELO_ESPECIES_GRANDES", formato_artefacto="ONNX",
        ruta_artefacto="/app/storage/modelos/x.onnx", tamanio_artefacto_bytes=10,
        hash_artefacto_sha256="a" * 64, dataset_entrenamiento_hash="b" * 64, id_proceso_rf71=PROCESO,
        f1_score=Decimal("0.6169"), recall_clase_riesgo_alto=Decimal("0.6763"), precision_modelo=None,
        accuracy=None, roc_auc_score=None, recall_por_clase=None, matriz_confusion=None,
        compatibilidad_variables=[14, 13, 16], fecha_entrenamiento=datetime(2026, 10, 25, tzinfo=timezone.utc),
        id_activo_biologico=2, fuente_datos="SINTETICA",
    )
    v.id_version_modelo, v.estado_version = 1, estado
    return v


class _Catalogo:
    def __init__(self, animales, referencia=1):
        self._animales, self._referencia = animales, referencia

    def animales(self, id_activo=None):
        return [a for a in self._animales if id_activo is None or a.id_activo_biologico == id_activo]

    def version_referencia(self, tipo_modelo):
        return self._referencia

    def lecturas(self, id_activo, desde, hasta):
        return []


class _Repo:
    def __init__(self, *versiones):
        self.versiones = {v.id_version_modelo: v for v in versiones}
        self.historial = []

    def obtener_por_id(self, id_version):
        return self.versiones.get(id_version)

    def guardar(self, v):
        v.id_version_modelo = max(self.versiones) + 1
        self.versiones[v.id_version_modelo] = v
        return v

    def registrar_historial(self, **kw):
        self.historial.append((kw["estado_anterior"], kw["estado_nuevo"], kw["tipo_actor"]))


def _caso(animales, repo, referencia=1):
    auditoria = Mock()
    return AsignarVersionAnimalUseCase(Mock(), _Catalogo(animales, referencia), repo, auditoria), auditoria


def test_animal_nuevo_recibe_copia_en_sombra_del_modelo_de_su_tipo():
    repo = _Repo(_original())
    caso, auditoria = _caso([AnimalMotor(4, "MODELO_ESPECIES_GRANDES")], repo)
    copia = caso.execute(4)
    assert (copia.id_activo_biologico, copia.estado_version, copia.version_referencia) == (4, "SOMBRA", 1)
    assert copia.hash_artefacto_sha256 == "a" * 64 and copia.ruta_artefacto == "/app/storage/modelos/x.onnx"
    assert copia.nombre_version == "ESPECIES_GRANDES_4_261025_ed219d41"
    assert copia.detalle_validacion.startswith("Copia automática de la versión 1 para el activo 4")
    assert repo.historial == [(None, "EN_VALIDACION", "SISTEMA"), ("EN_VALIDACION", "APROBADO", "SISTEMA"),
                              ("APROBADO", "SOMBRA", "SISTEMA")]
    assert auditoria.registrar.call_args.kwargs["payload_evento"]["copia_de"] == 1


def test_animal_con_version_propia_no_se_copia_otra_vez():
    repo = _Repo(_original())
    caso, auditoria = _caso([AnimalMotor(2, "MODELO_ESPECIES_GRANDES", 1, "n", "a" * 64, "SINTETICA")], repo)
    assert caso.execute(2).id_version_modelo == 1
    assert len(repo.versiones) == 1 and not auditoria.registrar.called


@pytest.mark.parametrize("animales, referencia, codigo", [
    ([], 1, "ANIMAL_FUERA_DEL_MOTOR"),
    ([AnimalMotor(4, "MODELO_ESPECIES_GRANDES")], None, "SIN_MODELO_DE_REFERENCIA"),
])
def test_sin_animal_atendible_o_sin_modelo_de_referencia_404(animales, referencia, codigo):
    caso, _ = _caso(animales, _Repo(_original()), referencia)
    with pytest.raises(NotFoundError) as e:
        caso.execute(4)
    assert e.value.code == codigo


def test_artefacto_solo_de_versiones_vigentes_y_dentro_del_almacen(tmp_path):
    (tmp_path / "x.onnx").write_bytes(b"onnx")
    v = _original()
    v.ruta_artefacto = str(tmp_path / "x.onnx")
    assert ObtenerArtefactoVersionUseCase(_Repo(v), str(tmp_path)).execute(1).read_bytes() == b"onnx"

    for estado, ruta in (("DEPRECADO", str(tmp_path / "x.onnx")), ("SOMBRA", "/etc/passwd")):
        v.estado_version, v.ruta_artefacto = estado, ruta
        with pytest.raises(NotFoundError):
            ObtenerArtefactoVersionUseCase(_Repo(v), str(tmp_path)).execute(1)


def test_rutas_del_motor_exigen_su_token(monkeypatch):
    from fastapi.testclient import TestClient

    from main import app

    monkeypatch.setenv("IOT_INFERENCIA_M04_TOKEN", "secreto")
    rutas = {r.path for r in app.routes}
    assert {"/prediccion/motor/catalogo", "/prediccion/motor/activos/{id_activo}/version",
            "/prediccion/motor/versiones/{id_version}/artefacto",
            "/prediccion/motor/activos/{id_activo}/lecturas"} <= rutas
    cliente = TestClient(app)
    assert cliente.get("/prediccion/motor/catalogo").status_code == 401
    assert cliente.post("/prediccion/motor/activos/4/version", headers={"Authorization": "Bearer otro"}).status_code == 401
