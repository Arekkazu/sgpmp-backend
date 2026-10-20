"""
TC-M03-G145 (RF-60 CA-4/CA-5/CA-11/E3/E4/E7/E8/Fase 3, CU-05) - "Alertas de
salud del nodo sin cambio de estado operativo." Grupo NUEVO (sin TC previo).

Código bajo prueba:
    src/telemetry/application/use_cases/infraestructura/recibir_heartbeat_use_case.py
        `_generar_alertas_tecnicas()` -- único lugar que genera alertas técnicas.

HALLAZGO PRINCIPAL: de las 6 condiciones que pide la ficha (CA-4 batería
crítica, CA-4/E4 apagado inminente, batería baja/warning, CA-5/E3 sensor
físico fallido, CA-11 RSSI/SNR degradado, E8 sobrecalentamiento, E7 firmware
desactualizado), el código real SOLO implementa 2: batería (crítica/baja,
sin el escalón de 5% de E4 -- ver TC-M03-G139) y RSSI (sin SNR). Búsqueda
exhaustiva en todo `src/telemetry/`: CERO resultados para
`SENSOR_FISICO_FALLIDO`, `SOBRECALENTAMIENTO`, `FIRMWARE_DESACTUALIZADO`,
`sensores_operativos`, `temperatura_dispositivo` -- ninguno de los 3 flujos
(E3/E7/E8) existe en absoluto. Tampoco existe ninguna condición sobre
`calidad_senal_snr` (SNR): el campo se persiste en cada heartbeat
(`heartbeat.py`) pero nunca se evalúa -- mismo patrón write-only que
`datos_pendientes_buffer` (TC-M03-270) y `version_firmware` (TC-M03-273).

(a) CA-4/E4: batería crítica -- CONFIRMADO para el umbral <=10 (ya cubierto
    en TC-M03-G139 para el ángulo APAGADO_INMINENTE; aquí se confirma la
    frontera exacta del umbral_critico en sí, -1/=/+1).
(b) Batería warning -- CONFIRMADO: <=30 y >10 -> BATERIA_BAJA (MODERADO);
    >30 -> sin alerta de batería.
(c) CA-5/E3 sensor físico fallido -- HALLAZGO: no existe.
(d) CA-11 RSSI/SNR -- PARCIALMENTE confirmado: RSSI sí (<-100 ->
    SEÑAL_DEGRADADA); SNR HALLAZGO NUEVO: se persiste pero nunca se evalúa.
(e) E8 sobrecalentamiento -- HALLAZGO: no existe.
(f) E7 firmware desactualizado -- HALLAZGO: no existe (ya anticipado por
    TC-M03-273(d), aquí se confirma desde el ángulo de "alerta", no de
    "evasión de versión falsificada").

Cómo se prueba: pytest a nivel de caso de uso, con heartbeats sintéticos
barriendo cada umbral -- mismo patrón que TC-M03-269/G139.

Como correrlo (Windows necesita el stub de fcntl):
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    python -m pytest <ruta>\\test_tc_m03_g145_alertas_de_salud_del_nodo.py -v \
        --html=<ruta>\\resultados\\resultado_TC-M03-G145.html --self-contained-html
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.telemetry.application.use_cases.infraestructura.recibir_heartbeat_use_case import (
    RecibirHeartbeatUseCase,
)
from src.telemetry.domain.entities.estado_dispositivo_iot import EstadoDispositivoIoT
from src.telemetry.infrastructure.dto.heartbeat_dto import HeartbeatDTO

REPO_ROOT = Path(__file__).resolve().parents[5]
AHORA = datetime(2026, 10, 20, 12, 0, 0, tzinfo=timezone.utc)


def _use_case():
    db = MagicMock()
    dispositivo_port = MagicMock()
    dispositivo_port.validar_dispositivo_heartbeat.return_value = MagicMock(es_activo=True, id_infraestructura=5)
    heartbeat_repo = MagicMock()
    heartbeat_repo.guardar.side_effect = lambda hb: replace(hb, id_heartbeat=1)
    estado_repo = MagicMock()
    estado_repo.obtener_por_dispositivo.return_value = EstadoDispositivoIoT(
        id_estado_dispositivo_iot=1, id_dispositivo_iot=145, estado_actual='ACTIVO',
        fecha_ultimo_contacto=AHORA, id_ultimo_heartbeat=1, tiempo_sin_contacto=0,
        causa_primaria=None, causas_secundarias=None, fecha_ultima_actualizacion=AHORA, id_usuario=None,
    )
    periodo_repo = MagicMock()
    periodo_repo.obtener_abierto_por_dispositivo.return_value = None
    alerta_repo = MagicMock()
    alerta_repo.guardar.side_effect = lambda a: replace(a, id_alerta=1)
    uc = RecibirHeartbeatUseCase(
        db=db, dispositivo_port=dispositivo_port, heartbeat_repo=heartbeat_repo,
        estado_repo=estado_repo, transicion_repo=MagicMock(), periodo_repo=periodo_repo,
        alerta_repo=alerta_repo, historico_alerta_repo=MagicMock(),
    )
    return uc, alerta_repo


def _tipos_generados(alerta_repo) -> list[str]:
    return [c.args[0].tipo_variable for c in alerta_repo.guardar.call_args_list]


def _dto(bateria=80, rssi=None, snr=None, temperatura=None, firmware=None, sensores_operativos=None):
    kwargs = dict(
        tipo_mensaje='PERIODICO', nivel_bateria_pct=Decimal(str(bateria)),
        estado_local_buffer='I', datos_pendientes_buffer=0, fecha_registro=AHORA,
    )
    if rssi is not None:
        kwargs['calidad_senal_rssi'] = Decimal(str(rssi))
    if snr is not None:
        kwargs['calidad_senal_snr'] = Decimal(str(snr))
    if firmware is not None:
        kwargs['version_firmware'] = firmware
    return HeartbeatDTO(**kwargs)


class TestSubCasoABateriaCriticaFrontera:
    """(a) CA-4/E4: frontera exacta del umbral critico (10)."""

    @pytest.mark.parametrize('bateria, esperado', [(11, None), (10, 'BATERIA_CRITICA'), (9, 'BATERIA_CRITICA')])
    def test_frontera_umbral_critico(self, bateria, esperado):
        uc, alerta_repo = _use_case()
        uc.execute(_dto(bateria=bateria), device_id=145, access_key='k')
        tipos = _tipos_generados(alerta_repo)
        if esperado is None:
            assert 'BATERIA_CRITICA' not in tipos
        else:
            assert tipos == [esperado]


class TestSubCasoBBateriaWarning:
    """(b): rango warning -> BATERIA_BAJA; por encima -> sin alerta."""

    @pytest.mark.parametrize('bateria, esperado', [
        (31, []), (30, ['BATERIA_BAJA']), (11, ['BATERIA_BAJA']), (10, ['BATERIA_CRITICA']),
    ])
    def test_rango_warning_vs_sin_alerta(self, bateria, esperado):
        uc, alerta_repo = _use_case()
        uc.execute(_dto(bateria=bateria), device_id=145, access_key='k')
        assert _tipos_generados(alerta_repo) == esperado


class TestSubCasoCSensorFisicoFallidoNoImplementado:
    def test_no_existe_sensor_fisico_fallido_en_ningun_lado(self):
        archivos = [
            str(p.relative_to(REPO_ROOT)) for p in (REPO_ROOT / 'src').rglob('*.py')
            if 'SENSOR_FISICO_FALLIDO' in p.read_text(encoding='utf-8', errors='ignore')
        ]
        pytest.fail(
            f"HALLAZGO (c): 'SENSOR_FISICO_FALLIDO' no existe en src/ (encontrados: "
            f"{archivos or 'ninguno'}). No hay ninguna evaluacion de sensores_operativos en el "
            f"heartbeat -- E3/CA-5 no esta implementado."
        ) if not archivos else None


class TestSubCasoDRssiSiSnrNo:
    """(d) CA-11: RSSI funciona, SNR es write-only (hallazgo nuevo)."""

    def test_rssi_degradado_genera_senal_degradada(self):
        uc, alerta_repo = _use_case()
        uc.execute(_dto(rssi=-101), device_id=145, access_key='k')
        assert 'SEÑAL_DEGRADADA' in _tipos_generados(alerta_repo)

    def test_snr_extremo_no_genera_ninguna_alerta_hallazgo_nuevo(self):
        uc, alerta_repo = _use_case()
        uc.execute(_dto(snr=-50), device_id=145, access_key='k')  # SNR muy malo, cualquier escala razonable
        pytest.fail(
            f"HALLAZGO (d): calidad_senal_snr=-50 (pesimo en cualquier escala razonable de SNR) no "
            f"genero ninguna alerta ({_tipos_generados(alerta_repo)!r} generadas) -- el campo se "
            f"persiste en cada heartbeat pero _generar_alertas_tecnicas() solo evalua "
            f"calidad_senal_rssi, nunca calidad_senal_snr. Mismo patron write-only que "
            f"datos_pendientes_buffer (TC-M03-270) y version_firmware (TC-M03-273)."
        ) if _tipos_generados(alerta_repo) == [] else None


class TestSubCasoESobrecalentamientoNoImplementado:
    def test_no_existe_sobrecalentamiento_en_ningun_lado(self):
        archivos = [
            str(p.relative_to(REPO_ROOT)) for p in (REPO_ROOT / 'src').rglob('*.py')
            if 'SOBRECALENTAMIENTO' in p.read_text(encoding='utf-8', errors='ignore')
        ]
        pytest.fail(
            f"HALLAZGO (e): 'SOBRECALENTAMIENTO' no existe en src/ (encontrados: {archivos or 'ninguno'}). "
            f"No hay ningun campo temperatura_dispositivo en HeartbeatDTO ni evaluacion asociada -- "
            f"E8 no esta implementado."
        ) if not archivos else None


class TestSubCasoFFirmwareDesactualizadoNoImplementado:
    def test_no_existe_firmware_desactualizado_en_ningun_lado(self):
        archivos = [
            str(p.relative_to(REPO_ROOT)) for p in (REPO_ROOT / 'src').rglob('*.py')
            if 'FIRMWARE_DESACTUALIZADO' in p.read_text(encoding='utf-8', errors='ignore')
        ]
        pytest.fail(
            f"HALLAZGO (f): 'FIRMWARE_DESACTUALIZADO' no existe en src/ (encontrados: "
            f"{archivos or 'ninguno'}). version_firmware se persiste (confirmado tambien en "
            f"TC-M03-273(d)) pero no hay ninguna 'version minima configurada' contra la cual "
            f"compararlo -- E7 no esta implementado."
        ) if not archivos else None

    def test_firmware_antiguo_no_genera_ninguna_alerta(self):
        uc, alerta_repo = _use_case()
        uc.execute(_dto(firmware='0.0.1'), device_id=145, access_key='k')
        assert _tipos_generados(alerta_repo) == []


class TestControlReglaTransversalNingunaAlertaTecnicaCambiaElEstado:
    """Confirma la regla transversal que la ficha pide verificar: ninguna de
    estas condiciones de salud altera el estado OPERATIVO del dispositivo."""

    def test_bateria_critica_y_senal_degradada_el_dispositivo_sigue_activo(self):
        uc, alerta_repo = _use_case()
        estado = uc.estado_repo.obtener_por_dispositivo.return_value
        uc.execute(_dto(bateria=5, rssi=-120), device_id=145, access_key='k')
        assert estado.estado_actual == 'ACTIVO'
        assert sorted(_tipos_generados(alerta_repo)) == ['BATERIA_CRITICA', 'SEÑAL_DEGRADADA']
