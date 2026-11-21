"""TC-M03-G55 — RF-56 / CU-02.

Subcasos: TC-M03-090 (estructura), TC-M03-091 (envío real M04), TC-M03-092 (fragmentación).

La fragmentación vigente no parte 501 variables de un evento: un evento genera un
PaqueteInferencia y DrenarPaquetesPendientesUseCase envía pendientes en lotes ≤500.

La integración HTTP (TC-M03-091) queda deshabilitada salvo G55_M04_INTEGRATION=1 y
IOT_INFERENCIA_M04_URL de TEST. No hay POST /inferencia en este backend: el cliente
POST a IOT_INFERENCIA_M04_URL (las pruebas G63 usan /inferencia/paquetes).
"""
from __future__ import annotations

import dataclasses
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import Mock

import pytest

from src.shared.errors import BusinessRuleError, ValidationError
from src.telemetry.application.use_cases.inferencia.consolidar_paquete_inferencia_use_case import (
    ConsolidarEnviarPaqueteUseCase,
)
from src.telemetry.application.use_cases.inferencia.drenar_paquetes_pendientes_use_case import (
    DrenarPaquetesPendientesUseCase,
)
from src.telemetry.domain.entities.telemetria import (
    CLAVE_HUELLA_CONTENIDO,
    MAX_REGISTROS_POR_ENVIO_INFERENCIA,
    EstadoPaqueteInferencia,
    PaqueteInferencia,
    TipoEventoEdge,
)
from src.telemetry.domain.repositories.motor_inferencia_port import MotorInferenciaPort
from src.telemetry.domain.repositories.paquete_inferencia_repository import (
    PaqueteInferenciaRepository,
)
from src.telemetry.infrastructure.adapters.motor_inferencia_http_adapter import (
    MotorInferenciaHttpAdapter,
)
from src.telemetry.infrastructure.adapters.motor_inferencia_stub_adapter import (
    MotorInferenciaStubAdapter,
)

_MODULO3 = Path(__file__).resolve().parents[2]
if str(_MODULO3) not in sys.path:
    sys.path.insert(0, str(_MODULO3))
from rf56_dobles import (  # noqa: E402
    MotorObservado,
    PaqueteInferenciaRepoMemoria,
    SesionNula,
    ahora_utc,
    evento_para_consolidar,
)

_EVIDENCIAS = Path(__file__).resolve().parent / "Resultados" / "evidencias" / "run-2026-10-31-g55"
_BASE = datetime(2026, 10, 31, 12, 0, tzinfo=timezone.utc)

_CAMPOS_SERIALIZACION_ADAPTER = (
    "id_sensor",
    "id_dispositivo_iot",
    "id_evento_edge_computing",
    "tipo_variable",
    "valor_numerico",
    "estado_calidad",
    "fecha_envio",
    "estado_paquete",
    "intento_envios",
    "contexto_incompleto",
    "id_paquetes_inferencia",
    "unidad",
    "estado_desviacion",
    "severidad",
    "origen",
    "contexto_ambiental",
    "metadatos",
    "id_version_modelo",
)


def _consolidar(motor: MotorObservado, evento=None):
    repo = PaqueteInferenciaRepoMemoria()
    use_case = ConsolidarEnviarPaqueteUseCase(
        db=SesionNula(),
        paquete_repo=repo,
        motor_inferencia_port=motor,
    )
    return use_case.execute(evento or evento_para_consolidar()), repo, motor


def _volcar_json(nombre: str, payload) -> Path:
    _EVIDENCIAS.mkdir(parents=True, exist_ok=True)
    destino = _EVIDENCIAS / nombre
    destino.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    return destino


class _RepoPendientesMemoria(PaqueteInferenciaRepository):
    """Cola de pendientes en memoria (mismo contrato que INC-M03-112)."""

    def __init__(self, cantidad: int) -> None:
        self.paquetes = {
            i: PaqueteInferencia(
                id_paquetes_inferencia=i,
                id_sensor=3,
                id_dispositivo_iot=2,
                id_evento_edge_computing=i,
                tipo_variable="TEMPERATURA_AMBIENTAL",
                valor_numerico=Decimal("38.5"),
                estado_calidad="LECTURA_VALIDA",
                fecha_envio=_BASE + timedelta(milliseconds=i),
                estado_paquete="PENDIENTE",
                intento_envios=0,
                contexto_incompleto=False,
            )
            for i in range(1, cantidad + 1)
        }

    def obtener_por_evento(self, id_evento, *, bloquear_evento=False):
        ...

    def obtener(self, id_paquete, *, ids_fincas_permitidas=None):
        ...

    def guardar(self, paquete):
        ...

    def actualizar_estado(self, id_paquete, estado, intento, fecha_intento=None):
        cambios = dict(estado_paquete=estado, intento_envios=intento)
        if fecha_intento is not None:
            cambios["fecha_envio"] = fecha_intento
        self.paquetes[id_paquete] = dataclasses.replace(self.paquetes[id_paquete], **cambios)

    def listar_pendientes(self, limite):
        pendientes = [p for p in self.paquetes.values() if p.estado_paquete == "PENDIENTE"]
        return pendientes[:limite]


