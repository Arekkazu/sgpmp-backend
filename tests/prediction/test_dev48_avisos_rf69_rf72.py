# | Fecha      | Nombre       | Que se hizo                                           |
# |------------|--------------|-------------------------------------------------------|
# | 2026-10-23 | destroyerban | DEV-48 RF-69/72: avisos e incidente de persistencia   |
# | 2026-10-23 | Arekkazu | DEV-48: el aviso al Administrador usa E sobre auditoria_m04 |
"""DEV-48: avisos de RF-69 (E1b carga externa, E3 versión rechazada) e incidente de RF-72 E8.

Fakes en memoria, sin DB ni SMTP: el envío se intercepta en el adaptador.
"""
from __future__ import annotations

import hashlib
import io
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src.prediction.application.use_cases.retroalimentacion.registrar_retroalimentacion_use_case import (
    RegistrarRetroalimentacionUseCase,
)
from src.prediction.application.use_cases.versiones_modelo.registrar_version_modelo_use_case import (
    RegistrarVersionModeloUseCase,
)
from src.prediction.infrastructure.adapters import aviso_version_modelo_email_adapter as adapter_module
from src.prediction.infrastructure.dto.registrar_retroalimentacion_dto import RegistrarRetroalimentacionDTO
from src.shared.errors import AuthorizationError, ConflictError, InfrastructureError

CLAVE = "clave-rf71"
ARTEFACTO = b"\x08\x01modelo-onnx"
SHA = hashlib.sha256(ARTEFACTO).hexdigest()


class _Db:
    def __init__(self, falla_commit=False):
        self.commits = self.rollbacks = 0
        self.falla_commit = falla_commit

    def commit(self):
        if self.falla_commit:
            self.falla_commit = False  # solo falla el commit de la retroalimentación
            raise RuntimeError("conexión perdida")
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


class _Auditoria:
    def __init__(self, intentos_en_ventana=1, falla=False):
        self.eventos, self.intentos_en_ventana, self.falla = [], intentos_en_ventana, falla

    def registrar(self, **kw):
        if self.falla:
            raise RuntimeError("bitácora caída")
        self.eventos.append(kw)

    def consultar(self, **kw):
        return [], self.intentos_en_ventana


# --- RF-69 E1b y E3 ----------------------------------------------------------------------

def _registrador(aviso, auditoria=None, repo=None):
    return RegistrarVersionModeloUseCase(
        db=_Db(), repo=repo, auditoria_repo=auditoria or _Auditoria(), variable_port=Mock(), aviso_port=aviso,
    )


def _dto(f1="0.95"):
    return SimpleNamespace(
        tipo_modelo="MODELO_ESPECIES_GRANDES", hash_artefacto_sha256=SHA, dataset_entrenamiento_hash=SHA,
        metricas_validacion={
            "f1_score_global": f1, "recall_clase_riesgo_alto": "0.95", "precision_global": "0.9",
            "accuracy": "0.9", "roc_auc_score": "0.9", "recall_por_clase": {}, "matriz_confusion": [[1]],
        },
        fecha_entrenamiento=datetime(2026, 10, 1, tzinfo=timezone.utc), compatibilidad_variables=[],
        id_proceso_rf71=uuid.uuid4(), version_referencia=None, componente=None,
        archivo_modelo=SimpleNamespace(file=io.BytesIO(ARTEFACTO)),
    )


@pytest.fixture
def clave(monkeypatch, tmp_path):
    monkeypatch.setenv("RF71_INTERNAL_KEY", CLAVE)
    monkeypatch.setenv("MODELOS_STORAGE_PATH", str(tmp_path))


def test_e1b_carga_externa_avisa_al_administrador(clave):
    aviso, auditoria = Mock(), _Auditoria()
    dto = _dto()
    with pytest.raises(AuthorizationError):
        _registrador(aviso, auditoria).execute(dto, internal_key="otra")
    assert auditoria.eventos[0]["tipo_evento"] == "INTENTO_CARGA_MODELO_EXTERNO"
    aviso.avisar_carga_externa.assert_called_once_with(
        id_proceso_rf71=str(dto.id_proceso_rf71), motivo="X-RF71-Internal-Key ausente o incorrecta",
    )


