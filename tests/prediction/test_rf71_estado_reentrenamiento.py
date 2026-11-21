# | Fecha      | Nombre   | Que se hizo                                                        |
# |------------|----------|--------------------------------------------------------------------|
# | 2026-10-31 | Arekkazu | RF-71: aviso de datos insuficientes para reentrenar el modelo individual |
# | 2026-10-31 | Arekkazu | RF-71/RF-73: solicitud de reentrenamiento como evento de auditoría |
"""RF-71: estado de datos para reentrenar los modelos individuales (aviso por debajo de 200)."""
from __future__ import annotations

from datetime import datetime, timezone

from unittest.mock import Mock

import pytest

from src.configuration.application.use_cases.configuracion_global.parametros_retroalimentacion_use_case import (
    ParametrosRetroalimentacionUseCase,
)
from src.configuration.domain.entities.parametro_mlops import (
    RF71_MIN_REENTRENAMIENTO,
    RF71_MIN_SOLICITUD,
    ParametroMLOps,
)
from src.prediction.application.use_cases.versiones_modelo.consultar_estado_reentrenamiento_use_case import (
    ConsultarEstadoReentrenamientoUseCase,
)
from src.prediction.domain.entities.estado_reentrenamiento import EstadoReentrenamiento
from src.shared.errors import ServiceUnavailableError

DESDE = datetime(2026, 10, 1, tzinfo=timezone.utc)


class _Parametros:
    def __init__(self, **valores):
        self.valores = {n: ParametroMLOps(n, v) for n, v in valores.items()}

    def bloquear_configuracion(self):
        pass

    def obtener(self, nombres):
        return {n: p for n, p in self.valores.items() if n in nombres}

    def guardar(self, parametros, id_usuario):
        self.valores.update({p.nombre: p for p in parametros})


class _Retro:
    def __init__(self, conteos):
        self.conteos = conteos

    def contar_nuevas_por_tipo_modelo(self, tipos_modelo):
        return {t: self.conteos[t] for t in tipos_modelo if t in self.conteos}


@pytest.mark.parametrize(("n", "estado", "faltan"), [
    (0, "INSUFICIENTE", 200), (199, "INSUFICIENTE", 1), (200, "PUEDE_SOLICITARSE", 300),
    (499, "PUEDE_SOLICITARSE", 1), (500, "LISTO", 0), (900, "LISTO", 0),
])
def test_estado_por_volumen(n, estado, faltan):
    e = EstadoReentrenamiento("MODELO_ESPECIES_GRANDES", n, DESDE, 200, 500)
    assert (e.estado, e.faltan) == (estado, faltan)


def test_sin_configurar_usa_los_valores_base():
    estados = ConsultarEstadoReentrenamientoUseCase(
        retroalimentacion_repo=_Retro({"MODELO_ESPECIES_GRANDES": (250, DESDE)}),
        parametros_port=_Parametros(),
    ).execute()
    grandes, medianas = estados
    assert (grandes.tipo_modelo, grandes.registros_nuevos, grandes.desde, grandes.estado) == (
        "MODELO_ESPECIES_GRANDES", 250, DESDE, "PUEDE_SOLICITARSE")
    assert (grandes.minimo_solicitud, grandes.minimo_reentrenamiento) == (200, 500)
    # Sin retroalimentaciones ni versión: avisa que faltan 200.
    assert (medianas.tipo_modelo, medianas.registros_nuevos, medianas.desde, medianas.estado, medianas.faltan) == (
        "MODELO_ESPECIES_MEDIANAS", 0, None, "INSUFICIENTE", 200)


def test_minimos_configurados_en_m09():
    (grandes, _) = ConsultarEstadoReentrenamientoUseCase(
        retroalimentacion_repo=_Retro({"MODELO_ESPECIES_GRANDES": (120, DESDE)}),
        parametros_port=_Parametros(**{RF71_MIN_SOLICITUD: 100, RF71_MIN_REENTRENAMIENTO: 120}),
    ).execute()
    assert grandes.estado == "LISTO"


