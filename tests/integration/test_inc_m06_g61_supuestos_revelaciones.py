# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-11-13 | Leandro | TC-M06-G61 RF-92: validar cobertura, aviso, versiones y descargas. |
# | 2026-11-13 | Arekkazu | Lote M05/M06 13-11: el cierre de la prueba sigue a la trazabilidad de RF-91 (#1115) |
import os
from datetime import timedelta
from decimal import Decimal
from io import BytesIO
from zipfile import ZipFile

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.financial_valuation.infrastructure.adapters.notificacion_financiera_m01_adapter import (
    NotificacionFinancieraM01Adapter,
)
from src.financial_valuation.infrastructure.routers.m06_router import router
from src.shared import jwt
from src.shared.database import get_db
from src.shared.error_handlers import register_error_handlers
from tests.integration.conftest import JWT_SECRET_INTEGRACION
from tests.integration.test_m06_flujo_nic41_integration import (
    HOY, NIT, _activo, _configurar, _finca, _matriz, _pesaje, _precio, contador, m06,
)

pytestmark = pytest.mark.integration
SECCION = "niif13_93_metodos_y_supuestos"


class NotificadorPrueba:
    def __init__(self, db):
        self.db = db
        self.avisos = []
        self.adaptador = NotificacionFinancieraM01Adapter(
            lambda: Session(bind=db.connection(), join_transaction_mode="create_savepoint"),
        )

    def a_contadores(self, tipo, mensaje, detalle, id_finca=None):
        if detalle.get("motivo") == "SUPUESTOS_REVELACIONES_INSUFICIENTES":
            assert not self.db.in_transaction()
            self.avisos.append((tipo, mensaje, detalle, id_finca))
            self.adaptador.a_contadores(tipo, mensaje, detalle, id_finca)

    def ya_notificado(self, tipo, detalle):
        return False


def test_rol_api_puede_leer_las_columnas_de_supuestos(db_session):
    rol = os.getenv("TEST_ROL_APP", "sgpmp_app")
    columnas = ("id_calculo_actual", "id_activo_biologico", "id_periodo_contable",
                "fecha_medicion", "id_medicion_posterior", "supuestos_aplicados")
    permisos = db_session.execute(text("""
        SELECT has_column_privilege(:rol, 'modulo6.mediciones_posteriores', columna, 'SELECT')
          FROM unnest(CAST(:columnas AS text[])) AS columna
    """), {"rol": rol, "columnas": list(columnas)}).scalars().all()
    assert permisos == [True] * len(columnas)
    assert db_session.execute(text("""
        SELECT relrowsecurity AND relforcerowsecurity
          FROM pg_class WHERE oid = 'modulo6.mediciones_posteriores'::regclass
    """)).scalar_one()


