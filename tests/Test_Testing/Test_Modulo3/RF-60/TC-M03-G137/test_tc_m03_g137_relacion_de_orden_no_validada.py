"""
TC-M03-G137 (RF-60 CA-19/Restricción 12/Precondición 3, CU-12) -
"Validación de la relación de orden entre parámetros temporales."

REEJECUCIÓN 2026-10-29 TRAS MERGE DE `origin/test` (811 commits reales,
autoría Leandro/DEV-27 2026-10-21) -- ver
[[feedback_verify_against_live_before_local_code]]. El HALLAZGO PRINCIPAL
de la ronda anterior ("no existe ninguna validación de relación de orden
entre HB/FM/margen") queda INVERTIDO por completo: el código real
AHORA SÍ implementa exactamente esa validación, solo que repartida entre
dos capas en vez de vivir en el DTO de `PATCH /configuracion/parametros/{id}`.

HALLAZGO PRINCIPAL ACTUALIZADO: `ActualizarConfiguracionUseCase.execute()`
llama a `validar_cadena_heartbeat(parametros_repo, frecuencia.valor,
heartbeat.valor)`, que a su vez llama a `validar_heartbeat_configurado()`
(`src/configuration/domain/entities/parametros_heartbeat.py`), que llama a
`validar_cadena()`:
    - `intervalo_heartbeat <= frecuencia_muestreo / 2` (HB <= FM/2, EXACTO
      a la Precondición 3 de la ficha).
    - `margen_tolerancia >= max(intervalo_heartbeat, frecuencia_muestreo / 2)`
      (EXACTO a la Restricción 12 de la ficha, mensaje de error cita
      textualmente "Restricción 12").
El campo `margen` no vive en `ActualizarConfiguracionDTO` (que solo tiene
`frecuencia_muestreo`/`heartbeat`) sino en un catálogo de parámetros
MLOps separado (`margen_tolerancia`, clave `MARGEN`, gestionado por
`SqlAlchemyParametrosMLOpsRepository`) -- pero SÍ se valida de forma
cruzada contra frecuencia/heartbeat en el momento de guardar.

(a) Rechazo con mensaje que identifique la restricción violada --
    HALLAZGO INVERTIDO: `validar_cadena()` SÍ rechaza con
    `ValidationError('CADENA_HEARTBEAT_INVALIDA', ...)`, con mensaje que
    cita textualmente "Restricción 12" o "Cadena canónica" según cuál
    regla se viole. No existe un campo `margen` en ESTE DTO -- vive en el
    catálogo MLOps -- pero la validación cruzada real sí ocurre.
(b) Previsualización de umbral_sin_senal/umbral_inactivo -- SIGUE NO
    EVALUABLE como endpoint dedicado, pero con HALLAZGO ACTUALIZADO: ya
    no es cierto que "RF-60 nunca derive sus umbrales de estos campos" --
    ver TC-M03-G132 (reejecutado 2026-10-29): `ParametrosComunicacionHeartbeat`
    SÍ calcula `umbral_activo=max(HB,FM)`, `umbral_sin_senal=umbral_activo+margen`,
    `umbral_inactivo=umbral_sin_senal+inactividad_extendida` dinámicamente
    por dispositivo.
(c) Parametrización por tipo de dispositivo y por variable -- HALLAZGO
    PARCIALMENTE INVERTIDO: SÍ existe parametrización por TIPO de
    dispositivo para el intervalo de heartbeat (`intervalos_heartbeat_por_tipo`,
    con una clave aparte `intervalo_heartbeat_camara` para cámaras) --
    pero sigue sin existir parametrización por "variable" individual ni
    por dispositivo específico (sigue siendo uno por categoría/tipo, no
    por id_dispositivo).
(d) FM=5 con HB=5 debe ser RECHAZADO (viola HB<=FM/2) -- HALLAZGO
    INVERTIDO: `validar_cadena()` SÍ rechaza esta combinación -- la regla
    `2*intervalo > frecuencia_seg` dispara `ServiceUnavailableError`
    envuelto como `ValidationError('CADENA_HEARTBEAT_INVALIDA', ...)`.

Cómo se prueba: inspección directa de
`src/configuration/application/use_cases/configuracion/validar_cadena_heartbeat.py`
y `src/configuration/domain/entities/parametros_heartbeat.py` (función
`validar_cadena`), más una llamada directa a `validar_cadena()` con los
valores límite exactos que la ficha pide verificar.

Como correrlo (Windows necesita el stub de fcntl):
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    $env:SECRET_KEY = "test"
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    python -m pytest <ruta>\\test_tc_m03_g137_relacion_de_orden_no_validada.py -v \
        --html=<ruta>\\resultados\\resultado_TC-M03-G137.html --self-contained-html
"""
from __future__ import annotations

