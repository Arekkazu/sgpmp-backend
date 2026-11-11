# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-10 | Arekkazu | CP088/CP111/H-M05-19 RF-77/80/81: PDF sin recorte y legible; el reporte reabierto conserva su desglose |
"""Primera evaluación QA de M05: los PDF recortaban columnas y mostraban nombres internos, y un reporte de
gastos reabierto perdía el desglose que se vio al generarlo."""
from __future__ import annotations

import io
import re
from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

from src.supplies.application.use_cases.auditoria.exportar_auditoria_suministros_use_case import (
    _CAMPOS,
    ExportarAuditoriaSuministrosUseCase,
)
from src.supplies.application.use_cases.exportacion.generador_archivos import (
    Documento,
    _anchos,
    fecha,
    generar_pdf,
    moneda,
    numero,
)
from src.supplies.domain.entities.evento_auditoria_suministro import EventoAuditoriaSuministroConsulta
from src.supplies.domain.entities.reporte_gasto import (
    DesgloseCategoria,
    DesglosePeriodo,
    RegistroSinCosto,
    ReporteGasto,
    TendenciaGasto,
)
from src.supplies.infrastructure.repositories.reporte_gasto_repository import SqlAlchemyReporteGastoRepository

AHORA = datetime(2026, 11, 10, 15, tzinfo=timezone.utc)


def _evento(i: int) -> EventoAuditoriaSuministroConsulta:
    return EventoAuditoriaSuministroConsulta(
        id_auditoria_suministro=i, entidad_afectada="registro_suministro", tipo_operacion="UPDATE", id_usuario=12,
        resultado="EXITOSO", fecha_evento=AHORA, datos_anteriores=None, datos_nuevos=None, ip_origen="10.0.0.1",
        id_sesion=3, fecha_emision=None, id_activo_biologico=5, id_ciclo_productivo=40, costo_afectado=Decimal("180000"),
        origen_precio="MANUAL", clasificacion_registro="NIC41", retencion_aplicable="5 años", hash_integridad="a1" * 32,
        registro_incompleto=False, detalle_causa=None, numero_reintentos=0, fecha_intentos=None, id_gestion_fases=901,
    )


def test_formatos_de_moneda_numero_y_fecha():
    assert moneda(Decimal("322000.0000")) == "$ 322.000"
    assert moneda("1234.5") == "$ 1.234,50"
    assert moneda(-50) == "−$ 50"
    assert numero("1250.500", 3) == "1.250,5"
    assert fecha(date(2026, 1, 2)) == "02/01/2026"


def test_pdf_reparte_el_ancho_y_declara_idioma_titulo_y_autor():
    columnas = [f"Columna {i}" for i in range(22)]
    doc = Documento(titulo="Prueba", columnas=columnas, filas=[["x" * 64] * 22])
    pdf = generar_pdf(doc, AHORA).decode("latin1")
    assert "/Lang (es-CO)" in pdf and "/DisplayDocTitle true" in pdf and "/Author (SIGAB)" in pdf
    assert re.search(r"/MediaBox \[ 0 0 1190", pdf), "con más de 10 columnas la hoja pasa a A3 horizontal"
    assert len(_anchos(doc)) == 22 and all(p >= 7 for p in _anchos(doc))


def test_auditoria_excel_y_pdf_legibles_y_csv_tecnico():
    uc = ExportarAuditoriaSuministrosUseCase(read_port=SimpleNamespace(consultar=lambda _f: ([_evento(1)], 1)))
    csv_texto = uc._a_csv([_evento(1)])
    assert csv_texto.splitlines()[0].split(",") == _CAMPOS  # integraciones: nombres técnicos

    from openpyxl import load_workbook
    hoja = load_workbook(io.BytesIO(uc._a_xlsx([_evento(1)]))).active
    filas = [[c.value for c in f] for f in hoja.iter_rows()]
    encabezado = next(f for f in filas if f and f[0] == "N.º de evento")
    datos = filas[filas.index(encabezado) + 1]
    assert len(encabezado) == len(_CAMPOS)
    assert "Operación" in encabezado and "Clasificación" in encabezado and "id_auditoria_suministro" not in encabezado
    assert "Modificación" in datos and "Exitoso" in datos and "NIC-41 (5 años)" in datos and "$ 180.000" in datos

    assert uc._a_pdf([_evento(1)]).startswith(b"%PDF")


def test_reporte_reabierto_conserva_desglose_tendencia_y_sin_costo():
    reporte = ReporteGasto(
        fecha_inicio=date(2026, 10, 1), fecha_fin=date(2026, 10, 31), tipo_periodo="MENSUAL",
        gasto_total_acumulado=Decimal("1000000.0000"), id_activo_biologico=1035, id_usuario=7,
        gasto_promedio_individuo=Decimal("50000.0000"),
        desglose_categorias=[DesgloseCategoria("ALIMENTACION", Decimal("750000"), 12, Decimal("75")),
                             DesgloseCategoria("MEDICACION", Decimal("250000"), 3, Decimal("25"))],
        desglose_temporal=[DesglosePeriodo("2026-10", date(2026, 10, 1), date(2026, 10, 31), Decimal("1000000"))],
        registros_sin_costo=[RegistroSinCosto("MEDICACION", 9, date(2026, 10, 3), "Vacuna sin precio")],
        tendencia=TendenciaGasto(Decimal("1000000"), Decimal("400000"), Decimal("150"), "CALCULADA"),
        nota_bajas="Un individuo murió el 12/10/2026.",
    )
    guardados = []

    class Db:
        def add(self, orm):
            guardados.append(orm)

        def flush(self):
            guardados[-1].id_reporte_gasto_acumulado = 77
            guardados[-1].fecha_generacion = AHORA

        def refresh(self, _orm):
            pass

        def get(self, _modelo, _id):
            return guardados[-1]

    repo = SqlAlchemyReporteGastoRepository(Db())
    repo.guardar(reporte)
    reabierto = repo.obtener(77)

    assert reabierto.gasto_promedio_individuo == Decimal("50000.0000")
    assert [(d.categoria, d.subtotal, d.num_registros) for d in reabierto.desglose_categorias] == [
        ("ALIMENTACION", Decimal("750000"), 12), ("MEDICACION", Decimal("250000"), 3)]
    assert reabierto.desglose_temporal[0].fecha_fin == date(2026, 10, 31)
    assert reabierto.registros_sin_costo[0].descripcion == "Vacuna sin precio"
    assert reabierto.tendencia.variacion_porcentual == Decimal("150") and reabierto.tendencia.estado == "CALCULADA"
    assert reabierto.nota_bajas == "Un individuo murió el 12/10/2026."


def test_reporte_antiguo_rehace_el_desglose_por_categoria_con_las_columnas():
    orm = SimpleNamespace(
        id_reporte_gasto_acumulado=5, id_activo_biologico=5, id_infraestructura=None, fecha_incio_reporte=date(2026, 9, 1),
        fecha_fin_report=date(2026, 9, 30), categoria="CICLO_COMPLETO", total_costo_directo=Decimal("400"),
        total_costo_alimento=Decimal("300"), total_costo_medicamento=Decimal("100"), id_usuario=7, fecha_generacion=AHORA,
        json_parametros={"fecha_inicio": "2026-09-01"},
    )
    reporte = SqlAlchemyReporteGastoRepository._a_entidad(orm)
    assert [(d.categoria, d.subtotal, d.porcentaje) for d in reporte.desglose_categorias] == [
        ("ALIMENTACION", Decimal("300"), Decimal("75.00")), ("MEDICACION", Decimal("100"), Decimal("25.00"))]
