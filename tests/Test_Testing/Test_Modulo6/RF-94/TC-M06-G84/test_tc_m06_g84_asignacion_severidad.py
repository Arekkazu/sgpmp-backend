"""
TC-M06-G84 (RF-94 Fase 3, CU-02) - "Asignación automática de severidad_evento."

Construido 2026-11-07 contra el código real de RF-94. Primera ronda.

Código bajo prueba:
    src/financial_valuation/domain/value_objects/nic41.py (Severidad enum)
    Todo src/financial_valuation/application/**/*.py que llama a
        AuditoriaFinancieraRepository.registrar(...)/construye EventoAuditoria
        (grep exhaustivo de ``severidad=``, 30+ sitios de llamada reales)
    src/financial_valuation/infrastructure/routers/m06_router.py (Severidad = Literal[...])

HALLAZGO PRINCIPAL (no existe ninguna "regla automática" central -- la
severidad es una decisión manual, ad hoc, de cada caso de uso): no hay
ninguna función ni tabla que mapee `tipo_evento -> severidad`
automáticamente. Cada caso de uso de M06 escribe su propio literal
`severidad="INFO"`/`Severidad.WARNING.value`/etc. en el punto donde
construye el `EventoAuditoria`. Verificado contra el catálogo real
(`DESCRIPCIONES` en `consultar_auditoria_financiera_use_case.py`, 40+ tipos
de evento), la correspondencia real NO coincide con la de la ficha:

- "CRITICAL para cierre con error" -- CONFIRMA: `CIERRE_PERIODO_FALLIDO` =
  `Severidad.CRITICAL.value` (`ejecutar_cierre_periodo_use_case.py:364`).
- "CRITICAL para exportación fallida" -- HALLAZGO: no existe ningún tipo de
  evento de "exportación fallida" en todo el catálogo de M06; la exportación
  de informes (`exportar_reporte_use_case.py`) no registra ningún
  `EventoAuditoria` en absoluto (ni éxito ni fallo).
- "CRITICAL para activo sin mercado" -- HALLAZGO: el evento real más
  cercano, `RECONOCIMIENTO_BLOQUEADO_SIN_VALOR` (activo sin precio NI
  costo, bloqueado), es `Severidad.WARNING`, no `CRITICAL`
  (`confirmar_reconocimiento_use_case.py:124`).
- "WARNING para precio vencido" -- HALLAZGO: `COTIZACION_VENCIDA` (el
  evento de vencimiento real existente) es `severidad="INFO"`
  (`modificar_cotizacion_use_case.py:79`), no `WARNING`.
- "WARNING para precio inactivado manualmente" -- HALLAZGO: no existe
  ningún tipo de evento de "precio inactivado manualmente"; el catálogo solo
  tiene `PRECIO_MARCADO_REEMPLAZADO` (severidad INFO) y
  `ACTIVO_MARCADO_SIN_MERCADO` (sin ningún `registrar()` real encontrado
  para este tipo en los casos de uso inspeccionados -- es una ETIQUETA de
  `DESCRIPCIONES` sin emisor confirmado).
- "WARNING para cadena verificada con resultado INCOMPLETA" -- CONFIRMA:
  `verificar_trazabilidad_use_case.py:58` asigna `Severidad.WARNING` cuando
  `estado != 'VERIFICADO'`.
- "ERROR cuando el emisor marca resultado_operacion = FALLIDO" -- HALLAZGO
  GRAVE: el campo `resultado_operacion` NO EXISTE en ninguna parte del
  esquema de M06 (ni en `EventoAuditoria`, ni en la tabla
  `auditorias_financieras`, ni en ningún caso de uso de
  `financial_valuation`). Es exclusivamente un campo del módulo de
  predicción (M04/RF-72, `resultado_operacion="EXITOSO"/"FALLIDO"` en
  `prediction/application/use_cases/...`) -- un concepto de otro módulo que
  la ficha confunde con RF-94. Más aún: la severidad `ERROR` del enum
  `Severidad` NUNCA se usa en ningún `registrar()` real de todo
  `financial_valuation` (grep exhaustivo de `Severidad.ERROR`/
  `severidad="ERROR"`: cero resultados en el módulo); el único uso real de
  `severidad="ERROR"` en todo el backend está en `accounting_integration`
  (M07), un módulo distinto.
- "INFO para el resto del catálogo" -- demasiado amplio para confirmar
  exhaustivamente, pero FALSO como regla por defecto estricta: existen
  tipos `WARNING` fuera de los dos casos que la ficha enumera (p. ej.
  `RECONOCIMIENTO_REVERTIDO`, `REVERSION_BLOQUEADA`, `DETERIORO_REGISTRADO`,
  `METODO_VALORACION_CAMBIADO`, `LINEA_ASIENTO_PENDIENTE_CUENTA`,
  `MEDICION_PENDIENTE` -- todos `WARNING`, no `INFO`).

(TC-94-016, cruce ERROR/CRITICAL/WARNING): la ficha reconoce que la regla de
ERROR "cruza sin precedencia definida" -- la realidad es más simple y más
grave: no hay cruce porque no hay regla de ERROR en absoluto dentro de M06.

Cómo se prueba: pytest de unidad por inspección exhaustiva (grep) de todos
los sitios reales de asignación de severidad en `financial_valuation`, más
el enum real, sin requerir BD viva.

Como correrlo (Windows necesita el stub de fcntl):
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    $env:SECRET_KEY = "test"
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    python -m pytest <ruta>\\test_tc_m06_g84_asignacion_severidad.py -v \\
        --html=<ruta>\\resultados\\resultado_TC-M06-G84.html --self-contained-html
"""
from __future__ import annotations

