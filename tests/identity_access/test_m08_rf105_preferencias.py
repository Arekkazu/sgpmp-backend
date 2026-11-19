# | Fecha      | Nombre   | Que se hizo                                                     |
# |------------|----------|-----------------------------------------------------------------|
# | 2026-11-18 | Arekkazu | M08 RF-105 R6: canales por defecto y preferencias en la entrega |
"""RF-105 R6 — preferencias de canal: valores por defecto y entrega que las respeta (sin BD)."""
from __future__ import annotations

from datetime import datetime, timezone

from src.identity_access.application.use_cases.notificaciones.entregar_notificaciones_use_case import (
    EntregarNotificacionesUseCase,
)
from src.identity_access.application.use_cases.notificaciones.preferencias_notificacion_use_case import (
    ConsultarPreferenciasNotificacionUseCase,
)
from src.identity_access.domain.repositories.notificacion_repository import EntregaPendiente
from src.identity_access.domain.value_objects.nivel_notificacion import canal_por_defecto

AHORA = datetime(2026, 11, 18, 15, 0, tzinfo=timezone.utc)


def test_valores_por_defecto_del_rf():
    assert canal_por_defecto("CRITICA", "PUSH") and canal_por_defecto("CRITICA", "EMAIL")
    assert canal_por_defecto("ADVERTENCIA", "PUSH") and not canal_por_defecto("ADVERTENCIA", "EMAIL")
    assert not canal_por_defecto("INFORMATIVA", "PUSH") and not canal_por_defecto("INFORMATIVA", "EMAIL")


class Repo:
    def __init__(self, preferencias=None):
        self.prefs = preferencias or {}
        self.intentos, self.registrados = [], []

    def pendientes_de_entrega(self, limite):
        return [EntregaPendiente(1, 10, 7, "Fiebre en el galpón", "CRITICA", 0, "telemetria")]

    def canal_habilitado(self, id_usuario, nivel, canal):
        return self.prefs.get((nivel, canal), canal_por_defecto(nivel, canal))

    def preferencias(self, id_usuario):
        return self.prefs

    def buscar_fcm_tokens(self, id_usuario):
        return ["token"]

    def registrar_intento_push(self, id_notificacion, entregada, proximo):
        self.intentos.append(entregada)

    def buscar_correo_usuario(self, id_usuario):
        return "vet@example.com"

    def registrar(self, **kwargs):
        self.registrados.append(kwargs)
        return 99

    def actualizar_estado(self, *_):
        pass


class Db:
    def commit(self):
        pass

    def rollback(self):
        pass


def _entregar(repo):
    push, correo = [], []
    EntregarNotificacionesUseCase(Db(), repo, enviar_push=lambda **k: push.append(k) or True,
                                  enviar_correo=lambda **k: correo.append(k)).execute(AHORA)
    return push, correo


def test_sin_preferencias_la_critica_va_por_push_y_correo():
    push, correo = _entregar(Repo())
    assert len(push) == 1 and len(correo) == 1


def test_push_y_correo_apagados_no_se_envian_pero_la_bandeja_queda():
    repo = Repo({("CRITICA", "PUSH"): False, ("CRITICA", "EMAIL"): False})
    push, correo = _entregar(repo)
    assert push == [] and correo == [] and repo.intentos == [True]


def test_la_bandeja_siempre_esta_activa_y_no_es_editable():
    vista = ConsultarPreferenciasNotificacionUseCase(Repo({("ADVERTENCIA", "PUSH"): False})).execute(7)
    in_app = [v for v in vista if v["canal"] == "IN_APP"]
    assert len(in_app) == 3 and all(v["habilitado"] and not v["editable"] for v in in_app)
    push_adv = next(v for v in vista if v["nivel"] == "ADVERTENCIA" and v["canal"] == "PUSH")
    assert push_adv == {"nivel": "ADVERTENCIA", "canal": "PUSH", "habilitado": False, "por_defecto": False,
                        "editable": True}