def _motor_lote(**kw):
    motor = Mock(spec=MotorInferenciaPort)
    motor.enviar_lote.configure_mock(**kw)
    return motor


def test_tc_m03_090_estructura_paquete_desde_evento_desviacion() -> None:
    paquete, repo, motor = _consolidar(MotorObservado(exito=False))
    assert paquete is not None
    assert paquete.id_paquetes_inferencia is not None
    assert paquete.tipo_variable == "TEMPERATURA_AMBIENTAL"
    assert paquete.estado_desviacion == TipoEventoEdge.DESVIACION_SIMPLE
    tipos = {v["tipo_variable"] for v in paquete.contexto_ambiental["AMBIENTAL"]}
    assert tipos == {"TEMPERATURA_AMBIENTAL", "HUMEDAD_RELATIVA"}
    assert paquete.contexto_incompleto is False
    assert paquete.metadatos["clasificacion_rf55"] == TipoEventoEdge.DESVIACION_SIMPLE
    assert "timestamp_captura" in paquete.metadatos
    assert "timestamp_procesamiento_edge" in paquete.metadatos
    assert paquete.severidad == "MODERADO"
    assert len(repo.guardados) == 1
    assert motor.exito is False
    assert paquete.estado_paquete == EstadoPaqueteInferencia.PENDIENTE
    assert paquete.intento_envios == 1
    assert repo.estados == [
        (paquete.id_paquetes_inferencia, EstadoPaqueteInferencia.PENDIENTE, 1)
    ]
    assert len(motor.paquetes) == 1


def test_tc_m03_090_serializacion_json_contrato_adapter() -> None:
    """El cuerpo que viajaría a M04 es {paquetes: [asdict(PaqueteInferencia)]} (G63)."""
    paquete, _, _ = _consolidar(MotorObservado(exito=False))
    cuerpo = {"paquetes": [dataclasses.asdict(paquete)]}
    serializado = json.dumps(cuerpo, default=str)
    parsed = json.loads(serializado)
    registro = parsed["paquetes"][0]
    for campo in _CAMPOS_SERIALIZACION_ADAPTER:
        assert campo in registro
    assert registro["id_paquetes_inferencia"] is not None
    assert registro["id_sensor"] is not None
    assert registro["id_dispositivo_iot"] is not None
    assert registro["tipo_variable"]
    assert registro["valor_numerico"] is not None
    assert registro["unidad"] is not None
    assert registro["estado_calidad"] == "LECTURA_VALIDA"
    assert registro["estado_desviacion"]
    assert registro["severidad"]
    assert registro["origen"]
    assert registro["id_version_modelo"] is None
    assert "area_id" not in registro
    assert CLAVE_HUELLA_CONTENIDO in registro["metadatos"]
    _volcar_json("tc_m03_090_paquete.json", parsed)


def test_tc_m03_090_normal_no_genera_paquete() -> None:
    paquete, repo, motor = _consolidar(
        MotorObservado(exito=False),
        evento_para_consolidar(clasificacion_rf55=TipoEventoEdge.NORMAL),
    )
    assert paquete is None
    assert repo.guardados == []
    assert motor.paquetes == []


def test_tc_m03_090_desviacion_compuesta_conserva_clasificacion() -> None:
    paquete, repo, motor = _consolidar(
        MotorObservado(exito=False),
        evento_para_consolidar(clasificacion_rf55=TipoEventoEdge.DESVIACION_COMPUESTA),
    )
    assert paquete.estado_desviacion == TipoEventoEdge.DESVIACION_COMPUESTA
    assert paquete.metadatos["clasificacion_rf55"] == TipoEventoEdge.DESVIACION_COMPUESTA
    assert paquete.estado_paquete == EstadoPaqueteInferencia.PENDIENTE
    assert len(repo.guardados) == 1
    assert motor.exito is False
    assert len(motor.paquetes) == 1


