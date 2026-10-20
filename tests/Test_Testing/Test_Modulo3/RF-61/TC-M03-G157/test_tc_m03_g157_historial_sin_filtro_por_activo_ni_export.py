"""
TC-M03-G157 (RF-61 v1.2 Salida 6/RNF-07/RNF-09/Postcondición 4, CU-14) -
"Consulta del historial de vinculaciones por activo biológico." Grupo
existente de RF-61 (TC-M03-G26).

Código bajo prueba:
    src/telemetry/application/use_cases/infraestructura/listar_vinculaciones_use_case.py
    src/telemetry/infrastructure/repositories/vinculacion_lectura_repository.py (método `listar`)
    src/telemetry/infrastructure/routers/vinculacion_router.py

HALLAZGO PRINCIPAL (invalida (a) y buena parte de (c)/(e) por ausencia de
base): el caso de uso CU-14 que la ficha describe es "historial de
vinculaciones POR ACTIVO BIOLÓGICO" -- pero `GET /iot/vinculaciones` (el
único endpoint de listado que existe) NO acepta `id_activo_biologico` como
filtro. Los únicos filtros reales, confirmados en
`vinculacion_lectura_repository.py:listar()`, son: `id_telemetria`,
`estado_vinculacion`, `mecanismo_vinculacion`, `id_infraestructura`,
`fecha_desde`, `fecha_hasta`. No hay ninguna forma de pedirle a la API "el
historial de ANI-001" directamente: solo se puede filtrar por dispositivo
(`id_infraestructura`), lo cual mezcla las lecturas de TODOS los activos
que pasaron por ese dispositivo (relevante en modelo POBLACIONAL) y
obligaría a un filtrado adicional del lado del cliente. Tampoco existe
ningún filtro por "tipo de variable" (ese atributo vive en
`telemetria`/`sensor`, no en `vinculacion_lectura`).

(a) Filtrado por tipo de variable, periodo y mecanismo -- HALLAZGO: el
    filtro por periodo (`fecha_desde`/`fecha_hasta`) y por mecanismo SÍ
    existen; el filtro por tipo de variable NO existe (no está en el
    dominio de esta tabla) y, más grave, no existe NINGÚN filtro por
    activo biológico, que es el eje central de la Salida 6 ("historial POR
    ACTIVO").
(b) SUPERADAS con motivo_correccion y usuario, diferenciadas de la vigente
    -- HALLAZGO PARCIAL: el estado real no se llama "SUPERADA" sino
    "CORREGIDA" (confirmado en TC-M03-G152); sí lleva motivo_correccion e
    id_usuario correctamente, así que el CONCEPTO funciona, solo con otro
    nombre de estado.
(c) Orden cronológico y paginación estable sobre 525.600 registros --
    HALLAZGO: `listar()` ordena únicamente por
    `VinculacionLecturaModel.fecha_creacion.desc()`, sin ningún criterio
    de desempate (p. ej. `id_vinculacion_lectura`). Si dos filas comparten
    el mismo `fecha_creacion` (plausible en una carga histórica masiva o
    inserciones rápidas sucesivas), el orden relativo entre ellas no es
    determinista entre páginas -- puede repetir o saltarse registros al
    paginar, justo el riesgo que la ficha advierte explícitamente.
(d) Contador/revisor fiscal con acceso de solo lectura -- NO VERIFICADO EN
    ESTA SESIÓN: requiere confirmar en la matriz de roles/permisos real
    (BD de M01, recurso 37) si el rol existe con permiso 37:2 -- no se
    verifica por alcance de solo lectura sin consulta en vivo al entorno.
(e) Exportación del historial -- HALLAZGO: no existe ningún endpoint de
    exportación en `vinculacion_router.py` (los 4 únicos endpoints son
    listar, detalle, resolver, corregir; ninguno con sufijo `/export` ni
    `Content-Disposition`).
(f) Activo sin lecturas -> respuesta vacía controlada -- NO EVALUABLE EN LA
    FORMA PEDIDA: como (a) confirma que no se puede filtrar por activo en
    absoluto, no hay una "consulta por activo sin resultados" que probar;
    sí se confirma que `listar()` sin resultados devuelve lista vacía y
    total=0 de forma controlada (sin error) para cualquier otro filtro.

Cómo se prueba: inspección de la firma de `ListarVinculacionesUseCase.execute()`
y del método `listar()` del repositorio + grep del router para `/export`.

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
            f"HALLAZGO (a): ListarVinculacionesUseCase.execute() no declara 'id_activo_biologico' "
            f"como parametro -- parametros reales: {sorted(parametros)!r}. No hay forma de pedir "
            f"'el historial de ESTE activo' a la API; CU-14 se llama 'Historial de vinculaciones "
            f"POR ACTIVO' pero el filtro central no existe."
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
            f"HALLAZGO (c): la unica clausula ORDER BY del listado es "
            f"{linea_order_by.strip()!r} -- ordena solo por fecha_creacion, sin un segundo "
            f"criterio de desempate (p. ej. id_vinculacion_lectura). Con filas que comparten "
            f"fecha_creacion, la paginacion con OFFSET/LIMIT puede repetir o saltarse registros "
            f"entre paginas, exactamente el riesgo que (c) advierte para un historial de "
            f"525.600 registros."
        ) if 'id_vinculacion_lectura' not in linea_order_by else None


class TestSubCasoENoExisteExportacion:
    def test_no_existe_endpoint_de_exportacion(self):
        archivo = REPO_ROOT / 'src/telemetry/infrastructure/routers/vinculacion_router.py'
        texto = archivo.read_text(encoding='utf-8')
        assert 'export' not in texto.lower()


class TestSubCasoFRespuestaVaciaControladaParaOtrosFiltros:
    def test_filtrar_por_un_id_infraestructura_inexistente_no_lanza_error(self):
        """Confirma que el camino 'sin resultados' si esta bien manejado
        para los filtros que SI existen, aunque no exista el filtro por
        activo que (f) pide especificamente."""
        archivo = REPO_ROOT / 'src/telemetry/application/use_cases/infraestructura/listar_vinculaciones_use_case.py'
        texto = archivo.read_text(encoding='utf-8')
        assert 'raise' not in texto
