# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-23 | destroyerban | DEV-37 RF-73: reintentos, respaldo local y sincronización de la bitácora M04 |
# | 2026-10-27 | Leandro | INC-M04-158-G086 RF-73: probar fallo de persistencia con referencia valida y conservar E1. |
# | 2026-10-29 | Arekkazu | QA-M04-27-10 CU09 H-02/H-04 RF-73: NOTAS_REGISTRADAS; solo RF-67 emite HISTORIAL_CONSULTADO |
# | 2026-10-30 | Arekkazu | INC-M04-229-G070 RF-72: VENTANA_RETROALIMENTACION_AMPLIADA |
# | 2026-10-31 | Arekkazu | RF-71/RF-73: REENTRENAMIENTO_SOLICITADO |
"""DEV-03 (RF-67/70/73): la auditoría M04 solo emite valores que existen en sus enums.

Cinco use cases emitían ``tipo_evento`` fuera de ``enum_tipo_evento_auditoria_m04``
y ``resultado_operacion = "OK"`` fuera de ``enum_resultado_operacion_auditoria``.
El repositorio se tragaba el error del flush y dejaba la sesión inutilizable:
``GET /prediccion/historial/{id}``, ``GET /prediccion/modelos/{id}/ota-status``
y ``GET /prediccion/despliegues`` respondían 500 en toda consulta válida, y
consultar o exportar la auditoría perdía su evento. Fakes en memoria, sin DB;
``tests/integration/test_dev03_auditoria_m04_enum_integration.py`` verifica
estas mismas listas contra ``pg_enum``.
"""
from __future__ import annotations

import contextlib

import re
from datetime import date, timedelta
from pathlib import Path

import pytest

from src.prediction.application.use_cases.auditoria.consultar_auditoria_m04_use_case import ConsultarAuditoriaM04UseCase
from src.prediction.application.use_cases.auditoria.exportar_auditoria_m04_use_case import ExportarAuditoriaM04UseCase
from src.prediction.application.use_cases.historial_diagnostico.consultar_historial_use_case import ConsultarHistorialUseCase
from src.prediction.application.use_cases.ota.consultar_ota_status_use_case import ConsultarOtaStatusUseCase
from src.prediction.application.use_cases.ota.listar_despliegues_use_case import ListarDesplieguesUseCase
from src.prediction.infrastructure.repositories.evento_auditoria_m04_repository import (
    SqlAlchemyEventoAuditoriaM04Repository,
)
from src.shared.errors import InfrastructureError

RAIZ_PREDICTION = Path(__file__).resolve().parents[2] / "src" / "prediction"

#: Copia de ``modulo4.enum_tipo_evento_auditoria_m04`` (la prueba de integración
#: la compara contra la base).
TIPOS_EVENTO_M04 = frozenset({
    "CATALOGO_PATOLOGIA_AGREGADA", "CATALOGO_PATOLOGIA_MODIFICADA", "CATALOGO_PATOLOGIA_INACTIVADA",
    "CONFIGURACION_MOTOR_CAMBIADA", "INFERENCIA_EJECUTADA", "INFERENCIA_RECHAZADA", "LATENCIA_EXCEDIDA",
    "INFERENCIA_NO_DISPONIBLE", "ALERTA_PREDICCION_GENERADA", "HISTORIAL_CONSULTADO", "EXPORTACION_GENERADA",
    "RIESGO_CONTAGIO_CALCULADO", "ALERTA_CONTAGIO_GENERADA", "ERROR_DATOS_INSUFICIENTES",
    "ERROR_DATOS_DESINCRONIZADOS", "SOBRECARGA_MODELO_CONTAGIO", "ALERTA_CALIDAD_DATOS", "VERSION_REGISTRADA",
    "VERSION_APROBADA", "VERSION_RECHAZADA", "VERSION_ACTIVADA", "VERSION_DEPRECADA", "NOTAS_REGISTRADAS",
    "HASH_INVALIDO_DETECTADO",
    "INTENTO_CARGA_MODELO_EXTERNO", "MODELO_DISTRIBUIDO_EDGE", "MODELO_ACTIVADO_EDGE", "DISTRIBUCION_FALLIDA",
    "DISTRIBUCION_POSPUESTA", "REENTRENAMIENTO_SOLICITADO", "REENTRENAMIENTO_INICIADO", "REENTRENAMIENTO_COMPLETADO", "REENTRENAMIENTO_FALLIDO",
    "REENTRENAMIENTO_ABORTADO", "REENTRENAMIENTO_INTERRUMPIDO", "REENTRENAMIENTO_PAUSADO_POR_PRIORIDAD",
    "DEGRADACION_DETECTADA", "RETROALIMENTACION_REGISTRADA", "CONFLICTO_RETROALIMENTACION",
    "VENTANA_RETROALIMENTACION_AMPLIADA",
    "AUDITORIA_EVENTO_INVALIDO", "AUDITORIA_FALLA_PERSISTENCIA", "AUDITORIA_FALLBACK_ACTIVADO",
    "TIMESTAMP_CORREGIDO",
})
#: Copia de ``modulo4.enum_resultado_operacion_auditoria``.
RESULTADOS_OPERACION_M04 = frozenset({"EXITOSO", "FALLIDO", "PARCIAL"})


