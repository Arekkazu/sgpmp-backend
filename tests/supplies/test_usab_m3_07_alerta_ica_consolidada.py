# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-25 | Arekkazu | USAB-M03 M3-07 RF-74: recalcular el ICA no duplica la alerta abierta |
"""M3-07: CONVERSION_ALIMENTICIA con el mismo valor aparecía 4 veces en 3 minutos."""
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

from src.supplies.infrastructure.adapters.alerta_ica_m03_adapter import AlertaICAM03Adapter


class _Db:
    def __init__(self, abierta):
        self.abierta = abierta
        self.sentencias = []

    def execute(self, sql, params):
        self.sentencias.append('UPDATE' if 'UPDATE' in str(sql) else 'INSERT')
        fila = SimpleNamespace(id_alerta=self.abierta) if self.abierta else None
        if self.sentencias[-1] == 'INSERT':
            fila = SimpleNamespace(id_alerta=99)
        return SimpleNamespace(fetchone=lambda: fila)

    def flush(self):
        pass


def _generar(db):
    return AlertaICAM03Adapter(db).generar_alerta_critica(
        id_activo_biologico=1, ca_calculado=Decimal('6.7226'), periodo_evaluacion='MENSUAL',
        origen_evento='BACKEND', fecha_evento=datetime(2026, 7, 30, tzinfo=timezone.utc))


def test_con_alerta_abierta_consolida_y_no_inserta():
    db = _Db(abierta=37)
    assert _generar(db) == 37
    assert db.sentencias == ['UPDATE']


def test_sin_alerta_abierta_inserta_una_nueva():
    db = _Db(abierta=None)
    assert _generar(db) == 99
    assert db.sentencias == ['UPDATE', 'INSERT']
