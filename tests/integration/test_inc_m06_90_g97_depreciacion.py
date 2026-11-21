# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-13 | Arekkazu | INC-M06-90-G97 RF-88: depreciación lineal consultable y sin vida útil no se deprecia en un mes |
"""INC-M06-90-G97 / RF-88 pasos 4-6 y FA-2 contra el esquema real.

TC-M06-09: costo de 12.000.000 con vida útil de 6 años (72 meses) → 2.000.000 al año.
TC-M06-08: sin vida útil no hay cálculo (422), ni al reconocer al costo ni en el cierre, que antes
depreciaba todo el costo en un mes."""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal as D

import pytest
from sqlalchemy import text

from src.financial_valuation.domain.entities.contabilidad import ParametroEspecie
from src.shared.errors import AppError
from tests.integration.test_m06_flujo_nic41_integration import (  # noqa: F401 (fixtures)
    HOY,
    _activo,
    _configurar,
    _finca,
    _matriz,
    contador,
    m06,
)

pytestmark = pytest.mark.integration
ESPECIE = 3  # sin precios: el activo entra al costo
NIT, DV = "830095213", "0"


def _al_costo(db, m, uid, vida) -> int:
    finca = _finca(db, uid, nit=NIT, dv=DV)
    _configurar(m, uid, ESPECIE, vida=vida)
    _matriz(m, uid)
    activo = _activo(db, finca, uid, especie=ESPECIE, origen="compra", costo=D("12000000"))
    assert m.confirmar_reconocimiento().execute(activo, uid)["indicador_valoracion"] == "VALORACION_POR_COSTO"
    return activo


def test_depreciacion_lineal_de_12_millones_en_6_anios_es_2_millones_al_anio(db_session, m06, contador):
    activo = _al_costo(db_session, m06, contador["id_usuario"], vida=72)

    resultado = m06.consultar_depreciacion().execute(activo, HOY.replace(year=HOY.year + 1))

    assert resultado["vida_util_meses"] == 72 and resultado["meses_transcurridos"] == 12
    assert resultado["depreciacion_anual"] == D("2000000") and resultado["depreciacion_mensual"] == D("166666.6667")
    assert resultado["depreciacion_acumulada"] == D("2000000") and resultado["valor_contable"] == D("10000000")
    assert resultado["depreciacion_registrada"] == D("0")  # la registra el cierre, la consulta no
    assert m06.consultar_depreciacion().execute(activo, HOY)["depreciacion_acumulada"] == D("0")


def test_sin_vida_util_no_se_reconoce_al_costo_ni_se_calcula_ni_se_cierra(db_session, m06, contador):
    uid = contador["id_usuario"]
    finca = _finca(db_session, uid, nit=NIT, dv=DV)
    _configurar(m06, uid, ESPECIE, vida=None)
    sin_vida = _activo(db_session, finca, uid, especie=ESPECIE, origen="compra", costo=D("12000000"))
    with pytest.raises(AppError) as reconocer:  # TC-M06-08 por la vía que existe: el reconocimiento al costo
        m06.confirmar_reconocimiento().execute(sin_vida, uid)
    assert (reconocer.value.status_code, reconocer.value.code) == (422, "VIDA_UTIL_NO_CONFIGURADA")

    # Un registro al costo sin vida útil (anterior a la columna) tampoco se calcula ni se deprecia en un mes.
    activo = _al_costo(db_session, m06, uid, vida=72)
    db_session.execute(text("SET LOCAL session_replication_role = replica"))
    db_session.execute(text("UPDATE modulo6.valoraciones_por_costos SET vida_util_meses = NULL WHERE id_activo_biologico = :a"),
                       {"a": activo})
    db_session.execute(text("SET LOCAL session_replication_role = origin"))
    m06.guardar_parametro_especie().execute(ParametroEspecie(ESPECIE, "CONSUMO", "PESO_KG", None), uid)
    with pytest.raises(AppError) as consulta:
        m06.consultar_depreciacion().execute(activo, HOY + timedelta(days=40))
    assert (consulta.value.status_code, consulta.value.code) == (422, "VIDA_UTIL_NO_CONFIGURADA")

    periodo = m06.periodos.que_contiene(NIT, HOY)
    bloqueos = {b["codigo"]: b["mensaje"] for b in m06.cierre().prevalidar(periodo).bloqueos}
    assert f"M06-{activo}" in bloqueos["VIDA_UTIL_NO_CONFIGURADA"]
    with pytest.raises(AppError) as cierre:
        m06.cierre().execute(periodo.id_periodo_contable, uid)
    assert (cierre.value.status_code, cierre.value.code) == (422, "CIERRE_BLOQUEADO")

    # Con la vida útil de la especie configurada, el registro antiguo la usa (como el cierre).
    m06.guardar_parametro_especie().execute(ParametroEspecie(ESPECIE, "CONSUMO", "PESO_KG", 72), uid)
    assert m06.consultar_depreciacion().execute(activo, HOY)["vida_util_meses"] == 72