def _literales(campo: str) -> dict[str, set[str]]:
    """Valor literal de ``campo=`` -> archivos de ``src/prediction`` que lo emiten."""
    patron = re.compile(rf"""\b{campo}=["']([A-Z_]+)["']""")
    encontrados: dict[str, set[str]] = {}
    for archivo in RAIZ_PREDICTION.rglob("*.py"):
        for valor in patron.findall(archivo.read_text(encoding="utf-8")):
            encontrados.setdefault(valor, set()).add(archivo.relative_to(RAIZ_PREDICTION).as_posix())
    return encontrados


# ── Ningún use case de M04 emite un valor fuera del enum ───────────────────

def test_todo_tipo_evento_emitido_existe_en_el_enum():
    fuera = {v: a for v, a in _literales("tipo_evento").items() if v not in TIPOS_EVENTO_M04}
    assert not fuera, f"tipo_evento fuera de enum_tipo_evento_auditoria_m04: {fuera}"


def test_todo_resultado_operacion_emitido_existe_en_el_enum():
    fuera = {v: a for v, a in _literales("resultado_operacion").items() if v not in RESULTADOS_OPERACION_M04}
    assert not fuera, f"resultado_operacion fuera de enum_resultado_operacion_auditoria: {fuera}"


# ── Los cinco use cases de D-03 ─────────────────────────────────────────────

class _Db:
    def __init__(self): self.commits = 0
    def commit(self): self.commits += 1
    def rollback(self): pass


class _Auditoria:
    def __init__(self): self.eventos: list[dict] = []
    def registrar(self, **kw): self.eventos.append(kw)
    def consultar(self, **_kw): return [], 0


class _HistorialRepo:
    def consultar(self, **_kw): return []
    def materializar_eventos(self, _eventos): pass


class _ActivoAccesible:
    def activo_existe_y_accesible(self, *_a): return True


class _VersionExiste:
    def obtener_estado(self, _id): return "ACTIVO"


class _OtaRepo:
    def obtener_por_version(self, **_kw): return []
    def listar(self, **_kw): return [], 0


def _evento_unico(auditoria: _Auditoria) -> dict:
    assert len(auditoria.eventos) == 1
    return auditoria.eventos[0]


def test_consultar_historial_emite_historial_consultado():
    db, auditoria = _Db(), _Auditoria()
    hoy = date.today()
    ConsultarHistorialUseCase(
        db=db, repo=_HistorialRepo(), auditoria_repo=auditoria, activo_port=_ActivoAccesible(),
    ).execute(
        id_activo_biologico=5, fecha_inicio=hoy - timedelta(days=7), fecha_fin=hoy, nivel_riesgo=None,
        id_patologia=None, incluir_alertas=True, cursor_paginacion=None, id_usuario=1, id_rol=1,
    )
    evento = _evento_unico(auditoria)
    assert evento["tipo_evento"] == "HISTORIAL_CONSULTADO"
    assert evento["resultado_operacion"] == "EXITOSO"
    assert evento["payload_evento"]["consulta"] == "HISTORIAL_DIAGNOSTICO"
    assert db.commits == 1


