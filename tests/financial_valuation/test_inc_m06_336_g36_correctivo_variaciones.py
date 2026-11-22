# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-11-10 | destroyerban | INC-M06-336-G36 RF-86: correctivo de variaciones con aprobación del Contador |
"""INC-M06-336-G36 / RF-86 restricción 5, CA-12 y CA-13: correctivo de variaciones.

Antes no había operación para corregir una variación errónea, y PUT/PATCH/DELETE sobre variaciones y líneas
respondían 404 sin código ni orientación. Ahora: solicitud PENDIENTE, aprobación por otro Contador (variación
de monto opuesto que referencia la original y líneas inversas) y respuestas 409 que orientan al correctivo."""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.financial_valuation.application.use_cases.valoracion.correctivo_variacion_use_case import (
    ResolverCorrectivoVariacionUseCase,
    SolicitarCorrectivoVariacionUseCase,
)
from src.financial_valuation.domain.entities.valoracion import SolicitudCorrectivo, VariacionRegistro
from src.financial_valuation.infrastructure.routers import m06_router
from src.identity_access.domain.entities.cuenta import Cuenta
from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.shared.database import get_db
from src.shared.error_handlers import register_error_handlers
from src.shared.errors import AuthorizationError, BusinessRuleError, ConflictError, NotFoundError, ValidationError

D = Decimal
MOTIVO = "El pesaje del evento se digitó con un cero de más y la ganancia es errónea."


def _variacion(**cambios) -> VariacionRegistro:
    datos = dict(id_activo_biologico=7, tipo="GANANCIA_TRANSFORMACION_BIOLOGICA", variacion_transformacion=D("4600000"),
                 variacion_precio_mercado=D("0"), valor_razonable_anterior=D("18800000"),
                 valor_razonable_nuevo=D("23400000"), id_periodo_contable=8, id_usuario=1, tiene_estimacion=False,
                 id_medicion_posterior=40, id_evento=500, id_variacion_valor_razonable=249)
    datos.update(cambios)
    return VariacionRegistro(**datos)


def _solicitud(**cambios) -> SolicitudCorrectivo:
    datos = dict(id_solicitud_correctivo_variacion=31, id_variacion_valor_razonable=249, motivo=MOTIVO, estado="PENDIENTE",
                 id_usuario_solicitante=9, fecha_solicitud=datetime(2026, 11, 10, tzinfo=timezone.utc))
    datos.update(cambios)
    return SolicitudCorrectivo(**datos)


# --- Dominio ----------------------------------------------------------------------------------------

def test_el_correctivo_tiene_monto_opuesto_y_referencia_al_original() -> None:
    original = _variacion()

    correctivo = original.correctivo(id_usuario=12)

    assert correctivo.tipo == "PERDIDA_TRANSFORMACION_BIOLOGICA"
    assert correctivo.monto_variacion == D("-4600000") == -original.monto_variacion
    assert (correctivo.valor_razonable_anterior, correctivo.valor_razonable_nuevo) == (D("23400000"), D("18800000"))
    assert correctivo.id_variacion_corregida == 249 and correctivo.es_correctivo and correctivo.id_usuario == 12
    assert (correctivo.id_evento, correctivo.id_medicion_posterior, correctivo.id_periodo_contable) == (500, 40, 8)
    assert original.monto_variacion == D("4600000") and not original.es_correctivo  # el original no cambia


def test_correctivo_de_una_perdida_por_precio_es_una_ganancia_por_precio() -> None:
    perdida = _variacion(tipo="PERDIDA_PRECIO_MERCADO", variacion_transformacion=D("0"), variacion_precio_mercado=D("-600000"))
    correctivo = perdida.correctivo(12)
    assert correctivo.tipo == "GANANCIA_PRECIO_MERCADO" and correctivo.monto_variacion == D("600000")


# --- Casos de uso -----------------------------------------------------------------------------------

class _Db:
    def __init__(self) -> None:
        self.registro = []

    def commit(self):
        self.registro.append("commit")

    def rollback(self):
        self.registro.append("rollback")


