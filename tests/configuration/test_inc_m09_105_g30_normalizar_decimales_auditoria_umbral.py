"""INC-M09-105-G30 (#296) — observación 2: los snapshots de auditoría de umbrales
representaban el mismo valor con formato inconsistente ("42.0" vs "42.00"), según el
Decimal viniera recién parseado de un DTO o releído de BD. `modulo9.umbrales_ambientales`
y `modulo9.niveles_alerta_ambientales` son NUMERIC(_, 2), así que `_snapshot()` ahora
normaliza siempre a 2 decimales.
"""
from __future__ import annotations

from decimal import Decimal

from src.configuration.domain.entities.nivel_alerta_ambiental import NivelAlertaAmbiental
from src.configuration.domain.entities.umbral_ambiental import UmbralAmbiental
from src.configuration.domain.value_objects.nivel_alerta import NivelAlerta


def _umbral(valor_min: Decimal, valor_max: Decimal, limite_inferior: Decimal, limite_superior: Decimal) -> UmbralAmbiental:
    return UmbralAmbiental(
        id_especie=1,
        id_variable_ambiental=13,
        unidad_medida='°C',
        valor_min=valor_min,
        valor_max=valor_max,
        es_activo=True,
        niveles=[NivelAlertaAmbiental(nivel=NivelAlerta.normal, limite_inferior=limite_inferior, limite_superior=limite_superior)],
        id_umbral_ambiental=44,
    )


class TestSnapshotNormalizaDecimales:
    def test_valor_con_un_decimal_se_serializa_con_dos(self) -> None:
        umbral = _umbral(Decimal('42.0'), Decimal('45.0'), Decimal('42.0'), Decimal('43.0'))

        snapshot = umbral._snapshot()

        assert snapshot['valor_min'] == '42.00'
        assert snapshot['valor_max'] == '45.00'
        assert snapshot['niveles'][0]['limite_inferior'] == '42.00'
        assert snapshot['niveles'][0]['limite_superior'] == '43.00'

    def test_valor_con_dos_decimales_no_cambia(self) -> None:
        umbral = _umbral(Decimal('42.00'), Decimal('45.00'), Decimal('42.00'), Decimal('43.00'))

        snapshot = umbral._snapshot()

        assert snapshot['valor_min'] == '42.00'
        assert snapshot['valor_max'] == '45.00'

    def test_valor_entero_sin_decimales_se_normaliza_igual(self) -> None:
        umbral = _umbral(Decimal('42'), Decimal('45'), Decimal('42'), Decimal('43'))

        snapshot = umbral._snapshot()

        assert snapshot['valor_min'] == '42.00'
        assert snapshot['valor_max'] == '45.00'

    def test_dos_snapshots_del_mismo_valor_logico_son_textualmente_iguales(self) -> None:
        """Reproduce el reporte de QA: "42.0" (recién parseado) vs "42.00" (releído de BD)."""
        recien_parseado = _umbral(Decimal('42.0'), Decimal('45.0'), Decimal('42.0'), Decimal('43.0'))
        releido_de_bd = _umbral(Decimal('42.00'), Decimal('45.00'), Decimal('42.00'), Decimal('43.00'))

        assert recien_parseado._snapshot()['valor_min'] == releido_de_bd._snapshot()['valor_min']
        assert recien_parseado._snapshot()['niveles'] == releido_de_bd._snapshot()['niveles']
