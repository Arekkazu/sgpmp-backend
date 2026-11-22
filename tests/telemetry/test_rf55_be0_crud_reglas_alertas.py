# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-28 | Arekkazu | BE-0..BE-3 RF-55: CRUD de reglas y regla aplicada en eventos Edge |
"""RF-55 BE-0: CRUD de reglas de alerta; BE-1/2/3: lo que el Edge manda de la regla.

Fakes en memoria. El trigger de versión y los permisos RBAC se prueban contra
la BD en la migración 46252dbd62b4.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src.shared.errors import BusinessRuleError, NotFoundError, PreconditionFailedError, ValidationError
from src.telemetry.application.use_cases.inferencia import recibir_evento_edge_use_case as modulo_evento
from src.telemetry.application.use_cases.reglas.crear_regla_alerta_use_case import CrearReglaAlertaUseCase
from src.telemetry.application.use_cases.reglas.desactivar_regla_alerta_use_case import DesactivarReglaAlertaUseCase
from src.telemetry.application.use_cases.reglas.editar_regla_alerta_use_case import EditarReglaAlertaUseCase
from src.telemetry.application.use_cases.reglas.reactivar_regla_alerta_use_case import ReactivarReglaAlertaUseCase
from src.telemetry.domain.entities.alerta import ReglaAlerta, regla_edge
from src.telemetry.infrastructure.dto.recibir_evento_edge_dto import RecibirEventoEdgeDTO
from src.telemetry.infrastructure.dto.regla_alerta_dto import CrearReglaAlertaDTO, EditarReglaAlertaDTO

T0 = datetime(2026, 10, 28, 14, 0, tzinfo=timezone.utc)
_BASE = dict(nombre="ESTRES_TERMICO", tipo_sensor="TEMPERATURA", umbral_min="18", umbral_max="30",
             ventana_confirmacion_min="5", lectura_confirmacion_max="3")


class _Repo:
    """Simula la BD: asigna id al crear y, como el trigger, renueva fecha y versión al actualizar."""

    def __init__(self):
        self.reglas: dict[int, ReglaAlerta] = {}

    def obtener_por_id(self, id_regla_alertas, *, bloquear=False):
        return self.reglas.get(id_regla_alertas)

    def crear(self, regla):
        regla.id_regla_alertas = len(self.reglas) + 1
        regla.fecha_creacion = regla.fecha_actualizacion = T0
        self.reglas[regla.id_regla_alertas] = regla
        return regla

    def actualizar(self, regla):
        regla.version_regla += 1
        regla.fecha_actualizacion = regla.fecha_actualizacion + timedelta(seconds=1)
        return regla


@pytest.fixture
def ctx():
    db, sincronizar = Mock(), Mock()
    sincronizar.execute.return_value = "resultado-sync"
    return SimpleNamespace(db=db, repo=_Repo(), sincronizar=sincronizar)


def _crear(ctx, **cambios):
    dto = CrearReglaAlertaDTO(**{**_BASE, **cambios})
    return CrearReglaAlertaUseCase(ctx.db, ctx.repo, ctx.sincronizar).execute(dto, id_usuario=1)


# --- BE-0: crear ---------------------------------------------------------------------------

def test_crear_regla_simple_no_se_propaga_al_edge(ctx):
    regla, sync = _crear(ctx)
    assert regla.id_regla_alertas == 1 and regla.es_activa and regla.id_usuario == 1
    assert sync is None
    ctx.db.commit.assert_called_once()
    ctx.sincronizar.execute.assert_not_called()


def test_crear_compuesta_para_edge_se_propaga_despues_del_commit(ctx):
    orden = []
    ctx.db.commit.side_effect = lambda: orden.append("commit")
    ctx.sincronizar.execute.side_effect = lambda *a: orden.append("sync") or "resultado-sync"
    regla, sync = _crear(ctx, es_regla_compuesta=True, tiene_ejecutar_edge=True)
    assert sync == "resultado-sync"
    ctx.sincronizar.execute.assert_called_once_with(regla.id_regla_alertas, 1)
    assert orden == ["commit", "sync"]


@pytest.mark.parametrize("cambios, codigo", [
    ({"umbral_min": None, "umbral_max": None}, "REGLA_SIN_UMBRAL"),
    ({"umbral_min": "30", "umbral_max": "30"}, "RANGO_UMBRAL_INVALIDO"),
    ({"tiene_ejecutar_edge": True}, "REGLA_EDGE_NO_COMPUESTA"),
])
def test_crear_rechaza_reglas_que_no_se_pueden_evaluar(ctx, cambios, codigo):
    with pytest.raises(ValidationError) as exc:
        _crear(ctx, **cambios)
    assert exc.value.code == codigo
    ctx.db.commit.assert_not_called()


def test_compuesta_solo_con_umbrales_severidad_es_valida(ctx):
    regla, _ = _crear(ctx, umbral_min=None, umbral_max=None, es_regla_compuesta=True,
                      umbrales_severidad={"THI": {"MODERADO": 72, "CRITICO": 79}})
    assert regla.umbrales_severidad == {"THI": {"MODERADO": 72, "CRITICO": 79}}


_EDGE = dict(es_regla_compuesta=True, tiene_ejecutar_edge=True)


@pytest.mark.parametrize("cambios, codigo", [
    ({"lectura_confirmacion_max": "2.5"}, "LECTURAS_CONFIRMACION_INVALIDAS"),
    ({"lectura_confirmacion_max": "101"}, "LECTURAS_CONFIRMACION_INVALIDAS"),
    ({"ventana_confirmacion_min": "0"}, "VENTANA_CONFIRMACION_INVALIDA"),
    ({"umbrales_severidad": {"leve": 68}}, "UMBRALES_SEVERIDAD_INVALIDOS"),
])
def test_regla_edge_rechaza_lo_que_el_firmware_no_aplicaria(ctx, cambios, codigo):
    with pytest.raises(ValidationError) as exc:
        _crear(ctx, **_EDGE, **cambios)
    assert exc.value.code == codigo


def test_regla_edge_sin_ventana_con_una_lectura_es_valida(ctx):
    regla, _ = _crear(ctx, **_EDGE, ventana_confirmacion_min="0", lectura_confirmacion_max="1",
                      umbrales_severidad={"LEVE": 68, "MODERADO": 72, "CRITICO": 79})
    assert regla.ventana_confirmacion_min == 0


def test_regla_edge_no_cambia_de_alcance(ctx):
    _crear(ctx, **_EDGE, id_finca=1)
    with pytest.raises(BusinessRuleError) as exc:
        _editar(ctx, T0, id_finca=2)
    assert exc.value.code == "ALCANCE_REGLA_EDGE_INMUTABLE"
    regla, _ = _editar(ctx, T0, id_finca=1, umbral_max="31")
    assert regla.umbral_max == Decimal("31")


def test_dto_rechaza_tipo_sensor_fuera_del_enum():
    with pytest.raises(Exception):
        CrearReglaAlertaDTO(**{**_BASE, "tipo_sensor": "THI"})


# --- BE-0: editar --------------------------------------------------------------------------

def _editar(ctx, fecha, **cambios):
    dto = EditarReglaAlertaDTO(**{**_BASE, **cambios, "fecha_actualizacion": fecha})
    return EditarReglaAlertaUseCase(ctx.db, ctx.repo, ctx.sincronizar).execute(1, dto, id_usuario=2)


def test_editar_reemplaza_la_regla_y_sube_version(ctx):
    _crear(ctx, es_regla_compuesta=True, tiene_ejecutar_edge=True)
    ctx.sincronizar.reset_mock()
    regla, sync = _editar(ctx, T0, lectura_confirmacion_max="4", descripcion=None)
    assert regla.lectura_confirmacion_max == Decimal("4") and regla.version_regla == 2
    assert regla.id_usuario == 2 and regla.es_regla_compuesta and regla.tiene_ejecutar_edge
    assert sync == "resultado-sync"


def test_editar_acepta_la_misma_fecha_en_otra_zona(ctx):
    _crear(ctx)
    regla, _ = _editar(ctx, T0.astimezone(timezone(timedelta(hours=-5))), umbral_max="31")
    assert regla.umbral_max == Decimal("31")


@pytest.mark.parametrize("fecha", [T0 - timedelta(seconds=1), None])
def test_editar_con_fecha_vieja_o_ausente_da_412(ctx, fecha):
    _crear(ctx)
    with pytest.raises(PreconditionFailedError) as exc:
        _editar(ctx, fecha)
    assert exc.value.code == "CONFLICTO_CONCURRENCIA"
    ctx.db.rollback.assert_called_once()


def test_editar_regla_inactiva_da_422(ctx):
    regla, _ = _crear(ctx)
    regla.es_activa = False
    with pytest.raises(BusinessRuleError) as exc:
        _editar(ctx, T0)
    assert exc.value.code == "REGLA_ALERTA_INACTIVA"


def test_editar_regla_inexistente_da_404(ctx):
    with pytest.raises(NotFoundError):
        _editar(ctx, T0)


# --- BE-0: desactivar / reactivar ------------------------------------------------------------

def test_desactivar_retira_del_edge_y_reactivar_la_devuelve(ctx):
    _crear(ctx, es_regla_compuesta=True, tiene_ejecutar_edge=True)
    ctx.sincronizar.reset_mock()
    regla, sync = DesactivarReglaAlertaUseCase(ctx.db, ctx.repo, ctx.sincronizar).execute(1, id_usuario=3)
    assert not regla.es_activa and sync == "resultado-sync"
    with pytest.raises(BusinessRuleError) as exc:
        DesactivarReglaAlertaUseCase(ctx.db, ctx.repo, ctx.sincronizar).execute(1, id_usuario=3)
    assert exc.value.code == "REGLA_ALERTA_YA_INACTIVA"

    regla, _ = ReactivarReglaAlertaUseCase(ctx.db, ctx.repo, ctx.sincronizar).execute(1, id_usuario=3)
    assert regla.es_activa
    assert ctx.sincronizar.execute.call_count == 2
    with pytest.raises(BusinessRuleError) as exc:
        ReactivarReglaAlertaUseCase(ctx.db, ctx.repo, ctx.sincronizar).execute(1, id_usuario=3)
    assert exc.value.code == "REGLA_ALERTA_YA_ACTIVA"


# --- BE-3: la regla que evaluó el Edge llega a la alerta ------------------------------------

def test_regla_edge_compuesta_usa_el_nombre_de_la_regla_en_bd():
    regla = ReglaAlerta(id_regla_alertas=12, nombre="Estrés térmico por THI", tipo_sensor="TEMPERATURA",
                        es_regla_compuesta=True, ventana_confirmacion_min=Decimal("5"),
                        lectura_confirmacion_max=Decimal("3"), es_activa=True, version_regla=3)
    metadata = {"regla_aplicada": "ESTRES_TERMICO", "version_regla": 3}
    assert regla_edge("DESVIACION_COMPUESTA", metadata, regla, "TEMPERATURA_AMBIENTAL") == {
        "id": 12, "nombre": "Estrés térmico por THI", "tipo": "REGLA_EDGE", "codigo_edge": "ESTRES_TERMICO",
        "clasificacion_rf55": "DESVIACION_COMPUESTA", "version_regla": 3,
    }


def test_regla_edge_simple_conserva_los_datos_del_umbral():
    metadata = {"regla_aplicada": "UMBRAL_AMBIENTAL", "id_umbral_ambiental": 5, "version_umbral": 2,
                "nivel_umbral": "critico"}
    r = regla_edge("DESVIACION_SIMPLE", metadata, None, "PH_AGUA")
    assert r["id_umbral_ambiental"] == 5 and r["version_umbral"] == 2 and r["tipo"] == "UMBRAL_AMBIENTAL"
    assert regla_edge("DESVIACION_SIMPLE", None, None, "PH_AGUA") == "DESVIACION_SIMPLE"


# --- BE-1 / BE-2: eventos Edge ---------------------------------------------------------------

def _evento(metadata):
    captura = datetime.now(timezone.utc) - timedelta(minutes=1)
    return RecibirEventoEdgeDTO(
        device_id=3, sensor_id=7, serial="TC-M09-0001", clasificacion_rf55="DESVIACION_COMPUESTA",
        severidad="MODERADO", timestamp_captura=captura, timestamp_procesamiento_edge=captura,
        origen="TIEMPO_REAL", estado_conectividad=True, metadata_edge=metadata,
        variables_involucradas=[{"tipo_variable": "TEMPERATURA_AMBIENTAL", "valor": "32.5", "unidad": "C",
                                 "sensor": "dht22_ambiente", "serial": "TC-M09-0001", "sensor_id": 7}],
    )


@pytest.fixture
def recibir(monkeypatch):
    monkeypatch.setattr(modulo_evento, "registrar_llamada", lambda *a: None)
    eventos, dispositivos, reglas = Mock(), Mock(), Mock()
    dispositivos.obtener_dispositivo_activo.return_value = SimpleNamespace(
        id_dispositivo_iot=3, id_sensor=7, id_infraestructura=9, es_activo_dispositivo=True, es_activo_sensor=True,
    )
    eventos.guardar.side_effect = lambda e: setattr(e, "id_evento_edge_computing", 17) or e
    reglas.obtener_por_id.side_effect = lambda i: SimpleNamespace(id_regla_alertas=12) if i == 12 else None
    uc = modulo_evento.RecibirEventoEdgeUseCase(
        Mock(), eventos, Mock(), dispositivos, Mock(), Mock(), None, regla_repo=reglas,
    )
    # La consolidación a M04 y la alerta no son de esta prueba.
    monkeypatch.setattr(modulo_evento, "ConsolidarEnviarPaqueteUseCase", lambda **k: Mock(execute=lambda e: None))
    monkeypatch.setattr(uc, "_generar_alerta_best_effort", Mock())
    return SimpleNamespace(uc=uc, eventos=eventos)


def test_variables_conservan_sensor_serial_y_sensor_id(recibir):
    recibir.uc.execute(_evento({}))
    variable = recibir.eventos.guardar.call_args.args[0].variables_involucradas[0]
    assert variable["sensor"] == "dht22_ambiente" and variable["serial"] == "TC-M09-0001"
    assert variable["sensor_id"] == 7


@pytest.mark.parametrize("metadata, esperado", [
    ({"id_regla_alerta": 12}, 12),
    ({"id_regla_alerta": 99}, None),     # no existe: la FK haría perder el evento
    ({"id_regla_alerta": True}, None),   # bool es int en Python
    ({"id_regla_alerta": "12"}, None),
    ({"id_regla_alerta": 2**40}, None),  # fuera de integer: no se consulta
    (None, None),
])
def test_evento_guarda_id_regla_alerta_solo_si_la_regla_existe(recibir, metadata, esperado):
    recibir.uc.execute(_evento(metadata))
    assert recibir.eventos.guardar.call_args.args[0].id_regla_alerta == esperado
    if esperado:
        assert recibir.uc._generar_alerta_best_effort.call_args.kwargs["regla"].id_regla_alertas == esperado
