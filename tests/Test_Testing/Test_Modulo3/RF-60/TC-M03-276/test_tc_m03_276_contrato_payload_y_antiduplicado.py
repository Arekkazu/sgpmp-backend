"""
TC-M03-276 (b)/(c) (RF-60 CA-13/Fase 6/Salida 2, CU-11) - Contrato de payload
hacia RF-57 y volumen de alertas. (a) se prueba en la coleccion Postman
hermana (`tc_m03_276_enrutamiento_alertas_por_rol.postman_collection.json`,
confirmada en vivo contra TEST, ambas partes correctas).

(b) HALLAZGO: el payload real (`AlertaSchema`) no coincide con el que
describe la ficha. Comparación campo a campo:
  - `id_alerta_tecnica` (UUID) esperado  -> real: `id_alerta: int` (autoincremental, no UUID).
  - `device_id` esperado                -> real: `id_dispositivo_ioit` (con el typo heredado de la BD).
  - `unidad productiva` esperado        -> real: `id_infraestructura` (no hay concepto de "unidad productiva" en el schema).
  - `datos_diagnostico` esperado        -> real: `diagnostico` (campo distinto, sin ese nombre).
  - `destinatario_rol` esperado         -> real: NO EXISTE ningún campo de este tipo; el enrutamiento
    por rol se resuelve enteramente en el RBAC del endpoint (confirmado en (a)), no en un campo del payload.
  - `tipo` del catálogo de 12 tipos esperado -> real: `tipo_alerta` solo toma `'TECNICA'` para este
    camino (RF-60); el detalle de causa va en `tipo_variable` (`BATERIA_CRITICA`/`BATERIA_BAJA`/
    `SEÑAL_DEGRADADA`/`FALLO_CONECTIVIDAD` -- 4 valores, no 12; los otros 8 valores de
    `enum_tipo_alerta` son biológicos, no técnicos).
  - `timestamp` esperado                -> real: hay 7 campos de fecha distintos (`fecha_evento`,
    `fecha_generacion`, `fecha_registro`, `fecha_notificacion`, `fecha_atencion`, `fecha_resolucion`,
    `fecha_vencimiento`), ninguno llamado literalmente `timestamp`.
  - "sin credenciales" SÍ se cumple: no hay ningún campo de credencial/secreto en el schema.

(c) CONFIRMADO (mismo mecanismo ya documentado en TC-M03-269 para CA-6): el
job periódico solo genera una alerta la PRIMERA vez que abre un periodo de
inactividad (`periodo_existente is None`); mientras el periodo siga abierto,
evaluaciones repetidas del mismo dispositivo en el mismo estado NO generan
alertas nuevas. Simulando 120 ciclos de evaluación (2 h a 60 s/ciclo) sobre un
dispositivo que permanece SIN_SEÑAL todo el tiempo: se genera exactamente 1
alerta, no 120.

Cómo correrlo (desde la raíz del repo; stub de fcntl en Windows):
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    python -m pytest <ruta>\\test_tc_m03_276_contrato_payload_y_antiduplicado.py -v \
        --html=<ruta>\\resultados\\resultado_TC-M03-276.html --self-contained-html
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from src.telemetry.application.use_cases.infraestructura.evaluar_estado_dispositivos_use_case import (
    EvaluarEstadoDispositivosUseCase,
)
from src.telemetry.domain.entities.estado_dispositivo_iot import EstadoDispositivoIoT
from src.telemetry.infrastructure.schema.alerta_schema import AlertaSchema

T0 = datetime(2026, 9, 26, 12, 0, 0, tzinfo=timezone.utc)


def _congelar_reloj(modulo, ahora: datetime):
    import unittest.mock as mock

    class _DatetimeFijo(datetime):
        @classmethod
        def now(cls, tz=None):
            return ahora

    return mock.patch.object(modulo, 'datetime', _DatetimeFijo)


class TestGrupoBContratoDePayload:

    def test_los_campos_que_pide_la_ficha_no_existen_en_el_schema_real(self):
        campos_reales = set(AlertaSchema.model_fields.keys())
        campos_que_pide_la_ficha = {
            'id_alerta_tecnica', 'device_id', 'unidad_productiva', 'datos_diagnostico', 'destinatario_rol', 'timestamp',
        }
        coinciden = campos_que_pide_la_ficha & campos_reales
        pytest.fail(
            f"HALLAZGO (b): ninguno de los nombres de campo que pide la ficha "
            f"({sorted(campos_que_pide_la_ficha)}) existe en AlertaSchema. Campos reales: "
            f"{sorted(campos_reales)}. El enrutamiento por rol se resuelve en el RBAC del endpoint "
            f"(confirmado en la coleccion Postman hermana), no en un campo 'destinatario_rol' del payload."
        ) if not coinciden else None

    def test_id_alerta_es_entero_autoincremental_no_uuid(self):
        assert AlertaSchema.model_fields['id_alerta'].annotation is int, (
            "la ficha pide id_alerta_tecnica como UUID; el campo real id_alerta es int"
        )


class TestGrupoCAntiduplicadoEn120Ciclos:

    def test_120_ciclos_de_evaluacion_en_2_horas_generan_una_sola_alerta(self):
        import src.telemetry.application.use_cases.infraestructura.evaluar_estado_dispositivos_use_case as modulo

        estado = EstadoDispositivoIoT(
            id_estado_dispositivo_iot=1, id_dispositivo_iot=88, estado_actual='ACTIVO',
            fecha_ultimo_contacto=T0, id_ultimo_heartbeat=1, tiempo_sin_contacto=0,
            causa_primaria=None, causas_secundarias=None, fecha_ultima_actualizacion=T0, id_usuario=None,
        )
        estado_repo = MagicMock()
        estado_repo.listar_activos.return_value = [estado]
        periodo_repo = MagicMock()
        periodo_abierto = {'abierto': False}

        def _obtener_abierto(_id):
            return MagicMock(id_periodo_inactividad=1) if periodo_abierto['abierto'] else None

        def _abrir(_periodo):
            periodo_abierto['abierto'] = True
            return _periodo

        periodo_repo.obtener_abierto_por_dispositivo.side_effect = _obtener_abierto
        periodo_repo.abrir.side_effect = _abrir
        alerta_repo = MagicMock()
        alerta_repo.guardar.return_value = MagicMock(id_alerta=1)

        job = EvaluarEstadoDispositivosUseCase(
            db=MagicMock(), estado_repo=estado_repo, transicion_repo=MagicMock(),
            periodo_repo=periodo_repo, alerta_repo=alerta_repo, historico_alerta_repo=MagicMock(),
        )

        # El dispositivo deja de responder en T0 + 5min (entra en SIN_SEÑAL) y se queda ahi
        # durante 2 horas, evaluado cada 60s (120 ciclos).
        for ciclo in range(120):
            ahora = T0 + timedelta(minutes=5) + timedelta(seconds=60 * ciclo)
            with _congelar_reloj(modulo, ahora):
                job.execute()

        assert alerta_repo.guardar.call_count == 1, (
            f"se esperaba 1 alerta activa por condicion tras 120 ciclos de evaluacion, no "
            f"{alerta_repo.guardar.call_count}"
        )
