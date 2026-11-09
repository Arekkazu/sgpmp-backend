# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-04 | Arekkazu | M06 RF-82..94: flujo NIC 41 de punta a punta contra PostgreSQL |
# | 2026-11-05 | Arekkazu | M06 RF-83..94: listados del período, resumen de auditoría y filtros inválidos |
# | 2026-11-08 | Arekkazu | INC-M06-314-G15 / INC-M06-332-G88: filtros de mediciones y cotización en período cerrado |
# | 2026-11-08 | Arekkazu | RFC-024 RF-88 v2.0 / RF-89 v1.1: aviso del cierre por activos al costo con precio y 400 en la justificación |
"""M06 de punta a punta contra Postgres real (migración c4d81e6f2a95 y triggers de modulo6).

Reconocimiento (¶26-27), medición por evento con separación precio/transformación (¶51), costos de
M05 (CONSUMO_INSUMO), reversión bloqueada, cierre con comprobante, estado de resultados, informe de
revelaciones, modelo de costo (¶30) y RBAC del router."""
from __future__ import annotations

import random
import string
import uuid
from datetime import timedelta
from decimal import Decimal as D

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.financial_valuation.application.use_cases.costos.registrar_costo_use_case import SolicitudCosto
from src.financial_valuation.application.use_cases.precios.registrar_precio_use_case import SolicitudPrecio
from src.financial_valuation.domain.entities.contabilidad import ParametroEspecie
from src.financial_valuation.infrastructure.factories.m06_factory import M06
from src.shared.errors import AppError
from src.shared.fechas import hoy_usuario

pytestmark = pytest.mark.integration

HOY = hoy_usuario()
NIT = "900123456"  # DV DIAN = 8
_MATRIZ = [("RECONOCIMIENTO_DIFERENCIA", "GANANCIA", "1586", "4250"), ("RECONOCIMIENTO_DIFERENCIA", "PERDIDA", "5250", "1586"),
           ("RECONOCIMIENTO_NACIMIENTO", "UNICO", "1586", "4251"), ("VARIACION_VR_TB", "GANANCIA", "1586", "4252"),
           ("VARIACION_VR_TB", "PERDIDA", "5252", "1586"), ("VARIACION_VR_PM", "GANANCIA", "1586", "4253"),
           ("VARIACION_VR_PM", "PERDIDA", "5253", "1586"), ("CONSUMO_INSUMO", "UNICO", "5105", "1405"),
           ("MANO_OBRA_PROPIA", "UNICO", "5106", "2505"), ("BAJA_ACTIVO", "UNICO", "6105", "1586"),
           ("BAJA_ACTIVO", "PERDIDA", "5310", "1586"), ("DEPRECIACION_ACTIVO_COSTO", "UNICO", "5160", "1592")]


class _Notificador:
    def __init__(self) -> None:
        self.avisos: list[str] = []

    def a_contadores(self, tipo_evento, mensaje, detalle, id_finca=None) -> None:
        self.avisos.append(mensaje)


def _id() -> int:
    return uuid.uuid4().int % (10**8) + 10**8


def _letras() -> str:
    """Los nombres de finca y área solo admiten letras (triggers de M09)."""
    return "".join(random.choices(string.ascii_letters, k=10))


@pytest.fixture
def contador(crear_usuario_db) -> dict:
    return crear_usuario_db(id_rol=5, estado=2)


@pytest.fixture
def m06(db_session: Session) -> M06:
    db_session.execute(text(
        "INSERT INTO modulo2.estados_activos_biologicos (id_estado_activo_biologico, nombre) VALUES "
        "(1,'ACTIVO'),(2,'INACTIVO'),(3,'EN_TRATAMIENTO'),(4,'AISLADO'),(5,'CERRADO'),(6,'BAJA') "
        "ON CONFLICT (id_estado_activo_biologico) DO NOTHING"))
    m = M06(db_session)
    m.__dict__["notificador"] = _Notificador()
    return m


