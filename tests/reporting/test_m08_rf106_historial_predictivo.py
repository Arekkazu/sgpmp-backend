# | Fecha      | Nombre   | Que se hizo                                                           |
# |------------|----------|-----------------------------------------------------------------------|
# | 2026-11-18 | Arekkazu | M08 RF-106: TVCO, conflictos, correspondencias, colisiones y degradación |
# | 2026-11-21 | Arekkazu | INC-M08-386-G018 RF-106: rango máximo de 24 meses por calendario |
"""RF-106 — historial clínico predictivo: reglas del dominio y aviso de degradación del modelo (sin BD)."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone

import pytest

from src.reporting.application.use_cases.historial.consultar_historial_predictivo_use_case import (
    ConsultarHistorialPredictivoUseCase,
)
from src.reporting.application.use_cases.reportes.generacion import Solicitante
from src.reporting.application.use_cases.historial.vigilar_degradacion_modelo_use_case import (
    TasaValidacionPort,
    VigilarDegradacionModeloUseCase,
)
from src.shared.errors import ValidationError
from src.reporting.domain.historial_predictivo import (
    Marcador,
    agrupar_colisiones,
    calcular_tvco,
    correspondencias,
    inicio_minimo,
    pendientes,
)

T0 = datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)


def _retro(inferencia: str, valoracion: str) -> dict:
    return {"id_resultado_inferencia": inferencia, "valoracion": valoracion}


def test_tvco_prueba_a_sin_conflicto():
    tvco = calcular_tvco(["a", "b", "c", "d", "e"], [_retro("a", "CORRECTO"), _retro("b", "CORRECTO"),
                                                       _retro("c", "CORRECTO"), _retro("d", "INCORRECTO")])
    assert tvco.porcentaje == 75 and tvco.validadas == 4
    assert tvco.texto == "75% (4 validadas; 1 excluida: sin retro)"


def test_tvco_prueba_b_con_conflicto_excluye_numerador_y_denominador():
    tvco = calcular_tvco(["a", "b", "c"], [_retro("a", "CORRECTO"), _retro("b", "CORRECTO"),
                                            _retro("b", "INCORRECTO")])
    assert tvco.porcentaje == 100 and tvco.con_conflicto == 1
    assert tvco.texto == "100% (1 validada; 2 excluidas: 1 conflicto + 1 sin retro)"


def test_dos_valoraciones_iguales_no_son_conflicto():
    tvco = calcular_tvco(["a"], [_retro("a", "CORRECTO"), _retro("a", "CORRECTO")])
    assert tvco.con_conflicto == 0 and tvco.porcentaje == 100


def test_sin_retroalimentacion_no_hay_datos_suficientes():
    tvco = calcular_tvco(["a"], [])
    assert tvco.porcentaje is None and tvco.texto == "Sin datos suficientes para calcular"


def test_rango_maximo_de_24_meses_por_calendario():
    # INC-M08-386-G018: 2024-11-19 → 2026-11-20 son 731 días y pasaba; 24 meses exactos empiezan el 2024-11-20.
    assert inicio_minimo(date(2026, 11, 20)) == date(2024, 11, 20)
    assert date(2024, 11, 19) < inicio_minimo(date(2026, 11, 20))
    assert inicio_minimo(date(2028, 2, 29)) == date(2026, 2, 28)


class _Fuente:
    def ubicar(self, _tipo, _id):
        return {"id_finca": 1, "estado": "ACTIVO"}

    def inferencias(self, **_):
        return []

    def eventos_sanitarios_aislados(self, **_):
        return [{"id_evento": 9, "tipo": "CONTROL_PREVENTIVO", "descripcion": "Vacuna", "id_veterinario": None,
                 "fecha": T0, "fuente": "M02"}]

    def retroalimentaciones(self, **_):
        return []

    def parametro(self, _nombre):
        return None

    def nombres_usuarios(self, _ids):
        return {}

    def ficha(self, _id):
        return {}


@contextmanager
def _abrir(_usuario, _zona):
    yield _Fuente()


def _consultar(**kw):
    solicitante = Solicitante(id_usuario=1, nombre="Vet", permitidos=set(), fincas=None)
    return ConsultarHistorialPredictivoUseCase(_abrir).execute(5, solicitante, **kw)


def test_un_dia_mas_de_24_meses_es_400_y_24_exactos_pasan():
    with pytest.raises(ValidationError) as error:
        _consultar(fecha_inicio=date(2024, 11, 19), fecha_fin=date(2026, 11, 20))
    assert error.value.field == "fecha_inicio"
    assert _consultar(fecha_inicio=date(2024, 11, 20), fecha_fin=date(2026, 11, 20))["rango_fechas_aplicado"] == {
        "fecha_inicio": "2024-11-20", "fecha_fin": "2026-11-20"}


def test_el_tipo_clinico_del_evento_no_pisa_el_tipo_del_marcador():
    # INC-M08-388-G021 OBS-7: «tipo» llegaba como CONTROL_PREVENTIVO y la vista no lo reconocía como evento.
    evento = _consultar(fecha_inicio=date(2026, 10, 1), fecha_fin=date(2026, 11, 20))["eventos_sanitarios"][0]
    assert evento["tipo"] == "EVENTO_SANITARIO" and evento["tipo_evento"] == "CONTROL_PREVENTIVO"


def test_correspondencia_dentro_y_fuera_de_la_ventana():
    prediccion = Marcador("PREDICCION", T0, {"id_resultado_inferencia": "a"})
    cerca = Marcador("EVENTO_SANITARIO", T0 + timedelta(hours=10), {"id_evento": 1})
    lejos = Marcador("EVENTO_SANITARIO", T0 + timedelta(hours=20), {"id_evento": 2})
    pares = correspondencias([prediccion], [cerca, lejos], timedelta(hours=12))
    assert [p["id_evento"] for p in pares] == [1] and pares[0]["diferencia"] == "Diferencia: 10 h"


def test_colision_de_media_hora_agrupa_con_la_retroalimentacion_primero():
    grupos = agrupar_colisiones([
        Marcador("PREDICCION", T0), Marcador("EVENTO_SANITARIO", T0 + timedelta(minutes=10)),
        Marcador("RETROALIMENTACION", T0 + timedelta(minutes=30)), Marcador("PREDICCION", T0 + timedelta(hours=5)),
    ])
    assert [m.tipo for m in grupos[0]] == ["RETROALIMENTACION", "EVENTO_SANITARIO", "PREDICCION"]
    assert len(grupos) == 2


def test_pendientes_de_mas_de_48_horas_por_riesgo_y_fecha():
    ahora = T0 + timedelta(days=5)
    inferencias = [
        {"id_resultado_inferencia": "a", "fecha_inferencia": T0, "nivel_riesgo": 1},
        {"id_resultado_inferencia": "b", "fecha_inferencia": T0 + timedelta(hours=1), "nivel_riesgo": 3},
        {"id_resultado_inferencia": "c", "fecha_inferencia": T0 + timedelta(hours=2), "nivel_riesgo": 3},
        {"id_resultado_inferencia": "d", "fecha_inferencia": ahora - timedelta(hours=10), "nivel_riesgo": 3},
        {"id_resultado_inferencia": "e", "fecha_inferencia": T0, "nivel_riesgo": 2},
    ]
    lista = pendientes(inferencias, {"e"}, ahora)
    assert [i["id_resultado_inferencia"] for i in lista] == ["c", "b", "a"]


class Tasa(TasaValidacionPort):
    def __init__(self, porcentaje, validadas, avisado=False):
        self.valor, self.validadas, self.avisado, self.avisos = porcentaje, validadas, avisado, []

    def tvco_global(self, dias):
        return self.valor, self.validadas

    def umbral(self):
        return 60

    def avisado_hoy(self):
        return self.avisado

    def avisar_administradores(self, mensaje, detalle):
        self.avisos.append(mensaje)


def test_degradacion_avisa_bajo_el_umbral_con_muestra_suficiente():
    tasa = Tasa(45.5, 20)
    assert VigilarDegradacionModeloUseCase(tasa).execute() is True
    assert "45.5 %" in tasa.avisos[0] and "umbral 60 %" in tasa.avisos[0]


def test_degradacion_no_avisa_con_poca_muestra_ni_dos_veces_el_mismo_dia():
    assert VigilarDegradacionModeloUseCase(Tasa(10, 3)).execute() is False
    assert VigilarDegradacionModeloUseCase(Tasa(10, 30, avisado=True)).execute() is False
    assert VigilarDegradacionModeloUseCase(Tasa(80, 30)).execute() is False
