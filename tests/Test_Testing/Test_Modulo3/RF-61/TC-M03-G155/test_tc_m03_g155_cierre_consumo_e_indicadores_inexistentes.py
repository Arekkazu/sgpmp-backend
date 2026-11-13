"""
TC-M03-G155 (RF-61 v1.2 CA-10/CA-12/Restricción 3/Salidas 5 y 7/
Postcondiciones 5 y 9/RNF-07, CU-12) - "Cierre: consumo por módulos
dependientes, indicadores y auditoría."

REEJECUTADO 2026-10-30 CONTRA CÓDIGO POST-MERGE (origin/test, 2026-10-29,
DEV-44 Leandro) -- este TC nunca se había reverificado en ninguna ronda
anterior. El estado real de `estado_vinculacion` (confirmado también en
TC-M03-G152 reescrito en esta misma ronda) es
`SIN_VINCULAR|CONFIRMADA|PENDIENTE_REVISION|SUPERADA` -- no los 4/5
estados que asumía esta redacción anterior ni el AMBIGUA que esta
redacción seguía citando.

HALLAZGO PRINCIPAL ACTUALIZADO (c): INVERTIDO POR COMPLETO. Sí existe una
bitácora RF-63 real para RF-61: `evidencia_vinculacion.py::registrar_evidencia()`
(DEV-44, 2026-10-22) construye un `EventoAuditoriaIot` real
(`componente_origen=ComponenteOrigen.RF61`, con `hash_integridad` vía
`_calcular_hash()`, igual que el resto de RF-63) y LOS TRES casos de uso
de vinculación (`VincularLecturaActivoUseCase`, `ResolverVinculacionUseCase`,
`CorregirVinculacionUseCase`) reciben un `auditoria_repo` real por
constructor y lo invocan. Catálogo real de tipos de evento confirmado por
grep directo: `VINCULACION_AUTOMATICA`/`SIN_VINCULAR`/`VINCULACION_AMBIGUA`
(desde `vincular_lectura_activo_use_case.py`), `VINCULACION_MANUAL` (desde
`resolver_vinculacion_use_case.py`), `CORRECCION_VINCULACION` (desde
`corregir_vinculacion_use_case.py`) y `TRASLADO_PROCESADO` (desde
`vinculacion_traslado_m03_adapter.py`) -- los 2 nombres que esta redacción
daba por inexistentes (`VINCULACION_AUTOMATICA`, `TRASLADO_PROCESADO`) SÍ
existen tal cual, literalmente.

(a) "M06 recibe UNICAMENTE lecturas CONFIRMADA" -- HALLAZGO VIGENTE SIN
    CAMBIOS: `CONFIRMADA` sí es un estado real ahora (ver arriba), pero
    sigue sin existir ningún código en `src/supplies/` que lea
    `vinculacion_lectura`/`telemetria` -- no hay consumidor M06, con
    cualquier nombre de estado.
(b) Salida 5, indicadores de M08 -- HALLAZGO VIGENTE SIN CAMBIOS: cero de
    esos campos existe; el router de vinculaciones sigue con exactamente
    4 rutas (ninguna de indicadores/agregados).
(c) Salida 7, catálogo de eventos de RF-63 -- HALLAZGO INVERTIDO (ver
    arriba).
(d) Log injection en `motivo_correccion` -- SIGUE SIN APLICAR EN LA FORMA
    PEDIDA, pero por una razón distinta a la original: ya SÍ existe una
    bitácora RF-63 real para RF-61 (contradice la premisa "no hay
    bitácora"), y el `motivo` del DTO SÍ llega a ella
    (`corregir_vinculacion_use_case.py`: `registrar_evidencia(...,
    {'motivo': dto.motivo}, ...)`) -- pero como payload estructurado
    (`accion_detallada`, un dict), no como texto libre interpolado en un
    mensaje de log. El único `logger.warning()` de esta ruta sigue sin
    incluir `motivo` en su mensaje.
(e) Intentos denegados de G149/G150/G154 registrados -- NO REEVALUADO EN
    DETALLE esta ronda (esos TC no son RF-60/RF-61/RF-71): dado que (c)
    se invirtió, la premisa "no hay ninguna bitácora de RF-63 para
    RF-61" ya no es cierta en general, así que esta conclusión derivada
    tampoco puede darse por válida sin revisarla directamente.

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
_CATALOGO_SALIDA_7 = (
    'VINCULACION_AUTOMATICA', 'TRASLADO_PROCESADO', 'VINCULACION_MANUAL',
    'CORRECCION_VINCULACION',
)


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


class TestSubCasoCCatalogoDeAuditoriaRf63AhoraSiExisteParaRf61:
    @pytest.mark.parametrize('tipo_evento', _CATALOGO_SALIDA_7)
    def test_tipo_de_evento_si_existe_tras_el_merge(self, tipo_evento):
        archivos = _grep(tipo_evento, 'src/telemetry')
        pytest.fail(
            f"HALLAZGO (c) INVERTIDO: '{tipo_evento}' SI existe en src/telemetry/ tras el "
            f"merge de origin/test (encontrados: {archivos}) -- la ronda anterior (codigo "
            f"stale) afirmo que no existia."
        ) if archivos else None

    @pytest.mark.parametrize('use_case_cls', [
        VincularLecturaActivoUseCase, ResolverVinculacionUseCase, CorregirVinculacionUseCase,
    ])
    def test_los_3_casos_de_uso_de_vinculacion_ahora_si_reciben_auditoria_repo(self, use_case_cls):
        firma = inspect.signature(use_case_cls.__init__)
        nombres = set(firma.parameters)
        pytest.fail(
            f"HALLAZGO (c) INVERTIDO: {use_case_cls.__name__}.__init__ SI declara un parametro "
            f"de auditoria (parametros reales: {sorted(nombres)!r}) -- la ronda anterior "
            f"(codigo stale) afirmo que ninguno lo tenia."
        ) if any('auditoria' in p.lower() for p in nombres) else None

    def test_evidencia_vinculacion_construye_un_evento_auditoria_iot_real_de_rf61(self):
        """Confirma que no es un logging generico: es el mismo mecanismo de
        RF-63 (EventoAuditoriaIot con hash_integridad), con
        ComponenteOrigen.RF61 dedicado."""
        archivo = REPO_ROOT / 'src/telemetry/application/use_cases/infraestructura/evidencia_vinculacion.py'
        texto = archivo.read_text(encoding='utf-8')
        pytest.fail(
            "HALLAZGO (c) INVERTIDO, MECANISMO CONFIRMADO: evidencia_vinculacion.py SI construye "
            "un EventoAuditoriaIot real con ComponenteOrigen.RF61 y hash_integridad via "
            "_calcular_hash() -- es el mismo mecanismo de auditoria que usa el resto de RF-63."
        ) if 'ComponenteOrigen.RF61' in texto and '_calcular_hash' in texto else None


class TestSubCasoDLogInjectionSinSumideroAlcanzable:
    @pytest.mark.parametrize('archivo_rel', [
        'src/telemetry/application/use_cases/infraestructura/resolver_vinculacion_use_case.py',
        'src/telemetry/application/use_cases/infraestructura/corregir_vinculacion_use_case.py',
    ])
    def test_motivo_nunca_se_pasa_a_logger(self, archivo_rel):
        texto = (REPO_ROOT / archivo_rel).read_text(encoding='utf-8')
        bloque_logger = texto.split('logger.warning(')[1] if 'logger.warning(' in texto else ''
        assert 'motivo' not in bloque_logger.split(')')[0]