def test_tc_m03_090_mapeo_puerto_true_es_enviado_del_puerto_no_m04() -> None:
    paquete, repo, motor = _consolidar(MotorObservado(exito=True))
    assert motor.exito is True
    assert paquete.estado_paquete == EstadoPaqueteInferencia.ENVIADO
    assert paquete.intento_envios == 1
    assert repo.estados == [
        (paquete.id_paquetes_inferencia, EstadoPaqueteInferencia.ENVIADO, 1)
    ]
    assert len(motor.paquetes) == 1


def test_tc_m03_090_error_configuracion_consolida_si_se_invoca_directo() -> None:
    """Consolidar solo omite NORMAL. Recibir no llama a este camino (FA-07 / G59)."""
    paquete, repo, motor = _consolidar(
        MotorObservado(exito=False),
        evento_para_consolidar(clasificacion_rf55=TipoEventoEdge.ERROR_CONFIGURACION),
    )
    assert paquete is not None
    assert paquete.estado_desviacion == TipoEventoEdge.ERROR_CONFIGURACION
    assert paquete.estado_paquete == EstadoPaqueteInferencia.PENDIENTE
    assert len(repo.guardados) == 1
    assert len(motor.paquetes) == 1


@pytest.mark.parametrize(
    "variables",
    [
        [],
        [{"tipo_variable": "TEMPERATURA_AMBIENTAL", "valor": None}],
        [{"tipo_variable": "", "valor": "1"}],
    ],
)
def test_tc_m03_090_paquete_inconsistente(variables: list) -> None:
    evento = evento_para_consolidar()
    evento.variables_involucradas = variables
    repo = PaqueteInferenciaRepoMemoria()
    use_case = ConsolidarEnviarPaqueteUseCase(
        db=SesionNula(),
        paquete_repo=repo,
        motor_inferencia_port=MotorObservado(exito=False),
    )
    with pytest.raises(BusinessRuleError) as exc:
        use_case.execute(evento)
    assert exc.value.code == "PAQUETE_INCONSISTENTE"
    assert repo.guardados == []


def test_tc_m03_090_timestamps_delta_mayor_5s_descarta_agrupacion() -> None:
    """FA-03 vigente: no rechaza el paquete; descarta el agrupado multivariable."""
    ts = ahora_utc()
    evento = evento_para_consolidar(
        variables=[
            {
                "tipo_variable": "TEMPERATURA_AMBIENTAL",
                "valor": "40.0",
                "unidad": "C",
                "timestamp_captura": ts,
            },
            {
                "tipo_variable": "HUMEDAD_RELATIVA",
                "valor": "80.0",
                "unidad": "%",
                "timestamp_captura": ts + timedelta(seconds=6),
            },
        ]
    )
    paquete, repo, motor = _consolidar(MotorObservado(exito=False), evento)
    assert paquete is not None
    assert paquete.contexto_incompleto is True
    assert paquete.metadatos["agrupacion_descartada"]["maximo_seg"] == 5
    assert len(repo.guardados) == 1
    assert len(motor.paquetes) == 1


def _integracion_m04_habilitada() -> bool:
    return os.environ.get("G55_M04_INTEGRATION", "").strip() == "1"


def _url_m04_es_test(url: str) -> bool:
    baja = url.lower()
    if "main" in baja or "prod" in baja:
        return False
    return "test" in baja or "sigab-test" in baja or "api-sgpmp-test" in baja


def test_tc_m03_091_envio_real_a_m04() -> None:
    url = os.environ.get("IOT_INFERENCIA_M04_URL", "").strip()
    token_presente = bool(os.environ.get("IOT_INFERENCIA_M04_TOKEN", "").strip())
    if not _integracion_m04_habilitada():
        pytest.skip(
            "BLOQUEADO TC-M03-091: G55_M04_INTEGRATION!=1. No se POST a M04. "
            "Cliente real: MotorInferenciaHttpAdapter → IOT_INFERENCIA_M04_URL "
            "(G63 usa path /inferencia/paquetes). Ficha QA POST /inferencia no existe "
            "en src/prediction. Contrato IA-1 documentado como provisional "
            "(cuerpo {paquetes:[asdict]}, Bearer IOT_INFERENCIA_M04_TOKEN). "
            f"URL_proceso={'SET' if url else 'UNSET'} TOKEN={'SET' if token_presente else 'UNSET'}."
        )
    if not url or not token_presente:
        pytest.skip("BLOQUEADO TC-M03-091: faltan IOT_INFERENCIA_M04_URL o TOKEN en este entorno.")
    if not _url_m04_es_test(url):
        pytest.skip("BLOQUEADO TC-M03-091: la URL no se identifica como TEST; no se envía.")
    adapter = MotorInferenciaHttpAdapter.desde_entorno()
    if adapter is None:
        pytest.skip("BLOQUEADO TC-M03-091: MotorInferenciaHttpAdapter.desde_entorno() devolvió None.")
    paquete, _, _ = _consolidar(MotorObservado(exito=False))
    aceptado = adapter.enviar_paquete(paquete)
    _volcar_json(
        "tc_m03_091_resultado_envio.json",
        {
            "http_exito_is_success": aceptado,
            "nota": "True solo indica HTTP 2xx; el adapter no parsea id de recepción M04.",
            "campos_enviados": list(dataclasses.asdict(paquete).keys()),
        },
    )
    assert aceptado is True


