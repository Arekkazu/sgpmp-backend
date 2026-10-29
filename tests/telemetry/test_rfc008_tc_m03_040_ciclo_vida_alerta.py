"""RFC-008 / TC-M03-040 (RF-57 v1.1): CERRADA no es un estado de alerta.

El cierre se instrumenta con RESUELTA, DESCARTADA o VENCIDA; cualquier transición
hacia CERRADA se rechaza con 422. RFC-008 no cambió código: esto fija lo ratificado.
"""
from datetime import datetime, timezone

import pytest

from src.shared.errors import BusinessRuleError
from src.telemetry.domain.entities.alerta import Alerta, EstadoAlerta


def _alerta(estado: str) -> Alerta:
    ahora = datetime.now(timezone.utc)
    return Alerta(
        tipo_alerta="ESTRES_TERMICO", severidad="MODERADO", estado_alerta=estado,
        origen_evento="BACKEND", tipo_variable="TEMPERATURA_AMBIENTAL", fecha_evento=ahora, fecha_generacion=ahora,
    )


def test_cerrada_no_es_un_estado_del_catalogo():
    assert "CERRADA" not in {e.value for e in EstadoAlerta}


@pytest.mark.parametrize("desde", [e.value for e in EstadoAlerta])
def test_ninguna_transicion_hacia_cerrada_es_valida(desde):
    with pytest.raises(BusinessRuleError) as e:
        _alerta(desde).transicionar("CERRADA", id_usuario=1, motivo=None)
    assert e.value.status_code == 422 and e.value.code == "TRANSICION_INVALIDA"


@pytest.mark.parametrize(
    "desde, hacia",
    [("ACTIVA", "EN_ATENCION"), ("EN_ATENCION", "RESUELTA"), ("ACTIVA", "DESCARTADA"), ("ACTIVA", "VENCIDA")],
)
def test_las_transiciones_de_cierre_ratificadas_son_validas(desde, hacia):
    alerta = _alerta(desde)
    alerta.transicionar(hacia, id_usuario=1, motivo="falso positivo")
    assert alerta.estado_alerta == hacia
