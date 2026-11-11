"""
TC-M06-G80 (RF-93 Restricciones 3 y 6, CU-09/CU-10) - "Errores críticos en
los RF fuente y prohibición de modificación manual."

Construido 2026-11-07 contra el código real de RF-93. Primera ronda.

Código bajo prueba:
    src/financial_valuation/application/use_cases/reportes/generar_estado_resultados_use_case.py
    src/financial_valuation/application/use_cases/auditoria/consultar_auditoria_financiera_use_case.py
    alembic/baseline/esquema_baseline.sql (trigger tgr_m06_23_inmutabilidad_estado_resultados)

Ficha: "un error que impida recuperar una categoría bloquea la generación
con registro en RF-94 y alerta crítica, en las cuatro fuentes y en los tres
modos de fallo (timeout, 5xx, datos corruptos); y ningún componente del
estado puede alterarse manualmente por API, por inyección en el payload ni
en base de datos." Nota: "Distinguir el error crítico de la ausencia
legítima de registros... OWASP API3:2023 para la inyección de totales."

HALLAZGO PRINCIPAL (ausencia total, primera mitad): no existe NINGÚN manejo
diferenciado de errores por fuente/modo de fallo. `GenerarEstadoResultadosUseCase.
generar()` envuelve todo en un único bloque:
```python
try:
    resultado = self.constructor.guardar(...)
    self.auditoria.registrar(EventoAuditoria(tipo_evento="ESTADO_RESULTADOS_GENERADO", ...))
    self.db.commit()
except Exception:
    self.db.rollback()
    raise
```
Cualquier excepción (timeout de BD, error 500 interno, dato corrupto que
rompa un `Decimal(...)`, lo que sea) cae en el mismo `except Exception`
genérico: hace `rollback()` y re-lanza la excepción ORIGINAL sin envolverla,
sin registrar NINGÚN evento de auditoría (el `self.auditoria.registrar(...)`
de la línea anterior nunca llega a ejecutarse si el fallo es en
`constructor.guardar()`), y sin ninguna forma de identificar "cuál de las
4 fuentes" falló -- `self.calcular()` ejecuta una sola consulta SQL
combinada (`movimientos()` + `del_periodo()`), así que un error ahí es
monolítico, no atribuible a una fuente específica. No hay ninguna
distinción entre timeout/5xx/datos corruptos: Python no diferencia el tipo
de excepción más allá de `except Exception`.

HALLAZGO SEGUNDA MITAD (CONFIRMADO, no invertido): la prohibición de
modificación manual SÍ existe y es robusta -- un trigger real de BD,
`tgr_m06_23_inmutabilidad_estado_resultados` (BEFORE DELETE OR UPDATE ON
`modulo6.estados_resultados_periodo`), bloquea con una EXCEPCIÓN DE POSTGRES
cualquier intento de: (1) eliminar una fila ya creada; (2) modificar
cualquier columna de una fila en estado `GENERADO` o `APROBADO`, salvo la
transición exacta `GENERADO -> APROBADO` tocando solo `estado`,
`id_usuario_aprobador`, `fecha_aprobacion`. Esto cubre tanto la vía API
(no existe ningún endpoint de `PATCH`/`PUT` sobre un estado de resultados
en `m06_router.py` -- solo `POST .../aprobacion`) como una escritura directa
a BD (el trigger se dispara sin importar el origen de la escritura) --
la inyección de payload (OWASP API3:2023, mass assignment) tampoco aplica
porque no existe ningún endpoint que acepte un payload de "componentes" o
"resultado_neto" directamente: `FiltrosEstadoDTO` (el único body que acepta
el endpoint de generación) solo tiene 4 campos de filtro, ninguno de
contenido financiero.

(a)-(e) Error crítico en las 4 fuentes / timeout / 5xx / datos corruptos,
    con registro en RF-94 y alerta crítica -- HALLAZGO: nada de esto existe;
    ver arriba.
(f)-(h) Prohibición de modificación por API / inyección en payload / BD --
    CONFIRMADO CORRECTO en los tres frentes -- ver arriba.

Cómo se prueba: pytest directo sobre el manejo de excepciones de
`generar()` (simulando un fallo en `constructor.guardar()` con un mock que
lanza), inspección del router para confirmar la ausencia de
endpoints de modificación, e inspección de la migración/baseline para
confirmar el trigger de inmutabilidad.

Como correrlo (Windows necesita el stub de fcntl):
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    $env:SECRET_KEY = "test"
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    python -m pytest <ruta>\\test_tc_m06_g80_errores_criticos_y_prohibicion_modificacion.py -v \\
        --html=<ruta>\\resultados\\resultado_TC-M06-G80.html --self-contained-html
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.financial_valuation.application.use_cases.reportes.generar_estado_resultados_use_case import (
    GenerarEstadoResultadosUseCase,
)
from src.financial_valuation.domain.entities.contabilidad import Periodo

REPO_ROOT = Path(__file__).resolve().parents[5]
ROUTER = REPO_ROOT / 'src/financial_valuation/infrastructure/routers/m06_router.py'
BASELINE = REPO_ROOT / 'alembic/baseline/esquema_baseline.sql'
# El baseline tiene una version MAS VIEJA (pre-migracion) del cuerpo de la funcion: solo crea el
# trigger. La migracion posterior hace CREATE OR REPLACE FUNCTION sobre el MISMO nombre -- Postgres
# resuelve el cuerpo de una funcion PL/pgSQL en el momento de disparo, asi que el trigger ya
# adjunto en el baseline usa el cuerpo MAS RECIENTE (el de la migracion), no el original. Por eso el
# texto exacto del mensaje de excepcion se verifica contra la migracion, no contra el baseline.
MIGRACION = REPO_ROOT / 'alembic/versions/c4d81e6f2a95_m06_nic41_esquema_rfc018.py'


def _periodo():
    import datetime
    return Periodo(id_periodo_contable=93, numero_id_tributaria="900123456", tipo_cierre="MENSUAL",
                   fecha_inicio=datetime.date(2026, 10, 1), fecha_fin=datetime.date(2026, 10, 31), estado="CERRADO")


class TestSubCasoAEErrorCriticoNoSeDistinguePorFuenteNiSeAuditaHallazgo:
    def test_un_fallo_en_el_calculo_no_registra_ningun_evento_de_auditoria(self):
        periodos = MagicMock()
        periodos.obtener.return_value = _periodo()
        periodos.ultima_ejecucion.return_value = {}
        constructor = MagicMock()
        constructor.guardar.side_effect = RuntimeError("datos corruptos: Decimal inválido en costos")
        auditoria = MagicMock()
        db = MagicMock()
        uc = GenerarEstadoResultadosUseCase(db=db, periodos=periodos, reportes=MagicMock(), constructor=constructor,
                                            auditoria=auditoria)
        with pytest.raises(RuntimeError):
            uc.generar(id_periodo_contable=93, filtros={}, id_usuario=1)
        pytest.fail(
            "HALLAZGO CONFIRMADO: ante un fallo del calculo (simulando 'datos corruptos'), "
            "auditoria.registrar() NUNCA se invoca (count="
            f"{auditoria.registrar.call_count}) -- no hay ningun registro en RF-94 ni alerta "
            "critica; solo se hace rollback() y se relanza la excepcion original sin envolver."
        ) if auditoria.registrar.call_count == 0 else None

    def test_el_rollback_si_se_ejecuta_pero_sin_distincion_de_causa(self):
        periodos = MagicMock()
        periodos.obtener.return_value = _periodo()
        periodos.ultima_ejecucion.return_value = {}
        constructor = MagicMock()
        constructor.guardar.side_effect = TimeoutError("timeout simulado de una fuente")
        db = MagicMock()
        uc = GenerarEstadoResultadosUseCase(db=db, periodos=periodos, reportes=MagicMock(), constructor=constructor,
                                            auditoria=MagicMock())
        with pytest.raises(TimeoutError):
            uc.generar(id_periodo_contable=93, filtros={}, id_usuario=1)
        db.rollback.assert_called_once()

    def test_no_existe_ningun_mecanismo_para_identificar_cual_de_las_cuatro_fuentes_fallo(self):
        archivo = REPO_ROOT / 'src/financial_valuation/application/services/reportes.py'
        texto = archivo.read_text(encoding='utf-8')
        pytest.fail(
            "HALLAZGO: calcular() ejecuta una sola llamada a reportes.movimientos() y otra a "
            "costos.del_periodo() combinando TODAS las fuentes -- no existe ningun try/except "
            "por fuente individual (VARIACION_VR_TB, VARIACION_VR_PM, PRODUCTO_AGRICOLA, "
            "costos_mantenimiento) que permita identificar cual fallo especificamente."
        ) if texto.count('try:') == 0 else None


class TestSubCasoFGHProhibicionDeModificacionManualConfirmadaCorrecta:
    def test_no_existe_ningun_endpoint_de_modificacion_directa_del_estado(self):
        texto = ROUTER.read_text(encoding='utf-8')
        tiene_patch_o_put_sobre_estado = (
            '@router.patch("/estados-resultados' in texto or '@router.put("/estados-resultados' in texto
        )
        assert not tiene_patch_o_put_sobre_estado

    def test_el_unico_post_de_modificacion_es_aprobacion_sin_payload_de_contenido(self):
        texto = ROUTER.read_text(encoding='utf-8')
        assert '@router.post("/estados-resultados/{id_estado}/aprobacion"' in texto

    def test_el_trigger_real_de_inmutabilidad_existe_y_esta_atado_a_la_tabla(self):
        texto_baseline = BASELINE.read_text(encoding='utf-8', errors='ignore')
        texto_migracion = MIGRACION.read_text(encoding='utf-8', errors='ignore')
        assert 'CREATE TRIGGER tgr_m06_23_inmutabilidad_estado_resultados BEFORE DELETE OR UPDATE ON modulo6.estados_resultados_periodo' in texto_baseline
        assert "RAISE EXCEPTION '[TGR-M06-23]" in texto_migracion

    def test_el_trigger_bloquea_cualquier_delete_sin_excepcion(self):
        texto = MIGRACION.read_text(encoding='utf-8', errors='ignore')
        assert "IF TG_OP = 'DELETE' THEN" in texto
        assert "no puede eliminarse" in texto
