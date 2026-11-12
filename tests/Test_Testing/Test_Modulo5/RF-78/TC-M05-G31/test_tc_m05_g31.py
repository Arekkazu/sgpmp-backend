# | Fecha      | Nombre           | Que se hizo                                   |
# |------------|------------------|-----------------------------------------------|
# | 2026-11-06 | Juan Manuel      | TC-M05-G31 RF-78: atomicidad y reintentos del costeo directo |
"""TC-M05-G31 / TC-M05-048 (RF-78, CA-6, E5, FA-07/FA-08): atomicidad ante fallo de BD y reintentos 1 s / 3 s / 5 s.

No se ejecuta en TEST (inyección de fallos). Se prueban los casos de uso reales
(RegistrarSuministroDirectoUseCase y RegistrarCorreccionSuministroUseCase) con los puertos reemplazados
por dobles en memoria. La ficha pide Postgres local, pero en este entorno no hay base local; la política
de reintentos, rollback y auditoría del fallo vive en los casos de uso.

Uso:  pytest tests/Test_Testing/Test_Modulo5/RF-78/TC-M05-G31 -v --noconftest
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from psycopg2 import errors as pg_errors

from src.shared.errors import ConflictError, InfrastructureError
from src.supplies.application.use_cases.costeo_suministros import registrar_correccion_suministro_use_case as mod_corr
from src.supplies.application.use_cases.costeo_suministros import registrar_suministro_directo_use_case as mod_reg
from src.supplies.application.use_cases.costeo_suministros.registrar_correccion_suministro_use_case import (
    RegistrarCorreccionSuministroUseCase,
)
from src.supplies.application.use_cases.costeo_suministros.registrar_suministro_directo_use_case import (
    RegistrarSuministroDirectoUseCase,
)
from src.supplies.domain.entities.registro_suministro_directo import RegistroSuministroDirecto
from src.supplies.domain.repositories.ciclo_abierto_port import CicloAbierto, FaseProductiva
from src.supplies.infrastructure.dto.registrar_correccion_suministro_dto import RegistrarCorreccionSuministroDTO
from src.supplies.infrastructure.dto.registrar_suministro_directo_dto import RegistrarSuministroDirectoDTO

USUARIO = SimpleNamespace(id_usuario=143)
HOY = datetime.now(timezone.utc).date()


class Sesion:
    def __init__(self):
        self.commits = self.rollbacks = 0

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


class Auditoria:
    def __init__(self):
        self.eventos = []

    def registrar(self, evento):
        self.eventos.append(evento)


class Movimiento:
    """RF-80/RF-79: mueve el acumulado. Si el guardado falla nunca debe llamarse."""

    def __init__(self):
        self.llamadas = []

    def registrar(self, registro, **k):
        self.llamadas.append(registro)


class RepoQueFalla:
    def __init__(self, error, original=None):
        self.error, self.original, self.intentos, self.guardados = error, original, 0, []

    def existe_idempotente(self, uuid):
        return None

    def existe_duplicado_contenido(self, **k):
        return False

    def obtener_por_id(self, id_):
        return self.original

    def guardar(self, entidad):
        self.intentos += 1
        raise self.error


def _dto():
    return RegistrarSuministroDirectoDTO(
        id_activo_biologico=825, tipo_suministro="SERVICIO_VETERINARIO", id_idempotencia=uuid4(), cantidad=Decimal("1"),
        unidad_medida="servicio", precio_unitario=Decimal("150000"), fecha_aplicacion=HOY - timedelta(days=2),
        justificacion_precio="Tarifa de la factura del veterinario externo")


def _registro(error, monkeypatch):
    esperas = []
    monkeypatch.setattr(mod_reg.time, "sleep", lambda s: esperas.append(s))
    db, aud, mov, repo = Sesion(), Auditoria(), Movimiento(), RepoQueFalla(error)
    uc = RegistrarSuministroDirectoUseCase(
        db=db, registro_repo=repo, auditoria_port=aud, movimiento=mov,
        ciclo_port=SimpleNamespace(obtener_abierto=lambda id_: CicloAbierto(
            id_ciclo_productivo=4, fecha_inicio=datetime(2026, 10, 13, 1, 49, tzinfo=timezone.utc), id_gestion_fases=300)))
    return SimpleNamespace(uc=uc, db=db, aud=aud, mov=mov, repo=repo, esperas=esperas)


# ─────────────────────────────── TC-M05-048: registro ───────────────────────────────
def test_048a_fallo_de_bd_reintenta_3_veces_y_luego_500(monkeypatch):
    t = _registro(InfrastructureError(code="BD_FALLO", message="fallo inyectado al guardar"), monkeypatch)
    with pytest.raises(InfrastructureError):   # el handler global lo responde como 500
        t.uc.execute(_dto(), USUARIO)
    assert t.repo.intentos == 3, "3 intentos de persistencia (CA-6)"
    assert t.db.rollbacks >= 3, "cada intento fallido revierte toda la transacción"
    assert t.mov.llamadas == [], "el acumulado no se toca si el registro no se guardó"


def test_048b_backoff_de_1_3_y_5_segundos(monkeypatch):
    """La ficha pide 1 s / 3 s / 5 s. Con 3 intentos solo hay 2 esperas: el 5 s nunca se aplica."""
    t = _registro(InfrastructureError(code="BD_FALLO", message="fallo inyectado"), monkeypatch)
    with pytest.raises(InfrastructureError):
        t.uc.execute(_dto(), USUARIO)
    assert t.esperas == [1, 3, 5], f"esperas aplicadas entre reintentos: {t.esperas}"


def test_048c_tras_agotar_reintentos_queda_registro_fallido_con_3_reintentos(monkeypatch):
    t = _registro(InfrastructureError(code="BD_FALLO", message="fallo inyectado al guardar"), monkeypatch)
    with pytest.raises(InfrastructureError):
        t.uc.execute(_dto(), USUARIO)
    assert len(t.aud.eventos) == 1
    ev = t.aud.eventos[0]
    assert ev.tipo_operacion == "REGISTRO_FALLIDO" and ev.resultado == "FALLIDO"
    assert ev.numero_reintentos == 3 and ev.id_usuario == 143 and ev.id_gestion_fases == 300
    assert "fallo inyectado" in ev.detalle_causa


# ─────────────────────────────── TC-M05-048: corrección con bloqueo ───────────────────────────────
def _original():
    return RegistroSuministroDirecto(
        id_activo_biologico=825, id_ciclo_productivo=4, id_gestion_fases=300, tipo_suministro="SERVICIO_VETERINARIO",
        cantidad=Decimal("1"), unidad_medida="servicio", precio_unitario_resuelto=Decimal("150000"),
        costo_registro=Decimal("150000"), origen_precio="MANUAL", fecha_aplicacion=HOY - timedelta(days=2),
        naturaleza_costo="MANTENIMIENTO", id_idempotencia=uuid4(), tipo_operacion="REGISTRO", id_registro_suministro=uuid4())


def test_048e_correccion_con_bloqueo_responde_409_conflicto_concurrencia(monkeypatch):
    monkeypatch.setattr(mod_corr.time, "sleep", lambda s: None)
    bloqueo = InfrastructureError(code="BD_BLOQUEO", message="could not obtain lock on row",
                                  original_error=SimpleNamespace(orig=pg_errors.LockNotAvailable()))
    intentos = []

    def obtener_bloqueando(id_gf):
        intentos.append(id_gf)
        raise bloqueo

    db, aud, mov = Sesion(), Auditoria(), Movimiento()
    original = _original()
    uc = RegistrarCorreccionSuministroUseCase(
        db=db, registro_repo=RepoQueFalla(None, original=original), auditoria_port=aud, movimiento=mov,
        acumulado_repo=SimpleNamespace(obtener_bloqueando=obtener_bloqueando),
        ciclo_port=SimpleNamespace(obtener_por_id=lambda id_: FaseProductiva(
            id_gestion_fases=300, id_activo_biologico=825, id_ciclo_productivo=4,
            fecha_inicio=datetime(2026, 10, 13, tzinfo=timezone.utc), fecha_finalizacion=None, es_activa=True)))
    dto = RegistrarCorreccionSuministroDTO(id_idempotencia=uuid4(), cantidad=Decimal("1"), precio_unitario=Decimal("-30000"),
                                           justificacion_precio="Descuento acordado en la factura",
                                           motivo_correccion="Ajuste por descuento comercial de la factura")
    with pytest.raises(ConflictError) as exc:
        uc.execute(original.id_registro_suministro, dto, USUARIO)
    assert exc.value.code == "CONFLICTO_CONCURRENCIA"
    assert len(intentos) == 3, "3 intentos de tomar el bloqueo del acumulado"
    assert mov.llamadas == [], "sin bloqueo no se mueve el acumulado"
    assert [e.tipo_operacion for e in aud.eventos] == ["CONFLICTO_CONCURRENCIA"], "evento del mismo nombre en auditoría"