from pathlib import Path

import pytest

from src.financial_valuation.domain.value_objects.nic41 import Severidad

REPO_ROOT = Path(__file__).resolve().parents[5]
FINANCIAL_VALUATION_DIR = REPO_ROOT / 'src/financial_valuation'


def _grep(patron: str) -> list[str]:
    coincidencias = []
    for p in FINANCIAL_VALUATION_DIR.rglob('*.py'):
        texto = p.read_text(encoding='utf-8', errors='ignore')
        if patron in texto:
            coincidencias.append(str(p.relative_to(REPO_ROOT)))
    return coincidencias


class TestSubCasoNoExisteNingunaReglaCentralDeAsignacionDeSeveridad:
    def test_no_existe_ninguna_funcion_de_mapeo_tipo_evento_a_severidad(self):
        archivos_catalogo = [p for p in FINANCIAL_VALUATION_DIR.rglob('*.py')
                             if 'nic41.py' in p.name or 'consultar_auditoria_financiera' in p.name]
        hay_mapeo_automatico = any(
            'MAPEO_SEVERIDAD' in p.read_text(encoding='utf-8', errors='ignore')
            or 'SEVERIDAD_POR_TIPO' in p.read_text(encoding='utf-8', errors='ignore')
            for p in archivos_catalogo
        )
        pytest.fail(
            "HALLAZGO: no existe ninguna tabla/funcion de mapeo automatico tipo_evento->severidad "
            "-- cada caso de uso de M06 decide su propia severidad manualmente, en el punto exacto "
            "donde construye el EventoAuditoria. No hay 'asignacion automatica' centralizada."
        ) if not hay_mapeo_automatico else None


class TestSubCasoCriticalParaCierreConErrorConfirmadoCorrecto:
    def test_cierre_periodo_fallido_si_es_critical(self):
        archivos = _grep('CIERRE_PERIODO_FALLIDO')
        texto = next(p for p in FINANCIAL_VALUATION_DIR.rglob('ejecutar_cierre_periodo_use_case.py')).read_text(encoding='utf-8')
        assert 'tipo_evento="CIERRE_PERIODO_FALLIDO", severidad=Severidad.CRITICAL.value' in texto


class TestSubCasoCriticalParaExportacionFallidaYActivoSinMercadoHallazgo:
    def test_no_existe_ningun_tipo_de_evento_de_exportacion_fallida(self):
        archivos = _grep('EXPORTACION_FALLIDA')
        pytest.fail(
            "HALLAZGO: no existe ningun tipo_evento 'EXPORTACION_FALLIDA' (ni similar) en todo "
            "financial_valuation -- exportar_reporte_use_case.py no registra ningun EventoAuditoria, "
            "ni en exito ni en fallo. El escenario de la ficha es irreproducible."
        ) if not archivos else None

    def test_reconocimiento_bloqueado_sin_valor_es_warning_no_critical(self):
        texto = next(FINANCIAL_VALUATION_DIR.rglob('confirmar_reconocimiento_use_case.py')).read_text(encoding='utf-8')
        pytest.fail(
            "HALLAZGO: RECONOCIMIENTO_BLOQUEADO_SIN_VALOR (el evento mas cercano a 'activo sin "
            "mercado') tiene severidad=Severidad.WARNING.value, no CRITICAL como pide la ficha."
        ) if 'tipo_evento="RECONOCIMIENTO_BLOQUEADO_SIN_VALOR", severidad=Severidad.WARNING.value' in texto else None


