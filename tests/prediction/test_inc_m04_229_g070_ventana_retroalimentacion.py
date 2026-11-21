# | Fecha      | Nombre   | Que se hizo                                                        |
# |------------|----------|--------------------------------------------------------------------|
# | 2026-10-30 | Arekkazu | INC-M04-229-G070 RF-72: ventana desde M09 y ampliación por resultado |
# | 2026-10-31 | Arekkazu | RF-71: la sección también trae los mínimos de reentrenamiento     |
"""RF-72 (#865): ventana global administrable (7..365) y excepción para un resultado."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest

from src.configuration.application.use_cases.configuracion_global.parametros_retroalimentacion_use_case import (
    ParametrosRetroalimentacionUseCase,
)
from src.configuration.domain.entities.parametro_mlops import RF72_VENTANA, ParametroMLOps
from src.prediction.application.use_cases.retroalimentacion.ampliar_ventana_retroalimentacion_use_case import (
    AmpliarVentanaRetroalimentacionUseCase,
)
from src.prediction.application.use_cases.retroalimentacion.registrar_retroalimentacion_use_case import (
    RegistrarRetroalimentacionUseCase,
)
from src.prediction.domain.services.validacion_auditoria_m04 import validar_evento
from src.prediction.infrastructure.dto.registrar_retroalimentacion_dto import RegistrarRetroalimentacionDTO
from src.shared.errors import BusinessRuleError, NotFoundError, ValidationError


class _Parametros:
    def __init__(self):
        self.valores: dict[str, ParametroMLOps] = {}

    def bloquear_configuracion(self):
        pass

    def obtener(self, nombres):
        return {n: p for n, p in self.valores.items() if n in nombres}

    def guardar(self, parametros, id_usuario):
        self.valores.update({p.nombre: p for p in parametros})


@pytest.mark.parametrize("dias, aceptado", [(6, False), (7, True), (8, True), (365, True), (366, False), (90.5, False)])
def test_ventana_global_respeta_7_a_365(dias, aceptado):
    parametros = _Parametros()
    use_case = ParametrosRetroalimentacionUseCase(Mock(), parametros)
    if aceptado:
        p = next(x for x in use_case.actualizar({RF72_VENTANA: dias}, 1) if x.nombre == RF72_VENTANA)
        assert (p.valor, p.fuente) == (dias, "CONFIGURADO")
    else:
        with pytest.raises(ValidationError):
            use_case.actualizar({RF72_VENTANA: dias}, 1)
        assert RF72_VENTANA not in parametros.valores


def test_ventana_global_no_acepta_otros_parametros():
    with pytest.raises(ValidationError) as exc:
        ParametrosRetroalimentacionUseCase(Mock(), _Parametros()).actualizar({"rf62_k": 2}, 1)
    assert exc.value.code == "PARAMETRO_RETROALIMENTACION_INVALIDO"


class _Ampliaciones:
    def __init__(self):
        self.filas = []

    def guardar(self, entidad):
        entidad.id_ampliacion_ventana_retroalimentacion = len(self.filas) + 1
        self.filas.append(entidad)
        return entidad

    def fecha_limite_vigente(self, id_resultado):
        fechas = [a.fecha_limite for a in self.filas if a.id_resultado_inferencia == id_resultado]
        return max(fechas, default=None)


def _resultados(*ids):
    resultados = Mock()
    vencidos = {i: {"fecha_inferencia": datetime.now(timezone.utc) - timedelta(days=120),
                    "id_activo_biologico": 885, "activo_en_baja": False} for i in ids}
    resultados.obtener_por_id.side_effect = vencidos.get
    return resultados


def _registrar(resultados, ampliaciones):
    repo = Mock()
    repo.obtener_por_resultado_y_usuario.return_value = None
    repo.listar_por_resultado.return_value = []
    repo.guardar.side_effect = lambda e: e
    parametros = _Parametros()
    parametros.valores[RF72_VENTANA] = ParametroMLOps(RF72_VENTANA, 90, 7, 365)
    return RegistrarRetroalimentacionUseCase(
        db=Mock(), repo=repo, resultado_port=resultados, patologia_repo=Mock(), auditoria_repo=Mock(),
        parametros_port=parametros, ampliacion_repo=ampliaciones,
    )


def _dto(id_resultado):
    return RegistrarRetroalimentacionDTO(
        id_resultado_inferencia=id_resultado, id_activo_biologico=885, estado_retroalimentacion="CORRECTO",
    )


def test_ampliacion_habilita_solo_el_resultado_autorizado_y_se_audita():
    a, b = uuid.uuid4(), uuid.uuid4()
    resultados, ampliaciones, auditoria = _resultados(a, b), _Ampliaciones(), Mock()
    registrar = _registrar(resultados, ampliaciones)

    for vencido in (a, b):
        with pytest.raises(BusinessRuleError) as exc:
            registrar.execute(_dto(vencido), 7)
        assert exc.value.code == "FUERA_DE_VENTANA_TEMPORAL"

    AmpliarVentanaRetroalimentacionUseCase(
        db=Mock(), repo=ampliaciones, resultado_port=resultados, auditoria_repo=auditoria,
    ).execute(id_resultado_inferencia=a, dias_habilitados=5, justificacion="Necropsia tardía del lote", id_usuario=1)

    assert registrar.execute(_dto(a), 7).id_resultado_inferencia == a
    with pytest.raises(BusinessRuleError) as exc:
        registrar.execute(_dto(b), 7)
    assert exc.value.code == "FUERA_DE_VENTANA_TEMPORAL"

    evento = auditoria.registrar.call_args.kwargs
    assert evento["tipo_evento"] == "VENTANA_RETROALIMENTACION_AMPLIADA"
    assert evento["payload_evento"]["justificacion"] == "Necropsia tardía del lote"
    assert validar_evento(
        tipo_evento=evento["tipo_evento"], tipo_actor=evento["tipo_actor"], id_usuario=evento["id_usuario"],
        id_sistema=None, id_referencia=evento["id_referencia"], payload_evento=evento["payload_evento"],
    ) == ()


def test_ampliacion_vencida_no_habilita():
    a = uuid.uuid4()
    ampliaciones = _Ampliaciones()
    AmpliarVentanaRetroalimentacionUseCase(
        db=Mock(), repo=ampliaciones, resultado_port=_resultados(a), auditoria_repo=Mock(),
    ).execute(id_resultado_inferencia=a, dias_habilitados=1, justificacion="Excepción de prueba", id_usuario=1)
    ampliaciones.filas[0].fecha_limite = datetime.now(timezone.utc) - timedelta(minutes=1)
    with pytest.raises(BusinessRuleError):
        _registrar(_resultados(a), ampliaciones).execute(_dto(a), 7)


def test_ampliacion_de_resultado_inexistente_es_404():
    with pytest.raises(NotFoundError):
        AmpliarVentanaRetroalimentacionUseCase(
            db=Mock(), repo=_Ampliaciones(), resultado_port=_resultados(), auditoria_repo=Mock(),
        ).execute(id_resultado_inferencia=uuid.uuid4(), dias_habilitados=5, justificacion="x" * 10, id_usuario=1)
