# | Fecha      | Nombre   | Que se hizo                                                                          |
# |------------|----------|--------------------------------------------------------------------------------------|
# | 2026-11-23 | Arekkazu | QA-M08 ronda 3 RF-103/RF-104: semáforo, dispositivos de la finca y reportes del Admin |
"""Integración de la ronda 3 de QA M08 (23/11/2026) contra PostgreSQL.

- CU01 H-02 (RF-103 R5): una alerta que no es de RF-57 ni de RF-66 (conversión alimenticia) no pinta el semáforo.
- CU01 H-04 (RF-103): el dispositivo registrado en el área sin sensor vinculado también cuenta en la finca.
- CU02 H-01/H-06 (RF-104 CA-6..CA-9, RFC-032): el Administrador solo genera los reportes de Gerencia.
"""
from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.reporting.domain.reportes.catalogo import CATALOGO
from src.reporting.infrastructure.adapters.solicitante_reportes import construir_solicitante
from src.reporting.infrastructure.repositories.datos_widget_repository import SqlAlchemyDatosWidgetRepository

pytestmark = pytest.mark.integration

FINCA, AREA, DISPOSITIVO = 8301, 8301, 8301

GERENCIA = {"REPORTE_INVENTARIO_BIOLOGICO", "REPORTE_COSTOS_SUMINISTROS", "REPORTE_PRODUCTIVIDAD",
            "REPORTE_BAJAS_Y_SALIDAS", "REPORTE_EJECUTIVO_CONSOLIDADO", "REPORTE_RENTABILIDAD_FINCA",
            "REPORTE_COMPARATIVO_PERIODOS"}


def _enum(tipo: str) -> str:
    return (f"(SELECT enumlabel::{tipo} FROM pg_enum e JOIN pg_type t ON t.oid = e.enumtypid "
            f"WHERE t.oid = '{tipo}'::regtype ORDER BY enumsortorder LIMIT 1)")


def _sembrar(db: Session) -> None:
    db.execute(text("SET LOCAL session_replication_role = replica"))
    db.execute(text(f"""
    INSERT INTO modulo9.fincas (id_finca, nombre, razon_social, numero_id_tributaria, dv, es_activo, tipo_id_tributaria,
        ubicacion, tamano_h, fecha_creacion, fecha_actualizacion)
        VALUES ({FINCA}, 'Finca Ronda 3', 'Agro Ronda SAS', '901777666', '1', true, 'NIT', '{{}}', 5, now(), now());
    INSERT INTO modulo9.infraestructuras (id_infraestructura, nombre, id_finca, es_activo, tipo, superficie)
        VALUES ({AREA}, 'Galpón Principal', {FINCA}, true, 'GALPON', 50);
    INSERT INTO modulo9.dispositivos_iot (id_dispositivo_iot, serial, descripcion, es_activo, fecha_creacion,
        id_infraestructura, id_tipo_dispositivo)
        VALUES ({DISPOSITIVO}, 'ESP-R3', 'Nodo del galpón', true, now(), {AREA}, 1);
    """))
    db.execute(text("SET LOCAL session_replication_role = origin"))


def test_conversion_alimenticia_no_pinta_el_semaforo(db_session: Session):
    _sembrar(db_session)
    db_session.execute(text(f"""
    INSERT INTO modulo3.alertas (tipo_alerta, severidad, estado_alerta, origen_evento, fecha_evento, tipo_variable,
        id_infraestructura)
        VALUES ('CONVERSION_ALIMENTICIA', 'MODERADO', 'ACTIVA', {_enum('modulo3.enum_origen_evento_alerta')}, now(),
                'CONVERSION', {AREA});
    """))
    [fila] = SqlAlchemyDatosWidgetRepository(db_session).semaforo_areas(FINCA, None)
    assert (fila["criticas"], fila["advertencias"]) == (0, 0)


def test_el_dispositivo_del_area_sin_sensor_cuenta_en_la_finca(db_session: Session):
    _sembrar(db_session)
    filas = SqlAlchemyDatosWidgetRepository(db_session).dispositivos(FINCA, None)
    # Antes la vista solo veía dispositivos con sensor vinculado o con animal: este no aparecía.
    assert [(f["id_dispositivo_iot"], f["area"], f["estado"]) for f in filas] == [
        (DISPOSITIVO, "Galpón Principal", "DESCONOCIDO")]


def test_el_administrador_solo_genera_los_reportes_de_gerencia(db_session: Session):
    roles: dict[str, int] = {n: i for n, i in db_session.execute(text("SELECT nombre_rol, id_rol FROM modulo1.roles"))}
    admin = construir_solicitante(db_session, 1, roles["Administrador"], "UTC")
    assert admin.permitidos == GERENCIA
    contador = construir_solicitante(db_session, 1, roles["Contador"], "UTC")
    assert {"REPORTE_VALORACION_NIC41", "REPORTE_ESTADO_EXPORTACIONES", "REPORTE_VARIACION_PERIODOS"} <= contador.permitidos
    ingeniero = construir_solicitante(db_session, 1, roles["Ingeniero de Campo"], "UTC")
    assert ingeniero.permitidos == {"REPORTE_TELEMETRIA", "REPORTE_ESTADO_DISPOSITIVOS", "REPORTE_CALIBRACION_SENSORES",
                                    "REPORTE_ALERTAS_SENSORES"}
    veterinario = construir_solicitante(db_session, 1, roles["Veterinario"], "UTC")
    assert "REPORTE_RIESGO_SANITARIO" in veterinario.permitidos
    assert GERENCIA <= set(CATALOGO)