class TestSubCasoWarningParaPrecioVencidoYPrecioInactivadoHallazgo:
    def test_cotizacion_vencida_es_info_no_warning(self):
        texto = next(FINANCIAL_VALUATION_DIR.rglob('modificar_cotizacion_use_case.py')).read_text(encoding='utf-8')
        pytest.fail(
            "HALLAZGO: COTIZACION_VENCIDA (el evento real de vencimiento de precio/cotizacion) "
            "tiene severidad=\"INFO\", no WARNING como pide la ficha."
        ) if 'tipo_evento="COTIZACION_VENCIDA", severidad="INFO"' in texto else None

    def test_no_existe_ningun_tipo_de_evento_de_precio_inactivado_manualmente(self):
        archivos = _grep('PRECIO_INACTIVADO')
        pytest.fail(
            "HALLAZGO: no existe ningun tipo_evento 'PRECIO_INACTIVADO' en todo financial_valuation "
            "-- el escenario de 'precio inactivado manualmente' de la ficha no tiene ningun evento "
            "de auditoria real que lo represente."
        ) if not archivos else None


class TestSubCasoWarningParaCadenaIncompletaConfirmadoCorrecto:
    def test_verificar_trazabilidad_asigna_warning_si_no_esta_verificado(self):
        texto = next(FINANCIAL_VALUATION_DIR.rglob('verificar_trazabilidad_use_case.py')).read_text(encoding='utf-8')
        assert 'severidad=(Severidad.INFO if estado == "VERIFICADO" else Severidad.WARNING).value' in texto


class TestSubCasoErrorPorResultadoOperacionFalsidoNoExisteEnM06HallazgoGrave:
    def test_resultado_operacion_no_existe_en_ningun_lugar_de_m06(self):
        archivos = _grep('resultado_operacion')
        pytest.fail(
            f"HALLAZGO GRAVE: 'resultado_operacion' no aparece en ningun archivo de "
            f"financial_valuation (coincidencias: {archivos!r}) -- es un campo exclusivo del "
            f"modulo de prediccion (M04/RF-72), no de RF-94/M06. La ficha confunde un concepto de "
            f"otro modulo con el de RF-94."
        ) if not archivos else None

    def test_severidad_error_nunca_se_usa_en_ningun_registrar_real_de_m06(self):
        archivos = _grep('Severidad.ERROR') + _grep('severidad="ERROR"') + _grep("severidad='ERROR'")
        pytest.fail(
            f"HALLAZGO GRAVE: Severidad.ERROR (o su literal) nunca se usa en ningun registrar() "
            f"real de financial_valuation (coincidencias: {archivos!r}) -- la severidad ERROR del "
            f"enum existe pero esta MUERTA dentro de M06; la regla 'ERROR cuando resultado_operacion"
            f"=FALLIDO' no tiene ninguna implementacion real que probar."
        ) if not archivos else None

    def test_severidad_error_si_existe_en_el_enum(self):
        assert Severidad.ERROR.value == 'ERROR'


class TestSubCasoInfoPorDefectoEsFalsoComoReglaEstrictaHallazgo:
    def test_existen_multiples_tipos_warning_fuera_de_los_dos_casos_de_la_ficha(self):
        tipos_warning_adicionales = [
            'RECONOCIMIENTO_REVERTIDO', 'REVERSION_BLOQUEADA', 'DETERIORO_REGISTRADO',
            'METODO_VALORACION_CAMBIADO', 'LINEA_ASIENTO_PENDIENTE_CUENTA', 'MEDICION_PENDIENTE',
        ]
        encontrados = [t for t in tipos_warning_adicionales if _grep(t)]
        pytest.fail(
            f"HALLAZGO: existen al menos {len(encontrados)} tipos de evento con severidad WARNING "
            f"fuera de los 2 que la ficha reconoce como excepcion ({encontrados!r}) -- 'INFO para "
            f"el resto del catalogo' no es una regla real, es una generalizacion incorrecta."
        ) if len(encontrados) >= 3 else None
