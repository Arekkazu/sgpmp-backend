# | Fecha      | Nombre         | Que se hizo                                                                  |
# |------------|----------------|------------------------------------------------------------------------------|
# | 2026-11-12 | LuisfNarvaez01 | INC-M06-358-G71/G72 y INC-M06-359-G79 RF-93: bajas sin venta, excluidos y ceros |
"""Estado de resultados (RF-93).

- INC-M06-358-G71/G72 (#1083): la baja sin venta (``BAJA_ACTIVO`` / ``PERDIDA``) se descartaba; ahora
  suma en ``bajas_activos`` (gasto).
- INC-M06-359-G79 (#1084): los activos excluidos del cierre quedan fuera de todos los componentes (no
  solo listados) y se listan con sus montos; los montos salen con 4 decimales («0.0000»).
"""
from decimal import Decimal as D

from src.financial_valuation.application.services.reportes import ConstructorEstadoResultados
from src.financial_valuation.domain.services.consolidacion import MovimientoResultado, estado_resultados


def test_baja_sin_venta_suma_en_gastos():
    er = estado_resultados([MovimientoResultado("BAJA_ACTIVO", "PERDIDA", D("1200"))], [])
    assert er.componentes["bajas_activos"] == D("1200")
    assert er.total_gastos == D("1200") and er.resultado_neto == D("-1200")


def test_baja_por_venta_sigue_en_gastos_y_ambas_se_suman():
    er = estado_resultados([MovimientoResultado("BAJA_ACTIVO", "UNICO", D("500")),
                            MovimientoResultado("BAJA_ACTIVO", "PERDIDA", D("300"))], [])
    assert er.componentes["bajas_activos"] == D("800")


class _Reportes:
    def __init__(self, lineas):
        self.lineas = lineas
        self.estado = None

    def movimientos(self, id_periodo, filtros):
        excluir = set(filtros.get("excluir_activos") or ())
        solo = filtros.get("id_activo_biologico")
        return [ln for ln in self.lineas
                if ln["id_activo_biologico"] not in excluir and (solo is None or ln["id_activo_biologico"] == solo)]

    def siguiente_version_estado(self, id_periodo):
        return "V1"

    def agregar_estado(self, datos):
        self.estado = datos
        return 1


class _Costos:
    def __init__(self, costos):
        self.costos = costos

    def del_periodo(self, id_periodo, filtros=None):
        filtros = filtros or {}
        excluir = set(filtros.get("excluir_activos") or ())
        solo = filtros.get("id_activo_biologico")
        return [c for c in self.costos
                if c["id_activo_biologico"] not in excluir and (solo is None or c["id_activo_biologico"] == solo)]


def _linea(activo, tipo, sentido, valor):
    return {"id_activo_biologico": activo, "tipo_hecho": tipo, "sentido": sentido, "valor": valor, "es_reverso": False}


def _costo(activo, monto):
    return {"id_activo_biologico": activo, "naturaleza_costo": "MANTENIMIENTO", "politica_capitalizacion": None,
            "monto_costo": monto, "es_reverso": False, "subtipo_costo": "ALIMENTO"}


def test_activo_excluido_del_cierre_no_suma_y_se_lista_con_sus_montos():
    reportes = _Reportes([_linea(1, "VARIACION_VR_TB", "GANANCIA", "1000"),
                          _linea(943, "VARIACION_VR_TB", "GANANCIA", "700")])
    constructor = ConstructorEstadoResultados(reportes, _Costos([_costo(1, "100"), _costo(943, "40")]))

    resultado = constructor.guardar(7, {}, 5, [{"id_activo_biologico": 943, "identificador": "BOV-943",
                                                "motivo": "PENDIENTE_PRECIO"}])

    assert resultado["componentes"]["ganancia_transformacion_biologica"] == "1000.0000"
    assert resultado["componentes"]["costos_mantenimiento"] == "100.0000"
    assert resultado["resultado_neto"] == D("900.0000")
    [excluido] = reportes.estado["componentes"]["activos_excluidos_cierre"]
    assert excluido["id_activo_biologico"] == 943 and excluido["identificador"] == "BOV-943"
    assert excluido["montos_excluidos"]["componentes"] == {"ganancia_transformacion_biologica": "700.0000",
                                                           "costos_mantenimiento": "40.0000"}
    assert excluido["montos_excluidos"]["resultado_neto"] == "660.0000"


def test_componente_sin_movimientos_se_serializa_con_cuatro_decimales():
    resultado = ConstructorEstadoResultados(_Reportes([]), _Costos([])).calcular(7, {})
    assert set(resultado["componentes"].values()) == {"0.0000"}
    assert set(resultado["desglose_costos_mantenimiento"].values()) == {"0.0000"}
    assert str(resultado["resultado_neto"]) == "0.0000"
