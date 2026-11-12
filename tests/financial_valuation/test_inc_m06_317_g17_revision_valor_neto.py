# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-11-09 | destroyerban | INC-M06-317-G17 RF-84: cálculo en revisión y validación del valor neto ≤ 0 |
# | 2026-11-10 | Arekkazu | Lote M05/M06: fakes al día con el lote integrado (elegibilidad, alertas, período cerrado, referencia documental) |
# | 2026-11-11 | Arekkazu | USAB-M05-M06 B-01 RF-82: el monto del mensaje en formato colombiano |
"""INC-M06-317-G17 / RF-84 R3, FA-2: el valor neto ≤ 0 deja el cálculo en REVISION_REQUERIDA con alerta crítica
y el Contador puede validarlo con justificación.

Antes la confirmación respondía 422 VALOR_NETO_NO_POSITIVO sin guardar nada, sin auditoría y sin forma de validar."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.financial_valuation.application.services.propuesta_reconocimiento import Propuesta
from src.financial_valuation.application.services.valorador import Valorador
from src.financial_valuation.application.use_cases.reconocimiento.confirmar_reconocimiento_use_case import (
    ConfirmarReconocimientoUseCase,
)
from src.financial_valuation.application.use_cases.valoracion.validar_calculo_no_positivo_use_case import (
    ValidarCalculoNoPositivoUseCase,
)
from src.financial_valuation.domain.entities.valoracion import CalculoValor
from src.financial_valuation.domain.services.precios import Precio
from src.financial_valuation.infrastructure.routers import m06_router
from src.identity_access.domain.entities.cuenta import Cuenta
from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.shared.database import get_db
from src.shared.error_handlers import register_error_handlers
from src.shared.errors import BusinessRuleError, ConflictError, NotFoundError, ValidationError

D = Decimal
JUSTIFICACION = "Subasta con costos de transporte extraordinarios por cierre de la vía principal."
ACTIVO = SimpleNamespace(id_activo_biologico=7, identificador="BOV-007", especie="Bovino", id_especie=2, cabezas=1,
                         id_evento_peso=None, numero_id_tributaria="900123456", id_finca=3,
                         magnitud=lambda _c: (D("400"), "kg"))


def _valorar(costos_manuales):
    precio = Precio(id_precio_mercado=12, id_especie=2, categoria="PESO_KG", precio_unitario=D("25000"),
                    unidad_medida="kg", fuente="MERCADO_ACTIVO", fecha_vigencia=date(2026, 9, 1))
    config = SimpleNamespace(
        costos_venta_vigentes=lambda _e: SimpleNamespace(pct_transporte=D("0.01"), pct_comisiones=D("0.02"),
                                                         pct_impuestos=D("0"), id_parametro_costo_venta=1),
        parametro_especie=lambda _e: None)
    return Valorador(None, config).valorar(ACTIVO, date(2026, 11, 9), 0, 9, precio_congelado=precio,
                                           costos_manuales=costos_manuales, justificacion=JUSTIFICACION)


# --- Valorador -------------------------------------------------------------------------------------

def test_valor_neto_no_positivo_devuelve_el_calculo_en_revision() -> None:
    resultado = _valorar({"transporte": D("9800000")})  # 10.000.000 − 9.800.000 − 200.000 = 0

    assert resultado.motivo == "VALOR_NETO_NO_POSITIVO" and not resultado.es_valido
    assert resultado.calculo.estado == "REVISION_REQUERIDA"
    assert resultado.calculo.valor_neto == D("0")


def test_valor_neto_positivo_sigue_calculado() -> None:
    resultado = _valorar(None)

    assert resultado.es_valido and resultado.calculo.estado == "CALCULADO"


# --- Confirmación con valor neto ≤ 0 ---------------------------------------------------------------

class _Db:
    def __init__(self, registro: list) -> None:
        self.registro = registro

    def commit(self) -> None:
        self.registro.append("commit")

    def rollback(self) -> None:
        self.registro.append("rollback")


def _confirmar(bloqueos_previos: list[dict]):
    registro: list = []
    calculo = _valorar({"transporte": D("9900000")}).calculo  # neto −100.000
    propuesta = Propuesta(ACTIVO, date(2026, 11, 9), False)
    for b in bloqueos_previos:
        propuesta.bloquear(b["codigo"], b["mensaje"])
    propuesta.calculo_revision = calculo
    propuesta.bloquear("VALOR_NETO_NO_POSITIVO", "mensaje del valorador")
    calculos, eventos, avisos = [], [], []
    caso = ConfirmarReconocimientoUseCase(
        db=_Db(registro),
        activos=SimpleNamespace(obtener=lambda _id: ACTIVO),
        valoraciones=SimpleNamespace(reconocimiento_confirmado=lambda _id: None,
                                     agregar_calculo=lambda c: calculos.append(c) or 55),
        proponedor=SimpleNamespace(proponer=lambda *a, **k: propuesta),
        contabilizador=SimpleNamespace(periodo_para=lambda *a: SimpleNamespace(id_periodo_contable=4),
                                       auditar=eventos.append),
        notificador=SimpleNamespace(a_contadores=lambda *a: avisos.append((list(registro), a))),
    )
    with pytest.raises(BusinessRuleError) as excinfo:
        caso.execute(7, 9, costos_manuales={"transporte": D("9900000")}, justificacion=JUSTIFICACION,
                         referencia_documental="Factura de venta FV-1234")
    return excinfo.value, calculos, eventos, avisos, registro


def test_confirmacion_deja_el_calculo_en_revision_con_alerta_critica() -> None:
    error, calculos, eventos, avisos, registro = _confirmar([])

    assert error.code == "VALOR_NETO_NO_POSITIVO" and error.status_code == 422
    assert "−$ 100.000" in error.message and "quedó en revisión" in error.message
    assert [c.estado for c in calculos] == ["REVISION_REQUERIDA"] and calculos[0].id_periodo_contable == 4
    assert len(eventos) == 1
    evento = eventos[0]
    assert (evento.tipo_evento, evento.severidad, evento.id_referencia) == ("CALCULO_VALOR_RAZONABLE", "CRITICAL", 55)
    assert evento.payload["estado"] == "REVISION_REQUERIDA" and evento.payload["valor_neto"] == "-100000.0000"
    assert evento.payload["costos_venta"]["transporte"] == "9900000.0000"
    assert registro == ["commit"]
    assert avisos[0][0] == ["commit"]  # la alerta al Contador sale después del commit
    assert avisos[0][1][0] == "ALERTA_FINANCIERA_NIC41" and avisos[0][1][2]["id_calculo_valor_razonable"] == 55


def test_con_otro_bloqueo_no_se_registra_el_calculo() -> None:
    error, calculos, eventos, avisos, registro = _confirmar([{"codigo": "FINCA_SIN_TITULAR", "mensaje": "Sin titular."}])

    assert error.code == "FINCA_SIN_TITULAR"
    assert calculos == [] and eventos == [] and avisos == [] and registro == []


# --- Validación del Contador ------------------------------------------------------------------------

def _calculo(estado: str = "REVISION_REQUERIDA") -> CalculoValor:
    return CalculoValor(
        id_activo_biologico=7, id_precio_mercado=12, id_periodo_contable=4, magnitud=D("400"), unidad_magnitud="kg",
        precio_unitario=D("25000"), valor_razonable_bruto=D("10000000"), costo_transporte=D("9900000"),
        costo_comisiones=D("200000"), costo_impuestos_transaccion=D("0"), otros_costos_disposicion=D("0"),
        valor_neto=D("-100000"), metodo_costo="MIXTO", json_metodo_costo={}, id_usuario=9, estado=estado,
        id_calculo_valor_razonable=55)


def _validador(calculo=None, periodo_abierto: bool = True):
    registro: dict = {"validados": [], "eventos": [], "db": []}
    caso = ValidarCalculoNoPositivoUseCase(
        db=_Db(registro["db"]),
        valoraciones=SimpleNamespace(obtener_calculo=lambda _id: calculo,
                                     validar_calculo=lambda i, v: registro["validados"].append((i, v))),
        contabilizador=SimpleNamespace(
            periodos=SimpleNamespace(obtener=lambda _id: SimpleNamespace(esta_abierto=periodo_abierto)),
            auditar=registro["eventos"].append),
    )
    return caso, registro


@pytest.mark.parametrize("justificacion", [None, "", "      ", "muy corta"])
def test_validar_sin_justificacion_se_rechaza(justificacion) -> None:
    caso, registro = _validador(_calculo())

    with pytest.raises(ValidationError) as excinfo:
        caso.execute(55, justificacion, 9)

    assert excinfo.value.code == "JUSTIFICACION_VALIDACION_REQUERIDA" and excinfo.value.field == "justificacion"
    assert excinfo.value.status_code == 400
    assert registro["validados"] == [] and registro["db"] == []


def test_validar_con_justificacion_pasa_a_calculado_y_audita() -> None:
    caso, registro = _validador(_calculo())

    resultado = caso.execute(55, f"  {JUSTIFICACION}  ", 9)

    assert resultado["estado"] == "CALCULADO"
    (id_calculo, validacion), = registro["validados"]
    assert id_calculo == 55 and validacion["justificacion"] == JUSTIFICACION and validacion["id_usuario"] == 9
    evento, = registro["eventos"]
    assert (evento.tipo_evento, evento.severidad, evento.id_referencia) == ("CALCULO_VALOR_RAZONABLE", "WARNING", 55)
    assert evento.payload["estado_anterior"] == "REVISION_REQUERIDA" and evento.payload["justificacion"] == JUSTIFICACION
    assert registro["db"] == ["commit"]


def test_validar_calculo_inexistente_404() -> None:
    caso, _ = _validador(None)
    with pytest.raises(NotFoundError):
        caso.execute(55, JUSTIFICACION, 9)


def test_validar_calculo_que_no_esta_en_revision_409() -> None:
    caso, registro = _validador(_calculo("CALCULADO"))
    with pytest.raises(ConflictError) as excinfo:
        caso.execute(55, JUSTIFICACION, 9)
    assert excinfo.value.code == "CALCULO_SIN_REVISION_PENDIENTE" and registro["validados"] == []


def test_validar_con_periodo_cerrado_422() -> None:
    caso, registro = _validador(_calculo(), periodo_abierto=False)
    with pytest.raises(BusinessRuleError) as excinfo:
        caso.execute(55, JUSTIFICACION, 9)
    assert excinfo.value.code == "PERIODO_NO_ABIERTO" and registro["validados"] == []


class _Q:
    def join(self, *a, **k):
        return self

    def filter(self, *a, **k):
        return self

    def first(self):
        return object()  # permiso concedido


@pytest.mark.parametrize("cuerpo", [{}, {"justificacion": ""}, {"justificacion": "     "}])
def test_contrato_http_400_validacion_sin_justificacion(cuerpo) -> None:
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(m06_router.router)
    app.dependency_overrides[get_db] = lambda: SimpleNamespace(query=lambda *_a: _Q())
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(
        id_usuario=9, id_token=1, id_rol=5, id_estado_cuenta=Cuenta.ESTADO_ACTIVO)

    with TestClient(app, raise_server_exceptions=False) as client:
        respuesta = client.post("/finanzas/calculos/55/validacion", json=cuerpo)

    assert respuesta.status_code == 400
    assert respuesta.json()["error_code"] == "JUSTIFICACION_VALIDACION_REQUERIDA"
    assert [f["field"] for f in respuesta.json()["fields"]] == ["justificacion"]
