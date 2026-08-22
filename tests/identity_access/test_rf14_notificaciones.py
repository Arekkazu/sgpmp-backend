"""Pruebas unitarias del servicio central y la bandeja RF-14."""
from datetime import datetime, timezone
import pytest

from src.identity_access.application.use_cases.notificaciones.listar_notificaciones_use_case import (
    ListarNotificacionesUseCase,
)
from src.identity_access.application.use_cases.notificaciones.marcar_notificacion_leida_use_case import (
    MarcarNotificacionLeidaUseCase,
)
from src.identity_access.domain.entities.notificacion import Notificacion
from src.shared import notificacion_service as service_module
from src.shared.errors import NotFoundError
from src.shared.notificacion_service import NotificacionService


class DbFake:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


class PortServicioFake:
    def __init__(self) -> None:
        self.registros = []
        self.estados = {}
        self.fcm_tokens = []
        self.tipo_evento_actual = None

    def buscar_estado_cuenta(self, _id_usuario):
        return 1

    def buscar_ultimo_evento_id(self, _id_usuario, tipo_evento):
        self.tipo_evento_actual = tipo_evento
        return 91

    def buscar_correo_usuario(self, _id_usuario):
        return "ana@example.com"

    def buscar_fcm_tokens(self, _id_usuario):
        return self.fcm_tokens

    def verificar_anti_spam(
        self,
        id_usuario,
        tipo_evento,
        id_canal,
        _ventana_minutos,
    ):
        return any(
            registro["id_usuario"] == id_usuario
            and registro["tipo_evento"] == tipo_evento
            and registro["id_canal"] == id_canal
            for registro in self.registros
        )

    def registrar(self, **datos):
        datos["tipo_evento"] = self.tipo_evento_actual
        self.registros.append(datos)
        return len(self.registros)

    def actualizar_estado(self, id_notificacion, estado):
        self.estados[id_notificacion] = estado


def test_servicio_central_no_persiste_token_y_aplica_anti_spam(monkeypatch) -> None:
    port = PortServicioFake()
    db = DbFake()
    correos = []
    monkeypatch.setattr(
        service_module,
        "send_email",
        lambda **datos: correos.append(datos),
    )

    servicio = NotificacionService(port=port, db=db)
    datos = {
        "tipo_evento": 1,
        "id_usuario": 7,
        "correo_destino": "ana@example.com",
        "asunto_email": "Activa tu cuenta",
        "contenido_html_email": "<a>token-super-secreto</a>",
    }
    servicio.notificar(**datos)
    servicio.notificar(**datos)

    assert len(port.registros) == 2
    assert {r["id_canal"] for r in port.registros} == {1, 2}
    assert all("token-super-secreto" not in r["mensaje"] for r in port.registros)
    assert correos == [
        {
            "to": "ana@example.com",
            "subject": "Activa tu cuenta",
            "html_body": "<a>token-super-secreto</a>",
        }
    ]
    assert port.estados == {1: "enviado", 2: "enviado"}


def test_bandeja_interna_sigue_entregada_si_firebase_falla(monkeypatch) -> None:
    port = PortServicioFake()
    port.fcm_tokens = ["dispositivo-sin-firebase"]
    db = DbFake()
    monkeypatch.setattr(service_module, "send_email", lambda **_datos: None)
    monkeypatch.setattr(service_module, "send_push", lambda **_datos: False)

    NotificacionService(port=port, db=db).notificar(
        tipo_evento=2,
        id_usuario=7,
        correo_destino="ana@example.com",
    )

    assert port.estados == {1: "enviado", 2: "enviado"}


class BandejaRepoFake:
    def __init__(self, notificaciones: list[Notificacion]) -> None:
        self.notificaciones = notificaciones
        self.guardada = None

    def listar_internas(self, id_usuario, solo_no_leidas, offset, limit):
        filas = [n for n in self.notificaciones if n.id_usuario == id_usuario]
        if solo_no_leidas:
            filas = [n for n in filas if not n.es_leido]
        return filas[offset : offset + limit]

    def contar_internas(self, id_usuario, solo_no_leidas):
        return len(self.listar_internas(id_usuario, solo_no_leidas, 0, 1000))

    def obtener_interna(self, id_notificacion, id_usuario):
        return next(
            (
                n
                for n in self.notificaciones
                if n.id_notificacion == id_notificacion
                and n.id_usuario == id_usuario
            ),
            None,
        )

    def guardar(self, notificacion):
        self.guardada = notificacion


def _notificacion(id_notificacion: int, id_usuario: int, leida: bool = False):
    return Notificacion(
        id_notificacion=id_notificacion,
        id_evento=100 + id_notificacion,
        tipo_evento=2,
        id_usuario=id_usuario,
        mensaje="Cuenta activada",
        fecha_envio=datetime.now(timezone.utc),
        es_leido=leida,
        estado_envio="enviado",
    )


def test_bandeja_lista_solo_propias_y_cuenta_no_leidas() -> None:
    repo = BandejaRepoFake(
        [_notificacion(1, 7), _notificacion(2, 7, True), _notificacion(3, 8)]
    )

    resultado = ListarNotificacionesUseCase(repo).execute(
        id_usuario=7,
        pagina=1,
        tamano=20,
        solo_no_leidas=False,
    )

    assert resultado["total"] == 2
    assert resultado["no_leidas"] == 1
    assert [n.id_notificacion for n in resultado["items"]] == [1, 2]


def test_marcar_leida_es_idempotente_y_no_permite_notificacion_ajena() -> None:
    propia = _notificacion(1, 7)
    repo = BandejaRepoFake([propia, _notificacion(2, 8)])
    db = DbFake()
    caso = MarcarNotificacionLeidaUseCase(repo, db)

    resultado = caso.execute(1, 7)
    repetido = caso.execute(1, 7)

    assert resultado.es_leido is True
    assert repetido.es_leido is True
    assert db.commits == 2

    with pytest.raises(NotFoundError) as error:
        caso.execute(2, 7)

    assert error.value.code == "NOTIFICACION_NO_ENCONTRADA"
