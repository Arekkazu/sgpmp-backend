"""
TC-M03-G139 (RF-60 CA-13/E4/Fase 6/Salida 2, CU-11) - "Enrutamiento,
contrato y volumen de alertas." Consolida CP-ALE-08/09/10, misma agrupación
que TC-M03-276 (ya ejecutado: (a) RBAC confirmado en vivo vía colección
hermana; (b) payload real no coincide campo a campo con la ficha; (c)
anti-duplicado confirmado).

RELACIÓN CON TC-M03-276 (NO duplicar): (a), (b), (c) ya están confirmados
ahí. Este archivo cubre SOLO (d) [CORREGIDO]: el catálogo real debería tener
13 tipos de alerta (los 12 de la Salida 2 + `APAGADO_INMINENTE`, que solo
aparece en E4: batería <= 5%, destinatario ADMINISTRADOR).

HALLAZGO: `APAGADO_INMINENTE` no es solo un error de catálogo/documentación
-- NO EXISTE EN EL CÓDIGO en absoluto. `_generar_alertas_tecnicas()`
(`recibir_heartbeat_use_case.py`) solo evalúa batería contra 2 umbrales
(`_UMBRAL_BATERIA_CRITICA=10`, `_UMBRAL_BATERIA_BAJA=30`), generando como
máximo `BATERIA_CRITICA` o `BATERIA_BAJA` -- no hay ningún tercer umbral ni
condición para `<=5%`, ni ninguna alerta adicional dirigida
específicamente al rol ADMINISTRADOR (las alertas técnicas actuales no
tienen ningún campo de "destinatario", el enrutamiento por rol se resuelve
aparte, ver TC-M03-276(a)/(b)). Un dispositivo con batería al 3% recibe
exactamente la misma alerta `BATERIA_CRITICA` que uno al 9% -- ninguna señal
adicional distingue "crítico" de "a punto de apagarse".

Cómo se prueba: pytest a nivel de caso de uso, con heartbeats sintéticos
barriendo el umbral de 5% -- mismo patrón que TC-M03-269 para fronteras.

Como correrlo (Windows necesita el stub de fcntl):
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    python -m pytest <ruta>\\test_tc_m03_g139_apagado_inminente_no_implementado.py -v \
        --html=<ruta>\\resultados\\resultado_TC-M03-G139.html --self-contained-html
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
AHORA = datetime(2026, 10, 19, 12, 0, 0, tzinfo=timezone.utc)


def _estado() -> EstadoDispositivoIoT:
    return EstadoDispositivoIoT(
        id_estado_dispositivo_iot=1, id_dispositivo_iot=139, estado_actual='ACTIVO',
        fecha_ultimo_contacto=AHORA, id_ultimo_heartbeat=1, tiempo_sin_contacto=0,
        causa_primaria=None, causas_secundarias=None, fecha_ultima_actualizacion=AHORA, id_usuario=None,
    )


def _heartbeat_con_bateria(pct) -> HeartbeatDTO:
    return HeartbeatDTO(
        tipo_mensaje='PERIODICO', nivel_bateria_pct=Decimal(str(pct)),
        estado_local_buffer='I', datos_pendientes_buffer=0, fecha_registro=AHORA,
    )


def _use_case():
    db = MagicMock()
    dispositivo_port = MagicMock()
    dispositivo_port.validar_dispositivo_heartbeat.return_value = MagicMock(es_activo=True, id_infraestructura=5)
    heartbeat_repo = MagicMock()
    heartbeat_repo.guardar.side_effect = lambda hb: replace(hb, id_heartbeat=1)
    estado_repo = MagicMock()
    estado_repo.obtener_por_dispositivo.return_value = _estado()
    transicion_repo = MagicMock()
    periodo_repo = MagicMock()
    periodo_repo.obtener_abierto_por_dispositivo.return_value = None
    alerta_repo = MagicMock()
    alerta_repo.guardar.side_effect = lambda a: replace(a, id_alerta=1) if hasattr(a, '__dataclass_fields__') else a
    historico_alerta_repo = MagicMock()
    uc = RecibirHeartbeatUseCase(
        db=db, dispositivo_port=dispositivo_port, heartbeat_repo=heartbeat_repo,
        estado_repo=estado_repo, transicion_repo=transicion_repo, periodo_repo=periodo_repo,
        alerta_repo=alerta_repo, historico_alerta_repo=historico_alerta_repo,
    )
    return uc, alerta_repo


class TestSubCasoDApagadoInminenteNoImplementado:
    """(d) [CORREGIDO]: bateria <= 5% deberia generar APAGADO_INMINENTE ademas de
    BATERIA_CRITICA. HALLAZGO: no existe ninguna condicion para esto."""

    def test_no_existe_apagado_inminente_en_ningun_archivo(self):
        archivos_con_alerta = [
            str(p.relative_to(REPO_ROOT)) for p in (REPO_ROOT / 'src').rglob('*.py')
            if 'APAGADO_INMINENTE' in p.read_text(encoding='utf-8', errors='ignore')
        ]
        pytest.fail(
            f"HALLAZGO (d): 'APAGADO_INMINENTE' no existe en ningun archivo de src/ (encontrados: "
            f"{archivos_con_alerta or 'ninguno'}). No es solo un error de catalogo en la Salida 2 -- "
            f"el codigo no tiene ninguna condicion de umbral de 5% ni genera esta alerta."
        ) if not archivos_con_alerta else None

    @pytest.mark.parametrize('bateria_pct', [5, 3, 1, 0])
    def test_bateria_5_porciento_o_menos_solo_genera_bateria_critica_no_apagado_inminente(self, bateria_pct):
        uc, alerta_repo = _use_case()
        uc.execute(_heartbeat_con_bateria(bateria_pct), device_id=139, access_key='k')

        tipos_generados = [c.args[0].tipo_variable for c in alerta_repo.guardar.call_args_list]
        assert tipos_generados == ['BATERIA_CRITICA'], (
            f'con bateria={bateria_pct}%, se esperaba SOLO BATERIA_CRITICA (lo que el codigo real '
            f'genera); se obtuvo {tipos_generados!r}. Si APAGADO_INMINENTE aparece aqui, (d) ya '
            f'estaria implementado.'
        )

    def test_bateria_critica_al_9_y_al_3_porciento_generan_la_misma_alerta_sin_distincion(self):
        """Control: demuestra que no hay ninguna gradacion dentro de BATERIA_CRITICA --
        9% (critico pero no inminente) y 3% (inminente) producen exactamente la misma alerta."""
        uc1, alerta_repo_9 = _use_case()
        uc1.execute(_heartbeat_con_bateria(9), device_id=139, access_key='k')
        uc2, alerta_repo_3 = _use_case()
        uc2.execute(_heartbeat_con_bateria(3), device_id=139, access_key='k')

        alerta_9 = alerta_repo_9.guardar.call_args.args[0]
        alerta_3 = alerta_repo_3.guardar.call_args.args[0]
        assert alerta_9.tipo_variable == alerta_3.tipo_variable == 'BATERIA_CRITICA'
        assert alerta_9.severidad == alerta_3.severidad, (
            f'HALLAZGO (d): bateria al 9% y al 3% generan la MISMA alerta '
            f'({alerta_9.tipo_variable!r}, severidad {alerta_9.severidad!r}) -- no hay ninguna '
            f'senal adicional que distinga "critico" de "a punto de apagarse" (lo que '
            f'APAGADO_INMINENTE deberia aportar).'
        )