# CU09 H-04: HISTORIAL_CONSULTADO es del historial diagnóstico (RF-67). Consultar la
# OTA, los despliegues o la bitácora llenaba la auditoría con 5 a 7 eventos por carga.

def test_consultar_ota_status_no_deja_evento():
    ota = _OtaRepo()
    assert ConsultarOtaStatusUseCase(repo=ota, version_port=_VersionExiste()).execute(
        id_version=3, id_dispositivo=None, estado=None,
    ) == (3, [])


def test_listar_despliegues_no_deja_evento():
    assert ListarDesplieguesUseCase(repo=_OtaRepo(), version_port=_VersionExiste()).execute(
        id_version=None, id_dispositivo=None, estado=None, limit=20, offset=0,
    ) == ([], 0)


def test_consultar_auditoria_no_deja_evento():
    auditoria = _Auditoria()
    ConsultarAuditoriaM04UseCase(auditoria).listar(
        tipo_evento=None, fecha_desde=None, fecha_hasta=None, id_usuario=None, id_sistema=None,
        id_referencia=None, severidad_evento=None, pagina=1, por_pagina=50,
    )
    assert auditoria.eventos == []


def test_exportar_auditoria_emite_exportacion_generada():
    db, auditoria = _Db(), _Auditoria()
    ExportarAuditoriaM04UseCase(db, auditoria).exportar(
        tipo_evento=None, fecha_desde=None, fecha_hasta=None, id_usuario=None, id_sistema=None,
        id_referencia=None, severidad_evento=None, formato="json", id_usuario_exportador=1,
    )
    evento = _evento_unico(auditoria)
    assert evento["tipo_evento"] == "EXPORTACION_GENERADA"
    assert evento["resultado_operacion"] == "EXITOSO"
    assert evento["payload_evento"]["exportacion"] == "AUDITORIA_M04"
    assert db.commits == 1


# ── El repositorio ya no se traga el error del flush ───────────────────────

class _SesionFlushFalla:
    def begin_nested(self): return contextlib.nullcontext()
    def add(self, _orm): pass
    def flush(self): raise RuntimeError("invalid input value for enum")


class _RespaldoFalla:
    """DEV-37: el 500 solo queda cuando tampoco se puede respaldar el evento."""
    def guardar(self, _evento): raise OSError("disco lleno")


def _repo_sin_respaldo():
    return SqlAlchemyEventoAuditoriaM04Repository(_SesionFlushFalla(), _RespaldoFalla(), pausa_reintento=0)


def test_flush_fallido_se_propaga_como_500():
    repo = _repo_sin_respaldo()
    with pytest.raises(InfrastructureError) as exc:
        repo.registrar(
            tipo_evento="HISTORIAL_CONSULTADO", tipo_actor="USUARIO", id_usuario=1,
            id_referencia="consulta-ota", payload_evento={"consulta": "OTA_STATUS"},
        )
    assert exc.value.code == "AUDITORIA_M04_NO_PERSISTIDA"
    assert isinstance(exc.value.__cause__, RuntimeError)


def test_flush_fallido_del_evento_invalido_tambien_se_propaga():
    """Un payload sin sus campos mínimos se guarda como AUDITORIA_EVENTO_INVALIDO;
    si ese flush falla, tampoco puede quedar la sesión rota en silencio."""
    repo = _repo_sin_respaldo()
    with pytest.raises(InfrastructureError):
        repo.registrar(tipo_evento="VERSION_ACTIVADA", tipo_actor="USUARIO", id_usuario=1, payload_evento={})
