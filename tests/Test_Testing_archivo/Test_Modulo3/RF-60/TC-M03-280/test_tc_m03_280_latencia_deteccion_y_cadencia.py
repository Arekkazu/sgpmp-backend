"""
TC-M03-280 (RF-60 RNF-01/RNF-02/Restricción 7, CU-02) - Latencia de detección
y cadencia del ciclo.

NO EJECUTADO como prueba de carga real (20 fallos simulados con Grafana/APM,
60 ciclos con 50 dispositivos): esta sesión no tiene Grafana/APM ni un
simulador de nodos configurado, y `POST /iot/heartbeat` está roto en TEST
(TC-M03-273), lo que impide generar los 20 fallos reales que pide (a). Se
documenta en su lugar, a partir del código real, lo que SÍ se puede confirmar
sin esa infraestructura.

(a) HALLAZGO: la fórmula de la ficha (`≤ 2×frecuencia_muestreo + margen = 25
min`) depende de la configuración `frecuencia_muestreo`/`heartbeat` de RF-18,
que TC-M03-274 ya confirmó DESCONECTADA del algoritmo real de RF-60. La
latencia de detección REAL no depende de esa configuración en absoluto: es
`UMBRAL_ACTIVO_SEG` (5 min fijos, ver TC-M03-269) más, en el peor caso, el
intervalo entre corridas de la tarea periódica (hasta 60 s). Es decir, la
latencia real máxima observable es ~6 minutos, bastante MENOR que los 25
minutos que la ficha usa como cota -- pero por una razón distinta a la que
asume (no hay ningún cálculo de `2×FM+margen`, los 5 minutos son una
constante fija sin relación con ningún parámetro configurable). No se
reprodujo con apagones reales por la falta de infraestructura mencionada;
queda como una proyección a partir del código, no una medición.

(b) RNF-02, confirmado a partir de `main.py` (`_evaluar_dispositivos_
periodicamente`):
  - El patrón real es `while True: await asyncio.sleep(60); ...
    use_case.execute() ...` -- un bucle SECUENCIAL de un solo proceso: al no
    disparar la siguiente iteración hasta que `execute()` termine, NO puede
    haber dos corridas SUPERPUESTAS dentro de un mismo proceso. Confirmado.
  - Pero la duración del ciclo NO está acotada a 60 s en ningún punto: el
    código no mide `execute()` ni aborta si tarda más de 60 s. Con 50
    dispositivos reales y consultas de BD más lentas, el intervalo efectivo
    entre evaluaciones sería `60 s + tiempo de execute()`, sin que nada lo
    detecte ni lo reporte -- "duración de ciclo inferior a 60 s" es una
    expectativa, no una garantía del código.
  - HALLAZGO MÁS GRAVE: esta tarea se registra de forma INCONDICIONAL en el
    `lifespan` de FastAPI (`main.py`, línea ~533,
    `asyncio.create_task(_evaluar_dispositivos_periodicamente())`), sin
    ningún guard de "solo el worker 0" ni ningún lock/advisory-lock de
    Postgres. Si la app se despliega con más de un worker de uvicorn (un
    escenario común en producción, y uno que el propio repositorio se toma
    en serio en otra parte -- ver el candado basado en `fcntl` que el
    buffer de auditoría RF-52 de M02 usa explícitamente para "serializar
    workers de uvicorn"), CADA worker ejecutaría su propia copia de este
    bucle, evaluando y escribiendo las MISMAS transiciones N veces por
    minuto (N = número de workers) -- esto se SUMA al doble-registro que
    TC-M03-277/278 ya documentaron a nivel de triggers de BD, multiplicando
    el problema por el número de workers.

Cómo correrlo (desde la raíz del repo; stub de fcntl en Windows):
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    python -m pytest <ruta>\\test_tc_m03_280_latencia_deteccion_y_cadencia.py -v \
        --html=<ruta>\\resultados\\resultado_TC-M03-280.html --self-contained-html
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from src.telemetry.domain.entities.estado_dispositivo_iot import UMBRAL_ACTIVO_SEG

REPO_ROOT = Path(__file__).resolve().parents[5]
MAIN = REPO_ROOT / 'main.py'


class TestGrupoALatenciaDeDeteccionRealVsFormulaDeLaFicha:

    def test_la_latencia_real_depende_del_umbral_fijo_no_de_frecuencia_muestreo(self):
        latencia_peor_caso_seg = UMBRAL_ACTIVO_SEG + 60
        pytest.fail(
            f"HALLAZGO (a): la latencia maxima real de deteccion es UMBRAL_ACTIVO_SEG ({UMBRAL_ACTIVO_SEG}s) "
            f"+ hasta 60s de espera del ciclo = {latencia_peor_caso_seg}s (~{latencia_peor_caso_seg/60:.1f} min), "
            f"sin ninguna relacion con frecuencia_muestreo/margen de RF-18 (confirmado desconectado en "
            f"TC-M03-274). La formula '2xFM+margen=25min' de la ficha no es como el sistema calcula la "
            f"latencia real."
        )

    def test_no_se_ejecutaron_20_fallos_simulados_por_falta_de_infraestructura(self):
        pytest.skip(
            "(a) requiere 20 apagones reales medidos con Grafana/APM y un simulador de nodos; "
            "ademas POST /iot/heartbeat esta roto en TEST (TC-M03-273). No ejecutado en esta sesion."
        )


class TestGrupoBCadenciaDelCicloYRiesgoMultiWorker:

    def test_el_ciclo_es_secuencial_sin_solape_dentro_de_un_proceso(self):
        texto = MAIN.read_text(encoding='utf-8')
        inicio = texto.index('async def _evaluar_dispositivos_periodicamente')
        fin = texto.index('\n\n\n', inicio) if '\n\n\n' in texto[inicio:] else texto.index('async def _ejecutar_batch_ica_diario', inicio)
        cuerpo = texto[inicio:fin]
        assert 'while True' in cuerpo
        assert 'await asyncio.sleep(60)' in cuerpo
        assert 'await use_case.execute()' not in cuerpo and 'use_case.execute()' in cuerpo

    def test_la_duracion_del_ciclo_no_esta_medida_ni_acotada(self):
        texto = MAIN.read_text(encoding='utf-8')
        inicio = texto.index('async def _evaluar_dispositivos_periodicamente')
        fin = texto.index('async def _ejecutar_batch_ica_diario', inicio)
        cuerpo = texto[inicio:fin]
        assert not re.search(r'perf_counter|time\.time\(\)|timeout', cuerpo), (
            'se esperaba que el ciclo NO midiera su propia duracion ni tuviera timeout'
        )

    def test_la_tarea_periodica_se_registra_sin_guard_de_multiples_workers(self):
        texto = MAIN.read_text(encoding='utf-8')
        linea_registro = next(l for l in texto.splitlines() if '_evaluar_dispositivos_periodicamente()' in l and 'create_task' in l)
        contexto = texto[texto.index(linea_registro) - 300 : texto.index(linea_registro) + 50]
        pytest.fail(
            f"HALLAZGO (b) mas grave: '{linea_registro.strip()}' se registra sin ningun guard de "
            f"'solo un worker' ni advisory lock de Postgres (contexto: ...{contexto[-200:]}). Con N "
            f"workers de uvicorn, la evaluacion periodica correria N veces en paralelo, multiplicando "
            f"el doble-registro ya documentado en TC-M03-277/278."
        ) if not re.search(r'worker_id|WORKER_ID|pg_try_advisory_lock|only.*worker.*0', contexto, re.I) else None

    def test_el_buffer_de_auditoria_m02_si_usa_un_candado_para_el_mismo_problema(self):
        """Contraste: el propio repo SI conoce y resuelve este problema en otro lugar (RF-52 de M02),
        lo que confirma que la ausencia de proteccion en RF-60 no es por desconocimiento general del
        patron, sino una omision especifica de este modulo."""
        bitacora = REPO_ROOT / 'src/biological_assets/application/use_cases/_registrar_evento_bitacora.py'
        texto = bitacora.read_text(encoding='utf-8')
        assert 'flock' in texto or 'LOCK_EX' in texto
        assert 'workers de uvicorn' in texto or 'uvicorn' in texto.lower()