def test_tc_m03_092_un_evento_un_paquete_sin_partir() -> None:
    paquete, repo, motor = _consolidar(MotorObservado(exito=False))
    assert len(repo.guardados) == 1
    assert len(motor.paquetes) == 1
    assert paquete.id_paquetes_inferencia == repo.guardados[0].id_paquetes_inferencia


def test_tc_m03_092_un_evento_con_501_variables_sigue_siendo_un_paquete() -> None:
    """Hueco vs ficha: consolidar no fragmenta 501 registros de un mismo evento."""
    ts = ahora_utc()
    variables = [
        {
            "tipo_variable": "TEMPERATURA_AMBIENTAL" if i == 0 else "HUMEDAD_RELATIVA",
            "valor": str(20 + (i % 10)),
            "unidad": "C" if i == 0 else "%",
            "timestamp_captura": ts,
        }
        for i in range(501)
    ]
    paquete, repo, motor = _consolidar(
        MotorObservado(exito=False),
        evento_para_consolidar(variables=variables),
    )
    assert paquete is not None
    assert len(repo.guardados) == 1
    assert len(motor.paquetes) == 1


@pytest.mark.parametrize(
    ("cantidad", "lotes_esperados"),
    [
        (500, [500]),
        (501, [500, 1]),
        (1000, [500, 500]),
        (1001, [500, 500, 1]),
    ],
)
def test_tc_m03_092_drenar_fragmenta_pendientes(cantidad: int, lotes_esperados: list[int]) -> None:
    repo, db = _RepoPendientesMemoria(cantidad), Mock()
    motor = _motor_lote(return_value=True)
    resultado = DrenarPaquetesPendientesUseCase(db, repo, motor).execute()
    enviados = [call.args[0] for call in motor.enviar_lote.call_args_list]
    assert [len(lote) for lote in enviados] == lotes_esperados == resultado.lotes
    assert all(len(lote) <= MAX_REGISTROS_POR_ENVIO_INFERENCIA for lote in enviados)
    ids = [p.id_paquetes_inferencia for lote in enviados for p in lote]
    assert ids == list(range(1, cantidad + 1))
    assert resultado.enviados == cantidad and resultado.fallidos == 0
    assert {p.estado_paquete for p in repo.paquetes.values()} == {"ENVIADO"}
    _volcar_json(
        f"tc_m03_092_lotes_{cantidad}.json",
        {
            "cantidad_pendientes": cantidad,
            "lotes": resultado.lotes,
            "enviados": resultado.enviados,
            "ids_primero_ultimo": [ids[0], ids[-1]] if ids else [],
        },
    )


def test_tc_m03_092_tamano_lote_fuera_de_limite() -> None:
    with pytest.raises(ValidationError) as error:
        DrenarPaquetesPendientesUseCase(
            Mock(), _RepoPendientesMemoria(1), _motor_lote(), tamano_lote=501
        )
    assert error.value.code == "TAMANO_LOTE_INVALIDO"


def test_tc_m03_092_fallo_de_un_lote_no_confirma_envio() -> None:
    """Un False del motor reprograma el primer lote; con max_lotes=1 no se toca el resto."""
    repo = _RepoPendientesMemoria(501)
    resultado = DrenarPaquetesPendientesUseCase(
        Mock(), repo, _motor_lote(return_value=False)
    ).execute(max_lotes=1)
    assert resultado.lotes == [500]
    assert resultado.enviados == 0
    assert resultado.reprogramados == 500
    assert {p.estado_paquete for p in repo.paquetes.values()} == {"PENDIENTE"}
    sin_intento = [p.id_paquetes_inferencia for p in repo.paquetes.values() if p.intento_envios == 0]
    assert sin_intento == [501]
