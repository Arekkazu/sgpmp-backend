# | Fecha      | Nombre   | Que se hizo                                                         |
# |------------|----------|---------------------------------------------------------------------|
# | 2026-11-14 | Arekkazu | M08 RF-105: ciclo de vida, niveles, entrega con reintentos y agrupación |
# | 2026-11-18 | Arekkazu | M08 RF-105: los falsos responden preferencias por defecto y ventana de M09 |
# | 2026-11-19 | Arekkazu | M8-05 RF-105: los inicios de sesión no entran a la bandeja |
"""RF-105 — ciclo de vida de las notificaciones, nivel por tipo, entrega en segundo plano y agrupación.

Sin BD: entidad y casos de uso con falsos. Los CHECK de la BD (crítica no descartable, acción de
20+ caracteres) se verifican en la prueba de la migración.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from src.identity_access.domain.value_objects.nivel_notificacion import canal_por_defecto
from src.identity_access.application.use_cases.notificaciones.entregar_notificaciones_use_case import (
    EntregarNotificacionesUseCase,
)
from src.identity_access.domain.entities.notificacion import Notificacion
from src.identity_access.domain.repositories.notificacion_repository import EntregaPendiente
from src.identity_access.domain.value_objects.nivel_notificacion import (
    destino_por_defecto,
    modulo_desde,
    nivel_para,
    titulo_push,
)
from src.shared import notificacion_service as service_module
from src.shared.errors import BusinessRuleError, FlowError, ValidationError
from src.shared.notificacion_service import NotificacionService

AHORA = datetime(2026, 11, 14, 15, 0, tzinfo=timezone.utc)


def _notificacion(nivel="CRITICA", estado="NUEVA") -> Notificacion:
    return Notificacion(id_notificacion=1, id_evento=10, tipo_evento=32, id_usuario=7, mensaje="Fiebre en el lote",
                        fecha_envio=AHORA, es_leido=estado != "NUEVA", estado_envio="enviado", nivel=nivel,
                        estado=estado)


# ── Ciclo de vida (Fase 4, CA-2, CA-3) ────────────────────────────────────────

@pytest.mark.parametrize("accion", ["ok", " " * 20, "aaaaaaaaaaaaaaaaaaaaaaaa", "ok ok ok ok ok ok ok ok", None])
def test_critica_no_se_atiende_sin_una_accion_que_diga_algo(accion):
    with pytest.raises(ValidationError) as exc:
        _notificacion().atender(accion, AHORA)
    assert exc.value.field == "accion_documentada"


def test_critica_se_atiende_con_una_accion_descriptiva():
    n = _notificacion()
    n.atender("  Se revisó el bebedero y se cambió la válvula  ", AHORA)
    assert (n.estado, n.es_leido, n.fecha_atencion, n.fecha_lectura) == ("ATENDIDA", True, AHORA, AHORA)
    assert n.accion_documentada == "Se revisó el bebedero y se cambió la válvula"


def test_critica_no_se_descarta():
    with pytest.raises(BusinessRuleError) as exc:
        _notificacion().descartar(AHORA)
    assert exc.value.code == "CRITICA_NO_DESCARTABLE"


def test_advertencia_se_atiende_sin_accion_y_se_descarta():
    atendida = _notificacion(nivel="ADVERTENCIA")
    atendida.atender(None, AHORA)
    assert atendida.estado == "ATENDIDA"

    descartada = _notificacion(nivel="INFORMATIVA", estado="LEIDA")
    descartada.descartar(AHORA)
    assert (descartada.estado, descartada.fecha_descarte) == ("DESCARTADA", AHORA)


@pytest.mark.parametrize("estado", ["ATENDIDA", "DESCARTADA"])
def test_cerrada_no_vuelve_a_cambiar(estado):
    n = _notificacion(nivel="ADVERTENCIA", estado=estado)
    with pytest.raises(FlowError):
        n.atender("Se revisó todo de nuevo con calma", AHORA)
    with pytest.raises(FlowError):
        n.descartar(AHORA)


def test_leer_no_reabre_una_atendida():
    n = _notificacion(estado="ATENDIDA")
    n.marcar_como_leida(AHORA)
    assert n.estado == "ATENDIDA"


def test_puede_descartarse_solo_lo_no_critico_y_abierto():
    assert not _notificacion().puede_descartarse
    assert _notificacion(nivel="ADVERTENCIA").puede_descartarse
    assert not _notificacion(nivel="ADVERTENCIA", estado="ATENDIDA").puede_descartarse


# ── Nivel, módulo y destino ───────────────────────────────────────────────────

@pytest.mark.parametrize("tipo,sugerido,esperado", [
    ("NOTIFICACION_ALERTA", None, "ADVERTENCIA"),
    ("NOTIFICACION_ALERTA", "CRITICA", "CRITICA"),       # se puede subir
    ("ALERTA_INTEGRACION_CONTABLE", "INFORMATIVA", "CRITICA"),  # nunca bajar
    ("LOGIN_EXITOSO", None, "INFORMATIVA"),
    (None, None, "INFORMATIVA"),
])
def test_nivel_por_tipo_se_sube_pero_no_se_baja(tipo, sugerido, esperado):
    assert nivel_para(tipo, sugerido) == esperado


@pytest.mark.parametrize("texto,esperado", [
    ("MODULO3", "telemetria"), ("Modulo 2", "activos"), ("modulo1", "cuentas"), (None, None), ("", None),
])
def test_modulo_se_normaliza_venga_como_venga(texto, esperado):
    assert modulo_desde(texto) == esperado


def test_destino_y_titulo_sin_codigos_internos():
    assert destino_por_defecto("finanzas") == "finanzas"
    assert destino_por_defecto(None) == "dashboard"
    assert titulo_push("CRITICA", "integracion") == "Alerta crítica · Integración contable"
    assert titulo_push("ADVERTENCIA", None) == "SIGAB"


# ── Entrega en segundo plano (Fase 3, restricción 5, CA-7) ────────────────────

class DbFake:
    def __init__(self):
        self.commits = 0

    def commit(self):
        self.commits += 1

    def rollback(self):
        pass


class RepoEntregaFake:
    canal_habilitado = staticmethod(lambda _u, nivel, canal: canal_por_defecto(nivel, canal))

    def __init__(self, pendientes, tokens=("t1",)):
        self.pendientes = pendientes
        self.tokens = list(tokens)
        self.intentos = []
        self.registros = []
        self.estados = {}

    def pendientes_de_entrega(self, limite):
        return self.pendientes

    def buscar_fcm_tokens(self, id_usuario):
        return self.tokens

    def registrar_intento_push(self, id_notificacion, entregada, proximo_intento):
        self.intentos.append((id_notificacion, entregada, proximo_intento))

    def buscar_correo_usuario(self, id_usuario):
        return "ana@example.com"

    def registrar(self, **datos):
        self.registros.append(datos)
        return 900

    def actualizar_estado(self, id_notificacion, estado):
        self.estados[id_notificacion] = estado


def _pendiente(nivel="CRITICA", intentos=0) -> EntregaPendiente:
    return EntregaPendiente(id_notificacion=5, id_evento=10, id_usuario=7, mensaje="Exportación fallida",
                            nivel=nivel, intentos_push=intentos, modulo="integracion",
                            contexto={"url": "integracion"})


def _entregar(repo, push_ok=True):
    pushes, correos = [], []

    def push(**datos):
        pushes.append(datos)
        return push_ok

    EntregarNotificacionesUseCase(DbFake(), repo, enviar_push=push,
                                  enviar_correo=lambda **d: correos.append(d)).execute(AHORA)
    return pushes, correos


def test_critica_sale_por_push_con_sus_datos_y_por_correo_una_vez():
    repo = RepoEntregaFake([_pendiente()])
    pushes, correos = _entregar(repo)

    assert repo.intentos == [(5, True, None)]
    assert pushes[0]["datos"] == {"url": "integracion", "id_notificacion": 5, "nivel": "CRITICA"}
    assert pushes[0]["titulo"] == "Alerta crítica · Integración contable"
    assert [c["to"] for c in correos] == ["ana@example.com"]
    assert repo.registros[0]["id_canal"] == 1 and repo.estados == {900: "enviado"}


def test_advertencia_no_va_por_correo():
    _, correos = _entregar(RepoEntregaFake([_pendiente(nivel="ADVERTENCIA")]))
    assert correos == []


@pytest.mark.parametrize("intentos_previos,espera", [(0, 1), (1, 5), (2, 15)])
def test_push_fallido_se_reintenta_a_1_5_y_15_minutos(intentos_previos, espera):
    repo = RepoEntregaFake([_pendiente(nivel="ADVERTENCIA", intentos=intentos_previos)])
    _entregar(repo, push_ok=False)
    assert repo.intentos == [(5, False, AHORA + timedelta(minutes=espera))]


def test_tras_el_tercer_reintento_queda_solo_en_la_bandeja(caplog):
    repo = RepoEntregaFake([_pendiente(nivel="ADVERTENCIA", intentos=3)])
    _entregar(repo, push_ok=False)
    assert repo.intentos == [(5, False, None)]
    assert "queda en la bandeja" in caplog.text


def test_reintento_de_una_critica_no_repite_el_correo():
    _, correos = _entregar(RepoEntregaFake([_pendiente(intentos=1)]))
    assert correos == []


def test_sin_dispositivos_queda_entregada_en_la_bandeja():
    repo = RepoEntregaFake([_pendiente(nivel="ADVERTENCIA")], tokens=())
    pushes, _ = _entregar(repo)
    assert pushes == [] and repo.intentos == [(5, True, None)]


# ── Servicio de RF-14: nivel, agrupación y datos del push ─────────────────────

class PortServicioFake:
    canal_habilitado = staticmethod(lambda _u, nivel, canal: canal_por_defecto(nivel, canal))
    ventana_agrupacion_minutos = staticmethod(lambda: 5)

    def __init__(self, agrupa=False):
        self.agrupa = agrupa
        self.registros = []
        self.estados = {}
        self.ocurrencias = []

    def buscar_estado_cuenta(self, _id):
        return 2

    def buscar_ultimo_evento_id(self, _id, _tipo):
        return 91

    def buscar_correo_usuario(self, _id):
        return None

    def buscar_fcm_tokens(self, _id):
        return ["tok"]

    def verificar_anti_spam(self, *_):
        return False

    def sumar_ocurrencia(self, id_usuario, tipo_evento, id_activo, ventana):
        self.ocurrencias.append((id_usuario, tipo_evento, id_activo, ventana))
        return self.agrupa

    def registrar(self, **datos):
        self.registros.append(datos)
        return len(self.registros)

    def actualizar_estado(self, id_notificacion, estado):
        self.estados[id_notificacion] = estado


def test_misma_alerta_del_mismo_animal_suma_una_ocurrencia_sin_otro_push(monkeypatch):
    pushes = []
    monkeypatch.setattr(service_module, "send_push", lambda **d: pushes.append(d) or True)
    port = PortServicioFake(agrupa=True)

    NotificacionService(port=port, db=DbFake()).notificar(
        tipo_evento=32, id_usuario=7, nivel="CRITICA", id_activo_biologico=44, aplicar_anti_spam_interno=False)

    assert port.ocurrencias == [(7, 32, 44, 5)]
    assert port.registros == [] and pushes == []


def test_push_de_alerta_lleva_destino_y_nivel_y_se_reintenta_si_falla(monkeypatch):
    pushes = []
    monkeypatch.setattr(service_module, "send_push", lambda **d: pushes.append(d) and False)
    port = PortServicioFake()

    NotificacionService(port=port, db=DbFake()).notificar(
        tipo_evento=32, id_usuario=7, nivel="CRITICA", id_activo_biologico=44,
        datos_push={"url": "telemetria/alertas", "id_infraestructura": 3}, aplicar_anti_spam_interno=False)

    interna = port.registros[0]
    assert (interna["nivel"], interna["id_activo_biologico"], interna["entrega_inmediata"]) == ("CRITICA", 44, True)
    assert pushes[0]["datos"] == {"url": "telemetria/alertas", "id_infraestructura": 3,
                                  "id_notificacion": 1, "nivel": "CRITICA"}
    assert port.estados[1] == "fallido"  # el entregador lo reintenta


def test_aviso_de_cuenta_sin_nivel_sigue_como_antes_aunque_el_push_falle(monkeypatch):
    monkeypatch.setattr(service_module, "send_push", lambda **d: False)
    port = PortServicioFake()
    NotificacionService(port=port, db=DbFake()).notificar(tipo_evento=6, id_usuario=7)
    assert port.estados[1] == "enviado"


def test_inicio_de_sesion_va_solo_por_correo_y_no_entra_a_la_bandeja(monkeypatch):
    pushes = []
    monkeypatch.setattr(service_module, "send_push", lambda **d: pushes.append(d) or True)
    port = PortServicioFake()
    for tipo in (3, 20):  # LOGIN_EXITOSO y LOGIN_SSO_EXITOSO (M8-05)
        NotificacionService(port=port, db=DbFake()).notificar(tipo_evento=tipo, id_usuario=7)
    assert [r["id_canal"] for r in port.registros] == [1, 1] and pushes == []
