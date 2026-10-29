# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-28 | destroyerban | INC-M03-170-G77 RF-57 E6: aviso al administrador sin anti-spam y uno por sensor sin BD |
"""INC-M03-170-G77: el aviso de contexto incompleto (E6) sale siempre, una vez por sensor cada 24 h."""
from datetime import timedelta

from tests.telemetry.test_dev32_rf57_notificaciones import AHORA, _Alertas, _alerta, _Notificacion, _uc

_TITULO = "Alerta sin contexto de activo biológico"


def _con_sensor(id_alerta, sensor):
    a = _alerta(id_alerta, "LEVE", contexto_incompleto=True)
    a.id_sensor = sensor
    return a


class _AlertasConHistorial(_Alertas):
    def __init__(self, pendientes, avisados=()):
        super().__init__(pendientes)
        self.avisados, self.consultas = set(avisados), []

    def contexto_incompleto_avisado_desde(self, id_sensor, desde, antes_de):
        self.consultas.append((id_sensor, desde, antes_de))
        return id_sensor in self.avisados


def _avisos(notif):
    return [u for u, titulo, agrupable in notif.enviadas if titulo == _TITULO and agrupable is False]


def test_el_aviso_no_usa_anti_spam():
    notif = _Notificacion()
    _uc(_AlertasConHistorial([_con_sensor(1, 8)]), notif).execute(AHORA)
    assert _avisos(notif) == [1]


def test_un_aviso_por_sensor_en_la_misma_vuelta():
    notif = _Notificacion()
    alertas = _AlertasConHistorial([_con_sensor(1, 8), _con_sensor(2, 8), _con_sensor(3, 9)])
    _uc(alertas, notif).execute(AHORA)
    assert len(_avisos(notif)) == 2
    assert [s for s, _, _ in alertas.consultas] == [8, 9]
    assert all((desde, antes) == (AHORA - timedelta(hours=24), AHORA) for _, desde, antes in alertas.consultas)


def test_sensor_ya_avisado_en_24_horas_no_se_repite():
    notif = _Notificacion()
    _uc(_AlertasConHistorial([_con_sensor(1, 8)], avisados={8}), notif).execute(AHORA)
    assert _avisos(notif) == []


def test_alerta_sin_sensor_avisa_siempre():
    notif = _Notificacion()
    _uc(_AlertasConHistorial([_con_sensor(1, None)]), notif).execute(AHORA)
    assert _avisos(notif) == [1]
