"""RF-18 — TC-M09-G38 (TC-M09-80): rollback de parámetros operativos ante fallo de auditoría.

`ActualizarConfiguracionUseCase` escribe la config y el registro de auditoría
en la misma transacción y hace `rollback()` ante cualquier excepción (ver
`actualizar_configuracion_use_case.py`):

    try:
        config_actualizada = self.config_repo.actualizar(config)
        self.auditoria_repo.registrar(...)
        self.db.commit()
    except Exception:
        self.db.rollback()
        raise

Esta prueba ejercita el repositorio SQLAlchemy REAL de `configuraciones_globales`
contra PostgreSQL -no un fake en memoria- y fuerza el fallo únicamente en el
subsistema de auditoría con un adaptador roto (`_AuditoriaRotaFake`), para
comprobar el rollback releyendo la fila con un SELECT fresco después del
fallo, no el objeto de dominio que ya está en memoria del lado de la
aplicación. Es justo el motivo por el que este caso no se automatiza como un
simple request/response HTTP (Newman): un cliente HTTP nunca ve la fila
intermedia que el `flush()` del repository ya escribió antes de que el
`rollback()` la revierta.
"""
from __future__ import annotations

import datetime

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration


class _AuditoriaRotaFake:
    """Sustituye a `AuditoriaConfigRepository` para forzar un fallo real del
    subsistema de auditoría (ej.: constraint violado, tabla bloqueada, error
    de serialización JSONB) sin depender de condiciones de BD frágiles."""

    def registrar(self, **kwargs) -> None:
        raise RuntimeError("Fallo simulado del subsistema de auditoria (TC-M09-80)")


def _hay_tabla_configuraciones_globales(db_session: Session) -> bool:
    existe = db_session.execute(
        text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = 'modulo9' AND table_name = 'configuraciones_globales'"
        )
    ).first()
    return existe is not None


def _preparar_configuracion_base(
    db_session: Session, id_usuario: int, frecuencia: int, heartbeat: int
) -> tuple[int, datetime.datetime]:
    """Deja una configuración activa con valores base conocidos, dentro del
    savepoint de la prueba (se revierte al terminar como todo lo demás).

    Un trigger de BD (`trg_fn_configuracion_global_unicidad`) impide más de
    una fila activa a la vez, y en el entorno compartido de pruebas ya suele
    existir una (la deja, por ejemplo, TC-M09-G37). Por eso se reutiliza esa
    fila con un UPDATE en vez de intentar un INSERT que chocaría con el
    trigger; solo se inserta si de verdad no hay ninguna activa todavía.
    """
    existente = db_session.execute(
        text("SELECT id_configuracion_global FROM modulo9.configuraciones_globales WHERE es_activo = true LIMIT 1")
    ).first()

    if existente is not None:
        fila = db_session.execute(
            text(
                """
                UPDATE modulo9.configuraciones_globales
                SET frecuencia_muestreo = :frecuencia, heartbeat = :heartbeat,
                    fecha_actualizacion = now(), id_usuario = :id_usuario
                WHERE id_configuracion_global = :id
                RETURNING id_configuracion_global, fecha_actualizacion
                """
            ),
            {"frecuencia": frecuencia, "heartbeat": heartbeat, "id_usuario": id_usuario, "id": existente[0]},
        ).one()
    else:
        fila = db_session.execute(
            text(
                """
                INSERT INTO modulo9.configuraciones_globales
                    (frecuencia_muestreo, heartbeat, fecha_actualizacion, id_usuario, es_activo)
                VALUES (:frecuencia, :heartbeat, now(), :id_usuario, true)
                RETURNING id_configuracion_global, fecha_actualizacion
                """
            ),
            {"frecuencia": frecuencia, "heartbeat": heartbeat, "id_usuario": id_usuario},
        ).one()

    db_session.flush()
    return fila.id_configuracion_global, fila.fecha_actualizacion


def _leer_configuracion(db_session: Session, id_configuracion_global: int):
    return db_session.execute(
        text(
            """
            SELECT frecuencia_muestreo, heartbeat, fecha_actualizacion
            FROM modulo9.configuraciones_globales
            WHERE id_configuracion_global = :id
            """
        ),
        {"id": id_configuracion_global},
    ).one()


def _contar_auditoria(db_session: Session, id_configuracion_global: int) -> int:
    return db_session.execute(
        text(
            "SELECT count(*) FROM modulo9.auditorias_configuraciones_globales "
            "WHERE id_configuracion_global = :id"
        ),
        {"id": id_configuracion_global},
    ).scalar_one()


