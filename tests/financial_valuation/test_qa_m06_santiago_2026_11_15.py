# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-15 | Arekkazu | QA-M06 CU09 H-01, CU-COT H-01, CU08 H-02: trazabilidad del costo manual, alcance de cotizaciones y productos |
"""QA manual de M06 (Santiago, 15-11, TEST rc.70).

- CU09 H-01: la línea de mano de obra propia nunca pasaba la trazabilidad («falta auditoria_m02»): un costo
  manual no nace de un evento biológico, así que no hay auditoría de M02 que exigir (RF-91 paso 5).
- CU-COT H-01: el Contador veía cotizaciones de otros titulares (la RLS le da visión completa).
- CU08 H-02: el Contador no lee Configuración → Métricas; los productos llegan con la configuración contable."""
from __future__ import annotations

from src.financial_valuation.domain.services.trazabilidad import verificar_cadena
from src.financial_valuation.infrastructure.repositories.configuracion_contable_repository import (
    SqlAlchemyConfiguracionContableRepository,
)
from src.financial_valuation.infrastructure.repositories.cotizacion_repository import SqlAlchemyCotizacionRepository
from src.financial_valuation.infrastructure.repositories.sql import ES_ADMINISTRADOR, PERIODOS_DE_MIS_FINCAS

_SIN_EVENTO = {"origen": True, "evento_m02": None, "lecturas_nic41": None, "precio_documentado": None,
               "cierre": None, "evento_sanitario": None, "auditoria_m02": False, "ids": {}}


def test_costo_manual_sin_evento_biologico_queda_verificado():
    assert verificar_cadena("REGISTRO_MANUAL", dict(_SIN_EVENTO)) == ("VERIFICADO", [], None)


def test_linea_de_evento_sin_auditoria_m02_sigue_pendiente():
    estado, faltantes, nivel = verificar_cadena("REGISTRO_MANUAL", {**_SIN_EVENTO, "evento_m02": True})
    assert (estado, faltantes, nivel) == ("PENDIENTE_TRAZABILIDAD", ["auditoria_m02"], 2)


def test_iot_sin_lecturas_exige_tambien_sus_auditorias():
    eslabones = {**_SIN_EVENTO, "evento_m02": False, "lecturas_nic41": False, "auditoria_m03": False}
    estado, faltantes, _ = verificar_cadena("IOT_DIRECTO", eslabones)
    assert estado == "PENDIENTE_TRAZABILIDAD"
    assert {"evento_m02", "lecturas_nic41", "auditoria_m02", "auditoria_m03"} <= set(faltantes)


class _Db:
    """Guarda el SQL de cada consulta; no devuelve filas."""

    def __init__(self):
        self.sql: list[str] = []

    def execute(self, sql, _params=None):
        self.sql.append(str(sql))
        return self

    def mappings(self):
        return self

    def first(self):
        return None

    def all(self):
        return []

    def __iter__(self):
        return iter([])


def test_cotizaciones_se_acotan_a_los_titulares_de_las_fincas_del_usuario():
    db = _Db()
    repo = SqlAlchemyCotizacionRepository(db)
    repo.listar({})
    repo.obtener(7)
    for sql in db.sql:
        assert ES_ADMINISTRADOR in sql
        assert f"c.id_periodo_contable IN ({PERIODOS_DE_MIS_FINCAS})" in sql


def test_la_configuracion_trae_los_productos_activos_de_cada_especie():
    db = _Db()
    SqlAlchemyConfiguracionContableRepository(db).listar_parametros_especie()
    assert "FROM modulo9.metricas_produccion m WHERE m.id_especie = e.id_especie AND m.es_activo" in db.sql[0]
    assert "AS productos" in db.sql[0]


def test_el_ajuste_de_periodo_anterior_encuentra_su_origen():
    from src.financial_valuation.domain.entities.contabilidad import LineaAsiento
    from src.financial_valuation.infrastructure.repositories.trazabilidad_repository import (
        SqlAlchemyTrazabilidadRepository,
    )

    db = _Db()
    linea = LineaAsiento(tipo_hecho="AJUSTE_PERIODO_ANTERIOR", sentido="UNICO", valor=1, fecha_hecho=None,
                         id_periodo_contable=1, id_activo_biologico=1, id_especie=1, id_finca=1,
                         numero_id_tributaria="900", tabla_origen="lineas_asiento_nic41", id_origen=9,
                         tipo_evidencia="REGISTRO_MANUAL")
    SqlAlchemyTrazabilidadRepository(db).eslabones(linea)
    assert "FROM modulo6.lineas_asiento_nic41 WHERE id_linea_asiento_nic41 = :id" in db.sql[0]


def test_la_matriz_rechaza_el_gasto_de_mano_de_obra_contra_el_activo():
    import pytest

    from src.financial_valuation.application.use_cases.configuracion.guardar_asignacion_cuenta_use_case import (
        GuardarAsignacionCuentaUseCase,
    )
    from src.shared.errors import BusinessRuleError

    caso = GuardarAsignacionCuentaUseCase(db=None, config=None, asientos=None, auditoria=None)
    for tipo in ("MANO_OBRA_PROPIA", "CONSUMO_INSUMO"):
        with pytest.raises(BusinessRuleError) as error:
            caso.execute(tipo, "UNICO", None, None, "158405", "250505", 1)
        assert error.value.code == "CUENTA_DEBITO_NO_ES_GASTO"
        assert "158405" not in error.value.message