def _finca(db: Session, id_usuario: int, nit: str = NIT, dv: str = "8") -> int:
    id_finca = _id()
    db.execute(text("SET LOCAL app.usuario_id = :u"), {"u": id_usuario})
    db.execute(text("""INSERT INTO modulo9.fincas (id_finca, nombre, ubicacion, tamano_h, fecha_actualizacion, fecha_creacion,
                         es_activo, tipo_id_tributaria, numero_id_tributaria, dv, razon_social)
                       VALUES (:f, :n, '{}', 10, now(), now(), true, 'NIT', :nit, :dv, 'Ganadería de Prueba SAS')"""),
               {"f": id_finca, "n": f"Finca Nic {_letras()}", "nit": nit, "dv": dv})
    db.execute(text("INSERT INTO modulo9.usuarios_fincas (id_usuario, id_finca) VALUES (:u, :f)"), {"u": id_usuario, "f": id_finca})
    db.execute(text("""INSERT INTO modulo9.infraestructuras (id_infraestructura, nombre, id_finca, superficie, es_activo, tipo)
                       VALUES (:f, :n, :f, 100, true, 'Corral')"""), {"f": id_finca, "n": f"Corral {_letras()}"})
    return id_finca


def _activo(db: Session, id_finca: int, id_usuario: int, *, especie: int, origen: str, costo, tipo: str = "INDIVIDUAL") -> int:
    id_activo = _id()
    db.execute(text("SET LOCAL session_replication_role = replica"))
    db.execute(text("""INSERT INTO modulo2.activos_biologicos (id_activo_biologico, id_especie, identificador, id_infraestructura,
                         tipo, fecha_inicio_ciclo, id_estado, descripcion, origen_financiero, costo_adquisicion,
                         atributos_dinamicos, id_usuario, fecha_creacion, soporte_documental, detalles_procedencia)
                       VALUES (:a, :e, :ident, :i, CAST(:t AS modulo2.enum_activo_biologico_tipo), current_date, 1, 'M06',
                               CAST(:o AS modulo2.enum_activo_biologico_origen_financiero), :c, '{}', :u, now(), 'Factura 1', '')"""),
               {"a": id_activo, "e": especie, "ident": f"M06-{id_activo}", "i": id_finca, "t": tipo, "o": origen, "c": costo,
                "u": id_usuario})
    db.execute(text("SET LOCAL session_replication_role = origin"))
    return id_activo


def _pesaje(db: Session, id_activo: int, kg: str, desfase=timedelta(0)) -> int:
    id_evento = _id()
    db.execute(text("SET LOCAL session_replication_role = replica"))
    db.execute(text("INSERT INTO modulo2.eventos_activos (id_eventos, id_activo_biologico, fecha) VALUES (:e, :a, now() + :d)"),
               {"e": id_evento, "a": id_activo, "d": desfase})
    db.execute(text("""INSERT INTO modulo2.eventos_crecimeinto (id_evento, tipo_medicion, valor_medicion, unidad_medida)
                       VALUES (:e, 'PESO', :kg, 'kg')"""), {"e": id_evento, "kg": D(kg)})
    db.execute(text("SET LOCAL session_replication_role = origin"))
    return id_evento


def _precio(m: M06, id_usuario: int, especie: int, valor: str, vigencia, fuente: str = "MERCADO_ACTIVO") -> dict:
    return m.registrar_precio().execute(SolicitudPrecio(
        id_especie=especie, categoria="PESO_KG", precio_unitario=D(valor), fecha_vigencia=vigencia, fuente=fuente,
        evidencia_documental="Boletín feria ganadera de prueba", confirmar_desviacion=True), id_usuario)


def _configurar(m: M06, id_usuario: int, especie: int, clasificacion: str = "CONSUMO", vida: int | None = None) -> None:
    m.guardar_parametro_especie().execute(ParametroEspecie(especie, clasificacion, "PESO_KG", vida), id_usuario)
    m.guardar_costos_venta().execute(especie, D("0.05"), D("0"), D("0"), id_usuario)


def _matriz(m: M06, id_usuario: int) -> None:
    for tipo, sentido, debito, credito in _MATRIZ:
        m.guardar_asignacion().execute(tipo, sentido, None, None, debito, credito, id_usuario)


def _provision_m05(db: Session, id_activo: int, monto: str, tipo: str = "ALIMENTO", fecha=None) -> None:
    import json
    db.execute(text("""INSERT INTO modulo6.recepciones_provisiones_m05 (id_evento_provision, modalidad, schema_version,
                         id_activo_biologico, json_contenido, fecha_recepcion)
                       VALUES (:id, 'INCREMENTAL', '1.1', :a, CAST(:c AS jsonb), now())"""),
               {"id": uuid.uuid4(), "a": id_activo, "c": json.dumps({
                   "id_tipo_suministro": tipo, "tipo_operacion": "REGISTRO", "costo_registro": monto,
                   "fecha_aplicacion": (fecha or HOY).isoformat(), "id_registro_suministro": str(uuid.uuid4())})})


