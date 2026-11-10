# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-11-09 | destroyerban | INC-M06-323-G27 RF-85 FA-1/FA-2: la cosecha pendiente continúa con precio o costos manuales |
"""INC-M06-323-G27 / RF-85 FA-1 y FA-2: una cosecha pendiente por falta de precio o de costos de venta continúa.

Antes: (a) con el precio ESTIMADO ya registrado, la cola no volvía a tomar el evento MEDICION_PENDIENTE y la
cosecha de 200 kg nunca se reconocía; (b) no había operación para ingresar a mano los costos del producto."""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.financial_valuation.application.use_cases.valoracion.procesar_eventos_m02_use_case import (
    ProcesarEventosM02UseCase,
)
from src.financial_valuation.application.use_cases.valoracion.reconocer_cosecha_pendiente_use_case import (
    ReconocerCosechaPendienteUseCase,
)
from src.financial_valuation.domain.repositories.evento_m02_port import EventoM02
from src.financial_valuation.domain.services.precios import Precio
from src.financial_valuation.infrastructure.factories import m06_factory
from src.financial_valuation.infrastructure.routers import m06_router
from src.identity_access.domain.entities.cuenta import Cuenta
from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.shared.database import get_db
from src.shared.error_handlers import register_error_handlers
from src.shared.errors import BusinessRuleError, NotFoundError, ValidationError

D = Decimal
JUSTIFICACION = "Flete y comisión del acopiador de leche según la factura FE-881 de noviembre."
PRECIO = Precio(id_precio_mercado=40, id_especie=2, categoria="PRODUCTO", precio_unitario=D("3500"), unidad_medida="L",
                fuente="ESTIMADA", fecha_vigencia=date(2026, 11, 1))
PARAMETRO = SimpleNamespace(pct_transporte=D("0.06"), pct_comisiones=D("0"), pct_impuestos=D("0"), id_parametro_costo_venta=8)


def _procesador(clasificacion="PRODUCCION", precio=PRECIO, parametro=PARAMETRO):
    activo = SimpleNamespace(id_activo_biologico=7, identificador="BOV-007", id_especie=2, id_finca=3,
                             numero_id_tributaria="900123456", id_dispositivo_iot=None)
    calculos, productos, lineas, eventos = [], [], [], []
    caso = ProcesarEventosM02UseCase(
        db=SimpleNamespace(commit=lambda: None, rollback=lambda: None), eventos=None,
        activos=SimpleNamespace(obtener=lambda _id: activo,
                                metrica_produccion=lambda _id: {"id_metrica_produccion": 3, "nombre": "Leche",
                                                                "unidad_medida": "L"}),
        valoraciones=SimpleNamespace(valoracion_costo_activa=lambda _id: None,
                                     reconocimiento_confirmado=lambda _id: SimpleNamespace(clasificacion=clasificacion),
                                     agregar_calculo=lambda c: calculos.append(c) or 91,
                                     agregar_producto=lambda d: productos.append(d) or 70),
        precios=SimpleNamespace(de_especie=lambda *a: [precio] if precio else []),
        medidor=SimpleNamespace(valorador=SimpleNamespace(config=SimpleNamespace(costos_venta_vigentes=lambda _e: parametro))),
        contabilizador=SimpleNamespace(periodo_para=lambda *a: SimpleNamespace(id_periodo_contable=4),
                                       asentar=lambda linea, _u: lineas.append(linea), auditar=eventos.append),
        id_usuario_servicio=1,
    )
    return caso, calculos, productos, lineas, eventos


EVENTO = EventoM02(id_evento=500, id_activo_biologico=7, tipo="PRODUCTIVO",
                   fecha=datetime(2026, 11, 9, 15, tzinfo=timezone.utc),
                   datos={"cantidad_producida": "200", "id_metrica_produccion": 3})


# --- (a) con el precio registrado, la cosecha retomada se reconoce --------------------------------

def test_sin_precio_queda_pendiente() -> None:
    caso, _, productos, _, eventos = _procesador(precio=None)

    assert caso._procesar(EVENTO) == ("MEDICION_PENDIENTE", "Falta precio de mercado para el producto Leche.")
    assert productos == [] and eventos[0].tipo_evento == "RECONOCIMIENTO_PRODUCTO_PENDIENTE"


def test_retomada_con_precio_estimado_se_reconoce_por_658_000() -> None:
    caso, _, productos, lineas, _ = _procesador()

    assert caso._procesar(EVENTO) == ("PROCESADO", None)
    assert productos[0]["valor_producto"] == D("658000.00")  # 200 × 3.500 − 6 %
    assert lineas[0].valor == D("658000.00")


# --- (b) costos manuales del Contador -------------------------------------------------------------

def test_costos_manuales_reconocen_la_cosecha_sin_parametros_de_m09() -> None:
    caso, calculos, productos, lineas, eventos = _procesador(parametro=None)

    resultado = caso.reconocer_cosecha_pendiente(EVENTO, {"transporte": D("42000")}, JUSTIFICACION, 9)

    assert resultado == ("PROCESADO", None)
    calculo, = calculos
    assert calculo.metodo_costo == "MANUAL" and calculo.justificacion == JUSTIFICACION and calculo.id_usuario == 9
    assert calculo.id_parametro_costo_venta is None and calculo.valor_neto == D("658000.0000")
    assert productos[0]["justificacion"] == JUSTIFICACION and productos[0]["id_usuario"] == 9
    assert lineas[0].valor == D("658000.00")
    reconocido, = eventos
    assert reconocido.id_usuario == 9 and reconocido.id_sistema is None  # actor: el Contador
    assert reconocido.payload["justificacion_costos_manual"] == JUSTIFICACION