def test_generacion_cierre_consulta_aprobacion_y_descargas(
    db_session, m06, contador, crear_usuario_db, crear_auth_headers, monkeypatch,
):
    usuario = contador["id_usuario"]
    finca = _finca(db_session, usuario)
    _configurar(m06, usuario, 2)
    _configurar(m06, usuario, 3, vida=24)
    _matriz(m06, usuario)
    _precio(m06, usuario, 2, "8000", HOY - timedelta(days=10))
    con_supuestos = _activo(db_session, finca, usuario, especie=2, origen="compra", costo=Decimal("3000000"))
    sin_supuestos = _activo(db_session, finca, usuario, especie=3, origen="compra", costo=Decimal("2000000"))
    for activo in (con_supuestos, sin_supuestos):
        _pesaje(db_session, activo, "400")
        m06.confirmar_reconocimiento().execute(activo, usuario)
    _precio(m06, usuario, 2, "8500", HOY)

    notificador = NotificadorPrueba(db_session)
    m06.__dict__["notificador"] = notificador
    periodo = m06.periodos.que_contiene(NIT, HOY).id_periodo_contable
    cierre = m06.cierre().execute(periodo, usuario, autorizar_exclusiones=True)
    id_automatico = cierre["reportes"]["informe_revelaciones"]["id_informe"]
    [aviso_cierre] = notificador.avisos
    assert aviso_cierre[2]["id_informe"] == id_automatico and aviso_cierre[3] == finca
    aprobado_anterior = m06.informe_revelaciones().resolver(id_automatico, True, None, usuario)
    otro_contador = crear_usuario_db(id_rol=5, estado=2)

    # Semilla de supuestos de fuente. El flujo productivo actual solo guarda la fuente de precio
    # y los métodos de costos de venta. La fila se siembra antes de la fecha de corte del reporte.
    db_session.execute(text("SET LOCAL session_replication_role = replica"))
    db_session.execute(text("""
        UPDATE modulo6.calculos_valor_razonable
           SET json_metodo_costo = (json_metodo_costo - 'fuente_precio') ||
               '{"tasa_descuento": 0, "supuestos_crecimiento": "Estable",
                 "condicion_corporal": 3}'::jsonb
         WHERE id_activo_biologico = :activo
    """), {"activo": con_supuestos})
    db_session.execute(text("""
        UPDATE modulo6.mediciones_posteriores
           SET supuestos_aplicados = (supuestos_aplicados - 'fuente') || '{"produccion_esperada": 0}'::jsonb
         WHERE id_activo_biologico = :activo
    """), {"activo": con_supuestos})
    db_session.execute(text("SET LOCAL session_replication_role = origin"))
    if os.getenv("TEST_ROL_APP") == "sgpmp_app":
        from src.shared.database import declarar_identidad

        declarar_identidad(db_session, usuario, "Contador")
        db_session.execute(text("SET LOCAL ROLE sgpmp_app"))
        try:
            assert db_session.execute(text("""
                SELECT supuestos_aplicados->>'produccion_esperada'
                  FROM modulo6.mediciones_posteriores WHERE id_activo_biologico = :a
            """), {"a": con_supuestos}).scalars().all() == ["0"]
        finally:
            db_session.execute(text("RESET ROLE"))

    app = FastAPI()
    register_error_handlers(app)
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db_session
    monkeypatch.setattr(jwt, "_SECRET_KEY", JWT_SECRET_INTEGRACION)
    monkeypatch.setattr("src.financial_valuation.infrastructure.routers.m06_router.M06", lambda db: m06)
    headers = crear_auth_headers(contador)
    with TestClient(app) as client:
        generacion = client.post(
            f"/finanzas/periodos/{periodo}/revelaciones", headers=headers,
            json={"declaracion_sin_novedad": True,
                  "justificacion_inconsistencias": "Conciliación revisada por el Contador de prueba"},
        )
        assert generacion.status_code == 201, generacion.text
        id_manual = generacion.json()["id_informe"]
        assert "supuestos_insuficientes" not in generacion.json()
        _, mensaje, detalle, finca_aviso = notificador.avisos[-1]
        assert detalle["id_informe"] == id_manual and finca_aviso == finca
        assert [a["id_activo_biologico"] for a in detalle["activos"]] == [sin_supuestos]
        assert f"M06-{sin_supuestos}" in mensaje
        assert client.get(f"/finanzas/revelaciones/{id_manual}/descarga", headers=headers).status_code == 422
        aprobado = client.post(f"/finanzas/revelaciones/{id_manual}/resolucion", headers=headers, json={"aprobar": True})
        assert aprobado.status_code == 200, aprobado.text
        consulta = client.get(f"/finanzas/revelaciones/{id_manual}", headers=headers)
        assert consulta.status_code == 200, consulta.text
        contenido = consulta.json()["contenido"]
        filas = {a["id_activo_biologico"]: a for a in contenido[SECCION]}
        assert set(filas) == {a["id_activo_biologico"] for a in contenido["parr_50_conciliacion"]}
        assert filas[con_supuestos]["fuente"] == "MERCADO_ACTIVO"
        assert filas[con_supuestos]["tasa_descuento"] == 0
        assert filas[con_supuestos]["produccion_esperada"] == 0
        assert filas[con_supuestos]["datos_insuficientes"] is False
        assert filas[sin_supuestos]["fuente"] is None
        assert filas[sin_supuestos]["datos_insuficientes"] is True
        assert "condicion_corporal" in filas[sin_supuestos]["campos_faltantes"]

        excel = client.get(f"/finanzas/revelaciones/{id_manual}/descarga?formato=excel", headers=headers)
        assert excel.status_code == 200, excel.text
        with ZipFile(BytesIO(excel.content)) as libro:
            xml = libro.read("xl/worksheets/sheet1.xml")
            if "xl/sharedStrings.xml" in libro.namelist():
                xml += libro.read("xl/sharedStrings.xml")
        assert b"Datos insuficientes" in xml
        pdf = client.get(f"/finanzas/revelaciones/{id_manual}/descarga", headers=headers)
        assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
        assert len(notificador.avisos) == 2

    anterior = m06.reportes.obtener_informe(id_automatico)
    assert anterior["estado"] == "ARCHIVADO"
    assert anterior["hash_informe"] == aprobado_anterior["hash_informe"]
    assert anterior["contenido"] == aprobado_anterior["contenido"]
    assert all(fila["datos_insuficientes"] for fila in anterior["contenido"][SECCION])
    avisos = db_session.execute(text("""
        SELECT n.id_usuario, (e.detalle->>'id_informe')::integer
          FROM modulo1.notificaciones n
          JOIN modulo1.eventos e ON e.id_evento = n.id_evento
         WHERE e.detalle->>'motivo' = 'SUPUESTOS_REVELACIONES_INSUFICIENTES'
           AND (e.detalle->>'id_informe')::integer IN (:automatico, :manual)
    """), {"automatico": id_automatico, "manual": id_manual}).all()
    assert sorted(avisos) == sorted([(usuario, id_automatico), (usuario, id_manual)])
    assert otro_contador["id_usuario"] not in {a.id_usuario for a in avisos}
