"""
TC-M03-G146 (RF-60 E2/Fase 1/Restricción 11/Salida 1, CU-03) - "Robustez
temporal del mensaje." Grupo NUEVO (sin TC previo) -- la propia ficha
advierte que abre "un hueco de enmascaramiento".

Código bajo prueba:
    src/telemetry/infrastructure/dto/heartbeat_dto.py (`fecha_registro`, sin validadores)
    src/telemetry/application/use_cases/infraestructura/recibir_heartbeat_use_case.py

HALLAZGO PRINCIPAL: `fecha_registro` del `HeartbeatDTO` se persiste tal
cual pero **no influye en ningún cálculo de la máquina de estados**, ni en
el sentido que la ficha teme ni en ningún otro. Esto conecta directamente
con el hallazgo ya confirmado en TC-M03-273 (replay): `fecha_ultimo_contacto`
en `recibir_heartbeat_use_case.py` siempre se fija con `ahora =
datetime.now(timezone.utc)` (reloj del SERVIDOR), nunca con
`dto.fecha_registro`. Y en el mismo heartbeat, `tiempo_sin_contacto_seg` que
alimenta `evaluar_transicion()` está HARDCODEADO a `0` (línea con comentario
explícito "heartbeat recibido -> tiempo=0 -> ACTIVO"), sin derivarse de
ninguna resta de timestamps en ese momento. Consecuencia para cada
sub-caso:

(a) timestamp futuro -> "se marca reloj_desincronizado=true y se genera
    DESINCRONIZACION_RELOJ" -- HALLAZGO: ninguno de los dos existe para
    heartbeats. `reloj_desincronizado` SÍ existe, pero es un campo de la
    entidad `Telemetria` (RF-53, otro módulo), no de `EstadoDispositivoIoT`
    ni de `Heartbeat` -- y ni siquiera ahí se calcula (persistido tal cual,
    nunca comparado contra el reloj del servidor en ningún `if`). El DTO sí
    trae `reloj_sincronizado` (nombre distinto, sin el "des-"), pero es un
    valor que el PROPIO dispositivo autorreporta -- el backend nunca lo
    calcula ni lo contrasta con su propio reloj. `DESINCRONIZACION_RELOJ`
    no existe en ningún archivo de `src/` (grep exhaustivo).
(b) "solo el desvío fuera de umbral dispara la alerta" -- HALLAZGO: no
    existe ningún umbral configurable de desvío de reloj en absoluto, ni la
    comparación que lo necesitaría.
(c) [RIESGO A VERIFICAR, resuelto]: la ficha teme que un timestamp
    adelantado 30 min produzca `tiempo_sin_contacto` NEGATIVO y mantenga
    ACTIVO a un nodo caído. **Esto no puede pasar, pero no porque el sistema
    lo prevenga -- porque `fecha_registro` nunca llega a usarse para ese
    cálculo**: el heartbeat vivo ignora el timestamp del mensaje por
    completo (usa el reloj del servidor); el riesgo real, ya confirmado en
    TC-M03-273, es el opuesto y más amplio -- CUALQUIER heartbeat (sea cual
    sea su `fecha_registro`, futuro, pasado o repetido) reinicia el contacto
    al momento de llegada. El timestamp del mensaje es, en la práctica,
    metadata decorativa para esta máquina de estados.
(d) formato no-ISO-8601 o sin zona horaria -> rechazo "per Fase 1" --
    HALLAZGO: `fecha_registro: datetime` no tiene ningún `field_validator`
    propio (el único `field_validator` importado en el archivo nunca se usa
    -- import muerto). La validación de formato depende enteramente del
    parser de Pydantic/`datetime`, que SÍ exige una representación
    parseable pero acepta un datetime *naive* (sin zona horaria) sin
    rechazarlo -- no hay ningún rechazo explícito "per Fase 1" en el
    dominio de este DTO.

Cómo se prueba: pytest, validando el DTO directamente y el caso de uso con
repos de prueba.

Como correrlo (Windows necesita el stub de fcntl):
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    python -m pytest <ruta>\\test_tc_m03_g146_robustez_temporal_del_mensaje.py -v \
        --html=<ruta>\\resultados\\resultado_TC-M03-G146.html --self-contained-html
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from src.telemetry.application.use_cases.infraestructura.recibir_heartbeat_use_case import (
    RecibirHeartbeatUseCase,
)
from src.telemetry.domain.entities.estado_dispositivo_iot import EstadoDispositivoIoT
from src.telemetry.infrastructure.dto.heartbeat_dto import HeartbeatDTO

REPO_ROOT = Path(__file__).resolve().parents[5]
AHORA = datetime(2026, 10, 20, 12, 0, 0, tzinfo=timezone.utc)


class TestSubCasoADesincronizacionRelojNoImplementada:
    def test_no_existe_desincronizacion_reloj_en_ningun_lado(self):
        archivos = [
            str(p.relative_to(REPO_ROOT)) for p in (REPO_ROOT / 'src').rglob('*.py')
            if 'DESINCRONIZACION_RELOJ' in p.read_text(encoding='utf-8', errors='ignore')
        ]
        pytest.fail(
            f"HALLAZGO (a): 'DESINCRONIZACION_RELOJ' no existe en src/ (encontrados: "
            f"{archivos or 'ninguno'}). No hay ninguna alerta de este tipo."
        ) if not archivos else None

    def test_reloj_desincronizado_es_de_telemetria_rf53_no_de_heartbeat_rf60(self):
        texto_heartbeat = (REPO_ROOT / 'src/telemetry/domain/entities/heartbeat.py').read_text(encoding='utf-8')
        assert 'reloj_desincronizado' not in texto_heartbeat, (
            'Si esto aparece, la entidad Heartbeat ya tiene este campo -- revisar si (a) cambio.'
        )
        pytest.fail(
            "HALLAZGO (a): 'reloj_desincronizado' existe SOLO en la entidad Telemetria (RF-53), "
            "nunca en Heartbeat ni en EstadoDispositivoIoT (RF-60) -- el mecanismo que pide esta "
            "ficha para heartbeats no tiene ningun lugar donde vivir en el modulo correcto."
        )

    def test_timestamp_futuro_se_procesa_sin_ninguna_senal_de_desincronizacion(self):
        """Confirma que el heartbeat SI se procesa (no rechaza por timestamp futuro),
        pero no deja ningun rastro de desincronizacion."""
        db = MagicMock()
        dispositivo_port = MagicMock()
        dispositivo_port.validar_dispositivo_heartbeat.return_value = MagicMock(es_activo=True, id_infraestructura=5)
        heartbeat_repo = MagicMock()
        heartbeat_capturado = {}

        def _guardar(hb):
            heartbeat_capturado.update(hb.__dict__ if hasattr(hb, '__dict__') else {})
            return replace(hb, id_heartbeat=1)

        heartbeat_repo.guardar.side_effect = _guardar
        estado_repo = MagicMock()
        estado_repo.obtener_por_dispositivo.return_value = EstadoDispositivoIoT(
            id_estado_dispositivo_iot=1, id_dispositivo_iot=146, estado_actual='ACTIVO',
            fecha_ultimo_contacto=AHORA, id_ultimo_heartbeat=1, tiempo_sin_contacto=0,
            causa_primaria=None, causas_secundarias=None, fecha_ultima_actualizacion=AHORA, id_usuario=None,
        )
        periodo_repo = MagicMock()
        periodo_repo.obtener_abierto_por_dispositivo.return_value = None
        uc = RecibirHeartbeatUseCase(
            db=db, dispositivo_port=dispositivo_port, heartbeat_repo=heartbeat_repo,
            estado_repo=estado_repo, transicion_repo=MagicMock(), periodo_repo=periodo_repo,
            alerta_repo=MagicMock(), historico_alerta_repo=MagicMock(),
        )
        timestamp_adelantado_30min = AHORA + timedelta(minutes=30)
        dto = HeartbeatDTO(
            tipo_mensaje='PERIODICO', nivel_bateria_pct=Decimal('80'),
            estado_local_buffer='I', datos_pendientes_buffer=0, fecha_registro=timestamp_adelantado_30min,
        )
        resultado = uc.execute(dto, device_id=146, access_key='k')
        assert resultado is not None, 'el heartbeat con timestamp adelantado 30 min SE PROCESA sin rechazo'


class TestSubCasoBSinUmbralDeDesvioConfigurable:
    def test_no_existe_ningun_umbral_de_desvio_de_reloj(self):
        archivos_rf60 = list((REPO_ROOT / 'src' / 'telemetry' / 'application' / 'use_cases' / 'infraestructura').glob('*.py'))
        coincidencias = [
            a.name for a in archivos_rf60
            if 'desvio' in a.read_text(encoding='utf-8', errors='ignore').lower()
            or 'umbral_reloj' in a.read_text(encoding='utf-8', errors='ignore').lower()
        ]
        pytest.fail(
            f"HALLAZGO (b): ningun archivo de infraestructura/ (RF-60) menciona un umbral de desvio "
            f"de reloj configurable (encontrados: {coincidencias or 'ninguno'})."
        ) if not coincidencias else None


class TestSubCasoCTimestampNoInfluyeEnElCalculoRealResuelto:
    """(c) [RIESGO A VERIFICAR -> resuelto]: no hay tiempo_sin_contacto negativo
    porque fecha_registro simplemente no se usa para ese calculo -- ni con
    heartbeats futuros, ni pasados, ni repetidos (conecta con TC-M03-273)."""

    def test_tiempo_sin_contacto_seg_esta_hardcodeado_a_cero_ignora_fecha_registro(self):
        archivo = REPO_ROOT / 'src/telemetry/application/use_cases/infraestructura/recibir_heartbeat_use_case.py'
        texto = archivo.read_text(encoding='utf-8')
        pytest.fail(
            "HALLAZGO (c) RESUELTO: 'tiempo_sin_contacto_seg=0' esta hardcodeado en la llamada a "
            "evaluar_transicion() dentro del camino de heartbeat -- nunca se calcula a partir de "
            "dto.fecha_registro. El riesgo real no es 'tiempo negativo por timestamp adelantado': "
            "es que el timestamp del mensaje no tiene NINGUNA influencia en el calculo, adelantado, "
            "atrasado o repetido (mismo mecanismo de fondo que el hallazgo de replay de TC-M03-273)."
        ) if 'tiempo_sin_contacto_seg=0' in texto else None


class TestSubCasoDFormatoYZonaHorariaSinValidacionPropia:
    def test_el_dto_no_tiene_ningun_validador_propio_para_fecha_registro(self):
        texto = (REPO_ROOT / 'src/telemetry/infrastructure/dto/heartbeat_dto.py').read_text(encoding='utf-8')
        # El import de field_validator existe pero no se usa como decorador en ningun campo.
        usos_decorador = texto.count('@field_validator')
        pytest.fail(
            f"HALLAZGO (d): HeartbeatDTO importa field_validator pero lo usa {usos_decorador} veces "
            f"(0 esperado) -- fecha_registro no tiene ninguna validacion propia de formato/zona "
            f"horaria; depende enteramente del parser por defecto de Pydantic/datetime, que acepta "
            f"un datetime 'naive' (sin tzinfo) sin rechazarlo."
        ) if usos_decorador == 0 else None

    def test_un_datetime_naive_sin_zona_horaria_es_aceptado_por_el_dto(self):
        """Confirma en vivo (a nivel de DTO) que un datetime sin tzinfo no se rechaza."""
        sin_tz = datetime(2026, 10, 20, 12, 0, 0)  # naive, sin timezone
        dto = HeartbeatDTO(
            tipo_mensaje='PERIODICO', nivel_bateria_pct=Decimal('80'),
            estado_local_buffer='I', datos_pendientes_buffer=0, fecha_registro=sin_tz,
        )
        assert dto.fecha_registro.tzinfo is None, (
            'HALLAZGO (d): un datetime sin zona horaria fue aceptado tal cual, sin rechazo ni '
            'normalizacion a UTC.'
        )
