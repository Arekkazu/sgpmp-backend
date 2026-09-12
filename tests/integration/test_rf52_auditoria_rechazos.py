"""Integración RF-52 CA-10: los rechazos tempranos sobreviven al rollback funcional."""
from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.biological_assets.application.use_cases.gestion.registrar_evento_reproductivo_use_case import (
    RegistrarEventoReproductivoUseCase,
)
from src.biological_assets.infrastructure.dto.registrar_evento_reproductivo_dto import (
    RegistrarEventoReproductivoDTO,
)
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
from src.shared.errors import BusinessRuleError


@pytest.mark.integration
def test_nacimiento_fuera_de_secuencia_deja_rechazo_en_bitacora(
    db_session: Session,
) -> None:
    id_activo = db_session.execute(text(
        """
        SELECT a.id_activo_biologico
        FROM modulo2.activos_biologicos AS a
        WHERE a.tipo = 'INDIVIDUAL'
          AND a.id_estado = 1
          AND NOT EXISTS (
              SELECT 1
              FROM modulo2.eventos_activos AS e
              JOIN modulo2.eventos_reproductivos AS r
                ON r.id_evento_reproductivo = e.id_eventos
              WHERE e.id_activo_biologico = a.id_activo_biologico
                AND r.categoria IN ('servicio', 'inseminacion')
          )
        ORDER BY a.id_activo_biologico
        LIMIT 1
        """
    )).scalar_one_or_none()
    if id_activo is None:
        pytest.skip('No existe un activo individual apto para reproducir TC-M02-271.')

    id_usuario = db_session.execute(text(
        'SELECT id_usuario FROM modulo1.usuarios ORDER BY id_usuario LIMIT 1'
    )).scalar_one()

    use_case = RegistrarEventoReproductivoUseCase(
        db=db_session,
        activo_repo=SqlAlchemyActivoBiologicoRepository(db_session),
        evento_repo=SqlAlchemyEventoActivoRepository(db_session),
        bitacora_repo=SqlAlchemyBitacoraAuditoriaRepository(db_session),
    )
    dto = RegistrarEventoReproductivoDTO(
        categoria='nacimiento',
        resultado='exitoso',
        numero_crias=1,
    )
    usuario = UsuarioActual(id_usuario=id_usuario, id_token=1, id_rol=1)

    with pytest.raises(BusinessRuleError) as exc:
        use_case.execute(id_activo, dto, usuario)

    assert exc.value.status_code == 422
    assert exc.value.code == 'SECUENCIA_REPRODUCTIVA_INVALIDA'

    auditoria = db_session.execute(text(
        """
        SELECT rf_origen, tipo_evento, resultado, severidad_log,
               id_activo_biologico, id_usuario_responsable,
               detalle_tecnico
        FROM modulo2.bitacora_auditoria_m02
        WHERE id_activo_biologico = :id_activo
          AND rf_origen = 'RF42'
          AND tipo_evento = 'SECUENCIA_REPRODUCTIVA_VIOLADA'
        ORDER BY id_bitacora DESC
        LIMIT 1
        """
    ), {'id_activo': id_activo}).mappings().one()

    assert auditoria['resultado'] == 'RECHAZADO'
    assert auditoria['severidad_log'] == 'WARNING'
    assert auditoria['id_usuario_responsable'] == id_usuario
    assert auditoria['detalle_tecnico']['error_code'] == 'SECUENCIA_REPRODUCTIVA_INVALIDA'
    assert 'nacimiento' in auditoria['detalle_tecnico']['causa']

    eventos_reproductivos = db_session.execute(text(
        """
        SELECT count(*)
        FROM modulo2.eventos_activos AS e
        JOIN modulo2.eventos_reproductivos AS r
          ON r.id_evento_reproductivo = e.id_eventos
        WHERE e.id_activo_biologico = :id_activo
          AND r.categoria = 'nacimiento'
        """
    ), {'id_activo': id_activo}).scalar_one()
    assert eventos_reproductivos == 0
