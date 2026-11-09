"""
TC-M03-G155 (RF-61 v1.2 CA-10/CA-12/Restricción 3/Salidas 5 y 7/
Postcondiciones 5 y 9/RNF-07, CU-12) - "Cierre: consumo por módulos
dependientes, indicadores y auditoría."

RELACIÓN CON TC-M03-G149/G152: RF-63 no audita nada del lado de RF-60; el
catálogo real de `estado_vinculacion` es 4 estados, no 5.

(a) "M06 recibe UNICAMENTE lecturas CONFIRMADA" -- HALLAZGO doble: (1) el
    estado `CONFIRMADA` no existe; (2) no existe ningún código en
    `src/supplies/` que lea `vinculacion_lectura`/`telemetria` -- no hay
    consumidor, con cualquier nombre de estado.
(b) Salida 5, indicadores de M08 -- HALLAZGO: cero de esos campos existe;
    no hay ningún endpoint de indicadores para vinculaciones.
(c) Salida 7, catálogo de 6 tipos de evento en RF-63 -- HALLAZGO: de los
    6, los 2 que no colisionan con nombres ya usados para otro fin
    (`VINCULACION_AUTOMATICA`, `TRASLADO_PROCESADO`) no existen tal cual;
    ninguno de los 3 casos de uso de vinculación recibe un
    `auditoria_repo`.
(d) Log injection en `motivo_correccion` -- NO APLICA EN LA FORMA
    PEDIDA: como no hay bitácora de RF-63 para RF-61, no hay "bitácora
    saneada o no" que verificar; el único `logger.warning()` nunca
    incluye `motivo`.
(e) Intentos denegados de G149/G150/G154 registrados -- NO APLICA: no
    hay ninguna bitácora de RF-63 para RF-61.

Cómo se prueba: grep exhaustivo sobre src/telemetry/ y src/supplies/ +
inspect.signature() sobre los 3 casos de uso de vinculación.

Como correrlo (Windows necesita el stub de fcntl):
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    python -m pytest <ruta>\\test_tc_m03_g155_cierre_consumo_e_indicadores_inexistentes.py -v \
        --html=<ruta>\\resultados\\resultado_TC-M03-G155.html --self-contained-html
"""
from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from src.telemetry.application.use_cases.infraestructura.corregir_vinculacion_use_case import (
    CorregirVinculacionUseCase,
)
from src.telemetry.application.use_cases.infraestructura.resolver_vinculacion_use_case import (
    ResolverVinculacionUseCase,
)
from src.telemetry.application.use_cases.infraestructura.vincular_lectura_activo_use_case import (
    VincularLecturaActivoUseCase,
)

REPO_ROOT = Path(__file__).resolve().parents[5]
_CATALOGO_SALIDA_7 = ('VINCULACION_AUTOMATICA', 'TRASLADO_PROCESADO')
# 'MANUAL', 'AMBIGUA', 'SIN_VINCULAR' y 'CORRECCION' se excluyen de este grep
# porque ya existen como valores literales de mecanismo_vinculacion/
# estado_vinculacion (falso positivo). El hallazgo estructural (ningun caso
# de uso recibe auditoria_repo) ya cubre estos 4 tambien.


def _grep(termino: str, carpeta: str) -> list[str]:
    return [
        str(p.relative_to(REPO_ROOT)) for p in (REPO_ROOT / carpeta).rglob('*.py')
        if termino in p.read_text(encoding='utf-8', errors='ignore')
    ]


class TestSubCasoANoHayConsumidorM06Real:
    def test_supplies_nic41_no_lee_vinculacion_lectura_ni_telemetria(self):
        archivos = _grep('VinculacionLectura', 'src/supplies') + _grep('vinculacion_lectura', 'src/supplies')
        pytest.fail(
            f"HALLAZGO (a): ningun archivo de src/supplies/ importa ni consulta "
            f"VinculacionLectura/vinculacion_lectura (encontrados: {archivos or 'ninguno'})."
        ) if not archivos else None


class TestSubCasoBIndicadoresDeM08NoExisten:
    @pytest.mark.parametrize('campo', [
        'total_CONFIRMADA', 'total_AMBIGUA', 'total_SIN_VINCULAR', 'total_PENDIENTE_REVISION',
    ])
    def test_campo_de_indicador_salida_5_no_existe(self, campo):
        archivos = _grep(campo, 'src/telemetry')
        pytest.fail(
            f"HALLAZGO (b): '{campo}' no existe en src/telemetry/ (encontrados: "
            f"{archivos or 'ninguno'})."
        ) if not archivos else None

    def test_no_hay_ningun_endpoint_de_indicadores_de_vinculacion(self):
        archivo = REPO_ROOT / 'src/telemetry/infrastructure/routers/vinculacion_router.py'
        texto = archivo.read_text(encoding='utf-8')
        rutas = [l.strip() for l in texto.splitlines() if '@router.' in l]
        assert len(rutas) == 4


class TestSubCasoCCatalogoDeAuditoriaRf63NoExiste:
    @pytest.mark.parametrize('tipo_evento', _CATALOGO_SALIDA_7)
    def test_tipo_de_evento_no_existe(self, tipo_evento):
        archivos = _grep(tipo_evento, 'src/telemetry')
        pytest.fail(
            f"HALLAZGO (c): '{tipo_evento}' no existe en src/telemetry/ (encontrados: "
            f"{archivos or 'ninguno'})."
        ) if not archivos else None

    @pytest.mark.parametrize('use_case_cls', [
        VincularLecturaActivoUseCase, ResolverVinculacionUseCase, CorregirVinculacionUseCase,
    ])
    def test_ningun_caso_de_uso_de_vinculacion_recibe_auditoria_repo(self, use_case_cls):
        firma = inspect.signature(use_case_cls.__init__)
        nombres = set(firma.parameters)
        pytest.fail(
            f"HALLAZGO (c): {use_case_cls.__name__}.__init__ no declara ningun parametro de "
            f"auditoria -- parametros reales: {sorted(nombres)!r}."
        ) if not any('auditoria' in p.lower() for p in nombres) else None


class TestSubCasoDLogInjectionSinSumideroAlcanzable:
    @pytest.mark.parametrize('archivo_rel', [
        'src/telemetry/application/use_cases/infraestructura/resolver_vinculacion_use_case.py',
        'src/telemetry/application/use_cases/infraestructura/corregir_vinculacion_use_case.py',
    ])
    def test_motivo_nunca_se_pasa_a_logger(self, archivo_rel):
        texto = (REPO_ROOT / archivo_rel).read_text(encoding='utf-8')
        bloque_logger = texto.split('logger.warning(')[1] if 'logger.warning(' in texto else ''
        assert 'motivo' not in bloque_logger.split(')')[0]
