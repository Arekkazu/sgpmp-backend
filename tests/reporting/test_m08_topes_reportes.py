"""RF-104: los reportes de M08 tienen tope de rango, de frecuencia y de cola por usuario."""
from datetime import date
from types import SimpleNamespace

import pytest

from src.reporting.application.use_cases.reportes import generacion
from src.reporting.application.use_cases.reportes.solicitar_reporte_use_case import (
    MAX_EN_PROCESO_POR_USUARIO,
    SolicitarReporteUseCase,
)
from src.reporting.domain.reportes.catalogo import CATALOGO, MAX_DIAS_TELEMETRIA, validar_filtros
from src.reporting.domain.reportes.solicitud import EN_PROCESO, GENERADO
from src.shared.errors import TooManyRequestsError, ValidationError

HOY = date(2026, 11, 23)
_TELEMETRIA = CATALOGO["REPORTE_TELEMETRIA"]


def test_telemetria_rechaza_rangos_de_anos():
    with pytest.raises(ValidationError):
        validar_filtros(_TELEMETRIA, {"fecha_inicio": "2000-01-01", "fecha_fin": "2026-11-22",
                                      "infraestructura_id": 1}, HOY)


def test_telemetria_acepta_un_mes():
    limpios = validar_filtros(_TELEMETRIA, {"fecha_inicio": "2026-10-23", "fecha_fin": "2026-11-22",
                                            "infraestructura_id": 1}, HOY)
    assert (limpios["fecha_fin"] - limpios["fecha_inicio"]).days <= MAX_DIAS_TELEMETRIA


def test_el_tope_de_rango_es_solo_para_telemetria():
    otro = next(d for t, d in CATALOGO.items() if t != "REPORTE_TELEMETRIA"
                and {"fecha_inicio", "fecha_fin"} <= {f.nombre for f in d.filtros}
                and not any(f.obligatorio for f in d.filtros if f.nombre not in ("fecha_inicio", "fecha_fin")))
    validar_filtros(otro, {"fecha_inicio": "2020-01-01", "fecha_fin": "2026-11-22"}, HOY)


def test_limite_de_solicitudes_por_minuto():
    for _ in range(generacion.SOLICITUDES_POR_MINUTO):
        generacion.limitar_solicitudes(987654)
    with pytest.raises(TooManyRequestsError):
        generacion.limitar_solicitudes(987654)


def test_tope_de_reportes_en_proceso_antes_de_armar_nada():
    repo = SimpleNamespace(listar_por_usuario=lambda id_usuario, limite: (
        [SimpleNamespace(estado=EN_PROCESO)] * MAX_EN_PROCESO_POR_USUARIO + [SimpleNamespace(estado=GENERADO)]))

    def abrir_fuente(*_):
        raise AssertionError("no debe abrir la instantánea")

    caso = SolicitarReporteUseCase(None, repo, abrir_fuente, None, None)
    solicitante = SimpleNamespace(id_usuario=987655, zona_horaria="UTC")
    with pytest.raises(TooManyRequestsError) as exc:
        caso.execute("REPORTE_TELEMETRIA", "EXCEL", {}, solicitante)
    assert exc.value.code == "REPORTES_EN_PROCESO"
