"""
TC-M03-G148 (RF-60 CA-14/RNF-07/Restricción 1, CU-12) - "Configuración en
caliente sin redespliegue." Grupo NUEVO (sin TC previo).

Código bajo prueba:
    src/configuration/application/use_cases/configuracion/actualizar_configuracion_use_case.py (RF-18)
    src/configuration/infrastructure/adapters/iot_stub_adapter.py
    src/configuration/domain/entities/configuracion_global.py

RELACIÓN CON TC-M03-274 (RF-18/RF-60, ya confirmado): "frecuencia_muestreo"/
"heartbeat" de `ConfiguracionGlobal` nunca se leen desde `src/telemetry` --
los umbrales reales de RF-60 son constantes fijas. Este TC confirma el
mismo hecho desde un ángulo distinto y más contundente: el PROPIO código de
RF-18 ya sabe que no hay integración, y lo dice en su propio comentario.

HALLAZGO PRINCIPAL (confirma y refuerza TC-274, con evidencia aún más
directa): `ActualizarConfiguracionUseCase.execute()` llama a
`self.iot_port.notificar_configuracion(...)` después de guardar el cambio
-- esto PARECE ser exactamente el mecanismo de "propagación en caliente"
que pide (a)/(c). Pero la única implementación real de `IotNotificacionPort`
es `IotStubAdapter`, cuyo propio docstring dice literalmente: **"Stub del
adaptador IoT — no hace nada hasta que el módulo de monitoreo esté
disponible."** `notificar_configuracion()` es un método vacío (`pass`). Es
decir: el código SABE que debería notificar a RF-60 y tiene el punto de
extensión preparado para hacerlo -- pero hoy ese punto no hace nada.

(a) CA-14 "el siguiente heartbeat se evalúa con los nuevos valores, sin
    reiniciar" -- HALLAZGO: no puede evaluarse con valores nuevos porque
    nunca se evalúa con NINGÚN valor de esta configuración (TC-274). El
    cambio se guarda en BD pero no llega a ningún lado de RF-60.
(b) RNF-07 "aplica a los 4 grupos de parámetros (intervalos de heartbeat,
    umbrales de tolerancia, umbrales de batería y señal, políticas de
    escalada)" -- HALLAZGO: `ConfiguracionGlobal` (la única entidad de
    configuración operativa de RF-18) solo tiene 2 campos,
    `frecuencia_muestreo` y `heartbeat` -- ni un solo campo para umbrales de
    tolerancia (esos son las constantes fijas de TC-M03-269), ni para
    batería/señal (las constantes `_UMBRAL_BATERIA_*`/`_UMBRAL_RSSI_*` de
    `recibir_heartbeat_use_case.py`, confirmado en TC-M03-G139/145), ni para
    políticas de escalada (no existe ningún concepto de "escalada" con
    plazo configurable en RF-60). Los "4 grupos" de RNF-07 son, en el mejor
    caso, 1: intervalos de heartbeat/muestreo -- y ese único grupo tampoco
    se propaga (ver (a)).
(c) "el dispositivo que queda fuera de umbral bajo la nueva configuración
    transiciona en el siguiente ciclo" -- HALLAZGO: no aplica, mismo motivo
    que (a) -- no hay "nueva configuración" que pueda sacar a un dispositivo
    de umbral, porque el umbral nunca cambia con RF-18.
(d) "el cambio de configuración queda registrado en RF-63 con usuario,
    timestamp, valor anterior y valor nuevo" -- PARCIALMENTE CONFIRMADO:
    SÍ se audita con exactamente esos datos (usuario, timestamps,
    snapshot anterior/nuevo) -- pero en `AuditoriaConfigRepository`
    (tabla de auditoría propia de configuración/M09), NO en la bitácora de
    RF-63 (`BitacoraAuditoriaIotRepository`, la que sí usa
    `aplicar_mantenimiento_dispositivo_use_case.py` para CA-7/CA-8 en
    TC-M03-G144). Los datos que pide (d) SÍ se guardan, pero no donde la
    ficha dice.

Cómo se prueba: pytest a nivel de caso de uso, con repos de prueba, más
inspección directa de `IotStubAdapter`.

Como correrlo (Windows necesita el stub de fcntl):
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    python -m pytest <ruta>\\test_tc_m03_g148_config_en_caliente_no_propaga.py -v \
        --html=<ruta>\\resultados\\resultado_TC-M03-G148.html --self-contained-html
"""
from __future__ import annotations

from dataclasses import fields
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.configuration.application.use_cases.configuracion.actualizar_configuracion_use_case import (
    ActualizarConfiguracionUseCase,
)
from src.configuration.domain.entities.configuracion_global import ConfiguracionGlobal
from src.configuration.domain.value_objects.frecuencia_muestreo import FrecuenciaMuestreo
from src.configuration.domain.value_objects.heartbeat import Heartbeat
from src.configuration.infrastructure.adapters.iot_stub_adapter import IotStubAdapter
from src.configuration.infrastructure.dto.actualizar_configuracion_dto import ActualizarConfiguracionDTO

REPO_ROOT = Path(__file__).resolve().parents[5]
AHORA = datetime(2026, 10, 20, 12, 0, 0, tzinfo=timezone.utc)