def _escalar(db: Session, sql: str, **p):
    return db.execute(text(sql), p).scalar()


def test_flujo_nic41_reconocimiento_medicion_costos_cierre_y_reportes(db_session, m06, contador):
    uid = contador["id_usuario"]
    especie = 2
    finca = _finca(db_session, uid)
    _configurar(m06, uid, especie)
    _matriz(m06, uid)
    activo = _activo(db_session, finca, uid, especie=especie, origen="compra", costo=D("3000000"))
    _pesaje(db_session, activo, "400", -timedelta(minutes=5))
    _precio(m06, uid, especie, "8000", HOY - timedelta(days=10))

    # RF-82: VN = 400 kg × 8.000 × 0,95 = 3.040.000; compra a 3.000.000 → diferencia +40.000 (¶26-27).
    [propuesta] = [p for p in m06.propuestas().execute(uid) if p["id_activo_biologico"] == activo]
    assert propuesta["es_confirmable"], propuesta["bloqueos"]
    assert propuesta["valor_inicial"] == D("3040000.0000")
    assert propuesta["hechos"] == [{"tipo_hecho": "RECONOCIMIENTO_DIFERENCIA", "sentido": "GANANCIA", "valor": D("40000.00")}]
    reconocido = m06.confirmar_reconocimiento().execute(activo, uid)
    assert [(ln["cuenta_debito"], ln["cuenta_credito"], ln["estado"]) for ln in reconocido["lineas"]] == [("1586", "4250", "REGISTRADA")]
    with pytest.raises(AppError) as fa1:
        m06.confirmar_reconocimiento().execute(activo, uid)
    assert fa1.value.code == "RECONOCIMIENTO_EXISTENTE"

    # RF-83/86: pesaje 420 kg y precio 8.500 → precio = 400×500×0,95 = 190.000; TB = 20×8.500×0,95 = 161.500.
    _precio(m06, uid, especie, "8500", HOY)
    evento = _pesaje(db_session, activo, "420")
    resultado_eventos = m06.procesar_eventos().execute()
    assert resultado_eventos.get("PROCESADO") == 1, (resultado_eventos, db_session.execute(text("SELECT resultado, detalle FROM modulo6.procesamientos_eventos_m02")).all())
    lineas = {(ln.tipo_hecho, ln.sentido): ln.valor for ln in m06.asientos.del_activo(activo)}
    assert lineas[("VARIACION_VR_TB", "GANANCIA")] == D("161500.00")
    assert lineas[("VARIACION_VR_PM", "GANANCIA")] == D("190000.00")

    # Listados del período para las vistas: cada registro trae el activo por su identificador de negocio.
    id_periodo = m06.periodos.que_contiene(NIT, HOY).id_periodo_contable
    [medicion] = [x for x in m06.valoraciones.mediciones_del_periodo(id_periodo) if x["id_activo_biologico"] == activo]
    assert medicion["variacion_total"] == D("351500.0000") and medicion["identificador"] and medicion["especie"]
    # INC-M06-314-G15: la medición se consulta por su evento y trae el evento y el período que la originaron.
    [por_evento] = m06.valoraciones.mediciones_del_periodo(id_periodo, id_evento=evento)
    assert (por_evento["id_evento"], por_evento["id_periodo_contable"]) == (evento, id_periodo)
    assert m06.valoraciones.mediciones_del_periodo(id_periodo, id_evento=evento, tiene_valor_estimado=True) == []
    variaciones = {x["tipo"]: x for x in m06.valoraciones.variaciones_del_periodo(id_periodo) if x["id_activo_biologico"] == activo}
    assert set(variaciones) == {"GANANCIA_TRANSFORMACION_BIOLOGICA", "GANANCIA_PRECIO_MERCADO"}
    assert all(v["id_linea"] and v["estado_trazabilidad"] for v in variaciones.values())
    assert any(c["id_activo_biologico"] == activo for c in m06.valoraciones.calculos_del_periodo(id_periodo))

    # M05 → RF-90: consumo de alimento = gasto contra inventario (CONSUMO_INSUMO), nunca resta del valor.
    _provision_m05(db_session, activo, "150000")
    _provision_m05(db_session, activo, "80000", tipo="SERVICIO_VETERINARIO")
    assert m06.procesar_provisiones().execute()["PROCESADO"] == 2
    lineas = {(ln.tipo_hecho, ln.sentido): ln.valor for ln in m06.asientos.del_activo(activo)}
    assert lineas[("CONSUMO_INSUMO", "UNICO")] == D("150000.00") and len(lineas) == 4  # el servicio no genera línea (D-3)

    # RF-82 R2 b: con mediciones posteriores la reversión se bloquea.
    with pytest.raises(AppError) as bloqueo:
        m06.revertir_reconocimiento().execute(activo, "Error en el costo de adquisición registrado", uid)
    assert bloqueo.value.code == "REVERSION_BLOQUEADA"

    # RF-87: cierre del período (sin variación nueva) con comprobante por tipo de hecho y especie.
    periodo = m06.periodos.que_contiene(NIT, HOY)
    assert m06.cierre().prevalidar(periodo).puede_cerrar
    cierre = m06.cierre().execute(periodo.id_periodo_contable, uid)
    assert cierre["estado"] == "CERRADO"
    codigos = sorted(c["codigo"].split("-")[3] for c in cierre["comprobantes"])
    assert codigos == ["CONSUMO_INSUMO", "RECONOCIMIENTO_DIFERENCIA", "VARIACION_VR_PM", "VARIACION_VR_TB"]
    assert m06.notificador.avisos and "cerrado" in m06.notificador.avisos[-1]

    # RF-93: ingresos 40.000 + 161.500 + 190.000; gastos 150.000 + 80.000 (el servicio sí es gasto del período).
    id_estado = cierre["reportes"]["estado_resultados"]["id_estado"]
    estado = m06.reportes.obtener_estado(id_estado)
    assert (estado["total_ingresos"], estado["total_gastos"], estado["resultado_neto"]) == (
        D("391500.0000"), D("230000.0000"), D("161500.0000"))

    # Un hecho con fecha del período cerrado entra al período siguiente (RF-87 v1.1, sin reapertura).
    _provision_m05(db_session, activo, "1000")
    m06.procesar_provisiones().execute()
    siguiente = _escalar(db_session, "SELECT id_periodo_contable FROM modulo6.registros_costos ORDER BY id_registro_costo DESC LIMIT 1")
    assert siguiente == cierre["id_periodo_siguiente"]
    with pytest.raises(AppError) as cerrado:
        m06.cierre().execute(periodo.id_periodo_contable, uid)
    assert cerrado.value.code == "PERIODO_CERRADO"
    # RF-COT FA-3: con el período de hoy cerrado la cotización se rechaza, no pasa al período siguiente.
    with pytest.raises(AppError) as cotizacion:
        m06.registrar_cotizacion().execute([activo], D("3500000"), None, None, uid)
    assert cotizacion.value.code == "PERIODO_CONTABLE_CERRADO"

    # RF-92: borrador con revelaciones manuales, aprobación y descarga.
    informe = m06.informe_revelaciones().generar(periodo.id_periodo_contable, {"declaracion_sin_novedad": True},
                                                 "Diferencias de redondeo revisadas por el Contador", uid)
    assert informe["version_informe"].endswith("-V2")  # la V1 la generó el cierre
    aprobado = m06.informe_revelaciones().resolver(informe["id_informe"], True, None, uid)
    assert aprobado["estado"] == "APROBADO"
    contenido, tipo, _, _ = m06.exportar().informe(informe["id_informe"], "pdf")
    assert tipo == "application/pdf" and contenido[:4] == b"%PDF"
    m06.estado_resultados().aprobar(id_estado, uid)
    assert m06.exportar().comprobantes(periodo.id_periodo_contable, "csv")[0].startswith(b"Comprobante")

    # RF-94: la auditoría registró la cadena completa con hash.
    eventos = m06.consultar_auditoria().execute({"id_periodo_contable": periodo.id_periodo_contable}, 1, 500, True)
    tipos = {e["tipo_evento"] for e in eventos["eventos"]}
    assert {"CIERRE_PERIODO_INICIADO", "CIERRE_PERIODO_COMPLETADO", "COMPROBANTE_GENERADO"} <= tipos
    assert all(e["integridad_verificable"] for e in eventos["eventos"])
    assert sum(eventos["resumen_severidad"].values()) == eventos["total_registros"]
    assert not any(str(e["activo"]).startswith("Activo #") for e in eventos["eventos"])