import inspect
from decimal import Decimal
from pathlib import Path

import pytest

from src.configuration.application.use_cases.configuracion.actualizar_configuracion_use_case import (
    ActualizarConfiguracionUseCase,
)
from src.configuration.domain.entities.parametros_heartbeat import _invalido, validar_cadena
from src.configuration.infrastructure.dto.actualizar_configuracion_dto import ActualizarConfiguracionDTO
from src.shared.errors import ServiceUnavailableError

REPO_ROOT = Path(__file__).resolve().parents[5]


class TestSubCasoAyDLaValidacionCruzadaSiExisteAhora:
    def test_el_use_case_si_llama_a_validar_cadena_heartbeat(self):
        archivo = REPO_ROOT / 'src/configuration/application/use_cases/configuracion/actualizar_configuracion_use_case.py'
        texto = archivo.read_text(encoding='utf-8')
        pytest.fail(
            "HALLAZGO INVERTIDO: execute() SI invoca 'validar_cadena_heartbeat(...)' antes de "
            "guardar -- la ronda anterior (codigo stale pre-merge) afirmo que no habia ninguna "
            "validacion cruzada; ahora si la hay, solo que vive fuera de este DTO."
        ) if 'validar_cadena_heartbeat(' in texto else None

    @pytest.mark.parametrize('frecuencia_seg,intervalo_seg,margen_seg,debe_rechazar', [
        (600, 300, 300, False),   # HB=300<=FM/2=300 (limite exacto, inclusive) y margen=300>=max(300,300)
        (600, 301, 300, True),    # HB=301 > FM/2=300 -> viola Precondicion 3
        (600, 300, 299, True),    # margen=299 < max(300,300)=300 -> viola Restriccion 12
    ])
    def test_validar_cadena_aplica_precondicion_3_y_restriccion_12_en_los_limites_exactos(
        self, frecuencia_seg, intervalo_seg, margen_seg, debe_rechazar,
    ):
        if debe_rechazar:
            with pytest.raises(ServiceUnavailableError):
                validar_cadena([intervalo_seg], frecuencia_seg, frecuencia_seg + margen_seg, Decimal(margen_seg))
        else:
            validar_cadena([intervalo_seg], frecuencia_seg, frecuencia_seg + margen_seg, Decimal(margen_seg))

    def test_fm5_hb5_se_rechaza_porque_viola_hb_menor_o_igual_fm_medios(self):
        with pytest.raises(ServiceUnavailableError):
            validar_cadena([5], 5, 100, Decimal(10))


class TestSubCasoCParametrizacionPorTipoSiExisteParaIntervaloHeartbeat:
    def test_existe_clave_de_intervalos_por_tipo_de_dispositivo(self):
        archivo = REPO_ROOT / 'src/configuration/domain/entities/parametros_heartbeat.py'
        texto = archivo.read_text(encoding='utf-8')
        pytest.fail(
            "HALLAZGO PARCIALMENTE INVERTIDO: SI existe 'intervalos_heartbeat_por_tipo' "
            "(parametrizacion por categoria de dispositivo) y una clave aparte para camaras -- "
            "pero sigue sin existir parametrizacion por id_dispositivo individual ni por "
            "'variable' en el sentido que pedia la ficha original."
        ) if "INTERVALOS_TIPO = 'intervalos_heartbeat_por_tipo'" in texto else None

    def test_execute_sigue_sin_recibir_id_dispositivo_individual(self):
        firma = inspect.signature(ActualizarConfiguracionUseCase.execute)
        parametros = set(firma.parameters)
        assert 'id_dispositivo' not in parametros


class TestSubCasoBPrevisualizacionNoExisteComoEndpointPeroElCalculoSiEsDinamico:
    def test_no_existe_ningun_endpoint_de_previsualizacion_de_umbral(self):
        archivos = [
            str(p.relative_to(REPO_ROOT)) for p in (REPO_ROOT / 'src').rglob('*.py')
            if 'previsualizacion' in p.read_text(encoding='utf-8', errors='ignore').lower()
        ]
        pytest.fail(
            f"HALLAZGO (b) VIGENTE: no existe ningun endpoint de 'previsualizacion' de umbral "
            f"(encontrados: {archivos or 'ninguno'}) -- sigue sin ser evaluable como feature "
            f"independiente, aunque el calculo subyacente (ver TC-M03-G132) SI es dinamico."
        ) if not archivos else None