class TestSubCasoAyCNotificacionEsUnStubQueNoPropagaNada:
    """(a)/(c): el punto de extension para propagar en caliente existe,
    pero su unica implementacion real no hace nada."""

    def test_iot_stub_adapter_no_hace_nada(self):
        adapter = IotStubAdapter()
        resultado = adapter.notificar_configuracion(frecuencia_muestreo=10, heartbeat=5)
        assert resultado is None
        pytest.fail(
            "HALLAZGO (a)/(c): IotStubAdapter.notificar_configuracion() es un metodo vacio ('pass') "
            "-- su propio docstring de clase dice 'no hace nada hasta que el modulo de monitoreo "
            "este disponible'. El cambio de configuracion se guarda en BD pero no se propaga a "
            "RF-60 por ningun medio -- consistente con TC-M03-274 (frecuencia_muestreo/heartbeat "
            "nunca se leen desde src/telemetry)."
        )

    def test_actualizar_configuracion_llama_al_stub_sin_verificar_su_efecto(self):
        """Confirma que el use case SI invoca la notificacion (la intencion esta
        ahi), simplemente el adaptador real no hace nada util con ella."""
        config = ConfiguracionGlobal(
            id_configuracion_global=1, frecuencia_muestreo=FrecuenciaMuestreo(10), heartbeat=Heartbeat(5),
            es_activo=True, id_usuario=1, fecha_actualizacion=AHORA,
        )
        config_repo = MagicMock()
        config_repo.obtener_por_id.return_value = config
        config_repo.actualizar.side_effect = lambda c: c
        auditoria_repo = MagicMock()
        iot_port = MagicMock()
        uc = ActualizarConfiguracionUseCase(
            db=MagicMock(), config_repo=config_repo, auditoria_repo=auditoria_repo, iot_port=iot_port,
        )
        dto = ActualizarConfiguracionDTO(frecuencia_muestreo=20, heartbeat=25, fecha_actualizacion=AHORA)

        uc.execute(id_configuracion_global=1, dto=dto, usuario_actual=MagicMock(id_usuario=1))

        iot_port.notificar_configuracion.assert_called_once_with(frecuencia_muestreo=20, heartbeat=25)


class TestSubCasoBConfiguracionGlobalSoloTieneUnGrupoDeParametros:
    """(b) RNF-07: se esperan 4 grupos; ConfiguracionGlobal solo tiene 1."""

    def test_configuracion_global_solo_tiene_frecuencia_y_heartbeat(self):
        nombres_campos = {f.name for f in fields(ConfiguracionGlobal)}
        campos_de_umbrales_tolerancia = {c for c in nombres_campos if 'umbral' in c.lower() or 'tolerancia' in c.lower()}
        campos_de_bateria_senal = {c for c in nombres_campos if 'bateria' in c.lower() or 'senal' in c.lower() or 'rssi' in c.lower()}
        campos_de_escalada = {c for c in nombres_campos if 'escalad' in c.lower() or 'plazo' in c.lower()}

        pytest.fail(
            f"HALLAZGO (b): ConfiguracionGlobal declara {sorted(nombres_campos)!r} -- ningun campo "
            f"de umbrales de tolerancia ({campos_de_umbrales_tolerancia or 'ninguno'}), de "
            f"bateria/senal ({campos_de_bateria_senal or 'ninguno'}) ni de politicas de escalada "
            f"({campos_de_escalada or 'ninguno'}). RNF-07 pide 4 grupos de parametros; solo existe "
            f"1 (intervalos de heartbeat/muestreo), y ese tampoco se propaga (ver (a)/(c))."
        )


class TestSubCasoDAuditoriaEnTablaDistintaANoRF63:
    """(d): SI se audita con los datos correctos, pero en una tabla distinta
    a la bitacora de RF-63."""

    def test_el_cambio_se_audita_con_usuario_y_snapshots(self):
        config = ConfiguracionGlobal(
            id_configuracion_global=1, frecuencia_muestreo=FrecuenciaMuestreo(10), heartbeat=Heartbeat(5),
            es_activo=True, id_usuario=1, fecha_actualizacion=AHORA,
        )
        config_repo = MagicMock()
        config_repo.obtener_por_id.return_value = config
        config_repo.actualizar.side_effect = lambda c: c
        auditoria_repo = MagicMock()
        uc = ActualizarConfiguracionUseCase(
            db=MagicMock(), config_repo=config_repo, auditoria_repo=auditoria_repo, iot_port=MagicMock(),
        )
        dto = ActualizarConfiguracionDTO(frecuencia_muestreo=20, heartbeat=25, fecha_actualizacion=AHORA)

        uc.execute(id_configuracion_global=1, dto=dto, usuario_actual=MagicMock(id_usuario=7))

        auditoria_repo.registrar.assert_called_once()
        llamada = auditoria_repo.registrar.call_args.kwargs
        assert llamada['id_usuario'] == 7
        assert llamada['tipo_operacion'] == 'UPDATE'
        assert 'valores_anteriores' in llamada and 'valores_nuevos' in llamada

    def test_la_auditoria_de_config_es_una_tabla_distinta_a_la_bitacora_rf63(self):
        archivo_repo = REPO_ROOT / 'src/configuration/infrastructure/repositories/auditoria_config_repository.py'
        texto = archivo_repo.read_text(encoding='utf-8')
        pytest.fail(
            "HALLAZGO (d): el audit trail de cambios de configuracion vive en "
            "AuditoriaConfigRepository (modulo configuration), una tabla propia de M09/config -- "
            "NO en BitacoraAuditoriaIotRepository (RF-63, telemetry), que es la que usa "
            "aplicar_mantenimiento_dispositivo_use_case.py para CA-7/CA-8 (TC-M03-G144). Los datos "
            "que pide (d) si se guardan (usuario, timestamps, valores antes/despues), pero no en "
            "'RF-63' como dice la ficha -- un consumidor que consulte la bitacora de RF-63 esperando "
            "ver estos cambios de configuracion no los encontrara ahi."
        ) if 'BitacoraAuditoriaIot' not in texto else None
