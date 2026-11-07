# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-06 | Arekkazu | M07 RF-98/RF-SSO02: ciclo de vida del contrato y token de canal (sin BD) |
"""Contrato AAEF (RF-98) y token de canal (RF-SSO02) sin base de datos."""
from datetime import date, datetime, timedelta, timezone

import pytest

from src.accounting_integration.domain.entities.contrato import (
    AnexoMapeo,
    VersionContrato,
    exigir_cupo,
    motivo_bloqueo_activacion,
    resolver_version,
    versiones_a_deprecar,
)
from src.accounting_integration.domain.entities.evento_integracion import EventoIntegracion
from src.shared import jwt as jwt_module
from src.shared.errors import AppError

AHORA = datetime(2026, 11, 6, tzinfo=timezone.utc)


def _contrato(version, estado="PENDIENTE", tipo="MAJOR", id_=None):
    return VersionContrato(id_ or int(version.replace(".", "")), version, tipo, date(2026, 11, 1), 1, ["COMPRAS"],
                           periodo_gracia_dias=90 if tipo == "MAJOR" else None, estado=estado)


def test_transiciones_solo_hacia_adelante_y_sin_reactivar():
    c = _contrato("3.0")
    c.activar(AHORA)
    c.deprecar(AHORA, 30)
    assert c.fecha_inactivacion == AHORA + timedelta(days=30)
    with pytest.raises(AppError) as gracia:
        c.inactivar(AHORA + timedelta(days=1))
    assert gracia.value.code == "PERIODO_GRACIA_VIGENTE"
    c.inactivar(AHORA + timedelta(days=31))
    with pytest.raises(AppError) as reactivar:
        c.activar(AHORA)
    assert reactivar.value.code == "REACTIVACION_NO_PERMITIDA"
    with pytest.raises(AppError):
        _contrato("3.1").deprecar(AHORA, 90)  # salto PENDIENTE -> DEPRECADO


def test_major_depreca_las_activas_menores_y_minor_no():
    vieja = _contrato("3.0", "ACTIVO")
    assert versiones_a_deprecar(_contrato("4.0"), [vieja]) == [vieja]
    assert versiones_a_deprecar(_contrato("3.1", tipo="MINOR"), [vieja]) == []


def test_limite_de_dos_vigentes_dice_cual_retirar():
    with pytest.raises(AppError) as e:
        exigir_cupo(_contrato("5.0"), [_contrato("3.0", "DEPRECADO"), _contrato("4.0", "ACTIVO")])
    assert e.value.code == "LIMITE_VERSIONES_EXCEDIDO" and "3.0" in e.value.message


def test_resolucion_de_version():
    vigentes = [_contrato("3.0", "DEPRECADO"), _contrato("3.1", "ACTIVO", "MINOR"), _contrato("2.0", "INACTIVO")]
    assert resolver_version(vigentes, None).contrato_version == "3.1"
    assert resolver_version(vigentes, "3.0").contrato_version == "3.0"  # deprecada sigue respondiendo
    for pedida, codigo in (("2.0", "VERSION_INACTIVA"), ("9.9", "VERSION_NO_REGISTRADA"), ("3", "VERSION_FORMATO_INVALIDO")):
        with pytest.raises(AppError) as e:
            resolver_version(vigentes, pedida)
        assert e.value.code == codigo
    with pytest.raises(AppError) as sin_activa:
        resolver_version([_contrato("3.0", "PENDIENTE")], None)
    assert sin_activa.value.code == "CONTRATO_NO_ACTIVO"


def test_anexo_en_revision_solo_sirve_fuera_de_produccion():
    anexo = AnexoMapeo(1, "AAEF-3.0", "3.0", "docs/anexo.md", "a" * 64, estado="EN_REVISION")
    assert motivo_bloqueo_activacion(_contrato("3.0"), anexo, es_produccion=False) is None
    assert motivo_bloqueo_activacion(_contrato("3.0"), anexo, es_produccion=True)


def test_evento_de_auditoria_detecta_alteraciones_y_campos_faltantes():
    evento = EventoIntegracion(tipo_evento="CONTRATO_ACTIVADO", version_contrato="3.0", fecha_evento=AHORA, fecha_registro=AHORA)
    original = evento.hash_integridad
    alterado = EventoIntegracion(**{**evento.__dict__, "version_contrato": "3.1"})
    assert alterado.hash_integridad != original and evento.faltantes() == []
    assert EventoIntegracion(tipo_evento="CONTRATO_ACTIVADO").faltantes() == ["version_contrato"]


def test_token_de_canal_no_sirve_para_la_web_y_al_reves(monkeypatch):
    monkeypatch.setattr(jwt_module, "_SECRET_KEY", "clave-de-prueba")
    canal, segundos = jwt_module.create_token_canal(7, 5, 1, "AGROFUSION", 15)
    assert segundos == 900 and jwt_module.verify_token_canal(canal)["cli"] == 1
    with pytest.raises(AppError):
        jwt_module.verify_token(canal)  # la app web lo rechaza (audiencia)
    web, _ = jwt_module.create_token(1, 7, 5)
    with pytest.raises(AppError) as e:
        jwt_module.verify_token_canal(web)
    assert e.value.code == "NO_AUTENTICADO"
