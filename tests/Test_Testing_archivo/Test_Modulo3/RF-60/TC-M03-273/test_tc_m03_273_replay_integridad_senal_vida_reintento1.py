"""
TC-M03-273 (RF-60 E7/RNF-05/Restricción 11, CU-19) - Integridad de la señal de
vida: replay y confianza en el transporte IoT.

HALLAZGO PREVIO, bloquea la ejecución EN VIVO de este TC tal como la ficha la
plantea ("capturar un heartbeat válido... y reenviarlo"): `POST /iot/heartbeat`
está roto en TEST para CUALQUIER llamada, nueva o existente, sin importar el
`tipo_mensaje` -- confirmado en vivo 2026-10-04 con 2 dispositivos distintos
(uno recién creado, otro reutilizado) y 4 valores de `tipo_mensaje`: siempre
`400 VALOR_FUERA_DE_RANGO` ("El valor excede el tamaño o formato permitido por
la base de datos"), que `db_error_translator.py` mapea desde cualquier
`sqlalchemy.exc.DataError` -- compatible con un cast implícito roto hacia una
columna ENUM nativa de Postgres (`estados_dispositivos_iot.estado_actual` u
otra) al insertar desde SQLAlchemy sin tipo explícito. No se pudo diagnosticar
la columna exacta sin acceso a logs/BD. **Es un hallazgo aparte, independiente
de este TC, pero relevante: actualmente NINGÚN heartbeat real llega a
procesarse en TEST**, lo que de hecho también "anula la detección de
inactividad sin dejar rastro" (coincide con la nota BLOQUEANTE de la ficha,
aunque por una causa distinta -- un bug de infraestructura, no la ausencia de
anti-replay).

Por eso este TC se prueba al nivel de caso de uso (Backend / pytest, con un
reloj simulado -- consistente con TC-M03-269/270), igual que ya hizo falta
para rodear ese bug en TC-M03-269/270.

(a) HALLAZGO CONFIRMADO (BLOQUEANTE, tal como anticipa la ficha): no existe
NINGÚN mecanismo anti-replay en `recibir_heartbeat_use_case.py` ni en
`heartbeat.py`/`heartbeat_model.py` -- sin nonce, sin contador de trama, sin
ventana firmada (búsqueda exhaustiva en `src/telemetry`: cero resultados para
nonce/contador_trama/replay). Más grave: `fecha_ultimo_contacto` se actualiza
SIEMPRE con `ahora = datetime.now(timezone.utc)` (el reloj del SERVIDOR en el
momento de la llamada), nunca con `dto.fecha_registro` (el timestamp que
declara el propio mensaje). Esto significa que reenviar un heartbeat
CAPTURADO, sin modificar un solo byte, 30 minutos después de que el nodo
realmente se apagó, actualiza el contacto a "ahora" igual que un heartbeat
genuino -- el dispositivo nunca transiciona a SIN_SEÑAL mientras alguien
siga reenviando el mismo mensaje capturado. La ficha pide exactamente lo
contrario ("descarte... sin actualizar timestamp_ultimo_contacto, de modo que
el dispositivo transicione a SIN_SEÑAL"); el código hace lo opuesto.

(b) CONFIRMADO: cero código LoRaWAN en el repositorio (mismo hallazgo ya
documentado para M09 y TC-M03-269/270) -- "join con claves no aprovisionadas"
no es una condición que este backend pueda evaluar, no existe un join server.

(c) CONFIRMADO: no existe ningún registro ni validación de gateways. El único
rastro de "gateway" en todo `src/` es el header opcional `X-Gateway-Id`
(`telemetria_router.py`/`evento_edge_router.py`, RF-53/RF-56 -- ni siquiera en
el heartbeat de RF-60) que se guarda tal cual para trazabilidad, sin
comparar contra ninguna lista de gateways registrados. "Tramas inyectadas
desde un gateway no registrado" no es rechazable porque no hay concepto de
gateway registrado en absoluto.

(d) CONFIRMADO: `version_firmware` se persiste (`heartbeat_model.py`) pero
nunca se lee en ninguna condición de negocio (búsqueda exhaustiva en
`recibir_heartbeat_use_case.py`) -- un valor fabricado como "99.9.9" se
acepta y almacena igual que cualquier otro, sin ningún efecto sobre alertas
ni estado. Coincide exactamente con lo que pide documentar la ficha.

Cómo correrlo (desde la raíz del repo; stub de fcntl en Windows, ver memoria
del proyecto):
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    python -m pytest <ruta>\\test_tc_m03_273_replay_integridad_senal_vida.py -v \
        --html=<ruta>\\resultados\\resultado_TC-M03-273.html --self-contained-html
"""
from __future__ import annotations

