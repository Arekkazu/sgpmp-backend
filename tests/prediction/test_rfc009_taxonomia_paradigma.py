"""RFC-009 en M04: seis tipos de modelo en tres paradigmas.

RF-65 (umbrales y versión activa por paradigma), RF-69 (componente, métricas
poblacionales, unicidad ACTIVO por (tipo_modelo, componente)) y RF-73 (campos
mínimos de auditoría por paradigma). Fakes en memoria, sin DB.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from src.prediction.application.use_cases.motor_ia.configurar_motor_use_case import ConfigurarMotorUseCase
from src.prediction.application.use_cases.versiones_modelo.activar_version_modelo_use_case import ActivarVersionModeloUseCase
from src.prediction.application.use_cases.versiones_modelo.registrar_version_modelo_use_case import RegistrarVersionModeloUseCase
from src.prediction.domain.entities.version_modelo import VersionModelo
from src.prediction.infrastructure.dto.configurar_motor_dto import ConfigurarMotorDTO
from src.prediction.infrastructure.repositories.evento_auditoria_m04_repository import _validar_payload
from src.shared.errors import BusinessRuleError, PreconditionFailedError


class _Db:
    def commit(self): pass
    def rollback(self): pass


class _Auditoria:
    def __init__(self): self.eventos = []
    def registrar(self, **kw): self.eventos.append(kw)


# ── RF-65: configuración del motor ─────────────────────────────────────────

class _ConfigRepo:
    def obtener_por_tipo(self, _tipo): return None
    def guardar(self, entidad):
        entidad.id_configuracion_motor = 1
        return entidad


class _Versiones:
    """id_version -> (estado, tipo_modelo, componente)."""
    LLAVES = {
        10: ("ACTIVO", "MODELO_AVES", "DETECTOR"),
        11: ("ACTIVO", "MODELO_PORCINOS", "DETECTOR"),
        12: ("APROBADO", "MODELO_AVES", "ANOMALIAS"),
        20: ("ACTIVO", "MODELO_ESPECIES_GRANDES", None),
    }
    def obtener_llave(self, id_version): return self.LLAVES.get(id_version)


class _NodosEdge:
    def hay_nodos_activos(self, _tipo): return True


def _configurar(**campos):
    uc = ConfigurarMotorUseCase(
        db=_Db(), repo=_ConfigRepo(), auditoria_repo=_Auditoria(),
        version_port=_Versiones(), nodo_edge_port=_NodosEdge(),
    )
    entidad, _ = uc.execute(ConfigurarMotorDTO(ventana_temporal_min=10, **campos), id_usuario=1)
    return entidad


def test_poblacional_usa_umbral_de_anomalia_y_descarta_los_umbrales_supervisados():
    entidad = _configurar(
        tipo_modelo="MODELO_AVES", umbral_score_anomalia=Decimal("0.62"),
        umbral_riesgo_alto=Decimal("0.7"), umbral_alerta_critica=Decimal("0.8"),
        versiones_activas_por_componente={"DETECTOR": 10},
    )
    assert entidad.paradigma == "POBLACIONAL"
    assert (entidad.umbral_riesgo_alto, entidad.umbral_alerta_critica) == (None, None)
    assert entidad.umbral_score_anomalia == Decimal("0.62")
    assert entidad.versiones_activas_por_componente == {"DETECTOR": 10}
    assert entidad._snapshot()["paradigma"] == "POBLACIONAL"


@pytest.mark.parametrize("umbral", [None, Decimal("1.2"), Decimal("-0.1")])
def test_poblacional_sin_umbral_de_anomalia_valido_es_422(umbral):
    with pytest.raises(BusinessRuleError) as e:
        _configurar(tipo_modelo="MODELO_ACUICULTURA", umbral_score_anomalia=umbral)
    assert e.value.code == "UMBRAL_SCORE_ANOMALIA_FUERA_RANGO"


@pytest.mark.parametrize(
    "versiones, error, codigo",
    [
        ({"DETECTOR": 11}, BusinessRuleError, "VERSION_MODELO_INCOMPATIBLE"),  # otro tipo_modelo
        ({"SEGUIMIENTO": 10}, BusinessRuleError, "VERSION_MODELO_INCOMPATIBLE"),  # otro componente
        ({"ANOMALIAS": 12}, PreconditionFailedError, "MODELO_NO_ACTIVO"),
    ],
)
def test_poblacional_valida_la_llave_tipo_componente_de_cada_version(versiones, error, codigo):
    with pytest.raises(error) as e:
        _configurar(tipo_modelo="MODELO_AVES", umbral_score_anomalia=Decimal("0.5"),
                    versiones_activas_por_componente=versiones)
    assert e.value.code == codigo


def test_individual_exige_umbrales_supervisados():
    with pytest.raises(BusinessRuleError) as e:
        _configurar(tipo_modelo="MODELO_ESPECIES_GRANDES", umbral_score_anomalia=Decimal("0.5"))
    assert e.value.code == "UMBRALES_REQUERIDOS"


def test_individual_conserva_sus_reglas_y_descarta_el_umbral_de_anomalia():
    entidad = _configurar(
        tipo_modelo="MODELO_ESPECIES_GRANDES", umbral_riesgo_alto=Decimal("0.7"),
        umbral_alerta_critica=Decimal("0.9"), umbral_score_anomalia=Decimal("0.5"), id_version_modelo_activa=20,
    )
    assert entidad.paradigma == "INDIVIDUAL" and entidad.umbral_score_anomalia is None
    assert entidad.id_version_modelo_activa == 20
    with pytest.raises(BusinessRuleError) as e:
        _configurar(tipo_modelo="MODELO_ESPECIES_MEDIANAS", umbral_riesgo_alto=Decimal("0.7"),
                    umbral_alerta_critica=Decimal("0.9"), id_version_modelo_activa=20)
    assert e.value.code == "VERSION_MODELO_INCOMPATIBLE"


def test_los_tipos_por_tamano_ya_no_son_validos():
    with pytest.raises(BusinessRuleError) as e:
        _configurar(tipo_modelo="ESPECIES_PEQUEÑAS", umbral_riesgo_alto=Decimal("0.7"),
                    umbral_alerta_critica=Decimal("0.9"))
    assert e.value.code == "TIPO_MODELO_INVALIDO"


# ── RF-69: versiones ───────────────────────────────────────────────────────

def _version(tipo_modelo, componente=None, metricas_poblacionales=None, f1="0.9", recall="0.9"):
    v = VersionModelo.crear(
        tipo_modelo=tipo_modelo, formato_artefacto="ONNX", ruta_artefacto="/tmp/x", tamanio_artefacto_bytes=10,
        hash_artefacto_sha256="a" * 64, dataset_entrenamiento_hash="b" * 64, id_proceso_rf71=uuid.uuid4(),
        f1_score=Decimal(f1) if f1 else None, recall_clase_riesgo_alto=Decimal(recall) if recall else None,
        precision_modelo=None, accuracy=None, roc_auc_score=None, recall_por_clase=None, matriz_confusion=None,
        compatibilidad_variables=[], fecha_entrenamiento=datetime(2026, 10, 1, tzinfo=timezone.utc),
        componente=componente, metricas_poblacionales=metricas_poblacionales,
    )
    v.id_version_modelo = 7
    return v


_POBLACIONALES_OK = {"calibracion_completada": True, "tasa_falsos_positivos_rutina": 0.04,
                     "tasa_deteccion_eventos_clinicos": 0.91}


def test_poblacional_se_aprueba_por_calibracion_completada_sin_f1():
    v = _version("MODELO_PORCINOS", "DETECTOR", _POBLACIONALES_OK, f1=None, recall=None)
    v.validar_y_asignar_estado()
    assert v.estado_version == "APROBADO"
    assert v.nombre_version.startswith("PORCINOS_DETECTOR_")


def test_poblacional_sin_calibracion_completada_se_rechaza():
    v = _version("MODELO_PORCINOS", "DETECTOR", {**_POBLACIONALES_OK, "calibracion_completada": False}, f1=None, recall=None)
    v.validar_y_asignar_estado()
    assert v.estado_version == "RECHAZADO" and "calibracion_completada" in v.detalle_validacion


def test_individual_sigue_validandose_por_f1_y_recall():
    v = _version("MODELO_ESPECIES_MEDIANAS", f1="0.7")
    v.validar_y_asignar_estado()
    assert v.estado_version == "RECHAZADO" and "f1_score_global" in v.detalle_validacion


def _registrador():
    return RegistrarVersionModeloUseCase(db=_Db(), repo=None, auditoria_repo=_Auditoria(), variable_port=None)


@pytest.mark.parametrize("componente", [None, "CAMARA"])
def test_poblacional_exige_un_componente_valido(componente):
    with pytest.raises(BusinessRuleError) as e:
        _registrador()._validar_componente(componente)
    assert e.value.code == "COMPONENTE_INVALIDO"


@pytest.mark.parametrize(
    "metricas, codigo",
    [
        ({"calibracion_completada": True}, "METRICAS_INCOMPLETAS"),
        ({**_POBLACIONALES_OK, "calibracion_completada": "si"}, "METRICA_INVALIDA"),
        ({**_POBLACIONALES_OK, "tasa_falsos_positivos_rutina": "0.1"}, "METRICA_INVALIDA"),
        ({**_POBLACIONALES_OK, "tasa_deteccion_eventos_clinicos": 1.5}, "METRICA_FUERA_DE_RANGO"),
    ],
)
def test_metricas_poblacionales_invalidas(metricas, codigo):
    with pytest.raises(BusinessRuleError) as e:
        _registrador()._validar_metricas_poblacionales(metricas)
    assert e.value.code == codigo


class _VersionRepo:
    def __init__(self, entidad, previa):
        self.entidad, self.previa, self.llave = entidad, previa, None
    def obtener_por_id(self, _id): return self.entidad
    def obtener_activo_por_tipo(self, tipo_modelo, componente=None):
        self.llave = (tipo_modelo, componente)
        return self.previa
    def actualizar(self, v): return v
    def registrar_historial(self, **kw): pass


def test_activar_deprecia_solo_la_version_activa_del_mismo_componente():
    nueva = _version("MODELO_AVES", "DETECTOR", _POBLACIONALES_OK, f1=None, recall=None)
    nueva.estado_version, nueva.notas_validacion = "APROBADO", "Validada en campo"
    previa = _version("MODELO_AVES", "DETECTOR", _POBLACIONALES_OK, f1=None, recall=None)
    previa.id_version_modelo, previa.estado_version = 3, "ACTIVO"
    repo, auditoria = _VersionRepo(nueva, previa), _Auditoria()

    ActivarVersionModeloUseCase(db=_Db(), repo=repo, auditoria_repo=auditoria).execute(7, id_usuario=1)

    assert repo.llave == ("MODELO_AVES", "DETECTOR")
    assert previa.estado_version == "DEPRECADO" and nueva.estado_version == "ACTIVO"
    activada = next(e for e in auditoria.eventos if e["tipo_evento"] == "VERSION_ACTIVADA")
    assert _validar_payload("VERSION_ACTIVADA", activada["payload_evento"]) == []


# ── RF-73: campos mínimos por paradigma ────────────────────────────────────

def test_rf73_el_snapshot_de_cada_paradigma_cumple_los_campos_minimos():
    poblacional = _version("MODELO_ACUICULTURA", "METRICAS", _POBLACIONALES_OK, f1=None, recall=None)
    individual = _version("MODELO_ESPECIES_GRANDES")
    for v in (poblacional, individual):
        for evento in ("VERSION_REGISTRADA", "VERSION_APROBADA", "VERSION_RECHAZADA", "VERSION_DEPRECADA"):
            assert _validar_payload(evento, v._snapshot()) == [], (v.tipo_modelo, evento)


def test_rf73_poblacional_no_exige_f1_pero_si_sus_metricas_equivalentes():
    payload = {"tipo_modelo": "MODELO_AVES", "id_version": 1}
    assert _validar_payload("VERSION_APROBADA", payload) == [
        "calibracion_completada", "tasa_falsos_positivos_rutina", "tasa_deteccion_eventos_clinicos",
    ]
    payload = {"tipo_modelo": "MODELO_ESPECIES_GRANDES", "id_version": 1}
    assert _validar_payload("VERSION_APROBADA", payload) == ["f1_score_global", "recall_clase_riesgo_alto"]


def test_nombre_version_cabe_en_varchar_40_con_el_tipo_y_componente_mas_largos():
    from src.shared.tipo_modelo import COMPONENTES_POBLACIONAL, PARADIGMA_POR_TIPO_MODELO, es_poblacional

    for tipo in PARADIGMA_POR_TIPO_MODELO:
        for componente in (COMPONENTES_POBLACIONAL if es_poblacional(tipo) else (None,)):
            assert len(_version(tipo, componente).nombre_version) <= 40, (tipo, componente)
