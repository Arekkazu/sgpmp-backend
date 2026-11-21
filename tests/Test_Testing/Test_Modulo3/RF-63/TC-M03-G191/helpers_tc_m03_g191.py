"""Helpers y fixtures para TC-M03-G191. NO ejecuta, solo construye."""

from datetime import datetime, timezone
from src.telemetry.application.use_cases.auditoria.registrar_evento_auditoria_iot_use_case import (
    RegistrarEventoAuditoriaIotUseCase,
)
from src.telemetry.infrastructure.repositories.bitacora_auditoria_iot_repository import (
    SqlAlchemyBitacoraAuditoriaIotRepository,
)
from src.telemetry.infrastructure.models.bitacora_auditoria_iot_model import (
    BitacoraAuditoriaIotModel,
)
from src.telemetry.domain.entities.evento_auditoria_iot import (
    TipoResultado,
    SeveridadLog,
    ComponenteOrigen,
    EntidadAfectadaTipo,
)


def construir_use_case(db_session):
    """Instancia el use case con repositorios reales."""
    repo = SqlAlchemyBitacoraAuditoriaIotRepository(db_session)
    return RegistrarEventoAuditoriaIotUseCase(db=db_session, auditoria_repo=repo)


def payload_base_completo():
    """Payload minimo completo para evento 367d."""
    return {
        "tipo_evento": "TELEMETRIA_VALIDADA",
        "resultado": TipoResultado.EXITOSO,
        "componente_origen": ComponenteOrigen.RF53,
        "severidad_log": SeveridadLog.INFO,
        "descripcion": "Evento de prueba QA",
        "entidad_afectada_tipo": EntidadAfectadaTipo.LECTURA,
        "entidad_afectada_id": "test-123",
        "accion_detallada": {"origen": "test_tc_m03_g191"},
        "registro_incompleto": False,
    }


def buscar_evento_por_descripcion(db_session, descripcion):
    """Helper: busca un evento por descripcion en la BD."""
    return db_session.query(BitacoraAuditoriaIotModel).filter_by(
        descripcion=descripcion
    ).first()
