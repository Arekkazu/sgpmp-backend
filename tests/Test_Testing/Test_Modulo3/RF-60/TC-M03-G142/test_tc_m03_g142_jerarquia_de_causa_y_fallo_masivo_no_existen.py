"""
TC-M03-G142 (RF-60 CA-12/CA-16/E9/Restricción 10/Fase 6, CU-09) -
"Correlación y causa primaria."

REEJECUCIÓN 2026-10-29 TRAS MERGE DE `origin/test` -- ver
[[feedback_verify_against_live_before_local_code]]. El hallazgo (a) de la
ronda anterior queda PARCIALMENTE INVERTIDO: sí existe ahora una
jerarquía real de escalamiento, pero es una jerarquía de NIVELES de
batería (BATERIA_BAJA < BATERIA_CRITICA < APAGADO_INMINENTE), no la
jerarquía "batería-crítica-vs-conectividad" que pedía la Restricción 10.

HALLAZGO PRINCIPAL ACTUALIZADO (a): `RecibirHeartbeatUseCase.execute()`
(bloque final) SÍ implementa una jerarquía real con un diccionario
`orden_bateria = {'BATERIA_BAJA': 0, 'BATERIA_CRITICA': 1,
'APAGADO_INMINENTE': 2}`: si ya existe una alerta activa de un nivel
inferior y llega un heartbeat que amerita un nivel superior, llama a
`alerta_repo.escalar_bateria(...)` en vez de crear una alerta nueva. Esto
es jerarquía real de severidad -- pero sigue siendo puramente DENTRO del
dominio de batería, nunca cruzada con conectividad/señal. El campo
`causa_primaria` (de `EstadoDispositivoIoT`, usado por las transiciones
de estado RF-60) sigue tomando solo `None` o `'FALLO_CONECTIVIDAD'` en
todo el código -- CONFIRMADO VIGENTE, sin cambios: nunca se calcula a
partir del nivel de batería, porque batería y conectividad son dos
sistemas de alerta independientes (uno vive en `EstadoDispositivoIoT.
causa_primaria`, el otro en `Alerta.tipo_variable`), no una jerarquía
unificada como asume la Restricción 10.

(a3) Batería crítica + señal degradada con contacto vigente -> el
    dispositivo permanece ACTIVO, con dos alertas independientes --
    SIGUE CONFIRMADO CORRECTO: el bloque de batería/señal en
    `RecibirHeartbeatUseCase.execute()` nunca toca `estado.estado_actual`
    -- solo genera/escala alertas técnicas.
(b) CA-12/E9: N+1 dispositivos de la misma unidad -> una única alerta
    `FALLO_MASIVO` con `causa_primaria=FALLO_INFRAESTRUCTURA_COMPARTIDA`
    -- HALLAZGO VIGENTE, SIN CAMBIOS: ninguno de los dos términos existe
    en ningún archivo de `src/telemetry/` tras el merge. El job
    periódico sigue iterando dispositivos de forma independiente
    (`for candidato in candidatos`), sin ninguna agregación por
    infraestructura.

Cómo se prueba: inspección directa de la jerarquía real de escalamiento
de batería en `recibir_heartbeat_use_case.py`, confirmación de que
`causa_primaria` del estado del dispositivo sigue limitado a
None/FALLO_CONECTIVIDAD, y grep exhaustivo de los términos de (b).

Como correrlo (Windows necesita el stub de fcntl):
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    python -m pytest <ruta>\\test_tc_m03_g142_jerarquia_de_causa_y_fallo_masivo_no_existen.py -v \
        --html=<ruta>\\resultados\\resultado_TC-M03-G142.html --self-contained-html
"""
from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[5]
ARCHIVO_HB = REPO_ROOT / 'src/telemetry/application/use_cases/infraestructura/recibir_heartbeat_use_case.py'
ARCHIVO_EVAL = REPO_ROOT / 'src/telemetry/application/use_cases/infraestructura/evaluar_estado_dispositivos_use_case.py'


class TestSubCasoAJerarquiaDeBateriaSiExisteCausaPrimariaSigueLimitada:
    def test_si_existe_una_jerarquia_real_de_escalamiento_de_bateria(self):
        texto = ARCHIVO_HB.read_text(encoding='utf-8')
        pytest.fail(
            "HALLAZGO (a) ACTUALIZADO: SI existe una jerarquia real de escalamiento "
            "(orden_bateria = {BATERIA_BAJA:0, BATERIA_CRITICA:1, APAGADO_INMINENTE:2}) con "
            "alerta_repo.escalar_bateria() -- pero es una jerarquia interna al dominio de "
            "bateria, nunca cruzada con conectividad como pide la Restriccion 10."
        ) if 'orden_bateria' in texto and 'escalar_bateria' in texto else None

    def test_causa_primaria_del_estado_del_dispositivo_sigue_limitada_a_none_o_fallo_conectividad(self):
        for archivo in (ARCHIVO_HB, ARCHIVO_EVAL):
            texto = archivo.read_text(encoding='utf-8')
            assert "causa='BATERIA_BAJA'" not in texto and "causa_primaria='BATERIA_BAJA'" not in texto
        pytest.fail(
            "HALLAZGO (a) VIGENTE para EstadoDispositivoIoT.causa_primaria: sigue sin existir "
            "ninguna rama que la calcule a partir del nivel de bateria -- bateria y "
            "conectividad siguen siendo dos sistemas de alerta independientes, no una "
            "jerarquia unificada de causa primaria como asume la Restriccion 10."
        )


class TestSubCasoA3DosAlertasIndependientesConfirmadoCorrecto:
    def test_el_bloque_de_bateria_y_senal_nunca_toca_el_estado_operativo(self):
        texto = ARCHIVO_HB.read_text(encoding='utf-8')
        bloque = texto[texto.index('causas = []'):]
        assert 'estado.estado_actual =' not in bloque
        assert 'aplicar_transicion' not in bloque


class TestSubCasoBFalloMasivoSigueSinExistir:
    @pytest.mark.parametrize('termino', ['FALLO_MASIVO', 'FALLO_INFRAESTRUCTURA_COMPARTIDA'])
    def test_termino_no_existe_en_telemetry_tras_el_merge(self, termino):
        archivos = [
            str(p.relative_to(REPO_ROOT)) for p in (REPO_ROOT / 'src/telemetry').rglob('*.py')
            if termino in p.read_text(encoding='utf-8', errors='ignore')
        ]
        pytest.fail(
            f"HALLAZGO (b) VIGENTE: '{termino}' sigue sin existir en ningun archivo de "
            f"src/telemetry/ tras el merge (encontrados: {archivos or 'ninguno'})."
        ) if not archivos else None

    def test_el_job_periodico_sigue_sin_agrupar_dispositivos_por_infraestructura(self):
        texto = ARCHIVO_EVAL.read_text(encoding='utf-8')
        pytest.fail(
            "HALLAZGO (b) VIGENTE: execute() sigue iterando 'for candidato in candidatos' "
            "procesando cada dispositivo de forma completamente independiente -- no agrupa por "
            "id_infraestructura ni cuenta fallos simultaneos de la misma unidad."
        ) if 'for candidato in candidatos' in texto else None