def test_costos_manuales_no_aplican_a_la_cosecha_de_consumo() -> None:
    caso, _, productos, _, _ = _procesador(clasificacion="CONSUMO")

    resultado, detalle = caso.reconocer_cosecha_pendiente(EVENTO, {"transporte": D("42000")}, JUSTIFICACION, 9)

    assert resultado == "MEDICION_PENDIENTE" and "no admite costos manuales" in detalle and productos == []


class _Db:
    def __init__(self) -> None:
        self.registro = []

    def commit(self):
        self.registro.append("commit")

    def rollback(self):
        self.registro.append("rollback")


def _caso(evento=EVENTO, resultado=("PROCESADO", None)):
    db, procesados = _Db(), []
    caso = ReconocerCosechaPendienteUseCase(
        db=db,
        eventos=SimpleNamespace(cosecha_pendiente=lambda _id: evento,
                                registrar_procesamiento=lambda i, r, d: procesados.append((i, r))),
        procesador=SimpleNamespace(reconocer_cosecha_pendiente=lambda *a: resultado),
    )
    return caso, db, procesados


@pytest.mark.parametrize("costos, justificacion, codigo", [
    (None, JUSTIFICACION, "COSTOS_VENTA_REQUERIDOS"),
    ({"transporte": None}, JUSTIFICACION, "COSTOS_VENTA_REQUERIDOS"),
    ({"transporte": D("42000")}, None, "JUSTIFICACION_REQUERIDA"),
    ({"transporte": D("42000")}, "   corta   ", "JUSTIFICACION_REQUERIDA"),
])
def test_validaciones_del_ingreso_manual(costos, justificacion, codigo) -> None:
    caso, db, _ = _caso()
    with pytest.raises(ValidationError) as excinfo:
        caso.execute(500, costos, justificacion, 9)
    assert excinfo.value.code == codigo and excinfo.value.status_code == 400 and db.registro == []


def test_evento_que_no_esta_pendiente_404() -> None:
    caso, _, _ = _caso(evento=None)
    with pytest.raises(NotFoundError):
        caso.execute(500, {"transporte": D("42000")}, JUSTIFICACION, 9)


def test_si_sigue_pendiente_responde_422_y_no_guarda() -> None:
    caso, db, procesados = _caso(resultado=("MEDICION_PENDIENTE", "Falta precio de mercado para el producto Leche."))
    with pytest.raises(BusinessRuleError) as excinfo:
        caso.execute(500, {"transporte": D("42000")}, JUSTIFICACION, 9)
    assert excinfo.value.message == "Falta precio de mercado para el producto Leche."
    assert db.registro == ["rollback"] and procesados == []


def test_reconocida_marca_el_evento_procesado_y_hace_commit() -> None:
    caso, db, procesados = _caso()
    assert caso.execute(500, {"transporte": D("42000")}, JUSTIFICACION, 9) == {"id_evento": 500, "resultado": "PROCESADO"}
    assert procesados == [(500, "PROCESADO")] and db.registro == ["commit"]


class _Q:
    def join(self, *a, **k):
        return self

    def filter(self, *a, **k):
        return self

    def first(self):
        return object()  # permiso concedido


def test_contrato_http_400_sin_justificacion(monkeypatch) -> None:
    monkeypatch.setattr(m06_factory, "id_usuario_servicio", lambda _db: 1)  # la BD de la prueba es falsa
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(m06_router.router)
    app.dependency_overrides[get_db] = lambda: SimpleNamespace(query=lambda *_a: _Q())
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(
        id_usuario=9, id_token=1, id_rol=5, id_estado_cuenta=Cuenta.ESTADO_ACTIVO)
    with TestClient(app, raise_server_exceptions=False) as client:
        respuesta = client.post("/finanzas/productos/pendientes/500/reconocimiento",
                                json={"costos_manuales": {"transporte": 42000}, "justificacion": "  "})
    assert respuesta.status_code == 400
    assert respuesta.json()["error_code"] == "JUSTIFICACION_REQUERIDA"
    assert [f["field"] for f in respuesta.json()["fields"]] == ["justificacion"]


def test_contrato_http_lista_las_cosechas_pendientes(monkeypatch) -> None:
    pendiente = {"id_evento": 500, "identificador": "BOV-007", "producto_agricola": "Leche", "cantidad_cosechada": "200",
                 "motivo": "Falta costos de venta para el producto Leche.", "admite_costos_manuales": True}
    monkeypatch.setattr(m06_factory.M06, "eventos", SimpleNamespace(cosechas_pendientes=lambda: [pendiente]))
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(m06_router.router)
    app.dependency_overrides[get_db] = lambda: SimpleNamespace(query=lambda *_a: _Q())
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(
        id_usuario=9, id_token=1, id_rol=5, id_estado_cuenta=Cuenta.ESTADO_ACTIVO)
    with TestClient(app, raise_server_exceptions=False) as client:
        respuesta = client.get("/finanzas/productos/pendientes")
    assert respuesta.status_code == 200 and respuesta.json() == [pendiente]
