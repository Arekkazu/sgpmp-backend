"""INC-M02-72-G80 (RF-48, C2): valida contra Postgres real que la tabla
modulo9.compatibilidades_tipo_area_especie y el adapter que la consulta
reflejan la regla real (Estanque solo compatible con especies acuicolas).
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from src.biological_assets.infrastructure.adapters.infraestructura_m09_adapter import InfraestructuraM09Adapter

ID_ESPECIE_BOVINO_MIGUEL = 11
ID_ESPECIE_TILAPIA = 10


def test_estanque_rechaza_bovino_y_acepta_pez(db_session: Session):
    adapter = InfraestructuraM09Adapter(db_session)

    assert adapter.es_tipo_compatible('Estanque', ID_ESPECIE_BOVINO_MIGUEL) is False
    assert adapter.es_tipo_compatible('Estanque', ID_ESPECIE_TILAPIA) is True


def test_tipo_sin_regla_configurada_es_compatible_por_defecto(db_session: Session):
    adapter = InfraestructuraM09Adapter(db_session)

    # Corral no tiene ninguna fila en compatibilidades_tipo_area_especie todavia
    # -> sin restriccion configurada, no debe bloquear nada.
    assert adapter.es_tipo_compatible('Corral', ID_ESPECIE_BOVINO_MIGUEL) is True