def test_modelo_de_costo_sin_precio_y_bloqueo_sin_valor(db_session, m06, contador):
    uid = contador["id_usuario"]
    especie = 3  # sin precios en el repositorio
    finca = _finca(db_session, uid)
    _configurar(m06, uid, especie, vida=24)
    nacido = _activo(db_session, finca, uid, especie=especie, origen="nacimiento", costo=None)
    comprado = _activo(db_session, finca, uid, especie=especie, origen="compra", costo=D("1200000"))
    _pesaje(db_session, nacido, "30")
    _pesaje(db_session, comprado, "30")

    # FA-7: nacimiento sin precio ni costo → bloqueado (¶30 no tiene base fiable).
    with pytest.raises(AppError) as fa7:
        m06.confirmar_reconocimiento().execute(nacido, uid)
    assert fa7.value.code == "RECONOCIMIENTO_BLOQUEADO_SIN_VALOR"
    # RF-88 A: compra sin precio → modelo de costo por el costo de adquisición; la compra entra por factura.
    resultado = m06.confirmar_reconocimiento().execute(comprado, uid)
    assert resultado["indicador_valoracion"] == "VALORACION_POR_COSTO" and resultado["lineas"] == []
    # Con precio disponible, ¶30 exige pasar a valor razonable: la diferencia va a resultados.
    _precio(m06, uid, especie, "50000", HOY)
    m06.guardar_asignacion().execute("VARIACION_VR_PM", "GANANCIA", None, None, "1586", "4253", uid)
    cambio = m06.cambiar_a_valor_razonable().execute(comprado, uid)
    assert cambio["valor_razonable"] == D("1425000.0000")  # 30 × 50.000 × 0,95
    assert cambio["diferencia"] == D("225000.0000")
    assert m06.valoraciones.valoracion_costo_activa(comprado) is None


