# | Fecha      | Nombre      | Que se hizo |
# |------------|-------------|-------------|
# | 2026-11-17 | Laura López | TC-M07-G053: hash SHA-256, CORRUPTO, alerta y ausencia de enmascaramiento HMAC. |
"""Pruebas unitarias RF-102 integridad / detección / enmascaramiento (sin BD TEST).

Código:
  - EventoIntegracion.hash_integridad → hash_sha256(asdict campos; property excluida)
  - ConsultarAuditoriaIntegracionUseCase._presentar → INTEGRO/CORRUPTO + alertar
  - ClienteExterno.snapshot / SECRETO_ROTADO: no guardan secreto en claro
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, fields
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from src.accounting_integration.application.use_cases.auditoria.consultar_auditoria_integracion_use_case import (
    ConsultarAuditoriaIntegracionUseCase,
)
from src.accounting_integration.domain.entities.cliente_externo import ClienteExterno
from src.accounting_integration.domain.entities.evento_integracion import EventoIntegracion
from src.financial_valuation.domain.services.nic41 import hash_sha256

AHORA = datetime(2026, 11, 17, 20, 0, tzinfo=timezone.utc)


def _evento(**kwargs) -> EventoIntegracion:
    base = dict(
        tipo_evento="CONTRATO_ACTIVADO",
        version_contrato="3.0",
        fecha_evento=AHORA,
        fecha_registro=AHORA,
        id_evento_integracion="55555555-5555-4555-8555-555555555553",
    )
    base.update(kwargs)
    return EventoIntegracion(**base)


class TestE1HashSha256:
    def test_algoritmo_es_sha256_json_canonico(self):
        ev = _evento()
        payload = {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in asdict(ev).items()}
        esperado = hashlib.sha256(
            json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        assert ev.hash_integridad == esperado == hash_sha256(payload)
        assert len(ev.hash_integridad) == 64

    def test_hash_integridad_no_es_campo_del_dataclass(self):
        nombres = {f.name for f in fields(EventoIntegracion)}
        assert "hash_integridad" not in nombres
        assert "hash_integridad" not in asdict(_evento())

    def test_cambio_de_campo_cambia_el_hash(self):
        a = _evento(version_contrato="3.0")
        b = _evento(version_contrato="3.1")
        assert a.hash_integridad != b.hash_integridad


class TestE2DeteccionCorrupcion:
    def test_presentar_marca_corrupto_y_alerta(self):
        ev = _evento()
        hash_ok = ev.hash_integridad
        hash_malo = "0" * 64
        assert hash_ok != hash_malo
        alertas = []
        uc = ConsultarAuditoriaIntegracionUseCase(auditoria=MagicMock(), alertar=lambda m, d: alertas.append((m, d)))
        filas = [(ev, hash_malo, {"correo_usuario": None, "nombre_cliente": None})]
        out = uc._presentar(filas, restringida=False)
        assert out[0]["integridad"] == "CORRUPTO"
        assert alertas and "alterados" in alertas[0][0].lower()
        assert ev.id_evento_integracion in alertas[0][1]["id_eventos"]

    def test_presentar_integro_sin_alerta(self):
        ev = _evento()
        alertas = []
        uc = ConsultarAuditoriaIntegracionUseCase(auditoria=MagicMock(), alertar=lambda m, d: alertas.append((m, d)))
        out = uc._presentar([(ev, ev.hash_integridad, {})], restringida=False)
        assert out[0]["integridad"] == "INTEGRO"
        assert alertas == []


class TestE4ProteccionSensible:
    def test_snapshot_cliente_no_incluye_secreto(self):
        c = ClienteExterno(
            id_cliente_externo=1, codigo="QA", nombre="QA", identificador_publico="qa-g53",
            estado="ACTIVO", tipo="SISTEMA_INTERMEDIARIO", ip_permitida=None,
            ttl_token_canal_minutos=15, canales={"CONSULTA_AAEF": 60},
        )
        snap = c.snapshot()
        # Claves esperadas sin secretos; ttl_token_canal_minutos es TTL (no un token).
        assert set(snap.keys()) == {"estado", "ip_permitida", "ttl_token_canal_minutos", "canales"}
        texto = json.dumps(snap).lower()
        assert "client_secret" not in texto and "password" not in texto
        assert "access_token" not in texto and "bearer " not in texto

    def test_no_existe_enmascaramiento_hmac_ocho_caracteres_en_m07(self):
        """RF-102 ficha menciona HMAC[:8]+***; en accounting_integration no hay esa lógica."""
        from pathlib import Path
        root = Path(__file__).resolve().parents[4] / "src/accounting_integration"
        hits = []
        for p in root.rglob("*.py"):
            t = p.read_text(encoding="utf-8", errors="ignore").lower()
            if "hmac" in t or "enmascar" in t or '[:8] + "***"' in t or "[:8]+'***'" in t:
                hits.append(str(p.relative_to(root.parent.parent)))
        assert hits == [], f"Se encontró posible enmascaramiento HMAC: {hits}"

    def test_vista_restringida_oculta_ip_y_detalle(self):
        ev = _evento(ip_origen="203.0.113.10", json_detalle={"token": "TEST_SECRET_123456"})
        uc = ConsultarAuditoriaIntegracionUseCase(auditoria=MagicMock(), alertar=lambda *_: None)
        out = uc._presentar([(ev, ev.hash_integridad, {})], restringida=True)
        assert out[0]["ip_origen"] is None and out[0]["json_detalle"] is None
