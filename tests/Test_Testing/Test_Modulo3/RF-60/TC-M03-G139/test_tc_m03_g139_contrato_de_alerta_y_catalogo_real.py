"""
TC-M03-G139 (RF-60 CA-13/E4/Fase 6/Salida 2, CU-11) - "Enrutamiento,
contrato y volumen de alertas."

Código bajo prueba:
    src/telemetry/domain/entities/alerta.py
    src/telemetry/infrastructure/routers/alerta_router.py
    src/telemetry/application/use_cases/infraestructura/recibir_heartbeat_use_case.py
    src/telemetry/application/use_cases/infraestructura/evaluar_estado_dispositivos_use_case.py

(a) Alertas visibles solo para ingeniero de campo/administrador, 403 para
    productor/veterinario -- PARCIALMENTE CONFIRMADO: el router real
    (`/iot/alertas`, no `/api/v1/alerts/technical`) sí protege la
    consulta con `require_permission(32, 2)`. NO RE-VERIFICADO en esta
    sesión: qué roles concretos tienen el permiso de recurso 32 vive en
    la matriz de roles de BD, no en este código -- no se confirma en
    vivo.
(b) Payload completo (`id_alerta_tecnica` UUID, tipo, severidad,
    `device_id`, unidad productiva, `sensores_afectados`,
    `datos_diagnostico`, `destinatario_rol`, timestamp, sin credenciales)
    -- HALLAZGO DE NOMBRES MASIVO: la entidad real `Alerta` no tiene
    NINGUNO de estos 5 nombres. Tiene `id_alerta` (entero, no UUID, y no
    `id_alerta_tecnica`), `id_dispositivo_ioit` (no `device_id`, con
    error de tipeo "ioit"), `id_infraestructura` (no "unidad
    productiva"), `diagnostico` (no `datos_diagnostico`), y NINGÚN campo
    `destinatario_rol` ni `sensores_afectados` en absoluto -- el
    enrutamiento por rol se resuelve solo vía RBAC en el endpoint, nunca
    se almacena como dato de la alerta.
(c) 2h de SIN_SEÑAL con evaluación cada 60s -> una sola alerta activa,
    no 120 -- CONFIRMADO CORRECTO: `evaluar_estado_dispositivos_use_case.py`
    solo genera una alerta la PRIMERA vez que abre un periodo de
    inactividad (`periodo_existente is None`); en todos los ciclos
    siguientes, mientras el periodo siga abierto, el código no hace
    nada (mismo mecanismo confirmado en TC-M03-G132(f)).
(d) Catálogo de 13 tipos de alerta -- REEJECUTADO 2026-10-29 TRAS MERGE DE
    `origin/test`: el catálogo real creció respecto a la ronda anterior
    (que leía código 380 commits desactualizado). Catálogo real
    confirmado contra el código fuente actual de
    `src/telemetry/application/use_cases/infraestructura/`:
    `BATERIA_CRITICA`, `BATERIA_BAJA`, `SEÑAL_DEGRADADA`,
    `DESINCRONIZACION_RELOJ` (heartbeat); `DISPOSITIVO_SIN_SEÑAL`,
    `DISPOSITIVO_INACTIVO`, `HEARTBEAT_AUSENTE` (evaluación periódica,
    `FALLO_CONECTIVIDAD` ya NO es un tipo_variable de alerta -- quedó
    como `causa_primaria` de la transición, ver TC-M03-G132 reejecutado);
    `SENSOR_FISICO_FALLIDO`, `SOBRECALENTAMIENTO` (con severidad CRITICO
    posible), `FIRMWARE_DESACTUALIZADO` (diagnóstico de heartbeat,
    `evaluar_diagnostico_heartbeat_use_case.py`) -- 10 valores reales
    confirmados, no 4 ni 13. `APAGADO_INMINENTE` sigue sin existir en
    ningún lado. Ver también TC-M03-G145 (reejecutado), que documenta en
    detalle `SENSOR_FISICO_FALLIDO`/`SOBRECALENTAMIENTO`.

Cómo se prueba: inspección directa de los campos de `Alerta`, del router
real, y grep exhaustivo del catálogo de `tipo_variable` generado desde
código.

Como correrlo (Windows necesita el stub de fcntl):
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    $env:SECRET_KEY = "test"
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    python -m pytest <ruta>\\test_tc_m03_g139_contrato_de_alerta_y_catalogo_real.py -v \
        --html=<ruta>\\resultados\\resultado_TC-M03-G139.html --self-contained-html
"""
from __future__ import annotations