import re
from dataclasses import replace
from datetime import datetime, timedelta, timezone
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
T0 = datetime(2026, 9, 26, 12, 0, 0, tzinfo=timezone.utc)  # el instante real del heartbeat original


def _estado(fecha_ultimo_contacto: datetime) -> EstadoDispositivoIoT:
    return EstadoDispositivoIoT(
        id_estado_dispositivo_iot=1, id_dispositivo_iot=99, estado_actual='ACTIVO',
        fecha_ultimo_contacto=fecha_ultimo_contacto, id_ultimo_heartbeat=1,
        tiempo_sin_contacto=0, causa_primaria=None, causas_secundarias=None,
        fecha_ultima_actualizacion=fecha_ultimo_contacto, id_usuario=None,
    )


def _dto(version_firmware=None) -> HeartbeatDTO:
    return HeartbeatDTO(tipo_mensaje='PERIODICO', fecha_registro=T0, version_firmware=version_firmware)


def _use_case(estado_existente):
    db = MagicMock()
    dispositivo_port = MagicMock()
    dispositivo_port.validar_dispositivo_heartbeat.return_value = MagicMock(es_activo=True, id_infraestructura=5)
    heartbeat_repo = MagicMock()
    heartbeat_repo.guardar.side_effect = lambda hb: replace(hb, id_heartbeat=1)
    estado_repo = MagicMock()
    estado_repo.obtener_por_dispositivo.return_value = estado_existente
    periodo_repo = MagicMock()
    periodo_repo.obtener_abierto_por_dispositivo.return_value = None
    uc = RecibirHeartbeatUseCase(
        db=db, dispositivo_port=dispositivo_port, heartbeat_repo=heartbeat_repo,
        estado_repo=estado_repo, transicion_repo=MagicMock(), periodo_repo=periodo_repo,
        alerta_repo=MagicMock(), historico_alerta_repo=MagicMock(),
    )
    return uc, estado_existente, heartbeat_repo


def _congelar_reloj(ahora: datetime):
    import unittest.mock as mock
    import src.telemetry.application.use_cases.infraestructura.recibir_heartbeat_use_case as modulo

    class _DatetimeFijo(datetime):
        @classmethod
        def now(cls, tz=None):
            return ahora

    return mock.patch.object(modulo, 'datetime', _DatetimeFijo)


