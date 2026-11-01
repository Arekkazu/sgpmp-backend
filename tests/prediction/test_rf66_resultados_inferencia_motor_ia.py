# | Fecha      | Nombre   | Que se hizo                                                     |
# |------------|----------|-----------------------------------------------------------------|
# | 2026-10-30 | Arekkazu | RF-66: el motor IA registra resultados en el backend             |
# | 2026-10-30 | Arekkazu | RF-66: patología base por código RF-64                           |
# | 2026-10-31 | Arekkazu | RFC-010 RF-69: llave con animal, SOMBRA y fuente_datos en los dobles |
"""RF-66: ``POST /prediccion/inferencias`` — el motor IA entrega sus resultados."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.prediction.application.use_cases.inferencia.registrar_resultado_inferencia_use_case import (
    RegistrarResultadoInferenciaUseCase,
    ResultadoRegistro,
)
from src.prediction.domain.entities.resultado_inferencia import ResultadoInferencia
from src.prediction.infrastructure.dto.registrar_resultado_inferencia_dto import RegistrarResultadoInferenciaDTO
from src.prediction.infrastructure.routers import monitor_prediccion_router
from src.shared.database import get_db_sistema
from src.shared.error_handlers import register_error_handlers
from src.shared.errors import BusinessRuleError, NotFoundError

TOKEN = "token-motor-de-prueba"


def _cuerpo(**cambios) -> dict:
    cuerpo = {
        "id_resultado_inferencia": str(uuid.uuid4()),
        "id_activo_biologico": 885,
        "tipo_modelo": "MODELO_ESPECIES_GRANDES",
        "id_version_modelo": 12,
        "nivel_riesgo": 0,
        "probabilidad_riesgo": {"0": 0.762, "1": 0.1, "2": 0.08, "3": 0.058},
        "probabilidad_enfermedad": {"0": 0.762, "6": 0.0736, "7": 0.086},
        "confianza_global": "0.762",
        "contexto_incompleto": False,
        "modo_ejecucion": "SERVIDOR",
        "latencia_ms": 50,
        "fecha_inicio_ventana": "2026-09-20T14:50:00+00:00",
        "fecha_fin_ventana": "2026-09-20T15:00:00+00:00",
        "fecha_inferencia": "2026-10-25T20:30:49+00:00",
        "modo_sombra": True,
    }
    cuerpo.update(cambios)
    return cuerpo


def _use_case(*, existente=None, llave=("APROBADO", "MODELO_ESPECIES_GRANDES", None, None), especie=4):
    repo = Mock()
    repo.obtener.return_value = existente
    version = Mock()
    version.obtener_llave.return_value = llave
    activo = Mock()
    activo.obtener_especie.return_value = especie
    auditoria = Mock()
    db = Mock()
    patologias = Mock()
    patologias.id_base_por_codigo_rf64.side_effect = lambda codigo: {6: 13}.get(codigo)
    use_case = RegistrarResultadoInferenciaUseCase(
        db=db, repo=repo, version_port=version, activo_port=activo, auditoria_repo=auditoria,
        patologia_repo=patologias,
    )
    return use_case, repo, auditoria, db


def _dto(**cambios) -> RegistrarResultadoInferenciaDTO:
    return RegistrarResultadoInferenciaDTO(**_cuerpo(**cambios))


def test_registra_en_sombra_con_especie_del_activo_y_audita():
    use_case, repo, auditoria, db = _use_case()
    registro = use_case.execute(_dto())
    assert not registro.duplicado
    guardado = repo.guardar.call_args.args[0]
    assert (guardado.id_especie, guardado.modo_sombra, guardado.latencia_excedida) == (4, True, False)
    assert [c.kwargs["tipo_evento"] for c in auditoria.registrar.call_args_list] == ["INFERENCIA_EJECUTADA"]
    evento = auditoria.registrar.call_args.kwargs
    assert (evento["tipo_actor"], evento["id_sistema"], evento["origen_dato"]) == ("SISTEMA", "MOTOR_IA", "BACKEND")
    assert evento["payload_evento"]["probabilidad_riesgo_alto"] == 0.058
    db.commit.assert_called_once()


def test_latencia_sobre_2s_queda_marcada_y_auditada():
    use_case, repo, auditoria, _ = _use_case()
    use_case.execute(_dto(latencia_ms=2001))
    assert repo.guardar.call_args.args[0].latencia_excedida is True
    tipos = [c.kwargs["tipo_evento"] for c in auditoria.registrar.call_args_list]
    assert tipos == ["INFERENCIA_EJECUTADA", "LATENCIA_EXCEDIDA"]


def test_mismo_id_devuelve_el_guardado_sin_escribir():
    existente = Mock(spec=ResultadoInferencia)
    use_case, repo, auditoria, db = _use_case(existente=existente)
    registro = use_case.execute(_dto(modo_sombra=False))  # ni siquiera se revalida
    assert registro == ResultadoRegistro(existente, duplicado=True)
    repo.guardar.assert_not_called()
    auditoria.registrar.assert_not_called()
    db.commit.assert_not_called()


@pytest.mark.parametrize(
    ("kwargs_uc", "cambios", "error", "codigo"),
    [
        ({}, {"modo_sombra": False}, BusinessRuleError, "INFERENCIA_VINCULANTE_NO_DISPONIBLE"),
        ({"llave": None}, {}, NotFoundError, "VERSION_MODELO_NO_ENCONTRADA"),
        ({"llave": ("DEPRECADO", "MODELO_ESPECIES_GRANDES", None, None)}, {}, BusinessRuleError, "VERSION_MODELO_NO_UTILIZABLE"),
        ({"llave": ("ACTIVO", "MODELO_AVES", None, None)}, {}, BusinessRuleError, "TIPO_MODELO_NO_COINCIDE"),
        ({"especie": None}, {}, NotFoundError, "ACTIVO_NO_ENCONTRADO"),
    ],
)
def test_rechazos_no_persisten(kwargs_uc, cambios, error, codigo):
    use_case, repo, _, db = _use_case(**kwargs_uc)
    with pytest.raises(error) as exc:
        use_case.execute(_dto(**cambios))
    assert exc.value.code == codigo
    repo.guardar.assert_not_called()
    db.commit.assert_not_called()


@pytest.mark.parametrize(("cambios", "id_esperado"), [
    ({"codigo_patologia_rf64": 6}, 13),                      # el motor no conoce el id del ambiente
    ({"codigo_patologia_rf64": 6, "id_patologia": 99}, 99),  # si viene el id, manda el id
    ({"codigo_patologia_rf64": 5}, None),                    # sin base con ese código: se guarda igual
    ({}, None),
])
def test_patologia_por_codigo_rf64(cambios, id_esperado):
    use_case, repo, _, _ = _use_case()
    use_case.execute(_dto(**cambios))
    assert repo.guardar.call_args.args[0].id_patologia == id_esperado


def test_falla_al_guardar_hace_rollback():
    use_case, repo, _, db = _use_case()
    repo.guardar.side_effect = RuntimeError("bd caída")
    with pytest.raises(RuntimeError):
        use_case.execute(_dto())
    db.rollback.assert_called_once()
    db.commit.assert_not_called()


# ── Router ────────────────────────────────────────────────────────────────


@pytest.fixture
def cliente(monkeypatch):
    monkeypatch.setenv("IOT_INFERENCIA_M04_TOKEN", TOKEN)
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(monitor_prediccion_router.router)
    app.dependency_overrides[get_db_sistema] = lambda: Mock()
    return TestClient(app)


def _fijar_registro(monkeypatch, *, duplicado: bool):
    resultado = ResultadoInferencia(
        id_resultado_inferencia=uuid.uuid4(), id_activo_biologico=885, tipo_modelo="MODELO_ESPECIES_GRANDES",
        id_version_modelo=12, nivel_riesgo=0, probabilidad_riesgo={}, probabilidad_enfermedad={},
        confianza_global=0, contexto_incompleto=False, modo_ejecucion="SERVIDOR", modo_sombra=True,
        fecha_inferencia=datetime.now(timezone.utc), latencia_ms=2500,
    )
    fake = Mock()
    fake.return_value.execute.return_value = ResultadoRegistro(resultado, duplicado=duplicado)
    monkeypatch.setattr(monitor_prediccion_router, "RegistrarResultadoInferenciaUseCase", fake)
    return resultado


def _auth(token: str = TOKEN) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.parametrize(("duplicado", "status"), [(False, 201), (True, 200)])
def test_post_201_nuevo_200_duplicado(cliente, monkeypatch, duplicado, status):
    resultado = _fijar_registro(monkeypatch, duplicado=duplicado)
    r = cliente.post("/prediccion/inferencias", json=_cuerpo(), headers=_auth())
    assert r.status_code == status, r.text
    assert r.json() == {
        "id_resultado_inferencia": str(resultado.id_resultado_inferencia),
        "duplicado": duplicado,
        "modo_sombra": True,
        "latencia_excedida": True,
        "tiene_alerta_generada": False,
    }


@pytest.mark.parametrize("headers", [{}, _auth("otro"), {"Authorization": TOKEN}])
def test_post_sin_token_valido_401(cliente, monkeypatch, headers):
    _fijar_registro(monkeypatch, duplicado=False)
    r = cliente.post("/prediccion/inferencias", json=_cuerpo(), headers=headers)
    assert (r.status_code, r.json()["error_code"]) == (401, "TOKEN_SERVICIO_INVALIDO")


def test_post_sin_token_configurado_503(cliente, monkeypatch):
    monkeypatch.setenv("IOT_INFERENCIA_M04_TOKEN", "")
    r = cliente.post("/prediccion/inferencias", json=_cuerpo(), headers=_auth())
    assert (r.status_code, r.json()["error_code"]) == (503, "TOKEN_SERVICIO_NO_CONFIGURADO")


@pytest.mark.parametrize(
    "cambios",
    [
        {"nivel_riesgo": 4},
        {"confianza_global": "1.5"},
        {"probabilidad_riesgo": {}},
        {"probabilidad_enfermedad": {"0": 1.2}},
        {"tipo_modelo": "MODELO_INVENTADO"},
        {"codigo_patologia_rf64": 8},
        {"modo_ejecucion": "NUBE"},
        {"fecha_fin_ventana": "2026-09-20T14:00:00+00:00"},
    ],
)
def test_post_cuerpo_invalido_no_llega_al_caso_de_uso(cliente, monkeypatch, cambios):
    _fijar_registro(monkeypatch, duplicado=False)
    r = cliente.post("/prediccion/inferencias", json=_cuerpo(**cambios), headers=_auth())
    assert r.status_code in (400, 422), r.text
    monitor_prediccion_router.RegistrarResultadoInferenciaUseCase.return_value.execute.assert_not_called()