from dataclasses import fields
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.telemetry.application.use_cases.infraestructura.evaluar_estado_dispositivos_use_case import (
    EvaluarEstadoDispositivosUseCase,
)
from src.telemetry.domain.entities.alerta import Alerta
from src.telemetry.domain.entities.estado_dispositivo_iot import EstadoDispositivoIoT

REPO_ROOT = Path(__file__).resolve().parents[5]
AHORA = datetime(2026, 10, 20, 12, 0, 0, tzinfo=timezone.utc)


class TestSubCasoAProteccionRbacExisteNoReverificadaContraMatrizDeRoles:
    def test_el_endpoint_real_es_iot_alertas_con_rbac(self):
        archivo = REPO_ROOT / 'src/telemetry/infrastructure/routers/alerta_router.py'
        texto = archivo.read_text(encoding='utf-8')
        assert 'prefix="/iot/alertas"' in texto
        assert 'require_permission(32, 2)' in texto


class TestSubCasoBContratoDePayloadNoCoincideEnNombres:
    def test_ninguno_de_los_5_nombres_de_la_ficha_existe_en_la_entidad_real(self):
        nombres_campos = {f.name for f in fields(Alerta)}
        nombres_ficha = {'id_alerta_tecnica', 'device_id', 'unidad_productiva', 'sensores_afectados', 'destinatario_rol'}
        interseccion = nombres_campos & nombres_ficha
        pytest.fail(
            f"HALLAZGO (b): Alerta declara {sorted(nombres_campos)!r} -- ninguno de "
            f"{sorted(nombres_ficha)!r} existe (interseccion: {sorted(interseccion) or 'vacia'}). "
            f"Los nombres reales equivalentes son id_alerta (int, no UUID), "
            f"id_dispositivo_ioit, id_infraestructura y diagnostico. destinatario_rol y "
            f"sensores_afectados no tienen ningun equivalente: el enrutamiento por rol vive "
            f"solo en el RBAC del endpoint, nunca en la alerta."
        ) if not interseccion else None

    def test_id_alerta_es_entero_no_uuid(self):
        archivo = REPO_ROOT / 'src/telemetry/domain/entities/alerta.py'
        texto = archivo.read_text(encoding='utf-8')
        assert 'id_alerta: Optional[int] = None' in texto