class TestGrupoAReplayNoDetectadoActualizaContactoReal:

    def test_reenviar_el_mismo_heartbeat_30_min_despues_actualiza_el_contacto_al_momento_del_reenvio(self):
        """(a) El dispositivo murio de verdad en T0. 30 minutos despues, alguien reenvia -- sin
        modificar un solo byte -- el MISMO heartbeat capturado en T0 (mismo dto.fecha_registro=T0).
        La ficha pide que esto se descarte y el dispositivo transicione a SIN_SEÑAL. El codigo real
        acepta el reenvio igual que uno legitimo."""
        estado = _estado(T0)
        uc, estado_existente, heartbeat_repo = _use_case(estado)
        dto_capturado = _dto()  # exactamente el mismo heartbeat, sin cambios -- esto ES el replay

        reenvio_30min_despues = T0 + timedelta(minutes=30)
        with _congelar_reloj(reenvio_30min_despues):
            uc.execute(dto_capturado, device_id=99, access_key='k')

        assert estado_existente.fecha_ultimo_contacto == reenvio_30min_despues, (
            f"HALLAZGO (a) BLOQUEANTE: el reenvio del heartbeat capturado en T0 actualizo "
            f"fecha_ultimo_contacto a {estado_existente.fecha_ultimo_contacto} (el momento del "
            f"REENVIO, no el de la captura original) -- igual que si fuera un heartbeat legitimo. "
            f"No existe nonce, contador de trama ni ventana firmada que lo distinga de uno real; "
            f"'recibir_heartbeat_use_case.py' siempre usa 'ahora = datetime.now(timezone.utc)' del "
            f"servidor, nunca dto.fecha_registro, para decidir el contacto. Un atacante que siga "
            f"reenviando el mismo mensaje capturado puede mantener 'vivo' un nodo apagado "
            f"indefinidamente, sin que el algoritmo de RF-60 lo detecte jamas."
        )
        assert estado_existente.estado_actual == 'ACTIVO', (
            'consecuencia directa: el dispositivo NUNCA transiciona a SIN_SEÑAL mientras el replay continue'
        )

    def test_dto_fecha_registro_nunca_se_compara_contra_el_contacto_anterior(self):
        """Evidencia estructural complementaria: ninguna condicion de recibir_heartbeat_use_case.py
        compara dto.fecha_registro contra fecha_ultimo_contacto (lo que haria falta para detectar
        un mensaje repetido o fuera de orden)."""
        archivo = REPO_ROOT / 'src/telemetry/application/use_cases/infraestructura/recibir_heartbeat_use_case.py'
        texto = archivo.read_text(encoding='utf-8')
        comparaciones = re.findall(r'(if|elif|assert)\b[^\n]*fecha_registro[^\n]*fecha_ultimo_contacto|'
                                    r'(if|elif|assert)\b[^\n]*fecha_ultimo_contacto[^\n]*fecha_registro', texto)
        assert comparaciones == [], (
            f'se esperaba que NINGUNA condicion comparara dto.fecha_registro contra fecha_ultimo_contacto; '
            f'se encontraron: {comparaciones} (si aparece esto, la ficha podria estar corregida)'
        )


class TestGrupoBJoinLoRaWANNoAprovisionado:

    def test_no_existe_codigo_lorawan_en_telemetry(self):
        archivos = [
            str(p.relative_to(REPO_ROOT)) for p in (REPO_ROOT / 'src' / 'telemetry').rglob('*.py')
            if re.search(r'lorawan', p.read_text(encoding='utf-8', errors='ignore'), re.I)
        ]
        pytest.fail(
            f"(b) HALLAZGO: no existe ningun codigo LoRaWAN en src/telemetry (encontrado: "
            f"{archivos or 'ninguno'}). 'Join con claves no aprovisionadas' no es una condicion que "
            f"este backend pueda rechazar porque no implementa ningun join server LoRaWAN -- mismo "
            f"hallazgo ya documentado para M09 (TC-M09-G69/G128) y TC-M03-269/270."
        ) if not archivos else None


class TestGrupoCGatewayNoRegistrado:

    def test_no_existe_registro_ni_validacion_de_gateways(self):
        archivos_gateway = [
            str(p.relative_to(REPO_ROOT)) for p in (REPO_ROOT / 'src').rglob('*.py')
            if re.search(r'gateway', p.read_text(encoding='utf-8', errors='ignore'), re.I)
        ]
        # Se espera encontrar SOLO el uso de X-Gateway-Id como dato de trazabilidad (telemetria_router,
        # evento_edge_router, ingerir_telemetria_use_case) y GatewayTimeoutError (ajeno, RF-23/M09) --
        # nunca un GatewayRepository, lista de gateways o validacion de pertenencia.
        con_registro = [a for a in archivos_gateway if re.search(r'class\s+\w*Gateway\w*Repository|gateway.*registrad', a, re.I)]
        pytest.fail(
            f"(c) HALLAZGO: no existe ningun registro de gateways ni validacion de pertenencia en todo "
            f"src/ (archivos que mencionan 'gateway': {archivos_gateway}; ninguno implementa un registro "
            f"o valida 'gateway no registrado'). El unico uso real es X-Gateway-Id como header OPCIONAL "
            f"de trazabilidad en RF-53/RF-56 (ni siquiera en el heartbeat de RF-60) -- 'tramas inyectadas "
            f"desde un gateway no registrado' no es rechazable porque el concepto de 'gateway registrado' "
            f"no existe en el backend."
        ) if not con_registro else None