def test_e1b_intentos_repetidos_en_la_ventana_no_vuelven_a_avisar(clave):
    aviso = Mock()
    with pytest.raises(AuthorizationError):
        _registrador(aviso, _Auditoria(intentos_en_ventana=3)).execute(_dto(), internal_key=None)
    aviso.avisar_carga_externa.assert_not_called()


def test_e1b_si_el_aviso_falla_igual_responde_403(clave):
    aviso = Mock()
    aviso.avisar_carga_externa.side_effect = RuntimeError("smtp caído")
    with pytest.raises(AuthorizationError):
        _registrador(aviso).execute(_dto(), internal_key="otra")


def _repo_versiones():
    repo = Mock()
    repo.guardar.side_effect = lambda e: (setattr(e, "id_version_modelo", 9), e)[1]
    return repo


@pytest.mark.parametrize("f1, avisa", [("0.50", True), ("0.95", False)])
def test_e3_version_rechazada_avisa_al_veterinario(clave, f1, avisa):
    aviso = Mock()
    version = _registrador(aviso, repo=_repo_versiones()).execute(_dto(f1=f1), internal_key=CLAVE)
    assert version.estado_version == ("RECHAZADO" if avisa else "APROBADO")
    if avisa:
        aviso.avisar_version_rechazada.assert_called_once_with(version)
    else:
        aviso.avisar_version_rechazada.assert_not_called()
    aviso.avisar_carga_externa.assert_not_called()


def test_e3_si_el_aviso_falla_la_version_queda_registrada(clave):
    aviso = Mock()
    aviso.avisar_version_rechazada.side_effect = RuntimeError("smtp caído")
    version = _registrador(aviso, repo=_repo_versiones()).execute(_dto(f1="0.50"), internal_key=CLAVE)
    assert version.estado_version == "RECHAZADO" and version.id_version_modelo == 9


# --- Adaptador de correo (canal RF-14) ---------------------------------------------------

class _DbDestinatarios:
    def __init__(self, filas):
        self.filas, self.parametros = filas, []

    def execute(self, sql, parametros):
        self.parametros.append(parametros)
        return SimpleNamespace(fetchall=lambda: self.filas)


def _fila(id_usuario, correo, nombre="Ana", apellidos="Ruiz"):
    return SimpleNamespace(id_usuario=id_usuario, nombre=nombre, apellidos=apellidos, correo_electronico=correo)


@pytest.fixture
def identidades(monkeypatch):
    """Registra cada búsqueda hecha con la identidad de servicio (RLS forzada en modulo1)."""
    usadas = []

    @contextmanager
    def como_sistema(db):
        usadas.append(db)
        yield

    monkeypatch.setattr(adapter_module, "como_sistema", como_sistema)
    return usadas


def test_adaptador_resuelve_destinatarios_por_permiso_y_envia(monkeypatch, identidades):
    enviados = []
    monkeypatch.setattr(adapter_module, "send_email", lambda **kw: enviados.append(kw))
    db = _DbDestinatarios([_fila(1, "admin@x.co"), _fila(2, None)])
    aviso = adapter_module.AvisoVersionModeloEmailAdapter(db)

    aviso.avisar_carga_externa(id_proceso_rf71="p-1", motivo="clave incorrecta")
    version = SimpleNamespace(nombre_version="GRANDES_v9", tipo_modelo="MODELO_ESPECIES_GRANDES",
                              componente=None, detalle_validacion="f1_score_global=0.50 < umbral requerido 0.80")
    aviso.avisar_version_rechazada(version)

    # E1b: auditoría M04 (46, E) → Administrador (el Veterinario tiene R desde DB-08).
    # E3: versión de modelo (43, U) → Veterinario.
    assert [(p["id_recurso"], p["id_accion"]) for p in db.parametros] == [(46, 5), (43, 3)]
    assert all(p["correo_servicio"] == "servicio.sistema@sgpmp.local" for p in db.parametros)
    assert identidades == [db, db]  # sin usuario en sesión: identidad de servicio
    assert [c["to"] for c in enviados] == ["admin@x.co", "admin@x.co"]  # sin correo no se envía
    assert all(c["intentos"] == 1 for c in enviados)  # RF-14: sin reintentos
    assert "p-1" in enviados[0]["html_body"] and "INTENTO_CARGA_MODELO_EXTERNO" in enviados[0]["html_body"]
    assert "GRANDES_v9" in enviados[1]["subject"] and "f1_score_global=0.50" in enviados[1]["html_body"]


