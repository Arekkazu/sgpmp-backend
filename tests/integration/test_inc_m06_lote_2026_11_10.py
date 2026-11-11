# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-10 | Arekkazu | INC-M06-337/342/345/350/351 RF-86/87: cierre en espera, ajuste, acumulado, matriz, titular y 403 |
"""Lote QA M06 del 2026-11-10 contra el esquema real: el cierre que espera autorización se queda
EN_CIERRE (y se cancela), el período cerrado nombra a quién lo cerró, el ajuste de período anterior,
el acumulado del período abierto, los bloqueos por matriz y titular, el aviso de cuenta faltante y
el 403 con el rol."""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal as D

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text

from src.shared.errors import AppError
from tests.integration.test_m06_flujo_nic41_integration import (  # noqa: F401 (fixtures)
    HOY,
    _MATRIZ,
    _activo,
    _configurar,
    _finca,
    _pesaje,
    _precio,
    contador,
    m06,
)

pytestmark = pytest.mark.integration

NIT, DV = "830095213", "0"
ESPECIE = 2


class _Notificador:
    def __init__(self) -> None:
        self.avisos: list[str] = []

    def a_contadores(self, tipo_evento, mensaje, detalle, id_finca=None) -> None:
        self.avisos.append(mensaje)

    def ya_notificado(self, tipo_evento, detalle) -> bool:
        return False


def _reconocido(db, m, uid, matriz=_MATRIZ):
    """Activo comprado a 3.000.000 y reconocido a valor razonable (400 kg × 8.000 × 0,95)."""
    finca = _finca(db, uid, nit=NIT, dv=DV)
    _configurar(m, uid, ESPECIE)
    for tipo, sentido, debito, credito in matriz:
        m.guardar_asignacion().execute(tipo, sentido, None, None, debito, credito, uid)
    activo = _activo(db, finca, uid, especie=ESPECIE, origen="compra", costo=D("3000000"))
    _pesaje(db, activo, "400", -timedelta(minutes=5))
    _precio(m, uid, ESPECIE, "8000", HOY - timedelta(days=10))
    m.confirmar_reconocimiento().execute(activo, uid)
    return finca, activo, m.periodos.que_contiene(NIT, HOY)


def _codigo(llamada) -> str:
    with pytest.raises(AppError) as error:
        llamada()
    return error.value.code, error.value.message


def test_cierre_espera_en_cierre_se_cancela_y_el_ajuste_va_al_periodo_abierto(db_session, m06, contador):
    uid = contador["id_usuario"]
    _, activo, periodo = _reconocido(db_session, m06, uid)
    db_session.execute(text("SET LOCAL session_replication_role = replica"))  # el precio vence: activo sin precio
    db_session.execute(text("UPDATE modulo6.precios_mercado SET fecha_vencimiento = :d WHERE id_especie = :e"),
                       {"d": HOY - timedelta(days=1), "e": ESPECIE})
    db_session.execute(text("SET LOCAL session_replication_role = origin"))
    p = periodo.id_periodo_contable

    # INC-M06-345-G43 A: la autorización pendiente deja el período EN_CIERRE, no ABIERTO.
    codigo, mensaje = _codigo(lambda: m06.cierre().execute(p, uid))
    assert codigo == "EXCLUSION_REQUIERE_AUTORIZACION" and "queda en cierre" in mensaje
    assert m06.periodos.obtener(p).estado == "EN_CIERRE"
    assert m06.periodos.ejecucion_en_proceso(p)["esperando_autorizacion"]

    # INC-M06-350-G44 03: un segundo intento sin decisión es concurrencia, con hora y usuario del primero.
    codigo, mensaje = _codigo(lambda: m06.cierre().execute(p, uid))
    assert codigo == "CIERRE_EN_EJECUCION" and "Integracion Prueba" in mensaje and "espera la autorización" in mensaje

    # La cancelación restaura ABIERTO sin cambios.
    assert m06.cierre().cancelar(p, uid)["estado"] == "ABIERTO"
    assert m06.periodos.obtener(p).estado == "ABIERTO"
    assert m06.periodos.ultima_ejecucion(p)["estado"] == "ROLLBACK"
    assert _codigo(lambda: m06.cierre().cancelar(p, uid))[0] == "CIERRE_NO_CANCELABLE"

    # La autorización continúa el mismo cierre.
    _codigo(lambda: m06.cierre().execute(p, uid))
    en_espera = m06.periodos.ejecucion_en_proceso(p)["id_cierre"]
    cierre = m06.cierre().execute(p, uid, incluir_activos_sin_precio=True)
    assert (cierre["estado"], cierre["id_cierre"]) == ("CERRADO", en_espera)

    # INC-M06-350-G44 02: el período cerrado nombra a quien lo cerró.
    codigo, mensaje = _codigo(lambda: m06.cierre().execute(p, uid))
    assert codigo == "PERIODO_CERRADO" and "por Integracion Prueba" in mensaje

    # INC-M06-351-G45 03: ajuste en el período abierto, con referencia y justificación; el cerrado no cambia.
    [original] = [ln for ln in m06.asientos.del_activo(activo)
                  if ln.tipo_hecho == "RECONOCIMIENTO_DIFERENCIA" and ln.id_periodo_contable == p]
    lineas_cerradas = len(m06.asientos.del_periodo(p))
    justificacion = "El costo de adquisición tenía un descuento no aplicado"
    assert _codigo(lambda: m06.ajuste_periodo_anterior().execute(
        original.id_linea_asiento_nic41, "DISMINUIR", D("40000.01"), justificacion, uid))[0] == "AJUSTE_SUPERA_VALOR"
    ajuste = m06.ajuste_periodo_anterior().execute(original.id_linea_asiento_nic41, "DISMINUIR", D("10000"),
                                                   justificacion, uid)
    assert ajuste["id_periodo_contable"] == cierre["id_periodo_siguiente"] and ajuste["estado"] == "REGISTRADA"
    [linea] = [ln for ln in m06.asientos.ajustes_de(original.id_linea_asiento_nic41)]
    assert (linea.tipo_hecho, linea.tipo_hecho_corregido, linea.justificacion) == (
        "AJUSTE_PERIODO_ANTERIOR", "RECONOCIMIENTO_DIFERENCIA", justificacion)
    assert (linea.cuenta_debito, linea.cuenta_credito) == (original.cuenta_credito, original.cuenta_debito)
    assert len(m06.asientos.del_periodo(p)) == lineas_cerradas
    assert _codigo(lambda: m06.ajuste_periodo_anterior().execute(
        linea.id_linea_asiento_nic41, "AUMENTAR", D("1"), justificacion, uid))[0] == "AJUSTE_SOBRE_AJUSTE"

    # INC-M06-337-G37: el acumulado del período abierto ya refleja el ajuste, sin generar versión.
    acumulado = m06.estado_resultados().acumulado(cierre["id_periodo_siguiente"], {})
    assert acumulado["estado_periodo"] == "ABIERTO" and not acumulado["es_definitivo"]
    # El ajuste resta del componente del hecho que corrige (la consulta usa tipo_hecho_corregido).
    assert D(acumulado["componentes"]["ganancia_reconocimiento_inicial"]) == D("-10000")
    assert m06.reportes.listar_estados(cierre["id_periodo_siguiente"]) == []