def test_costo_manual_con_factura_y_reparto(db_session, m06, contador):
    uid = contador["id_usuario"]
    especie = 2
    finca = _finca(db_session, uid, nit="860069804", dv="2")
    _configurar(m06, uid, especie)
    _matriz(m06, uid)
    _precio(m06, uid, especie, "8000", HOY - timedelta(days=5))
    activos = []
    for _ in range(2):
        a = _activo(db_session, finca, uid, especie=especie, origen="nacimiento", costo=None)
        _pesaje(db_session, a, "100", -timedelta(minutes=1))
        m06.confirmar_reconocimiento().execute(a, uid)
        activos.append(a)
    factura = dict(subtipo_costo="VETERINARIO", origen_costo="SERVICIO_TERCERO", monto_costo=D("100.01"), fecha_costo=HOY,
                   activos_reparto=activos, tercero_nit="800555111", tercero_dv="1", tercero_razon_social="Veterinaria SAS",
                   factura_prefijo="FE", factura_numero="88231", fecha_factura=HOY, fecha_vencimiento_factura=HOY)
    m06.guardar_asignacion().execute("CONSUMO_INSUMO", "UNICO", None, "VETERINARIO", "5135", "1405", uid)
    registro = m06.registrar_costo().execute(SolicitudCosto(**factura), uid)
    montos = sorted(r["monto_costo"] for r in registro["registros"])
    assert montos == [D("50.00"), D("50.01")] and registro["aviso"]  # CA-7 y aviso de fuente única
    assert {r["vehiculo_contable"] for r in registro["registros"]} == {"FACTURA_COMPRA"}
    with pytest.raises(AppError) as duplicada:  # CA-3
        m06.registrar_costo().execute(SolicitudCosto(**factura), uid)
    assert duplicada.value.code == "FACTURA_DUPLICADA"
    with pytest.raises(AppError) as reservado:  # FA-12
        m06.registrar_costo().execute(SolicitudCosto(**{**factura, "origen_costo": "CONSUMO_INVENTARIO"}), uid)
    assert reservado.value.code == "ORIGEN_RESERVADO_M05"


