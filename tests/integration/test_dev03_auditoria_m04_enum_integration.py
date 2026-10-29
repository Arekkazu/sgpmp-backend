"""DEV-03 contra Postgres real: las consultas M04 dejan su evento en eventos_auditoria_m04.

Antes, los tres GET (historial, ota-status, despliegues) emitían un ``tipo_evento``
y un ``resultado_operacion`` fuera de sus enums: el flush fallaba, el repositorio
se lo tragaba y el ``commit`` del use case respondía 500 en toda consulta válida.
Acá corren los use cases con los repositorios SQLAlchemy reales; solo los puertos
que no tocan la auditoría (acceso al activo, existencia de la versión) son fakes.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.prediction.application.use_cases.auditoria.consultar_auditoria_m04_use_case import ConsultarAuditoriaM04UseCase
from src.prediction.application.use_cases.auditoria.exportar_auditoria_m04_use_case import ExportarAuditoriaM04UseCase
from src.prediction.application.use_cases.historial_diagnostico.consultar_historial_use_case import ConsultarHistorialUseCase
from src.prediction.application.use_cases.ota.consultar_ota_status_use_case import ConsultarOtaStatusUseCase
from src.prediction.application.use_cases.ota.listar_despliegues_use_case import ListarDesplieguesUseCase
from src.prediction.infrastructure.repositories.despliegue_ota_repository import SqlAlchemyDespliegueOtaRepository
from src.prediction.infrastructure.repositories.evento_auditoria_m04_repository import (
    SqlAlchemyEventoAuditoriaM04Repository,
)
from src.prediction.infrastructure.repositories.historial_diagnostico_repository import (
    SqlAlchemyHistorialDiagnosticoRepository,
)
from tests.prediction.test_dev03_auditoria_m04_enum import RESULTADOS_OPERACION_M04, TIPOS_EVENTO_M04


class _ActivoAccesible:
    def activo_existe_y_accesible(self, *_a): return True


class _VersionExiste:
    def obtener_estado(self, _id): return "ACTIVO"


def _valores_enum(db: Session, nombre: str) -> set[str]:
    return set(db.execute(
        text(
            "SELECT e.enumlabel FROM pg_enum e JOIN pg_type t ON t.oid = e.enumtypid "
            "JOIN pg_namespace n ON n.oid = t.typnamespace "
            "WHERE n.nspname = 'modulo4' AND t.typname = :nombre"
        ),
        {"nombre": nombre},
    ).scalars())


@pytest.fixture
def id_usuario(db_session: Session) -> int:
    id_ = db_session.execute(text("SELECT min(id_usuario) FROM modulo1.usuarios")).scalar()
    if id_ is None:
        pytest.skip("La base de pruebas no tiene usuarios para fk_eam_usuario.")
    return id_


def _eventos(db: Session, tipo_evento: str, clave: str, valor: str) -> int:
    return db.execute(
        text(
            "SELECT count(*) FROM modulo4.eventos_auditoria_m04 "
            "WHERE tipo_evento = CAST(:tipo AS modulo4.enum_tipo_evento_auditoria_m04) "
            "AND resultado_operacion = 'EXITOSO' AND payload_evento ->> :clave = :valor"
        ),
        {"tipo": tipo_evento, "clave": clave, "valor": valor},
    ).scalar_one()


def test_las_copias_de_los_enums_coinciden_con_la_base(db_session: Session):
    assert _valores_enum(db_session, "enum_tipo_evento_auditoria_m04") == TIPOS_EVENTO_M04
    assert _valores_enum(db_session, "enum_resultado_operacion_auditoria") == RESULTADOS_OPERACION_M04


def test_historial_diagnostico_deja_su_evento(db_session: Session, id_usuario: int):
    hoy = date.today()
    ConsultarHistorialUseCase(
        db=db_session,
        repo=SqlAlchemyHistorialDiagnosticoRepository(db_session),
        auditoria_repo=SqlAlchemyEventoAuditoriaM04Repository(db_session),
        activo_port=_ActivoAccesible(),
    ).execute(
        id_activo_biologico=-1, fecha_inicio=hoy - timedelta(days=7), fecha_fin=hoy, nivel_riesgo=None,
        id_patologia=None, incluir_alertas=False, cursor_paginacion=None, id_usuario=id_usuario, id_rol=1,
    )
    assert _eventos(db_session, "HISTORIAL_CONSULTADO", "consulta", "HISTORIAL_DIAGNOSTICO") == 1


def test_ota_status_deja_su_evento(db_session: Session, id_usuario: int):
    ConsultarOtaStatusUseCase(
        db=db_session,
        repo=SqlAlchemyDespliegueOtaRepository(db_session),
        auditoria_repo=SqlAlchemyEventoAuditoriaM04Repository(db_session),
        version_port=_VersionExiste(),
    ).execute(id_version=-1, id_dispositivo=None, estado=None, id_usuario=id_usuario)
    assert _eventos(db_session, "HISTORIAL_CONSULTADO", "consulta", "OTA_STATUS") == 1


def test_despliegues_deja_su_evento(db_session: Session, id_usuario: int):
    ListarDesplieguesUseCase(
        db=db_session,
        repo=SqlAlchemyDespliegueOtaRepository(db_session),
        auditoria_repo=SqlAlchemyEventoAuditoriaM04Repository(db_session),
        version_port=_VersionExiste(),
    ).execute(id_version=None, id_dispositivo=None, estado=None, limit=20, offset=0, id_usuario=id_usuario)
    assert _eventos(db_session, "HISTORIAL_CONSULTADO", "consulta", "DESPLIEGUES_OTA") == 1


def test_consultar_y_exportar_auditoria_dejan_su_evento(db_session: Session, id_usuario: int):
    repo = SqlAlchemyEventoAuditoriaM04Repository(db_session)
    filtros = dict(
        tipo_evento=None, fecha_desde=None, fecha_hasta=None, id_usuario=None,
        id_sistema=None, id_referencia=None, severidad_evento=None,
    )
    ConsultarAuditoriaM04UseCase(db_session, repo).listar(
        **filtros, pagina=1, por_pagina=10, id_usuario_consultor=id_usuario,
    )
    ExportarAuditoriaM04UseCase(db_session, repo).exportar(
        **filtros, formato="json", id_usuario_exportador=id_usuario,
    )
    assert _eventos(db_session, "HISTORIAL_CONSULTADO", "consulta", "AUDITORIA_M04") == 1
    assert _eventos(db_session, "EXPORTACION_GENERADA", "exportacion", "AUDITORIA_M04") == 1