def _caso(clase, variacion=None, vigente=None, solicitud=None, periodo_abierto=True):
    estado = {"agregadas": [], "aprobadas": [], "rechazadas": [], "variaciones": [], "revertidas": [], "eventos": []}
    lineas = [SimpleNamespace(id_linea_asiento_nic41=892)]
    db = _Db()
    caso = clase(
        db=db,
        correctivos=SimpleNamespace(
            variacion=lambda _id: variacion, solicitud_vigente=lambda _id: vigente,
            obtener=lambda _id, bloquear=False: solicitud,
            agregar=lambda v, m, u: estado["agregadas"].append((v, m, u)) or 31,
            aprobar=lambda s, u, c: estado["aprobadas"].append((s, u, c)),
            rechazar=lambda s, u, m: estado["rechazadas"].append((s, u, m))),
        valoraciones=SimpleNamespace(agregar_variacion=lambda v: estado["variaciones"].append(v) or 250),
        contabilizador=SimpleNamespace(
            periodos=SimpleNamespace(obtener=lambda _id: SimpleNamespace(esta_abierto=periodo_abierto,
                                                                         fecha_fin=date(2026, 11, 30))),
            asientos=SimpleNamespace(lineas_de_origen=lambda t, i: lineas if (t, i) == ("variaciones_valor_razonable", 249) else []),
            revertir_lineas=lambda originales, periodo, fecha, tabla, id_origen, justificacion, id_usuario: (
                estado["revertidas"].append((originales, tabla, id_origen, justificacion, id_usuario)) or [SimpleNamespace(
                    id_linea_asiento_nic41=901, id_linea_corregida=892, tipo_hecho="VARIACION_VR_TB", valor=D("4600000"),
                    cuenta_debito="4105", cuenta_credito="1580", estado="REGISTRADA")]),
            auditar=estado["eventos"].append),
    )
    return caso, estado, db


@pytest.mark.parametrize("motivo", [None, "", "     ", "corto"])
def test_solicitar_sin_motivo_suficiente_400(motivo) -> None:
    caso, estado, db = _caso(SolicitarCorrectivoVariacionUseCase, variacion=_variacion())
    with pytest.raises(ValidationError) as excinfo:
        caso.execute(249, motivo, 9)
    assert excinfo.value.code == "MOTIVO_REQUERIDO" and excinfo.value.field == "motivo" and db.registro == []


def test_solicitar_crea_la_solicitud_pendiente_y_no_toca_la_variacion() -> None:
    caso, estado, db = _caso(SolicitarCorrectivoVariacionUseCase, variacion=_variacion())

    resultado = caso.execute(249, f"  {MOTIVO}  ", 9)

    assert resultado == {"id_solicitud_correctivo_variacion": 31, "id_variacion_valor_razonable": 249,
                         "estado": "PENDIENTE", "monto_correctivo": D("-4600000")}
    assert estado["agregadas"] == [(249, MOTIVO, 9)] and estado["variaciones"] == [] and estado["revertidas"] == []
    assert estado["eventos"][0].tipo_evento == "CORRECTIVO_VARIACION_SOLICITADO" and db.registro == ["commit"]


@pytest.mark.parametrize("variacion, vigente, abierto, error, codigo", [
    (None, None, True, NotFoundError, "VARIACION_NO_ENCONTRADA"),
    (_variacion(id_variacion_corregida=200), None, True, ConflictError, "CORRECTIVO_NO_CORREGIBLE"),
    (_variacion(), _solicitud(), True, ConflictError, "CORRECTIVO_EXISTENTE"),
    (_variacion(), None, False, BusinessRuleError, "PERIODO_NO_ABIERTO"),
])
def test_solicitar_rechazos(variacion, vigente, abierto, error, codigo) -> None:
    caso, estado, db = _caso(SolicitarCorrectivoVariacionUseCase, variacion=variacion, vigente=vigente, periodo_abierto=abierto)
    with pytest.raises(error) as excinfo:
        caso.execute(249, MOTIVO, 9)
    assert excinfo.value.code == codigo and estado["agregadas"] == [] and db.registro == []


def test_aprobar_registra_el_correctivo_y_las_lineas_inversas() -> None:
    caso, estado, db = _caso(ResolverCorrectivoVariacionUseCase, variacion=_variacion(), solicitud=_solicitud())

    resultado = caso.aprobar(31, 12)

    correctivo, = estado["variaciones"]
    assert correctivo.id_variacion_corregida == 249 and correctivo.monto_variacion == D("-4600000")
    (originales, tabla, id_origen, justificacion, id_usuario), = estado["revertidas"]
    assert [ln.id_linea_asiento_nic41 for ln in originales] == [892]
    assert (tabla, id_origen, justificacion, id_usuario) == ("variaciones_valor_razonable", 250, MOTIVO, 12)
    assert estado["aprobadas"] == [(31, 12, 250)]
    assert resultado["estado"] == "APROBADA" and resultado["id_variacion_correctiva"] == 250
    assert resultado["lineas_inversas"][0]["id_linea_corregida"] == 892
    evento, = estado["eventos"]
    assert evento.tipo_evento == "CORRECTIVO_VARIACION_APROBADO" and evento.payload["lineas_inversas"] == [901]
    assert db.registro == ["commit"]


