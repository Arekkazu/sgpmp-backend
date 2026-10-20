"""
TC-M03-G135 (RF-60 E1/RNF-05/Restricción 11, CU-17) - "Autenticación de
dispositivo y suplantación de identidad." Consolida CP-SEG-01/05/14 y
CP-VAL-02 -- misma agrupación que TC-M03-272, ya ejecutado en vivo contra
TEST el 2026-10-04 (ver `TC-M03-272/tc_m03_272_autenticacion_dispositivo.postman_collection.json`).

RELACIÓN CON TC-M03-272 (NO duplicar): (a) BOLA, (b) ID inexistente/credencial
inválida + hallazgo de auditoría faltante, (c) dispositivo dado de baja sin
ventana de gracia, y (d) respuestas indistinguibles (mismo código, mismo
mensaje, sin diferencia de tiempo detectable) -- los 4 ya están confirmados
en vivo por TC-272, sin cambios de código desde entonces (mismo
`recibir_heartbeat_use_case.py` / `dispositivo_m09_adapter.py`). Este
archivo SOLO cubre lo nuevo de la ficha v1.3:

(e) [NUEVO] "Tras cada rechazo, timestamp_ultimo_contacto de la víctima
permanece INTACTO, de modo que el reloj de inactividad sigue corriendo y el
nodo caído transiciona a SIN_SEÑAL en su umbral normal." La ficha lo marca
BLOQUEANTE ("permitiría mantener 'vivo' un nodo caído si el rechazo
actualizara el contacto antes de validar").

**CONFIRMADO: SÍ se cumple -- no es un hallazgo de bug, es una confirmación
positiva.** Lectura completa de `recibir_heartbeat_use_case.py::execute()`:
el "Paso 1: Autenticar dispositivo" es literalmente el PRIMER paso de la
función, antes de "Paso 2: Persistir heartbeat" y "Paso 3: Obtener o
inicializar estado" -- si `dispositivo_port.validar_dispositivo_heartbeat()`
devuelve `None` o `es_activo=False`, se lanza `AuthenticationError` de
inmediato y la ejecución nunca llega a tocar
`EstadoDispositivoIoTRepository` en absoluto. No hay ninguna ruta de código
donde un rechazo de autenticación alcance a leer o escribir
`fecha_ultimo_contacto`. Confirmado aquí con un spy sobre `estado_repo`
que no debe recibir ninguna llamada ante un rechazo.

Cómo se prueba: a nivel de caso de uso con repos de prueba (igual criterio
que TC-M03-269/270/273) -- el orden de ejecución es una propiedad del
código, no depende de datos en vivo; probarlo así es más determinista que
contra TEST y no arriesga más cuentas/dispositivos de prueba.

Como correrlo (Windows necesita el stub de fcntl):
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    python -m pytest <ruta>\\test_tc_m03_g135_timestamp_intacto_tras_rechazo.py -v \
        --html=<ruta>\\resultados\\resultado_TC-M03-G135.html --self-contained-html
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from src.shared.errors import AuthenticationError
from src.telemetry.application.use_cases.infraestructura.recibir_heartbeat_use_case import (
    RecibirHeartbeatUseCase,
)
from src.telemetry.infrastructure.dto.heartbeat_dto import HeartbeatDTO

AHORA = datetime(2026, 10, 19, 12, 0, 0, tzinfo=timezone.utc)


def _heartbeat_dto() -> HeartbeatDTO:
    return HeartbeatDTO(
        tipo_mensaje='PERIODICO',
        nivel_bateria_pct=Decimal('80'),
        estado_local_buffer='I',
        datos_pendientes_buffer=0,
        fecha_registro=AHORA,
    )


def _use_case(dispositivo_valido) -> tuple[RecibirHeartbeatUseCase, MagicMock]:
    db = MagicMock()
    dispositivo_port = MagicMock()
    dispositivo_port.validar_dispositivo_heartbeat.return_value = dispositivo_valido
    heartbeat_repo = MagicMock()
    heartbeat_repo.guardar.side_effect = lambda hb: replace(hb, id_heartbeat=1)
    estado_repo = MagicMock()
    transicion_repo = MagicMock()
    periodo_repo = MagicMock()
    alerta_repo = MagicMock()
    historico_alerta_repo = MagicMock()
    uc = RecibirHeartbeatUseCase(
        db=db, dispositivo_port=dispositivo_port, heartbeat_repo=heartbeat_repo,
        estado_repo=estado_repo, transicion_repo=transicion_repo, periodo_repo=periodo_repo,
        alerta_repo=alerta_repo, historico_alerta_repo=historico_alerta_repo,
    )
    return uc, estado_repo


class TestSubCasoETimestampIntactoTrasRechazoDeAutenticacion:
    """(e) [NUEVO]: confirmado -- la autenticacion es el primer paso, antes de
    tocar el repositorio de estado del dispositivo victima."""

    def test_dispositivo_inexistente_nunca_toca_el_repositorio_de_estado(self):
        uc, estado_repo = _use_case(dispositivo_valido=None)

        with pytest.raises(AuthenticationError):
            uc.execute(_heartbeat_dto(), device_id=999999, access_key='clave-cualquiera')

        estado_repo.obtener_por_dispositivo.assert_not_called()
        estado_repo.actualizar.assert_not_called()
        estado_repo.guardar.assert_not_called()

    def test_dispositivo_desactivado_nunca_toca_el_repositorio_de_estado(self):
        dispositivo_dado_de_baja = MagicMock(es_activo=False, id_infraestructura=5)
        uc, estado_repo = _use_case(dispositivo_valido=dispositivo_dado_de_baja)

        with pytest.raises(AuthenticationError):
            uc.execute(_heartbeat_dto(), device_id=4, access_key='clave-de-baja')

        estado_repo.obtener_por_dispositivo.assert_not_called()
        estado_repo.actualizar.assert_not_called()
        estado_repo.guardar.assert_not_called()

    def test_control_un_heartbeat_valido_SI_toca_el_repositorio_de_estado(self):
        """Control: confirma que el spy funciona -- un heartbeat valido SI debe
        llegar a tocar el repositorio de estado, para que los dos tests de
        arriba no pasen por una razon trivial (p.ej. un mock mal armado)."""
        dispositivo_valido = MagicMock(es_activo=True, id_infraestructura=5)
        uc, estado_repo = _use_case(dispositivo_valido=dispositivo_valido)
        estado_repo.obtener_por_dispositivo.return_value = None  # dispositivo nuevo, primer heartbeat

        uc.execute(_heartbeat_dto(), device_id=1, access_key='clave-valida')

        estado_repo.obtener_por_dispositivo.assert_called_once_with(1)
        estado_repo.guardar.assert_called_once()
