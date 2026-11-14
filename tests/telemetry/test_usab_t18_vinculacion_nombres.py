# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-25 | Arekkazu | USAB-M03 T-18 RF-61: la vinculación trae nombres además de IDs |
"""T-18: Vinculaciones mostraba solo IDs (#115703, #854, #391)."""
from datetime import datetime, timezone
from decimal import Decimal

from src.telemetry.domain.entities.vinculacion_lectura import VinculacionLectura
from src.telemetry.infrastructure.repositories.vinculacion_lectura_repository import (
    SqlAlchemyVinculacionLecturaRepository,
)

CAPTURA = datetime(2026, 10, 25, 21, 0, tzinfo=timezone.utc)


class _Filas:
    def __init__(self, filas):
        self.filas = filas

    def all(self):
        return self.filas


class _Db:
    """Responde según la tabla consultada; registra cuántas consultas hubo."""

    def __init__(self):
        self.consultas = 0

    def execute(self, sql, params):
        self.consultas += 1
        sql = str(sql)
        if 'activos_biologicos' in sql:
            return _Filas([(829, None, 'Tilapia Roja')])
        if 'infraestructuras' in sql:
            return _Filas([(391, 'Estanque-01', 'Finca El Remanso')])
        if 'telemetrias' in sql:
            return _Filas([(115703, 'pH del agua', 'Sensor pH', Decimal('7.20'), 'pH', CAPTURA)])
        return _Filas([(137, 'Camila Nossa')])


def _vinculacion(id_telemetria, id_activo=None, id_usuario=None):
    return VinculacionLectura(
        id_vinculacion_lectura=1, id_telemetria=id_telemetria, modelo_manejo='POBLACIONAL',
        id_activo_biologico=id_activo, id_infraestructura=391, fecha_inicio_vinculacion=CAPTURA,
        fecha_fin_vinculacion=None, mecanismo_vinculacion='AUTOMATICO', estado_vinculacion='CONFIRMADA',
        id_usuario=id_usuario, motivo_correccion=None, id_vinculacion_reemplazada=None, fecha_creacion=CAPTURA,
    )


def test_resuelve_nombres_por_pagina_y_deja_vacio_lo_que_no_encuentra():
    db = _Db()
    con, sin = SqlAlchemyVinculacionLecturaRepository(db)._con_nombres([
        _vinculacion(115703, id_activo=829, id_usuario=137),
        _vinculacion(999),  # lectura que no aparece; sin activo ni usuario
    ])

    assert db.consultas == 4  # una por tabla, no una por fila
    assert (con.especie_activo, con.nombre_activo) == ('Tilapia Roja', None)
    assert (con.nombre_infraestructura, con.nombre_finca) == ('Estanque-01', 'Finca El Remanso')
    assert (con.nombre_variable, con.valor_lectura, con.unidad_lectura) == ('pH del agua', 7.2, 'pH')
    assert con.nombre_usuario == 'Camila Nossa'
    assert (sin.nombre_variable, sin.valor_lectura, sin.nombre_activo, sin.nombre_usuario) == (None, None, None, None)
