"""Integración RF-52 CA-10: los rechazos tempranos sobreviven al rollback funcional."""
from __future__ import annotations

import random
import string
import uuid

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


def _sid() -> int:
    return uuid.uuid4().int % (10**9)


def _letras(n: int = 10) -> str:
    return ''.join(random.choices(string.ascii_letters, k=n))


def _crear_activo_individual(db_session: Session, id_usuario: int) -> int:
    # `pruebas` no trae datos transaccionales precargados (ver
    # scripts/provisionar_pruebas.sh); se crea el activo en la propia
    # transacción de la prueba, igual que test_inc_m02_75_g53_evento_fecha_race.
    sid = _sid()
    db_session.execute(
        text(
            """
            INSERT INTO modulo9.fincas (id_finca, nombre, ubicacion, tamano_h,
                fecha_actualizacion, fecha_creacion, es_activo)
            VALUES (:id, :nombre, '{}', 10, now(), now(), TRUE)
            """
        ),
        {"id": sid, "nombre": f"Finca Integracion {_letras()}"},
    )
    db_session.execute(
        text(
            """
            INSERT INTO modulo9.infraestructuras (id_infraestructura, nombre, id_finca,
                superficie, es_activo, tipo)
            VALUES (:id, :nombre, :id_finca, 100, TRUE, 'Estanque')
            """
        ),
        {"id": sid, "nombre": f"Infra Integracion {_letras()}", "id_finca": sid},
    )
    db_session.execute(
        text(
            """
            INSERT INTO modulo2.estados_activos_biologicos (id_estado_activo_biologico, nombre)
            VALUES (1, 'ACTIVO')
            ON CONFLICT (id_estado_activo_biologico) DO NOTHING
            """
        ),
    )
    db_session.execute(
        text(
            """
            INSERT INTO modulo2.activos_biologicos (id_activo_biologico, id_especie,
                identificador, id_infraestructura, tipo, fecha_inicio_ciclo, id_estado,
                descripcion, origen_financiero, costo_adquisicion, atributos_dinamicos,
                id_usuario, fecha_creacion, id_dispositivo_iot, soporte_documental,
                detalles_procedencia)
            VALUES (:id, 2, :identificador, :id, 'INDIVIDUAL', current_date, 1,
                '', 'compra', 100, '{}', :id_usuario, now() - interval '1 hour',
                0, 'doc', '')
            """
        ),
        {"id": sid, "identificador": f"RF52G107-{sid}", "id_usuario": id_usuario},
    )
    db_session.flush()
    return sid


@pytest.mark.integration
def test_nacimiento_fuera_de_secuencia_deja_rechazo_en_bitacora(
    db_session: Session,
    crear_usuario_db,
) -> None:
    usuario_datos = crear_usuario_db()
    id_usuario = usuario_datos["id_usuario"]
    db_session.execute(text("SET app.usuario_id = :uid"), {"uid": str(id_usuario)})
    id_activo = _crear_activo_individual(db_session, id_usuario)
    # Sella el fixture en un savepoint propio: el use case hace rollback() al
    # capturar el rechazo (ejecutar_con_auditoria_de_rechazo), y en el modo
    # "create_savepoint" de la sesión de pruebas eso revertiría también el
    # setup de arriba si no quedara ya confirmado en su propio savepoint.
    db_session.commit()

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
