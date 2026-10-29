# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-21 | Arekkazu | DEV-32 RF-57: notificación individual, tormenta (E8), contexto incompleto (E6), fallo (E7) y escalamiento |
# | 2026-10-28 | destroyerban | INC-M03-170-G77 RF-57 E6: el aviso de contexto incompleto sale sin anti-spam |
"""DEV-32 (RF-57 Fase 8, E6, E7, E8, E10)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.telemetry.application.use_cases.alertas.notificar_alertas_use_case import NotificarAlertasUseCase
from src.telemetry.application.use_cases.alertas.vencer_alertas_sla_use_case import VencerAlertasSlaUseCase
from src.telemetry.domain.entities.alerta import Alerta

AHORA = datetime(2026, 10, 21, 12, 0, tzinfo=timezone.utc)


class _Db:
    def commit(self): pass
    def rollback(self): pass


class _Bitacora:
    def __init__(self): self.eventos = []
    def registrar(self, evento):
        evento.id_evento = len(self.eventos) + 1
        self.eventos.append(evento)
        return evento


class _Alertas:
    def __init__(self, pendientes, total=0, por_area=None, tormenta_reciente=False):
        self.pendientes, self.total, self.por_area = pendientes, total, por_area or {}
        self.tormenta_reciente, self.guardadas = tormenta_reciente, []
    def reclamar_pendientes_notificacion(self, ahora, ventana_min=10, limite=100): return self.pendientes
    def contar_generadas_desde(self, desde): return self.total, self.por_area
    def existe_tormenta_desde(self, desde): return self.tormenta_reciente
    def contexto_incompleto_avisado_desde(self, id_sensor, desde, antes_de): return False
    def guardar(self, alerta):
        alerta.id_alerta = 900 + len(self.guardadas)
        self.guardadas.append(alerta)
        return alerta
    def vencer_activas_con_sla_cumplido(self, ahora, limite=200): return self.pendientes


class _Notificacion:
    def __init__(self, falla=False):
        self.enviadas, self.falla, self.reintentos = [], falla, 0
    def destinatarios(self, area, *, escalamiento): return [10, 11] if not escalamiento else [20]
    def administradores(self): return [1]
    def enviar(self, id_usuario, titulo, cuerpo, *, agrupable):
        self.enviadas.append((id_usuario, titulo, agrupable))
        return False if self.falla else True
    def reintentar_fallidas(self, ahora): self.reintentos += 1


class _Parametros:
    def __init__(self, umbrales=(20, 5)): self.umbrales = umbrales
    def obtener_umbrales_tormenta(self): return self.umbrales


def _alerta(id_, severidad="CRITICO", contexto_incompleto=False):
    return Alerta(id_alerta=id_, tipo_alerta="ESTRES_TERMICO", severidad=severidad, estado_alerta="ACTIVA",
                  origen_evento="EDGE", tipo_variable="TEMPERATURA", fecha_evento=AHORA, fecha_generacion=AHORA,
                  id_infraestructura=3, id_sensor=8, tiene_contexto_incompleto=contexto_incompleto)


def _uc(alertas, notificacion, parametros=None, bitacora=None):
    return NotificarAlertasUseCase(_Db(), alertas, notificacion, parametros or _Parametros(), bitacora or _Bitacora())


def test_sin_tormenta_cada_alerta_va_a_cada_destinatario():
    notif = _Notificacion()
    assert _uc(_Alertas([_alerta(1, "CRITICO"), _alerta(2, "LEVE")], total=2), notif).execute(AHORA) == 2
    assert [(u, a) for u, _, a in notif.enviadas] == [(10, False), (11, False), (10, True), (11, True)]
    assert notif.reintentos == 1  # E7: cada vuelta reintenta los fallidos


def test_tormenta_agrupa_leve_y_moderado_pero_no_critico_y_avisa_una_vez_al_admin():
    notif, alertas = _Notificacion(), _Alertas([_alerta(1, "CRITICO"), _alerta(2, "LEVE"), _alerta(3, "MODERADO")],
                                              total=25)
    _uc(alertas, notif).execute(AHORA)
    [tormenta] = alertas.guardadas
    assert tormenta.tipo_alerta == "TORMENTA_DE_ALERTAS" and tormenta.metadato_evento["alertas_ultimo_minuto"] == 25
    titulos = [(u, t) for u, t, _ in notif.enviadas]
    assert (1, "Alerta MODERADO: tormenta de alertas") in titulos
    assert sum(1 for u, t in titulos if t.startswith("Alerta CRITICO")) == 2      # individual a 10 y 11
    assert [(u, t) for u, t in titulos if t.startswith("Resumen")] == [(10, "Resumen de 2 alertas"),
                                                                       (11, "Resumen de 2 alertas")]


def test_tormenta_por_unidad_y_sin_repetir_la_alerta_en_la_ventana():
    notif, alertas = _Notificacion(), _Alertas([_alerta(2, "LEVE")], total=6, por_area={3: 6}, tormenta_reciente=True)
    _uc(alertas, notif).execute(AHORA)
    assert alertas.guardadas == []  # ya hubo una en los últimos 10 min
    assert [t for _, t, _ in notif.enviadas] == ["Resumen de 1 alertas", "Resumen de 1 alertas"]


def test_umbrales_sin_configurar_no_agrupan():
    notif, alertas = _Notificacion(), _Alertas([_alerta(2, "LEVE")], total=500)
    _uc(alertas, notif, _Parametros(None)).execute(AHORA)
    assert alertas.guardadas == [] and all(t.startswith("Alerta LEVE") for _, t, _ in notif.enviadas)


def test_contexto_incompleto_avisa_al_administrador():
    notif = _Notificacion()
    _uc(_Alertas([_alerta(5, "LEVE", contexto_incompleto=True)]), notif).execute(AHORA)
    # G77: el aviso de E6 no pasa por el anti-spam (antes True: otra notificación de alerta lo descartaba).
    assert (1, "Alerta sin contexto de activo biológico", False) in notif.enviadas


def test_fallo_de_entrega_queda_como_notificacion_fallida():
    bitacora = _Bitacora()
    _uc(_Alertas([_alerta(5)]), _Notificacion(falla=True), bitacora=bitacora).execute(AHORA)
    assert [e.tipo_evento for e in bitacora.eventos] == ["NOTIFICACION_FALLIDA"] * 2
    assert {e.accion_detallada["id_usuario_destinatario"] for e in bitacora.eventos} == {10, 11}


def test_vencer_por_sla_notifica_el_escalamiento_salvo_leve():
    notif = _Notificacion()
    vencidas = [_alerta(7, "CRITICO"), _alerta(8, "LEVE")]
    VencerAlertasSlaUseCase(_Db(), _Alertas(vencidas), _Bitacora(), notif).execute(AHORA)
    assert notif.enviadas == [(20, "Escalamiento: alerta CRITICO #7 sin atender", False)]