def test_minimo_configurado_invalido_falla_expresamente():
    with pytest.raises(ServiceUnavailableError):
        ConsultarEstadoReentrenamientoUseCase(
            retroalimentacion_repo=_Retro({}), parametros_port=_Parametros(**{RF71_MIN_SOLICITUD: 0}),
        ).execute()


def test_m09_expone_y_cambia_los_minimos():
    parametros = _Parametros()
    use_case = ParametrosRetroalimentacionUseCase(Mock(), parametros)
    por_nombre = {p.nombre: p for p in use_case.consultar()}
    assert (por_nombre[RF71_MIN_SOLICITUD].valor, por_nombre[RF71_MIN_SOLICITUD].fuente) == (200, "VALOR_BASE")
    assert por_nombre[RF71_MIN_REENTRENAMIENTO].valor == 500
    por_nombre = {p.nombre: p for p in use_case.actualizar({RF71_MIN_SOLICITUD: 150}, id_usuario=1)}
    assert (por_nombre[RF71_MIN_SOLICITUD].valor, por_nombre[RF71_MIN_SOLICITUD].fuente) == (150, "CONFIGURADO")


# ── Solicitud (RF-71/RF-73) ─────────────────────────────────────────────────

class _Auditoria:
    def __init__(self, aceptado=True):
        self.eventos, self.aceptado = [], aceptado

    def registrar(self, **evento):
        from uuid import uuid4
        from src.prediction.domain.services.validacion_auditoria_m04 import ResultadoRegistroAuditoriaM04, validar_evento
        assert not validar_evento(tipo_evento=evento["tipo_evento"], tipo_actor=evento["tipo_actor"],
                                  id_usuario=evento.get("id_usuario"), id_sistema=evento.get("id_sistema"),
                                  id_referencia=evento.get("id_referencia"), payload_evento=evento["payload_evento"])
        self.eventos.append(evento)
        return ResultadoRegistroAuditoriaM04(self.aceptado, uuid4())


def _solicitar(conteo, auditoria=None, tipo="MODELO_ESPECIES_GRANDES"):
    from src.prediction.application.use_cases.versiones_modelo.solicitar_reentrenamiento_use_case import (
        SolicitarReentrenamientoUseCase,
    )
    db, auditoria = Mock(), auditoria or _Auditoria()
    estado = ConsultarEstadoReentrenamientoUseCase(
        retroalimentacion_repo=_Retro({"MODELO_ESPECIES_GRANDES": (conteo, DESDE)}), parametros_port=_Parametros())
    resultado = SolicitarReentrenamientoUseCase(db=db, estado_use_case=estado, auditoria_repo=auditoria).execute(
        tipo, "Brote en lote 3", 7)
    return resultado, auditoria, db


def test_solicitud_queda_en_la_bitacora():
    (estado, _), auditoria, db = _solicitar(230)
    assert estado.estado == "PUEDE_SOLICITARSE"
    [evento] = auditoria.eventos
    assert (evento["tipo_evento"], evento["id_usuario"], evento["id_referencia"]) == (
        "REENTRENAMIENTO_SOLICITADO", 7, "MODELO_ESPECIES_GRANDES")
    assert evento["payload_evento"]["registros_nuevos"] == 230
    assert evento["payload_evento"]["motivo"] == "Brote en lote 3"
    db.commit.assert_called_once()


def test_por_debajo_del_minimo_no_se_puede_solicitar():
    from src.shared.errors import BusinessRuleError
    with pytest.raises(BusinessRuleError) as exc:
        _solicitar(199)
    assert exc.value.code == "DATOS_INSUFICIENTES_REENTRENAMIENTO"


def test_solo_modelos_individuales():
    from src.shared.errors import ValidationError
    with pytest.raises(ValidationError):
        _solicitar(300, tipo="MODELO_AVES")


def test_evento_rechazado_no_confirma():
    from src.shared.errors import InfrastructureError
    with pytest.raises(InfrastructureError):
        _solicitar(300, auditoria=_Auditoria(aceptado=False))
