# | Fecha      | Nombre      | Que se hizo |
# |------------|-------------|-------------|
# | 2026-11-17 | Laura López | TC-M07-G052 E3: validaciones aisladas incompleto/duplicado/no catalogado (sin BD TEST). |
"""E3 (TC-M07-102-003) — rechazo de eventos inválidos en unidad aislada.

Código bajo prueba:
  - EventoIntegracion.faltantes()  (RF-102 8.2 / FA-8)
  - SqlAlchemyAuditoriaIntegracionRepository.registrar()

Hallazgos de implementación (inspección, no invención):
  - Incompleto: se valida en registrar() ANTES de escribir(); InfrastructureError AUDITORIA_INCOMPLETA.
  - Duplicado: no hay if/raise de duplicados en Python; solo PK eventos_integracion_pkey en migración.
  - No catalogado: faltantes() usa _OBLIGATORIOS.get(tipo, ()) → tipo desconocido no falla en Python;
    el CAST a enum_evento_integracion_tipo_evento ocurre en el INSERT (PostgreSQL).

Sin BD TEST compartida. Duplicado/no catalogado a nivel persistencia requieren BD aislada PostgreSQL.

    python -m pytest tests/Test_Testing/Test_Modulo7/RF-102/TC-M07-G052/test_tc_m07_g52_e3_validaciones_aisladas.py -v
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.accounting_integration.domain.entities.evento_integracion import (
    _OBLIGATORIOS,
    EventoIntegracion,
)
from src.accounting_integration.infrastructure.repositories.auditoria_integracion_repository import (
    SqlAlchemyAuditoriaIntegracionRepository,
)
from src.shared.errors import InfrastructureError

AHORA = datetime(2026, 11, 17, 12, 0, tzinfo=timezone.utc)
TIPO_DESCONOCIDO = "TIPO_NO_CATALOGADO_QA_G52"
UUID_FICTICIO = "00000000-0000-4000-8000-000000000052"


def _repo() -> SqlAlchemyAuditoriaIntegracionRepository:
    return SqlAlchemyAuditoriaIntegracionRepository(db=MagicMock(name="db_aislada"))


def _completo_contrato() -> EventoIntegracion:
    return EventoIntegracion(
        tipo_evento="CONTRATO_ACTIVADO",
        version_contrato="3.0",
        fecha_evento=AHORA,
        fecha_registro=AHORA,
        id_evento_integracion=str(uuid.uuid4()),
    )


class TestE31EventoIncompleto:
    """E3.1 — campo obligatorio ausente → AUDITORIA_INCOMPLETA y sin persistencia."""

    def test_faltantes_detecta_version_contrato(self):
        ev = EventoIntegracion(tipo_evento="CONTRATO_ACTIVADO", fecha_evento=AHORA, fecha_registro=AHORA)
        assert ev.faltantes() == ["version_contrato"]

    def test_registrar_rechaza_incompleto_sin_llamar_escribir(self):
        ev = EventoIntegracion(
            tipo_evento="CONTRATO_ACTIVADO",
            fecha_evento=AHORA,
            fecha_registro=AHORA,
            id_evento_integracion=UUID_FICTICIO,
        )
        assert "version_contrato" in ev.faltantes()

        with patch(
            "src.accounting_integration.infrastructure.repositories.auditoria_integracion_repository.escribir"
        ) as mock_escribir:
            with pytest.raises(InfrastructureError) as exc:
                _repo().registrar(ev)
            assert exc.value.code == "AUDITORIA_INCOMPLETA"
            assert "version_contrato" in (exc.value.message or "")
            mock_escribir.assert_not_called()

    def test_registrar_paquete_aaef_incompleto_sin_persistir(self):
        # Solo tipo: faltan todos los de PAQUETE_AAEF_CONSULTADO
        ev = EventoIntegracion(
            tipo_evento="PAQUETE_AAEF_CONSULTADO",
            fecha_evento=AHORA,
            fecha_registro=AHORA,
            id_evento_integracion=str(uuid.uuid4()),
        )
        esperados = list(_OBLIGATORIOS["PAQUETE_AAEF_CONSULTADO"])
        assert ev.faltantes() == esperados

        with patch(
            "src.accounting_integration.infrastructure.repositories.auditoria_integracion_repository.escribir"
        ) as mock_escribir:
            with pytest.raises(InfrastructureError) as exc:
                _repo().registrar(ev)
            assert exc.value.code == "AUDITORIA_INCOMPLETA"
            mock_escribir.assert_not_called()

    def test_registrar_completo_si_invoca_escribir(self):
        ev = _completo_contrato()
        assert ev.faltantes() == []
        with patch(
            "src.accounting_integration.infrastructure.repositories.auditoria_integracion_repository.escribir"
        ) as mock_escribir, patch(
            "src.accounting_integration.infrastructure.repositories.auditoria_integracion_repository.a_json",
            return_value=None,
        ):
            _repo().registrar(ev)
            mock_escribir.assert_called_once()


class TestE32EventoDuplicado:
    """E3.2 — no hay validación de duplicados en registrar(); solo PK de BD.

    Este módulo demuestra la ausencia de lógica de aplicación. No prueba el PK real
    (requeriría PostgreSQL aislado). UUID sintético; sin datos de TEST.
    """

    def test_registrar_no_contiene_validacion_de_duplicados(self):
        import inspect
        import re

        from src.accounting_integration.infrastructure.repositories import (
            auditoria_integracion_repository as mod,
        )

        fuente = inspect.getsource(mod.SqlAlchemyAuditoriaIntegracionRepository.registrar)
        # Única guarda de negocio: faltantes / AUDITORIA_INCOMPLETA
        assert "AUDITORIA_INCOMPLETA" in fuente
        assert "faltantes" in fuente
        assert not re.search(r"duplicad", fuente, re.I)
        assert "UNIQUE" not in fuente
        assert "ya existe" not in fuente.lower()

    def test_dos_registros_mismo_uuid_llaman_escribir_dos_veces_en_capa_python(self):
        """Sin BD, la capa Python no rechaza el segundo intento: escribir se invoca 2 veces."""
        mismo_id = "11111111-1111-4111-8111-111111111152"
        ev1 = EventoIntegracion(
            tipo_evento="CONTRATO_ACTIVADO",
            version_contrato="3.0",
            fecha_evento=AHORA,
            fecha_registro=AHORA,
            id_evento_integracion=mismo_id,
        )
        ev2 = EventoIntegracion(
            tipo_evento="CONTRATO_ACTIVADO",
            version_contrato="3.0",
            fecha_evento=AHORA,
            fecha_registro=AHORA,
            id_evento_integracion=mismo_id,
        )
        assert ev1.id_evento_integracion == ev2.id_evento_integracion

        with patch(
            "src.accounting_integration.infrastructure.repositories.auditoria_integracion_repository.escribir"
        ) as mock_escribir, patch(
            "src.accounting_integration.infrastructure.repositories.auditoria_integracion_repository.a_json",
            return_value=None,
        ):
            repo = _repo()
            repo.registrar(ev1)
            repo.registrar(ev2)
            assert mock_escribir.call_count == 2

    def test_pk_documentada_en_migracion_no_ejecutada_aqui(self):
        from pathlib import Path

        migracion = Path(__file__).resolve().parents[5] / (
            "alembic/versions/94b14a6931d6_m07_integracion_aaef_rfc017.py"
        )
        texto = migracion.read_text(encoding="utf-8")
        assert "CONSTRAINT eventos_integracion_pkey PRIMARY KEY (id_evento_integracion)" in texto


class TestE33TipoNoCatalogado:
    """E3.3 — tipo fuera de catálogo: Python no rechaza; CAST enum es de PostgreSQL."""

    def test_faltantes_vacio_si_tipo_no_esta_en_obligatorios(self):
        ev = EventoIntegracion(
            tipo_evento=TIPO_DESCONOCIDO,
            fecha_evento=AHORA,
            fecha_registro=AHORA,
            id_evento_integracion=str(uuid.uuid4()),
        )
        assert TIPO_DESCONOCIDO not in _OBLIGATORIOS
        assert ev.faltantes() == []

    def test_registrar_intenta_persistir_tipo_no_catalogado_en_capa_python(self):
        """Demuestra que NO hay rechazo previo en registrar(); escribir SÍ se invoca."""
        ev = EventoIntegracion(
            tipo_evento=TIPO_DESCONOCIDO,
            fecha_evento=AHORA,
            fecha_registro=AHORA,
            id_evento_integracion=str(uuid.uuid4()),
        )
        with patch(
            "src.accounting_integration.infrastructure.repositories.auditoria_integracion_repository.escribir"
        ) as mock_escribir, patch(
            "src.accounting_integration.infrastructure.repositories.auditoria_integracion_repository.a_json",
            return_value=None,
        ):
            _repo().registrar(ev)
            mock_escribir.assert_called_once()

    def test_insert_usa_cast_enum_postgres(self):
        from src.accounting_integration.infrastructure.repositories import (
            auditoria_integracion_repository as mod,
        )

        assert "enum_evento_integracion_tipo_evento" in mod._INSERT
        assert "CAST(:tipo_evento AS modulo7.enum_evento_integracion_tipo_evento)" in mod._INSERT

    def test_tipo_desconocido_no_esta_en_catalogo_migracion(self):
        from pathlib import Path
        import ast

        migracion = Path(__file__).resolve().parents[5] / (
            "alembic/versions/94b14a6931d6_m07_integracion_aaef_rfc017.py"
        )
        # Extrae la tupla _TIPOS_EVENTO del archivo sin ejecutar upgrade()
        modulo = ast.parse(migracion.read_text(encoding="utf-8"))
        tipos = None
        for nodo in modulo.body:
            if isinstance(nodo, ast.Assign):
                for t in nodo.targets:
                    if isinstance(t, ast.Name) and t.id == "_TIPOS_EVENTO":
                        tipos = ast.literal_eval(nodo.value)
        assert tipos is not None
        assert TIPO_DESCONOCIDO not in tipos
        assert "CONTRATO_ACTIVADO" in tipos
