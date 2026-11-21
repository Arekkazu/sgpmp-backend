# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-10 | Arekkazu | INC-M05-269-G23 RF-77: PDF con nombres del activo, desglose por período y notas de tendencia |
# | 2026-11-10 | Arekkazu | TC-DIS-204 RF-77: montos en pesos, filas legibles y tendencia con signo |
"""El PDF del reporte de gastos salía con ids, sin desglose mensual y sin la nota de la tendencia."""
from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

from src.supplies.application.use_cases.reporte_gastos import exportar_reporte_gastos_use_case as modulo
from src.supplies.domain.entities.reporte_gasto import DesgloseCategoria, DesglosePeriodo, ReporteGasto, TendenciaGasto


class _Detalle:
    def describir_alcance(self, id_activo, id_infra, id_especie):
        return {"identificador": "QA-BOV-57", "tipo_activo": "INDIVIDUAL", "especie": "Bovino",
                "infraestructura": "Corral 2"}


def _reporte():
    return ReporteGasto(
        fecha_inicio=date(2026, 1, 1), fecha_fin=date(2026, 2, 28), tipo_periodo="MENSUAL",
        gasto_total_acumulado=Decimal("10.0000"), id_activo_biologico=57,
        desglose_categorias=[DesgloseCategoria("ALIMENTACION", Decimal("10.0000"), 1, Decimal("100"))],
        desglose_temporal=[DesglosePeriodo("2026-01", date(2026, 1, 1), date(2026, 1, 31), Decimal("10.0000")),
                           DesglosePeriodo("2026-02", date(2026, 2, 1), date(2026, 2, 28), Decimal("0"))],
        tendencia=TendenciaGasto(Decimal("10"), Decimal("0"), None, "SIN_BASE_COMPARATIVA",
                                 nota="No existen gastos registrados en el período anterior equivalente."),
    )


def test_pdf_lleva_nombres_desglose_y_nota(monkeypatch):
    capturado = {}
    monkeypatch.setattr(modulo, "generar_pdf", lambda doc, ahora: capturado.setdefault("doc", doc) and b"%PDF")
    uc = modulo.ExportarReporteGastosUseCase(
        db=None, reporte_repo=None, generador=SimpleNamespace(detalle_port=_Detalle()), archivo_repo=None,
        logo_port=SimpleNamespace(ruta_logo=lambda **_: None), auditoria_port=None)

    uc._pdf(_reporte(), [], datetime(2026, 11, 10, tzinfo=timezone.utc), 1)
    doc = capturado["doc"]

    assert doc.encabezado[0] == "Activo: QA-BOV-57 (individual) · Área: Corral 2 · Especie: Bovino"
    assert "(Mensual)" in doc.encabezado[1]
    texto = "\n".join(doc.pie)
    assert "Alimentación: $ 10 (100 %)" in texto
    assert "Desglose mensual:" in texto and "01/02/2026 – 28/02/2026: $ 0" in texto
    assert "sin base comparativa" in texto
    assert "No existen gastos registrados en el período anterior equivalente." in texto
    assert "SIN_BASE_COMPARATIVA" not in texto and "ALIMENTACION" not in texto


def test_pdf_sin_valores_crudos_y_tendencia_con_signo(monkeypatch):
    """TC-DIS-204: ni «monto_cop», ni «ALIMENTACION», ni «322000.0000 COP», ni «CALCULADA 250.0»."""
    capturado = {}
    monkeypatch.setattr(modulo, "generar_pdf", lambda doc, ahora: capturado.setdefault("doc", doc) and b"%PDF")
    uc = modulo.ExportarReporteGastosUseCase(
        db=None, reporte_repo=None, generador=SimpleNamespace(detalle_port=_Detalle()), archivo_repo=None,
        logo_port=SimpleNamespace(ruta_logo=lambda **_: None), auditoria_port=None)
    reporte = _reporte()
    reporte.gasto_total_acumulado = Decimal("322000.0000")
    reporte.tendencia = TendenciaGasto(Decimal("350"), Decimal("100"), Decimal("250.0"), "CALCULADA")
    filas = [["2026-01-05", "ALIMENTACION", "Concentrado", Decimal("322000.0000"), "VALIDADO"],
             ["2026-01-06", "MEDICACION", "Vacuna", "", "SIN_COSTO_REGISTRADO"]]

    uc._pdf(reporte, filas, datetime(2026, 11, 10, tzinfo=timezone.utc), 1)
    doc = capturado["doc"]

    assert doc.columnas == ["Fecha", "Categoría", "Descripción", "Monto", "Estado"]
    assert doc.filas[0] == ["05/01/2026", "Alimentación", "Concentrado", "$ 322.000", "Validado"]
    assert doc.filas[1][4] == "Sin costo registrado"
    todo = "\n".join([*doc.encabezado, *doc.pie])
    assert "Gasto total acumulado: $ 322.000" in todo
    assert "Tendencia frente al período anterior: +250 % (el gasto subió; período anterior $ 100)" in todo
    for crudo in ("monto_cop", "ALIMENTACION", "COP", "CALCULADA"):
        assert crudo not in todo