class TestGrupoDVersionFirmwareFalsificadaSinValorProbatorio:

    def test_firmware_99_9_9_se_acepta_igual_sin_ningun_efecto(self):
        """(d) Un version_firmware fabricado para evadir una alerta (ej. una alerta que dependiera de
        version minima) se acepta y persiste igual -- el campo no participa en ninguna decision."""
        estado = _estado(T0)
        uc, estado_existente, heartbeat_repo = _use_case(estado)
        dto_falsificado = _dto(version_firmware='99.9.9')

        with _congelar_reloj(T0 + timedelta(minutes=1)):
            heartbeat = uc.execute(dto_falsificado, device_id=99, access_key='k')

        assert heartbeat.version_firmware == '99.9.9', 'se persiste tal cual, sin validar contra nada'
        assert estado_existente.estado_actual == 'ACTIVO', (
            'ningun efecto distinto sobre el estado ni sobre ninguna alerta por declarar una version falsa'
        )

    def test_version_firmware_nunca_se_lee_en_una_decision_de_negocio(self):
        archivo = REPO_ROOT / 'src/telemetry/application/use_cases/infraestructura/recibir_heartbeat_use_case.py'
        usos_en_condicion = [
            i for i, linea in enumerate(archivo.read_text(encoding='utf-8').splitlines(), start=1)
            if 'version_firmware' in linea and re.search(r'(if|elif|while|assert)\b.*version_firmware', linea)
        ]
        assert usos_en_condicion == [], (
            f'se esperaba que version_firmware NUNCA apareciera en una condicion de negocio; '
            f'se encontro en las lineas: {usos_en_condicion}'
        )


# ---------------------------------------------------------------------------
# Reintento 1 (2026-10-04, TEST): prueba en vivo del heartbeat, hallazgo M3-01.
# ---------------------------------------------------------------------------
import httpx as _httpx
import os as _os

_API = _os.getenv('SGPMP_BASE_URL', 'https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test')


class TestGrupoEHeartbeatEnVivoTEST:

    def test_heartbeat_valido_responde_200_en_test(self):
        """Hallazgo M3-01: cualquier heartbeat valido responde 400 VALOR_FUERA_DE_RANGO en TEST.
        Se usa un dispositivo creado para la prueba (ver reporte de la sesion)."""
        admin = _httpx.post(f'{_API}/sesiones/', json={'correo_electronico': 'admin@pecuaria.co', 'contrasena': 'Test1234!'}, timeout=30).json()['token']
        h = {'Authorization': f'Bearer {admin}'}
        serial = f"QA-M03-273-R1-{_os.urandom(3).hex()}"
        d = _httpx.post(f'{_API}/configuracion/dispositivos-iot', headers=h, timeout=30, json={
            'serial': serial, 'descripcion': 'QA TC-M03-273 reintento1', 'id_infraestructura': 6,
            'id_tipo_dispositivo': 1, 'es_activo': True}).json()
        from datetime import datetime, timezone
        r = _httpx.post(f'{_API}/iot/heartbeat', timeout=30,
                        headers={'X-Device-Id': str(d['id_dispositivo_iot']), 'X-Device-API-Key': serial},
                        json={'tipo_mensaje': 'PERIODICO', 'fecha_registro': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')})
        assert r.status_code == 200, f'heartbeat valido respondio {r.status_code}: {r.text}'
