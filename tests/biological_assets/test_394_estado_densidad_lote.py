# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-10 | Arekkazu | #394 RF-36: estado de la densidad del lote frente al límite de su etapa o especie |
"""#394: la ficha del lote dice si su densidad está dentro, cerca o por encima del máximo, y de dónde sale."""
from decimal import Decimal as D

from src.biological_assets.application.use_cases._capacidad_area import _validar_densidad_etapa
from src.biological_assets.domain.repositories.infraestructura_consulta_port import InfraestructuraConsulta, LimiteEtapa
from src.biological_assets.domain.services.densidad_lote import evaluar_densidad
from src.shared.errors import BusinessRuleError

CEBA = LimiteEtapa(nombre_etapa="Ceba", densidad_maxima=D("2"), biomasa_maxima=D("900"), aviso_preventivo_pct=85)


def test_gana_el_maximo_mas_estricto_y_avisa_desde_el_porcentaje_de_la_etapa():
    e = evaluar_densidad(cantidad=88, superficie=D("50"), densidad_especie=D("3"), limite_etapa=CEBA, biomasa_total=D("30000"))
    assert (e.estado, e.fuente, e.densidad_maxima, e.capacidad_maxima, e.cupo_disponible) == ("AVISO", "ETAPA", D("2"), 100, 12)
    assert e.porcentaje_del_maximo == D("88.00") and e.biomasa_por_m2 == D("600.00")


def test_dentro_excede_y_sin_configurar():
    assert evaluar_densidad(cantidad=50, superficie=D("50"), densidad_especie=None, limite_etapa=CEBA).estado == "OK"
    assert evaluar_densidad(cantidad=101, superficie=D("50"), densidad_especie=None, limite_etapa=CEBA).estado == "EXCEDE"
    especie = evaluar_densidad(cantidad=10, superficie=D("50"), densidad_especie=D("1"), limite_etapa=None)
    assert (especie.estado, especie.fuente, especie.aviso_preventivo_pct) == ("OK", "ESPECIE", 90)
    assert evaluar_densidad(cantidad=10, superficie=D("50"), densidad_especie=None, limite_etapa=None).estado == "SIN_CONFIGURAR"


def test_entrada_que_supera_la_etapa_dice_cuantos_caben():
    area = InfraestructuraConsulta(id_infraestructura=1, nombre="Corral 2", tipo="CORRAL", es_activo=True, superficie=D("50"))
    _validar_densidad_etapa(CEBA, area, 100)  # cabe justo
    _validar_densidad_etapa(LimiteEtapa("Cría", None, None, 90), area, 10_000)  # sin densidad no limita
    try:
        _validar_densidad_etapa(CEBA, area, 101)
        raise AssertionError("debió rechazar")
    except BusinessRuleError as exc:
        assert exc.code == "DENSIDAD_ETAPA_EXCEDIDA"
        assert "caben como máximo 100 animales en Corral 2" in exc.message and "quedaría con 101" in exc.message


def test_el_listado_completa_el_estado_de_los_lotes_con_una_consulta():
    from types import SimpleNamespace as N

    from src.biological_assets.infrastructure.routers.activo_biologico_router import _completar_estado_densidad

    lote = N(id_activo_biologico=7, tipo="POBLACIONAL", estado_densidad=None,
             detalle_poblacional=N(cantidad_actual=95, biomasa_total=None))
    individual = N(id_activo_biologico=8, tipo="INDIVIDUAL", estado_densidad=None, detalle_poblacional=None)
    fila = N(id_activo_biologico=7, superficie=D("50"), densidad_area=D("3"), etapa="Ceba",
             densidad_maxima=D("2"), biomasa_maxima=None, aviso_preventivo_pct=90)
    consultas = []
    db = N(execute=lambda sql, params: consultas.append(params) or [fila])

    _completar_estado_densidad(db, [lote, individual])
    assert consultas == [{"ids": [7]}]
    assert (lote.estado_densidad.estado, lote.estado_densidad.fuente, lote.estado_densidad.cupo_disponible) == ("AVISO", "ETAPA", 5)
    assert individual.estado_densidad is None
