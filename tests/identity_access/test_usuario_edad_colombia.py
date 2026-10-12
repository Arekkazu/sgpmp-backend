"""RF-01: la edad mínima se calcula con el día de Colombia, no con el del
proceso (UTC en el contenedor), que desde las 19:00 ya va en el día siguiente.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

import src.shared.fechas as fechas
from src.identity_access.domain.entities.usuario import Usuario


def test_quien_cumple_18_manana_en_colombia_aun_no_es_mayor_de_edad(monkeypatch) -> None:
    # 2026-10-11 22:25 en Colombia == 2026-10-12 03:25 UTC
    monkeypatch.setattr(
        fechas, '_ahora', lambda: datetime(2026, 10, 12, 3, 25, tzinfo=timezone.utc).astimezone(fechas.ZONA_COLOMBIA),
    )
    # edad() solo lee fecha_nacimiento; no hace falta armar correo/contraseña.
    usuario = Usuario.__new__(Usuario)
    usuario.fecha_nacimiento = date(2008, 10, 12)

    assert usuario.edad() == 17
    assert not usuario.es_mayor_de_edad()
