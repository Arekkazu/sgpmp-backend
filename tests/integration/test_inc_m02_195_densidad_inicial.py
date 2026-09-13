"""[INC-M02-37-G24][RF-36] TC-M02-048 — densidad de un lote recién creado
debe calcularse (cantidad_actual / superficie) desde el registro, no quedar
`null` hasta el primer evento de crecimiento.

De los 4 problemas reportados en INC-M02-37-G24, solo este quedó en el
alcance de esta rama: los otros 3 ya están cubiertos por PRs abiertos
ajenos (#253 fases/TypeError, #254 trigger enum de baja) o son un gap de
arquitectura fuera de RF-16 (ver comentario dejado en la issue).
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
from src.identity_access.infrastructure.dependencies import UsuarioActual

pytestmark = pytest.mark.integration


@pytest.fixture
def especie_e_infra_500m2(db_session: Session, crear_usuario_db) -> tuple[int, int]:
    especie = db_session.execute(
        text("SELECT id_especie FROM modulo9.especies WHERE es_activo ORDER BY id_especie LIMIT 1")
    ).first()
    if especie is None:
        pytest.skip("Se requiere al menos una especie activa en modulo9.")

    dueno = crear_usuario_db()
    id_finca = db_session.execute(
        text(
            "INSERT INTO modulo9.fincas (nombre, ubicacion, tamano_h, fecha_actualizacion, fecha_creacion, id_usuario, es_activo) "
            "VALUES ('Finca Prueba Densidad', '{}'::jsonb, 10, now(), now(), :id_usuario, true) "
            "RETURNING id_finca"
        ),
        {"id_usuario": dueno["id_usuario"]},
    ).scalar_one()
    id_infra = db_session.execute(
        text(
            "INSERT INTO modulo9.infraestructuras (nombre, id_finca, superficie, es_activo, tipo) "
            "VALUES ('Estanque Prueba Densidad', :id_finca, 500, true, 'Estanque') "
            "RETURNING id_infraestructura"
        ),
        {"id_finca": id_finca},
    ).scalar_one()
    db_session.flush()
    return especie[0], id_infra


def test_lote_recien_creado_trae_densidad_calculada(
    db_session: Session, especie_e_infra_500m2: tuple[int, int], crear_usuario_db,
) -> None:
    id_especie, id_infraestructura = especie_e_infra_500m2
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
        cantidad_inicial=100,
    )

    activo = use_case.execute(dto, usuario)

    assert activo.detalle_poblacional.densidad == Decimal("0.2000")

    # Releer desde la fila persistida (no el objeto en memoria) para
    # confirmar que SqlAlchemyActivoBiologicoRepository.guardar() sí
    # escribió la columna, no solo el dominio.
    db_session.expire_all()
    persistido = db_session.execute(
        text(
            "SELECT densidad FROM modulo2.detalles_activos_biologicos_poblacionales "
            "WHERE id_activo_biologico = :id"
        ),
        {"id": activo.id_activo_biologico},
    ).scalar_one()
    assert persistido == Decimal("0.2000")
