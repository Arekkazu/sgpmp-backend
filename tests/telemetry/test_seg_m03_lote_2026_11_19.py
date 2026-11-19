# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-19 | Arekkazu | SEG-M03-01/03: reintento de la auditoría IoT y límites del cuerpo de ingesta |
"""SEG-M03-01: un evento de auditoría que falla se reintenta y no se pierde sin rastro.
SEG-M03-03: el cuerpo de ingesta y el vector de visión tienen tope."""
from dataclasses import replace
from unittest.mock import Mock
from uuid import uuid4

import pytest
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from src.shared.error_handlers import register_error_handlers
from src.telemetry.application.use_cases.auditoria import registrar_evento_auditoria_iot_use_case as auditoria
from src.telemetry.domain.entities.evento_auditoria_iot import ComponenteOrigen, TipoResultado
from src.telemetry.infrastructure.dto.ingerir_observaciones_vision_dto import ObservacionVisionDTO
from src.telemetry.infrastructure.routers.ruta_ingesta_auditada import LIMITE_CUERPO_BYTES, RutaIngestaAuditada


class _BitacoraIntermitente:
    def __init__(self):
        self.caida, self.guardados = True, []

    def registrar(self, evento):
        if self.caida:
            raise RuntimeError("bitácora caída")
        self.guardados.append(evento.tipo_evento)
        return replace(evento, id_evento=uuid4())


def test_evento_que_falla_se_reintenta_al_siguiente_registro(monkeypatch, caplog):
    monkeypatch.setattr(auditoria, "_PENDIENTES", auditoria.deque(maxlen=10))
    bitacora = _BitacoraIntermitente()
    caso = auditoria.RegistrarEventoAuditoriaIotUseCase(Mock(), bitacora)
    caso.execute("PRIMERO", TipoResultado.EXITOSO, ComponenteOrigen.RF53)
    assert len(auditoria._PENDIENTES) == 1 and "PRIMERO" in caplog.text
    assert any(r.levelname == "ERROR" for r in caplog.records)
    bitacora.caida = False
    caso.execute("SEGUNDO", TipoResultado.EXITOSO, ComponenteOrigen.RF53)
    assert bitacora.guardados == ["SEGUNDO", "PRIMERO"] and not auditoria._PENDIENTES


def test_cuerpo_de_ingesta_sobre_el_limite_responde_413_antes_del_endpoint():
    llamado = Mock()
    router = APIRouter(prefix="/iot/telemetria", route_class=RutaIngestaAuditada)
    router.add_api_route("/eco", lambda cuerpo: llamado(), methods=["POST"])  # el cuerpo no se llega a leer
    app = FastAPI()
    app.include_router(router)
    register_error_handlers(app)
    respuesta = TestClient(app).post("/iot/telemetria/eco", content=b"x" * (LIMITE_CUERPO_BYTES + 1))
    assert respuesta.status_code == 413 and respuesta.json()["error_code"] == "CUERPO_DEMASIADO_GRANDE"
    llamado.assert_not_called()


def test_vector_de_vision_acotado():
    base = dict(timestamp_captura="2026-11-19T10:00:00Z", cobertura_ventana="0.5", n_tracks=1, n_tracks_perdidos=0,
                fps_efectivo="10", estado_calibracion="CALIBRADO")
    ObservacionVisionDTO(**base, vector={f"c{i}": 1.0 for i in range(32)})
    for vector in ({f"c{i}": 1.0 for i in range(33)}, {"x" * 65: 1.0}):
        with pytest.raises(ValidationError):
            ObservacionVisionDTO(**base, vector=vector)
