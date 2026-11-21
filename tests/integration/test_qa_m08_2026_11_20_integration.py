# | Fecha      | Nombre   | Que se hizo                                                                    |
# |------------|----------|--------------------------------------------------------------------------------|
# | 2026-11-20 | Arekkazu | QA-M08 CU01 H-02 / CU03 H-01: semáforo por alertas activas y agrupación visual |
"""Integración del lote de QA M08 del 20/11/2026 contra PostgreSQL.

- CU01 H-02 (RF-103 R5): el semáforo sale solo de las alertas activas; una predicción de riesgo alto sin alerta no
  pinta el área.
- CU03 H-01 (RF-105 R7): los avisos activos del mismo tipo, nivel y activo se ven como uno con las ocurrencias de
  todos; sin activo, el mismo texto hace de activo. Leer el visible alcanza a los agrupados.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.identity_access.domain.repositories.notificacion_repository import FiltroBandeja
from src.identity_access.infrastructure.repositories.notificacion_repository import SqlAlchemyNotificacionRepository
from src.reporting.domain.widgets import estado_semaforo
from src.reporting.infrastructure.repositories.datos_widget_repository import SqlAlchemyDatosWidgetRepository

pytestmark = pytest.mark.integration

FINCA, AREA, ESPECIE, ANIMAL, OTRO = 8201, 8201, 8201, 8201, 8202


def _enum(tipo: str) -> str:
    return (f"(SELECT enumlabel::{tipo} FROM pg_enum e JOIN pg_type t ON t.oid = e.enumtypid "
            f"WHERE t.oid = '{tipo}'::regtype ORDER BY enumsortorder LIMIT 1)")


def _sembrar_area(db: Session) -> None:
    db.execute(text("SET LOCAL session_replication_role = replica"))
    db.execute(text(f"""
    INSERT INTO modulo9.fincas (id_finca, nombre, razon_social, numero_id_tributaria, dv, es_activo, tipo_id_tributaria,
        ubicacion, tamano_h, fecha_creacion, fecha_actualizacion)
        VALUES ({FINCA}, 'Finca Semáforo', 'Agro Semáforo SAS', '901888777', '1', true, 'NIT', '{{}}', 5, now(), now());
    INSERT INTO modulo9.infraestructuras (id_infraestructura, nombre, id_finca, es_activo, tipo, superficie)
        VALUES ({AREA}, 'Galpón Semáforo', {FINCA}, true, 'GALPON', 50);
    INSERT INTO modulo2.activos_biologicos (id_activo_biologico, id_especie, identificador, id_infraestructura, tipo,
        fecha_inicio_ciclo, id_estado, atributos_dinamicos, id_usuario, fecha_creacion, origen_financiero)
        VALUES ({ANIMAL}, {ESPECIE}, 'BOV-SEM', {AREA}, 'INDIVIDUAL', current_date - 30, 1, '{{}}', 1, now(),
                {_enum('modulo2.enum_activo_biologico_origen_financiero')});
    -- Riesgo alto hace 2 horas, sin alerta generada.
    INSERT INTO modulo4.resultados_inferencia (id_activo_biologico, id_especie, tipo_modelo, id_version_modelo,
        nivel_riesgo, probabilidad_riesgo, probabilidad_enfermedad, confianza_global, modo_ejecucion, fecha_inferencia)
        VALUES ({ANIMAL}, {ESPECIE}, {_enum('modulo4.enum_tipo_modelo')}, 1, 3, '{{}}', '{{}}', 0.9,
                {_enum('modulo4.enum_modo_ejecucion')}, now() - interval '2 hours');
    """))


def _estado(db: Session) -> str:
    [fila] = SqlAlchemyDatosWidgetRepository(db).semaforo_areas(FINCA, None)
    return estado_semaforo(fila["criticas"], fila["advertencias"], fila["sin_datos"])


def test_el_semaforo_sale_de_alertas_activas_y_no_del_riesgo_de_la_prediccion(db_session: Session):
    _sembrar_area(db_session)
    # Antes: la predicción de riesgo alto sola pintaba el área de rojo, sin ninguna alerta activa.
    assert _estado(db_session) == "VERDE"

    db_session.execute(text(f"""
    INSERT INTO modulo3.alertas (tipo_alerta, severidad, estado_alerta, origen_evento, fecha_evento, tipo_variable,
        id_infraestructura)
        VALUES ('ESTRES_TERMICO', 'MODERADO', 'ACTIVA', {_enum('modulo3.enum_origen_evento_alerta')}, now(),
                'TEMPERATURA', {AREA});
    """))
    assert _estado(db_session) == "AMARILLO"

    db_session.execute(text(f"""
    INSERT INTO modulo3.alertas (tipo_alerta, severidad, estado_alerta, origen_evento, fecha_evento, tipo_variable,
        id_infraestructura)
        VALUES ('PREDICCION_PATOLOGIA', 'CRITICO', 'ACTIVA', {_enum('modulo3.enum_origen_evento_alerta')}, now(),
                'PREDICCION', {AREA});
    """))
    assert _estado(db_session) == "ROJO"


def test_avisos_del_mismo_tipo_y_activo_se_ven_como_uno(db_session: Session, crear_usuario_db):
    from src.identity_access.infrastructure.repositories.evento_repository import SqlAlchemyEventoRepository

    db_session.execute(text("SET LOCAL session_replication_role = replica"))
    usuario = crear_usuario_db(id_rol=5)["id_usuario"]
    repo = SqlAlchemyNotificacionRepository(db_session)

    def aviso(mensaje: str, activo: int | None) -> int:
        id_evento = SqlAlchemyEventoRepository(db_session).registrar(
            tipo_evento=32, exitoso=True, id_usuario=usuario, detalle={"titulo": "Aviso"}, modulo="MODULO6")
        return repo.registrar(id_evento=id_evento, id_usuario=usuario, id_canal=2, mensaje=mensaje,
                              estado="en_cola", nivel="ADVERTENCIA", id_activo_biologico=activo)

    # Mismo activo con textos distintos (la agrupación al guardar exige el mismo texto y no los une).
    aviso("Precio nuevo del 16/11 para BOV-04", ANIMAL)
    visible = aviso("Precio nuevo del 17/11 para BOV-04", ANIMAL)
    aviso("Precio nuevo para BOV-05", OTRO)
    # Sin activo: el mismo texto agrupa, uno distinto no.
    aviso("La versión 4.0 del contrato no pudo activarse", None)
    aviso("La versión 5.0 del contrato no pudo activarse", None)

    filtro = FiltroBandeja()
    lista = repo.listar_internas(usuario, filtro, 0, 50)
    por_mensaje = {n.mensaje: n for n in lista}
    assert len(lista) == 4 and repo.contar_internas(usuario, filtro) == 4
    assert por_mensaje["Precio nuevo del 17/11 para BOV-04"].ocurrencias == 2
    assert "Precio nuevo del 16/11 para BOV-04" not in por_mensaje
    assert por_mensaje["Precio nuevo para BOV-05"].ocurrencias == 1

    notificacion = repo.obtener_interna(visible, usuario)
    assert notificacion is not None
    notificacion.marcar_como_leida(datetime.now(timezone.utc))
    repo.guardar(notificacion)
    leidas = db_session.execute(text("""
        SELECT count(*) FROM modulo1.notificaciones
        WHERE id_usuario = :u AND id_activo_biologico = :a AND estado = 'LEIDA'"""),
        {"u": usuario, "a": ANIMAL}).scalar()
    assert leidas == 2
    assert repo.contar_internas(usuario, FiltroBandeja(solo_no_leidas=True)) == 3
