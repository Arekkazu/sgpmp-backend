"""Issue #265 (SEG-M02-01): un fallo al escribir en la bitácora RF-52 ya no
puede quedar en silencio (`except Exception: pass`). Verifica que
`registrar_evento_bitacora` no bloquea la operación de negocio pero deja
rastro: log de aplicación con severidad CRITICAL y el evento completo en el
buffer local (RF-52 E1; su recuperación está en test_gaps_flujo_alterno_m02.py).
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from src.biological_assets.application.use_cases import _registrar_evento_bitacora as bitacora
from src.biological_assets.application.use_cases._registrar_evento_bitacora import (
    registrar_evento_bitacora,
)
from src.biological_assets.domain.entities.activo_biologico import EventoAuditoria


class DbFake:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


class BitacoraRepoOk:
    def __init__(self) -> None:
        self.eventos: list[EventoAuditoria] = []

    def registrar(self, evento: EventoAuditoria) -> None:
        self.eventos.append(evento)


class BitacoraRepoFalla:
    def registrar(self, evento: EventoAuditoria) -> None:
        raise RuntimeError('conexion agotada')


def _evento(**overrides) -> EventoAuditoria:
    base = dict(
        rf_origen='RF33',
        tipo_evento='ACTIVO_REGISTRADO',
        clasificacion_biologica='GESTION_OPERATIVA',
        resultado='EXITOSO',
        severidad_log='INFO',
        timestamp_evento=datetime.now(timezone.utc),
        id_activo_biologico=42,
        id_usuario_responsable=7,
    )
    base.update(overrides)
    return EventoAuditoria(**base)


def test_sin_bitacora_repo_no_hace_nada() -> None:
    db = DbFake()
    registrar_evento_bitacora(None, db, _evento())
    assert db.commits == 0
    assert db.rollbacks == 0


def test_escritura_exitosa_comitea() -> None:
    db = DbFake()
    repo = BitacoraRepoOk()
    registrar_evento_bitacora(repo, db, _evento())
    assert len(repo.eventos) == 1
    assert db.commits == 1
    assert db.rollbacks == 0


def test_fallo_no_bloquea_operacion_y_deja_rastro(caplog) -> None:
    db = DbFake()
    repo = BitacoraRepoFalla()
    evento = _evento(
        tipo_evento='ACTIVO_REGISTRO_FALLIDO',
        id_activo_biologico=99,
        id_usuario_responsable=3,
    )

    with caplog.at_level(logging.ERROR):
        registrar_evento_bitacora(repo, db, evento)  # nunca debe lanzar

    assert db.rollbacks == 1
    assert db.commits == 0
    assert any('Fallo al registrar evento de auditoría RF-52' in r.message for r in caplog.records)

    linea = json.loads(bitacora._buffer().read_text().strip().splitlines()[-1])
    assert linea['evento']['tipo_evento'] == 'ACTIVO_REGISTRO_FALLIDO'
    assert linea['evento']['id_activo_biologico'] == 99
    assert linea['evento']['id_usuario_responsable'] == 3
    assert 'conexion agotada' in linea['error']