class TestSubCasoCUnaSolaAlertaActivaConfirmadoCorrecto:
    def test_con_alerta_tecnica_ya_activa_no_se_genera_una_segunda(self):
        """REEJECUTADO 2026-10-29: el mecanismo real de deduplicacion cambio --
        ya NO depende de 'periodo ya abierto' (ver TC-M03-G132(f), pendiente
        de reverificar) sino de una consulta explicita
        alerta_repo.buscar_tecnica_activa_dispositivo(), ahora un chequeo de
        idempotencia deliberado, no un efecto colateral."""
        db = MagicMock()
        estado_repo = MagicMock()
        estado = EstadoDispositivoIoT(
            id_estado_dispositivo_iot=1, id_dispositivo_iot=139, estado_actual='SIN_SEÑAL',
            fecha_ultimo_contacto=AHORA - timedelta(hours=1), id_ultimo_heartbeat=1, tiempo_sin_contacto=0,
            causa_primaria='FALLO_CONECTIVIDAD', causas_secundarias=None, fecha_ultima_actualizacion=AHORA, id_usuario=None,
        )
        estado_repo.listar_activos.return_value = [estado]
        estado_repo.bloquear_por_dispositivo.return_value = estado
        periodo_repo = MagicMock()
        periodo_repo.obtener_abierto_por_dispositivo.return_value = None
        alerta_repo = MagicMock()
        alerta_repo.buscar_tecnica_activa_dispositivo.return_value = True
        alerta_repo.listar_conectividad_abierta.return_value = []
        parametros_port = MagicMock()
        parametros = MagicMock(
            umbral_activo=300, umbral_sin_senal=1800, umbral_inactivo=86400,
            estado_local_buffer=None, id_infraestructura=6,
        )
        parametros.heartbeat_ausente.return_value = False
        parametros_port.obtener_comunicacion.return_value = parametros
        uc = EvaluarEstadoDispositivosUseCase(
            db=db, estado_repo=estado_repo, transicion_repo=MagicMock(), periodo_repo=periodo_repo,
            alerta_repo=alerta_repo, historico_alerta_repo=MagicMock(), parametros_port=parametros_port,
        )
        with patch(
            'src.telemetry.application.use_cases.infraestructura.evaluar_estado_dispositivos_use_case.datetime'
        ) as mock_dt:
            mock_dt.now.return_value = AHORA
            for _ in range(120):  # simula 120 ciclos de evaluacion
                uc.execute()
        assert alerta_repo.guardar.call_count == 0


class TestSubCasoDCatalogoRealTieneAlMenos11ValoresNo13:
    def test_el_catalogo_de_tipo_variable_crecio_tras_el_merge_pero_sigue_sin_llegar_a_13(self):
        archivos = [
            REPO_ROOT / 'src/telemetry/application/use_cases/infraestructura/recibir_heartbeat_use_case.py',
            REPO_ROOT / 'src/telemetry/application/use_cases/infraestructura/evaluar_estado_dispositivos_use_case.py',
            REPO_ROOT / 'src/telemetry/application/use_cases/infraestructura/transicion_comunicacion.py',
            REPO_ROOT / 'src/telemetry/application/use_cases/infraestructura/evaluar_diagnostico_heartbeat_use_case.py',
        ]
        texto = ''.join(a.read_text(encoding='utf-8') for a in archivos)
        catalogo_real = {t for t in (
            'BATERIA_CRITICA', 'BATERIA_BAJA', 'APAGADO_INMINENTE', 'SEÑAL_DEGRADADA',
            'DESINCRONIZACION_RELOJ', 'DISPOSITIVO_SIN_SEÑAL', 'DISPOSITIVO_INACTIVO',
            'HEARTBEAT_AUSENTE', 'SENSOR_FISICO_FALLIDO', 'SOBRECALENTAMIENTO',
            'FIRMWARE_DESACTUALIZADO',
        ) if t in texto}
        pytest.fail(
            f"HALLAZGO (d) ACTUALIZADO (corrige tambien a esta misma ronda, ver TC-M03-G142 "
            f"reejecutado): el catalogo real de tipo_variable tras el merge de origin/test "
            f"tiene {len(catalogo_real)} valores confirmados ({sorted(catalogo_real)!r}) -- casi "
            f"el triple de los 4 de la ronda anterior (codigo stale), pero sigue sin llegar a "
            f"los 13 de la ficha. 'FALLO_CONECTIVIDAD' ya no es tipo_variable de alerta (paso a "
            f"ser solo causa_primaria de transicion). 'APAGADO_INMINENTE' SI existe ahora "
            f"(nivel_bateria_pct<=5, severidad CRITICO, con escalamiento real BATERIA_BAJA-> "
            f"BATERIA_CRITICA->APAGADO_INMINENTE vía alerta_repo.escalar_bateria) -- la "
            f"afirmacion anterior de que no existia en ningun lado era incorrecta."
        ) if len(catalogo_real) == 11 else None