def test_matriz_incompleta_y_finca_sin_titular_bloquean_y_la_cuenta_faltante_avisa(db_session, m06, contador):
    uid = contador["id_usuario"]
    m06.__dict__["notificador"] = _Notificador()
    sin = {("RECONOCIMIENTO_DIFERENCIA", "GANANCIA"), ("VARIACION_VR_PM", "PERDIDA")}
    finca, _, periodo = _reconocido(db_session, m06, uid, [f for f in _MATRIZ if f[:2] not in sin])

    # INC-M06-342-G40: la línea sin cuenta avisa al Contador qué combinación configurar.
    assert any("Falta la cuenta contable" in a and "ganancia" in a for a in m06.notificador.avisos)

    # INC-M06-350-G44 05: la matriz debe cubrir lo que registra el cierre, no solo lo ya pendiente.
    codigos = {b["codigo"]: b["mensaje"] for b in m06.cierre().prevalidar(periodo).bloqueos}
    assert "LINEAS_PENDIENTE_CUENTA" in codigos and "pérdida" in codigos["MATRIZ_CONTABLE_INCOMPLETA"]

    # INC-M06-350-G44 06: una finca con movimientos que perdió el titular bloquea el cierre.
    db_session.execute(text("SET LOCAL session_replication_role = replica"))
    db_session.execute(text("UPDATE modulo9.fincas SET tipo_id_tributaria = NULL, numero_id_tributaria = NULL, dv = NULL, razon_social = NULL WHERE id_finca = :f"), {"f": finca})
    db_session.execute(text("SET LOCAL session_replication_role = origin"))
    assert "FINCA_SIN_TITULAR" in {b["codigo"] for b in m06.cierre().prevalidar(periodo).bloqueos}
    assert _codigo(lambda: m06.cierre().execute(periodo.id_periodo_contable, uid))[0] == "CIERRE_BLOQUEADO"
    assert m06.periodos.obtener(periodo.id_periodo_contable).estado == "ABIERTO"


def test_403_del_cierre_nombra_el_rol(db_session, crear_usuario_db, crear_auth_headers, monkeypatch):
    """INC-M06-350-G44 01 (RF-87 FA-4)."""
    from src.financial_valuation.infrastructure.routers.m06_router import router
    from src.shared import jwt as jwt_module
    from src.shared.database import get_db
    from src.shared.error_handlers import register_error_handlers
    from tests.integration.conftest import JWT_SECRET_INTEGRACION

    app = FastAPI()
    register_error_handlers(app)
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db_session
    monkeypatch.setattr(jwt_module, "_SECRET_KEY", JWT_SECRET_INTEGRACION)
    with TestClient(app, raise_server_exceptions=False) as cliente:
        productor = crear_auth_headers(crear_usuario_db(id_rol=2, estado=2))
        cierre = cliente.post("/finanzas/periodos/1/cierre", headers=productor, json={})
        precios = cliente.post("/finanzas/precios", headers=productor, json={})
    assert cierre.status_code == 403 and "(Productor)" in cierre.json()["message"]
    assert "exclusiva del Contador" in cierre.json()["message"]
    assert precios.status_code == 403 and "(Productor)" in precios.json()["message"]
