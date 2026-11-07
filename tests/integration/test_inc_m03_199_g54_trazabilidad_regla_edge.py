# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-28 | destroyerban | INC-M03-199-G54 RF-55: el backend conserva la regla del evento compuesto (evento, paquete, alerta) |
"""INC-M03-199-G54 (RF-55 §6): trazabilidad de la regla en eventos DESVIACION_COMPUESTA.

Solo cubre la parte del backend (punto 3 del ticket): lo que el nodo emite llega sin perderse al
evento, al paquete de RF-56 y a la alerta de RF-57. Que el nodo Edge evalúe la regla y emita los
campos (puntos 1 y 2) es del firmware y queda bloqueado.
"""
import pytest
from sqlalchemy import text

from tests.integration.test_rf56_dev17_paquetes_pendientes import _payload, client, hardware, modelos  # noqa: F401

pytestmark = pytest.mark.integration

REGLA = {"regla_aplicada": 7, "nombre_regla": "ESTRES_TERMICO_GALPON", "version_regla": 3}


def _guardado(db, id_evento):
    evento = db.execute(text("SELECT metadatos FROM modulo3.eventos_edge_computing WHERE id_evento_edge_computing=:id"),
                        {"id": id_evento}).scalar_one()
    paquete = db.execute(text("SELECT metadatos FROM modulo3.paquetes_inferencia WHERE id_evento_edge_computing=:id"),
                         {"id": id_evento}).scalar_one()
    alerta = db.execute(text("SELECT metadato_evento FROM modulo3.alertas WHERE id_evento_edge_computing=:id"),
                        {"id": id_evento}).scalar_one_or_none()
    return evento, paquete, alerta


@pytest.mark.parametrize("transporte", ["nivel_superior", "metadata_edge"])
def test_evento_compuesto_conserva_la_regla_de_punta_a_punta(client, db_session, hardware, transporte):
    cuerpo = _payload(hardware, "DESVIACION_COMPUESTA")
    if transporte == "nivel_superior":
        cuerpo.update(REGLA)
    else:
        cuerpo["metadata_edge"] = {**cuerpo["metadata_edge"], **REGLA}
    r = client.post("/iot/eventos-edge", json=cuerpo)
    assert r.status_code == 201, r.text
    evento, paquete, alerta = _guardado(db_session, r.json()["id_evento_edge_computing"])
    assert alerta is not None  # severidad MODERADO: RF-57 genera la alerta del evento
    for campo, valor in REGLA.items():
        assert evento[campo] == valor and paquete[campo] == valor and alerta[campo] == valor, campo
    assert evento["trazabilidad_regla_completa"] is True
    assert evento["origen_prueba"] == "DEV-17"  # el resto de metadata_edge sigue intacto


def test_evento_compuesto_sin_regla_se_acepta_y_queda_marcado(client, db_session, hardware):
    """La obligatoriedad espera el contrato aprobado: hoy se acepta, pero queda visible que falta."""
    r = client.post("/iot/eventos-edge", json=_payload(hardware, "DESVIACION_COMPUESTA"))
    assert r.status_code == 201, r.text
    evento, paquete, _ = _guardado(db_session, r.json()["id_evento_edge_computing"])
    assert evento["trazabilidad_regla_completa"] is False
    assert not any(c in paquete for c in REGLA)


def test_regla_contradictoria_entre_nivel_superior_y_metadata_edge_es_400(client, db_session, hardware):
    cuerpo = {**_payload(hardware, "DESVIACION_COMPUESTA"), **REGLA}
    cuerpo["metadata_edge"] = {**cuerpo["metadata_edge"], "version_regla": 4}
    r = client.post("/iot/eventos-edge", json=cuerpo)
    assert r.status_code == 400 and r.json()["error_code"] == "VAL_ENTRADA", r.text


def test_evento_simple_no_se_marca(client, db_session, hardware):
    r = client.post("/iot/eventos-edge", json={**_payload(hardware, "DESVIACION_SIMPLE"), **REGLA})
    assert r.status_code == 201, r.text
    evento, _, _ = _guardado(db_session, r.json()["id_evento_edge_computing"])
    assert "trazabilidad_regla_completa" not in evento and evento["nombre_regla"] == "ESTRES_TERMICO_GALPON"
