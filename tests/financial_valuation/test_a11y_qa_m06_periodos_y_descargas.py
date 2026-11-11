# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-10 | Arekkazu | TC-DIS-257/262/264 RF-92/93: períodos para quien solo consulta reportes y descargas en palabras |
"""Primera evaluación QA de M06: el Productor no veía ningún estado de resultados porque los períodos exigían el
permiso del cierre, y las descargas mostraban claves, montos crudos y estados sin traducir."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.financial_valuation.application.use_cases.reportes.exportar_reporte_use_case import ExportarReporteUseCase
from src.financial_valuation.infrastructure import rbac_auditoria
from src.financial_valuation.infrastructure.routers import m06_router
from src.identity_access.domain.entities.cuenta import Cuenta
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared import rbac
from src.shared.errors import AuthorizationError
from src.supplies.application.use_cases.exportacion import generador_archivos


class _Auditoria:
    eventos: list = []

    def __init__(self, _db) -> None:
        pass

    def registrar(self, evento) -> None:
        _Auditoria.eventos.append(evento)


class _Db:
    def commit(self):
        pass

    def rollback(self):
        pass

    def query(self, _m):
        return SimpleNamespace(filter=lambda *a, **k: SimpleNamespace(scalar=lambda: "Productor"))


def _usuario() -> UsuarioActual:
    return UsuarioActual(id_usuario=9, id_token=1, id_rol=2, id_estado_cuenta=Cuenta.ESTADO_ACTIVO)


def _request():
    from starlette.requests import Request
    return Request({"type": "http", "http_version": "1.1", "method": "GET", "scheme": "http", "path": "/finanzas/periodos",
                    "raw_path": b"", "query_string": b"", "headers": [], "client": ("qa", 1), "server": ("t", 80),
                    "path_params": {}, "route": SimpleNamespace(path="/finanzas/periodos")})


def _ruta_periodos():
    return next(r for r in m06_router.router.routes if getattr(r, "path", "") == "/finanzas/periodos" and "GET" in r.methods)


def test_periodos_aceptan_lectura_del_estado_de_resultados(monkeypatch):
    concedidos = {("estado_resultados", 2)}
    monkeypatch.setattr(rbac, "tiene_permiso_sobre", lambda _db, _rol, recurso, accion: (recurso, accion) in concedidos)
    monkeypatch.setattr(rbac_auditoria, "SqlAlchemyAuditoriaFinancieraRepository", _Auditoria)
    [dep] = [d.call for d in _ruta_periodos().dependant.dependencies if getattr(d.call, "audita_rechazo_rbac_m06", False)]
    dep(request=_request(), db=_Db(), usuario_actual=_usuario())  # no lanza: basta leer el estado de resultados

    concedidos.clear()
    _Auditoria.eventos = []
    with pytest.raises(AuthorizationError):
        dep(request=_request(), db=_Db(), usuario_actual=_usuario())
    assert _Auditoria.eventos and _Auditoria.eventos[0].payload["recurso"] == "cierre_periodo"


def _doc(monkeypatch) -> dict:
    capturado = {}
    monkeypatch.setattr(generador_archivos, "generar_pdf", lambda d, _a: capturado.setdefault("doc", d) and b"%PDF")
    import src.financial_valuation.application.use_cases.reportes.exportar_reporte_use_case as modulo
    monkeypatch.setattr(modulo, "generar_pdf", lambda d, _a: capturado.setdefault("doc", d) and b"%PDF")
    return capturado


def test_estado_de_resultados_descargado_con_signo_y_ganancia(monkeypatch):
    capturado = _doc(monkeypatch)
    estado = {"estado": "APROBADO", "version": 2, "filtros": {"id_especie": None}, "total_ingresos": "1650000.00",
              "total_gastos": "1190000.00", "resultado_neto": "460000.00", "fecha_aprobacion": "2026-10-02T09:00:00",
              "nombre_aprobador": "Ana Contadora",
              "componentes": {"ganancia_transformacion_biologica": "850000.00", "costos_mantenimiento": "1095000.00",
                              "activos_excluidos_cierre": [{"identificador": "BOV-102", "motivo": "Sin precio"}]}}
    uc = ExportarReporteUseCase(periodos=None, reportes=SimpleNamespace(obtener_estado=lambda _i: estado))
    uc.estado_resultados(71, "pdf")
    doc = capturado["doc"]
    filas = {f[0]: f for f in doc.filas}
    assert filas["Costos de mantenimiento"][1:] == ["Gasto", "−$ 1.095.000"]
    assert filas["Ganancia por transformación biológica"][2] == "$ 850.000"
    assert filas["Ganancia por variación de precio de mercado"][2] == "Sin actividad en el período"
    texto = "\n".join([*doc.encabezado, *doc.pie])
    assert "Resultado neto: +$ 460.000 (Ganancia)" in texto
    assert "por Ana Contadora" in texto and "Alcance: consolidado (sin filtros)" in texto and "BOV-102 (Sin precio)" in texto


def test_informe_descargado_con_secciones_y_campos_en_palabras(monkeypatch):
    capturado = _doc(monkeypatch)
    informe = {"estado": "APROBADO", "version_informe": "2026-09-V2", "hash_informe": "e" * 64, "fecha_aprobacion": None,
               "nombre_aprobador": None,
               "contenido": {"parr_50_conciliacion": [{"identificador": "BOV-101", "valor_cierre": "4855000.00", "id_activo_biologico": 7}],
                             "parr_54_56_activos_al_costo": "DATOS_INSUFICIENTES"}}
    uc = ExportarReporteUseCase(periodos=None, reportes=SimpleNamespace(obtener_informe=lambda _i: informe))
    uc.informe(83, "pdf")
    doc = capturado["doc"]
    assert doc.filas[0] == ["Conciliación del valor en libros (¶50)", "Activo: BOV-101; Valor al cierre: $ 4.855.000"]
    assert doc.filas[1] == ["Activos medidos al costo (¶54-56)", "Datos insuficientes para esta sección"]
    assert doc.encabezado[0] == "Estado: Aprobado"
