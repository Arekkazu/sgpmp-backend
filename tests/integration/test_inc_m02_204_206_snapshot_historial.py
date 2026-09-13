"""INC-M02-G08 / INC-M02-46-G13: el snapshot inicial (RF-33) no aparecía en el
historial consultable (RF-46).

Causa raíz: `RegistrarActivoBiologicoUseCase` sí escribía el Evento 0 en
`modulo2.historial_activos`, pero `ConsultarHistorialUseCase` leía el
historial exclusivamente desde `SqlAlchemyTransferenciaRepository`, que nunca
consultaba esa tabla (solo vistas de RF-46 y `movimientos`). Escritura y
lectura vivían desconectadas.

Esta prueba registra un activo poblacional real contra PostgreSQL y verifica
que el historial consolidado (la misma consulta que usa el endpoint
GET /activos-biologicos/{id}/historial) incluye el snapshot CREACION con los
valores iniciales exigidos por el issue.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.biological_assets.application.use_cases.registro.registrar_activo_use_case import (
    RegistrarActivoBiologicoUseCase,
)
from src.biological_assets.infrastructure.adapters.especie_m09_adapter import EspecieM09Adapter
from src.biological_assets.infrastructure.adapters.infraestructura_m09_adapter import InfraestructuraM09Adapter
from src.biological_assets.infrastructure.adapters.parametros_especie_m09_adapter import ParametrosEspecieM09Adapter
from src.biological_assets.infrastructure.dto.registrar_activo_dto import RegistrarActivoBiologicoDTO
from src.biological_assets.infrastructure.repositories.activo_biologico_repository import (
    SqlAlchemyActivoBiologicoRepository,
)
from src.biological_assets.infrastructure.repositories.transferencia_repository import (
    SqlAlchemyTransferenciaRepository,
)
from src.identity_access.infrastructure.dependencies import UsuarioActual

pytestmark = pytest.mark.integration


@pytest.fixture
def especie_e_infra_activas(db_session: Session, crear_usuario_db) -> tuple[int, int]:
    especie = db_session.execute(
        text("SELECT id_especie FROM modulo9.especies WHERE es_activo ORDER BY id_especie LIMIT 1")
    ).first()
    if especie is None:
        pytest.skip("Se requiere al menos una especie activa en modulo9.")

    infra = db_session.execute(
        text("SELECT id_infraestructura FROM modulo9.infraestructuras WHERE es_activo ORDER BY id_infraestructura LIMIT 1")
    ).first()
    if infra is not None:
        return especie[0], infra[0]

    # La base de pruebas no trae fincas/infraestructuras sembradas: se crean
    # aquí, dentro de la misma transacción de la prueba (se revierte sola).
    dueno = crear_usuario_db()
    id_finca = db_session.execute(
        text(
            "INSERT INTO modulo9.fincas (nombre, ubicacion, tamano_h, fecha_actualizacion, fecha_creacion, id_usuario, es_activo) "
            "VALUES (:nombre, '{}'::jsonb, 10, now(), now(), :id_usuario, true) "
            "RETURNING id_finca"
        ),
        {"nombre": "Finca Prueba Integracion", "id_usuario": dueno["id_usuario"]},
    ).scalar_one()
    id_infra = db_session.execute(
        text(
            "INSERT INTO modulo9.infraestructuras (nombre, id_finca, superficie, es_activo, tipo) "
            "VALUES (:nombre, :id_finca, 500, true, 'Estanque') "
            "RETURNING id_infraestructura"
        ),
        {"nombre": "Infraestructura Prueba Integracion", "id_finca": id_finca},
    ).scalar_one()
    db_session.flush()
    return especie[0], id_infra


def test_snapshot_inicial_poblacional_aparece_en_historial_consolidado(
    db_session: Session,
    especie_e_infra_activas: tuple[int, int],
    crear_usuario_db,
) -> None:
    id_especie, id_infraestructura = especie_e_infra_activas
    usuario_db = crear_usuario_db()
    usuario = UsuarioActual(id_usuario=usuario_db["id_usuario"], id_token=1, id_rol=usuario_db["id_rol"])

    use_case = RegistrarActivoBiologicoUseCase(
        db=db_session,
        repo=SqlAlchemyActivoBiologicoRepository(db_session),
        especie_port=EspecieM09Adapter(db_session),
        infra_port=InfraestructuraM09Adapter(db_session),
        parametros_port=ParametrosEspecieM09Adapter(db_session),
    )
    dto = RegistrarActivoBiologicoDTO(
        tipo_activo="POBLACIONAL",
        id_especie=id_especie,
        fecha_inicio_ciclo=date(2024, 1, 1),
        origen_financiero="nacimiento",
        id_infraestructura=id_infraestructura,
        cantidad_inicial=10,
        peso_promedio_inicial=Decimal("2.5"),
    )

    activo = use_case.execute(dto, usuario)
    assert activo.id_activo_biologico is not None

    pagina = SqlAlchemyTransferenciaRepository(db_session).consultar_historial(
        id_activo=activo.id_activo_biologico,
    )

    assert pagina.total_registros >= 1
    creacion = next(r for r in pagina.registros if r.categoria == "CREACION")
    assert creacion.detalle_especifico["detalle_poblacional"]["cantidad_inicial"] == 10
    assert creacion.detalle_especifico["detalle_poblacional"]["cantidad_actual"] == 10
    assert Decimal(creacion.detalle_especifico["detalle_poblacional"]["peso_promedio_inicial"]) == Decimal("2.5")
