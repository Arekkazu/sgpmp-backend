"""[INC-M02-48-G25][RF-36] Reverificación end-to-end de la validación de
densidad máxima en eventos de crecimiento.

`test_registrar_evento_crecimiento_densidad_maxima.py` (unitario, con fakes)
ya prueba que `RegistrarEventoCrecimientoUseCase` calcula y compara
`cantidad_actual / superficie` contra `capacidad_maxima / superficie`
correctamente. INC-M02-48-G25 reportó que, en el ambiente de TEST, un lote de
50.000 individuos en 500 m² (100 ind/m²) se aceptó con 201 en vez de 409.

Investigación (ver `anotaciones/modulo_2/inc_m02_48_g25_rf36_reverificacion.md`):
la causa NO es un bug en la lógica (el unitario ya la cubre), sino que las 12
infraestructuras reales de `sgpmp_dev`/TEST tienen `capacidad_maxima = NULL` —
decisión ya tomada y probada explícitamente en
`test_sin_capacidad_maxima_configurada_no_bloquea` — y el fix (commit
`9cbb4418`) probablemente no estaba desplegado en TEST al momento de la prueba.

Esta prueba cierra la brecha entre "la lógica es correcta" (unitario, fakes) y
"funciona de punta a punta" (HTTP → use case → adapter real → Postgres),
usando el mismo patrón de `test_inc_m02_195_densidad_inicial.py`.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.biological_assets.application.use_cases.gestion.registrar_evento_crecimiento_use_case import (
    RegistrarEventoCrecimientoUseCase,
)
from src.biological_assets.application.use_cases.registro.registrar_activo_use_case import (
    RegistrarActivoBiologicoUseCase,
)
from src.biological_assets.infrastructure.adapters.ciclo_productivo_m09_adapter import CicloProductivoM09Adapter
from src.biological_assets.infrastructure.adapters.especie_m09_adapter import EspecieM09Adapter
from src.biological_assets.infrastructure.adapters.infraestructura_m09_adapter import InfraestructuraM09Adapter
from src.biological_assets.infrastructure.adapters.parametros_especie_m09_adapter import ParametrosEspecieM09Adapter
from src.biological_assets.infrastructure.dto.registrar_activo_dto import RegistrarActivoBiologicoDTO
from src.biological_assets.infrastructure.dto.registrar_evento_crecimiento_dto import RegistrarEventoCrecimientoDTO
from src.biological_assets.infrastructure.repositories.activo_biologico_repository import (
    SqlAlchemyActivoBiologicoRepository,
)
from src.biological_assets.infrastructure.repositories.bitacora_auditoria_repository import (
    SqlAlchemyBitacoraAuditoriaRepository,
)
from src.biological_assets.infrastructure.repositories.evento_activo_repository import (
    SqlAlchemyEventoActivoRepository,
)
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import ConflictError

pytestmark = pytest.mark.integration


def _crear_infra(db_session: Session, id_finca: int, superficie: int, capacidad_maxima: int | None) -> int:
    return db_session.execute(
        text(
            "INSERT INTO modulo9.infraestructuras (nombre, id_finca, superficie, capacidad_maxima, es_activo, tipo) "
            "VALUES ('Estanque Densidad Maxima', :id_finca, :superficie, :capacidad_maxima, true, 'Estanque') "
            "RETURNING id_infraestructura"
        ),
        {"id_finca": id_finca, "superficie": superficie, "capacidad_maxima": capacidad_maxima},
    ).scalar_one()


@pytest.fixture
def especie_y_finca(db_session: Session, crear_usuario_db) -> tuple[int, int]:
    # Debe tener PESO configurado en modulo9.metricas_produccion (RF-40 lo exige
    # antes de llegar a la validación de densidad que prueba este archivo).
    especie = db_session.execute(
        text(
            "SELECT e.id_especie FROM modulo9.especies e "
            "JOIN modulo9.metricas_produccion mp ON mp.id_especie = e.id_especie "
            "WHERE e.es_activo AND mp.tipo_medicion = 'PESO' "
            "ORDER BY e.id_especie LIMIT 1"
        )
    ).first()
    if especie is None:
        pytest.skip("Se requiere una especie activa con métrica PESO configurada en modulo9.")

    dueno = crear_usuario_db()
    id_finca = db_session.execute(
        text(
            "INSERT INTO modulo9.fincas (nombre, ubicacion, tamano_h, fecha_actualizacion, fecha_creacion, id_usuario, es_activo) "
            "VALUES ('Finca Densidad Maxima', '{}'::jsonb, 10, now(), now(), :id_usuario, true) "
            "RETURNING id_finca"
        ),
        {"id_usuario": dueno["id_usuario"]},
    ).scalar_one()
    db_session.flush()
    return especie[0], id_finca


def _registrar_lote(
    db_session: Session, id_especie: int, id_infraestructura: int, cantidad_inicial: int, usuario: UsuarioActual,
) -> int | None:
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
        cantidad_inicial=cantidad_inicial,
    )
    id_activo = use_case.execute(dto, usuario).id_activo_biologico

    # RF-40 exige fase productiva activa para aceptar eventos de crecimiento;
    # RegistrarActivoBiologicoUseCase no crea una automáticamente.
    db_session.execute(
        text(
            "INSERT INTO modulo2.gestiones_fases "
            "(id_activo_biologico, id_ciclo_productiva, fecha_inicio, es_activa, id_usuario) "
            "VALUES (:id_activo, 1, now(), true, :id_usuario)"
        ),
        {"id_activo": id_activo, "id_usuario": usuario.id_usuario},
    )
    db_session.flush()
    return id_activo


def _uc_crecimiento(db_session: Session) -> RegistrarEventoCrecimientoUseCase:
    return RegistrarEventoCrecimientoUseCase(
        db=db_session,
        activo_repo=SqlAlchemyActivoBiologicoRepository(db_session),
        evento_repo=SqlAlchemyEventoActivoRepository(db_session),
        infra_port=InfraestructuraM09Adapter(db_session),
        parametros_port=ParametrosEspecieM09Adapter(db_session),
        ciclo_port=CicloProductivoM09Adapter(db_session),
        bitacora_repo=SqlAlchemyBitacoraAuditoriaRepository(db_session),
    )


def test_lote_hacinado_es_rechazado_con_409_de_punta_a_punta(
    db_session: Session, especie_y_finca: tuple[int, int], crear_usuario_db,
) -> None:
    """Reproduce el caso de INC-M02-48-G25: 100 individuos en 500 m^2
    (0.2 ind/m^2) contra una infraestructura configurada con
    capacidad_maxima=1 (densidad_maxima = 1/500 = 0.002 ind/m^2)."""
    id_especie, id_finca = especie_y_finca
    usuario_db = crear_usuario_db()
    usuario = UsuarioActual(id_usuario=usuario_db["id_usuario"], id_token=1, id_rol=usuario_db["id_rol"])

    id_infraestructura = _crear_infra(db_session, id_finca, superficie=500, capacidad_maxima=1)
    id_activo = _registrar_lote(db_session, id_especie, id_infraestructura, cantidad_inicial=100, usuario=usuario)
    assert id_activo is not None

    dto = RegistrarEventoCrecimientoDTO(
        tipo_medicion="PESO",
        valor_medicion=Decimal("25"),
        unidad_medida="kg",
        nuevo_peso_promedio=Decimal("26"),
        cantidad_medida=100,
        tipo_agregacion="PROMEDIO",
        fecha=datetime.now(timezone.utc),
    )

    with pytest.raises(ConflictError) as exc_info:
        _uc_crecimiento(db_session).execute(id_activo, dto, usuario)

    assert exc_info.value.code == "DENSIDAD_MAXIMA_SUPERADA"


def test_lote_dentro_del_limite_es_aceptado_de_punta_a_punta(
    db_session: Session, especie_y_finca: tuple[int, int], crear_usuario_db,
) -> None:
    """Mismo lote (100/500 = 0.2 ind/m^2) contra capacidad_maxima=1000
    (densidad_maxima = 2 ind/m^2): dentro del límite, debe aceptarse."""
    id_especie, id_finca = especie_y_finca
    usuario_db = crear_usuario_db()
    usuario = UsuarioActual(id_usuario=usuario_db["id_usuario"], id_token=1, id_rol=usuario_db["id_rol"])

    id_infraestructura = _crear_infra(db_session, id_finca, superficie=500, capacidad_maxima=1000)
    id_activo = _registrar_lote(db_session, id_especie, id_infraestructura, cantidad_inicial=100, usuario=usuario)
    assert id_activo is not None

    dto = RegistrarEventoCrecimientoDTO(
        tipo_medicion="PESO",
        valor_medicion=Decimal("25"),
        unidad_medida="kg",
        nuevo_peso_promedio=Decimal("26"),
        cantidad_medida=100,
        tipo_agregacion="PROMEDIO",
        fecha=datetime.now(timezone.utc),
    )

    resultado, _ = _uc_crecimiento(db_session).execute(id_activo, dto, usuario)

    assert resultado is not None