@pytest.mark.parametrize("solicitud, usuario, error, codigo", [
    (None, 12, NotFoundError, "CORRECTIVO_NO_ENCONTRADO"),
    (_solicitud(estado="APROBADA", id_usuario_resolutor=12), 12, ConflictError, "CORRECTIVO_YA_RESUELTO"),
    (_solicitud(), 9, AuthorizationError, "APROBADOR_DEBE_SER_OTRO"),  # quien solicitó no aprueba
])
def test_aprobar_rechazos(solicitud, usuario, error, codigo) -> None:
    caso, estado, db = _caso(ResolverCorrectivoVariacionUseCase, variacion=_variacion(), solicitud=solicitud)
    with pytest.raises(error) as excinfo:
        caso.aprobar(31, usuario)
    assert excinfo.value.code == codigo and estado["variaciones"] == [] and estado["aprobadas"] == []


def test_aprobar_con_periodo_cerrado_422() -> None:
    caso, estado, _ = _caso(ResolverCorrectivoVariacionUseCase, variacion=_variacion(), solicitud=_solicitud(),
                            periodo_abierto=False)
    with pytest.raises(BusinessRuleError):
        caso.aprobar(31, 12)
    assert estado["variaciones"] == []


def test_rechazar_exige_motivo_y_otro_contador() -> None:
    caso, estado, db = _caso(ResolverCorrectivoVariacionUseCase, variacion=_variacion(), solicitud=_solicitud())
    with pytest.raises(ValidationError) as excinfo:
        caso.rechazar(31, "  ", 12)
    assert excinfo.value.field == "motivo_rechazo"
    with pytest.raises(AuthorizationError):
        caso.rechazar(31, "El pesaje está bien: la ganancia corresponde al crecimiento real.", 9)

    resultado = caso.rechazar(31, "El pesaje está bien: la ganancia corresponde al crecimiento real.", 12)

    assert resultado["estado"] == "RECHAZADA" and estado["rechazadas"][0][:2] == (31, 12)
    assert estado["variaciones"] == [] and estado["eventos"][0].tipo_evento == "CORRECTIVO_VARIACION_RECHAZADO"
    assert db.registro == ["commit"]


# --- Contrato HTTP ----------------------------------------------------------------------------------

class _Q:
    def join(self, *a, **k):
        return self

    def filter(self, *a, **k):
        return self

    def first(self):
        return object()  # permiso concedido


@pytest.fixture
def cliente():
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(m06_router.router)
    app.dependency_overrides[get_db] = lambda: SimpleNamespace(query=lambda *_a: _Q())
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(
        id_usuario=9, id_token=1, id_rol=5, id_estado_cuenta=Cuenta.ESTADO_ACTIVO)
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


@pytest.mark.parametrize("metodo", ["put", "patch", "delete"])
@pytest.mark.parametrize("ruta, codigo", [
    ("/finanzas/variaciones/249", "VARIACION_INMUTABLE"),
    ("/finanzas/periodos/8/variaciones/249", "VARIACION_INMUTABLE"),
    ("/finanzas/lineas/892", "LINEA_ASIENTO_INMUTABLE"),
])
def test_modificar_o_borrar_directamente_orienta_al_correctivo(cliente, metodo, ruta, codigo) -> None:
    respuesta = getattr(cliente, metodo)(ruta, **({} if metodo == "delete" else {"json": {"monto_variacion": 0}}))

    assert respuesta.status_code == 409
    assert respuesta.json()["error_code"] == codigo
    assert "solicite" in respuesta.json()["message"] and "correctivo" in respuesta.json()["message"]


def test_solicitar_por_http_sin_motivo_400(cliente) -> None:
    respuesta = cliente.post("/finanzas/variaciones/249/correctivos", json={"motivo": "   "})
    assert respuesta.status_code == 400 and respuesta.json()["error_code"] == "MOTIVO_REQUERIDO"


def test_estado_fuera_del_catalogo_400(cliente) -> None:
    respuesta = cliente.get("/finanzas/correctivos", params={"estado": "BORRADOR"})
    assert respuesta.status_code == 400 and respuesta.json()["error_code"] == "VAL_ENTRADA"


def test_openapi_publica_crear_y_aprobar(cliente) -> None:
    rutas = cliente.get("/openapi.json").json()["paths"]
    assert "post" in rutas["/finanzas/variaciones/{id_variacion}/correctivos"]
    assert "post" in rutas["/finanzas/correctivos/{id_solicitud}/aprobacion"]
    assert "post" in rutas["/finanzas/correctivos/{id_solicitud}/rechazo"]
