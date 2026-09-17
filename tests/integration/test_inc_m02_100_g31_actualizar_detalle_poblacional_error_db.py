"""[INC-M02-100-G31][RF-36] TC-M02-196 — POST .../eventos/crecimiento sobre un
lote poblacional devolvía 500 ERROR_INTERNO en vez del código de dominio
correspondiente cuando la actualización de `detalles_activos_biologicos_
poblacionales` violaba una restricción de base de datos.

`SqlAlchemyActivoBiologicoRepository.actualizar_detalle_poblacional()` no
capturaba errores de base de datos ni los traducía con `raise_from_db_error`
(a diferencia del resto de métodos de escritura del repositorio, y en
contra de la regla del proyecto). Cualquier violación de constraint durante
ese `flush()` — por ejemplo `chk_poblacional_cantidad_actual_coherente`
(`cantidad_actual <= cantidad_inicial`) — salía como una excepción cruda de
SQLAlchemy. `RegistrarEventoCrecimientoUseCase._execute()` la atrapaba en su
rama `except Exception` (no `except AppError`), dejaba constancia en
bitácora como `EVENTO_CRECIMIENTO_FALLIDO` y la relanzaba sin traducir —
Starlette la devolvía como 500 genérico en vez del 400/409/422 de dominio
que correspondía.
"""
from __future__ import annotations

from datetime import date

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
from src.shared.errors import ValidationError

pytestmark = pytest.mark.integration


@pytest.fixture
def especie_e_infra(db_session: Session, crear_usuario_db) -> tuple[int, int]:
    especie = db_session.execute(
        text("SELECT id_especie FROM modulo9.especies WHERE es_activo ORDER BY id_especie LIMIT 1")
    ).first()
    if especie is None:
        pytest.skip("Se requiere al menos una especie activa en modulo9.")

    dueno = crear_usuario_db()
    id_finca = db_session.execute(
        text(
            "INSERT INTO modulo9.fincas (nombre, ubicacion, tamano_h, fecha_actualizacion, fecha_creacion, id_usuario, es_activo) "
            "VALUES ('Finca Prueba INC-M02-100-G31', '{}'::jsonb, 10, now(), now(), :id_usuario, true) "
            "RETURNING id_finca"
        ),
        {"id_usuario": dueno["id_usuario"]},
    ).scalar_one()
    id_infra = db_session.execute(
        text(
            "INSERT INTO modulo9.infraestructuras (nombre, id_finca, superficie, es_activo, tipo) "
            "VALUES ('Estanque Prueba INC-M02-100-G31', :id_finca, 500, true, 'Estanque') "
            "RETURNING id_infraestructura"
        ),
        {"id_finca": id_finca},
    ).scalar_one()
    db_session.flush()
    return especie[0], id_infra


def test_violacion_de_constraint_en_actualizar_detalle_no_sale_como_500(
    db_session: Session, especie_e_infra: tuple[int, int], crear_usuario_db,
) -> None:
    id_especie, id_infraestructura = especie_e_infra
    usuario_db = crear_usuario_db()
    usuario = UsuarioActual(id_usuario=usuario_db["id_usuario"], id_token=1, id_rol=usuario_db["id_rol"])

    repo = SqlAlchemyActivoBiologicoRepository(db_session)
    use_case = RegistrarActivoBiologicoUseCase(
        db=db_session,
        repo=repo,
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
    db_session.commit()

    # Violación real de `chk_poblacional_cantidad_actual_coherente`
    # (cantidad_actual <= cantidad_inicial): un valor que ningún caso de uso
    # produciría por sí solo, pero que reproduce exactamente el tipo de
    # rechazo de base de datos que el reporte de QA describe como "fallo en
    # la capa de persistencia" para el lote 130.
    activo.detalle_poblacional.cantidad_actual = activo.detalle_poblacional.cantidad_inicial + 1

    # Antes del fix, `actualizar_detalle_poblacional` no envolvía el flush()
    # con `raise_from_db_error`: la excepción cruda de SQLAlchemy escapaba
    # de la capa de infraestructura sin traducir y terminaba como un 500
    # genérico en vez del 400 de dominio que corresponde a un CheckViolation.
    with pytest.raises(ValidationError) as exc_info:
        repo.actualizar_detalle_poblacional(activo)

    assert exc_info.value.status_code == 400
    assert exc_info.value.code == "VALOR_NO_PERMITIDO"
