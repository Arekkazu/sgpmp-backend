"""Integración RF-52 CA-8 con filtros SQL y rollback exterior."""
from __future__ import annotations

import random
import string
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.biological_assets.application.use_cases.gestion.consultar_bitacora_use_case import (
    ConsultarBitacoraUseCase,
)
from src.biological_assets.domain.entities.activo_biologico import EventoAuditoria
from src.biological_assets.infrastructure.dto.consultar_bitacora_dto import ConsultarBitacoraDTO
from src.biological_assets.infrastructure.repositories.bitacora_auditoria_repository import (
    SqlAlchemyBitacoraAuditoriaRepository,
)
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.identity_access.infrastructure.repositories.rol_repository import SqlAlchemyRolRepository
from src.shared.errors import AuthorizationError


pytestmark = pytest.mark.integration


def _letras(n: int = 10) -> str:
    return ''.join(random.choices(string.ascii_letters, k=n))


def _id_rol(db: Session, nombre: str) -> int:
    fila = db.execute(
        text('SELECT id_rol FROM modulo1.roles WHERE lower(nombre_rol) = lower(:nombre)'),
        {'nombre': nombre},
    ).first()
    if fila is None:
        pytest.skip(f'La base de integración no tiene el rol {nombre}.')
    return fila.id_rol


def _crear_activo_desde_fixture(db: Session, id_usuario: int) -> int:
    # `pruebas` no trae datos transaccionales precargados (ver
    # scripts/provisionar_pruebas.sh): se crea finca/infraestructura/activo
    # propios en vez de copiar una fila existente, igual que
    # test_inc_m02_75_g53_evento_fecha_race.py.
    sid = uuid.uuid4().int % (10**9)
    db.execute(text("SELECT set_config('app.usuario_id', :usuario, true)"), {'usuario': str(id_usuario)})
    db.execute(
        text(
            """
            INSERT INTO modulo9.fincas (id_finca, nombre, ubicacion, tamano_h,
                fecha_actualizacion, fecha_creacion, es_activo)
            VALUES (:id, :nombre, '{}', 10, now(), now(), TRUE)
            """
        ),
        {'id': sid, 'nombre': f'Finca Integracion {_letras()}'},
    )
    db.execute(
        text(
            """
            INSERT INTO modulo9.infraestructuras (id_infraestructura, nombre, id_finca,
                superficie, es_activo, tipo)
            VALUES (:id, :nombre, :id_finca, 100, TRUE, 'Estanque')
            """
        ),
        {'id': sid, 'nombre': f'Infra Integracion {_letras()}', 'id_finca': sid},
    )
    db.execute(
        text(
            """
            INSERT INTO modulo2.estados_activos_biologicos (id_estado_activo_biologico, nombre)
            VALUES (1, 'ACTIVO')
            ON CONFLICT (id_estado_activo_biologico) DO NOTHING
            """
        ),
    )
    identificador = f'G105-{uuid.uuid4().hex[:12]}'
    fila = db.execute(
        text(
            """
            INSERT INTO modulo2.activos_biologicos (
                id_activo_biologico, id_especie, identificador, id_infraestructura, tipo,
                fecha_inicio_ciclo, id_estado, descripcion, origen_financiero,
                costo_adquisicion, atributos_dinamicos, id_usuario,
                fecha_creacion, id_dispositivo_iot, soporte_documental,
                detalles_procedencia
            ) VALUES (
                :id, 2, :identificador, :id, 'INDIVIDUAL',
                current_date, 1, 'Fixture RF-52 CA-8',
                CAST('compra' AS modulo2.enum_activo_biologico_origen_financiero),
                100, '{}', :id_usuario, now(), 0, 'doc', ''
            )
            RETURNING id_activo_biologico
            """
        ),
        {'id': sid, 'identificador': identificador, 'id_usuario': id_usuario},
    ).first()
    return fila.id_activo_biologico


def _usuario(datos: dict) -> UsuarioActual:
    return UsuarioActual(
        id_usuario=datos['id_usuario'],
        id_token=1,
        id_rol=datos['id_rol'],
        id_estado_cuenta=2,
    )


def _evento(id_activo: int, clasificacion: str, id_usuario: int) -> EventoAuditoria:
    return EventoAuditoria(
        rf_origen='RF52',
        tipo_evento=f'FIXTURE_G105_{clasificacion}',
        clasificacion_biologica=clasificacion,
        timestamp_evento=datetime.now(timezone.utc),
        id_activo_biologico=id_activo,
        id_usuario_responsable=id_usuario,
    )