def test_TC_M09_80_fallo_de_auditoria_revierte_la_modificacion_de_parametros(
    db_session: Session, crear_usuario_db
) -> None:
    if not _hay_tabla_configuraciones_globales(db_session):
        pytest.skip("La base de pruebas no tiene aplicado el esquema modulo9 (configuraciones_globales).")

    from src.configuration.application.use_cases.configuracion.actualizar_configuracion_use_case import (
        ActualizarConfiguracionUseCase,
    )
    from src.configuration.infrastructure.adapters.iot_stub_adapter import IotStubAdapter
    from src.configuration.infrastructure.dto.actualizar_configuracion_dto import ActualizarConfiguracionDTO
    from src.configuration.infrastructure.repositories.configuracion_global_repository import (
        SqlAlchemyConfiguracionGlobalRepository,
    )
    from src.identity_access.infrastructure.dependencies import UsuarioActual

    admin = crear_usuario_db(id_rol=1, estado=2)
    id_config, fecha_previa = _preparar_configuracion_base(
        db_session, id_usuario=admin["id_usuario"], frecuencia=60, heartbeat=120
    )
    # Punto de commit intermedio: sin esto, el rollback() del use case (que
    # opera sobre el mismo savepoint que abrió esta prueba) retrocedería
    # tambien la preparacion del baseline de arriba, no solo el cambio bajo
    # prueba -el estado "antes" quedaria indefinido en vez de ser 60/120-.
    db_session.commit()
    conteo_auditoria_antes = _contar_auditoria(db_session, id_config)

    use_case = ActualizarConfiguracionUseCase(
        db=db_session,
        config_repo=SqlAlchemyConfiguracionGlobalRepository(db_session),
        auditoria_repo=_AuditoriaRotaFake(),
        iot_port=IotStubAdapter(),
    )
    dto = ActualizarConfiguracionDTO(frecuencia_muestreo=45, heartbeat=100, fecha_actualizacion=fecha_previa)
    usuario_actual = UsuarioActual(id_usuario=admin["id_usuario"], id_token=1, id_rol=1)

    with pytest.raises(RuntimeError, match="Fallo simulado del subsistema de auditoria"):
        use_case.execute(id_config, dto, usuario_actual)

    # Releido con un SELECT fresco tras el rollback interno del use case -no
    # el objeto de dominio en memoria, que el use case ya había mutado antes
    # de intentar persistir.
    fila = _leer_configuracion(db_session, id_config)
    assert fila.frecuencia_muestreo == 60
    assert fila.heartbeat == 120
    assert fila.fecha_actualizacion == fecha_previa

    # Tampoco debe quedar una fila de auditoria nueva para este intento fallido.
    assert _contar_auditoria(db_session, id_config) == conteo_auditoria_antes


def test_control_modificacion_exitosa_persiste_y_deja_registro_de_auditoria(
    db_session: Session, crear_usuario_db
) -> None:
    """Control positivo: confirma que el arnés SÍ distingue éxito de fallo -no
    está sesgado a que el rollback ocurra siempre por otra razón- usando el
    `SqlAlchemyAuditoriaConfigRepository` real en vez del fake roto."""
    if not _hay_tabla_configuraciones_globales(db_session):
        pytest.skip("La base de pruebas no tiene aplicado el esquema modulo9 (configuraciones_globales).")

    from src.configuration.application.use_cases.configuracion.actualizar_configuracion_use_case import (
        ActualizarConfiguracionUseCase,
    )
    from src.configuration.infrastructure.adapters.iot_stub_adapter import IotStubAdapter
    from src.configuration.infrastructure.dto.actualizar_configuracion_dto import ActualizarConfiguracionDTO
    from src.configuration.infrastructure.repositories.auditoria_config_repository import (
        SqlAlchemyAuditoriaConfigRepository,
    )
    from src.configuration.infrastructure.repositories.configuracion_global_repository import (
        SqlAlchemyConfiguracionGlobalRepository,
    )
    from src.identity_access.infrastructure.dependencies import UsuarioActual

    admin = crear_usuario_db(id_rol=1, estado=2)
    id_config, fecha_previa = _preparar_configuracion_base(
        db_session, id_usuario=admin["id_usuario"], frecuencia=60, heartbeat=120
    )
    db_session.commit()
    conteo_auditoria_antes = _contar_auditoria(db_session, id_config)

    use_case = ActualizarConfiguracionUseCase(
        db=db_session,
        config_repo=SqlAlchemyConfiguracionGlobalRepository(db_session),
        auditoria_repo=SqlAlchemyAuditoriaConfigRepository(db_session),
        iot_port=IotStubAdapter(),
    )
    dto = ActualizarConfiguracionDTO(frecuencia_muestreo=45, heartbeat=100, fecha_actualizacion=fecha_previa)
    usuario_actual = UsuarioActual(id_usuario=admin["id_usuario"], id_token=1, id_rol=1)

    use_case.execute(id_config, dto, usuario_actual)

    fila = _leer_configuracion(db_session, id_config)
    assert fila.frecuencia_muestreo == 45
    assert fila.heartbeat == 100
    assert fila.fecha_actualizacion != fecha_previa
    assert _contar_auditoria(db_session, id_config) == conteo_auditoria_antes + 1
