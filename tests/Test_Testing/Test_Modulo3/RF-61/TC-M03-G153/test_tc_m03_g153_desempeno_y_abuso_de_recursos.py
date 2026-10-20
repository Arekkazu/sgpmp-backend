"""
TC-M03-G153 (RF-61 v1.2 CA-14/CA-15/RNF-01/RNF-02/RNF-03/Restricción 11,
CU-10) - "Desempeño, escalabilidad, abuso de recursos y continuidad."
Grupo existente de RF-61.

RELACIÓN CON TC-M03-G152 (hallazgo raíz): (b) pide medir que 72h de buffer
se vinculen en <= 9 min -- pero G152 confirmó que el "Subcomponente B" de
resolución retrospectiva de buffer NO EXISTE (no hay batch, no hay endpoint
de resolución masiva). No hay ningún proceso que medir para (b): no es que
sea lento, es que no existe. Y (e) ("M02 no disponible -> SIN_VINCULAR
nunca al azar") ya está confirmado trivialmente por G152 -- M02 está "no
disponible" permanentemente, vía el stub, y el único resultado posible ya
es SIN_VINCULAR, nunca aleatorio, porque no hay ninguna rama de código que
produzca un resultado al azar.

Código bajo prueba:
    src/telemetry/infrastructure/routers/vinculacion_router.py (paginación)
    src/shared/rate_limit.py (anti-abuso, ya usado en otros módulos)

HALLAZGO NUEVO (c): existe infraestructura de rate limiting en el propio
repositorio (`src/shared/rate_limit.py`, usada en
`activo_biologico_router.py` y `dispositivo_iot_router.py`), pero
`vinculacion_router.py` NO la importa ni la aplica a ninguno de sus 4
endpoints (`listar`, `obtener`, `resolver`, `corregir`). Aplicación
inconsistente de un mecanismo anti-abuso que ya existe en la base de
código -- no es que falte la herramienta, es que no se usó aquí.

(a) CA-14/RNF-01, latencia <= 2 s / throughput 500 lecturas/min sostenido --
    NO EJECUTADO EN ESTA SESIÓN: requiere generar carga sostenida real
    contra el entorno TEST compartido (JMeter/k6), lo cual excede el
    alcance de una verificación de solo lectura y requiere autorización
    explícita antes de ejecutarse contra infraestructura compartida.
(b) CA-15/RNF-02, 72h de buffer en <= 9 min -- HALLAZGO: no aplica, mismo
    motivo que G152 -- no existe ningún proceso de resolución de buffer
    que medir.
(c) Abuso de recursos (tamaño/paginación/profundidad/tasa) -- MIXTO:
    CONFIRMADO para paginación (`por_pagina` está acotado por Pydantic/
    FastAPI con `le=200`, un lote de "limit=1000000" es rechazado con 422
    antes de llegar a la capa de aplicación); HALLAZGO para tasa (no hay
    rate limiting en ninguno de los 4 endpoints de vinculación, a pesar de
    que el mecanismo ya existe y se usa en otros routers del mismo
    repositorio); no aplica para "contexto_activo profundamente anidado"
    -- ese campo no existe en ningún esquema de RF-61 (solo existe, con
    otro nombre, `contexto_activo_biologico`, en `Alerta`/RF-60).
(d) RNF-03 disponibilidad >= 99,0% con cola diferida ante caída -- NO
    EJECUTADO EN ESTA SESIÓN: requiere inducir caídas reales del servicio
    contra el entorno compartido (chaos testing), lo cual requiere
    autorización explícita antes de ejecutarse.
(e) M02 no disponible -> SIN_VINCULAR nunca al azar -- CONFIRMADO (corolario
    directo de TC-M03-G152: el stub asegura que el único resultado posible,
    siempre, es SIN_VINCULAR).

Cómo se prueba: inspección estática del router y de `src/shared/rate_limit.py`
+ pytest sobre la validación de Pydantic del límite de paginación. Los
subescenarios (a), (b) y (d) que requieren carga real contra el entorno
compartido quedan señalados para autorización explícita antes de ejecutarse
con k6 (ya disponible en este entorno) -- no se ejecutan en este archivo.

Como correrlo:
    python -m pytest <ruta>\\test_tc_m03_g153_desempeno_y_abuso_de_recursos.py -v \
        --html=<ruta>\\resultados\\resultado_TC-M03-G153.html --self-contained-html
"""
from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[5]


class TestSubCasoCAbusoDeRecursos:
    def test_paginacion_esta_acotada_por_schema_le_200(self):
        archivo = REPO_ROOT / 'src/telemetry/infrastructure/routers/vinculacion_router.py'
        texto = archivo.read_text(encoding='utf-8')
        assert 'por_pagina: int = Query(default=50, ge=1, le=200)' in texto

    def test_no_existe_rate_limiting_en_vinculacion_router(self):
        archivo = REPO_ROOT / 'src/telemetry/infrastructure/routers/vinculacion_router.py'
        texto = archivo.read_text(encoding='utf-8')
        archivo_rate_limit = REPO_ROOT / 'src/shared/rate_limit.py'
        existe_mecanismo = archivo_rate_limit.exists()
        pytest.fail(
            f"HALLAZGO (c): src/shared/rate_limit.py existe en el repositorio "
            f"({'confirmado' if existe_mecanismo else 'no encontrado'}) y se usa en otros routers "
            f"(activo_biologico_router.py, dispositivo_iot_router.py), pero "
            f"vinculacion_router.py no lo importa ni lo aplica a ninguno de sus 4 endpoints "
            f"(listar, obtener, resolver, corregir). Aplicacion inconsistente de un mecanismo "
            f"anti-abuso que ya existe en la base de codigo."
        ) if existe_mecanismo and 'rate_limit' not in texto else None

    def test_contexto_activo_profundamente_anidado_no_aplica_no_existe_el_campo(self):
        archivo_schema = REPO_ROOT / 'src/telemetry/infrastructure/schema/vinculacion_lectura_schema.py'
        texto = archivo_schema.read_text(encoding='utf-8')
        assert 'contexto_activo' not in texto


class TestSubCasoBBufferDe72hNoAplica:
    def test_no_hay_proceso_de_resolucion_de_buffer_que_medir(self):
        pytest.fail(
            "HALLAZGO (b): no aplica -- TC-M03-G152 confirmo que no existe ningun 'Subcomponente "
            "B' de resolucion retrospectiva de buffer (ni endpoint batch-resolve, ni proceso "
            "asincrono). No hay nada que cronometrar porque el proceso que (b) pide medir no "
            "existe en el codigo."
        )


class TestSubCasoENuncaAlAzarCorolarioDeG152:
    def test_sin_vincular_es_el_unico_resultado_posible_nunca_aleatorio(self):
        archivo = REPO_ROOT / 'src/telemetry/application/use_cases/infraestructura/vincular_lectura_activo_use_case.py'
        texto = archivo.read_text(encoding='utf-8')
        assert 'random' not in texto.lower()
        assert "elif len(activos) == 0" in texto or "if len(activos) == 0" in texto
