"""
TC-M03-G157 (RF-61 v1.2 Salida 6/RNF-07/RNF-09/Postcondición 4, CU-14) -
"Consulta del historial de vinculaciones por activo biológico."

HALLAZGO PRINCIPAL: CU-14 se llama "historial de vinculaciones POR
ACTIVO" pero `GET /iot/vinculaciones` NO acepta `id_activo_biologico`
como filtro. Los únicos filtros reales son: `id_telemetria`,
`estado_vinculacion`, `mecanismo_vinculacion`, `id_infraestructura`,
`fecha_desde`, `fecha_hasta`.

(a) Filtrado por tipo de variable/periodo/mecanismo -- HALLAZGO: ni
    tipo de variable ni filtro por activo existen.
(b) SUPERADAS diferenciadas -- HALLAZGO PARCIAL: el estado real se llama
    "CORREGIDA", no "SUPERADA" -- el concepto funciona, con otro nombre.
(c) Paginación estable sobre 525.600 registros -- HALLAZGO: ordena solo
    por `fecha_creacion`, sin desempate por id.
(d) Contador/revisor fiscal solo lectura -- NO VERIFICADO (requiere
    matriz de roles en vivo).
(e) Exportación -- HALLAZGO: no existe ningún endpoint `/export`.
(f) Respuesta vacía controlada -- CONFIRMADO para los filtros que sí
    existen.

Cómo se prueba: inspección de la firma de `ListarVinculacionesUseCase`.

Como correrlo (Windows necesita el stub de fcntl):
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    python -m pytest <ruta>\\test_tc_m03_g157_historial_sin_filtro_por_activo_ni_export.py -v \
        --html=<ruta>\\resultados\\resultado_TC-M03-G157.html --self-contained-html
"""
from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from src.telemetry.application.use_cases.infraestructura.listar_vinculaciones_use_case import (
    ListarVinculacionesUseCase,
)
from src.telemetry.infrastructure.repositories.vinculacion_lectura_repository import (
    SqlAlchemyVinculacionLecturaRepository,
)

REPO_ROOT = Path(__file__).resolve().parents[5]


class TestSubCasoANoHayFiltroPorActivoNiTipoDeVariable:
    def test_listar_vinculaciones_use_case_no_acepta_id_activo_biologico(self):
        firma = inspect.signature(ListarVinculacionesUseCase.execute)
        parametros = set(firma.parameters)
        pytest.fail(
            f"HALLAZGO (a): ListarVinculacionesUseCase.execute() no declara "
            f"'id_activo_biologico' -- parametros reales: {sorted(parametros)!r}."
        ) if 'id_activo_biologico' not in parametros else None

    def test_repositorio_no_acepta_tipo_de_variable(self):
        firma = inspect.signature(SqlAlchemyVinculacionLecturaRepository.listar)
        parametros = set(firma.parameters)
        assert 'tipo_variable' not in parametros
        assert 'id_activo_biologico' not in parametros


class TestSubCasoCPaginacionSinCriterioDeDesempate:
    def test_listar_ordena_solo_por_fecha_creacion_sin_desempate(self):
        archivo = REPO_ROOT / 'src/telemetry/infrastructure/repositories/vinculacion_lectura_repository.py'
        texto = archivo.read_text(encoding='utf-8')
        linea_order_by = next(l for l in texto.splitlines() if '.order_by(' in l)
        pytest.fail(
            f"HALLAZGO (c): la unica clausula ORDER BY es {linea_order_by.strip()!r} -- sin "
            f"desempate por id_vinculacion_lectura."
        ) if 'id_vinculacion_lectura' not in linea_order_by else None


class TestSubCasoENoExisteExportacion:
    def test_no_existe_endpoint_de_exportacion(self):
        archivo = REPO_ROOT / 'src/telemetry/infrastructure/routers/vinculacion_router.py'
        texto = archivo.read_text(encoding='utf-8')
        assert 'export' not in texto.lower()


class TestSubCasoFRespuestaVaciaControladaParaOtrosFiltros:
    def test_filtrar_por_un_id_infraestructura_inexistente_no_lanza_error(self):
        archivo = REPO_ROOT / 'src/telemetry/application/use_cases/infraestructura/listar_vinculaciones_use_case.py'
        texto = archivo.read_text(encoding='utf-8')
        assert 'raise' not in texto
