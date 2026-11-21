"""RF-18 — TC-M09-G39 (TC-M09-81): dos actualizaciones simultáneas sobre la
misma configuración operativa.

`ActualizarConfiguracionUseCase` aplica concurrencia optimista comparando el
`fecha_actualizacion` que trae el DTO del cliente contra el valor real en BD
(ver `actualizar_configuracion_use_case.py`): si no coinciden, lanza
`PreconditionFailedError` (412) en vez de aplicar el cambio.

Esta prueba reproduce dos solicitudes reales concurrentes -no una simulación
con un solo objeto en memoria- usando dos `Session` de SQLAlchemy INDEPENDIENTES
bindeadas a la misma conexión/transacción de la prueba (el mismo patrón que ya
usa `crear_sesion_background` en `tests/integration/conftest.py` para simular
la sesión de otro request). Cada una tiene su propio mapa de identidad, así
que la segunda sesión no arrastra en caché el valor que la primera ya
modificó: su lectura para la comprobación de concurrencia golpea la BD de
verdad, igual que le pasaría a un request HTTP nuevo. Es el motivo por el que
este caso no se automatiza como un simple request/response HTTP (Newman):
requiere controlar el orden exacto de dos escrituras entrelazadas, algo que
un cliente HTTP no puede orquestar de forma determinista.

Ambas solicitudes parten del MISMO `fecha_actualizacion` (leyeron la
configuración antes de que cualquiera de las dos escribiera, como pasaría si
dos administradores abrieran la pantalla al mismo tiempo). La primera en
ejecutar su PATCH gana; la segunda, con el token ya desactualizado, debe
rechazarse con 412 sin tocar el valor que dejó la primera.
"""
from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration


def _hay_tabla_configuraciones_globales(db_session: Session) -> bool:
    existe = db_session.execute(
        text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = 'modulo9' AND table_name = 'configuraciones_globales'"
        )
    ).first()
    return existe is not None


def _preparar_configuracion_base(db_session: Session, id_usuario: int, frecuencia: int, heartbeat: int):
    """Deja una configuración activa con valores base conocidos (reutiliza la
    fila existente vía UPDATE si ya hay una activa, igual que TC-M09-G38, para
    no chocar con el trigger de unicidad `trg_fn_configuracion_global_unicidad`
    en el entorno de pruebas compartido)."""
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


def test_TC_M09_81_segunda_actualizacion_concurrente_es_rechazada_con_412(
    db_session: Session, crear_usuario_db
) -> None:
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
    from src.shared.errors import PreconditionFailedError

    admin1 = crear_usuario_db(id_rol=1, estado=2)
    admin2 = crear_usuario_db(id_rol=1, estado=2)
    id_config, fecha_leida_por_ambos = _preparar_configuracion_base(
        db_session, id_usuario=admin1["id_usuario"], frecuencia=60, heartbeat=120
    )
    # Punto de commit intermedio: deja "fecha_leida_por_ambos" como el estado
    # que ambos administradores habrian visto al abrir la pantalla, antes de
    # que cualquiera de los dos escriba.
    db_session.commit()

    def _armar_use_case(session: Session) -> ActualizarConfiguracionUseCase:
        return ActualizarConfiguracionUseCase(
            db=session,
            config_repo=SqlAlchemyConfiguracionGlobalRepository(session),
            auditoria_repo=SqlAlchemyAuditoriaConfigRepository(session),
            iot_port=IotStubAdapter(),
        )

    # Sesion A: representa el request del primer administrador. Bindeada a la
    # misma conexion/transaccion que db_session (mismo patron que
    # `crear_sesion_background` en tests/integration/conftest.py), pero con su
    # propio mapa de identidad -como lo tendria un request HTTP nuevo-.
    sesion_a = Session(bind=db_session.connection(), expire_on_commit=False, join_transaction_mode="create_savepoint")
    use_case_a = _armar_use_case(sesion_a)
    dto_a = ActualizarConfiguracionDTO(frecuencia_muestreo=45, heartbeat=100, fecha_actualizacion=fecha_leida_por_ambos)
    usuario_a = UsuarioActual(id_usuario=admin1["id_usuario"], id_token=1, id_rol=1)

    config_tras_a = use_case_a.execute(id_config, dto_a, usuario_a)
    sesion_a.commit()

    assert config_tras_a.frecuencia_muestreo.valor == 45
    assert config_tras_a.heartbeat.valor == 100

    # Sesion B: el segundo administrador, que abrio la pantalla al mismo
    # tiempo que el primero y por lo tanto trae el MISMO fecha_actualizacion
    # ya desactualizado (A ya escribio). Sesion nueva e independiente: su
    # propia lectura de concurrencia golpea la BD real, no un valor en cache.
    sesion_b = Session(bind=db_session.connection(), expire_on_commit=False, join_transaction_mode="create_savepoint")
    use_case_b = _armar_use_case(sesion_b)
    dto_b = ActualizarConfiguracionDTO(frecuencia_muestreo=30, heartbeat=90, fecha_actualizacion=fecha_leida_por_ambos)
    usuario_b = UsuarioActual(id_usuario=admin2["id_usuario"], id_token=2, id_rol=1)

    with pytest.raises(PreconditionFailedError) as exc_info:
        use_case_b.execute(id_config, dto_b, usuario_b)
    assert exc_info.value.code == "CONFLICTO_CONCURRENCIA"
    assert exc_info.value.status_code == 412
    sesion_b.close()

    # La operacion aceptada fue la de A; la de B quedo en conflicto y no debe
    # haber alterado el estado que dejo A.
    fila_final = _leer_configuracion(db_session, id_config)
    assert fila_final.frecuencia_muestreo == 45
    assert fila_final.heartbeat == 100
    assert fila_final.fecha_actualizacion != fecha_leida_por_ambos