def test_rbac_contador_si_productor_no(db_session, crear_usuario_db, crear_auth_headers, monkeypatch):
    from src.financial_valuation.infrastructure.routers.m06_router import router
    from src.shared import jwt as jwt_module
    from src.shared.database import get_db
    from src.shared.error_handlers import register_error_handlers

    app = FastAPI()
    register_error_handlers(app)
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db_session
    from tests.integration.conftest import JWT_SECRET_INTEGRACION

    monkeypatch.setattr(jwt_module, "_SECRET_KEY", JWT_SECRET_INTEGRACION)
    with TestClient(app, raise_server_exceptions=False) as cliente:
        contador = crear_auth_headers(crear_usuario_db(id_rol=5, estado=2))
        productor = crear_auth_headers(crear_usuario_db(id_rol=2, estado=2))
        assert cliente.get("/finanzas/precios", headers=contador).status_code == 200
        assert cliente.get("/finanzas/precios", headers=productor).status_code == 403
        # Un filtro fuera del catálogo es un 400, no una lista vacía silenciosa.
        assert cliente.get("/finanzas/costos?estado=INEXISTENTE", headers=contador).status_code == 400
        assert cliente.get("/finanzas/cotizaciones?estado=x", headers=contador).status_code == 400
        assert cliente.get("/finanzas/periodos/1/mediciones", headers=contador).status_code == 200
        assert cliente.get("/finanzas/periodos/1/mediciones?id_evento=0", headers=contador).status_code == 400
        assert cliente.get("/finanzas/periodos/1/mediciones?tiene_valor_estimado=talvez", headers=contador).status_code == 400
        assert cliente.post("/finanzas/costos", headers=contador,
                            json={"subtipo_costo": "ALIMENTO", "origen_costo": "MANO_OBRA_PROPIA", "monto_costo": "1",
                                  "fecha_costo": HOY.isoformat(), "id_lote": 3}).status_code in (400, 422)  # CA-8


def test_cada_tipo_de_evento_de_auditoria_tiene_descripcion_legible(db_session):
    """Un tipo sin descripción saldría al usuario como código crudo (CLAUDE.md § Textos visibles)."""
    from src.financial_valuation.application.use_cases.auditoria.consultar_auditoria_financiera_use_case import DESCRIPCIONES

    tipos = db_session.execute(text("SELECT unnest(enum_range(NULL::modulo6.enum_auditoria_financiera_tipo_evento))::text")).scalars()
    assert set(tipos) == set(DESCRIPCIONES)


def test_aviso_de_vencimiento_queda_marcado_en_la_bandeja(db_session, contador):
    """INC-M06-299-G81: la marca del aviso vive en el evento de la notificación, no en memoria."""
    from src.financial_valuation.infrastructure.adapters.notificacion_financiera_m01_adapter import (
        NotificacionFinancieraM01Adapter,
    )

    adaptador = NotificacionFinancieraM01Adapter(
        lambda: Session(bind=db_session.connection(), join_transaction_mode="create_savepoint"))
    marca = {"id_precio_mercado": _id(), "aviso": "15_DIAS"}
    assert not adaptador.ya_notificado("ALERTA_FINANCIERA_NIC41", marca)
    adaptador.a_contadores("ALERTA_FINANCIERA_NIC41", "El precio de mercado vence pronto.", marca)
    assert adaptador.ya_notificado("ALERTA_FINANCIERA_NIC41", marca)
    assert not adaptador.ya_notificado("ALERTA_FINANCIERA_NIC41", {**marca, "aviso": "7_DIAS"})


def test_cierre_avisa_activos_al_costo_con_precio_y_justificacion_corta_es_400(db_session, m06, contador):
    """RFC-024: RF-88 v2.0 (aviso de cierre) y RF-89 v1.1 CA-5 (justificación de estimación < 50 → 400)."""
    uid = contador["id_usuario"]
    especie = 3  # sin precios: el activo entra al costo
    finca = _finca(db_session, uid, nit="830095213", dv="0")
    _configurar(m06, uid, especie, vida=24)
    _matriz(m06, uid)
    comprado = _activo(db_session, finca, uid, especie=especie, origen="compra", costo=D("1200000"))
    assert m06.confirmar_reconocimiento().execute(comprado, uid)["indicador_valoracion"] == "VALORACION_POR_COSTO"

    with pytest.raises(AppError) as corta:
        _precio(m06, uid, especie, "50000", HOY, fuente="ESTIMADA")  # sin justificación
    assert (corta.value.status_code, corta.value.code) == (400, "JUSTIFICACION_ESTIMACION_INSUFICIENTE")

    _precio(m06, uid, especie, "50000", HOY)
    periodo = m06.periodos.que_contiene("830095213", HOY)
    cierre = m06.cierre().execute(periodo.id_periodo_contable, uid)
    identificador = f"M06-{comprado}"
    assert cierre["activos_al_costo_con_precio"] == [identificador]
    assert any(identificador in aviso and "valor razonable" in aviso for aviso in m06.notificador.avisos)
