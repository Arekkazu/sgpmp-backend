"""
TC-M03-275 (RF-60 CA-10/Restricción 3/Postcondición 8/Fase 8, CU-14) -
Trazabilidad hacia el historial de lecturas.

HALLAZGO PRINCIPAL (invalida (a) tal como la ficha la plantea): no existe
NINGÚN endpoint que permita consultar el historial de periodos de
inactividad. `PeriodoInactividadRepository` (puerto de dominio,
`periodo_inactividad_repository.py`) solo declara 3 métodos: `abrir()`,
`obtener_abierto_por_dispositivo()`, `cerrar()` -- ninguno de lectura masiva
("listar"/"consultar"). Ningún router de `src/telemetry` expone una ruta GET
sobre periodos de inactividad (confirmado leyendo las rutas registradas en
`infraestructura_iot_router.py` y `monitoreo_router.py`). El único endpoint
llamado "historial" en el módulo (`GET /iot/monitoreo/historial`, RF-59) es
sobre LECTURAS de telemetría (sensor_id, tipo_variable, estado_dato...), no
sobre periodos de inactividad de dispositivo -- la ficha parece asumir que
ese endpoint de RF-59 también expone `device_id, timestamp_inicio,
timestamp_fin, duracion_minutos, estado_durante_periodo, causa_primaria,
causas_secundarias, buffer_activo_durante_periodo`, pero esos campos
pertenecen a `PeriodoInactividad` (RF-60), que ningún endpoint de RF-59
expone ni referencia. Los periodos SE ESCRIBEN (vía `abrir()`/`cerrar()`,
confirmado en `evaluar_estado_dispositivos_use_case.py` y
`recibir_heartbeat_use_case.py`) pero NUNCA se pueden leer de vuelta por API.

También hay una discrepancia menor de nombres de campo: la entidad real usa
`duracion_min` (no `duracion_minutos`) y `buffer_activo_durante` (no
`buffer_activo_durante_periodo`); no existe un campo `causas_secundarias`
separado en `PeriodoInactividad` (sí existe en `EstadoDispositivoIoT`/
`HistoricoTransicionDispositivo` como `causas_secundarias`/
`causa_secundaria`).

(b) SÍ se confirma como la ficha espera: ninguno de los dos casos de uso de
RF-60 (`recibir_heartbeat_use_case.py`, `evaluar_estado_dispositivos_use_case.py`)
importa ni usa ningún repositorio de telemetría/lecturas (RF-53) -- búsqueda
exhaustiva de imports, cero coincidencias. RF-60 nunca inserta, modifica ni
elimina registros de RF-53; el ciclo de inactividad se representa
enteramente por referencia externa (el periodo apunta a `id_dispositivo_iot`
y a un rango de fechas, nunca a una fila de telemetría). El "vacío" de datos
durante SIN_SEÑAL/INACTIVO simplemente no genera filas de telemetría -- RF-53
y RF-60 son independientes por diseño.

Dado que `POST /iot/heartbeat` está roto en TEST para cualquier llamada
(hallazgo de TC-M03-273) y no existe ningún endpoint para leer periodos, este
TC se prueba enteramente a nivel de caso de uso (Backend / pytest con reloj
simulado), reproduciendo el ciclo ACTIVO->SIN_SEÑAL->ACTIVO completo con
dobles de prueba y verificando los campos REALES que `abrir()`/`cerrar()`
reciben.

Cómo correrlo (desde la raíz del repo; stub de fcntl en Windows):
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    python -m pytest <ruta>\\test_tc_m03_275_trazabilidad_historial_lecturas.py -v \
        --html=<ruta>\\resultados\\resultado_TC-M03-275.html --self-contained-html
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.telemetry.application.use_cases.infraestructura.evaluar_estado_dispositivos_use_case import (
    EvaluarEstadoDispositivosUseCase,
)
from src.telemetry.application.use_cases.infraestructura.recibir_heartbeat_use_case import (
    RecibirHeartbeatUseCase,
)
from src.telemetry.domain.entities.estado_dispositivo_iot import EstadoDispositivoIoT, UMBRAL_INACTIVO_SEG
from src.telemetry.domain.entities.periodo_inactividad import PeriodoInactividad
from src.telemetry.domain.repositories.periodo_inactividad_repository import PeriodoInactividadRepository
from src.telemetry.infrastructure.dto.heartbeat_dto import HeartbeatDTO

REPO_ROOT = Path(__file__).resolve().parents[5]
T0 = datetime(2026, 9, 26, 12, 0, 0, tzinfo=timezone.utc)


def _congelar_reloj(modulo, ahora: datetime):
    import unittest.mock as mock

    class _DatetimeFijo(datetime):
        @classmethod
        def now(cls, tz=None):
            return ahora

    return mock.patch.object(modulo, 'datetime', _DatetimeFijo)


class TestGrupoANoExisteEndpointDeConsultaDePeriodos:

    def test_el_puerto_de_periodos_no_declara_ningun_metodo_de_lectura_masiva(self):
        metodos = [m for m in dir(PeriodoInactividadRepository) if not m.startswith('_')]
        pytest.fail(
            f"HALLAZGO (a): PeriodoInactividadRepository solo declara {sorted(metodos)} -- ningun "
            f"'listar'/'consultar'/'historial'. Los periodos se escriben pero nunca se pueden leer "
            f"de vuelta por ningun endpoint; la ficha asume que RF-59 los expone y no es asi."
        ) if not any('list' in m.lower() or 'consult' in m.lower() or 'historial' in m.lower() for m in metodos) else None

    def test_ningun_router_de_telemetry_expone_una_ruta_de_periodos_de_inactividad(self):
        archivos = (REPO_ROOT / 'src' / 'telemetry' / 'infrastructure' / 'routers').glob('*.py')
        rutas_con_periodo = []
        for archivo in archivos:
            for linea in archivo.read_text(encoding='utf-8').splitlines():
                if '"/' in linea and 'periodo' in linea.lower() and '@router' not in linea:
                    continue
            # busqueda simple de decoradores @router.get seguidos de una ruta que mencione 'periodo'
            texto = archivo.read_text(encoding='utf-8')
            import re
            for m in re.finditer(r'@router\.get\(\s*"([^"]*)"', texto):
                if 'periodo' in m.group(1).lower() or 'inactividad' in m.group(1).lower():
                    rutas_con_periodo.append(f'{archivo.name}:{m.group(1)}')
        assert rutas_con_periodo == [], f'se encontraron rutas de periodos: {rutas_con_periodo} (si aparece, la ficha podria estar corregida)'

    def test_los_nombres_de_campo_reales_difieren_de_los_que_pide_la_ficha(self):
        campos_reales = set(PeriodoInactividad.__dataclass_fields__.keys())
        campos_que_pide_la_ficha = {'duracion_minutos', 'buffer_activo_durante_periodo', 'causas_secundarias'}
        coinciden = campos_que_pide_la_ficha & campos_reales
        assert coinciden == set(), (
            f'se esperaba que NINGUNO de los nombres literales de la ficha coincidiera con la entidad real '
            f'(campos reales: {sorted(campos_reales)}); la entidad usa duracion_min, buffer_activo_durante, '
            f'y no tiene causas_secundarias propio.'
        )


class TestGrupoBCicloCompletoConCamposReales:
    """Reproduce ACTIVO -> SIN_SEÑAL -> ACTIVO con dobles de prueba y verifica que abrir()/cerrar()
    reciben los campos reales (no los que pide la ficha) con los valores correctos."""

    def test_el_ciclo_completo_abre_y_cierra_el_periodo_con_los_campos_reales(self):
        import src.telemetry.application.use_cases.infraestructura.evaluar_estado_dispositivos_use_case as mod_job
        import src.telemetry.application.use_cases.infraestructura.recibir_heartbeat_use_case as mod_hb

        estado = EstadoDispositivoIoT(
            id_estado_dispositivo_iot=1, id_dispositivo_iot=77, estado_actual='ACTIVO',
            fecha_ultimo_contacto=T0, id_ultimo_heartbeat=1, tiempo_sin_contacto=0,
            causa_primaria=None, causas_secundarias=None, fecha_ultima_actualizacion=T0, id_usuario=None,
        )
        estado_repo = MagicMock()
        estado_repo.listar_activos.return_value = [estado]
        periodo_repo = MagicMock()
        periodo_repo.obtener_abierto_por_dispositivo.return_value = None
        alerta_repo = MagicMock()
        alerta_repo.guardar.return_value = MagicMock(id_alerta=1)

        # 1. 10 minutos despues: el job lo mueve a SIN_SEÑAL y ABRE el periodo.
        job = EvaluarEstadoDispositivosUseCase(
            db=MagicMock(), estado_repo=estado_repo, transicion_repo=MagicMock(),
            periodo_repo=periodo_repo, alerta_repo=alerta_repo, historico_alerta_repo=MagicMock(),
        )
        with _congelar_reloj(mod_job, T0 + timedelta(minutes=10)):
            job.execute()

        periodo_abierto = periodo_repo.abrir.call_args.args[0]
        assert periodo_abierto.id_dispositivo_iot == 77
        assert periodo_abierto.fecha_inicio == T0 + timedelta(minutes=10)
        assert periodo_abierto.fecha_fin is None
        assert periodo_abierto.estado_durante_periodo == 'SIN_SEÑAL'
        assert periodo_abierto.causa_primaria == 'FALLO_CONECTIVIDAD'
        assert periodo_abierto.buffer_activo_durante is False
        assert not hasattr(periodo_abierto, 'causas_secundarias')

        # 2. El dispositivo vuelve con un heartbeat: el periodo abierto se CIERRA.
        periodo_repo.obtener_abierto_por_dispositivo.return_value = periodo_abierto
        estado_repo.obtener_por_dispositivo.return_value = estado
        dispositivo_port = MagicMock()
        dispositivo_port.validar_dispositivo_heartbeat.return_value = MagicMock(es_activo=True, id_infraestructura=5)
        heartbeat_repo = MagicMock()
        from dataclasses import replace
        heartbeat_repo.guardar.side_effect = lambda hb: replace(hb, id_heartbeat=2)
        hb_uc = RecibirHeartbeatUseCase(
            db=MagicMock(), dispositivo_port=dispositivo_port, heartbeat_repo=heartbeat_repo,
            estado_repo=estado_repo, transicion_repo=MagicMock(), periodo_repo=periodo_repo,
            alerta_repo=alerta_repo, historico_alerta_repo=MagicMock(),
        )
        fecha_vuelta = T0 + timedelta(minutes=18)
        with _congelar_reloj(mod_hb, fecha_vuelta):
            hb_uc.execute(HeartbeatDTO(tipo_mensaje='PERIODICO', fecha_registro=fecha_vuelta), device_id=77, access_key='k')

        assert estado.estado_actual == 'ACTIVO'
        periodo_repo.cerrar.assert_called_once()
        periodo_cerrado = periodo_repo.cerrar.call_args.args[0]
        assert periodo_cerrado.fecha_fin == fecha_vuelta
        assert periodo_cerrado.duracion_min == 8, 'duracion_min, no duracion_minutos como pide la ficha'


class TestGrupoBIndependenciaDeRF53:

    def test_rf60_no_importa_ningun_repositorio_de_telemetria(self):
        archivos = [
            REPO_ROOT / 'src/telemetry/application/use_cases/infraestructura/recibir_heartbeat_use_case.py',
            REPO_ROOT / 'src/telemetry/application/use_cases/infraestructura/evaluar_estado_dispositivos_use_case.py',
        ]
        hallazgos = []
        for archivo in archivos:
            for linea in archivo.read_text(encoding='utf-8').splitlines():
                if linea.strip().startswith(('import', 'from')) and ('telemetria' in linea.lower() or 'lectura' in linea.lower()):
                    hallazgos.append(f'{archivo.name}: {linea.strip()}')
        assert hallazgos == [], (
            f'se esperaba que RF-60 NUNCA importara un repositorio de telemetria/lecturas; '
            f'se encontro: {hallazgos}'
        )
