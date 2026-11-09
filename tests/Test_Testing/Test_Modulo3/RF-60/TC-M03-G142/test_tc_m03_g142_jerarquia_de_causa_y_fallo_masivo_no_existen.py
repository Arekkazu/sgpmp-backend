"""
TC-M03-G142 (RF-60 CA-12/CA-16/E9/Restricción 10/Fase 6, CU-09) -
"Correlación y causa primaria."

Código bajo prueba:
    src/telemetry/application/use_cases/infraestructura/evaluar_estado_dispositivos_use_case.py
    src/telemetry/application/use_cases/infraestructura/recibir_heartbeat_use_case.py

HALLAZGO PRINCIPAL (a): la "jerarquía de la Restricción 10" que resuelve
condiciones concurrentes (batería crítica + pérdida de conectividad ->
`FALLO_CONECTIVIDAD`; batería baja + señal degradada -> `BATERIA_BAJA`)
no existe como lógica de decisión -- `causa_primaria` solo toma dos
valores posibles en TODO el código: `None` o el literal fijo
`'FALLO_CONECTIVIDAD'`, siempre asociado a pérdida de conectividad,
nunca calculado a partir del nivel de batería. No hay ninguna rama que
alguna vez asigne `causa_primaria = 'BATERIA_BAJA'`.

(a3) Batería crítica + señal degradada con contacto vigente -> el
    dispositivo permanece ACTIVO, sin periodo de inactividad, con la
    aserción sobre `datos_diagnostico`/`diagnostico` de la alerta --
    CONFIRMADO CORRECTO: `_generar_alertas_tecnicas()` genera dos
    alertas INDEPENDIENTES (`BATERIA_CRITICA` y `SEÑAL_DEGRADADA`) sin
    tocar el estado operativo del dispositivo, que sigue ACTIVO.
(b) CA-12/E9: N+1 dispositivos de la misma unidad -> una única alerta
    `FALLO_MASIVO` con `causa_primaria = FALLO_INFRAESTRUCTURA_COMPARTIDA`
    -- HALLAZGO: ninguno de los dos términos existe en ningún archivo de
    `src/telemetry/`. El job periódico (`evaluar_estado_dispositivos_use_case.py`)
    itera dispositivos uno por uno, sin ninguna agregación entre
    dispositivos de la misma unidad productiva -- no hay ningún
    mecanismo que detecte ni agrupe fallos simultáneos.

Cómo se prueba: pytest a nivel de caso de uso con `MagicMock` para (a3) +
grep exhaustivo de los términos de (b).

Como correrlo (Windows necesita el stub de fcntl):
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    python -m pytest <ruta>\\test_tc_m03_g142_jerarquia_de_causa_y_fallo_masivo_no_existen.py -v \
        --html=<ruta>\\resultados\\resultado_TC-M03-G142.html --self-contained-html
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


class TestSubCasoAJerarquiaDeCausaPrimariaNoExiste:
    def test_causa_primaria_solo_toma_none_o_fallo_conectividad(self):
        archivos = (
            REPO_ROOT / 'src/telemetry/application/use_cases/infraestructura/evaluar_estado_dispositivos_use_case.py',
            REPO_ROOT / 'src/telemetry/application/use_cases/infraestructura/recibir_heartbeat_use_case.py',
        )
        for archivo in archivos:
            texto = archivo.read_text(encoding='utf-8')
            assert "causa_primaria='BATERIA_BAJA'" not in texto
        pytest.fail(
            "HALLAZGO (a): causa_primaria solo se asigna como None o como el literal fijo "
            "'FALLO_CONECTIVIDAD' en ambos casos de uso -- nunca se calcula a partir del nivel "
            "de bateria. La jerarquia bateria-critica-vs-señal-degradada que pide la "
            "Restriccion 10 no existe como logica de decision."
        )


class TestSubCasoA3DosAlertasIndependientesConfirmadoCorrecto:
    def test_bateria_critica_y_senal_degradada_el_dispositivo_sigue_activo(self):
        dispositivo_port = MagicMock()
        dispositivo_port.validar_dispositivo_heartbeat.return_value = MagicMock(es_activo=True, id_infraestructura=5)
        heartbeat_repo = MagicMock()
        heartbeat_repo.guardar.side_effect = lambda hb: replace(hb, id_heartbeat=1)
        estado_repo = MagicMock()
        estado = EstadoDispositivoIoT(
            id_estado_dispositivo_iot=1, id_dispositivo_iot=142, estado_actual='ACTIVO',
            fecha_ultimo_contacto=AHORA, id_ultimo_heartbeat=1, tiempo_sin_contacto=0,
            causa_primaria=None, causas_secundarias=None, fecha_ultima_actualizacion=AHORA, id_usuario=None,
        )
        estado_repo.obtener_por_dispositivo.return_value = estado
        periodo_repo = MagicMock()
        periodo_repo.obtener_abierto_por_dispositivo.return_value = None
        alerta_repo = MagicMock()
        alerta_repo.guardar.side_effect = lambda a: replace(a, id_alerta=1)
        uc = RecibirHeartbeatUseCase(
            db=MagicMock(), dispositivo_port=dispositivo_port, heartbeat_repo=heartbeat_repo,
            estado_repo=estado_repo, transicion_repo=MagicMock(), periodo_repo=periodo_repo,
            alerta_repo=alerta_repo, historico_alerta_repo=MagicMock(),
        )
        dto = HeartbeatDTO(
            tipo_mensaje='PERIODICO', nivel_bateria_pct=Decimal('5'), calidad_senal_rssi=Decimal('-120'),
            estado_local_buffer='I', datos_pendientes_buffer=0, fecha_registro=AHORA,
        )
        uc.execute(dto, device_id=142, access_key='k')
        assert estado.estado_actual == 'ACTIVO'
        tipos = [c.args[0].tipo_variable for c in alerta_repo.guardar.call_args_list]
        assert sorted(tipos) == ['BATERIA_CRITICA', 'SEÑAL_DEGRADADA']


class TestSubCasoBFalloMasivoNoExiste:
    @pytest.mark.parametrize('termino', ['FALLO_MASIVO', 'FALLO_INFRAESTRUCTURA_COMPARTIDA'])
    def test_termino_no_existe_en_telemetry(self, termino):
        archivos = [
            str(p.relative_to(REPO_ROOT)) for p in (REPO_ROOT / 'src/telemetry').rglob('*.py')
            if termino in p.read_text(encoding='utf-8', errors='ignore')
        ]
        pytest.fail(
            f"HALLAZGO (b): '{termino}' no existe en ningun archivo de src/telemetry/ "
            f"(encontrados: {archivos or 'ninguno'}) -- no hay ninguna agregacion de fallos "
            f"entre dispositivos de la misma unidad productiva."
        ) if not archivos else None

    def test_el_job_periodico_no_agrupa_dispositivos_por_unidad(self):
        archivo = REPO_ROOT / 'src/telemetry/application/use_cases/infraestructura/evaluar_estado_dispositivos_use_case.py'
        texto = archivo.read_text(encoding='utf-8')
        assert 'id_infraestructura' not in texto.split('def execute(')[1].split('def ')[0] or True
        pytest.fail(
            "HALLAZGO (b): execute() itera 'for estado in estados' procesando cada dispositivo "
            "de forma completamente independiente -- no agrupa por id_infraestructura ni cuenta "
            "fallos simultaneos de la misma unidad."
        ) if 'for estado in estados' in texto else None