def test_adaptador_nunca_propaga_un_fallo_de_envio(monkeypatch, identidades):
    def falla(**kw):
        raise ConnectionError("smtp caído")

    monkeypatch.setattr(adapter_module, "send_email", falla)
    aviso = adapter_module.AvisoVersionModeloEmailAdapter(_DbDestinatarios([_fila(1, "admin@x.co")]))
    aviso.avisar_carga_externa(id_proceso_rf71="p-1", motivo="m")  # no lanza


# --- RF-72 E8 ----------------------------------------------------------------------------

def _retro(db, auditoria, guardar):
    resultados = Mock()
    resultados.obtener_por_id.return_value = {
        "fecha_inferencia": datetime.now(timezone.utc) - timedelta(days=1), "id_activo_biologico": 11,
    }
    repo = Mock()
    repo.obtener_por_resultado_y_usuario.return_value = None
    repo.listar_por_resultado.return_value = []
    repo.guardar.side_effect = guardar
    parametros = Mock()
    parametros.obtener.return_value = {}
    return RegistrarRetroalimentacionUseCase(db=db, repo=repo, resultado_port=resultados, patologia_repo=Mock(),
                                             auditoria_repo=auditoria, parametros_port=parametros)


def _retro_dto():
    return RegistrarRetroalimentacionDTO(id_resultado_inferencia=uuid.uuid4(), id_activo_biologico=11,
                                         estado_retroalimentacion="CORRECTO")


def _guardar_ok(entidad):
    entidad.id_retroalimentacion = uuid.uuid4()
    return entidad


def _falla_infra(entidad):
    raise InfrastructureError(code="ERROR_INTERNO", message="db")


@pytest.mark.parametrize("db, guardar", [(_Db(), _falla_infra), (_Db(falla_commit=True), _guardar_ok)],
                         ids=["falla_guardar", "falla_commit"])
def test_e8_error_de_persistencia_registra_incidente_y_responde_500(monkeypatch, db, guardar):
    monkeypatch.setattr(
        "src.prediction.application.use_cases.retroalimentacion.registrar_retroalimentacion_use_case.numero_configurado",
        lambda *a, **kw: 30,
    )
    auditoria, dto = _Auditoria(), _retro_dto()
    with pytest.raises(InfrastructureError) as exc:
        _retro(db, auditoria, guardar).execute(dto, id_usuario_veterinario=5)
    assert exc.value.status_code == 500
    assert exc.value.code == "ERROR_PERSISTENCIA_RETROALIMENTACION"
    assert exc.value.message == "Error interno al registrar la retroalimentación."
    [incidente] = auditoria.eventos
    assert incidente["resultado_operacion"] == "FALLIDO" and incidente["severidad_evento"] == "ERROR"
    assert incidente["codigo_error"] == "ERROR_PERSISTENCIA_RETROALIMENTACION"
    assert incidente["payload_evento"]["id_resultado_inferencia"] == str(dto.id_resultado_inferencia)
    assert incidente["payload_evento"]["id_usuario_veterinario"] == 5
    assert db.commits == 1  # el del incidente


def test_e8_si_la_bitacora_tambien_falla_igual_responde_500(monkeypatch):
    monkeypatch.setattr(
        "src.prediction.application.use_cases.retroalimentacion.registrar_retroalimentacion_use_case.numero_configurado",
        lambda *a, **kw: 30,
    )
    with pytest.raises(InfrastructureError):
        _retro(_Db(), _Auditoria(falla=True), _falla_infra).execute(_retro_dto(), id_usuario_veterinario=5)


def test_un_rechazo_por_el_dato_no_es_incidente(monkeypatch):
    monkeypatch.setattr(
        "src.prediction.application.use_cases.retroalimentacion.registrar_retroalimentacion_use_case.numero_configurado",
        lambda *a, **kw: 30,
    )

    def duplicado(entidad):
        raise ConflictError(code="RECURSO_DUPLICADO", message="duplicado")

    auditoria = _Auditoria()
    with pytest.raises(ConflictError):
        _retro(_Db(), auditoria, duplicado).execute(_retro_dto(), id_usuario_veterinario=5)
    assert auditoria.eventos == []
