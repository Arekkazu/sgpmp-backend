"""INC-M02-45-G12: TC-M02-014 — `peso_destete` fuera de rango (20-40 kg) para
la especie 4 (Cachama Blanca) debe rechazarse con 400.

No es una prueba de código nuevo: verifica que la configuración de RF-16
insertada para cerrar este issue (ver
`anotaciones/modulo_2/inc_m02_45_g12_peso_destete.md`) efectivamente hace que
el mecanismo de validación de rango — ya existente desde PR #245 — rechace
el caso que reportó QA.
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
from src.shared.errors import BusinessRuleError

pytestmark = pytest.mark.integration

_ID_ESPECIE_CACHAMA_BLANCA = 4


@pytest.fixture
def infra_cachama(db_session: Session, crear_usuario_db) -> int:
    metrica = db_session.execute(
        text(
            "SELECT 1 FROM modulo9.metricas_produccion "
            "WHERE id_especie = :id AND lower(nombre) = 'peso_destete'"
        ),
        {"id": _ID_ESPECIE_CACHAMA_BLANCA},
    ).first()
    if metrica is None:
        pytest.skip("Requiere la métrica peso_destete configurada para la especie 4 (ver INC-M02-45-G12).")

    dueno = crear_usuario_db()
    id_finca = db_session.execute(
        text(
            "INSERT INTO modulo9.fincas (nombre, ubicacion, tamano_h, fecha_actualizacion, fecha_creacion, id_usuario, es_activo) "
            "VALUES ('Finca Prueba Cachama', '{}'::jsonb, 10, now(), now(), :id_usuario, true) "
            "RETURNING id_finca"
        ),
        {"id_usuario": dueno["id_usuario"]},
    ).scalar_one()
    id_infra = db_session.execute(
        text(
            "INSERT INTO modulo9.infraestructuras (nombre, id_finca, superficie, es_activo, tipo) "
            "VALUES ('Estanque Prueba Cachama', :id_finca, 500, true, 'Estanque') "
            "RETURNING id_infraestructura"
        ),
        {"id_finca": id_finca},
    ).scalar_one()
    db_session.flush()
    return id_infra


def _use_case(db_session: Session) -> RegistrarActivoBiologicoUseCase:
    return RegistrarActivoBiologicoUseCase(
        db=db_session,
        repo=SqlAlchemyActivoBiologicoRepository(db_session),
        especie_port=EspecieM09Adapter(db_session),
        infra_port=InfraestructuraM09Adapter(db_session),
        parametros_port=ParametrosEspecieM09Adapter(db_session),
    )


def _dto(id_infraestructura: int, peso_destete) -> RegistrarActivoBiologicoDTO:
    return RegistrarActivoBiologicoDTO(
        tipo_activo="POBLACIONAL",
        id_especie=_ID_ESPECIE_CACHAMA_BLANCA,
        fecha_inicio_ciclo=date(2024, 1, 1),
        origen_financiero="nacimiento",
        id_infraestructura=id_infraestructura,
        cantidad_inicial=10,
        atributos_dinamicos={"peso_destete": peso_destete},
    )


def test_peso_destete_bajo_el_minimo_se_rechaza_con_400(
    db_session: Session, infra_cachama: int,
) -> None:
    use_case = _use_case(db_session)
    usuario = UsuarioActual(id_usuario=1, id_token=1, id_rol=1)

    with pytest.raises(BusinessRuleError) as exc_info:
        use_case.execute(_dto(infra_cachama, 5), usuario)

    # ATRIBUTO_FUERA_DE_RANGO es BusinessRuleError (422) en todo el módulo —
    # no 400 — consistente con el resto de _validar_atributos_dinamicos.
    assert exc_info.value.status_code == 422
    assert exc_info.value.code == "ATRIBUTO_FUERA_DE_RANGO"


def test_peso_destete_dentro_del_rango_se_acepta(
    db_session: Session, infra_cachama: int, crear_usuario_db,
) -> None:
    use_case = _use_case(db_session)
    usuario_db = crear_usuario_db()
    usuario = UsuarioActual(id_usuario=usuario_db["id_usuario"], id_token=1, id_rol=usuario_db["id_rol"])

    activo = use_case.execute(_dto(infra_cachama, 25), usuario)

    assert activo.atributos_dinamicos == {"peso_destete": 25}