def test_ca8_aplica_alcance_y_registra_rechazos_con_postgresql(
    db_session: Session,
    crear_usuario_db,
) -> None:
    productor = crear_usuario_db(id_rol=_id_rol(db_session, 'Productor'))
    otro_productor = crear_usuario_db(id_rol=_id_rol(db_session, 'Productor'))
    contador = crear_usuario_db(id_rol=_id_rol(db_session, 'Contador'))
    administrador = crear_usuario_db(id_rol=_id_rol(db_session, 'Administrador'))

    activo_propio = _crear_activo_desde_fixture(db_session, productor['id_usuario'])
    activo_ajeno = _crear_activo_desde_fixture(db_session, otro_productor['id_usuario'])

    repo = SqlAlchemyBitacoraAuditoriaRepository(db_session)
    for evento in (
        _evento(activo_propio, 'ACCESO_DATOS', productor['id_usuario']),
        _evento(activo_ajeno, 'ACCESO_DATOS', otro_productor['id_usuario']),
        _evento(activo_ajeno, 'GESTION_OPERATIVA', otro_productor['id_usuario']),
        _evento(activo_ajeno, 'CONTROL_ESTADO', otro_productor['id_usuario']),
        _evento(activo_ajeno, 'TRANSFORMACION_BIOLOGICA', otro_productor['id_usuario']),
        _evento(activo_ajeno, 'SANITARIO', otro_productor['id_usuario']),
    ):
        repo.registrar(evento)

    caso = ConsultarBitacoraUseCase(
        db_session,
        repo,
        SqlAlchemyRolRepository(db_session),
    )

    with pytest.raises(AuthorizationError) as productor_denegado:
        caso.execute(
            ConsultarBitacoraDTO(
                id_activo_biologico=activo_ajeno,
                clasificacion_biologica='ACCESO_DATOS',
            ),
            _usuario(productor),
        )
    assert productor_denegado.value.status_code == 403

    accesos_productor, _ = caso.execute(
        ConsultarBitacoraDTO(clasificacion_biologica='ACCESO_DATOS', page_size=100),
        _usuario(productor),
    )
    assert any(e.id_activo_biologico == activo_propio for e in accesos_productor)
    assert all(e.id_activo_biologico != activo_ajeno for e in accesos_productor)

    for clasificacion in ('GESTION_OPERATIVA', 'CONTROL_ESTADO'):
        with pytest.raises(AuthorizationError) as contador_denegado:
            caso.execute(
                ConsultarBitacoraDTO(
                    id_activo_biologico=activo_ajeno,
                    clasificacion_biologica=clasificacion,
                ),
                _usuario(contador),
            )
        assert contador_denegado.value.status_code == 403

    eventos_contador, _ = caso.execute(
        ConsultarBitacoraDTO(page_size=100),
        _usuario(contador),
    )
    assert {e.clasificacion_biologica for e in eventos_contador} <= {
        'TRANSFORMACION_BIOLOGICA',
        'SANITARIO',
    }
    assert {'TRANSFORMACION_BIOLOGICA', 'SANITARIO'} <= {
        e.clasificacion_biologica
        for e in eventos_contador
        if e.id_activo_biologico == activo_ajeno
    }

    eventos_admin, total_admin = caso.execute(
        ConsultarBitacoraDTO(page_size=100),
        _usuario(administrador),
    )
    assert total_admin >= len(eventos_admin)
    assert {'ACCESO_DATOS', 'GESTION_OPERATIVA', 'CONTROL_ESTADO'} <= {
        e.clasificacion_biologica
        for e in eventos_admin
        if e.id_activo_biologico == activo_ajeno
    }

    intentos = db_session.execute(
        text(
            """
            SELECT count(*)
            FROM modulo2.bitacora_auditoria_m02
            WHERE tipo_evento = 'ACCESO_NO_AUTORIZADO'
              AND id_usuario_responsable IN (:productor, :contador)
              AND id_activo_biologico = :activo_ajeno
            """
        ),
        {
            'productor': productor['id_usuario'],
            'contador': contador['id_usuario'],
            'activo_ajeno': activo_ajeno,
        },
    ).scalar_one()
    assert intentos == 3
